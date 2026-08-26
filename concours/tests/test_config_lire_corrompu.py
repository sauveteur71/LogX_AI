# -*- coding: utf-8 -*-
"""Config — _lireConfig() doit tolérer un blob localStorage CORROMPU (audit
STRATE-3 logx_configuration.js). `JSON.parse(localStorage.getItem('logx_config')
|| '{}')` ne protège QUE du cas vide/absent : un blob non-vide mais invalide
(JSON cassé) faisait lever JSON.parse et cassait l'assistant concours / la page.
_lireConfig() retombe sur {} sur corruption, et rend l'objet parsé sinon."""
import os
import re

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS = os.path.join(CONCOURS, 'logx_configuration.js')


def _fn(nom):
    src = open(JS, encoding='utf-8').read()
    m = re.search(r'\nfunction ' + re.escape(nom) + r'\s*\(', src)
    assert m, 'fonction %s introuvable' % nom
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
    raise AssertionError('accolade fermante introuvable')


def _ctx(blob):
    racer = pytest.importorskip('py_mini_racer')
    c = racer.MiniRacer()
    c.eval("var _blob = %s; var localStorage = { getItem: function(){ return _blob; } };"
           % ('null' if blob is None else '%r' % blob))
    c.eval(_fn('_lireConfig'))
    return c


def test_blob_corrompu_retombe_sur_objet_vide():
    c = _ctx('{ceci n est pas du JSON')
    assert c.eval("JSON.stringify(_lireConfig())") == '{}'


def test_blob_valide_est_parse():
    c = _ctx('{"callsign":"F4GLD","locator":"JN15"}')
    assert c.eval("_lireConfig().callsign") == 'F4GLD'
    assert c.eval("_lireConfig().locator") == 'JN15'


def test_blob_absent_donne_objet_vide():
    c = _ctx(None)
    assert c.eval("JSON.stringify(_lireConfig())") == '{}'


def test_plus_aucun_parse_brut_de_logx_config():
    # Tous les sites doivent passer par _lireConfig (structurel).
    src = open(JS, encoding='utf-8').read()
    assert "JSON.parse(localStorage.getItem('logx_config')" not in \
        src.replace("try{ return JSON.parse(localStorage.getItem('logx_config') || '{}') || {}; }", ''), \
        "un JSON.parse brut de logx_config subsiste hors de _lireConfig"
