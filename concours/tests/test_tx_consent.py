# -*- coding: utf-8 -*-
"""Consentement d'émission « ÉMISSION UNIQUE » (logx_tx_consent) — couche
d'autorisation HUMAINE par-dessus le garde-fou mode/bande (logx_tx_guard).

Politique (skill tx-human-consent) : jeton unique, expiration rapide (30 s),
usage unique, invalidé au moindre changement radio (fréquence/mode/puissance),
CAT confirmé exigé, PTT non verrouillé, Stop TX annule tout. L'IA prépare,
l'humain déclenche."""
import datetime
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
os.chdir(BASE)

import pytest   # noqa: E402

import logx_tx_consent as consent   # noqa: E402

UTC = datetime.timezone.utc


def _t(s=0):
    return datetime.datetime(2026, 8, 25, 12, 0, s, tzinfo=UTC)


def _radio(**over):
    r = {'frequency_hz': 14074000, 'mode': 'FT8', 'power_w': 20,
         'ptt_locked': False, 'cat_connected': True}
    r.update(over)
    return r


def _consent(now=None):
    return consent.create_tx_consent(
        operator_callsign='F1XYZ', radio_id='IC-7300', frequency_hz=14074000,
        mode='FT8', power_w=20, message='F4ABC F1XYZ R-12', now=now or _t(0))


# ─── cycle de vie du jeton ───────────────────────────────────────────────────

def test_consent_frais_valide_puis_expire():
    c = _consent(now=_t(0))
    assert c.token and not c.used
    assert c.is_valid(now=_t(10))               # dans les 30 s
    assert not c.is_valid(now=_t(31))           # expiré (>30 s)


def test_consent_utilise_invalide():
    c = _consent(now=_t(0))
    c.used = True
    assert not c.is_valid(now=_t(1))


# ─── autorisation juste avant PTT ────────────────────────────────────────────

def test_autorise_ok_marque_utilise_et_journalise():
    c = _consent(now=_t(0))
    audit = consent.authorize_transmission(c, _radio(), ptt_method='CAT', now=_t(5))
    assert c.used is True                        # consommé (usage unique)
    assert audit['event'] == 'TX_AUTHORIZED_AND_EXECUTED'
    assert audit['operator_callsign'] == 'F1XYZ' and audit['frequency_hz'] == 14074000
    assert audit['consent_mode'] == 'single_transmission'


def test_reutilisation_refusee():
    c = _consent(now=_t(0))
    consent.authorize_transmission(c, _radio(), now=_t(5))
    with pytest.raises(PermissionError):
        consent.authorize_transmission(c, _radio(), now=_t(6))   # déjà utilisé


def test_expire_refuse():
    c = _consent(now=_t(0))
    with pytest.raises(PermissionError):
        consent.authorize_transmission(c, _radio(), now=_t(31))  # >30 s


@pytest.mark.parametrize('champ,val', [
    ('frequency_hz', 14075000), ('mode', 'CW'), ('power_w', 100)])
def test_changement_radio_refuse(champ, val):
    c = _consent(now=_t(0))
    with pytest.raises(PermissionError):
        consent.authorize_transmission(c, _radio(**{champ: val}), now=_t(5))


def test_cat_non_confirme_refuse():
    c = _consent(now=_t(0))
    with pytest.raises(ConnectionError):
        consent.authorize_transmission(c, _radio(cat_connected=False), now=_t(5))


def test_ptt_verrouille_refuse():
    c = _consent(now=_t(0))
    with pytest.raises(PermissionError):
        consent.authorize_transmission(c, _radio(ptt_locked=True), now=_t(5))


# ─── Stop TX ─────────────────────────────────────────────────────────────────

def test_stop_tx_invalide_le_jeton_en_attente():
    consent.stop_tx()                            # repart propre
    c = _consent(now=_t(0))
    consent.register(c)
    assert consent.get(c.token) is not None
    n = consent.stop_tx()
    assert n >= 1
    assert consent.get(c.token) is None          # jeton annulé
    with pytest.raises(PermissionError):
        consent.authorize_transmission(c, _radio(), now=_t(2))   # annulé -> refusé


# ─── traçabilité des émissions COPILOTE (chemin client FT8, hors /tx/authorize) ──

def test_journal_copilote_emission_grave_dans_l_audit():
    """Les émissions copilote FT8 partent par le chemin CLIENT (envoyerMessage) et
    ne passent pas par /tx/authorize : elles doivent quand même être GRAVÉES dans
    le journal d'audit serveur (principe verrouillé « traçable »)."""
    consent.vider_audit()
    entry = consent.journal_copilote_emission({
        'operator_callsign': 'F1XYZ', 'radio_id': 'F4ABC', 'frequency_hz': 14074000,
        'mode': 'FT8', 'message': 'F4ABC F1XYZ R-12', 'declencheur': 'copilote_auto'})
    assert entry['event'] == 'TX_COPILOTE_EMISSION'
    assert entry['operator_callsign'] == 'F1XYZ'
    assert entry['radio_id'] == 'F4ABC'             # DX visé, jamais l'humain
    assert entry['frequency_hz'] == 14074000 and entry['mode'] == 'FT8'
    assert entry['message'] == 'F4ABC F1XYZ R-12'
    assert entry['declencheur'] == 'copilote_auto'  # auto vs confirmation manuelle
    assert 'timestamp_utc' in entry                 # horodaté UTC
    # RÉELLEMENT dans le journal consultable via /tx/audit
    derniere = consent.audit_entries(1)[-1]
    assert derniere['event'] == 'TX_COPILOTE_EMISSION'
    assert derniere['message'] == 'F4ABC F1XYZ R-12'


def test_journal_copilote_declencheur_par_defaut_et_ne_leve_jamais():
    consent.vider_audit()
    # déclencheur absent -> 'copilote' (confirmation manuelle) par défaut
    e = consent.journal_copilote_emission({'operator_callsign': 'F1XYZ',
                                           'message': 'CQ F1XYZ'})
    assert e['declencheur'] == 'copilote'
    # entrée illisible : ne lève pas (une trace ratée ne casse pas une émission)
    consent.journal_copilote_emission(None)
