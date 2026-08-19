# -*- coding: utf-8 -*-
"""DT FT8 : l'horloge du PC vérifiée par les stations reçues.

Question posée par F4GLD le 18/08/2026 après un essai en trafic réel. Elle
est fondée : en FT8 tout est calé sur des créneaux de 15 s alignés sur
00/15/30/45 s UTC, et le signal lui-même n'occupe que 12,64 s du créneau
(79 symboles à 6,25 baud — Franke, Somerville & Taylor, « The FT4 and FT8
Communication Protocols », QEX juillet-août 2020). Le guide utilisateur de
la tenue d'heure attendue est de l'ordre de LA SECONDE (horloge PC
synchronisée NTP sur l'UTC). Une première rédaction de ce fichier annonçait
« ±2 s selon le guide utilisateur de WSJT-X » : attribution fausse, corrigée
le 18/08/2026 en revue. Une valeur écrite de mémoire et habillée d'une
source est pire qu'une valeur sans source — elle ne se rediscute plus.

Or la page FT8 affichait une horloge UTC en en-tête qui n'est QUE l'horloge
du PC reformatée : elle ne vérifie rien. Un opérateur dont le PC dérive de
5 s voyait une horloge d'apparence normale, un waterfall plein de signaux, et
zéro décodage — sans le moindre indice sur la cause.

La mesure ajoutée ici n'utilise AUCUN service tiers et aucun accès réseau —
contrainte produit du logiciel (gratuit, autonome, respectueux de la vie
privée) : ce sont les stations reçues qui servent de référence. Le décodeur
sait où commence le motif de synchro Costas dans la fenêtre analysée
(startSample) ; l'écart avec le début théorique du créneau EST le DT.

Ce que ces tests NE prouvent PAS : le comportement sur un vrai signal reçu
par une vraie radio. Ils prouvent que la chaîne de mesure est juste.
"""
import json
import os
import re

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CODEC_JS = os.path.join(CONCOURS, 'logx_ft8_codec.js')
DSP_JS = os.path.join(CONCOURS, 'logx_ft8_dsp.js')
FT8_HTML = os.path.join(CONCOURS, 'logx_ft8.html')

py_mini_racer = pytest.importorskip('py_mini_racer')

SR = 12000


def _lire(chemin):
    with open(chemin, encoding='utf-8') as f:
        return f.read()


def _extraire_fonction(src, nom):
    """Comptage d'accolades — une regex non gloutonne s'arrêterait à la
    première accolade fermante imbriquée."""
    debut = src.index('function ' + nom)
    prof, i = 0, src.index('{', debut)
    while True:
        if src[i] == '{':
            prof += 1
        elif src[i] == '}':
            prof -= 1
            if prof == 0:
                return src[debut:i + 1]
        i += 1


@pytest.fixture(scope='module')
def moteur():
    ctx = py_mini_racer.MiniRacer()
    for path in (CODEC_JS, DSP_JS):
        ctx.eval(_lire(path))
    ctx.eval("""
    // Fabrique une fenêtre d'analyse RÉALISTE : du silence, puis le signal
    // FT8 à `decalageSec` du début de la fenêtre. C'est exactement ce que
    // extraireFenetre() fournit au décodeur en fonctionnement.
    function fenetreAvecDecalage(texte, sampleRate, decalageSec, dureeSec){
      var enc = ft8EncodeMessage(texte, null);
      if(!enc) return null;
      var wave = ft8SynthesizeGfsk(enc.symbols, {sampleRate: sampleRate, toneHz0: 1500});
      var total = Math.round(dureeSec * sampleRate);
      var out = new Float32Array(total);
      var debut = Math.round(decalageSec * sampleRate);
      for(var i = 0; i < wave.length && debut + i < total; i++) out[debut + i] = wave[i];
      return out;
    }""")
    return ctx


# ─── Le décodeur remonte bien la position du signal ──────────────────────────

MARGE_S = 1.5   # doit rester égal à `marge` dans extraireFenetre (logx_ft8.html)


