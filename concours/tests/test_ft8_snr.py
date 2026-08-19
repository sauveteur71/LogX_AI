# -*- coding: utf-8 -*-
"""Rapport signal/bruit FT8 — la colonne « Score » devient un vrai report.

CE QUI N'ALLAIT PAS. La colonne affichait `syncScore`, une somme de magnitudes
de corrélation : un nombre sans unité, proportionnel au NIVEAU D'ENTRÉE de la
carte son. Il ne se comparait d'un récepteur à l'autre, ne se comparait même
pas d'un réglage de gain à l'autre, et sur la station réelle de F4GLD il
affichait **0 sur les 17 décodages** — ses niveaux sont environ dix fois plus
faibles que ceux d'un signal de synthèse, et la normalisation posée
précédemment faisait tout arrondir à zéro.

Le décodeur ne produisait par ailleurs AUCUNE estimation de rapport
signal/bruit — vérifié, le mot n'apparaissait pas une fois dans le DSP. Le
séquenceur n'avait donc rien à annoncer et retombait sur une valeur par
défaut : il envoyait le MÊME report à toutes les stations, toujours.

CE QUE CES TESTS TIENNENT :
  - le rapport est insensible au gain d'entrée (c'est le défaut ci-dessus) ;
  - la constante de calibration est MESURÉE, et ce fichier refait la mesure :
    elle ne peut pas dériver en silence ;
  - le plancher de bruit se mesure HORS de la bande du signal, sans quoi la
    mesure sature sur les signaux forts (mesuré : 20 dB d'erreur) ;
  - la page affiche bien le SNR et non l'ancien score.

CE QU'ILS NE PROUVENT PAS : le comportement sur un signal réel reçu par une
vraie radio — QSB, brouillage, distorsion de la chaîne SSB. La vérité terrain
n'existe ici que parce que c'est nous qui fabriquons le signal ET le bruit.
"""
import json
import math
import os

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CODEC_JS = os.path.join(CONCOURS, 'logx_ft8_codec.js')
DSP_JS = os.path.join(CONCOURS, 'logx_ft8_dsp.js')
FT8_HTML = os.path.join(CONCOURS, 'logx_ft8.html')

py_mini_racer = pytest.importorskip('py_mini_racer')

FE = 12000.0
TONE0 = 1500.0
AMPLITUDE = 0.5
TEXTE = 'CQ F4GLD JN15'


@pytest.fixture(scope='module')
def moteur():
    ctx = py_mini_racer.MiniRacer()
    for path in (CODEC_JS, DSP_JS):
        with open(path, encoding='utf-8') as f:
            ctx.eval(f.read())
    ctx.eval("""
    // Bruit blanc reproductible. Math.imul pour un vrai wraparound 32 bits —
    // même précaution que test_ft8_codec.py.
    function bruitUniforme(sig, L, graine){
      var s = graine || 1, out = new Float32Array(sig.length);
      for(var i=0;i<sig.length;i++){
        s = (Math.imul(s,1103515245) + 12345) & 0x7fffffff;
        out[i] = sig[i] + ((s/0x7fffffff)*2-1)*L;
      }
      return out;
    }
    // Signal + bruit, le tout multiplié par `gain` : c'est ainsi qu'agit le
    // réglage d'entrée d'une carte son — sur le mélange, pas sur l'un des deux.
    function fabriquer(texte, fe, tone0, A, L, graine, gain){
      var enc = ft8EncodeMessage(texte, null);
      var sig = ft8SynthesizeGfsk(enc.symbols, {sampleRate: fe,
                                                toneHz0: tone0, amplitude: A});
      var b = bruitUniforme(sig, L, graine);
      if(gain !== undefined && gain !== 1){
        for(var i=0;i<b.length;i++) b[i] *= gain;
      }
      return b;
    }
    function mesurer(texte, fe, tone0, A, L, graine, gain){
      var b = fabriquer(texte, fe, tone0, A, L, graine, gain);
      var sync = ft8FindSync(b, fe, {});
      if(!sync) return null;
      return ft8EstimerSnr(b, sync.startSample, sync.baseFreqHz, fe);
    }
    """)
    return ctx


