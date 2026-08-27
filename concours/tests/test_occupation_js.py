# -*- coding: utf-8 -*-
"""Rendu de la carte d'occupation (logx_occupation.js) — testé en V8 avec un
document stubbé. La logique de fusion/conflits est côté serveur (logx_occupancy,
test_occupancy.py) ; ici on vérifie l'AFFICHAGE : surlignage des recouvrements,
alerte, échappement XSS, état vide.
"""
import os

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS = os.path.join(CONCOURS, 'logx_occupation.js')
py_mini_racer = pytest.importorskip('py_mini_racer')


def _ctx():
    ctx = py_mini_racer.MiniRacer()
    ctx.eval("""
      var window = {};
      var __el = { innerHTML: '' };
      var document = { getElementById: function(id){ return id === 'occupationCorps' ? __el : null; } };
    """)
    with open(JS, encoding='utf-8') as f:
        ctx.eval(f.read())
    return ctx


def test_rendu_surligne_les_conflits_et_alerte():
    ctx = _ctx()
    ctx.eval("""window.LogxOccupation._rendre({
      stations:[{station:'A',call:'TM6KJS',band:'20',mode:'SSB'},
                {station:'B',call:'TM6KJS',band:'20',mode:'SSB'}],
      conflits:[{band:'20',mode:'SSB',stations:['A','B']}]});""")
    html = ctx.eval("__el.innerHTML")
    assert 'occ-conflit' in html          # ligne surlignée
    assert 'recouvrement' in html         # alerte présente
    assert 'TM6KJS' in html


def test_rendu_sans_conflit_pas_dalerte():
    ctx = _ctx()
    ctx.eval("""window.LogxOccupation._rendre({
      stations:[{station:'A',call:'X',band:'20',mode:'SSB'},
                {station:'B',call:'Y',band:'40',mode:'CW'}],
      conflits:[]});""")
    html = ctx.eval("__el.innerHTML")
    assert 'occ-conflit' not in html
    assert 'recouvrement' not in html


def test_rendu_echappe_le_call():
    ctx = _ctx()
    ctx.eval("""window.LogxOccupation._rendre({
      stations:[{station:'A',call:'<img src=x onerror=1>',band:'20',mode:'SSB'}],conflits:[]});""")
    html = ctx.eval("__el.innerHTML")
    assert '<img' not in html and '&lt;img' in html


def test_rendu_vide_attente():
    ctx = _ctx()
    ctx.eval("window.LogxOccupation._rendre({stations:[],conflits:[]});")
    assert 'attente' in ctx.eval("__el.innerHTML").lower()


def test_logbook_cable_la_carte():
    """LOGBOOK charge le module + a le bouton bascule et le panneau (conteneur
    #occupationCorps que _rendre remplit)."""
    with open(os.path.join(CONCOURS, 'logx_logbook.html'), encoding='utf-8') as f:
        h = f.read()
    assert 'src="logx_occupation.js"' in h
    assert 'id="occupationToggle"' in h
    assert 'id="occupationPanel"' in h and 'id="occupationCorps"' in h
    assert 'LogxOccupation.basculer' in h


def test_assistant_detail_recommande_sync_et_actions():
    """Chaque scénario donne un sync conseillé + le bouton carte + le lien config.
    Type inconnu -> vide."""
    ctx = _ctx()
    for t in ('radioclub', 'expedition', 'special'):
        h = ctx.eval("window.LogxOccupation._detailScenario('%s')" % t)
        assert 'Sync conseillé' in h
        assert 'ouvrirCarte' in h and 'logx_configuration' in h
    assert ctx.eval("window.LogxOccupation._detailScenario('inconnu')") == ''


def test_logbook_a_lassistant_de_session():
    with open(os.path.join(CONCOURS, 'logx_logbook.html'), encoding='utf-8') as f:
        h = f.read()
    assert 'id="logPartageOverlay"' in h
    assert 'id="lpChoix"' in h and 'id="lpDetail"' in h
    assert "choisirScenario('radioclub')" in h
    assert "choisirScenario('special')" in h
