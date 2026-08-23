# -*- coding: utf-8 -*-
"""A06 (docs/FEUILLE_DE_ROTE.md) : couper une émission CW en WinKeyer SANS
CAT. Backend et logique client sont déjà corrigés (Lot 1, PR #108, revue
adversariale du 18/08/2026) -- ce test ferme le seul trou de couverture
restant : la logique JS (cwPiloteDisponible/updateCwStopBtn), jamais
exercée jusqu'ici (seul /hardware/state, côté serveur, l'était).

Le vrai critère d'acceptation du document ("déclencher une émission WinKeyer
sans CAT, vérifier que le raccourci l'arrête réellement") exige du matériel
et reste un test MANUEL -- ce module ne prétend pas le remplacer, il
verrouille seulement la logique qui décide QUAND le coupe-circuit doit
apparaître, pour qu'une régression future s'y heurte."""
import os

import pytest

py_mini_racer = pytest.importorskip(
    'py_mini_racer', reason='py_mini_racer absent (voir requirements.txt) — test JS réel ignoré')

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS_PATH = os.path.join(BASE, 'logx_hardware_cat.js')

_PREAMBLE = r"""
var __panels = {};
function ElProxy(id){
  var s = {style:{display:''}, textContent:''};
  var cls = { toggle:function(){}, add:function(){}, remove:function(){}, contains:function(){return false;} };
  __panels[id] = s;
  return new Proxy({}, { get:function(t,p){
                            if(p==='style') return s.style;
                            if(p==='classList') return cls;
                            if(p==='setAttribute' || p==='getAttribute') return function(){};
                            return s[p];
                          },
                          set:function(t,p,v){ s[p]=v; return true; } });
}
var document = { readyState: 'loading', addEventListener: function(){},
                 getElementById: function(id){ return __panels[id] || (__panels[id]=ElProxy(id)); } };
var __fetchCalls = [];
function fetch(url, opts){ __fetchCalls.push(url); return Promise.resolve({ok:true, json:function(){return Promise.resolve({});}}); }
"""


def _ctx():
    ctx = py_mini_racer.MiniRacer()
    ctx.eval(_PREAMBLE)
    with open(JS_PATH, encoding='utf-8') as f:
        ctx.eval(f.read())
    return ctx


def test_coupe_circuit_disponible_avec_winkeyer_seul_sans_cat():
    """Le coeur du défaut A06 : sans CAT, avec WinKeyer actif, le pilote
    doit être déclaré disponible -- sinon le bouton STOP reste invisible."""
    ctx = _ctx()
    ctx.eval("winkeyerState.enabled = true;")   # rigState indéfini = pas de CAT
    assert ctx.eval("cwPiloteDisponible()") is True


def test_coupe_circuit_indisponible_sans_cat_ni_winkeyer():
    ctx = _ctx()
    assert ctx.eval("cwPiloteDisponible()") is False


def test_bouton_stop_visible_des_que_winkeyer_actif_quel_que_soit_le_mode():
    """Piège corrigé en revue adversariale (18/08) : conditionner au MODE
    courant désarme le coupe-circuit en pleine émission, un message déjà
    parti continuant de se vider du tampon même après un changement de
    mode. updateCwStopBtn() doit rester indifférent au mode."""
    ctx = _ctx()
    ctx.eval("winkeyerState.enabled = true; currentMode = 'SSB';")
    ctx.eval("applyWinkeyerState({enabled:true});")
    assert ctx.eval("document.getElementById('cwStopPanel').style.display") == 'block'


def test_bouton_stop_cache_sans_aucun_pilote():
    ctx = _ctx()
    ctx.eval("applyWinkeyerState({enabled:false});")
    assert ctx.eval("document.getElementById('cwStopPanel').style.display") == 'none'


def test_rig_stop_cw_appelle_bien_lendpoint_serveur():
    ctx = _ctx()
    ctx.eval("rigStopCW();")
    assert ctx.eval("JSON.stringify(__fetchCalls)") == '["/rig/stop"]'
