# -*- coding: utf-8 -*-
"""Audit : les Sets d'alertes FT8 (_wsjtxAlerted/_carresAlertes) croissaient sans
borne (une entrée par décodage unique) -> fuite mémoire sur une longue session.
_capSet borne la taille en oubliant les plus anciens."""
import os
import re

import pytest

py_mini_racer = pytest.importorskip('py_mini_racer')

JS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logx_hardware_cat.js')


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


def test_capset_borne_le_set():
    src = open(JS, encoding='utf-8').read()
    mx = int(re.search(r'const _MAX_ALERTES = (\d+);', src).group(1))
    c = py_mini_racer.MiniRacer()
    c.eval("var _MAX_ALERTES = %d;" % mx)
    c.eval(_fn(src, '_capSet'))
    c.eval("var s = new Set(); for(var i=0;i<%d;i++){ s.add('k'+i); _capSet(s); }" % (mx + 500))
    size = c.eval("s.size")
    assert size <= mx, "le Set d'alertes doit être borné (%d > %d)" % (size, mx)
    # Les entrées les plus récentes sont conservées (les anciennes oubliées).
    assert c.eval("s.has('k%d')" % (mx + 499)) is True
    assert c.eval("s.has('k0')") is False
