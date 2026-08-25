# -*- coding: utf-8 -*-
"""Bug bloquant (F4GLD) : department_targets() etait AVEUGLE aux indicatifs
jamais loggues. Le locator PORTE PAR LE SPOT (souvent present sur le cluster)
etait jete, et le departement d'un chasseur inedit ne pouvait venir que d'un
lookup RESEAU (echoue hors ligne / en zone blanche / en plein contest). Or le
locator du spot suffit : dept_from_locator, en LOCAL, sans reseau.
"""
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
os.chdir(BASE)

import logx_departments as dep   # noqa: E402


def test_station_jamais_loggee_resolue_par_le_locator_du_spot_SANS_reseau():
    # Log VIDE -> tous les departements manquants. Un indicatif francais JAMAIS
    # loggue, spotte avec SON locator, doit apparaitre dans son departement
    # SANS aucun lookup reseau (cfg=None -> _resolve_spotted_live inactif).
    loc = 'JN18RR'
    d = dep.dept_from_locator(loc)          # meme resolution que le fix
    assert d in dep.DEPARTMENTS
    spots = {'144': [{'call': 'F5XYZ', 'freq': 144310.0, 'locator': loc}]}
    res = dep.department_targets([], contest_id='', spots_by_label=spots, cfg=None)
    cible = next((t for t in res['targets'] if t['dept'] == d), None)
    assert cible is not None, "le departement du spot doit etre une cible"
    calls = [s['call'] for s in cible['spotted']]
    assert 'F5XYZ' in calls, "la station jamais loggee doit apparaitre via son locator"
    # sa frequence est conservee (pour le QSY au clic)
    sp = next(s for s in cible['spotted'] if s['call'] == 'F5XYZ')
    assert sp.get('freq') == 144310.0


def test_spot_sans_locator_ni_reseau_n_apparait_pas():
    # Sans locator ET sans cfg (reseau) -> impossible de rattacher : pas de cible
    # fantome (on n'invente pas un departement).
    spots = {'144': [{'call': 'F9ZZZ', 'freq': 144200.0}]}
    res = dep.department_targets([], spots_by_label=spots, cfg=None)
    for t in res['targets']:
        assert 'F9ZZZ' not in [s['call'] for s in t['spotted']]


def test_indicatif_non_francais_pas_rattache_par_locator():
    # Coherence avec dept_for_qso : la resolution locator-only est reservee aux
    # indicatifs francais (le departement REF est un decoupage francais).
    spots = {'144': [{'call': 'DL1ABC', 'freq': 144290.0, 'locator': 'JN18RR'}]}
    res = dep.department_targets([], spots_by_label=spots, cfg=None)
    for t in res['targets']:
        assert 'DL1ABC' not in [s['call'] for s in t['spotted']]
