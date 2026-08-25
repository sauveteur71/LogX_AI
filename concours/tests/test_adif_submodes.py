# -*- coding: utf-8 -*-
"""Correctif : un sous-mode ADIF (FT4/JS8/Q65/FST4…) stocké comme mode « à plat »
doit sortir en MODE=<parent> + SUBMODE=<sous-mode>, jamais MODE=FT4 (non
conforme : les robots de concours/LoTW stricts rejettent). Généralise le cas
FT2 déjà traité, via la table sourcée logx_adif_enums.ADIF_MODES."""
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
os.chdir(BASE)

import logx_export as export   # noqa: E402


def _adif(mode):
    q = {'call': 'F4ABC', 'band': '20', 'mode': mode, 'date': '20260101',
         'time': '1200', 'rst_sent': '59', 'rst_rcvd': '-10'}
    return export.build_adif([q], {}).upper()


def test_ft4_sort_en_mfsk_submode():
    a = _adif('FT4')
    assert '<MODE:4>MFSK' in a and '<SUBMODE:3>FT4' in a, a
    assert '<MODE:3>FT4' not in a, a


def test_js8_sort_en_mfsk_submode():
    a = _adif('JS8')
    assert '<MODE:4>MFSK' in a and '<SUBMODE:3>JS8' in a, a


def test_ft2_reste_mfsk_submode():
    a = _adif('FT2')
    assert '<MODE:4>MFSK' in a and '<SUBMODE:3>FT2' in a, a


def test_ft8_reste_mode_top_level():
    # FT8 est un MODE ADIF autonome, PAS un sous-mode -> pas de SUBMODE.
    a = _adif('FT8')
    assert '<MODE:3>FT8' in a and '<SUBMODE:' not in a, a


def test_cw_ssb_inchanges():
    assert '<MODE:2>CW' in _adif('CW')
    assert '<MODE:3>SSB' in _adif('SSB')


# ─── Parité client (VRAI buildAdifText en V8) + cohérence du mapping ─────────

import json    # noqa: E402
import re       # noqa: E402

import pytest   # noqa: E402

py_mini_racer = pytest.importorskip(
    'py_mini_racer', reason='py_mini_racer absent — test JS réel ignoré')

_EXPORT_JS = open(os.path.join(BASE, 'logx_export_adif.js'), encoding='utf-8').read()
_STUBS = ("var myCall='F4GLD', myLocator='JN15WD';"
          "function _resolveOperatorCallsign(x){ return x||''; }")


def test_client_v8_ft4_en_mfsk_submode():
    ctx = py_mini_racer.MiniRacer()
    ctx.eval(_STUBS)
    ctx.eval(_EXPORT_JS)
    q = [{'call': 'F4ABC', 'band': '20', 'mode': 'FT4', 'date': '20260101',
          'time': '1200', 'rst_sent': '+00', 'rst_rcvd': '-10'}]
    adif = ctx.eval('buildAdifText(%s)' % json.dumps(q)).upper()
    assert '<MODE:4>MFSK' in adif and '<SUBMODE:3>FT4' in adif, adif
    assert '<MODE:3>FT4' not in adif, adif


def test_parite_js_submode_parent_est_bien_du_mfsk():
    # les clés du mapping JS DOIVENT être de vrais sous-modes ADIF de MFSK
    # (source Python ADIF_MODES) — pas d'invention côté client.
    from logx_adif_enums import ADIF_MODES
    mfsk = {s.upper() for s in ADIF_MODES.get('MFSK', ())}
    i = _EXPORT_JS.index('SUBMODE_PARENT = {')
    bloc = _EXPORT_JS[i:_EXPORT_JS.index('}', i)]
    cles = set(re.findall(r'(\w+):', bloc.split('{', 1)[1]))
    assert cles, bloc
    assert cles <= mfsk, (cles - mfsk)
