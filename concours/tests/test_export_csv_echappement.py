# -*- coding: utf-8 -*-
"""export CSV (complet) : échappement RFC-4180 + pas de « undefined ».

Le CSV complet assemblait chaque ligne SANS quoter ni échapper : un champ
contenant une virgule (échange, locator, opérateur), un guillemet ou un
retour-ligne décalait toutes les colonnes suivantes. De plus certains champs
sans repli imprimaient 'undefined' quand ils étaient absents.

Correctif : helper _csvField() (quote si `" , CR LF`, guillemets doublés ;
undefined/null -> ''), assemblage par tableau .map(_csvField).join(',').

Depuis la refonte « export par activité » (23/08), la construction du CSV est
isolée dans le builder SYNCHRONE _csvComplet(src) (les fonctions export* sont
devenues async pour proposer le périmètre). On teste le builder directement,
en V8 réel (py_mini_racer), sur le VRAI code extrait par comptage d'accolades.
"""
import json
import os
import re

import pytest

py_mini_racer = pytest.importorskip('py_mini_racer', reason='py_mini_racer absent')

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS_PATH = os.path.join(BASE, 'logx_export_adif.js')


def _extract_function(src, name):
    m = re.search(r'^(?:async\s+)?function %s\(' % re.escape(name), src, re.M)
    assert m, 'fonction %s introuvable' % name
    depth = 0
    i = src.index('{', m.start())
    while True:
        c = src[i]
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                return src[m.start():i + 1]
        i += 1


with open(JS_PATH, encoding='utf-8') as _f:
    _SRC = _f.read()
_HEADER_SRC = re.search(r"const _CSV_HEADER = '[^']*';", _SRC).group(0)
_PIECES_SRC = '\n'.join(_extract_function(_SRC, n)
                        for n in ('_csvField', '_csvBaseRow', '_csvComplet'))

_PREAMBLE = r"""
function _resolveOperatorCallsign(op){ return op ? String(op) : 'F4GLD'; }
function isValidQSO(q){ return true; }
"""


def _csv_for(qso):
    c = py_mini_racer.MiniRacer()
    c.eval(_PREAMBLE + '\n' + _HEADER_SRC + '\n' + _PIECES_SRC)
    return c.eval('_csvComplet(' + json.dumps([qso]) + ')')


def _data_line(csv):
    return csv.strip().split('\n')[1]   # après l'en-tête


def test_champ_avec_virgule_est_quote():
    csv = _csv_for({'date': '20260101', 'time': '1200', 'call': 'F5ABC',
                    'band': '20', 'mode': 'CW', 'num_rcvd': 'A,B,C'})
    assert '"A,B,C"' in csv, csv


def test_champ_absent_ne_donne_pas_undefined():
    csv = _csv_for({'date': '20260101', 'time': '1200', 'call': 'F5ABC', 'band': '20'})
    assert 'undefined' not in csv, csv


def test_guillemet_est_double():
    csv = _csv_for({'date': '20260101', 'time': '1200', 'call': 'A"B',
                    'band': '20', 'mode': 'CW'})
    assert '"A""B"' in csv, csv


def test_colonnes_stables_avec_virgule():
    ref = _data_line(_csv_for({'date': '1', 'time': '2', 'call': 'X', 'band': '20',
                               'mode': 'CW', 'num_rcvd': 'AB'}))
    with_comma = _data_line(_csv_for({'date': '1', 'time': '2', 'call': 'X', 'band': '20',
                                      'mode': 'CW', 'num_rcvd': 'A,B'}))

    def nues(s):
        out, q = 0, False
        for ch in s:
            if ch == '"':
                q = not q
            elif ch == ',' and not q:
                out += 1
        return out
    assert nues(with_comma) == nues(ref), (ref, with_comma)
