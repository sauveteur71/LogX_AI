# -*- coding: utf-8 -*-
"""Bandeau défilant sur LOGBOOK — câblage page (structure, pas mannequin).

LOGBOOK est le chemin critique : le bandeau doit être branché via le driver
partagé (avec ⚙ afficher/masquer), NON-intrusif (bande fine sous la nav, jamais
sur la saisie). Le moteur/driver sont testés ailleurs (test_bandeaux*.py) ; ici
on vérifie le branchement réel : framework+defs+driver chargés AVANT l'appel
brancher, conteneur présent, appel avec les bons bandeaux/flux. Une régression
silencieuse (script retiré, appel supprimé) doit rougir.
"""
import os
import re

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML = os.path.join(CONCOURS, 'logx_logbook.html')


def _lire():
    with open(HTML, encoding='utf-8') as f:
        return f.read()


def test_charge_framework_defs_et_driver_avant_lappel():
    h = _lire()
    i_fw = h.find('src="logx_bandeaux.js"')
    i_defs = h.find('src="logx_bandeaux_defs.js"')
    i_drv = h.find('src="logx_bandeaux_driver.js"')
    i_call = h.find('LogxBandeauxDriver.brancher(')
    assert i_fw != -1 and i_defs != -1 and i_drv != -1 and i_call != -1
    # ordre impératif : les 3 scripts définissent le socle AVANT l'appel.
    assert i_fw < i_call and i_defs < i_call and i_drv < i_call


def test_a_le_conteneur_bandeau():
    assert re.search(r'id="bandeaux"', _lire())


def test_brancher_sur_logbook_avec_les_deux_flux():
    h = _lire()
    m = re.search(r'LogxBandeauxDriver\.brancher\(\{.*?\}\);', h, re.S)
    assert m, "appel brancher introuvable"
    appel = m.group(0)
    assert "activite: 'logbook'" in appel
    assert "'dxped'" in appel and "'propag'" in appel
    assert '/data/dxpeditions_active' in appel
    assert '/data/propagation' in appel
