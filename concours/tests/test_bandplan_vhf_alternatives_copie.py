# -*- coding: utf-8 -*-
"""alternatives_nb() rendait une copie SUPERFICIELLE (dict(a)) partageant la
liste mutable 'alternatives' du global ALTERNATIVES_NB : un appelant qui
modifiait la liste rendue corrompait la table du module pour tous les appels
suivants. Incohérent avec les autres accesseurs (segments/centres_activite)."""
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

import logx_bandplan_vhf as bp   # noqa: E402


def _bande_avec_alternatives():
    for b in bp.ALTERNATIVES_NB:
        a = bp.alternatives_nb(b)
        if a and isinstance(a.get('alternatives'), list) and a['alternatives']:
            return b
    raise AssertionError("aucune bande avec 'alternatives' dans ALTERNATIVES_NB")


def test_alternatives_nb_ne_partage_pas_la_liste_du_global():
    band = _bande_avec_alternatives()
    a = bp.alternatives_nb(band)
    n0 = len(a['alternatives'])
    a['alternatives'].append((0.0, 0.0))          # mutation de la valeur rendue
    b2 = bp.alternatives_nb(band)
    assert len(b2['alternatives']) == n0, \
        "l'accesseur partage la liste mutable du global (copie de surface)"
