# -*- coding: utf-8 -*-
"""Lot 6 — onglet QSL (statuts d'envoi éditables) + recherche par tag.

Les statuts REÇUS viennent de la synchro (logx_qsl.py) ; ici seuls les statuts
ENVOYÉS se saisissent. La recherche du carnet retrouve un QSO par tag
multi-activité (SOTA, QRP, FT8…) en plus de l'indicatif/locator.
"""
import json
import os
import re

import pytest

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML = open(os.path.join(BASE, 'logx_logbook.html'), encoding='utf-8').read()
JS = open(os.path.join(BASE, 'logx_logbook.js'), encoding='utf-8').read()


def _pane(name):
    i = HTML.index('class="entry-tabpane" data-pane="%s"' % name)
    rest = HTML[i + 10:]
    nxt = rest.find('class="entry-tabpane" data-pane="')
    end = i + 10 + (nxt if nxt != -1 else len(rest))
    return HTML[i:end]


def test_statuts_qsl_dans_onglet_qsl():
    bloc = _pane('qsl')
    for cid in ('inputQslSent', 'inputLotwSent', 'inputEqslSent'):
        assert ('id="%s"' % cid) in bloc, cid


def test_recherche_par_tag_cablee():
    # filterLog inclut activity_tags dans le texte cherché.
    i = JS.index('function filterLog')
    bloc = JS[i:i + 1500]
    assert 'activity_tags' in bloc


def test_collect_extra_fields_prend_les_statuts_qsl():
    pytest.importorskip('py_mini_racer')
    from py_mini_racer import py_mini_racer as m

    def _fn(name):
        mm = re.search(r'function %s\(' % re.escape(name), JS)
        d = 0
        j = JS.index('{', mm.start())
        while True:
            if JS[j] == '{':
                d += 1
            elif JS[j] == '}':
                d -= 1
                if d == 0:
                    return JS[mm.start():j + 1]
            j += 1

    c = m.MiniRacer()
    c.eval('var __v = {inputQslSent:"Y", inputLotwSent:"N"};')
    c.eval("var document = { getElementById: function(id){ return (id in __v) ? {value:String(__v[id])} : null; } };")
    c.eval(_fn('collectExtraFields'))
    q = json.loads(c.eval('JSON.stringify(collectExtraFields())'))
    assert q['qsl_sent'] == 'Y' and q['lotw_qsl_sent'] == 'N'
