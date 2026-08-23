# -*- coding: utf-8 -*-
"""getVoiceDynMacros() ne doit pas renvoyer la RÉFÉRENCE de la const
VOICE_MACRO_DEFAULT (sinon editVoiceDynMacro la mute en place).

Tant qu'aucune macro n'est sauvegardée, getVoiceDynMacros() renvoyait
directement VOICE_MACRO_DEFAULT ; editVoiceDynMacro fait `macros[idx]={...}` ->
il écrivait dans le tableau de défaut lui-même, corrompant les valeurs d'usine
pour toute la session (et le repli en cas de localStorage illisible).

Correctif : renvoyer une COPIE du défaut. Vrai code extrait du fichier et
exécuté en V8 (py_mini_racer).
"""
import os
import re

import pytest

py_mini_racer = pytest.importorskip('py_mini_racer', reason='py_mini_racer absent')

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS = os.path.join(BASE, 'logx_esm_callbot.js')


def _extract_function(src, name):
    m = re.search(r'^(?:async\s+)?function %s\(' % re.escape(name), src, re.M)
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
_CONST = re.search(r'const VOICE_MACRO_DEFAULT = \[[\s\S]*?\];', _SRC).group(0)
_GET = _extract_function(_SRC, 'getVoiceDynMacros')

_PREAMBLE = r"""
var _store = {};
var localStorage = { getItem:function(k){ return (k in _store)?_store[k]:null; },
                     setItem:function(k,v){ _store[k]=String(v); } };
"""


def test_le_defaut_n_est_pas_mute_par_l_appelant():
    c = py_mini_racer.MiniRacer()
    c.eval(_PREAMBLE + '\n' + _CONST + '\n' + _GET)
    # localStorage vide -> on obtient le défaut ; on le mute
    c.eval("var a = getVoiceDynMacros(); a[0].label = 'HACKED';")
    # un nouvel appel doit rendre les valeurs d'USINE, pas la mutation
    assert c.eval("getVoiceDynMacros()[0].label") == 'CQ', \
        "getVoiceDynMacros() partage la const VOICE_MACRO_DEFAULT (mutation propagée)"
