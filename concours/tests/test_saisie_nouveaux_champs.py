# -*- coding: utf-8 -*-
"""Lot 2 — champs saisissables nouveaux par onglet (refonte saisie, A).

Structurel : chaque nouvel input est dans le BON onglet (.entry-tabpane).
Comportemental : collectExtraFields() (logx_logbook.js) lit ces inputs et rend
les clés du QSO — persistées via le schéma ouvert de logx_storage."""
import json
import os
import re

import pytest

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML = open(os.path.join(BASE, 'logx_logbook.html'), encoding='utf-8').read()
JS = open(os.path.join(BASE, 'logx_logbook.js'), encoding='utf-8').read()

CHAMPS = {
    'mystation': ['inputTxPwr', 'inputMyRig', 'inputMyAntenna', 'inputOperatingLocation'],
    'corr': ['inputEmail', 'inputQslVia', 'inputCqz', 'inputItuz', 'inputCnty'],
    'qso': ['inputFreqRx', 'inputTimeOff', 'inputPropMode'],
}


def _pane(name):
    # cible le VRAI div de panneau, pas une mention en commentaire.
    i = HTML.index('class="entry-tabpane" data-pane="%s"' % name)
    rest = HTML[i + 10:]
    nxt = rest.find('class="entry-tabpane" data-pane="')
    end = i + 10 + (nxt if nxt != -1 else len(rest))
    return HTML[i:end]


def test_chaque_champ_dans_son_onglet():
    for pane, ids in CHAMPS.items():
        bloc = _pane(pane)
        for cid in ids:
            assert ('id="%s"' % cid) in bloc, (pane, cid)


def _fn(src, name):
    m = re.search(r'function %s\(' % re.escape(name), src)
    assert m, name
    d = 0
    i = src.index('{', m.start())
    while True:
        if src[i] == '{':
            d += 1
        elif src[i] == '}':
            d -= 1
            if d == 0:
                return src[m.start():i + 1]
        i += 1


def _ctx_with_inputs(values):
    from py_mini_racer import py_mini_racer as m
    c = m.MiniRacer()
    c.eval('var __v = %s;' % json.dumps(values))
    c.eval("var document = { getElementById: function(id){ "
           "return (id in __v) ? {value: String(__v[id])} : null; } };")
    c.eval(_fn(JS, 'collectExtraFields'))
    return c


def test_collect_extra_fields_rend_les_cles():
    pytest.importorskip('py_mini_racer')
    c = _ctx_with_inputs({
        'inputTxPwr': '20', 'inputEmail': 'f4abc@example.fr', 'inputQslVia': 'BUREAU',
        'inputCqz': '14', 'inputItuz': '27', 'inputPropMode': 'ES',
        'inputOperatingLocation': 'PORTABLE', 'inputFreqRx': '14.075', 'inputMyRig': 'IC-7300',
    })
    q = json.loads(c.eval('JSON.stringify(collectExtraFields())'))
    assert q['tx_pwr'] == 20            # nombre, pas chaîne
    assert q['email'] == 'f4abc@example.fr'
    assert q['qsl_via'] == 'BUREAU'
    assert q['cqz'] == '14' and q['ituz'] == '27'
    assert q['prop_mode'] == 'ES'
    assert q['operating_location'] == 'PORTABLE'
    assert q['freq_rx'] == '14.075'
    assert q['my_rig'] == 'IC-7300'


def test_collect_extra_fields_ignore_les_vides():
    pytest.importorskip('py_mini_racer')
    c = _ctx_with_inputs({'inputTxPwr': '', 'inputEmail': '   '})
    q = json.loads(c.eval('JSON.stringify(collectExtraFields())'))
    assert 'tx_pwr' not in q and 'email' not in q   # champ vide -> clé absente


def test_submitqso_fusionne_extra_fields():
    # structurel : submitQSO appelle collectExtraFields et fusionne dans q.
    assert 'collectExtraFields(' in JS
