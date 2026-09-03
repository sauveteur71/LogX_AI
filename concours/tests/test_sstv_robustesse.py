# -*- coding: utf-8 -*-
"""Banc de robustesse SSTV : courbe SNR -> qualite, mesuree sur signal
synthetique bruite. Sert de baseline chiffree AVANT toute modif DSP, puis de
garde-fou de non-regression et de mesure A/B des leviers A1-A3.

Ce que ce banc NE prouve PAS : le QRM/QSB reel sur l'air (bruit non gaussien,
selectivite, fading correle). Il chiffre une robustesse RELATIVE (lever on vs
off, avant vs apres) sur un canal bruit-blanc — suffisant pour decider
« gain chiffre ou rejet » de chaque lever, pas pour certifier une perf terrain.

BASELINE CHIFFREE (2026-09-03, avant tout levier DSP A1-A3) — sortie REELLE de
`python -m pytest concours/tests/test_sstv_robustesse.py::test_baseline_snr_decrochage_actuel -v -s`,
balayage {snr, mode, lignes, mae, utilisable} sur 24 lignes, SEUIL_UTILISABLE=25 :

BASELINE M1     decrochage=9 dB  courbe=[(30, 1.3), (27, 1.6), (24, 2.1), (21, 2.8), (18, 3.8), (15, 5.2), (12, 7.1), (9, 9.7), (6, None), (3, None), (0, None)]
BASELINE M2     decrochage=9 dB  courbe=[(30, 2.0), (27, 2.3), (24, 2.8), (21, 3.5), (18, 4.6), (15, 6.1), (12, 8.2), (9, 11.2), (6, None), (3, None), (0, None)]
BASELINE S1     decrochage=9 dB  courbe=[(30, 1.4), (27, 1.7), (24, 2.2), (21, 2.9), (18, 3.9), (15, 5.3), (12, 7.4), (9, 10.2), (6, None), (3, None), (0, None)]
BASELINE S2     decrochage=9 dB  courbe=[(30, 1.6), (27, 2.0), (24, 2.5), (21, 3.3), (18, 4.4), (15, 6.0), (12, 8.4), (9, 11.7), (6, None), (3, None), (0, None)]
BASELINE R36    decrochage=9 dB  courbe=[(30, 8.8), (27, 9.0), (24, 9.5), (21, 10.4), (18, 11.8), (15, 14.2), (12, 17.3), (9, 22.9), (6, None), (3, None), (0, None)]
BASELINE R72    decrochage=9 dB  courbe=[(30, 4.1), (27, 4.5), (24, 5.3), (21, 6.5), (18, 8.4), (15, 11.1), (12, 14.9), (9, 20.2), (6, None), (3, None), (0, None)]
BASELINE PD90   decrochage=9 dB  courbe=[(30, 2.2), (27, 2.8), (24, 3.6), (21, 4.9), (18, 6.7), (15, 9.2), (12, 12.7), (9, 17.8), (6, None), (3, None), (0, None)]

Lecture : les 7 modes decrochent tous a 9 dB sur ce banc synthetique
(bruit-blanc gaussien, 24 lignes, graine fixe) — c'est le SNR le plus bas du
balayage ou le MAE reste encore sous le seuil (25) pour chacun d'eux ; a 6 dB
tous echouent deja (mode ou MAE invalide). Le vrai point de decrochage de
chaque mode est donc quelque part entre 6 et 9 dB, plus fin que la resolution
de ce balayage a 3 dB pres — un balayage resserre dans cette plage serait
necessaire pour les departager. Ce chiffre sert de reference AVANT les
leviers A1-A3 ; les taches suivantes mesurent le gain (dB gagnes sur ce
decrochage, ou sur un balayage plus fin) avec le meme banc.
"""
import json
import os

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS = os.path.join(CONCOURS, 'logx_sstvdecoder.js')
py_mini_racer = pytest.importorskip('py_mini_racer')

FS = 11025
SEUIL_UTILISABLE = 25          # MAE au-dela duquel l'image est inexploitable
SNRS_DB = [30, 27, 24, 21, 18, 15, 12, 9, 6, 3, 0]


