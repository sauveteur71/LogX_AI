# -*- coding: utf-8 -*-
"""Audit : sstvSauverImage révoquait l'URL blob IMMÉDIATEMENT après a.click(),
ce qui peut annuler le téléchargement PNG. Le revoke est désormais DIFFÉRÉ
(setTimeout) : juste après le clic, l'URL n'est PAS encore révoquée."""
import os
import re

import pytest

py_mini_racer = pytest.importorskip('py_mini_racer')

JS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logx_sstv_panel.js')


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


def test_revoke_est_differe_pas_immediat():
    c = py_mini_racer.MiniRacer()
    c.eval("""
        var _revoked = [], _timers = [];
        var _sstvLignesRecues = 5;
        var URL = { createObjectURL:function(){return 'blob:z';},
                    revokeObjectURL:function(u){ _revoked.push(u); } };
        function setTimeout(fn){ _timers.push(fn); }   // NE PAS exécuter tout de suite
        var document = { getElementById:function(){ return {toBlob:function(cb){ cb({}); }}; },
                         createElement:function(){ return {click:function(){}}; } };
        function notify(){} function trF(s){return s;}
    """)
    c.eval(_fn(open(JS, encoding='utf-8').read(), 'sstvSauverImage'))
    c.eval("sstvSauverImage()")
    assert c.eval("_revoked.length") == 0, "l'URL ne doit PAS être révoquée immédiatement (annule le download)"
    assert c.eval("_timers.length") == 1, "le revoke doit être programmé en différé"
    c.eval("_timers[0]()")   # déclenche le timer différé
    assert c.eval("JSON.stringify(_revoked)").find('blob:z') >= 0