def _decoder_a_dt(moteur, dt_sec, centre_sec):
    """Décode une fenêtre construite comme celle de la page : `MARGE_S` de
    silence, puis le signal décalé de `dt_sec` par rapport au créneau."""
    return json.loads(moteur.eval(f"""
      (function(){{
        var w = fenetreAvecDecalage('CQ F4GLD JN15', {SR}, {MARGE_S} + {dt_sec}, 18);
        if(!w) return JSON.stringify({{ok:false}});
        var r = ft8DecodeAudioAll(w, {SR}, null, {{centerSample: {centre_sec} * {SR}}});
        if(!r.length) return JSON.stringify({{ok:false}});
        return JSON.stringify({{ok:true, texte:r[0].text, startSample:r[0].startSample}});
      }})()"""))


@pytest.mark.parametrize('dt_sec', [-1.0, -0.5, 0.0, 0.5, 1.0])
def test_la_recherche_centree_accepte_le_dt_dans_les_deux_sens(moteur, dt_sec):
    """LE correctif du 18/08/2026, et la cause principale du « il ne me
    propose pas d'autres stations » de F4GLD.

    La recherche de synchro partait du DÉBUT DE LA FENÊTRE (startSample = 0),
    alors que la fenêtre commence AVANT le créneau. Elle explore ±6 symboles ;
    une station à DT nul se trouvait donc déjà au bord de la plage, et tout ce
    qui arrivait un peu APRÈS le créneau tombait dehors. Mesuré avant
    correctif : tolérance [-1,00 s ; 0,00 s] — rien du côté positif. Sur une
    bande réelle, les DT des stations se répartissent des deux côtés de zéro :
    la moitié était invisible, et si l'horloge du PC retardait un peu, la
    quasi-totalité.

    Après centrage (opts.centerSample) : [-1,00 s ; +1,00 s], symétrique."""
    res = _decoder_a_dt(moteur, dt_sec, MARGE_S)
    assert res['ok'], f'DT {dt_sec:+.1f} s doit se décoder après centrage'
    assert res['texte'] == 'CQ F4GLD JN15'
    attendu = (MARGE_S + dt_sec) * SR
    sps = SR / 6.25   # ft8RefineSync affine par pas de sps/8, pas à l'échantillon
    assert abs(res['startSample'] - attendu) < sps


@pytest.mark.parametrize('dt_sec', [0.2, 0.5, 1.0])
def test_sans_centrage_tout_dt_positif_etait_perdu(moteur, dt_sec):
    """Le pendant du test précédent : reproduit l'ANCIEN comportement
    (centerSample=0) pour prouver que le correctif porte bien sur ce point et
    n'est pas une coïncidence. Si ce test se met un jour à passer, c'est que
    la géométrie de recherche a encore changé — le relire avant de le
    supprimer."""
    assert not _decoder_a_dt(moteur, dt_sec, 0)['ok']


# ─── calculerDt : la vraie fonction de la page ───────────────────────────────

@pytest.fixture(scope='module')
def page():
    """Exécute calculerDt/medianeDt EXTRAITES de logx_ft8.html — pas une
    réécriture dans le test, qui ne prouverait rien sur le code livré."""
    src = _lire(FT8_HTML)
    ctx = py_mini_racer.MiniRacer()
    ctx.eval(f'var sr = {SR}; var dtRecents = [];')
    ctx.eval(_extraire_fonction(src, 'calculerDt'))
    ctx.eval(_extraire_fonction(src, 'medianeDt'))
    return ctx


def test_une_station_parfaitement_calee_donne_un_dt_nul(page):
    """La fenêtre commence 1 s avant le créneau (la marge de extraireFenetre)
    # La cadence est OBLIGATOIRE depuis la décimation : startSample n'est
    # plus exprimé dans la cadence de la carte son mais dans celle, réduite,
    # à laquelle le décodage a réellement travaillé. Le repli « cadence || sr »
    # rendait l'oubli silencieux — et juste par accident tant que la
    # décimation n'existait pas.
    et le signal démarre pile au créneau : DT = 0."""
    dt = page.eval(f'calculerDt(1000000 - 1000, 1.0 * {SR}, 1000000, {SR})')
    assert abs(dt) < 0.01


