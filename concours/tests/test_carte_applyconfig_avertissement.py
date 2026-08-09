# -*- coding: utf-8 -*-
"""logx_carte.html:applyConfig() affichait « ✅ Configuration chargée ! » dès que
`logx_config` existait dans localStorage — MÊME quand l'indicatif et le
locator étaient VIDES (station affichée « — »). Un opérateur qui n'a JAMAIS
rempli CONFIG voyait donc un message de succès trompeur au lieu d'être
prévenu qu'il doit d'abord se configurer.

Ce module exécute le VRAI applyConfig() (+ showConfigIncomplete(), sa nouvelle
fonction d'avertissement) extraits du fichier source dans un moteur JS réel
(V8 via py_mini_racer, même technique que tests/test_carte_ne_pousse_pas_la_config.py
et tests/test_qtc_panel_js.py), avec un DOM minimal — pas une relecture du
code, une exécution.
"""
import json
import os

import pytest

py_mini_racer = pytest.importorskip(
    'py_mini_racer', reason='py_mini_racer absent (voir requirements.txt) — test JS réel ignoré')

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML_PATH = os.path.join(BASE, 'logx_carte.html')


def _extract_function(src, name):
    """Extrait `function <name>(){...}` par comptage d'accolades : on exécute
    le VRAI code du fichier, pas une réécriture qui pourrait diverger."""
    start = src.index(f'function {name}(')
    i = src.index('{', start)
    depth = 0
    while True:
        if src[i] == '{':
            depth += 1
        elif src[i] == '}':
            depth -= 1
            if depth == 0:
                return src[start:i + 1]
        i += 1


with open(HTML_PATH, encoding='utf-8') as _f:
    _SRC = _f.read()

_APPLY_CONFIG_SRC = _extract_function(_SRC, 'applyConfig')
_SHOW_CONFIG_INCOMPLETE_SRC = _extract_function(_SRC, 'showConfigIncomplete')

# DOM minimal : juste ce dont applyConfig()/showConfigIncomplete() ont besoin
# (getElementById, createElement, createTextNode). addMsg() et rcT() sont
# stubbés — ce ne sont pas l'objet du test, seul applyConfig()/
# showConfigIncomplete() doit être du VRAI code.
_PREAMBLE = r"""
var __store = {};
function ElProxy(){
  var s = {textContent:'', innerHTML:'', className:'', href:'', style:{}, children:[]};
  var handler = {
    get:function(target, prop){
      if(prop === 'appendChild') return function(c){ s.children.push(c); return c; };
      if(prop === 'setAttribute') return function(){};
      if(prop === 'getAttribute') return function(){ return null; };
      if(prop === '__snapshot') return function(){
        return {className: s.className, textContent: s.textContent, href: s.href,
                children: s.children.map(function(c){
                  return (c && c.__snapshot) ? c.__snapshot() : c;
                })};
      };
      return s[prop];
    },
    set:function(target, prop, val){ s[prop] = val; return true; }
  };
  return new Proxy({}, handler);
}
var document = {
  getElementById: function(id){ if(!__store[id]) __store[id] = ElProxy(); return __store[id]; },
  createElement: function(){ return ElProxy(); },
  createTextNode: function(text){ var n = ElProxy(); n.textContent = text; return n; }
};
var __addMsgCalls = [];
function addMsg(role, text, type){ __addMsgCalls.push({role: role, text: text, type: type || ''}); }
function rcT(s){ return s; }
var cfg = {};
"""


def _run(cfg_dict):
    ctx = py_mini_racer.MiniRacer()
    ctx.eval(_PREAMBLE)
    ctx.eval(_SHOW_CONFIG_INCOMPLETE_SRC)
    ctx.eval(_APPLY_CONFIG_SRC)
    ctx.eval('cfg = %s;' % json.dumps(cfg_dict))
    ctx.eval('applyConfig();')
    calls = json.loads(ctx.eval('JSON.stringify(__addMsgCalls)'))
    chat = json.loads(ctx.eval("JSON.stringify(document.getElementById('chatMsgs').__snapshot())"))
    return calls, chat


def _bubble_of(chat):
    """La bulle d'avertissement est le 2e enfant (après le libellé AGENT) du
    dernier message ajouté à #chatMsgs."""
    assert chat['children'], 'aucun message ajouté à #chatMsgs'
    msg_div = chat['children'][-1]
    assert len(msg_div['children']) == 2, msg_div
    return msg_div['children'][1]


def _bubble_text(bubble):
    return ''.join(c.get('textContent') or '' for c in bubble['children'])


# ─── Callsign ET locator vides : le cas du bug d'origine ───────────────────

def test_config_jamais_remplie_pas_de_faux_succes():
    calls, chat = _run({'callsign': '', 'locator': '', 'contest': 'CQ_WW_SSB'})
    assert not calls, (
        f"applyConfig() affiche encore 'Configuration chargée !' alors que "
        f"l'indicatif et le locator sont vides : {calls}")


def test_config_jamais_remplie_avertissement_explicite():
    _, chat = _run({'callsign': '', 'locator': '', 'contest': 'CQ_WW_SSB'})
    bub = _bubble_of(chat)
    assert bub['className'] == 'bubble warn-config'
    assert 'incomplète' in _bubble_text(bub).lower()


def test_config_jamais_remplie_lien_cliquable_vers_config():
    _, chat = _run({'callsign': '', 'locator': '', 'contest': 'CQ_WW_SSB'})
    bub = _bubble_of(chat)
    liens = [c for c in bub['children'] if c.get('href')]
    assert len(liens) == 1, bub
    assert liens[0]['href'] == 'logx_configuration.html'
    assert liens[0]['textContent'] == 'CONFIG'


# ─── Un seul des deux champs vide : toujours un avertissement ──────────────

def test_locator_seul_vide_avertit_aussi():
    calls, chat = _run({'callsign': 'F4GLD', 'locator': '   ', 'contest': 'CQ_WW_SSB'})
    assert not calls
    bub = _bubble_of(chat)
    assert bub['className'] == 'bubble warn-config'
    assert 'locator' in _bubble_text(bub).lower()


def test_callsign_seul_vide_avertit_aussi():
    calls, chat = _run({'callsign': '', 'locator': 'JN18AA', 'contest': 'CQ_WW_SSB'})
    assert not calls
    bub = _bubble_of(chat)
    assert bub['className'] == 'bubble warn-config'
    assert 'indicatif' in _bubble_text(bub).lower()


# ─── Config complète : le message de succès existant est inchangé ─────────

def test_config_complete_garde_le_message_de_succes():
    calls, chat = _run({'callsign': 'F4GLD', 'locator': 'JN18AA', 'contest': 'CQ_WW_SSB',
                        'toggles': {'mode_ssb': True, 'band_20m': True}})
    assert len(calls) == 1, calls
    assert 'Configuration chargée' in calls[0]['text']
    assert not chat['children'], (
        "showConfigIncomplete() ne doit pas être appelée quand la config est complète")


def test_callsign_contest_compte_comme_indicatif_renseigne():
    """`callsign_contest` (indicatif spécifique au concours) est le repli
    utilisé par le reste d'applyConfig() pour l'affichage — il doit aussi
    compter comme « indicatif renseigné » pour ne pas avertir à tort."""
    calls, chat = _run({'callsign': '', 'callsign_contest': 'F4GLD/P',
                        'locator': 'JN18AA', 'contest': 'CQ_WW_SSB'})
    assert len(calls) == 1, calls
    assert not chat['children']
