# -*- coding: utf-8 -*-
"""Câblage de la grille départements dans le LOGBOOK. La logique pure (liste
INSEE, règle d'affichage) est couverte par test_dept_grid ; ici on vérifie la
présence + les invariants : la grille remplit le champ REÇU, et n'est montrée
que pour un échange-département (jamais dans une série VHF/UHF).
"""
import os
import re

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _lire(nom):
    with open(os.path.join(BASE, nom), encoding='utf-8') as f:
        return f.read()


def test_inclusion_et_conteneur():
    html = _lire('logx_logbook.html')
    assert 'logx_dept_grid.js' in html
    assert 'id="deptGrid"' in html and 'id="deptGridWrap"' in html


def test_grille_visible_seulement_si_echange_departement():
    js = _lire('logx_logbook.js')
    # _majDeptGrid gate l'affichage sur doitAfficher(currentExchange.label_r)
    assert re.search(
        r"wrap\.style\.display = LogxDeptGrid\.doitAfficher\(currentExchange\.label_r\)", js)
    # appelée à chaque changement d'échange
    assert '_majDeptGrid();' in js
    m = re.search(r'function applyExchangeFormat\(.*?\n\}', js, re.S)
    assert m and '_majDeptGrid()' in m.group(0), "grille non rafraîchie au change d'échange"


def test_clic_remplit_le_champ_recu_pas_une_serie():
    js = _lire('logx_logbook.js')
    m = re.search(r'function pickDept\(.*?\n\}', js, re.S)
    assert m, 'pickDept introuvable'
    corps = m.group(0)
    # remplit bien le champ REÇU (#inputNumRcvd), lu par dept_from_exchange
    assert "getElementById('inputNumRcvd')" in corps
    assert 'fR.value = code' in corps
    # met à jour la zone/multiplicateur après le clic
    assert 'checkExchangeZone' in corps
