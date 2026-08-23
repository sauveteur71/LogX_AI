# -*- coding: utf-8 -*-
"""Export « CSV valide » + 4 champs diagnostic sur le CSV complet (F4GLD 23/08).

- CSV complet (_csvComplet) : TOUS les QSO (même invalides) + colonnes Complet/
  Scoré/Concours/Echange_reçu_brut dérivées.
- CSV valide (_csvValide) : uniquement les QSO validés (filtre isValidQSO, comme
  l'export ADIF), colonnes propres.

Depuis la refonte « export par activité », ces deux builders sont SYNCHRONES
(les fonctions export* async ne font qu'ajouter le choix du périmètre autour).
Vrai code extrait par comptage d'accolades, exécuté en V8 (py_mini_racer).
"""
import json
import os
import re

import pytest

py_mini_racer = pytest.importorskip('py_mini_racer', reason='py_mini_racer absent')

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS = os.path.join(BASE, 'logx_export_adif.js')


def _extract_function(src, name):
    m = re.search(r'^(?:async\s+)?function %s\(' % re.escape(name), src, re.M)
    assert m, name
    depth = 0
    i = src.index('{', m.start())
    while True:
        if src[i] == '{':
            depth += 1
        elif src[i] == '}':
            depth -= 1
            if depth == 0:
                return src[m.start():i + 1]
        i += 1


with open(JS, encoding='utf-8') as f:
    _SRC = f.read()
_HEADER = re.search(r"const _CSV_HEADER = '[^']*';", _SRC).group(0)
_PIECES = '\n'.join(_extract_function(_SRC, n) for n in
                    ('_csvField', '_csvBaseRow', '_csvComplet', '_csvValide'))

_PREAMBLE = r"""
function _resolveOperatorCallsign(op){ return op ? String(op) : 'F4GLD'; }
function isValidQSO(q){ return !!q._valid; }   // stub contrôlable : teste le FILTRE
"""


def _run(fn, qsos):
    c = py_mini_racer.MiniRacer()
    c.eval(_PREAMBLE + '\n' + _HEADER + '\n' + _PIECES)
    return c.eval(fn + '(' + json.dumps(qsos) + ')')


_A = {'date': '20260101', 'time': '1200', 'call': 'F5A', 'band': '20', 'mode': 'CW',
      'num_rcvd': '033', 'contest': 'REF_HF', 'points': 1, '_valid': True}
_B = {'date': '', 'time': '', 'call': 'F5B', 'band': '20', 'mode': 'CW',
      'num_rcvd': '', 'contest': 'REF_HF', 'points': 0, '_valid': False}


def test_csv_valide_ne_garde_que_les_qso_valides():
    csv = _run('_csvValide', [_A, _B])
    assert 'F5A' in csv and 'F5B' not in csv, csv
    assert 'Complet' not in csv   # pas de colonnes diagnostic dans le CSV valide


def test_csv_complet_garde_tout_avec_les_4_champs():
    csv = _run('_csvComplet', [_A, _B])
    head = csv.splitlines()[0]
    assert head.endswith('Complet,Scoré,Concours,Echange_reçu_brut'), head
    assert 'F5A' in csv and 'F5B' in csv               # tous les QSO
    lignes = csv.splitlines()
    la = next(l for l in lignes if l.startswith('1,') or ',F5A,' in l)
    lb = next(l for l in lignes if ',F5B,' in l)
    assert la.endswith('oui,oui,REF_HF,033')           # A : complet + scoré
    assert lb.endswith('non,non,REF_HF,')              # B : ni complet ni scoré


def test_menu_logbook_cable_export_csv_valide():
    with open(os.path.join(BASE, 'logx_logbook.js'), encoding='utf-8') as f:
        js = f.read()
    assert re.search(r"apres\.push\(\['[^']*',\s*'[^']*valide[^']*',\s*'exportCSVValide'\]\)", js), \
        "entrée de menu 'exportCSVValide' absente ou mal câblée"
