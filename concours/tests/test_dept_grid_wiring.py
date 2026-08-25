# -*- coding: utf-8 -*-
"""Câblage de la grille départements dans le LOGBOOK. La logique pure (liste
INSEE, champ cible) est couverte par test_dept_grid ; le score par
test_dept_override. Ici : présence + invariants (la grille remplit le bon champ
selon l'échange/la bande, l'override VHF ne touche jamais la série reçue).
"""
import os
import re

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _lire(nom):
    with open(os.path.join(BASE, nom), encoding='utf-8') as f:
        return f.read()


def test_inclusion_et_conteneurs():
    html = _lire('logx_logbook.html')
    assert 'logx_dept_grid.js' in html
    assert 'id="deptGrid"' in html and 'id="deptGridWrap"' in html
    # champ override VHF/UHF « dept correspondant »
    assert 'id="inputDept"' in html and 'id="inputDeptGroup"' in html


def test_cible_dynamique_selon_echange_et_bande():
    js = _lire('logx_logbook.js')
    # la cible est décidée par champCible(label_r, VHF) — pas un champ codé en dur
    assert 'LogxDeptGrid.champCible(currentExchange.label_r, _deptEstVhf())' in js
    # VHF détectée via la liste canonique BANDES_THF (pas un parsing de fréquence)
    assert re.search(r'BANDES_THF.*indexOf\(currentBand\)', js)
    # rafraîchie au changement d'échange ET de bande
    assert len(re.findall(r'_majDeptGrid\(\)', js)) >= 3


def test_pick_remplit_la_cible_courante_pas_un_champ_fige():
    js = _lire('logx_logbook.js')
    m = re.search(r'function pickDept\(.*?\n\}', js, re.S)
    assert m, 'pickDept introuvable'
    corps = m.group(0)
    assert 'getElementById(_deptCibleId)' in corps and 'f.value = code' in corps
    # checkExchangeZone UNIQUEMENT quand on remplit le champ reçu (échange-dept)
    assert "_deptCibleId === 'inputNumRcvd'" in corps


def test_override_vhf_persiste_et_prime():
    js = _lire('logx_logbook.js')
    # le dept saisi part sur le QSO (champ dept) -> lu par dept_for_qso (serveur)
    assert re.search(r"dept:\s*\(\(document\.getElementById\('inputDept'\)", js)
    # vidé au nouveau contact
    assert re.search(r"getElementById\('inputDept'\); if\(_dp\) _dp\.value = ''", js)


def test_grille_marque_les_departements_travailles():
    """Aide au multiplicateur : la grille estompe les dept déjà travaillés (lecture
    seule /data/departments_worked). Aucune incidence sur le score."""
    html = _lire('logx_logbook.html')
    assert '.dept-cell.fait' in html                        # style « déjà fait »
    js = _lire('logx_logbook.js')
    assert "fetch('/data/departments_worked')" in js        # source lecture seule
    assert 'LogxDeptGrid.marquerTravailles(' in js          # coloration
    # rafraîchi après un QSO loggué (nouveau dept = nouveau mult)
    m = re.search(r'function clearForm\(.*?\n\}', js, re.S)
    assert m and '_rafraichirDeptTravailles()' in m.group(0)
