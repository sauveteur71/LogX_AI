# -*- coding: utf-8 -*-
"""Indicatifs à barre : de quel pays est `4O/ON5JE`, et de quel pays `VK2ZK/P4` ?

LA RÈGLE, qui n'était écrite nulle part. logx_dxcc._lookup_compute découpe sur
les barres, écarte les modificateurs (/P, /M, /MM, /QRP, un chiffre seul), puis
trie les morceaux restants PAR LONGUEUR CROISSANTE et retient le premier qui
résout. Autrement dit : le morceau le plus court gagne.

POURQUOI ÇA MARCHE. Un préfixe de lieu est presque toujours plus court qu'un
indicatif complet — `4O` face à `ON5JE`, `CT8` face à `DL7AFS`. Et la même
règle traite du même coup la forme inverse, INDICATIF/SUFFIXE-DE-LIEU, où le
lieu est en dernier : `VK2ZK/P4` rend Aruba parce que `P4` est plus court que
`VK2ZK`. Une règle « le premier morceau gagne » se tromperait sur toute cette
seconde famille.

CE QUE CES TESTS PROTÈGENT VRAIMENT. La résolution DXCC alimente le comptage
des entités, les multiplicateurs de concours, les diplômes, la position sur la
carte et les alertes de besoin. Une refonte de _lookup_compute qui remplacerait
le tri par longueur par « le premier morceau » passerait tous les autres tests
du projet et ferait basculer la Sicile en Italie sans un mot.

MESURE SUR LE CARNET RÉEL (9 392 QSO, 30/07/2026) : 851 indicatifs à barre,
dont 201 où deux morceaux désignent des pays DIFFÉRENTS. Aucun mal résolu. Les
cinq cas de la seconde famille — lieu en suffixe — sont repris tels quels
ci-dessous : ce sont de vrais QSO du carnet, pas des exemples inventés.
"""
import os
import sys

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CONCOURS not in sys.path:
    sys.path.insert(0, CONCOURS)

import logx_dxcc as dxcc   # noqa: E402


def pays(call):
    return (dxcc.lookup(call) or {}).get('country', '')


# ─── Forme PRÉFIXE-DE-LIEU / INDICATIF ───────────────────────────────────────

@pytest.mark.parametrize('call,attendu', [
    ('4O/ON5JE', 'Montenegro'),        # un Belge depuis le Montenegro
    ('5B/G4GMZ', 'Cyprus'),
    ('6W/F4GPK', 'Senegal'),
    ('9A/F5SNJ', 'Croatia'),
    ('CT8/DL7AFS', 'Azores'),
    ('CT9/R9DX', 'Madeira Islands'),
    ('DL/G4OBK', 'Fed. Rep. of Germany'),
    ('EA7/G1WUU', 'Spain'),
    ('F/ON4ABC', 'France'),
])
def test_le_prefixe_de_lieu_l_emporte_sur_l_indicatif(call, attendu):
    """C'est le pays d'ÉMISSION qui compte pour le DXCC, pas la nationalité de
    l'opérateur : un Belge au Montenegro donne du Montenegro."""
    assert pays(call) == attendu


# ─── Forme INDICATIF / SUFFIXE-DE-LIEU ───────────────────────────────────────
# Les cinq cas ci-dessous sont de VRAIS QSO du carnet de F4GLD.

@pytest.mark.parametrize('call,attendu', [
    ('IQ0FP/IT9', 'Sicily'),           # la Sicile est une entite DXCC a part
    ('IQ5QO/IM0', 'Sardinia'),         # la Sardaigne aussi
    ('IT9IMJ/I', 'Italy'),             # un Sicilien depuis la peninsule
    ('RA1QQ/P3', 'Cyprus'),
    ('VK2ZK/P4', 'Aruba'),
])
def test_LE_LIEU_EN_SUFFIXE_est_bien_retenu(call, attendu):
    """La famille que casserait une regle « le premier morceau gagne ». La
    Sicile et la Sardaigne comptent separement de l'Italie au DXCC : les
    confondre fausse le comptage d'entites ET le score en concours."""
    assert pays(call) == attendu


# ─── Les modificateurs ne sont pas des lieux ─────────────────────────────────

@pytest.mark.parametrize('call', ['F4GLD/P', 'F4GLD/M', 'F4GLD/QRP', 'F4GLD/8',
                                  'DL/G4OBK/P', 'DL/OE2GXL/P'])
def test_un_modificateur_ne_deplace_pas_la_station(call):
    """/P, /M, /QRP et un chiffre seul disent COMMENT on emet, pas D'OU. Sans
    cette mise a l'ecart, /P (Portugal ? non : portable) et /M deraillereaient."""
    attendu = pays(call.split('/')[0]) if not call.startswith('DL/') else 'Fed. Rep. of Germany'
    assert pays(call) == attendu


def test_POURQUOI_le_tri_par_LONGUEUR_et_pas_la_position():
    """Verrouille la RAISON de la regle. Si un jour _lookup_compute prenait le
    premier morceau au lieu du plus court, ce test tomberait tout seul — et les
    QSO en suffixe de lieu basculeraient silencieusement dans le mauvais pays.
    """
    # Meme paire de pays, dans les DEUX ordres : la position ne decide rien,
    # seule la longueur decide.
    assert pays('P4/VK2ZK') == 'Aruba'
    assert pays('VK2ZK/P4') == 'Aruba'
    assert pays('I/IT9IMJ') == 'Italy'
    assert pays('IT9IMJ/I') == 'Italy'


def test_un_indicatif_sans_barre_reste_inchange():
    assert pays('F4GLD') == 'France'
    assert pays('IT9IMJ') == 'Sicily'


def test_aucune_barre_ne_fait_lever_d_exception():
    for bizarre in ('/', '//', 'F4GLD/', '/F4GLD', 'F4GLD//P', '', None):
        dxcc.lookup(bizarre)   # ne doit jamais lever
