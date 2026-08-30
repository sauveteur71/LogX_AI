# -*- coding: utf-8 -*-
"""Filtre d'export SOTA « prêt pour sotadata » (logx_export.sota_qsos_pour_upload).

Deux uploads distincts côté sotadata (chasse / portable) : on sépare par rôle
pour éviter que l'import ADIF ne devine mal le rôle d'un fichier mixte.
"""
import os
import sys

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CONCOURS not in sys.path:
    sys.path.insert(0, CONCOURS)

import logx_export as export   # noqa: E402


def _chasse(sig_info, date='20260130', sig='SOTA'):
    return {'call': 'G0ABC', 'sig': sig, 'sig_info': sig_info, 'date': date}


def _portable(my_info, date='20260130'):
    return {'call': 'G0ABC', 'my_sig': 'SOTA', 'my_sig_info': my_info, 'date': date}


def test_chasse_selectionne_sig_sota():
    log = [_chasse('G/LD-001'), _chasse('W1/AB-002')]
    r = export.sota_qsos_pour_upload(log, 'chaser')
    assert [q['sig_info'] for q in r] == ['G/LD-001', 'W1/AB-002']


def test_chasse_exclut_non_sota_et_ref_vide():
    log = [_chasse('K-0001', sig='POTA'), _chasse(''), _chasse('G/LD-001')]
    r = export.sota_qsos_pour_upload(log, 'chaser')
    assert [q['sig_info'] for q in r] == ['G/LD-001']


def test_portable_selectionne_my_sig_sota():
    log = [_portable('G/LD-003'), _chasse('G/LD-001')]
    r = export.sota_qsos_pour_upload(log, 'activator')
    assert [q['my_sig_info'] for q in r] == ['G/LD-003']


def test_chasse_et_portable_ne_se_melangent_pas():
    log = [_chasse('G/LD-001'), _portable('G/LD-003')]
    assert len(export.sota_qsos_pour_upload(log, 'chaser')) == 1
    assert len(export.sota_qsos_pour_upload(log, 'activator')) == 1


def test_qso_s2s_present_dans_les_deux_roles():
    # QSO S2S : mon sommet ET le sien -> compte comme chasse ET comme portable.
    q = {'call': 'G0ABC', 'sig': 'SOTA', 'sig_info': 'F/AB-001',
         'my_sig': 'SOTA', 'my_sig_info': 'G/LD-003', 'date': '20260201'}
    assert export.sota_qsos_pour_upload([q], 'chaser') == [q]
    assert export.sota_qsos_pour_upload([q], 'activator') == [q]


def test_filtre_par_annee():
    log = [_chasse('G/LD-001', date='20251231'), _chasse('F/AB-001', date='20260101')]
    r = export.sota_qsos_pour_upload(log, 'chaser', year=2026)
    assert [q['sig_info'] for q in r] == ['F/AB-001']


def test_role_inconnu_rend_liste_vide():
    assert export.sota_qsos_pour_upload([_chasse('G/LD-001')], 'nimportequoi') == []


def test_entree_non_dict_toleree_et_non_mutee():
    log = [None, 'oups', _chasse('G/LD-001')]
    r = export.sota_qsos_pour_upload(log, 'chaser')
    assert len(r) == 1
    assert len(log) == 3   # entrée inchangée