def _niveau_pour(snr_db):
    """Niveau de bruit L donnant le SNR(2500 Hz) voulu.

    Inverse de la vérité terrain :
        SNR = 10*log10( (A^2/2) / ((L^2/3) * 2500/(fe/2)) )
    """
    return math.sqrt((AMPLITUDE ** 2 / 2.0) * 3.0 * (FE / 2.0) / 2500.0
                     / (10 ** (snr_db / 10.0)))


def _verite(L):
    return 10.0 * math.log10((AMPLITUDE ** 2 / 2.0) /
                             ((L ** 2 / 3.0) * 2500.0 / (FE / 2.0)))


def _mesure(moteur, snr_vise, graine, gain=1):
    L = _niveau_pour(snr_vise)
    v = moteur.eval('mesurer(%s,%f,%f,%f,%f,%d,%f)'
                    % (json.dumps(TEXTE), FE, TONE0, AMPLITUDE, L, graine, gain))
    return (v, _verite(L))


# ═══════════════════════════════════════════════════════════════════════════
# §1. LE DÉFAUT D'ORIGINE : une mesure qui suivait le niveau d'entrée
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize('gain', [0.001, 0.01, 0.1, 1.0, 4.0])
def test_le_rapport_ne_depend_pas_du_gain_d_entree(moteur, gain):
    """LE test de ce fichier. L'ancienne colonne affichait 0 chez F4GLD parce
    qu'elle mesurait une AMPLITUDE : baisser le gain de la carte son la faisait
    tomber, sans que le signal reçu soit moins bon pour autant.

    Un rapport de deux puissances prises dans la même fenêtre est invariant par
    changement de gain — le facteur se simplifie. On le vérifie sur quatre
    décades, dont un gain de 0,001 qui aurait mis n'importe quelle mesure
    d'amplitude à zéro."""
    reference, _ = _mesure(moteur, -5, graine=1, gain=1.0)
    assert reference is not None
    mesure, _ = _mesure(moteur, -5, graine=1, gain=gain)
    assert mesure is not None, 'aucune mesure au gain %g' % gain
    assert abs(mesure - reference) < 0.5, (
        'gain %g : SNR %.2f dB contre %.2f dB à gain unité — la mesure suit '
        'encore le niveau d\'entrée' % (gain, mesure, reference))


def test_l_ancien_score_lui_suivait_bel_et_bien_le_gain(moteur):
    """Contre-preuve : on montre que le défaut était RÉEL, et pas une
    hypothèse. Sans ce test, rien n'établit que le remplacement était
    nécessaire — et le test précédent pourrait passer sur un estimateur qui
    n'aurait jamais eu le problème."""
    L = _niveau_pour(-5)
    scores = []
    for gain in (1.0, 0.1):
        s = moteur.eval("""(function(){
            var b = fabriquer(%s,%f,%f,%f,%f,%d,%f);
            var sync = ft8FindSync(b, %f, {});
            return sync ? sync.score / ft8SamplesPerSymbol(%f) : null;
        })()""" % (json.dumps(TEXTE), FE, TONE0, AMPLITUDE, L, 1, gain, FE, FE))
        scores.append(s)
    assert scores[0] is not None and scores[1] is not None
    rapport = scores[0] / scores[1]
    assert rapport > 5, (
        'le score de corrélation devrait être divisé par ~10 quand le gain '
        "l'est : %.3f -> %.3f (rapport %.1f)" % (scores[0], scores[1], rapport))


# ═══════════════════════════════════════════════════════════════════════════
# §2. LA CALIBRATION — mesurée, donc vérifiable
# ═══════════════════════════════════════════════════════════════════════════

# Paliers couvrant la plage RÉELLE du FT8. Calibrer entre +25 et -5 dB, comme
# le faisait le premier jet, revient à mesurer là où l'on ne trafique pas.
PALIERS = [15, 10, 5, 0, -5, -10, -14, -17]
GRAINES = (1, 38, 75, 112, 149, 186)


