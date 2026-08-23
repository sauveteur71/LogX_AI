# -*- coding: utf-8 -*-
"""Terminal CW (logx_cw_terminal.js) : envoi via le chemin gardé, journal, Échap.

Le terminal ne crée AUCUN chemin d'émission : il passe par cwEnvoyerTexte()
(logx_macros.js → garde-fou serveur logx_cw_guard). On vérifie ici, en V8 réel,
que cwTermSend() route bien par ce chemin, vide la saisie sur succès et la
conserve sur refus, et que cwTermKey() déclenche STOP sur Échap.
"""
import os
import re

import pytest

py_mini_racer = pytest.importorskip('py_mini_racer', reason='py_mini_racer absent')

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TERM = os.path.join(BASE, 'logx_cw_terminal.js')
with open(TERM, encoding='utf-8') as f:
    _TERM_SRC = f.read()

_PRE = r"""
var __calls = [], __rows = [];
var _input = {value:''};
var _log = {appendChild:function(r){ __rows.push(r); }, scrollTop:0, scrollHeight:0};
var _wpm = {textContent:''};
var __stopped = 0;
var document = {
  getElementById:function(id){
    return id==='cwTermInput'?_input : id==='cwTermLog'?_log : id==='cwTermWpm'?_wpm : null;
  },
  createElement:function(){ return {className:'', textContent:''}; }
};
function rigStopCW(){ __stopped++; }
"""


def _ctx(reponse):
    c = py_mini_racer.MiniRacer()
    c.eval(_PRE)
    c.eval("function cwEnvoyerTexte(t){ __calls.push(t); return Promise.resolve(%s); }" % reponse)
    c.eval(_TERM_SRC)
    return c


def test_envoi_accepte_route_par_le_chemin_garde_et_vide_la_saisie():
    c = _ctx("{ok:true, wpm:28}")
    c.eval("_input.value = 'CQ TEST F4GLD';")
    c.eval("cwTermSend();")
    assert c.eval("__calls.join('|')") == 'CQ TEST F4GLD'   # passé à cwEnvoyerTexte
    assert c.eval("_input.value") == ''                     # vidé sur succès
    assert c.eval("__rows.length") == 1
    assert c.eval("_wpm.textContent") == '28 mots/min'      # WPM renvoyé par le keyer


def test_envoi_refuse_conserve_la_saisie_et_marque_le_journal():
    c = _ctx("{ok:false, error:'TX non armé'}")
    c.eval("_input.value = 'CQ';")
    c.eval("cwTermSend();")
    assert c.eval("__calls.join('|')") == 'CQ'
    assert c.eval("_input.value") == 'CQ'                   # NON vidé (refus)
    assert c.eval("__rows.length") == 1
    assert c.eval("__rows[0].className").find('refuse') >= 0


def test_saisie_vide_n_emet_rien():
    c = _ctx("{ok:true}")
    c.eval("_input.value = '   ';")
    c.eval("cwTermSend();")
    assert c.eval("__calls.length") == 0


def test_echap_declenche_le_stop_et_vide():
    c = _ctx("{ok:true}")
    c.eval("_input.value = 'CQ';")
    c.eval("cwTermKey({key:'Escape', preventDefault:function(){}});")
    assert c.eval("__stopped") == 1
    assert c.eval("_input.value") == ''


def test_entree_envoie():
    c = _ctx("{ok:true, wpm:25}")
    c.eval("_input.value = '73';")
    c.eval("cwTermKey({key:'Enter', preventDefault:function(){}});")
    assert c.eval("__calls.join('|')") == '73'


def test_html_cable_le_terminal():
    html = open(os.path.join(BASE, 'logx_logbook.html'), encoding='utf-8').read()
    assert 'logx_cw_terminal.js' in html                       # script inclus
    assert re.search(r'id="cwTermInput"[^>]*onkeydown="cwTermKey\(event\)"', html)
    assert 'id="cwTerminalPanel"' in html
