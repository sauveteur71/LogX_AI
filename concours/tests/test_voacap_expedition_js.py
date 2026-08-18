# -*- coding: utf-8 -*-
"""Rendu client de la planification DXpédition (backlog #119) : extraction
du meilleur créneau par mois (bestSlotOfMonth) et rendu du tableau
récapitulatif 12 mois (voacapExpeditionTableHtml), dans logx_carte.html.

Exécute le VRAI code (extrait par comptage d'accolades, même technique que
tests/test_carte_applyconfig_avertissement.py) dans un moteur JS réel (V8
via py_mini_racer)."""
import os
import re

import pytest

py_mini_racer = pytest.importorskip(
    'py_mini_racer', reason='py_mini_racer absent (voir requirements.txt) — test JS réel ignoré')

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML_PATH = os.path.join(BASE, 'logx_carte.html')

with open(HTML_PATH, encoding='utf-8') as _f:
    _SRC = _f.read()


def _extract_function(src, name):
    m = re.search(r'^(?:async )?function %s\(' % re.escape(name), src, re.M)
    assert m, 'fonction %s introuvable dans %s' % (name, HTML_PATH)
    i = src.index('{', m.start())
    depth = 0
    while True:
        c = src[i]
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                return src[m.start():i + 1]
        i += 1


_MONTH_NAMES_SRC = re.search(r'^const MONTH_NAMES_SHORT=\[.*?\];', _SRC, re.M).group(0)
_ESC_MAP_SRC = _extract_function(_SRC, 'escMap')
_BEST_SLOT_SRC = _extract_function(_SRC, 'bestSlotOfMonth')
_TABLE_HTML_SRC = _extract_function(_SRC, 'voacapExpeditionTableHtml')

_PREAMBLE = "function rcT(s){ return s; }"


def _make_ctx():
    ctx = py_mini_racer.MiniRacer()
    ctx.eval(_PREAMBLE)
    ctx.eval(_MONTH_NAMES_SRC)
    ctx.eval(_ESC_MAP_SRC)
    ctx.eval(_BEST_SLOT_SRC)
    ctx.eval(_TABLE_HTML_SRC)
    return ctx


# ─── bestSlotOfMonth() ──────────────────────────────────────────────────────

def test_best_slot_trouve_le_rel_maximum_toutes_bandes_heures():
    ctx = _make_ctx()
    data = {
        'hours': [
            {'hour': 6, 'bands': [{'freq_mhz': 14.0, 'rel': 0.2}, {'freq_mhz': 21.0, 'rel': 0.55}]},
            {'hour': 18, 'bands': [{'freq_mhz': 14.0, 'rel': 0.85}, {'freq_mhz': 21.0, 'rel': 0.4}]},
        ]
    }
    ctx.eval('var data = %s;' % __import__('json').dumps(data))
    best = ctx.eval('JSON.stringify(bestSlotOfMonth(data))')
    import json
    b = json.loads(best)
    assert b == {'rel': 0.85, 'freq': 14.0, 'hour': 18}


def test_best_slot_ignore_les_bandes_sans_donnee():
    ctx = _make_ctx()
    data = {'hours': [{'hour': 6, 'bands': [{'freq_mhz': 14.0, 'rel': None}, {'freq_mhz': 21.0, 'rel': 0.3}]}]}
    ctx.eval('var data = %s;' % __import__('json').dumps(data))
    best = ctx.eval('JSON.stringify(bestSlotOfMonth(data))')
    import json
    assert json.loads(best)['freq'] == 21.0


def test_best_slot_aucune_bande_renvoie_null():
    ctx = _make_ctx()
    ctx.eval('var data = {hours: []};')
    assert ctx.eval('bestSlotOfMonth(data)') is None


# ─── voacapExpeditionTableHtml() ────────────────────────────────────────────

def _results_ok_ko():
    """12 mois : 1 seul avec des données exploitables, les autres en échec
    (SSN indisponible ce mois-là, station injoignable...) -- cas réaliste
    d'une planification partiellement dégradée, pas un scénario jouet."""
    return [
        {'month': 1, 'year': 2027, 'data': {'ok': False, 'error': 'boom'}},
        {'month': 8, 'year': 2027, 'data': {
            'ok': True, 'distance_km': 16500.2,
            'hours': [{'hour': 20, 'bands': [{'freq_mhz': 14.0, 'rel': 0.72}]}],
        }},
    ]


def test_table_html_affiche_le_meilleur_creneau_du_mois_reussi():
    ctx = _make_ctx()
    ctx.eval('var results = %s;' % __import__('json').dumps(_results_ok_ko()))
    html = ctx.eval('voacapExpeditionTableHtml(results)')
    assert 'aoû 2027' in html
    assert '14 MHz' in html
    assert '20h' in html
    assert '72' in html                       # REL% arrondi


def test_table_html_signale_les_mois_sans_donnee_sans_planter():
    ctx = _make_ctx()
    ctx.eval('var results = %s;' % __import__('json').dumps(_results_ok_ko()))
    html = ctx.eval('voacapExpeditionTableHtml(results)')
    assert 'jan 2027' in html
    assert 'pas de donnée' in html


def test_table_html_tous_les_mois_en_echec_affiche_l_erreur():
    ctx = _make_ctx()
    results = [{'month': 1, 'year': 2027, 'data': {'ok': False, 'error': 'Station distante introuvable'}}]
    ctx.eval('var results = %s;' % __import__('json').dumps(results))
    html = ctx.eval('voacapExpeditionTableHtml(results)')
    assert 'Station distante introuvable' in html
