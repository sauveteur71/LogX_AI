# -*- coding: utf-8 -*-
"""Fusion incr. 4b+4c : la vue chasse de l'activité monte les panneaux
d'activation (POTA/SOTA/WWFF/WCA/DXpéditions) + la need-list. On fige la
STRUCTURE synchrone (conteneurs créés au bon endroit) ; le remplissage async
(fetch->render*) est délégué au module, testé ailleurs. Exécute le vrai
logx_accueil.js en V8.
"""
import pytest

py_mini_racer = pytest.importorskip(
    'py_mini_racer', reason='py_mini_racer absent — test JS réel ignoré')

from test_accueil_activite import _make_ctx

STUB_ROLE = (
    "var _rr={setRole:function(){}, roleConfig:function(r){"
    "return {chasse:(r==='chasse'||r==='mixte'), portable:(r==='portable'||r==='mixte')};}};"
    "var LogxXotaRole=_rr; window.LogxXotaRole=_rr;"
)


def test_role_chasse_monte_les_panneaux_activation():
    ctx = _make_ctx()
    ctx.eval(STUB_ROLE)
    ctx.eval("_choisirRoleXota('chasse');")
    html = ctx.eval("document.getElementById('ciblesChasse').innerHTML")
    for cid in ('panPota', 'panSota', 'panWwff', 'panWca', 'panDx', 'ckNeedList', 'xotaQsyStatus'):
        assert cid in html, cid
    assert 'POTA' in html and 'SOTA' in html and 'WWFF' in html
    assert 'WCA' in html and 'DXp' in html


def test_expose_qsyto_et_pointto():
    """qsyTo/pointTo (fusion incr. 4d) doivent être des fonctions globales,
    comme dans logx_chasse.html — c'est elles que les boutons QSY/rotor
    rendus par renderNeedList appellent via onclick."""
    ctx = _make_ctx()
    assert ctx.eval('typeof qsyTo') == 'function'
    assert ctx.eval('typeof pointTo') == 'function'


def test_role_portable_pur_ne_monte_pas_les_panneaux():
    ctx = _make_ctx()
    ctx.eval(STUB_ROLE)
    ctx.eval("_choisirRoleXota('portable');")
    # portable pur -> navigation logbook, pas de panneaux chasse montés
    assert ctx.eval('__redirected') == 'logx_logbook.html'
    assert 'panPota' not in ctx.eval("document.getElementById('ciblesChasse').innerHTML")
