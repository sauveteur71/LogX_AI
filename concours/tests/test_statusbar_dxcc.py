# -*- coding: utf-8 -*-
"""Barre de statut — bandeau « ⚠ DXCC indisponible » (décision F4GLD ②(b),
placement « barre de statut, partout »). refreshDxccStatus interroge
/dxcc/status et n'affiche l'item que si la résolution DXCC est désactivée ;
l'item est masqué par défaut et pointe vers CONFIG (recharger cty.dat)."""
import os
import re

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS = os.path.join(CONCOURS, 'logx_statusbar.js')


def _src():
    return open(JS, encoding='utf-8').read()


def _fn(nom):
    src = _src()
    m = re.search(r'\n\s*function ' + re.escape(nom) + r'\s*\(', src)
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


_HARNESS = """
var _item = { style: { display: 'INIT' } };
var _url = null;
var document = { getElementById:function(id){ return id === 'rcsbDxccItem' ? _item : null; } };
function fetch(u){ _url = u; return Promise.resolve({ ok:true, json:function(){ return Promise.resolve(_state); } }); }
var _state = {};
"""


def _run(state_js):
    racer = pytest.importorskip('py_mini_racer')
    c = racer.MiniRacer()
    c.eval(_HARNESS)
    c.eval("_state = %s;" % state_js)
    c.eval(_fn('refreshDxccStatus'))
    c.eval("refreshDxccStatus();")
    for _ in range(5):
        c.eval("0")
    return c


def test_affiche_le_bandeau_quand_dxcc_indisponible():
    c = _run("{available:false, status:'database_missing'}")
    assert c.eval("_url") == '/dxcc/status'
    assert c.eval("_item.style.display") == 'flex'


def test_masque_le_bandeau_quand_dxcc_disponible():
    c = _run("{available:true, status:'ready'}")
    assert c.eval("_item.style.display") == 'none'


def test_item_html_masque_par_defaut_et_pointe_vers_config():
    src = _src()
    m = re.search(r'id="rcsbDxccItem"[^>]*>', src)
    assert m, 'item rcsbDxccItem absent'
    assert 'display:none' in m.group(0), "l'item DXCC doit être masqué par défaut"
    # Le bloc de l'item contient un lien vers CONFIG.
    i = src.index('id="rcsbDxccItem"')
    bloc = src[i:i + 400]
    assert 'logx_configuration.html' in bloc


def test_le_bandeau_est_interroge_periodiquement():
    src = _src()
    assert re.search(r'rcPoll\(\s*refreshDxccStatus\s*,\s*\d+', src), "poll refreshDxccStatus absent"
    i = src.index('rcPoll(refreshDxccStatus')
    assert 'refreshDxccStatus();' in src[max(0, i - 300):i], "appel initial absent avant le poll"
