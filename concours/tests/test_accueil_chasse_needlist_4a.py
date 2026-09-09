# -*- coding: utf-8 -*-
"""Fusion incr. 4a : un rôle qui inclut la CHASSE (chasse/mixte) révèle les
cibles en direct DANS l'activité (pas de navigation) ; le rôle « activer » pur
part au logbook.

Doctrine : le contenu chasse est gâté par le RÔLE (D1) — pas montré d'office.
Le rendu de la need-list lui-même est délégué au module (testé ailleurs) ; ici
on fige le ROUTAGE synchrone (révéler vs naviguer). Exécute le vrai
logx_accueil.js en V8.
"""
import pytest

py_mini_racer = pytest.importorskip(
    'py_mini_racer', reason='py_mini_racer absent — test JS réel ignoré')

from test_accueil_activite import _make_ctx

# Stub du module de rôle (global + window, car le harnais a un window séparé).
# roleConfig reproduit la vraie logique (chasse = chasse|mixte).
STUB_ROLE = (
    "var _rr={setRole:function(){}, roleConfig:function(r){"
    "return {chasse:(r==='chasse'||r==='mixte'), portable:(r==='portable'||r==='mixte')};}};"
    "var LogxXotaRole=_rr; window.LogxXotaRole=_rr;"
)


def test_role_chasse_revele_les_cibles_sans_naviguer():
    ctx = _make_ctx()
    ctx.eval(STUB_ROLE)
    ctx.eval("_choisirRoleXota('chasse');")
    assert ctx.eval('__redirected') is None                       # pas de navigation
    html = ctx.eval("document.getElementById('ciblesChasse').innerHTML")
    assert 'Cibles en direct' in html                             # section révélée


def test_role_mixte_revele_aussi_les_cibles():
    ctx = _make_ctx()
    ctx.eval(STUB_ROLE)
    ctx.eval("_choisirRoleXota('mixte');")
    assert ctx.eval('__redirected') is None
    assert 'Cibles en direct' in ctx.eval("document.getElementById('ciblesChasse').innerHTML")


def test_role_portable_pur_part_au_logbook():
    ctx = _make_ctx()
    ctx.eval(STUB_ROLE)
    ctx.eval("_choisirRoleXota('portable');")
    assert ctx.eval('__redirected') == 'logx_logbook.html'        # activer pur -> logbook
