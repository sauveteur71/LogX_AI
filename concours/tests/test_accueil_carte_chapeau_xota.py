# -*- coding: utf-8 -*-
"""Activité « activation portable » = CARTE CHAPEAU (décision F4GLD D1).

Cliquer la carte ne part PAS tout de suite vers CONFIG/LOGBOOK comme les autres
activités : elle révèle le sous-choix de rôle (chasse / activer / mixte) DANS le
flux de l'activité. Les tuiles de rôle ne sont donc plus « toujours visibles »
sur l'accueil — elles apparaissent au clic sur la carte.

Exécute le VRAI logx_accueil.js en V8 (harnais de test_accueil_activite).
"""
import pytest

py_mini_racer = pytest.importorskip(
    'py_mini_racer', reason='py_mini_racer absent — test JS réel ignoré')

from test_accueil_activite import _make_ctx

# Stub minimal du module de rôle. Le code réel lit à la fois `window.LogxXotaRole`
# (garde) et `LogxXotaRole` en global (en navigateur window EST le global) ; le
# harnais V8 a un `window` séparé, on définit donc les deux.
STUB = ("var _r={getRole:function(){return 'mixte';},"
        "ROLES:[{id:'chasse',label:'Je chasse',hint:'x',icone:'i'},"
        "{id:'portable',label:'Jactive',hint:'x',icone:'i'},"
        "{id:'mixte',label:'Mixte',hint:'x',icone:'i'}]};"
        "var LogxXotaRole=_r; window.LogxXotaRole=_r;")


def test_carte_chapeau_revele_les_roles_sans_rediriger():
    ctx = _make_ctx()
    ctx.eval(STUB)
    ctx.eval("choisirActivite('iota_pota');")
    assert ctx.eval("localStorage.getItem('logx_activity')") == 'iota_pota'
    assert ctx.eval('__redirected') is None            # ne part pas : carte chapeau
    html = ctx.eval("document.getElementById('xotaRoleAccueil').innerHTML")
    assert 'xota-acc-tile' in html                     # les 3 rôles révélés


def test_pas_de_roles_toujours_visibles_au_chargement():
    """Carte chapeau : les rôles n'apparaissent QU'au clic, pas d'office."""
    ctx = _make_ctx()
    ctx.eval(STUB)
    html = ctx.eval("document.getElementById('xotaRoleAccueil').innerHTML")
    assert 'xota-acc-tile' not in html                 # rien tant qu'on n'a pas cliqué la carte


def test_autre_activite_redirige_directement():
    ctx = _make_ctx()
    ctx.eval("choisirActivite('normal');")
    assert ctx.eval('__redirected') == 'logx_configuration.html'
