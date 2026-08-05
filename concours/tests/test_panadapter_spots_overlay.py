# -*- coding: utf-8 -*-
"""Panadapter : repères de spots du cluster superposés au spectre, comme sur
le band map (demande F4GLD 04/08/2026).

Deux fonctions extraites du fichier LIVRÉ (logx_panadapter.html) et exécutées
dans un moteur V8 réel, même patron que tests/test_scope_etiquettes_chevauchement.py
et tests/test_cw_panel_consolidation.py : la fonction elle-même n'est jamais
recopiée, si la page change le test suit.

  - plageHzActuelle() : bornes RF réelles (Hz au pixel 0, Hz au pixel W) de
    l'axe actuellement affiché, selon la source (audio/CI-V/TCI) — null si
    aucune fréquence absolue n'est calculable.
  - dessinerSpotsOverlay() : place un repère par spot dont la fréquence tombe
    dans cette plage."""
import json
import os
import sys

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CONCOURS not in sys.path:
    sys.path.insert(0, CONCOURS)

PANADAPTER = os.path.join(CONCOURS, 'logx_panadapter.html')
py_mini_racer = pytest.importorskip('py_mini_racer')


def _lire():
    with open(PANADAPTER, encoding='utf-8') as f:
        return f.read()


def _extraire_plage_hz():
    src = _lire()
    debut = src.index('function plageHzActuelle(){')
    fin = src.index('function axeGraduations(nGrad){')
    bloc = src[debut:fin]
    assert 'return null' in bloc, 'plageHzActuelle() introuvable ou modifiee'
    return bloc


def _extraire_overlay():
    src = _lire()
    debut = src.index('let spotsCluster = [];')
    fin = src.index('function dessinerSpectre(){')
    bloc = src[debut:fin]
    assert 'function dessinerSpotsOverlay' in bloc
    return bloc


_DOM_PREAMBLE = r"""
function makeEl(){
  var el = {
    _props: {},
    children: [],
    className: '',
    title: '',
    textContent: '',
    appendChild: function(c){
      if(c && c._isFragment){
        for(var i=0;i<c.children.length;i++) el.children.push(c.children[i]);
        c.children = [];
      } else {
        el.children.push(c);
      }
      return c;
    },
    addEventListener: function(ev, fn){ el._handlers = el._handlers || {}; el._handlers[ev] = fn; },
  };
  el.style = { setProperty: function(k, v){ el._props[k] = v; } };
  Object.defineProperty(el.style, 'left', {
    get: function(){ return el._props.left; },
    set: function(v){ el._props.left = v; }
  });
  return el;
}
var _elements = {};
function elFor(id){ if(!_elements[id]) _elements[id] = makeEl(); return _elements[id]; }
var document = {
  getElementById: function(id){ return elFor(id); },
  createElement: function(tag){ return makeEl(); },
  createDocumentFragment: function(){ var f = makeEl(); f._isFragment = true; return f; },
};
"""


def _ctx_plage():
    ctx = py_mini_racer.MiniRacer()
    ctx.eval(_DOM_PREAMBLE)
    ctx.eval(_extraire_plage_hz())
    ctx.eval("""
    function testerPlage(mode, civL, tciL, rfk, rm, spanVal, rfScale){
      sourceMode = mode; civLine = civL; tciLine = tciL;
      rigFreqKhz = rfk; rigMode = rm;
      elFor('paSpan').value = spanVal;
      elFor('paRfScale').checked = rfScale;
      return plageHzActuelle();
    }
    """)
    return ctx


# ─── plageHzActuelle() ────────────────────────────────────────────────────

def test_plage_civ_mode_center():
    ctx = _ctx_plage()
    civ = {'ok': True, 'mode': 'center', 'center_freq_hz': 14195000, 'span_hz': 25000}
    r = ctx.call('testerPlage', 'civ', civ, None, 0, '', '3000', False)
    assert r == {'hz0': 14182500.0, 'hzW': 14207500.0}


