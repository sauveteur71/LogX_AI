# -*- coding: utf-8 -*-
"""Durcissement du consentement TX (additif, rétro-compatible) :

  A. EMPREINTE du message (SHA-256) gravée dans le journal d'audit — un
     caractère changé dans le message donne une empreinte différente. Renforce
     la traçabilité (« ce qui a RÉELLEMENT été autorisé+émis ») sans changer le
     comportement d'émission.
  B. PLAFOND DE PUISSANCE optionnel sur authorize_transmission : au-delà du
     plafond configuré, l'autorisation est REFUSÉE (jeton non consommé). Défaut
     None -> aucun plafond -> comportement inchangé (rétro-compat).

Ces tests s'ajoutent à test_tx_consent.py (cycle de vie, usage unique,
expiration, refus sur changement freq/mode/power, Stop TX) sans le modifier.
"""
import pytest

import logx_tx_consent as txc


def _radio_ok(c):
    """État CAT qui MATCHE le jeton (pour atteindre les contrôles ajoutés)."""
    return {'cat_connected': True, 'ptt_locked': False,
            'frequency_hz': c.frequency_hz, 'mode': c.mode, 'power_w': c.power_w}


# ── A. Empreinte du message ──────────────────────────────────────────────────

def test_empreinte_message_sha256_deterministe_et_sensible():
    e1 = txc.empreinte_message('CQ TEST DE F4GLD')
    assert len(e1) == 64 and all(ch in '0123456789abcdef' for ch in e1)  # sha256 hex
    assert txc.empreinte_message('CQ TEST DE F4GLD') == e1               # déterministe
    assert txc.empreinte_message('CQ TEST DE F4GLE') != e1               # 1 caractère -> tout change


def test_audit_porte_l_empreinte_du_message():
    c = txc.create_tx_consent('F4GLD', 'r1', 14074000, 'USB', 5, 'CQ TEST')
    entry = txc.authorize_transmission(c, _radio_ok(c))
    assert entry['message_sha256'] == txc.empreinte_message('CQ TEST')


def test_audit_copilote_porte_aussi_l_empreinte():
    entry = txc.journal_copilote_emission({'operator_callsign': 'DX', 'mode': 'FT8',
                                           'message': 'F4GLD JA1XYZ -12'})
    assert entry['message_sha256'] == txc.empreinte_message('F4GLD JA1XYZ -12')


# ── B. Plafond de puissance ──────────────────────────────────────────────────

def test_plafond_puissance_refuse_au_dessus():
    c = txc.create_tx_consent('F4GLD', 'r1', 14074000, 'USB', 100, 'CQ')
    with pytest.raises(PermissionError):
        txc.authorize_transmission(c, _radio_ok(c), max_power_w=50)
    assert c.used is False          # jeton NON consommé sur un refus


def test_plafond_puissance_ok_a_egalite():
    c = txc.create_tx_consent('F4GLD', 'r1', 14074000, 'USB', 50, 'CQ')
    entry = txc.authorize_transmission(c, _radio_ok(c), max_power_w=50)   # égal = autorisé
    assert entry['power_w'] == 50 and c.used is True


def test_plafond_chaine_numerique_est_honore():
    # Un plafond fourni comme chaîne numérique (config) reste appliqué.
    c = txc.create_tx_consent('F4GLD', 'r1', 14074000, 'USB', 100, 'CQ')
    with pytest.raises(PermissionError):
        txc.authorize_transmission(c, _radio_ok(c), max_power_w='50')


def test_plafond_illisible_ne_fait_pas_planter_et_n_impose_rien():
    # Config malformée (fail-OPEN sur ce garde-fou OPTIONNEL) : pas d'exception,
    # revient au comportement « pas de plafond » — jamais un 500 sur /tx/authorize.
    c = txc.create_tx_consent('F4GLD', 'r1', 14074000, 'USB', 100, 'CQ')
    entry = txc.authorize_transmission(c, _radio_ok(c), max_power_w='oops')
    assert entry['event'] == 'TX_AUTHORIZED_AND_EXECUTED'


def test_sans_plafond_aucun_refus_de_puissance():
    # Rétro-compat : max_power_w=None (défaut) -> aucun plafond, même à 1500 W.
    c = txc.create_tx_consent('F4GLD', 'r1', 14074000, 'USB', 1500, 'CQ')
    entry = txc.authorize_transmission(c, _radio_ok(c))
    assert entry['event'] == 'TX_AUTHORIZED_AND_EXECUTED'