def test_un_pc_en_avance_voit_toutes_les_stations_en_retard(page):
    """Le cas qui compte. Si l'horloge du PC AVANCE de 3 s, le créneau est
    ouvert 3 s trop tôt : le signal des correspondants arrive 3 s « en
    retard » dans notre fenêtre. Un DT positif sur TOUTES les stations est
    donc la signature de NOTRE horloge, pas de la leur."""
    dt = page.eval(f'calculerDt(1000000 - 1000, (1.0 + 3.0) * {SR}, 1000000, {SR})')
    assert abs(dt - 3.0) < 0.01


def test_le_dt_est_signe(page):
    """Un signal qui commence AVANT l'ouverture du créneau donne un DT
    négatif — sans le signe, impossible de dire dans quel sens régler."""
    dt = page.eval(f'calculerDt(1000000 - 1000, 0.4 * {SR}, 1000000, {SR})')
    assert dt < 0


# ─── La médiane : une station mal réglée ne doit pas donner l'alerte ─────────

def test_pas_de_conclusion_sous_trois_stations(page):
    """Conclure sur une seule station serait accuser notre horloge alors que
    c'est peut-être la sienne qui dérive."""
    page.eval('dtRecents = [3.2, 3.1];')
    assert page.eval('medianeDt()') is None


def test_une_station_isolee_mal_reglee_ne_fausse_pas_la_mediane(page):
    """Cinq stations correctes et une seule à +6 s : la médiane doit rester
    proche de 0. C'est précisément ce qu'une moyenne ne ferait pas."""
    page.eval('dtRecents = [0.1, -0.2, 0.0, 0.3, -0.1, 6.0];')
    assert abs(page.eval('medianeDt()')) < 0.3


def test_toutes_les_stations_decalees_font_ressortir_la_mediane(page):
    page.eval('dtRecents = [3.1, 2.9, 3.4, 3.0, 3.2];')
    assert abs(page.eval('medianeDt()') - 3.1) < 0.3


# ─── L'information atteint bien l'écran ─────────────────────────────────────

def test_la_colonne_dt_existe_dans_le_tableau():
    """Le DT affiché par station est la colonne standard de WSJT-X : c'est ce
    qui permet de distinguer « c'est lui » de « c'est moi »."""
    src = _lire(FT8_HTML)
    entete = re.search(r'<thead>.*?</thead>', src, re.S).group(0)
    assert '>DT<' in entete
    assert entete.index('>DT<') < entete.index('>Score<'), \
        'DT attendu avant Score, comme dans WSJT-X'


def test_le_bandeau_d_alerte_horloge_existe_et_part_masque():
    src = _lire(FT8_HTML)
    m = re.search(r'<div class="horloge-alerte" id="horlogeAlerte"[^>]*>', src)
    assert m, 'bandeau d\'alerte horloge absent'
    assert 'display:none' in m.group(0), 'il ne doit apparaître qu\'en cas de dérive'


def test_le_seuil_d_alerte_reste_sous_les_deux_secondes():
    """Le seuil doit être ATTEIGNABLE, ce qui est une contrainte plus dure
    qu'il n'y paraît : DT = (startSample - centerSample)/sr, et startSample ne
    peut sortir de centerSample ± 7 symboles (6 au balayage grossier, 1 de
    plus à l'affinage), soit ±1,12 s. Un seuil au-dessus de cette borne rend
    le bandeau et la coloration rouge PHYSIQUEMENT inaccessibles — c'était le
    cas avec 1,5 s, du code mort livré le 18/08/2026 et corrigé le jour même
    après revue."""
    src = _lire(FT8_HTML)
    m = re.search(r'const DT_ALERTE_S\s*=\s*([\d.]+)', src)
    assert m, 'DT_ALERTE_S introuvable'
    seuil = float(m.group(1))
    # 1,12 s = borne dure du DT mesurable (7 symboles de 0,160 s).
    assert 0 < seuil < 1.12, (
        f'seuil {seuil} s inatteignable : le DT est borné à ±1,12 s par la '
        'plage de recherche de ft8FindAllSync/ft8RefineSync')


