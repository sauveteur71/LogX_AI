# -*- coding: utf-8 -*-
"""Audit : findNetworkUpdatePath n'avait pas de verrou -> des clics répétés
lançaient des scans réseau PARALLÈLES. Un flag empêche désormais un 2e scan tant
que le 1er est en vol."""
import os
import re

import pytest

py_mini_racer = pytest.importorskip('py_mini_racer')

JS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logx_version_badge.js')


def _fn(src, nom):
    m = re.search(r'\n\s*(async\s+)?function ' + re.escape(nom) + r'\s*\(', src)
    assert m, nom
    pre = 'async ' if m.group(1) else ''
    i = src.index('function', m.start()); j = src.index('{', i); prof = 0
    for k in range(j, len(src)):
        if src[k] == '{':
            prof += 1
        elif src[k] == '}':
            prof -= 1
            if prof == 0:
                return pre + src[i:k + 1]
    raise AssertionError


def test_pas_de_scan_parallele():
    src = open(JS, encoding='utf-8').read()
    c = py_mini_racer.MiniRacer()
    c.eval("""
        var _fetchCount = 0;
        var _lastPeerList = [{ip:'1.2.3.4'}];
        var _scanReseauEnCours = false;
        function fetch(){ _fetchCount++; return new Promise(function(){}); }  // jamais résolu
        var document = { getElementById:function(){ return {textContent:''}; } };
        function _renderNetworkUpdatePath(){}
    """)
    c.eval(_fn(src, 'findNetworkUpdatePath'))
    c.eval("findNetworkUpdatePath(); findNetworkUpdatePath();")   # 2 clics rapprochés
    assert c.eval("_fetchCount") == 1, "un 2e scan a été lancé alors que le 1er était en vol"
