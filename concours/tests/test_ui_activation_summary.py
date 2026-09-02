# -*- coding: utf-8 -*-
"""UI M4 : renderActivationSummary (panneau DIPLÔMES) rend le résumé à vie des
activations/chasses par programme. Vrai code exécuté dans V8."""
import os
import re

import pytest

py_mini_racer = pytest.importorskip('py_mini_racer')

JS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logx_awards.js')


def _fn(src, nom):
    m = re.search(r'\n\s*function ' + re.escape(nom) + r'\s*\(', src)
    assert m, nom
    i = src.index('function', m.start()); j = src.index('{', i); prof = 0
    for k in range(j, len(src)):
        if src[k] == '{':
            prof += 1
        elif src[k] == '}':
            prof -= 1
            if prof == 0:
                return src[i:k + 1]
    raise AssertionError


def _ctx():
    src = open(JS, encoding='utf-8').read()
    c = py_mini_racer.MiniRacer()
    c.eval("function escHtml(s){ return String(s).replace(/</g,'&lt;'); }")
    c.eval("var _ACT_NOMS = " + re.search(r'const _ACT_NOMS = (\{[^}]+\});', src).group(1) + ";")
    c.eval(_fn(src, 'renderActivationSummary'))
    return c


def test_rend_les_programmes_avec_activite():
    c = _ctx()
    html = c.eval("""renderActivationSummary({
        POTA:{activated:2, hunted:1, activated_refs:['FR-0123','FR-0456'], hunted_refs:['US-1111']},
        SOTA:{activated:0, hunted:3, activated_refs:[], hunted_refs:['F/AB-001','F/AB-002','F/AB-003']}
    })""")
    assert 'POTA' in html and '2 activé' in html and '1 chassé' in html
    assert 'SOTA' in html and '3 chassé' in html
    assert 'FR-0123' in html and 'US-1111' in html   # réf dans le title


def test_message_si_aucune_activite():
    c = _ctx()
    html = c.eval("renderActivationSummary({})")
    assert 'Aucune activation' in html
