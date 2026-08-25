# -*- coding: utf-8 -*-
"""Sous-chantier B, lot 4 — injecter les confirmations REÇUES dans l'export ADIF.

Le statut « confirmé » d'un QSO (LoTW/eQSL/carte) vit dans
qsl_confirmations.json (rempli par la synchro LoTW — logx_qsl.py), PAS sur le
QSO lui-même. L'export ADIF l'ignorait : un log ré-importé ailleurs perdait
toute trace des confirmations. Correctif : build_adif accepte un dict
`confirmations` (injecté par l'appelant : endpoints d'export, archive, backup)
et émet LOTW_QSL_RCVD / EQSL_QSL_RCVD / QSL_RCVD = Y (+ date quand connue).

Sécurité : `confirmations=None` par défaut => AUCUN tag RCVD. Indispensable
pour les appelants d'UPLOAD (upload_lotw/upload_eqsl dans logx_qsl.py) qui ne
doivent jamais renvoyer à LoTW sa propre confirmation.

La clé de rapprochement QSO<->confirmation est celle des diplômes
(logx_awards._confirm_key = CALL|band|MODE) : l'export « confirmé » DOIT être
identique au « confirmé » affiché dans l'UI, pas une 2e définition divergente.
"""
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
os.chdir(BASE)

import logx_export as export           # noqa: E402
from logx_awards import _confirm_key    # noqa: E402  (même clé que les diplômes)


def _q(**extra):
    q = {'call': 'F4ABC', 'date': '20260824', 'time': '1215', 'band': '20',
         'mode': 'SSB', 'rst_sent': '59', 'rst_rcvd': '59'}
    q.update(extra)
    return q


def test_qso_confirme_lotw_emet_rcvd_et_date():
    q = _q()
    conf = {_confirm_key(q): {'lotw': '20260115'}}
    adif = export.build_adif([q], {}, confirmations=conf).upper()
    assert '<LOTW_QSL_RCVD:1>Y' in adif
    assert '<LOTW_QSLRDATE:8>20260115' in adif


def test_qso_confirme_eqsl_sans_date():
    q = _q()
    conf = {_confirm_key(q): {'eqsl': True}}      # confirmé, date inconnue
    adif = export.build_adif([q], {}, confirmations=conf).upper()
    assert '<EQSL_QSL_RCVD:1>Y' in adif
    assert 'EQSL_QSLRDATE' not in adif             # pas de date bidon


def test_qso_confirme_source_generique_carte():
    q = _q()
    conf = {_confirm_key(q): {'card': True}}       # source hors LoTW/eQSL
    adif = export.build_adif([q], {}, confirmations=conf).upper()
    assert '<QSL_RCVD:1>Y' in adif


def test_sans_confirmations_aucun_rcvd():
    # Défaut None : upload-safe, aucun tag RCVD injecté.
    q = _q()
    adif = export.build_adif([q], {}).upper()
    assert 'QSL_RCVD' not in adif
    adif2 = export.build_adif([q], {}, confirmations={}).upper()
    assert 'QSL_RCVD' not in adif2


def test_confirmation_non_matchante_ignoree():
    # Une confirmation pour un AUTRE QSO (clé différente) ne contamine pas.
    q = _q()
    conf = {'AUTRE|40|CW': {'lotw': '20260115'}}
    adif = export.build_adif([q], {}, confirmations=conf).upper()
    assert 'QSL_RCVD' not in adif


def test_date_datetime_non_adif_non_emise():
    # APP_LOTW_RXQSL peut valoir "2026-01-15 14:30:00" (pas une Date ADIF) :
    # RCVD=Y quand même mais AUCUNE *_QSLRDATE malformée.
    q = _q()
    conf = {_confirm_key(q): {'lotw': '2026-01-15 14:30:00'}}
    adif = export.build_adif([q], {}, confirmations=conf).upper()
    assert '<LOTW_QSL_RCVD:1>Y' in adif
    assert 'LOTW_QSLRDATE' not in adif


# ─── Câblage des appelants (AST : insensible aux commentaires/chaînes) ────────

import ast   # noqa: E402


def _appels_build_adif(module):
    """Ensemble de kwargs (noms) pour CHAQUE appel build_adif(...) du module."""
    src = open(os.path.join(BASE, module), encoding='utf-8').read()
    appels = []
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Call):
            nom = getattr(node.func, 'attr', None) or getattr(node.func, 'id', None)
            if nom == 'build_adif':
                appels.append({k.arg for k in node.keywords})
    return appels


def test_uploads_qsl_n_injectent_jamais_de_confirmations():
    # SÉCURITÉ : upload_lotw/upload_eqsl/… ne renvoient JAMAIS à un service sa
    # propre confirmation reçue. AUCUN appel build_adif de logx_qsl.py ne doit
    # passer `confirmations`.
    appels = _appels_build_adif('logx_qsl.py')
    assert appels, 'aucun appel build_adif trouvé dans logx_qsl.py (test à revoir)'
    for kw in appels:
        assert 'confirmations' not in kw, kw


def test_archive_et_backup_injectent_les_confirmations():
    for module in ('logx_archive.py', 'logx_backup.py'):
        appels = _appels_build_adif(module)
        assert appels, f'aucun appel build_adif dans {module}'
        assert all('confirmations' in kw for kw in appels), (module, appels)


def test_export_http_generique_injecte_les_confirmations():
    # L'export complet du log (endpoint /log/export/adif) embarque les
    # confirmations ; au moins un appel build_adif de logx_http.py les passe.
    appels = _appels_build_adif('logx_http.py')
    assert any('confirmations' in kw for kw in appels), appels
