# -*- coding: utf-8 -*-
"""Garde-fou d'émission CW (logx_cw_guard) : TX-enable maître + mode CW.

Refus BLOQUANT si le TX n'est pas armé, ou si le mode connu n'est pas CW.
Fonction pure -> testée sans poste ni serveur.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from logx_cw_guard import cw_tx_autorise, est_mode_cw


def test_refuse_si_tx_non_arme():
    ok, raison = cw_tx_autorise({'mode': 'CW'})            # armed absent
    assert ok is False and 'armé' in raison
    ok2, _ = cw_tx_autorise({'armed': False, 'mode': 'CW'})
    assert ok2 is False


def test_autorise_si_arme_et_mode_cw():
    for mode in ('CW', 'CW-R', 'CWR', 'CW-U', 'CW-L', 'cw', 'CW_R'):
        ok, raison = cw_tx_autorise({'armed': True, 'mode': mode})
        assert ok is True and raison == '', (mode, raison)


def test_refuse_si_mode_non_cw():
    for mode in ('USB', 'LSB', 'FT8', 'RTTY', 'FM', 'DATA-U'):
        ok, raison = cw_tx_autorise({'armed': True, 'mode': mode})
        assert ok is False and mode in raison, (mode, raison)


def test_mode_inconnu_ne_bloque_pas_si_arme():
    # WinKeyer sans CAT : mode absent -> seul l'armement compte
    ok, raison = cw_tx_autorise({'armed': True, 'mode': ''})
    assert ok is True and raison == ''
    ok2, _ = cw_tx_autorise({'armed': True})
    assert ok2 is True


def test_payload_non_dict_refuse():
    assert cw_tx_autorise(None)[0] is False
    assert cw_tx_autorise('CW')[0] is False


def test_est_mode_cw():
    assert est_mode_cw('CW') and est_mode_cw('cw-r') and est_mode_cw('CW_L')
    assert not est_mode_cw('USB') and not est_mode_cw('') and not est_mode_cw(None)


def test_handler_appelle_le_garde_fou_avant_le_verrou_tx():
    """Structure (pas juste présence) : /rig/cw doit appeler cw_tx_autorise
    AVANT de prendre le verrou TX, sinon un refus laisserait le verrou pris."""
    import re
    src = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            'logx_http.py'), encoding='utf-8').read()
    i_guard = src.find('cw_tx_autorise(')          # l'APPEL (parenthèse), pas un commentaire
    i_lock = src.find("verrouiller_tx(radio_active, 'cw')")
    assert i_guard != -1, 'garde-fou cw_tx_autorise non câblé dans /rig/cw'
    assert i_lock != -1, 'verrou TX introuvable'
    assert i_guard < i_lock, 'le garde-fou doit précéder la prise du verrou TX'
    # et le refus doit court-circuiter (return) avant le verrou
    entre = src[i_guard:i_lock]
    assert re.search(r'blocked.*True|403', entre) and 'return' in entre, \
        'un refus du garde-fou doit renvoyer 403 et return avant le verrou'
