# -*- coding: utf-8 -*-
"""DSP FT8 (logx_ft8_dsp.js) — synthèse GFSK + synchro Costas + démodulation.

Contrairement au codec (test_ft8_codec.py), il n'existe pas de "vecteur de
test" pour une forme d'onde audio — seule la question « ça se décode ou
pas » a un sens. Même principe que test_rtty_decodeur.py : on encode un
texte, on synthétise le signal, on le décode, on compare. Le pipeline est
exercé de bout en bout (codec + DSP), sans radio.

Ce que ces tests NE prouvent PAS : le comportement sur un signal réel reçu
par une vraie radio (QSB, distorsion audio de la chaîne SSB, offset Doppler,
horloge mal synchronisée). Ça reste à éprouver sur l'air — voir les notes de
conception de logx_ft8_dsp.js sur les compromis de recherche de synchro.
"""
import json
import os

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CODEC_JS = os.path.join(CONCOURS, 'logx_ft8_codec.js')
DSP_JS = os.path.join(CONCOURS, 'logx_ft8_dsp.js')

py_mini_racer = pytest.importorskip('py_mini_racer')


@pytest.fixture(scope='module')
def moteur():
    ctx = py_mini_racer.MiniRacer()
    for path in (CODEC_JS, DSP_JS):
        with open(path, encoding='utf-8') as f:
            ctx.eval(f.read())
    # Bruit blanc reproductible (Math.imul pour un vrai wraparound 32 bits —
    # voir le piège documenté dans test_ft8_codec.py, même précaution ici).
    ctx.eval("""
    function avecBruit(sig, niveau, graine){
      var s = graine || 1, out = new Float32Array(sig.length);
      for(var i=0;i<sig.length;i++){
        s = (Math.imul(s,1103515245) + 12345) & 0x7fffffff;
        out[i] = sig[i] + ((s/0x7fffffff)*2-1)*niveau;
      }
      return out;
    }
    function allerRetourAudio(texte, sampleRate, toneHz0, niveauBruit, graine){
      var enc = ft8EncodeMessage(texte, null);
      if(!enc) return {ok:false, reason:'encode a echoue'};
      var wave = ft8SynthesizeGfsk(enc.symbols, {sampleRate: sampleRate, toneHz0: toneHz0});
      if(niveauBruit) wave = avecBruit(wave, niveauBruit, graine || 1);
      var res = ft8DecodeAudio(wave, sampleRate, null, {});
      if(!res) return {ok:false, reason:'decode audio a echoue (pas de synchro/CRC)'};
      return {ok: res.text === texte, decoded: res.text, freqHz: res.freqHz};
    }""")
    return ctx


def _round_trip(moteur, texte, sample_rate=12000, tone_hz0=1500, bruit=0, graine=1):
    return json.loads(moteur.eval(
        f'JSON.stringify(allerRetourAudio({json.dumps(texte)}, {sample_rate}, {tone_hz0}, {bruit}, {graine}))'
    ))


# ─── Synthèse : dimensions et plausibilité du signal ─────────────────────────

def test_synthese_produit_la_bonne_duree(moteur):
    r = json.loads(moteur.eval("""
    JSON.stringify((function(){
      var enc = ft8EncodeMessage('CQ K1JT FN20', null);
      var wave = ft8SynthesizeGfsk(enc.symbols, {sampleRate: 12000});
      return {len: wave.length, attendu: 79 * ft8SamplesPerSymbol(12000)};
    })())"""))
    assert r['len'] == r['attendu']
    # 79 symboles * 0.160s = 12.64s, cohérent avec la spec FT8.
    assert abs(r['len'] / 12000 - 12.64) < 0.01


def test_synthese_reste_dans_lamplitude(moteur):
    r = json.loads(moteur.eval("""
    JSON.stringify((function(){
      var enc = ft8EncodeMessage('CQ K1JT FN20', null);
      var wave = ft8SynthesizeGfsk(enc.symbols, {sampleRate: 12000, amplitude: 0.9});
      var max = 0;
      for(var i=0;i<wave.length;i++) if(Math.abs(wave[i]) > max) max = Math.abs(wave[i]);
      return {max: max};
    })())"""))
    assert r['max'] <= 0.9 + 1e-6


# ─── Aller-retour complet, sans bruit ─────────────────────────────────────────

@pytest.mark.parametrize('texte', [
    'CQ K1JT FN20',
    'K1JT K9AN EN50',
    'K9AN K1JT -10',
    'K1JT K9AN R-12',
    'K9AN K1JT RRR',
    'K1JT K9AN 73',
])
def test_aller_retour_audio_sans_bruit(moteur, texte):
    r = _round_trip(moteur, texte)
    assert r['ok'], f'{texte!r} -> {r.get("decoded") or r.get("reason")!r}'


