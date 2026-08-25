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
