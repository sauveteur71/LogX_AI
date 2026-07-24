# -*- coding: utf-8 -*-
"""Tests du panneau ROULEMENT OPÉRATEURS de l'écran mural :
logx_wall._active_operators() (qui est actuellement au poste, proxy = dernier
QSO loggué par opérateur dans une fenêtre de récence) + son exposition dans
wall_state()['active_ops']. Le planning à VENIR (/shifts/list) est déjà
couvert par tests/test_shifts.py — logx_wall.html le consomme séparément,
sans logique serveur propre à tester ici."""
import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_wall as wall

NOW = datetime.datetime(2026, 7, 24, 14, 0, 0)


def _entry(call, op, minutes_ago, band='14', mode='CW'):
    dt = NOW - datetime.timedelta(minutes=minutes_ago)
    return {'call': call, 'operator': op, 'band': band, 'mode': mode,
            'date': dt.strftime('%Y%m%d'), 'time': dt.strftime('%H:%M')}


def test_operateur_recent_est_actif_avec_ses_qualifications():
    cfg = {'operators': [
        {'call': 'F4GLD', 'name': 'Olivier', 'modes': {'ssb': True, 'cw': True, 'digi': False}},
    ]}
    entries = [_entry('DL1AA', 'F4GLD', 5)]
    active = wall._active_operators(entries, cfg, NOW)
    assert len(active) == 1
    op = active[0]
    assert op['call'] == 'F4GLD'
    assert op['name'] == 'Olivier'
    assert op['modes'] == {'ssb': True, 'cw': True, 'digi': False}
    assert op['secs_ago'] == 5 * 60


def test_operateur_trop_ancien_nest_pas_actif():
    """QSO loggué il y a 30 min > ACTIVE_OP_WINDOW_MIN (15) -> exclu."""
    cfg = {'operators': [{'call': 'F6XYZ', 'name': 'Jean', 'modes': {}}]}
    entries = [_entry('DL2BB', 'F6XYZ', 30)]
    assert wall._active_operators(entries, cfg, NOW) == []


def test_operateur_juste_a_la_limite_de_la_fenetre_reste_actif():
    cfg = {}
    entries = [_entry('DL3CC', 'F1ABC', wall.ACTIVE_OP_WINDOW_MIN)]
    active = wall._active_operators(entries, cfg, NOW)
    assert len(active) == 1 and active[0]['call'] == 'F1ABC'


def test_operateur_inconnu_de_la_config_a_quand_meme_un_badge_par_defaut():
    """Un opérateur qui logge mais n'est pas (ou plus) déclaré dans
    CONFIG > Opérateurs ne doit jamais faire planter le panneau — qualifié
    partout par défaut, comme /shifts/add et collectConfig()."""
    entries = [_entry('DL4DD', 'F9ZZZ', 2)]
    active = wall._active_operators(entries, {}, NOW)
    assert len(active) == 1
    assert active[0]['name'] == ''
    assert active[0]['modes'] == {'ssb': True, 'cw': True, 'digi': True}


def test_qualification_partielle_ne_prive_pas_silencieusement_des_autres_modes():
    """modes={'cw': False} déclaré -> cw=False respecté, mais ssb/digi absents
    du dict retombent sur True (jamais désactivés par erreur)."""
    cfg = {'operators': [{'call': 'F6XYZ', 'modes': {'cw': False}}]}
    entries = [_entry('DL5EE', 'F6XYZ', 1)]
    active = wall._active_operators(entries, cfg, NOW)
    assert active[0]['modes'] == {'ssb': True, 'cw': False, 'digi': True}


def test_plusieurs_operateurs_actifs_tries_du_plus_recent_au_plus_ancien():
    cfg = {}
    entries = [
        _entry('DL1AA', 'F4GLD', 10),
        _entry('DL2BB', 'F6XYZ', 2),
        _entry('DL3CC', 'F1ABC', 14),
    ]
    active = wall._active_operators(entries, cfg, NOW)
    assert [a['call'] for a in active] == ['F6XYZ', 'F4GLD', 'F1ABC']


def test_seul_le_dernier_qso_dun_operateur_compte_pour_sa_recence():
    """Un opérateur avec un ancien ET un récent QSO reste actif — la fenêtre
    se juge sur son QSO le PLUS récent, pas le plus ancien."""
    cfg = {}
    entries = [
        _entry('DL1AA', 'F4GLD', 45),   # ancien
        _entry('DL2BB', 'F4GLD', 3),    # récent -> actif
    ]
    active = wall._active_operators(entries, cfg, NOW)
    assert len(active) == 1 and active[0]['secs_ago'] == 3 * 60


def test_entree_sans_operateur_ni_date_exploitable_est_ignoree_sans_planter():
    cfg = {}
    entries = [
        {'call': 'DL1AA', 'band': '14', 'mode': 'CW'},                     # pas d'opérateur
        {'call': 'DL2BB', 'operator': 'F4GLD', 'band': '14', 'mode': 'CW'},  # pas de date/heure
    ]
    assert wall._active_operators(entries, cfg, NOW) == []


def test_wall_state_expose_active_ops():
    log = [_entry('DL1AA', 'F4GLD', 1)]
    st = wall.wall_state(log, {'operators': [{'call': 'F4GLD', 'name': 'Olivier'}]},
                          now=NOW)
    assert 'active_ops' in st
    assert st['active_ops'][0]['call'] == 'F4GLD'
    assert st['active_ops'][0]['name'] == 'Olivier'


def test_wall_state_active_ops_vide_si_log_vide():
    st = wall.wall_state([], {}, now=NOW)
    assert st['active_ops'] == []
