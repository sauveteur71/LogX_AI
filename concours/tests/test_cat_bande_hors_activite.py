# -*- coding: utf-8 -*-
"""La bande de saisie doit suivre la VRAIE fréquence radio, même quand cette
bande n'est pas dans les bandes visibles de l'activité en cours.

LE DÉFAUT (remonté par F4GLD, capture d'écran) : en activité V/UHF (bandes
visibles 2 m / 70 cm…), tourner la radio sur 10 m (28.601 MHz) mettait bien la
FRÉQUENCE de saisie à 28.601 (appliquée sans condition par applyRigState) mais
laissait la BANDE sur « 2m » — car syncBandModeFromRig ne changeait la bande que
si elle figurait dans _currentVisibleBands. Résultat : couple bande/fréquence
INCOHÉRENT → QSO loggué avec la mauvaise bande.

Le correctif : la radio pilotée est SOURCE DE VÉRITÉ — sa bande réelle prime,
qu'elle soit ou non dans les bandes proposées par l'activité. Le garde
_currentVisibleBands reste, lui, pour la saisie MANUELLE d'une fréquence (ne pas
sauter sur une bande non proposée en tapant) — distinction vérifiée ci-dessous.

Tests sur les VRAIS logx_logbook.js / logx_hardware_cat.js dans un moteur JS
réel (même patron que test_saisie_decouplee_radio.py)."""
import pytest

py_mini_racer = pytest.importorskip(
    'py_mini_racer', reason='py_mini_racer absent — test JS réel ignoré')

from test_cat_manual_bandmode_qsy import _DOM_PREAMBLE, _real_source  # noqa: E402

_NET_STUB = r"""
function fetch(url, opts){
  return Promise.resolve({ok:true, status:200, json:function(){ return Promise.resolve({}); }});
}
"""

_INIT = r"""
function __init(){
  myCall = 'F4TEST'; myLocator = 'JN03QQ'; myOp = 'OP1';
  usageMode = 'contest'; currentContest = null; contestScoringDefs = {};
  qsoLog = []; serialByBand = {}; expeditionMode = false;
  applyExpeditionMode(false);
  pickBand('144');
  rigState.enabled = true;
  // Activité V/UHF : seules les bandes VHF+ sont proposées (10 m ABSENT).
  _currentVisibleBands = ['144', '432'];
  _currentVisibleModes = ['SSB', 'CW'];
}
"""


def _ctx():
    ctx = py_mini_racer.MiniRacer()
    ctx.eval(_DOM_PREAMBLE)
    ctx.eval(_real_source())
    ctx.eval(_NET_STUB)
    ctx.eval(_INIT)
    ctx.eval('__init();')
    return ctx


def test_la_bande_suit_la_radio_meme_hors_bandes_visibles():
    """Le scénario de la capture : radio réellement sur 10 m en activité V/UHF."""
    ctx = _ctx()
    ctx.eval("applyRigState({enabled:true, ok:true, freq_khz:28601, mode:'USB'});")
    assert ctx.eval('currentBand') == '28', (
        'la bande de saisie doit suivre la vraie fréquence radio (10 m), '
        'pas rester sur la bande de l\'activité')
    assert ctx.eval("document.getElementById('inputFreq').value") == '28.601', (
        'la fréquence doit rester cohérente avec la bande')


def test_bande_et_frequence_restent_coherentes():
    """Cœur du bug : jamais fréquence d'une bande et libellé d'une autre."""
    ctx = _ctx()
    ctx.eval("applyRigState({enabled:true, ok:true, freq_khz:28601, mode:'USB'});")
    from_band = ctx.eval('currentBand')
    freq = float(ctx.eval("document.getElementById('inputFreq').value"))
    # 28.601 MHz appartient bien à la bande retenue (10 m = '28'), pas à '144'.
    assert from_band == '28' and 28.0 <= freq <= 29.7


def test_saisie_manuelle_reste_contrainte_aux_bandes_visibles():
    """NON-régression : le garde _currentVisibleBands reste pour la saisie
    MANUELLE — taper 28.601 en activité V/UHF ne doit PAS changer la bande
    (seule la vraie radio en a le droit)."""
    ctx = _ctx()
    ctx.eval("var f=document.getElementById('inputFreq'); f.value='28.601'; onFreqInput();")
    assert ctx.eval('currentBand') == '144', (
        'taper une fréquence hors des bandes de l\'activité ne doit pas '
        'changer la bande (contrairement à la vraie radio)')


def test_la_bande_suit_toujours_la_radio_dans_les_bandes_visibles():
    """NON-régression du correctif IC-7300 : radio sur une bande visible (20 m)."""
    ctx = _ctx()
    ctx.eval("_currentVisibleBands = ['144','432','14'];")
    ctx.eval("applyRigState({enabled:true, ok:true, freq_khz:14200, mode:'USB'});")
    assert ctx.eval('currentBand') == '14'