def test_frequence_detectee_correspond_au_ton0(moteur):
    r = _round_trip(moteur, 'CQ K1JT FN20', tone_hz0=1500)
    assert r['ok']
    assert abs(r['freqHz'] - 1500) < 2.0   # résolution de recherche ~3.125 Hz


# ─── Robustesse : léger décalage de fréquence porteuse ──────────────────────
# Une vraie station n'est jamais exactement calée sur le ton 0 attendu — la
# recherche de synchro doit retrouver le signal même décalé de quelques Hz.

@pytest.mark.parametrize('tone_hz0', [300, 1000, 1500, 2200, 2800])
def test_aller_retour_sur_toute_la_bande_passante(moteur, tone_hz0):
    r = _round_trip(moteur, 'CQ K1JT FN20', tone_hz0=tone_hz0)
    assert r['ok'], f'ton0={tone_hz0}Hz -> {r.get("decoded") or r.get("reason")!r}'


# ─── Robustesse : bruit ajouté ────────────────────────────────────────────────

@pytest.mark.parametrize('niveau', [0.05, 0.15])
def test_aller_retour_avec_bruit(moteur, niveau):
    r = _round_trip(moteur, 'CQ K1JT FN20', bruit=niveau)
    assert r['ok'], f'bruit={niveau} -> {r.get("decoded") or r.get("reason")!r}'


def test_bruit_ecrasant_ne_renvoie_jamais_un_texte_faux(moteur):
    """FT8 est conçu pour du très faible rapport signal/bruit (corrélation
    Costas cohérente + gain de codage LDPC) : même avec un bruit 3x plus
    fort que le signal, un décodage réussi est plausible — CE N'EST PAS un
    bug (première version de ce test le supposait à tort, corrigé après
    l'avoir vu échouer sur un décodage qui avait en fait réussi). Ce qui
    compte réellement : jamais de plantage, et jamais un texte FAUX
    accepté à tort (le CRC-14 a une probabilité ~1/16384 de fausse
    acceptation — un échec propre (ok=False) reste le résultat le plus
    probable à ce niveau de bruit, mais un succès correct est acceptable."""
    r = _round_trip(moteur, 'CQ K1JT FN20', bruit=3.0)
    if r['ok'] is not True:
        assert r.get('decoded') in (None, '')
    else:
        assert r['decoded'] == 'CQ K1JT FN20'


# ─── Décodage multi-signaux (ft8FindAllSync/ft8DecodeAudioAll) ──────────────
# Une vraie bande FT8 porte des dizaines de signaux simultanés dans la même
# fenêtre de 15s — un décodeur qui n'en trouve qu'un seul par cycle serait de
# peu d'utilité réelle en contest. Deux messages synthétisés à des
# fréquences différentes, sommés dans le MÊME buffer (mélange additif, comme
# deux stations reçues en même temps), doivent tous les deux ressortir.

def test_deux_signaux_simultanes_sont_tous_les_deux_decodes(moteur):
    r = json.loads(moteur.eval("""
    JSON.stringify((function(){
      var enc1 = ft8EncodeMessage('CQ K1JT FN20', null);
      var enc2 = ft8EncodeMessage('K1JT K9AN EN50', null);
      var w1 = ft8SynthesizeGfsk(enc1.symbols, {sampleRate: 12000, toneHz0: 800});
      var w2 = ft8SynthesizeGfsk(enc2.symbols, {sampleRate: 12000, toneHz0: 2000});
      var mix = new Float32Array(w1.length);
      for(var i=0;i<mix.length;i++) mix[i] = w1[i] + w2[i];
      var results = ft8DecodeAudioAll(mix, 12000, null, {});
      return results.map(function(r){ return {text: r.text, freqHz: r.freqHz}; });
    })())"""))
    textes = [x['text'] for x in r]
    assert 'CQ K1JT FN20' in textes, f'signal 1 manquant, decodes: {textes}'
    assert 'K1JT K9AN EN50' in textes, f'signal 2 manquant, decodes: {textes}'


def test_decode_all_ne_renvoie_jamais_de_doublon_de_texte(moteur):
    """Deux pics locaux voisins du MÊME signal ne doivent pas ressortir comme
    deux décodages distincts (dédoublonnage par texte, voir ft8DecodeAudioAll)."""
    r = json.loads(moteur.eval("""
    JSON.stringify((function(){
      var enc = ft8EncodeMessage('CQ K1JT FN20', null);
      var wave = ft8SynthesizeGfsk(enc.symbols, {sampleRate: 12000, toneHz0: 1500});
      var results = ft8DecodeAudioAll(wave, 12000, null, {});
      return results.map(function(r){ return r.text; });
    })())"""))
    assert r.count('CQ K1JT FN20') == 1