def test_la_constante_de_calibration_est_celle_qu_on_mesure(moteur):
    """La constante figée dans le DSP doit rester celle que la mesure donne.
    Si quelqu'un touche à la façon de mesurer le bruit (fenêtres, sondes,
    médiane), l'offset bouge et ce test le dit — au lieu de laisser tous les
    reports partir faux sur l'air."""
    ecarts = []
    for cible in PALIERS:
        for g in GRAINES:
            mesure, verite = _mesure(moteur, cible, g)
            if mesure is None:
                continue
            # L'offset est déjà appliqué dans ft8EstimerSnr : ce qu'on regarde
            # ici est donc l'erreur RÉSIDUELLE du report final.
            ecarts.append(verite - mesure)
    assert len(ecarts) >= len(PALIERS) * len(GRAINES) - 2, (
        'trop de mesures manquantes : %d' % len(ecarts))
    moyenne = sum(ecarts) / len(ecarts)
    pire = max(abs(e) for e in ecarts)
    assert abs(moyenne) < 0.6, (
        'biais moyen de %.2f dB sur la plage utile — la constante '
        'FT8_SNR_OFFSET_DB a dérivé' % moyenne)
    assert pire < 2.0, (
        'erreur maximale de %.2f dB : trop pour un report envoyé sur l\'air'
        % pire)


@pytest.mark.parametrize('cible', PALIERS)
def test_chaque_palier_est_juste_a_moins_de_1_5_dB(moteur, cible):
    """Un biais moyen nul peut cacher deux erreurs opposées qui se compensent.
    On contrôle donc PALIER PAR PALIER."""
    ecarts = []
    for g in GRAINES:
        mesure, verite = _mesure(moteur, cible, g)
        if mesure is not None:
            ecarts.append(verite - mesure)
    assert ecarts, 'aucune mesure au palier %d dB' % cible
    moyen = sum(ecarts) / len(ecarts)
    assert abs(moyen) < 1.5, (
        'palier %d dB : erreur moyenne %.2f dB' % (cible, moyen))


def test_un_signal_plus_fort_donne_un_report_plus_haut(moteur):
    """Propriété la plus élémentaire, et pourtant celle qu'un estimateur qui
    sature cesse de tenir : c'est exactement ce qui arrivait quand le bruit
    était mesuré DANS la bande du signal."""
    mesures = []
    for cible in PALIERS:                       # PALIERS est décroissant
        v, _ = _mesure(moteur, cible, graine=1)
        assert v is not None, 'pas de mesure à %d dB' % cible
        mesures.append((cible, v))
    for (c1, m1), (c2, m2) in zip(mesures, mesures[1:]):
        assert m1 > m2, (
            '%d dB mesuré à %.2f, mais %d dB mesuré à %.2f : la mesure ne '
            'suit plus le signal' % (c1, m1, c2, m2))


def test_la_dynamique_mesuree_suit_la_dynamique_reelle(moteur):
    """Un estimateur peut être monotone tout en écrasant l'échelle (c'était le
    cas : 10 dB de plage mesurée pour 30 dB réels). On vérifie la PENTE."""
    haut, vh = _mesure(moteur, 15, graine=1)
    bas, vb = _mesure(moteur, -17, graine=1)
    assert haut is not None and bas is not None
    pente = (haut - bas) / (vh - vb)
    assert 0.85 < pente < 1.15, (
        'pente de %.2f dB par dB réel : l\'échelle est comprimée ou dilatée '
        '(%.1f -> %.1f mesuré pour %.1f -> %.1f réel)'
        % (pente, bas, haut, vb, vh))


# ═══════════════════════════════════════════════════════════════════════════
# §3. STRUCTURE — pourquoi la mesure est faite comme ça
# ═══════════════════════════════════════════════════════════════════════════

def test_les_sondes_de_bruit_sont_TOUTES_hors_de_la_bande_du_signal(moteur):
    """Le signal occupe les crans 0 à 7. Une sonde qui tomberait dedans
    mesurerait le signal et non le bruit — c'est la faute qui faisait saturer
    la première version (mesuré : offset dérivant de 20 dB sur la plage)."""
    sondes = json.loads(moteur.eval('JSON.stringify(FT8_SNR_SONDES)'))
    assert sondes, 'aucune sonde définie'
    for cran in sondes:
        assert cran < 0 or cran > 7, (
            'la sonde au cran %d tombe dans la bande du signal (crans 0 à 7)'
            % cran)
    # Et pas collées non plus : les jupes du signal débordent de sa bande.
    assert max(c for c in sondes if c < 0) <= -8, sondes
    assert min(c for c in sondes if c > 7) >= 15, sondes


