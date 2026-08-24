# -*- coding: utf-8 -*-
"""Sous-chantier B, lot 3 — multi-références en ADIF.

Une activation peut être un « two-fer » : ma station active SIMULTANÉMENT un
sommet SOTA ET un parc POTA (my_refs = [{program:'SOTA',...},{program:'POTA',
...}]). MY_SIG/MY_SIG_INFO ne portent qu'UNE référence (le 1er programme), donc
sans tag dédié le 2e programme du two-fer était PERDU à l'export.

Correctif : les deux générateurs (build_adif serveur, buildAdifText client)
émettent, EN PLUS de MY_SIG/SIG, les tags ADIF DÉDIÉS par programme quand la
spec ADIF 3.1.5 en définit un (adif.org/315) :
    SOTA -> SOTA_REF / MY_SOTA_REF
    POTA -> POTA_REF / MY_POTA_REF
    WWFF -> WWFF_REF / MY_WWFF_REF
    IOTA -> IOTA     / MY_IOTA
ARLHS et WCA n'ont PAS de tag ADIF dédié : ils restent sur le générique SIG
(une seule référence, my_refs[0]) — aucun tag inventé.
"""
import json
import os
import sys

import pytest

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
os.chdir(BASE)

import logx_export as export                       # noqa: E402
from logx_activation import ADIF_PROGRAM_TAGS       # noqa: E402  (source unique)


# ─── Serveur (build_adif) ────────────────────────────────────────────────────

def _q(**extra):
    q = {'call': 'F4ABC', 'date': '20260824', 'time': '1215', 'band': '20',
         'mode': 'SSB', 'rst_sent': '59', 'rst_rcvd': '59'}
    q.update(extra)
    return q


def test_two_fer_sota_pota_serveur():
    # Une activation SOTA+POTA en même temps : les DEUX références dédiées émises.
    q = _q(my_refs=[{'program': 'SOTA', 'ref': 'F/AB-123'},
                    {'program': 'POTA', 'ref': 'FR-0123'}])
    adif = export.build_adif([q], {}).upper()
    assert '<MY_SOTA_REF:8>F/AB-123' in adif
    assert '<MY_POTA_REF:7>FR-0123' in adif


def test_refs_correspondant_serveur():
    # Réf. du correspondant (Park-to-Park) : POTA_REF sans préfixe MY_.
    q = _q(refs=[{'program': 'POTA', 'ref': 'FR-0456'}])
    adif = export.build_adif([q], {}).upper()
    assert '<POTA_REF:7>FR-0456' in adif
    assert '<MY_POTA_REF:' not in adif    # côté correspondant, pas MY_


def test_retro_compat_my_sig_seul_serveur():
    # Vieux QSO stocké sans my_refs : my_sig='SOTA' -> MY_SOTA_REF quand même,
    # par repli sur la paire mono-valuée.
    q = _q(my_sig='SOTA', my_sig_info='F/AB-999')
    adif = export.build_adif([q], {}).upper()
    assert '<MY_SOTA_REF:8>F/AB-999' in adif


def test_programme_sans_tag_dedie_pas_de_tag_invente_serveur():
    # WCA n'a pas de tag ADIF dédié : aucun MY_WCA_REF / MY_WCA inventé.
    q = _q(my_refs=[{'program': 'WCA', 'ref': 'DL-00001'}])
    adif = export.build_adif([q], {}).upper()
    assert 'MY_WCA' not in adif


def test_iota_sans_suffixe_ref_serveur():
    # IOTA : le tag ADIF est 'IOTA'/'MY_IOTA' (PAS 'IOTA_REF').
    q = _q(my_refs=[{'program': 'IOTA', 'ref': 'EU-064'}])
    adif = export.build_adif([q], {}).upper()
    assert '<MY_IOTA:6>EU-064' in adif
    assert 'MY_IOTA_REF' not in adif


# ─── Client (buildAdifText) exécuté dans un VRAI moteur JS (V8) ──────────────

py_mini_racer = pytest.importorskip(
    'py_mini_racer', reason='py_mini_racer absent (requirements.txt) — test JS réel ignoré')

_EXPORT_JS = open(os.path.join(BASE, 'logx_export_adif.js'), encoding='utf-8').read()
# buildAdifText/adifField/adifBandLabel/ADIF_STD_TAGS vivent dans ce fichier ;
# seuls myCall/myLocator et _resolveOperatorCallsign sont externes -> stubs.
_STUBS = ("var myCall='F4GLD', myLocator='JN15WD';"
          "function _resolveOperatorCallsign(x){ return x||''; }")


def _build_client(qsos):
    ctx = py_mini_racer.MiniRacer()
    ctx.eval(_STUBS)
    ctx.eval(_EXPORT_JS)
    return ctx.eval('buildAdifText(%s)' % json.dumps(qsos))


def test_two_fer_client_v8():
    # Même two-fer que le serveur, mais via le VRAI buildAdifText JS.
    adif = _build_client([{'call': 'F4ABC', 'band': '20', 'mode': 'SSB',
                           'date': '20260824', 'time': '1215',
                           'rst_sent': '59', 'rst_rcvd': '59',
                           'my_refs': [{'program': 'SOTA', 'ref': 'F/AB-123'},
                                       {'program': 'POTA', 'ref': 'FR-0123'}]}]).upper()
    assert '<MY_SOTA_REF:8>F/AB-123' in adif
    assert '<MY_POTA_REF:7>FR-0123' in adif


def test_refs_correspondant_client_v8():
    adif = _build_client([{'call': 'F4ABC', 'band': '20', 'mode': 'SSB',
                           'date': '20260824', 'time': '1215',
                           'rst_sent': '59', 'rst_rcvd': '59',
                           'refs': [{'program': 'WWFF', 'ref': 'FFF-0123'}]}]).upper()
    assert '<WWFF_REF:8>FFF-0123' in adif


# ─── Parité de la table de mapping JS <-> Python (pas deux vérités) ──────────

def test_parite_mapping_js_python():
    # REF_ADIF_TAGS (JS) DOIT refléter ADIF_PROGRAM_TAGS (Python, source unique).
    i = _EXPORT_JS.index('REF_ADIF_TAGS = {')
    bloc = _EXPORT_JS[i:_EXPORT_JS.index('}', i)]
    for prog, tag in ADIF_PROGRAM_TAGS.items():
        assert ("%s:'%s'" % (prog, tag)) in bloc.replace(' ', ''), (prog, tag)
    # et aucun programme JS en trop hors de la table Python
    import re
    js_progs = set(re.findall(r'(\w+)\s*:', bloc.split('{', 1)[1]))
    assert js_progs == set(ADIF_PROGRAM_TAGS), (js_progs, set(ADIF_PROGRAM_TAGS))
