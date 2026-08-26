# -*- coding: utf-8 -*-
"""Panneau « Objectifs de chasse » sur la page CHASSE (option b). Propriété
CRITIQUE : les clés proposées à l'opérateur doivent correspondre EXACTEMENT à
celles du profil serveur (logx_operator_goals.CLES) — sinon une case cochée ne
piloterait aucun crédit. OBJECTIFS_DEF extrait du fichier livré et exécuté en
V8 ; le câblage fetch GET/POST est vérifié en grep."""
import json
import os
import re

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHASSE = os.path.join(CONCOURS, 'logx_chasse.html')
py_mini_racer = pytest.importorskip('py_mini_racer')


def _lire():
    with open(CHASSE, encoding='utf-8') as f:
        return f.read()


def test_cles_ui_alignees_sur_le_serveur():
    src = _lire()
    m = re.search(r'const OBJECTIFS_DEF = \[.*?\];', src, re.S)
    assert m, 'OBJECTIFS_DEF introuvable'
    ctx = py_mini_racer.MiniRacer()
    ctx.eval(m.group(0))
    cles = json.loads(ctx.eval("JSON.stringify(OBJECTIFS_DEF.map(function(o){return o.cle}))"))
    import sys
    if CONCOURS not in sys.path:
        sys.path.insert(0, CONCOURS)
    import logx_operator_goals as og
    assert set(cles) == set(og.CLES), 'les clés UI ne correspondent pas au profil serveur'
    assert len(cles) == len(og.CLES)             # pas de doublon


def test_panneau_et_cablage_present():
    src = _lire()
    assert 'id="objectifsList"' in src
    # lecture au chargement + écriture au changement, sur l'endpoint dédié
    assert "fetch('/data/operator_goals')" in src            # GET
    assert re.search(r"fetch\('/data/operator_goals',\s*\{[^}]*method:\s*'POST'", src), \
        'pas de POST vers /data/operator_goals'
    # un changement doit rafraîchir la liste des spots (effet immédiat)
    m = re.search(r'function enregistrerObjectifs\(.*?\n  \}', src, re.S)
    assert m and 'renderSpots(' in m.group(0), \
        'enregistrer les objectifs ne rafraîchit pas les spots'


def test_charge_au_demarrage():
    src = _lire()
    # chargerObjectifs doit être appelé à l'init (pas seulement défini)
    assert src.count('chargerObjectifs(') >= 2   # définition + au moins un appel
