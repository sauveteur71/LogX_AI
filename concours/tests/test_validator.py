# -*- coding: utf-8 -*-
"""Validateur de log (logx_validator) : indicatifs portables et actions.

Régression clé : un indicatif à PRÉFIXE de lieu (EA/F4GLD = F4GLD émettant
depuis l'Espagne) était signalé « busted call probable » à tort, sans moyen
simple de corriger/supprimer le QSO."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_validator as v


def test_plausible_call_portable_prefixe_et_suffixe():
    for good in ['F4GLD', 'EA/F4GLD', 'F4GLD/P', 'EA/F4GLD/P', 'W1AW/4',
                 '9A/DL1XYZ', 'F/G3XYZ', 'PJ2/K1ABC', 'EA8/DL1ABC']:
        assert v._plausible_call(good), f"{good} devrait être plausible"
    for bad in ['XYZ', '12345', '', '///']:
        assert not v._plausible_call(bad), f"{bad} ne devrait pas être plausible"


def test_prefixe_portable_non_signale_comme_busted():
    """Le cœur du bug utilisateur : EA/F4GLD ne doit plus produire de constat
    'indicatif_suspect'."""
    qsos = [{'id': 1, 'call': 'EA/F4GLD', 'band': '14', 'mode': 'SSB',
             'date': '20260720', 'time': '1200', 'rst_rcvd': '59'}]
    res = v.validate_log(qsos, contest_id='', cfg={'usage_mode': 'simple'})
    codes = {f['code'] for f in res['findings']}
    assert 'indicatif_suspect' not in codes
    assert 'prefixe_inconnu' not in codes


def test_findings_portent_l_id_pour_action_interface():
    """Chaque constat lié à un QSO doit exposer son id (bouton Corriger/Supprimer)."""
    qsos = [{'id': 42, 'call': '', 'band': '14'}]  # indicatif vide -> erreur
    res = v.validate_log(qsos, contest_id='', cfg={'usage_mode': 'simple'})
    assert res['findings']
    assert res['findings'][0].get('id') == 42