def _ctx_bandeau(dts):
    """Exécute le VRAI majAlerteHorloge() avec une liste de DT donnée, et rend
    le texte affiché à l'opérateur."""
    src = _lire(FT8_HTML)
    ctx = py_mini_racer.MiniRacer()
    ctx.eval("""
      // dataset : les deux bandeaux (silence / horloge) partagent cet élément
      // et marquent leur origine pour n'effacer que le leur.
      var __el = {textContent: '', style: {display: 'none'}, dataset: {}};
      var document = { getElementById: function(id){
        return id === 'horlogeAlerte' ? __el : null; } };
      var dtRecents = [];
      // majAlerteHorloge() demande depuis le 18/08/2026 une mesure d'horloge
      // SNTP pour savoir s'il peut accuser l'heure du PC. Ici on n'en fournit
      // pas : c'est le cas « mesure indisponible », celui où le texte doit
      // rester au CONSTAT et proposer les deux causes. Sans ce bouchon, la
      // fonction levait une ReferenceError avant même d'écrire son texte.
      function mesurerHorloge(){ return {then: function(){ return this; }}; }
      function affinerAlerteHorloge(){}
    """)
    ctx.eval(re.search(r'const DT_ALERTE_S\s*=\s*[\d.]+;', src).group(0)
             .replace('const', 'var', 1))
    ctx.eval(_extraire_fonction(src, 'medianeDt'))
    ctx.eval(_extraire_fonction(src, 'majAlerteHorloge'))
    ctx.eval('dtRecents = ' + json.dumps(dts) + ';')
    ctx.eval('majAlerteHorloge();')
    return {'texte': ctx.eval('__el.textContent'),
            'visible': ctx.eval("__el.style.display") != 'none'}


def test_un_pc_en_avance_est_annonce_EN_AVANCE():
    """LE test qui manquait. Le bandeau annonçait « en RETARD » pour un DT
    positif, alors qu'un DT positif signifie un PC EN AVANCE — l'opérateur
    était envoyé régler son horloge dans le mauvais sens, doublant l'erreur.

    Le fichier contenait DÉJÀ, quelques lignes plus haut,
    test_un_pc_en_avance_voit_toutes_les_stations_en_retard qui établit que
    PC en avance => DT positif. Le code et son propre test se contredisaient ;
    personne n'avait confronté les deux. C'est ce test-ci qui les relie."""
    r = _ctx_bandeau([0.9, 0.85, 0.95, 0.9])
    assert r['visible']
    assert 'en AVANCE' in r['texte'], r['texte']
    assert 'en RETARD' not in r['texte']


def test_un_pc_en_retard_est_annonce_EN_RETARD():
    r = _ctx_bandeau([-0.9, -0.85, -0.95, -0.9])
    assert r['visible']
    assert 'en RETARD' in r['texte'], r['texte']
    assert 'en AVANCE' not in r['texte']


def test_le_bandeau_se_declenche_bien_dans_la_plage_mesurable():
    """Le seuil doit être franchissable par des valeurs que la chaîne réelle
    peut produire (|DT| <= 1,12 s). Avec l'ancien seuil de 1,5 s, ce test
    échouait : le bandeau était du code mort."""
    assert _ctx_bandeau([0.8, 0.75, 0.85])['visible'], \
        'un décalage de 0,8 s doit déclencher le bandeau'


def test_le_bandeau_reste_muet_sur_un_reseau_sain():
    """Des DT de quelques dixièmes sont normaux entre stations bien réglées :
    le bandeau ne doit pas crier pour ça, sinon il ne sera plus lu."""
    assert not _ctx_bandeau([0.1, -0.2, 0.05, 0.15])['visible']


def test_l_alerte_ne_conseille_aucun_service_tiers_obligatoire():
    """Contrainte produit : autonome et respectueux de la vie privée. La
    mesure elle-même ne doit rien interroger sur le réseau — les stations
    reçues suffisent."""
    src = _lire(FT8_HTML)
    bloc = src[src.index('function majAlerteHorloge'):]
    bloc = bloc[:bloc.index('\n  }')]
    assert 'fetch(' not in bloc and 'XMLHttpRequest' not in bloc
