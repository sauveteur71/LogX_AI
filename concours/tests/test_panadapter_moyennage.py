# -*- coding: utf-8 -*-
"""Panadapter : moyennage spectral (video averaging). majMoyenne extrait du
fichier LIVRÉ et exécuté en V8 : moyenne exponentielle qui converge vers le
signal (abaisse le plancher de bruit, fait ressortir une porteuse faible et
stable). Source-agnostique : appliqué en place à dataArray avant les 3 tracés
(audio / CI-V / TCI)."""
import json
import os
import re

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PANADAPTER = os.path.join(CONCOURS, 'logx_panadapter.html')
py_mini_racer = pytest.importorskip('py_mini_racer')


def _lire():
    with open(PANADAPTER, encoding='utf-8') as f:
        return f.read()


def _ctx():
    m = re.search(r'  function majMoyenne\(.*?\n  \}', _lire(), re.S)
    assert m, 'majMoyenne introuvable'
    ctx = py_mini_racer.MiniRacer()
    ctx.eval(m.group(0))
    return ctx


def test_ema_converge_vers_le_signal():
    ctx = _ctx()
    # avg=[0,0], data=[100,200], alpha=0.5 -> avg += 0.5*(data-avg) = [50,100]
    assert json.loads(ctx.eval("JSON.stringify(majMoyenne([0,0],[100,200],0.5))")) == [50, 100]
    # une 2e trame identique rapproche encore : [50,100] -> [75,150]
    assert json.loads(ctx.eval("JSON.stringify(majMoyenne([50,100],[100,200],0.5))")) == [75, 150]


def test_alpha_1_suit_exactement_le_signal():
    ctx = _ctx()
    # alpha=1 : aucun lissage, la moyenne = la trame courante
    assert json.loads(ctx.eval("JSON.stringify(majMoyenne([10],[80],1))")) == [80]


def test_cable_dans_les_trois_chemins_et_selecteur():
    src = _lire()
    # appliquerMoyenne utilise majMoyenne et écrit dans dataArray
    m = re.search(r'function appliquerMoyenne\(.*?\n  \}', src, re.S)
    assert m, 'appliquerMoyenne introuvable'
    corps = m.group(0)
    assert 'majMoyenne(' in corps and 'moyArr' in corps and 'moyN' in corps
    # appliqué AVANT le tracé dans les 3 sources (audio boucle + CI-V + TCI) :
    # autant d'appels que de paires dessinerSpectre()/dessinerWaterfall().
    assert src.count('appliquerMoyenne()') >= 3, 'moyennage pas câblé sur les 3 sources'
    # chaque appel précède IMMÉDIATEMENT un tracé de spectre (donc lissage
    # appliqué avant spectre ET waterfall qui le suit) — indentation tolérée.
    couples = re.findall(r'appliquerMoyenne\(\);\s*\n\s*dessinerSpectre\(\);', src)
    assert len(couples) >= 3, 'appliquerMoyenne pas placé juste avant dessinerSpectre'
    # sélecteur + persistance
    assert 'id="paMoy"' in src
    assert "setItem('rc_pa_moy'" in src
