# -*- coding: utf-8 -*-
"""Audit : les exports (ADIF/CSV/EDI) créaient une URL blob via
URL.createObjectURL() jamais libérée -> fuite mémoire à chaque export. On la
libère désormais par URL.revokeObjectURL() APRÈS le démarrage du téléchargement
(revoke différé, un revoke immédiat pouvant annuler le téléchargement)."""
import os
import re

import pytest

py_mini_racer = pytest.importorskip('py_mini_racer')

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS = os.path.join(BASE, 'logx_export_adif.js')


def _fn(src, nom):
    m = re.search(r'\n\s*function ' + re.escape(nom) + r'\s*\(', src)
    assert m, nom
    i = src.index('function', m.start())
    j = src.index('{', i)
    prof = 0
    for k in range(j, len(src)):
        if src[k] == '{':
            prof += 1
        elif src[k] == '}':
            prof -= 1
            if prof == 0:
                return src[i:k + 1]
    raise AssertionError('accolade')


def test_download_adif_libere_l_url_blob():
    c = py_mini_racer.MiniRacer()
    c.eval("""
        var _revoked = [];
        var URL = { createObjectURL: function(){ return 'blob:xyz'; },
                    revokeObjectURL: function(u){ _revoked.push(u); } };
        function Blob(){}
        var document = { createElement: function(){ return {click:function(){}}; } };
        function setTimeout(fn){ fn(); }
        var myCall = 'F4TEST';
    """)
    c.eval(_fn(open(JS, encoding='utf-8').read(), 'downloadAdifBlob'))
    c.eval("downloadAdifBlob('des données adif', 'test')")
    revoked = c.eval("JSON.stringify(_revoked)")
    assert 'blob:xyz' in revoked, "l'URL blob doit être libérée (revokeObjectURL) : %s" % revoked
