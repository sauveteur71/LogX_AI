# -*- coding: utf-8 -*-
"""IA-2 lot 4 — intégration à l'export (option A, cadrée par F4GLD).

build_adif(..., completer=True) complète les champs dérivables VIDES via
logx_enrichissement.enrichir AVANT émission, sur une COPIE du QSO (le log stocké
n'est jamais modifié). Ne remplit que le vide, ne s'active que si demandé
(uploads laissés lean : LoTW/eQSL recalculent leurs zones). Lot 4 : peuple les
champs déjà émis par build_adif (CQZ/ITUZ/DISTANCE/ANT_AZ)."""
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
os.chdir(BASE)

import logx_export as export   # noqa: E402


def _q(**extra):
    q = {'call': 'W1AW', 'band': '20', 'mode': 'SSB', 'date': '20260101',
         'time': '1200', 'rst_sent': '59', 'rst_rcvd': '59'}
    q.update(extra)
    return q


def test_completer_derive_cqz_ituz_depuis_indicatif():
    adif = export.build_adif([_q()], {}, completer=True).upper()
    assert '<CQZ:' in adif and '<ITUZ:' in adif, adif


def test_sans_completer_rien_de_derive():
    # défaut : comportement inchangé (upload-safe).
    adif = export.build_adif([_q()], {}).upper()
    assert '<CQZ:' not in adif and '<ITUZ:' not in adif, adif


def test_completer_derive_distance_azimut_depuis_locators():
    q = _q(locator='JN18', my_locator='JO01')
    adif = export.build_adif([q], {}, completer=True).upper()
    assert '<DISTANCE:' in adif and '<ANT_AZ:' in adif, adif


def test_completer_n_ecrase_pas_une_saisie():
    q = _q(cqz='99')                       # zone saisie (fausse exprès)
    adif = export.build_adif([q], {}, completer=True).upper()
    assert '<CQZ:2>99' in adif, adif       # la saisie est respectée


def test_completer_ne_mute_pas_le_log_stocke():
    q = _q()
    export.build_adif([q], {}, completer=True)
    assert 'cqz' not in q, q               # le dict d'origine reste intact


# ─── Câblage (AST : insensible aux commentaires/chaînes) ─────────────────────

import ast   # noqa: E402


def _appels_build_adif(module):
    src = open(os.path.join(BASE, module), encoding='utf-8').read()
    out = []
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Call):
            nom = getattr(node.func, 'attr', None) or getattr(node.func, 'id', None)
            if nom == 'build_adif':
                out.append({k.arg for k in node.keywords})
    return out


def test_uploads_qsl_ne_completent_pas():
    # uploads lean : LoTW/eQSL recalculent leurs zones, on ne modifie pas la
    # donnée sortante -> aucun appel build_adif de logx_qsl ne passe completer.
    appels = _appels_build_adif('logx_qsl.py')
    assert appels
    for kw in appels:
        assert 'completer' not in kw, kw


def test_archive_et_backup_completent():
    for module in ('logx_archive.py', 'logx_backup.py'):
        appels = _appels_build_adif(module)
        assert appels and all('completer' in kw for kw in appels), (module, appels)


# ─── Lot 5 : COUNTRY/CONT + MY_COUNTRY/MY_CQ_ZONE/MY_ITU_ZONE ────────────────
# Noms de tags ADIF sourcés adif.org/315 (asymétrie CQZ/ITUZ vs MY_CQ_ZONE/
# MY_ITU_ZONE confirmée).

def test_completer_emet_country_et_continent():
    adif = export.build_adif([_q()], {}, completer=True).upper()   # W1AW -> USA / NA
    assert '<COUNTRY:' in adif and '<CONT:2>NA' in adif, adif


def test_completer_emet_my_country_et_zones_avec_config():
    adif = export.build_adif([_q()], {'callsign': 'W1AW'}, completer=True).upper()
    assert '<MY_COUNTRY:' in adif, adif
    assert '<MY_CQ_ZONE:' in adif and '<MY_ITU_ZONE:' in adif, adif


def test_country_importe_survit_au_reexport():
    # symétrie : COUNTRY importé -> clé interne -> ré-émis (pas de perte via
    # extra_fields, leçon de la revue B).
    import logx_import as imp
    adif_in = ("<CALL:4>W1AW<BAND:3>20m<MODE:3>SSB<QSO_DATE:8>20260101"
               "<TIME_ON:4>1200<COUNTRY:13>United States<CONT:2>NA<EOR>")
    qsos, err = imp.parse_adif_to_qsos(adif_in)
    assert not err and qsos[0].get('dxcc_country') == 'United States', qsos
    adif_out = export.build_adif(qsos, {}).upper()      # sans completer
    assert '<COUNTRY:13>UNITED STATES' in adif_out, adif_out


# ─── Parité client (VRAI buildAdifText en V8) ────────────────────────────────

import json    # noqa: E402
import pytest   # noqa: E402

py_mini_racer = pytest.importorskip(
    'py_mini_racer', reason='py_mini_racer absent — test JS réel ignoré')

_EXPORT_JS = open(os.path.join(BASE, 'logx_export_adif.js'), encoding='utf-8').read()
_STUBS = ("var myCall='F4GLD', myLocator='JN15WD';"
          "function _resolveOperatorCallsign(x){ return x||''; }")


def test_client_v8_emet_country_et_my_zones():
    ctx = py_mini_racer.MiniRacer()
    ctx.eval(_STUBS)
    ctx.eval(_EXPORT_JS)
    q = [{'call': 'W1AW', 'band': '20', 'mode': 'SSB', 'date': '20260101',
          'time': '1200', 'rst_sent': '59', 'rst_rcvd': '59',
          'dxcc_country': 'United States', 'continent': 'NA',
          'my_dxcc_country': 'France', 'my_cqz': '14', 'my_ituz': '27'}]
    adif = ctx.eval('buildAdifText(%s)' % json.dumps(q)).upper()
    assert '<COUNTRY:13>UNITED STATES' in adif and '<CONT:2>NA' in adif, adif
    assert '<MY_COUNTRY:6>FRANCE' in adif, adif
    assert '<MY_CQ_ZONE:2>14' in adif and '<MY_ITU_ZONE:2>27' in adif, adif