def test_plage_civ_mode_edge():
    ctx = _ctx_plage()
    civ = {'ok': True, 'mode': 'fixed', 'edge_lo_hz': 14000000, 'edge_hi_hz': 14350000}
    r = ctx.call('testerPlage', 'civ', civ, None, 0, '', '3000', False)
    assert r == {'hz0': 14000000, 'hzW': 14350000}


def test_plage_civ_pas_connecte():
    ctx = _ctx_plage()
    assert ctx.call('testerPlage', 'civ', None, None, 0, '', '3000', False) is None
    assert ctx.call('testerPlage', 'civ', {'ok': False}, None, 0, '', '3000', False) is None


def test_plage_tci():
    ctx = _ctx_plage()
    tci = {'ok': True, 'center_freq_hz': 7100000, 'span_hz': 192000}
    r = ctx.call('testerPlage', 'tci', None, tci, 0, '', '3000', False)
    assert r == {'hz0': 7004000.0, 'hzW': 7196000.0}


def test_plage_tci_pas_connecte():
    ctx = _ctx_plage()
    assert ctx.call('testerPlage', 'tci', None, None, 0, '', '3000', False) is None


def test_plage_audio_usb_avec_echelle_rf():
    """USB : le son grave = bas de la porteuse -> RF = dial + audio, axe
    CROISSANT (hz0 < hzW)."""
    ctx = _ctx_plage()
    r = ctx.call('testerPlage', 'audio', None, None, 14195, 'USB', '3000', True)
    assert r == {'hz0': 14195000, 'hzW': 14198000}


def test_plage_audio_lsb_avec_echelle_rf():
    """LSB : inverse -> RF = dial - audio, axe DÉCROISSANT (hz0 > hzW) —
    voulu, pas un bug (voir le commentaire de plageHzActuelle())."""
    ctx = _ctx_plage()
    r = ctx.call('testerPlage', 'audio', None, None, 7130, 'LSB', '3000', True)
    assert r == {'hz0': 7130000, 'hzW': 7127000}


def test_plage_audio_sans_echelle_rf():
    ctx = _ctx_plage()
    assert ctx.call('testerPlage', 'audio', None, None, 14195, 'USB', '3000', False) is None


def test_plage_audio_mode_non_ssb_meme_case_cochee():
    """CW/AM/FM : pas de convention fiable dial+/-audio (offset de ton
    variable par poste) — l'échelle RF ne s'applique qu'en USB/LSB."""
    ctx = _ctx_plage()
    assert ctx.call('testerPlage', 'audio', None, None, 14195, 'CW', '3000', True) is None


def test_plage_audio_sans_frequence_radio_connue():
    ctx = _ctx_plage()
    assert ctx.call('testerPlage', 'audio', None, None, 0, 'USB', '3000', True) is None


# ─── dessinerSpotsOverlay() ────────────────────────────────────────────────

def _ctx_overlay():
    ctx = py_mini_racer.MiniRacer()
    ctx.eval(_DOM_PREAMBLE)
    ctx.eval(_extraire_plage_hz())
    ctx.eval(_extraire_overlay())
    ctx.eval("""
    function testerOverlay(mode, civL, tciL, rfk, rm, spanVal, rfScale, spots){
      sourceMode = mode; civLine = civL; tciLine = tciL;
      rigFreqKhz = rfk; rigMode = rm;
      elFor('paSpan').value = spanVal;
      elFor('paRfScale').checked = rfScale;
      spotsCluster = spots;
      dessinerSpotsOverlay();
      var overlay = elFor('spotOverlay');
      return overlay.children.map(function(m){
        return {left: m._props.left, call: m.children[0].textContent, color: m._props['--c']};
      });
    }
    """)
    return ctx


