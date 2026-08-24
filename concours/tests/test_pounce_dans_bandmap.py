# -*- coding: utf-8 -*-
"""WAIT & POUNCE rattaché au band map + masquable via AFFICHAGE (F4GLD 24/08).

Le panneau #pouncePanel encombrait la colonne de saisie (défilement). Il agit
sur les spots du band map (alerte, clic pour armer) — il vit donc désormais DANS
#bandmapPanel, et il est déclaré dans STATUSBAR_TOGGLES pour être masquable au
même titre que le band map. Ces tests figent les deux propriétés."""
import os
import re

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML = open(os.path.join(BASE, 'logx_logbook.html'), encoding='utf-8').read()
STATUSBAR = open(os.path.join(BASE, 'logx_statusbar.js'), encoding='utf-8').read()


def _bloc_bandmap():
    """Contenu de #bandmapPanel : de son ouverture jusqu'au panneau suivant
    (#log-panel « LOG TABLE »), qui suit immédiatement sa fermeture. Borne
    fiable, sans comptage de balises."""
    i = HTML.index('id="bandmapPanel"')
    start = HTML.rindex('<div', 0, i)
    fin = HTML.index('<div class="log-panel">', start)
    return HTML[start:fin]


def test_pounce_est_dans_le_band_map():
    bloc = _bloc_bandmap()
    assert 'id="pouncePanel"' in bloc, 'WAIT & POUNCE doit être DANS #bandmapPanel'


def test_pounce_une_seule_occurrence():
    # pas de doublon laissé dans la colonne de saisie après le déplacement.
    assert HTML.count('id="pouncePanel"') == 1


def test_pounce_masquable_via_affichage():
    # déclaré dans STATUSBAR_TOGGLES (menu AFFICHAGE), en 'layered' comme le
    # band map (sa propre logique FT8 pilote aussi la visibilité).
    m = re.search(r"\{id:\s*'pouncePanel'[^}]*\}", STATUSBAR)
    assert m, "pouncePanel absent de STATUSBAR_TOGGLES"
    assert "layered: true" in m.group(0)


def test_band_map_masquable_via_affichage():
    # le band map reste déclaré (le toggle demandé existait déjà).
    assert re.search(r"\{id:\s*'bandmapPanel'[^}]*\}", STATUSBAR)
