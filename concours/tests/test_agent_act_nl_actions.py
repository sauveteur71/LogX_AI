# -*- coding: utf-8 -*-
"""Copilote NL — élargissement du vocabulaire d'actions (F4GLD 26/08). En plus
de pointer_rotor / qsy_radio, l'agent peut proposer : filtrer les spots (par
continent), changer de bande/mode (fréquence résolue serveur), pointer vers une
station (azimut résolu serveur depuis cty.dat). TOUT reste PROPOSÉ + confirmé,
jamais auto-exécuté : ces tests figent la validation/normalisation en
`pending_action` (jamais une valeur aberrante), sans réseau ni LLM."""
import os
import sys

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CONCOURS not in sys.path:
    sys.path.insert(0, CONCOURS)

import logx_http as h   # noqa: E402


def _p(tool, inp, cfg=None):
    return h.pending_action_from_tool({'tool': tool, 'input': inp}, cfg)


# ─── filtrer_spots (continent-based, mappe /spots/filter) ─────────────────
def test_filtre_continents_normalises():
    a = _p('filtrer_spots', {'dx_continents': ['as', 'oc']})
    assert a == {'type': 'filtre', 'dx_continents': ['AS', 'OC'], 'spotter_continents': []}


def test_filtre_continent_inconnu_ecarte():
    a = _p('filtrer_spots', {'dx_continents': ['AS', 'XX', 'zz']})
    assert a == {'type': 'filtre', 'dx_continents': ['AS'], 'spotter_continents': []}


def test_filtre_totalement_vide_est_refuse():
    # Un filtre qui ne filtre rien (aucun continent valide) est un no-op : None.
    assert _p('filtrer_spots', {'dx_continents': ['XX'], 'spotter_continents': []}) is None
    assert _p('filtrer_spots', {}) is None


# ─── changer_bande_mode (fréquence résolue via logx_frequences) ───────────
def test_bande_mode_numerique_freq_dial_precise():
    a = _p('changer_bande_mode', {'bande': '40m', 'mode': 'FT8'})
    assert a['type'] == 'qsy' and a['freq_khz'] == 7074.0
    assert a['mode'] == 'FT8' and a['approx'] is False and '40m' in a['cible']


def test_bande_mode_phonie_cw_bord_de_bande_approx():
    a = _p('changer_bande_mode', {'bande': '40m', 'mode': 'CW'})
    # CW/SSB n'ont pas de fréquence d'appel unique -> bord bas de bande, marqué approx.
    assert a['type'] == 'qsy' and a['freq_khz'] == 7000.0
    assert a['mode'] == 'CW' and a['approx'] is True


def test_bande_inconnue_refusee():
    assert _p('changer_bande_mode', {'bande': 'zzz', 'mode': 'CW'}) is None


# ─── pointer_vers (azimut résolu serveur depuis cty.dat + mon locator) ────
_CFG = {'locator': 'JN18CX'}


def test_pointer_vers_resout_azimut():
    a = _p('pointer_vers', {'indicatif': 'EA8AA'}, _CFG)   # Canaries
    assert a is not None and a['type'] == 'rotor'
    assert 200 <= a['azimut'] <= 240          # ~SO depuis la France
    assert 'Canary' in a['cible'] or 'EA8AA' in a['cible']


def test_pointer_vers_indicatif_inconnu_refuse():
    # QQ1X : préfixe non assigné (cty.dat rend None) -> pas d'azimut, pas d'action.
    assert _p('pointer_vers', {'indicatif': 'QQ1X'}, _CFG) is None


def test_pointer_vers_sans_mon_locator_refuse():
    # Sans locator station, l'azimut n'est pas calculable -> on ne propose rien.
    assert _p('pointer_vers', {'indicatif': 'EA8AA'}, {}) is None
