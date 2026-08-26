# -*- coding: utf-8 -*-
"""Bandeau accueil — câblage page (structure, pas mannequin).

Les tests test_bandeaux_defs.py couvrent le MOTEUR (dxped/propag). Ici on
vérifie que la page d'accueil est réellement BRANCHÉE dessus : scripts chargés
dans le bon ordre, conteneur présent, et le chemin d'appel _grille -> rendu.
Une régression silencieuse (script retiré, appel supprimé) doit rougir."""
import os
import re

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML = os.path.join(CONCOURS, 'logx_accueil.html')
JS = os.path.join(CONCOURS, 'logx_accueil.js')


def _lire(p):
    with open(p, encoding='utf-8') as f:
        return f.read()


def test_html_charge_framework_et_defs_avant_accueil():
    h = _lire(HTML)
    i_fw = h.find('src="logx_bandeaux.js"')
    i_defs = h.find('src="logx_bandeaux_defs.js"')
    i_acc = h.find('src="logx_accueil.js"')
    assert i_fw != -1 and i_defs != -1 and i_acc != -1        # les 3 scripts présents
    # Ordre impératif : le framework définit window.LogxBandeaux, les defs
    # l'alimentent, puis accueil.js s'en sert -> framework et defs AVANT accueil.
    assert i_fw < i_acc and i_defs < i_acc


def test_html_a_le_conteneur_bandeau():
    h = _lire(HTML)
    assert re.search(r'id="bandeaux"', h)


def test_grille_declenche_le_chargement_des_bandeaux():
    """_chargerBandeaux doit être APPELÉ par _grille (pas seulement défini) —
    sinon le bandeau ne s'affiche jamais bien que tout le reste existe."""
    js = _lire(JS)
    m = re.search(r'function _grille\(\).*?\n\}', js, re.S)
    assert m, "fonction _grille introuvable"
    assert '_chargerBandeaux(' in m.group(0)               # appel DANS _grille


def test_chargement_utilise_le_moteur_et_les_deux_flux():
    js = _lire(JS)
    m = re.search(r'function _chargerBandeaux\(\).*?\n\}', js, re.S)
    assert m, "fonction _chargerBandeaux introuvable"
    corps = m.group(0)
    # Rend via le framework, avec les DEUX bandeaux universels de l'accueil.
    assert 'rendreTicker' in corps
    assert "'dxped'" in corps and "'propag'" in corps
    # Alimenté par les deux vrais endpoints live.
    assert '/data/dxpeditions_active' in corps
    assert '/data/propagation' in corps
