# -*- coding: utf-8 -*-
"""Garde-fou TX unifié (CW + phonie) — sous-chantier « Unifier la sécurité TX ».

`logx_tx_guard.tx_autorise(payload, famille)` généralise l'ancien garde-fou CW à
la voix : même interrupteur maître (`armed`) et même contrôle de bande, mais le
contrôle de MODE dépend de la famille :

  - famille 'cw'     : refuse si le mode connu n'est PAS un mode CW.
  - famille 'phonie' : refuse si le mode connu est CW ou un mode DATA/numérique
                       (RTTY/FSK/DATA*/PKT*/FT8…) — on n'émet pas de voix dans
                       ces modes. LSB/USB/AM/FM/inconnu -> autorisé (armé requis).

Le garde-fou valide le mode/fréquence qui seront réellement TRANSMIS (VFO TX) —
le client envoie ces valeurs. Fonction PURE (aucune I/O radio).
"""
import logx_tx_guard as g


# ── Famille phonie : ce qui doit être REFUSÉ ────────────────────────────────

def test_phonie_refuse_si_non_arme():
    ok, raison = g.tx_autorise({'mode': 'USB'}, 'phonie')
    assert ok is False
    assert 'armé' in raison.lower() or 'arme' in raison.lower()


def test_phonie_refuse_mode_cw():
    ok, raison = g.tx_autorise({'armed': True, 'mode': 'CW'}, 'phonie')
    assert ok is False


def test_phonie_refuse_mode_data_rtty():
    ok, _ = g.tx_autorise({'armed': True, 'mode': 'RTTY'}, 'phonie')
    assert ok is False


def test_phonie_refuse_mode_data_ft8():
    ok, _ = g.tx_autorise({'armed': True, 'mode': 'FT8'}, 'phonie')
    assert ok is False


def test_phonie_refuse_mode_data_usb_suffixe():
    # Yaesu/Icom rapportent un créneau data dédié (DATA-USB / PKTUSB) : voix NON.
    ok, _ = g.tx_autorise({'armed': True, 'mode': 'DATA-USB'}, 'phonie')
    assert ok is False


def test_phonie_refuse_hors_bande():
    ok, _ = g.tx_autorise({'armed': True, 'mode': 'USB', 'freq_khz': 27500}, 'phonie')
    assert ok is False


# ── Famille phonie : ce qui doit être AUTORISÉ ──────────────────────────────

def test_phonie_autorise_ssb_usb():
    ok, raison = g.tx_autorise({'armed': True, 'mode': 'USB'}, 'phonie')
    assert ok is True
    assert raison == ''


def test_phonie_autorise_ssb_lsb():
    ok, _ = g.tx_autorise({'armed': True, 'mode': 'LSB'}, 'phonie')
    assert ok is True


def test_phonie_autorise_fm():
    ok, _ = g.tx_autorise({'armed': True, 'mode': 'FM'}, 'phonie')
    assert ok is True


def test_phonie_autorise_mode_inconnu():
    # Mode inconnu (pas de CAT) : on ne bloque pas sur le seul mode, l'arme suffit.
    ok, _ = g.tx_autorise({'armed': True, 'mode': ''}, 'phonie')
    assert ok is True


def test_phonie_autorise_en_bande():
    ok, _ = g.tx_autorise({'armed': True, 'mode': 'USB', 'freq_khz': 14200}, 'phonie')
    assert ok is True


# ── Famille cw : comportement historique préservé ───────────────────────────

def test_cw_refuse_si_non_arme():
    ok, _ = g.tx_autorise({'mode': 'CW'}, 'cw')
    assert ok is False


def test_cw_refuse_mode_phonie():
    ok, _ = g.tx_autorise({'armed': True, 'mode': 'USB'}, 'cw')
    assert ok is False


def test_cw_autorise_cw_arme():
    ok, raison = g.tx_autorise({'armed': True, 'mode': 'CW'}, 'cw')
    assert ok is True
    assert raison == ''


# ── Classifieur data (chaînes rapportées par le poste) ──────────────────────

def test_est_mode_data_reconnait_les_creneaux_poste():
    for m in ('RTTY', 'RTTY-R', 'FSK', 'DATA', 'DATA-USB', 'PKTUSB', 'FT8', 'PSK'):
        assert g.est_mode_data(m) is True, m


def test_est_mode_data_faux_pour_phonie_et_cw():
    for m in ('USB', 'LSB', 'FM', 'AM', 'CW', 'CW-R', ''):
        assert g.est_mode_data(m) is False, m
