# -*- coding: utf-8 -*-
"""Logguer un QSO fait sur un poste que le PC ne commande pas.

LE DÉFAUT, remonté par F4GLD le 20/08/2026. Il voulait faire tourner le FT8 en
automatique sur une radio pilotée en CAT et, en même temps, noter à la main des
QSO faits en CW ou en phonie sur un SECOND poste non connecté au PC. Le carnet
encaisse très bien les deux flux — le problème n'était pas là. Il était sur
l'air :

  - choisir la bande 7 et le mode CW dans LOGBOOK pour préparer la fiche
    envoyait un QSY à la radio PILOTÉE (`_qsyVersRadio`, logx_logbook.js), donc
    déplaçait la radio du FT8 sur 7 MHz en CW, en pleine séquence automatique ;
  - le sondage CAT, toutes les 3 à 20 s, ramenait en retour la bande et le mode
    de saisie sur ceux de la radio (`syncBandModeFromRig`,
    logx_hardware_cat.js) — le QSO 40 m risquait donc de partir au carnet avec
    la bande du FT8 ;
  - et la fréquence affichée était réécrite par celle du poste piloté.

Ces trois comportements sont VOULUS et ont chacun été demandés (correctif
IC-7300 du 15/08/2026). Ils ne sont faux que dans un cas : quand le QSO qu'on
note n'a pas été fait sur la radio pilotée. D'où un état explicite plutôt
qu'un changement de comportement par défaut.

CE QUE CES TESTS TIENNENT. Les trois chemins sont coupés quand la saisie est
découplée, et RIEN ne change quand elle ne l'est pas (non-régression du
correctif de 15/08). Ils s'exécutent sur les VRAIS logx_logbook.js et
logx_hardware_cat.js dans un moteur JS réel, avec un fetch-espion — pas sur
une réimplémentation, qui ne contraindrait qu'elle-même.

CE QU'ILS NE PROUVENT PAS. Que deux vraies radios cohabitent sur l'air : le
logiciel reste structurellement aveugle au second poste, il ne le bloquera pas
mais ne le protègera pas non plus. La règle « une seule porteuse » demeure à la
charge de l'opérateur.

Même patron que tests/test_cat_manual_bandmode_qsy.py, dont ce fichier
réutilise le DOM minimal plutôt que d'en écrire un troisième.
"""
import json

import pytest

py_mini_racer = pytest.importorskip(
    'py_mini_racer', reason='py_mini_racer absent (voir requirements.txt) — test JS réel ignoré')

from test_cat_manual_bandmode_qsy import _DOM_PREAMBLE, _real_source  # noqa: E402

_NET_STUB = r"""
var __fetchCalls = [];
function fetch(url, opts){
  var body = {};
  try{ body = (opts && opts.body) ? JSON.parse(opts.body) : {}; }catch(e){}
  __fetchCalls.push({url:String(url), body:body});
  return Promise.resolve({ok:true, status:200, json:function(){ return Promise.resolve({}); }});
}
// TOUT ce qui part vers la radio, pas seulement /rig/qsy : le découplage doit
// aussi couper la puissance TX automatique, qui partirait sinon d'après le
// mode d'un QSO fait sur un AUTRE poste.
function __versRadio(){
  return __fetchCalls.filter(function(c){ return c.url.indexOf('/rig/') === 0; });
}
"""

_INIT = r"""
function __init(){
  myCall = 'F4TEST'; myLocator = 'JN03QQ'; myOp = 'OP1';
  usageMode = 'contest';
  currentContest = null;
  contestScoringDefs = {};
  qsoLog = [];
  serialByBand = {};
  __fetchCalls = [];
  expeditionMode = false;
  applyExpeditionMode(false);
  pickBand('144');
  document.getElementById('inputCall').value = 'F6KQJ';
  rigState.enabled = true;
  _currentVisibleBands = ['144', '432', '14', '7'];
  _currentVisibleModes = ['SSB', 'CW'];
  __fetchCalls = [];
}
"""


