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


def test_brancher_sur_lactivite_courante_avec_les_deux_flux():
    """Adaptation : le LOGBOOK se cale sur l'activité courante (localStorage
    logx_activity), pas un bucket 'logbook' fixe."""
    h = _lire()
    assert "localStorage.getItem('logx_activity')" in h          # lit l'activité courante
    m = re.search(r'LogxBandeauxDriver\.brancher\(\{.*?\}\);', h, re.S)
    assert m, "appel brancher introuvable"
    appel = m.group(0)
    assert 'activite: _actLog' in appel                          # activité dynamique
    assert "'dxped'" in appel and "'propag'" in appel
    assert '/data/dxpeditions_active' in appel
    assert '/data/propagation' in appel


def test_spots_disponible_mais_off_par_defaut():
    """Spots DX est proposé (chip du ⚙) mais PAS actif par défaut sur le chemin
    critique (opt-in) ; fetch-aware -> /data/spots_ranked (lourd) n'est appelé
    que si l'opérateur l'active."""
    h = _lire()
    m = re.search(r'LogxBandeauxDriver\.brancher\(\{.*?\}\);', h, re.S)
    appel = m.group(0)
    assert "'spots'" in appel and '/data/spots_ranked' in appel   # disponible
    assert 'besoins' in appel                                     # fetch-aware déclaré
    # défauts (par activité) = dxped+propag SANS spots, quelle que soit l'activité
    d = re.search(r"_defLog\[_actLog\]\s*=\s*\[([^\]]*)\]", h)
    assert d and 'dxped' in d.group(1) and 'propag' in d.group(1) and 'spots' not in d.group(1)


def test_mults_deploye_concours_seulement():
    """Bandeau MULTS : proposé (ids + besoins) mais actif par défaut UNIQUEMENT
    en concours ; le driver l'écarte des autres activités (contextes)."""
    h = _lire()
    m = re.search(r'LogxBandeauxDriver\.brancher\(\{.*?\}\);', h, re.S)
    appel = m.group(0)
    assert "'mults'" in appel                                    # dans les ids
    assert re.search(r"mults:\s*\['spots_ranked'\]", appel)      # fetch-aware
    # ON par défaut seulement si l'activité courante est le concours
    assert re.search(r"_actLog\s*===\s*'concours'.*mults", h, re.S)
