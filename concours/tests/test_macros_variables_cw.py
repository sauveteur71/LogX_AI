# -*- coding: utf-8 -*-
"""Macros keyer CW Phase 1 : nouveaux jetons + F9–F12 + migration douce.

Jetons ajoutés à expandMacro() : {MYCALL}(=ma station), {SERIAL}(={NR}), {RST}
(champ #inputRSTsent, repli _rstParDefaut(mode)), {NAME}(op_name config),
{QTH}(city config). getMacros() garantit F1–F12 sans écraser les perso.

Vrai code extrait par comptage d'accolades, exécuté en V8 (py_mini_racer).
"""
import json
import os
import re

import pytest

py_mini_racer = pytest.importorskip('py_mini_racer', reason='py_mini_racer absent')

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS = os.path.join(BASE, 'logx_macros.js')


def _extract_function(src, name):
    m = re.search(r'^function %s\(' % re.escape(name), src, re.M)
    assert m, name
    depth = 0
    i = src.index('{', m.start())
    while True:
        if src[i] == '{':
            depth += 1
        elif src[i] == '}':
            depth -= 1
            if depth == 0:
                return src[m.start():i + 1]
        i += 1


with open(JS, encoding='utf-8') as f:
    _SRC = f.read()
_DEFAULTS = re.search(r'const DEFAULT_MACROS = \[.*?\];', _SRC, re.S).group(0)
_PIECES = '\n'.join([_DEFAULTS,
                     _extract_function(_SRC, '_hisCall'),
                     _extract_function(_SRC, 'expandMacro'),
                     _extract_function(_SRC, 'getMacros')])

_PREAMBLE = r"""
var _fields = {};
var document = { getElementById:function(id){ return _fields[id] || (_fields[id]={value:''}); } };
var _ls = {};
var localStorage = { getItem:function(k){ return (k in _ls)?_ls[k]:null; },
                     setItem:function(k,v){ _ls[k]=String(v); } };
var myCall='F4GLD', myLocator='JN15WD';
var currentExchange = {auto_serial:true};
var serialByBand = {'14':13};
var currentBand='14';
var currentMode='CW';
function _rstParDefaut(mode){ return /CW/i.test(mode)?'599':'59'; }
"""


def _ctx():
    c = py_mini_racer.MiniRacer()
    c.eval(_PREAMBLE + '\n' + _PIECES)
    return c


def test_nouveaux_jetons_toutes_sources_reelles():
    c = _ctx()
    c.eval("_ls['logx_config'] = " + json.dumps(json.dumps(
        {'callsign': 'TM6KJS', 'locator': 'JN15', 'op_name': 'JEAN', 'city': 'PARIS'})) + ";")
    c.eval("_fields['inputCall'] = {value:'F5ABC'};")
    c.eval("_fields['inputNumSent'] = {value:'007'};")
    c.eval("_fields['inputRSTsent'] = {value:''};")   # vide -> repli _rstParDefaut
    out = c.eval("expandMacro('{MYCALL} {CALL} {HISCALL} {SERIAL} {NR} {RST} {NAME} {QTH} {LOC}')")
    assert out == 'TM6KJS TM6KJS F5ABC 007 007 599 JEAN PARIS JN15', out


def test_rst_depuis_le_champ_si_renseigne():
    c = _ctx()
    c.eval("_ls['logx_config'] = '{}';")
    c.eval("_fields['inputRSTsent'] = {value:'559'};")
    assert c.eval("expandMacro('{RST}')") == '559'


def test_jeton_sans_source_ne_laisse_pas_de_parasite():
    # op_name/city absents -> '' (jamais 'undefined' ni un caractère sur l'air)
    c = _ctx()
    c.eval("_ls['logx_config'] = '{}';")
    out = c.eval("expandMacro('OP {NAME} QTH {QTH}')")
    assert out == 'OP  QTH ' and 'undefined' not in out, repr(out)


def test_getmacros_defaut_est_f1_a_f12():
    c = _ctx()
    assert c.eval("getMacros().length") == 12
    assert c.eval("getMacros().map(function(m){return m.key;}).join(',')") \
        == 'F1,F2,F3,F4,F5,F6,F7,F8,F9,F10,F11,F12'


def test_getmacros_migre_un_ancien_log_f1_a_f8_sans_ecraser():
    c = _ctx()
    ancien = [{'key': 'F%d' % i, 'label': 'L%d' % i, 'text': 'T%d' % i} for i in range(1, 9)]
    ancien[0] = {'key': 'F1', 'label': 'MON CQ', 'text': 'CQ PERSO'}   # F1 personnalisé
    c.eval("_ls['logx_macros'] = " + json.dumps(json.dumps(ancien)) + ";")
    assert c.eval("getMacros().length") == 12                      # F9–F12 ajoutés
    assert c.eval("getMacros()[0].text") == 'CQ PERSO'             # perso préservé
    assert c.eval("getMacros()[10].key") == 'F11'                  # défaut ajouté
