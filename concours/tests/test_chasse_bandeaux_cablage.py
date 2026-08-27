# -*- coding: utf-8 -*-
"""Bandeau défilant sur CHASSE — câblage page (structure, pas mannequin).

Le MOTEUR (rendreTicker, dxped/propag) et le DRIVER (⚙ on/off, fetch-aware) sont
testés ailleurs (test_bandeaux*.py, test_bandeaux_driver.py). Ici on vérifie que
CHASSE est réellement BRANCHÉE : framework+defs+driver chargés AVANT le script de
page, conteneur présent, appel brancher avec les bons bandeaux/flux, ET le clic
« fiche » sur un item actif (indépendant du driver). Une régression silencieuse
doit rougir.
"""
import os
import re

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML = os.path.join(CONCOURS, 'logx_chasse.html')


def _lire():
    with open(HTML, encoding='utf-8') as f:
        return f.read()


def test_charge_framework_defs_et_driver_avant_le_script_de_page():
    h = _lire()
    i_fw = h.find('src="logx_bandeaux.js"')
    i_defs = h.find('src="logx_bandeaux_defs.js"')
    i_drv = h.find('src="logx_bandeaux_driver.js"')
    assert i_fw != -1 and i_defs != -1 and i_drv != -1       # framework + defs + driver
    i_inline = h.rfind('<script>')
    assert i_inline != -1
    assert i_fw < i_inline and i_defs < i_inline and i_drv < i_inline


def test_a_le_conteneur_bandeau():
    assert re.search(r'id="bandeaux"', _lire())


def test_branche_via_le_driver_avec_les_deux_flux():
    h = _lire()
    m = re.search(r'LogxBandeauxDriver\.brancher\(\{.*?\}\);', h, re.S)
    assert m, "appel brancher introuvable"
    appel = m.group(0)
    assert "activite: 'chasse'" in appel
    assert "'dxped'" in appel and "'propag'" in appel
    assert '/data/dxpeditions_active' in appel
    assert '/data/propagation' in appel


def test_clic_item_actif_ouvre_une_fiche():
    """Un item ACTIF du bandeau (data-fiche) ouvre une fiche popup au clic :
    handler de clic DÉLÉGUÉ sur #bandeaux (indépendant du driver, robuste aux
    re-rendus) + openFicheModal agrégeant l'info live du cluster, le nom
    (/calldb/lookup) et un lien direct QRZ.com."""
    h = _lire()
    assert 'function openFicheModal' in h
    assert "addEventListener('click'" in h                  # clic délégué
    assert 'rcb-item' in h and 'data-fiche' in h            # cible les items actifs
    assert 'closest' in h                                   # remonte au <a> depuis la cible
    assert 'qrz.com/db/' in h                               # « toutes les infos QRZ.com »
    assert '/calldb/lookup/' in h                           # nom de l'opérateur
    assert 'closeFiche' in h                                # fermeture du popup
