# -*- coding: utf-8 -*-
"""Sous-chantier B — correctifs de revue adversariale (branche feat/logbook-adif-B).

Régressions introduites par la branche : un tag ajouté à _ADIF_STD_TAGS (jeu
anti-duplication de l'export) SANS mapping interne à l'import est SAUTÉ au
re-export alors que sa valeur importée dort dans extra_fields -> perte
silencieuse. Deux cas :
  #1 SUBMODE non-FT2 (JS8, FT4 en MFSK) ;
  #2 confirmations reçues (LOTW_QSL_RCVD…).
Plus #4 : deux références du MÊME programme dupliquaient le tag ADIF.
"""
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
os.chdir(BASE)

import logx_export as export     # noqa: E402


# ─── #1 SUBMODE non-FT2 préservé au re-export ────────────────────────────────

def test_submode_non_ft2_reexporte():
    # QSO JS8 tel que stocké après import (mode MFSK, SUBMODE en extra_fields).
    q = {'call': 'F4ABC', 'band': '20', 'mode': 'MFSK', 'date': '20260101',
         'time': '1200', 'rst_sent': '-05', 'rst_rcvd': '-07',
         'extra_fields': {'SUBMODE': 'JS8'}}
    adif = export.build_adif([q], {}).upper()
    assert '<SUBMODE:3>JS8' in adif, adif


# ─── #2 confirmation reçue importée préservée au re-export ───────────────────

def test_lotw_rcvd_en_extra_fields_reexporte_sans_confirmations():
    # QSO importé d'un ADIF étranger portant LOTW_QSL_RCVD=Y : sans store de
    # confirmations (confirmations=None), la valeur ne doit PAS disparaître.
    q = {'call': 'F4ABC', 'band': '20', 'mode': 'SSB', 'date': '20260101',
         'time': '1200', 'rst_sent': '59', 'rst_rcvd': '59',
         'extra_fields': {'LOTW_QSL_RCVD': 'Y'}}
    adif = export.build_adif([q], {}).upper()
    assert '<LOTW_QSL_RCVD:1>Y' in adif, adif


def test_confirmation_store_et_extra_fields_pas_de_double_rcvd():
    # QSO avec LOTW_QSL_RCVD en extra_fields ET confirmé dans le store : le tag
    # ne doit apparaître qu'UNE fois (pas de champ dupliqué dans le record).
    from logx_awards import _confirm_key
    q = {'call': 'F4ABC', 'band': '20', 'mode': 'SSB', 'date': '20260101',
         'time': '1200', 'rst_sent': '59', 'rst_rcvd': '59',
         'extra_fields': {'LOTW_QSL_RCVD': 'Y'}}
    conf = {_confirm_key(q): {'lotw': '20260115'}}
    adif = export.build_adif([q], {}, confirmations=conf).upper()
    assert adif.count('<LOTW_QSL_RCVD:') == 1, adif


# ─── #4 deux réfs même programme : tag ADIF émis une seule fois ──────────────

def test_two_refs_meme_programme_pas_de_tag_duplique():
    q = {'call': 'F4ABC', 'band': '20', 'mode': 'SSB', 'date': '20260101',
         'time': '1200', 'rst_sent': '59', 'rst_rcvd': '59',
         'my_refs': [{'program': 'POTA', 'ref': 'FR-0123'},
                     {'program': 'POTA', 'ref': 'FR-0456'}]}
    adif = export.build_adif([q], {}).upper()
    assert adif.count('<MY_POTA_REF:') == 1, adif


# ─── Parité JS : le VRAI buildAdifText préserve aussi SUBMODE=JS8 ─────────────

import json    # noqa: E402
import pytest   # noqa: E402

py_mini_racer = pytest.importorskip(
    'py_mini_racer', reason='py_mini_racer absent — test JS réel ignoré')

_EXPORT_JS = open(os.path.join(BASE, 'logx_export_adif.js'), encoding='utf-8').read()
_STUBS = ("var myCall='F4GLD', myLocator='JN15WD';"
          "function _resolveOperatorCallsign(x){ return x||''; }")


def test_submode_non_ft2_reexporte_client_v8():
    ctx = py_mini_racer.MiniRacer()
    ctx.eval(_STUBS)
    ctx.eval(_EXPORT_JS)
    q = [{'call': 'F4ABC', 'band': '20', 'mode': 'MFSK', 'date': '20260101',
          'time': '1200', 'rst_sent': '-05', 'rst_rcvd': '-07',
          'extra_fields': {'SUBMODE': 'JS8'}}]
    adif = ctx.eval('buildAdifText(%s)' % json.dumps(q)).upper()
    assert '<SUBMODE:3>JS8' in adif, adif
