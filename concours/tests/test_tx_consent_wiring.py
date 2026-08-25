# -*- coding: utf-8 -*-
"""Câblage backend du consentement d'émission (item 2, F4GLD 25/08).

Étend le module #251 (logx_tx_consent) avec ce qu'il faut pour brancher les
endpoints serveur SANS deviner : mappage de l'état CAT réel vers le contrôle
d'autorisation, verrou TX serveur posé par « Stop TX », journal d'audit en
mémoire (façon logx_cw_journal). On teste les FONCTIONS (le HTTP reste une
enveloppe mince), jamais le PTT matériel.
"""
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
os.chdir(BASE)

import logx_tx_consent as txc   # noqa: E402


def _consent(now):
    return txc.create_tx_consent(
        operator_callsign='F4GLD', radio_id='rig1', frequency_hz=14_074_000,
        mode='USB', power_w=50.0, message='TEST', now=now)


# ─── Mappage de l'état CAT réel → dict attendu par authorize_transmission ─────

def test_radio_state_from_cat_mappe_les_champs():
    import datetime
    now = datetime.datetime(2026, 8, 25, 12, 0, tzinfo=datetime.timezone.utc)
    c = _consent(now)
    # cat.get_state renvoie freq_hz/mode/ok/enabled (schéma réel vérifié
    # logx_cat.get_state) — PAS de power_w ni ptt_locked.
    cat_state = {'ok': True, 'enabled': True, 'freq_hz': 14_074_000, 'mode': 'USB'}
    rs = txc.radio_state_from_cat(cat_state, c, locked=False)
    assert rs['cat_connected'] is True
    assert rs['frequency_hz'] == 14_074_000
    assert rs['mode'] == 'USB'
    assert rs['ptt_locked'] is False
    # puissance : reportée du jeton (le CAT ne la lit pas — décision documentée)
    assert rs['power_w'] == 50.0
    # l'état ainsi mappé DOIT autoriser (tout concorde)
    entry = txc.authorize_transmission(c, rs, now=now)
    assert entry['event'] == 'TX_AUTHORIZED_AND_EXECUTED'


def test_radio_state_cat_absent_refuse():
    import datetime
    now = datetime.datetime(2026, 8, 25, 12, 0, tzinfo=datetime.timezone.utc)
    c = _consent(now)
    cat_state = {'ok': False, 'enabled': True, 'error': 'injoignable'}
    rs = txc.radio_state_from_cat(cat_state, c, locked=False)
    assert rs['cat_connected'] is False
    import pytest
    with pytest.raises(ConnectionError):
        txc.authorize_transmission(c, rs, now=now)


def test_radio_state_frequence_changee_refuse():
    import datetime
    now = datetime.datetime(2026, 8, 25, 12, 0, tzinfo=datetime.timezone.utc)
    c = _consent(now)
    cat_state = {'ok': True, 'enabled': True, 'freq_hz': 14_075_000, 'mode': 'USB'}
    rs = txc.radio_state_from_cat(cat_state, c, locked=False)
    import pytest
    with pytest.raises(PermissionError):
        txc.authorize_transmission(c, rs, now=now)


# ─── Verrou TX serveur (posé par « Stop TX ») ────────────────────────────────

def test_verrou_tx_pose_par_stop_bloque_autorisation():
    import datetime
    now = datetime.datetime(2026, 8, 25, 12, 0, tzinfo=datetime.timezone.utc)
    txc.unlock_tx()
    assert txc.is_tx_locked() is False
    c = _consent(now)
    cat_state = {'ok': True, 'enabled': True, 'freq_hz': 14_074_000, 'mode': 'USB'}
    # Stop TX pose le verrou serveur
    txc.stop_tx()
    assert txc.is_tx_locked() is True
    rs = txc.radio_state_from_cat(cat_state, c, locked=txc.is_tx_locked())
    assert rs['ptt_locked'] is True
    import pytest
    with pytest.raises(PermissionError):
        txc.authorize_transmission(c, rs, now=now)
    txc.unlock_tx()   # réarmement humain
    assert txc.is_tx_locked() is False


# ─── Journal d'audit en mémoire (façon logx_cw_journal) ──────────────────────

def test_journal_audit_enregistre_et_borne():
    txc.vider_audit()
    txc.journal_audit({'event': 'TX_AUTHORIZED_AND_EXECUTED', 'mode': 'USB'})
    entrees = txc.audit_entries()
    assert len(entrees) == 1
    assert entrees[-1]['mode'] == 'USB'
    # horodatage UTC ajouté si absent
    assert entrees[-1]['timestamp_utc'].endswith('Z')
    txc.vider_audit()
    assert txc.audit_entries() == []
