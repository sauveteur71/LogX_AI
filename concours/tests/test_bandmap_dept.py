# -*- coding: utf-8 -*-
"""Band map : les stations spottées dans un DÉPARTEMENT PAS ENCORE FAIT sont
signalées d'une couleur distincte + badge dept (demande F4GLD 25/08), pour
cliquer -> QSY + QSO pré-rempli (bandmapClick, inchangé). Assertions
structurelles (le rendu Leaflet/DOM n'est pas testé unitairement).
"""
import os
import re

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _lire(nom):
    with open(os.path.join(BASE, nom), encoding='utf-8') as f:
        return f.read()


def test_croisement_departements_manquants():
    js = _lire('logx_filtre_spots.js')
    # croise les spots par indicatif avec /departments/targets (dept via cluster/locator)
    assert "fetch('/departments/targets')" in js
    assert '_deptManquantParCall[String(sp.call' in js
    # seulement quand les départements comptent (VHF/UHF ou échange-département)
    assert 'BANDES_THF.indexOf(currentBand)' in js
    assert 'LogxDeptGrid.doitAfficher(currentExchange.label_r)' in js


def test_surbrillance_et_badge_dept():
    js = _lire('logx_filtre_spots.js')
    # classe distincte + badge dept sur la ligne du spot
    assert re.search(r"_deptM \? ' bm-dept-manquant' : ''", js)
    assert 'class="bm-dept"' in js
    html = _lire('logx_logbook.html')
    assert '.bm-spot.bm-dept-manquant' in html and '.bm-dept{' in html


def test_clic_qsy_prerempli_inchange():
    # le clic reste bandmapClick (QSY + pré-remplissage déjà en place) : on n'a
    # fait qu'AJOUTER la surbrillance, sans toucher le comportement du clic.
    js = _lire('logx_filtre_spots.js')
    assert "onclick=\"bandmapClick('${jsCall}',${f},'${modeSpot}')\"" in js


def test_panneau_departements_a_faire():
    """Panneau « départements À FAIRE » sur l'écran contest : dept manquants +
    stations spottées cliquables (QSY + QSO pré-rempli), depuis department_targets
    (déjà fetché). Montré seulement en contexte département."""
    html = _lire('logx_logbook.html')
    assert 'id="deptTodoPanel"' in html and 'id="deptTodoList"' in html
    assert '.dept-todo' in html and '.dt-call' in html
    js = _lire('logx_filtre_spots.js')
    assert 'function _rendreDeptTodo' in js
    assert '_rendreDeptTodo(dt.targets)' in js                 # alimenté par le fetch existant
    # station cliquable -> QSY + pré-rempli (bandmapClick), freq cluster kHz -> MHz
    assert "onclick=\"bandmapClick('${c}',${mhz},'')" in js
    assert '(parseFloat(sp.freq) || 0) / 1000' in js
    # caché hors contexte département
    assert re.search(r"panel\.style\.display = 'none';\s*// hors contexte dept", js)