def _ctx(decouple):
    ctx = py_mini_racer.MiniRacer()
    ctx.eval(_DOM_PREAMBLE)
    ctx.eval(_real_source())
    ctx.eval(_NET_STUB)          # après la source : remplace le fetch du préambule
    ctx.eval(_INIT)
    ctx.eval('__init();')
    # On passe par la VRAIE bascule, pas par une écriture directe dans
    # localStorage : si basculer cessait d'enregistrer l'état, un test qui
    # pose la clé lui-même ne s'en apercevrait jamais.
    if decouple:
        ctx.eval('basculerSaisieDecouplee();')
    return ctx


def _vers_radio(ctx):
    """py_mini_racer rend les tableaux JS en objet opaque : on repasse par
    JSON.stringify(), même patron que le reste de la suite."""
    return json.loads(ctx.eval('JSON.stringify(__versRadio())'))


# ─── 1) Saisie découplée : plus rien ne part vers la radio ──────────────────

def test_bascule_puis_choix_de_bande_ne_pilote_plus_la_radio():
    """Le geste exact du scénario : noter un QSO 40 m fait sur l'autre poste."""
    ctx = _ctx(decouple=True)
    ctx.eval("__fetchCalls = []; pickBand('7');")
    envois = _vers_radio(ctx)
    assert envois == [], (
        'saisie découplée : choisir une bande ne doit RIEN envoyer à la radio '
        'pilotée, or %r est parti' % envois)


def test_bascule_puis_choix_de_mode_ne_pilote_plus_la_radio():
    ctx = _ctx(decouple=True)
    ctx.eval("__fetchCalls = []; pickMode('CW');")
    envois = _vers_radio(ctx)
    assert envois == [], (
        'saisie découplée : choisir un mode ne doit RIEN envoyer à la radio '
        'pilotée, or %r est parti' % envois)


def test_la_bande_de_saisie_ne_suit_plus_la_radio():
    """Sans cette coupure, le sondage CAT ramènerait la bande de saisie sur
    celle du poste piloté entre la sélection et la validation — le QSO 40 m
    partirait au carnet avec la bande du FT8."""
    ctx = _ctx(decouple=True)
    ctx.eval("currentBand = '7'; currentMode = 'CW'; syncBandModeFromRig(14200, 'USB');")
    assert ctx.eval('currentBand') == '7', (
        'saisie découplée : la radio ne doit plus imposer sa bande à la saisie')
    assert ctx.eval('currentMode') == 'CW', (
        'saisie découplée : la radio ne doit plus imposer son mode à la saisie')


def test_la_frequence_saisie_n_est_plus_ecrasee_par_la_radio():
    """Le cadenas existant (dataset.userEdited) ne suffit PAS ici : il est
    effacé par setFreqForBand() dès qu'on change de bande. Il faut donc une
    coupure propre au découplage."""
    ctx = _ctx(decouple=True)
    ctx.eval("""
    var f = document.getElementById('inputFreq');
    f.value = '7.030';
    delete f.dataset.userEdited;      // état d'après un changement de bande
    applyRigState({enabled:true, ok:true, freq_khz:14200, mode:'USB'});
    """)
    assert ctx.eval("document.getElementById('inputFreq').value") == '7.030', (
        'saisie découplée : la fréquence du poste piloté ne doit pas remplacer '
        'celle saisie pour un QSO fait ailleurs')


# ─── 2) Non-régression : sans découplage, tout le comportement de 15/08 reste ─

def test_par_defaut_le_choix_de_bande_pilote_toujours_la_radio():
    """Le correctif IC-7300 du 15/08/2026 ne doit pas être annulé au passage :
    par défaut, la saisie pilote toujours la radio."""
    ctx = _ctx(decouple=False)
    ctx.eval("__fetchCalls = []; pickBand('14');")
    qsy = [c for c in _vers_radio(ctx) if c['url'] == '/rig/qsy']
    assert len(qsy) == 1, (
        'par défaut, choisir une bande doit toujours envoyer un /rig/qsy')
    assert qsy[0]['body']['freq_khz'] == 14150


