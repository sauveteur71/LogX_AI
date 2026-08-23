# -*- coding: utf-8 -*-
"""Bouton QSY du hub MODE NUMÉRIQUE (logx_modes_numeriques.html + /freq/digital).

Le bouton (déclenché par l'opérateur, jamais automatique) envoie le poste sur la
fréquence conventionnelle du mode numérique pour la bande choisie, via l'endpoint
existant /rig/qsy. Données sourcées IARU R1 (logx_rigs). Ces tests structurels
vérifient le câblage ; la vérification comportementale complète se fait en
navigateur (pratique du dépôt pour l'UI) + essai supervisé côté radio (CAT).
"""
import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_route_freq_digital_declaree():
    src = open(os.path.join(BASE, 'logx_http.py'), encoding='utf-8').read()
    assert "path == '/freq/digital'" in src, "route GET /freq/digital absente"
    assert 'digital_table()' in src, "l'endpoint doit renvoyer digital_table()"


def test_hub_panneau_qsy_cable():
    src = open(os.path.join(BASE, 'logx_modes_numeriques.html'), encoding='utf-8').read()
    # sélecteurs + bouton
    for anchor in ('id="qsyBand"', 'id="qsyMode"', 'id="qsyGo"', 'qsyAller()'):
        assert anchor in src, "élément QSY manquant : %s" % anchor
    # source des fréquences + endpoint de QSY réutilisé
    assert "fetch('/freq/digital')" in src, "le hub doit charger /freq/digital"
    assert "fetch('/rig/qsy'" in src, "le QSY doit passer par /rig/qsy (endpoint existant)"
    # déclenché par l'opérateur, pas au chargement : pas de qsyAller() auto
    assert 'qsyAller()' in src and 'onclick="qsyAller()"' in src
