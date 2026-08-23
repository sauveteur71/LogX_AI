# -*- coding: utf-8 -*-
"""Export par ACTIVITÉ (F4GLD 23/08) : filtre universel + BOM UTF-8.

Besoin : « pour toute expédition ou concours, SOTA POTA… pouvoir exporter un log
propre à chaque activité ». Le carnet reste UNIQUE (doctrine « activité = vue ») ;
on étend la logique scopée de Cabrillo/EDI/POTA à TOUS les exports.

- _activeActivity() dérive la portée depuis l'état de station : activation
  POTA/SOTA en cours (my_sig/my_sig_info) PRIORITAIRE, sinon concours sélectionné
  (currentContest, inclut les DXped type TM6KJS), sinon null (carnet complet).
- .match(q) filtre le carnet sur cette activité.
- _downloadCsv préfixe un BOM UTF-8 (﻿) pour qu'Excel lise les accents
  (N°, Scoré, reçu) sans corruption.

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
# _CONTEST_DEFAUT est une const hors fonction : l'extraire aussi, sinon
# _activeActivity() lèverait une ReferenceError (on suit ainsi la vraie valeur).
_CONST = re.search(r"const _CONTEST_DEFAUT = '[^']*';", _SRC).group(0)
_ACT_PIECES = _CONST + '\n' + '\n'.join(_extract_function(_SRC, n)
                                        for n in ('_activeActivity', '_safeSuffixe'))
_DL = _extract_function(_SRC, '_downloadCsv')


def _ctx(activationProgram='', myActivationRef='', currentContest=''):
    """Contexte V8 avec l'état de station simulé, puis les helpers extraits."""
    c = py_mini_racer.MiniRacer()
    c.eval('var activationProgram = %s;' % json.dumps(activationProgram))
    c.eval('var myActivationRef = %s;' % json.dumps(myActivationRef))
    c.eval('var currentContest = %s;' % json.dumps(currentContest))
    c.eval(_ACT_PIECES)
    return c


def test_aucune_activite_retourne_null():
    c = _ctx(currentContest='')          # ni concours ni activation
    assert c.eval('_activeActivity()') is None


def test_contest_par_defaut_traite_comme_aucune_activite():
    # 'REF_RPH' = repli de currentContest quand rien n'est configuré : il ne doit
    # PAS déclencher de dialogue de périmètre sur le chemin quotidien.
    c = _ctx(currentContest='REF_RPH')
    assert c.eval('_activeActivity()') is None


def test_concours_selectionne_filtre_par_contest():
    c = _ctx(currentContest='TM6KJS')
    assert c.eval('_activeActivity().label') == 'TM6KJS'
    assert c.eval("_activeActivity().match({contest:'TM6KJS'})") is True
    assert c.eval("_activeActivity().match({contest:''})") is False
    assert c.eval("_activeActivity().match({contest:'REF_HF'})") is False


def test_activation_pota_prioritaire_et_filtre_par_sig():
    # activation en cours ET un concours sélectionné : l'activation gagne
    c = _ctx(activationProgram='pota', myActivationRef='FR-0123', currentContest='TM6KJS')
    assert c.eval('_activeActivity().label') == 'POTA FR-0123'
    assert c.eval("_activeActivity().match({my_sig:'POTA', my_sig_info:'FR-0123'})") is True
    assert c.eval("_activeActivity().match({my_sig:'POTA', my_sig_info:'FR-9999'})") is False
    # un QSO du concours TM6KJS ne doit PAS entrer dans l'activation POTA active
    assert c.eval("_activeActivity().match({contest:'TM6KJS'})") is False


def test_filtre_carnet_ne_garde_que_l_activite():
    c = _ctx(currentContest='TM6KJS')
    log = [{'call': 'A', 'contest': 'TM6KJS'},
           {'call': 'B', 'contest': ''},          # historique non tagué
           {'call': 'C', 'contest': 'REF_HF'},    # autre activité
           {'call': 'D', 'contest': 'TM6KJS'}]
    c.eval('var log = ' + json.dumps(log) + ';')
    calls = c.eval('log.filter(_activeActivity().match).map(function(q){return q.call;}).join("")')
    assert calls == 'AD', calls


def test_suffixe_nom_de_fichier_assaini():
    c = _ctx(currentContest='TM6KJS')
    assert c.eval("_safeSuffixe('TM6/KJS 2026')") == 'TM6_KJS_2026'


def test_downloadcsv_prefixe_un_bom_utf8():
    c = py_mini_racer.MiniRacer()
    c.eval(r"""
      var _parts = null;
      function Blob(parts){ _parts = parts; }
      var URL = { createObjectURL: function(){ return 'blob:x'; } };
      var document = { createElement: function(){ return { click:function(){}, style:{} }; } };
      var myCall = 'F4GLD';
    """)
    c.eval(_DL)
    c.eval("_downloadCsv('N°,Date\\n', 'log')")
    joined = c.eval('_parts.join("")')
    assert joined[0] == '﻿', repr(joined[:3])     # BOM en tête
    assert 'N°,Date' in joined                    # contenu conservé après le BOM