def _spot(call, freq_khz, **kw):
    s = {'call': call, 'freq': freq_khz, 'new_mult': False}
    s.update(kw)
    return s


def test_overlay_spot_dans_la_plage_civ():
    ctx = _ctx_overlay()
    civ = {'ok': True, 'mode': 'center', 'center_freq_hz': 14195000, 'span_hz': 25000}
    # centre exact -> 50% de la largeur
    marques = ctx.call('testerOverlay', 'civ', civ, None, 0, '', '3000', False,
                       [_spot('W1AW', 14195.0)])
    assert len(marques) == 1
    assert marques[0]['call'] == 'W1AW'
    assert abs(float(marques[0]['left'].rstrip('%')) - 50.0) < 0.5


def test_overlay_spot_hors_plage_ignore():
    ctx = _ctx_overlay()
    civ = {'ok': True, 'mode': 'center', 'center_freq_hz': 14195000, 'span_hz': 25000}
    marques = ctx.call('testerOverlay', 'civ', civ, None, 0, '', '3000', False,
                       [_spot('LOIN', 14500.0)])   # tres au-dela du span de 25 kHz
    assert marques == []


def test_overlay_bord_gauche_et_bord_droit():
    ctx = _ctx_overlay()
    civ = {'ok': True, 'mode': 'fixed', 'edge_lo_hz': 14000000, 'edge_hi_hz': 14350000}
    marques = ctx.call('testerOverlay', 'civ', civ, None, 0, '', '3000', False,
                       [_spot('BORD_BAS', 14000.0), _spot('BORD_HAUT', 14350.0)])
    gauches = sorted(float(m['left'].rstrip('%')) for m in marques)
    assert abs(gauches[0] - 0.0) < 0.5
    assert abs(gauches[1] - 100.0) < 0.5


def test_overlay_aucune_plage_calculable_reste_vide():
    """Audio sans echelle RF : plageHzActuelle() renvoie null, donc AUCUN
    repere ne doit apparaitre (pas de frequence absolue a quoi les rattacher)."""
    ctx = _ctx_overlay()
    marques = ctx.call('testerOverlay', 'audio', None, None, 14195, 'USB', '3000', False,
                       [_spot('W1AW', 14195.0)])
    assert marques == []


def test_overlay_aucun_spot_reste_vide():
    ctx = _ctx_overlay()
    civ = {'ok': True, 'mode': 'center', 'center_freq_hz': 14195000, 'span_hz': 25000}
    assert ctx.call('testerOverlay', 'civ', civ, None, 0, '', '3000', False, []) == []


def test_overlay_nouveau_multiplicateur_couleur_distincte():
    ctx = _ctx_overlay()
    civ = {'ok': True, 'mode': 'center', 'center_freq_hz': 14195000, 'span_hz': 25000}
    marques = ctx.call('testerOverlay', 'civ', civ, None, 0, '', '3000', False,
                       [_spot('NEUF', 14195.0, new_mult=True), _spot('CONNU', 14196.0, new_mult=False)])
    par_call = {m['call']: m['color'] for m in marques}
    assert par_call['NEUF'] == 'var(--green)'
    assert par_call['CONNU'] == 'var(--yellow)'


def test_overlay_lsb_axe_decroissant_positionne_correctement():
    """Vérifie que le formulaire (freq-hz0)/(hzW-hz0) marche aussi quand
    hzW < hz0 (LSB) — pas seulement le cas croissant CI-V/TCI/USB."""
    ctx = _ctx_overlay()
    # dial 7130 kHz, span 3000 Hz, LSB -> hz0=7130000 (x=0%), hzW=7127000 (x=100%)
    marques = ctx.call('testerOverlay', 'audio', None, None, 7130, 'LSB', '3000', True,
                       [_spot('MILIEU', 7128.5)])   # exactement au centre de la plage
    assert len(marques) == 1
    assert abs(float(marques[0]['left'].rstrip('%')) - 50.0) < 0.5