def test_une_station_voisine_ne_fait_pas_seffondrer_le_report(moteur):
    """La séparation minimale entre deux stations décodées est de 50 Hz : une
    voisine PEUT tomber dans les sondes. La médiane est là pour ça — avec une
    moyenne, la porteuse parasite tirerait le plancher vers le haut et le
    report s'effondrerait."""
    L = _niveau_pour(-5)
    propre = moteur.eval('mesurer(%s,%f,%f,%f,%f,%d,1)'
                         % (json.dumps(TEXTE), FE, TONE0, AMPLITUDE, L, 1))
    pollue = moteur.eval("""(function(){
        var b = fabriquer(%s,%f,%f,%f,%f,%d,1);
        // Une porteuse forte à -150 Hz, en plein dans les sondes basses.
        var f = %f - 150;
        for(var i=0;i<b.length;i++)
          b[i] += 0.5*Math.sin(2*Math.PI*f*i/%f);
        var sync = ft8FindSync(b, %f, {});
        return sync ? ft8EstimerSnr(b, sync.startSample, sync.baseFreqHz, %f)
                    : null;
    })()""" % (json.dumps(TEXTE), FE, TONE0, AMPLITUDE, L, 1, TONE0, FE, FE, FE))
    assert propre is not None and pollue is not None
    assert abs(pollue - propre) < 3.0, (
        'une porteuse dans les sondes fait passer le report de %.1f à %.1f dB'
        % (propre, pollue))


def test_sur_du_bruit_pur_il_n_y_a_PAS_de_mesure(moteur):
    """Sans ce garde-fou, l'estimateur rendait -42 dB sur du bruit seul : la
    moyenne des 21 fenêtres de signal dépasse toujours un peu la médiane du
    plancher, donc la soustraction reste positive par le seul jeu du hasard.

    Une absence de signal doit se lire comme une absence, pas comme un nombre
    — qui serait affiché tel quel dans la colonne."""
    v = moteur.eval("""(function(){
        var vide = new Float32Array(Math.round(%f*15));
        var b = bruitUniforme(vide, 0.3, 1);
        return ft8EstimerSnr(b, 0, 1500, %f);
    })()""" % (FE, FE))
    assert v is None, (
        'du bruit pur donne un report de %r dB au lieu de « pas de mesure »' % v)


def test_avec_du_trafic_a_cote_et_rien_chez_nous_il_n_y_a_PAS_de_mesure(moteur):
    """Cas limite que la contre-épreuve a révélé non couvert : le plancher
    mesuré dépasse la puissance des tons du signal. Il n'est pas théorique —
    c'est la bande occupée de part et d'autre pendant que notre fréquence est
    vide.

    La soustraction devient alors négative, et le logarithme d'un nombre
    négatif n'existe pas. Rendre 0 dB ici afficherait « signal au niveau du
    bruit » là où il n'y a aucun signal du tout."""
    v = moteur.eval("""(function(){
        var fe = %f, n = Math.round(fe*15), b = new Float32Array(n);
        // De l'énergie SUR TOUTES les sondes, rien sur les 8 tons du signal.
        for(var k=0;k<FT8_SNR_SONDES.length;k++){
          var f = 1500 + FT8_SNR_SONDES[k]*FT8_TONE_SPACING;
          for(var i=0;i<n;i++) b[i] += 0.2*Math.sin(2*Math.PI*f*i/fe);
        }
        return ft8EstimerSnr(b, 0, 1500, fe);
    })()""" % FE)
    assert v is None, (
        'un plancher plus fort que nos tons donne %r au lieu de « pas de '
        'mesure »' % v)


