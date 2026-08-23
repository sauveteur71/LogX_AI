# -*- coding: utf-8 -*-
"""export CSV (complet) : échappement RFC-4180 + pas de « undefined ».

exportCSV() assemblait chaque ligne par template literal SANS quoter ni
échapper : un champ contenant une virgule (échange, locator, opérateur), un
guillemet ou un retour-ligne décalait toutes les colonnes suivantes. De plus
certains champs sans repli (q.mode, q.call…) imprimaient le texte 'undefined'
quand ils étaient absents, là où d'autres avaient déjà un `||''`.

Correctif : helper _csvField() (quote si `" , CR LF`, guillemets doublés ;
undefined/null -> ''), et assemblage par tableau .map(_csvField).join(',').

Le VRAI code d'exportCSV() est extrait par comptage d'accolades et exécuté en V8
(py_mini_racer), le Blob produit étant capturé pour inspecter le CSV réel.
"""
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
_EXPORTCSV_SRC = _extract_function(_SRC, 'exportCSV')
_CSVFIELD_SRC = ''
if re.search(r'^function _csvField\(', _SRC, re.M):
    _CSVFIELD_SRC = _extract_function(_SRC, '_csvField')

_PREAMBLE = r"""
var _csv = null;
function Blob(parts){ _csv = parts.join(''); }
var URL = { createObjectURL: function(){ return 'blob:x'; } };
var document = { createElement: function(){ return { click:function(){}, style:{} }; },
                 getElementById: function(){ return null; } };
var myCall = 'F4GLD';
function _resolveOperatorCallsign(op){ return op ? String(op) : 'F4GLD'; }
var qsoLog = [];
"""


def _csv_for(qso):
    c = py_mini_racer.MiniRacer()
    c.eval(_PREAMBLE + '\n' + _CSVFIELD_SRC + '\n' + _EXPORTCSV_SRC)
    import json
    c.eval('qsoLog = ' + json.dumps([qso]) + ';')
    c.eval('exportCSV();')
    return c.eval('_csv')


def _data_line(csv):
    return csv.strip().split('\n')[1]   # après l'en-tête


def test_champ_avec_virgule_est_quote():
    csv = _csv_for({'date': '20260101', 'time': '1200', 'call': 'F5ABC',
                    'band': '20', 'mode': 'CW', 'num_rcvd': 'A,B,C'})
    assert '"A,B,C"' in csv, csv


def test_champ_absent_ne_donne_pas_undefined():
    # mode/call absents : ne doivent PAS imprimer 'undefined'
    csv = _csv_for({'date': '20260101', 'time': '1200', 'call': 'F5ABC', 'band': '20'})
    assert 'undefined' not in csv, csv


def test_guillemet_est_double():
    csv = _csv_for({'date': '20260101', 'time': '1200', 'call': 'A"B',
                    'band': '20', 'mode': 'CW'})
    assert '"A""B"' in csv, csv


def test_colonnes_stables_avec_virgule():
    # sans virgule : 14 colonnes ; avec une virgule quotée : toujours 14
    ref = _data_line(_csv_for({'date': '1', 'time': '2', 'call': 'X', 'band': '20',
                               'mode': 'CW', 'num_rcvd': 'AB'}))
    with_comma = _data_line(_csv_for({'date': '1', 'time': '2', 'call': 'X', 'band': '20',
                                      'mode': 'CW', 'num_rcvd': 'A,B'}))
    # comptage naïf hors guillemets : la ligne à virgule ne doit pas avoir plus
    # de virgules "nues" que la référence.
    def nues(s):
        out, q = 0, False
        for ch in s:
            if ch == '"':
                q = not q
            elif ch == ',' and not q:
                out += 1
        return out
    assert nues(with_comma) == nues(ref), (ref, with_comma)