@pytest.fixture(scope='module')
def moteur():
    ctx = py_mini_racer.MiniRacer()
    with open(JS, encoding='utf-8') as f:
        ctx.eval(f.read())
    # Bloc JS sans aucun formatage Python (pas de '%') : FS est injecte a
    # part dans un eval separe ci-dessous, pour ne jamais faire collision
    # avec un '%' qui apparaitrait un jour dans ce bloc (piège documente
    # dans le brief -- test_sstv_decodeur.py utilise le formatage inline,
    # mais ce fichier prefere l'approche la plus robuste).
    ctx.eval("""
    function imageTestSstv(l, h){
      var px = new Uint8ClampedArray(l*h*3);
      for(var y=0;y<h;y++) for(var x=0;x<l;x++){
        var i=(y*l+x)*3;
        var r=Math.round(x*255/(l-1)), g=Math.round(y*255/(h-1));
        px[i]=r; px[i+1]=g; px[i+2]=Math.round(255-(r+g)/2);
      }
      return px;
    }
    function maeSstv(dec, px, l, lignes){
      var s=0, n=0;
      for(var y=0;y<lignes;y++) for(var x=0;x<l;x++){
        var i=y*l+x;
        s += Math.abs(dec.rgba[i*4]-px[i*3])
           + Math.abs(dec.rgba[i*4+1]-px[i*3+1])
           + Math.abs(dec.rgba[i*4+2]-px[i*3+2]);
        n += 3;
      }
      return s/n;
    }
    // Bruit blanc GAUSSIEN calibre en SNR (dB) sur la puissance du signal.
    // Box-Muller a partir d'un LCG a graine : un echec se rejoue a l'identique.
    function bruitGaussienSnr(sig, snrDb, graine){
      var p=0;
      for(var i=0;i<sig.length;i++) p += sig[i]*sig[i];
      var rms = Math.sqrt(p/sig.length);
      var sigma = rms / Math.pow(10, snrDb/20);
      var s = graine||1, out = new Float32Array(sig.length), spare=null;
      for(var i=0;i<sig.length;i++){
        var g;
        if(spare!==null){ g=spare; spare=null; }
        else {
          s=(s*1103515245+12345)&0x7fffffff; var u1=(s/0x7fffffff)||1e-9;
          s=(s*1103515245+12345)&0x7fffffff; var u2=(s/0x7fffffff);
          var mag=Math.sqrt(-2*Math.log(u1));
          g=mag*Math.cos(2*Math.PI*u2); spare=mag*Math.sin(2*Math.PI*u2);
        }
        out[i]=sig[i]+g*sigma;
      }
      return out;
    }
    // Un point de mesure : encode la mire du mode, bruite au SNR donne, decode
    // avec les options DSP passees (leviers A1-A3), renvoie la metrique.
    function mesureSnr(nomMode, snrDb, opts){
      opts = opts || {};
      var m = SSTV_MODES_PAR_NOM[nomMode];
      var px = imageTestSstv(m.largeur, m.hauteur);
      var lignes = opts.lignes || null;
      var sig = sstvEncodeSamples({mode:nomMode, pixels:px, sampleRate:FS, lignes:lignes});
      sig = bruitGaussienSnr(sig, snrDb, 7);
      var decOpts = Object.assign({sampleRate:FS}, opts.dec||{});
      var d = sstvDecodeSamples(sig, decOpts);
      var r = d.resume();
      r.snr = snrDb;
      r.mae = (r.mode===nomMode && r.lignesEmises>0)
            ? maeSstv(d, px, m.largeur, r.lignesEmises) : null;
      return r;
    }
    function courbeSnr(nomMode, snrsDb, opts){
      return snrsDb.map(function(s){ return mesureSnr(nomMode, s, opts); });
    }
    """)
    # FS injecte a part cote Python -- MiniRacer n'a pas la variable FS et le
    # bloc ci-dessus ne contient aucun formatage Python.
    ctx.eval('var FS = %d;' % FS)
    return ctx


def _courbe(moteur, mode, snrs=None, opts=None):
    snrs = snrs or SNRS_DB
    js = 'JSON.stringify(courbeSnr(%s, %s, %s))' % (
        json.dumps(mode), json.dumps(snrs), json.dumps(opts or {}))
    return json.loads(moteur.eval(js))


def _snr_decrochage(courbe):
    """Plus BAS SNR encore utilisable (mode correct, mae <= seuil). Plus bas =
    meilleur. None si aucun point n'est utilisable."""
    ok = [p['snr'] for p in courbe
          if p['mode'] and p['mae'] is not None and p['mae'] <= SEUIL_UTILISABLE]
    return min(ok) if ok else None


def test_le_banc_produit_une_baseline_exploitable(moteur):
    """Temoin du banc lui-meme : sur un mode robuste (Robot 36, lignes tronquees
    pour la vitesse), a SNR eleve l'image est utilisable, et il existe un SNR de
    decrochage fini dans le balayage. Sans ce temoin, un banc casse se lirait
    comme une protection parfaite (regle du depot).

    Contre-epreuve par mutation faite le 2026-09-03 : SEUIL_UTILISABLE mute a
    -1 (rien n'est jamais utilisable) -> ce test ECHOUE bien sur
    `assert d is not None`. Restaure, revert au vert. Mutation de
    bruitGaussienSnr pour renvoyer `sig` inchange : ce temoin reste VERT --
    ATTENDU, il ne teste QUE la mecanique du banc (encode/decode/MAE), pas la
    sensibilite au bruit -- cette derniere est prouvee par les mesures A/B
    des taches A1-A3 (courbe qui degrade avec le SNR), pas par ce temoin."""
    c = _courbe(moteur, 'R36', SNRS_DB, {'lignes': 16})
    haut = next(p for p in c if p['snr'] == 30)
    assert haut['mode'] == 'R36'
    assert haut['mae'] is not None and haut['mae'] < SEUIL_UTILISABLE
    d = _snr_decrochage(c)
    assert d is not None, 'aucun SNR utilisable — banc suspect'


BASELINE_MODES = ['M1', 'M2', 'S1', 'S2', 'R36', 'R72', 'PD90']  # 1 par famille + variantes rapides


@pytest.mark.parametrize('mode', BASELINE_MODES)
def test_baseline_snr_decrochage_actuel(moteur, mode, capsys):
    """Mesure et journalise le SNR de decrochage ACTUEL (avant tout levier).
    Assertion volontairement lache : on verrouille seulement qu'un mode decode
    en clair (SNR 30 dB). Le chiffre exact de decrochage est journalise pour
    servir de point de depart aux mesures A/B — il n'est pas fige en dur (on ne
    connait pas encore la cible, cf. spec §3)."""
    c = _courbe(moteur, mode, SNRS_DB, {'lignes': 24})
    haut = next(p for p in c if p['snr'] == 30)
    assert haut['mode'] == mode and haut['mae'] is not None
    with capsys.disabled():
        print('\nBASELINE %-6s decrochage=%s dB  courbe=%s' % (
            mode, _snr_decrochage(c),
            [(p['snr'], None if p['mae'] is None else round(p['mae'], 1)) for p in c]))
