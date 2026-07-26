# -*- coding: utf-8 -*-
"""Les points ne s'affichent que si un concours est RÉELLEMENT sélectionné.

Sans concours (mode 'simple', ou mode concours avant d'avoir choisi un
concours), le moteur retombe sur le préréglage 'km' de REF_RPH et produit des
points 1 pt/km : arithmétiquement justes, mais qu'aucun règlement ne compte.
Les afficher fait croire à un score — c'est le défaut signalé sur la page
CHASSE (« 243 pts · 170 pays » en logbook simple).

Ces tests figent la table de vérité de contest_actif() et la présence du
drapeau dans les charges utiles consommées par les pages. Le logbook, lui,
totalise côté client : il embarque un MIROIR de la même règle en JS
(contestActif() dans logx_logbook.js) — le dernier test vérifie que ce miroir
existe toujours et teste bien les deux mêmes conditions.
"""
import os
import re
import sys

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CONCOURS not in sys.path:
    sys.path.insert(0, CONCOURS)

from logx_storage import contest_actif  # noqa: E402


# ─── Table de vérité ────────────────────────────────────────────────────────
# (config, attendu, description) — le cas 'simple avec un concours resté en
# config' est le vrai piège : la config PORTE un concours, mais le mode dit
# que ce log est un journal personnel, donc aucun score.
CAS = [
    ({'usage_mode': 'simple', 'contest': 'CQ_WW_SSB'}, False,
     "mode simple, un concours traîne encore dans la config"),
    ({'usage_mode': 'simple', 'contest': ''}, False,
     "mode simple sans concours"),
    ({'usage_mode': 'contest', 'contest': ''}, False,
     "mode concours mais aucun concours choisi"),
    ({'usage_mode': 'contest'}, False,
     "mode concours, clé 'contest' absente"),
    ({'usage_mode': 'contest', 'contest': '   '}, False,
     "concours réduit à des espaces"),
    ({'usage_mode': 'contest', 'contest': 'CQ_WW_SSB'}, True,
     "mode concours avec un concours choisi"),
    ({'contest': 'REF_RPH'}, True,
     "usage_mode absent = mode concours par défaut"),
    ({}, False, "config vide"),
    (None, False, "config None"),
]


@pytest.mark.parametrize('cfg,attendu,description',
                         CAS, ids=[c[2] for c in CAS])
def test_contest_actif_table_de_verite(cfg, attendu, description):
    assert contest_actif(cfg) is attendu, description


def test_contest_actif_renvoie_un_vrai_booleen():
    """Sérialisé tel quel en JSON vers les pages : doit être True/False, pas
    la chaîne de portée ('' / 'CQ_WW_SSB_2026') dont il dérive."""
    assert contest_actif({'usage_mode': 'contest', 'contest': 'CQ_WW_SSB'}) is True
    assert contest_actif({'usage_mode': 'simple', 'contest': 'CQ_WW_SSB'}) is False


def test_meta_des_spots_classes_porte_le_drapeau():
    """CHASSE et le panneau détaché lisent meta.contest_actif — sans lui, ils
    retomberaient sur l'affichage de points (comportement d'avant le correctif)."""
    from logx_scoring import build_ranked_spots

    cfg_sans = {'usage_mode': 'simple', 'contest': 'REF_RPH',
                'callsign': 'F4GLD', 'locator': 'JN18AA'}
    cfg_avec = dict(cfg_sans, usage_mode='contest')

    _, meta_sans = build_ranked_spots({}, {}, cfg_sans)
    _, meta_avec = build_ranked_spots({}, {}, cfg_avec)

    assert meta_sans['contest_actif'] is False
    assert meta_avec['contest_actif'] is True


def test_miroir_javascript_du_logbook_teste_les_deux_conditions():
    """Le logbook totalise côté client : sa fonction contestActif() duplique
    la règle. Si quelqu'un la simplifie (par ex. en ne testant plus que
    usage_mode), le mode concours SANS concours choisi réafficherait un score
    calculé sur le repli 1 pt/km. On vérifie que les deux conditions y sont."""
    chemin = os.path.join(CONCOURS, 'logx_logbook.js')
    with open(chemin, encoding='utf-8') as f:
        source = f.read()

    m = re.search(r'function contestActif\(\)\s*\{(.*?)\n\}', source, re.S)
    assert m, "contestActif() a disparu de logx_logbook.js"
    corps = m.group(1)

    assert "usage_mode" in corps, "le miroir ne teste plus le mode d'utilisation"
    assert "'simple'" in corps, "le miroir ne compare plus au mode 'simple'"
    assert "contest" in corps, "le miroir ne teste plus le concours sélectionné"


def test_pages_ne_montrent_plus_de_points_sans_condition():
    """Garde-fou de non-régression : les emplacements corrigés doivent rester
    conditionnés. Une réécriture qui réintroduirait un '+ pts' inconditionnel
    sur CHASSE ou le panneau détaché ferait réapparaître le défaut signalé."""
    for fichier, marqueur in [('logx_chasse.html', 'contestActif'),
                              ('logx_panel.html', 'contestActif'),
                              ('logx_carte.html', 'contestActif')]:
        with open(os.path.join(CONCOURS, fichier), encoding='utf-8') as f:
            contenu = f.read()
        assert marqueur in contenu, f"{fichier} n'applique plus la condition"