def test_par_defaut_la_bande_de_saisie_suit_toujours_la_radio():
    ctx = _ctx(decouple=False)
    ctx.eval("currentBand = '144'; currentMode = 'CW'; syncBandModeFromRig(14200, 'USB');")
    assert ctx.eval('currentBand') == '14'
    assert ctx.eval('currentMode') == 'SSB'


def test_l_etat_par_defaut_est_bien_relie():
    """Personne ne doit se retrouver découplé sans l'avoir demandé : c'est le
    sens sûr (une radio qui ne suit pas se voit, une radio qui bouge toute
    seule en pleine séquence FT8, non)."""
    ctx = _ctx(decouple=False)
    assert ctx.eval('saisieDecoupleeActive()') is False


# ─── 3) L'état survit à un rechargement, et se voit à l'écran ───────────────

def test_l_etat_est_enregistre_pour_survivre_a_un_rechargement():
    """Une séquence FT8 dure des heures. Si le découplage se perdait à un
    rafraîchissement de page, le premier changement de bande enverrait un QSY
    surprise à la radio."""
    ctx = _ctx(decouple=True)
    assert ctx.eval("localStorage.getItem('rc_saisie_decouplee')") == '1'
    ctx.eval('basculerSaisieDecouplee();')
    assert ctx.eval("localStorage.getItem('rc_saisie_decouplee')") == '0'
    assert ctx.eval('saisieDecoupleeActive()') is False


def test_le_bouton_dit_lequel_des_deux_etats_est_en_cours():
    """Intuitivité : un état qui change le comportement de la radio ne doit
    jamais être invisible. On vérifie le LIBELLÉ vu par l'opérateur, pas
    seulement la variable interne."""
    ctx = _ctx(decouple=False)
    ctx.eval('majBoutonSaisieDecouplee();')
    assert ctx.eval("document.getElementById('posteSourceLabel').textContent") == 'RADIO PILOTÉE'
    assert ctx.eval("document.getElementById('posteSourceBtn').classList.contains('decouple')") is False

    ctx.eval('basculerSaisieDecouplee();')
    assert ctx.eval("document.getElementById('posteSourceLabel').textContent") == 'AUTRE POSTE'
    assert ctx.eval("document.getElementById('posteSourceBtn').classList.contains('decouple')") is True


def test_le_bouton_disparait_sans_radio_pilotee():
    """Sans CAT il n'y a rien à découpler : afficher le bouton serait du bruit.
    Même règle que le cadenas de fréquence juste au-dessus."""
    ctx = _ctx(decouple=False)
    ctx.eval('rigState.enabled = false; majBoutonSaisieDecouplee();')
    assert ctx.eval("document.getElementById('posteSourceGroup').style.display") == 'none'
    ctx.eval('rigState.enabled = true; majBoutonSaisieDecouplee();')
    assert ctx.eval("document.getElementById('posteSourceGroup').style.display") == ''


def test_masquer_le_bouton_ne_remet_pas_l_etat_a_zero():
    """« Masquer n'est pas désactiver » — règle permanente du dépôt. Un CAT qui
    tombe puis revient ne doit pas relier la saisie dans le dos de
    l'opérateur."""
    ctx = _ctx(decouple=True)
    ctx.eval('rigState.enabled = false; majBoutonSaisieDecouplee();')
    ctx.eval('rigState.enabled = true; majBoutonSaisieDecouplee();')
    assert ctx.eval('saisieDecoupleeActive()') is True
    assert ctx.eval("document.getElementById('posteSourceLabel').textContent") == 'AUTRE POSTE'