def test_sous_le_seuil_de_decodage_aucune_valeur_n_est_rendue(moteur):
    """Le plancher doit être effectif, pas seulement déclaré."""
    plancher = moteur.eval('FT8_SNR_PLANCHER_DB')
    assert plancher is not None and plancher < -20, (
        'plancher absent ou trop haut : %r' % plancher)
    v, _ = _mesure(moteur, -40, graine=1)
    assert v is None or v >= plancher, (
        'valeur %r rendue alors que le plancher est %r' % (v, plancher))


def test_la_soustraction_du_bruit_tient_les_signaux_tres_faibles(moteur):
    """Le ton attendu porte le signal ET le bruit tombant dans son filtre.

    Mesuré : l'écart entre avec et sans soustraction vaut 0,01 dB à 0 dB et
    0,34 dB à -17 — autant dire rien dans la plage où l'on trafique. Il atteint
    en revanche 1,31 dB à -24 dB, et c'est là — et LÀ SEULEMENT — qu'un test
    peut constater que la formule est la bonne. Un test posé plus haut serait
    satisfait par la formule fausse : c'est ce qui s'est produit, la
    contre-épreuve l'a montré."""
    ecarts = []
    for g in GRAINES:
        mesure, verite = _mesure(moteur, -24, g)
        if mesure is not None:
            ecarts.append(verite - mesure)
    assert ecarts, 'aucune mesure à -24 dB'
    moyen = sum(ecarts) / len(ecarts)
    assert abs(moyen) < 1.2, (
        'erreur de %.2f dB à -24 dB : sans la soustraction du bruit elle vaut '
        'environ 2 dB' % moyen)


def test_le_decodeur_remonte_le_snr_a_la_page(moteur):
    """Sans ça, tout ce qui précède reste dans le DSP et la page continue
    d'afficher l'ancien score."""
    L = _niveau_pour(-5)
    res = json.loads(moteur.eval("""JSON.stringify((function(){
        var b = fabriquer(%s,%f,%f,%f,%f,%d,1);
        return ft8DecodeAudioAll(b, %f, null, {});
    })())""" % (json.dumps(TEXTE), FE, TONE0, AMPLITUDE, L, 1, FE)))
    assert res, 'rien décodé'
    assert 'snrDb' in res[0], 'le décodeur ne remonte pas snrDb : %r' % res[0]
    assert isinstance(res[0]['snrDb'], (int, float)), res[0]['snrDb']
    assert -30 < res[0]['snrDb'] < 30, (
        'valeur invraisemblable : %r' % res[0]['snrDb'])


# ═══════════════════════════════════════════════════════════════════════════
# §4. LA PAGE
# ═══════════════════════════════════════════════════════════════════════════

def _html():
    with open(FT8_HTML, encoding='utf-8') as f:
        return f.read()


def test_la_page_affiche_le_snr_et_non_l_ancien_score():
    src = _html()
    assert 'ajouterDecodage(slotTermine, r.text, r.freqHz, r.snrDb, dt)' in src, (
        'la page passe encore autre chose que r.snrDb à l\'affichage')
    assert 'r.syncScore, dt)' not in src, (
        'l\'ancien score est toujours affiché')


def test_la_colonne_ne_s_appelle_plus_Score():
    """« Score » ne veut rien dire pour un opérateur, et c'est précisément la
    question posée : « a quoi sert le score ? si pas de concours c'est
    inutile »."""
    src = _html()
    assert '<th>Score</th>' not in src, 'la colonne s\'appelle encore Score'
    assert '>SNR</th>' in src, 'la colonne SNR est absente'


def test_le_signe_du_report_est_toujours_affiche():
    """« 3 » se lirait aussi bien +3 que -3, deux conditions très différentes.
    Et l'absence de mesure doit se voir comme une absence, pas comme un 0 —
    qui est une VRAIE valeur, celle d'un signal au niveau du bruit."""
    src = _html()
    i = src.index('const tdS = document.createElement(\'td\');')
    zone = src[i:i + 400]
    assert "snrDb >= 0 ? '+' : ''" in zone, (
        'le signe positif doit être explicite : %r' % zone[:200])
    assert "'—'" in zone, (
        'une mesure impossible doit afficher un tiret, pas 0 : %r' % zone[:200])
