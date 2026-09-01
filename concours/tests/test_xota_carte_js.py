# -*- coding: utf-8 -*-
"""Logique pure de la carte de sortie XOTA (logx_xota_carte.js) — testée en V8.

Le dessin canvas et l'export PNG ne sont pas testables en unitaire (comme le
DOM) ; ces tests couvrent la logique PURE : projection, filtre de sortie, choix
de position (locator précis vs indicatif approximatif), stats du bandeau.
"""
import os

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS = os.path.join(CONCOURS, 'logx_xota_carte.js')
py_mini_racer = pytest.importorskip('py_mini_racer')


def _ctx():
    ctx = py_mini_racer.MiniRacer()
    ctx.eval("var window = {};")
    with open(JS, encoding='utf-8') as f:
        ctx.eval(f.read())
    return ctx


def test_projection_equirectangulaire_coins_et_centre():
    ctx = _ctx()
    # (0,0) au centre ; (90,-180) coin haut-gauche ; (-90,180) coin bas-droit.
    assert ctx.eval("var p=window.LogxCarteSortie.projeterEquirect(0,0,360,180); p.x") == 180
    assert ctx.eval("window.LogxCarteSortie.projeterEquirect(0,0,360,180).y") == 90
    assert ctx.eval("window.LogxCarteSortie.projeterEquirect(90,-180,360,180).x") == 0
    assert ctx.eval("window.LogxCarteSortie.projeterEquirect(90,-180,360,180).y") == 0
    assert ctx.eval("window.LogxCarteSortie.projeterEquirect(-90,180,360,180).x") == 360
    assert ctx.eval("window.LogxCarteSortie.projeterEquirect(-90,180,360,180).y") == 180


def test_match_sortie_par_my_sig_insensible_casse():
    ctx = _ctx()
    ctx.eval("var M = window.LogxCarteSortie.matchSortie;")
    assert ctx.eval("M({my_sig:'SOTA', my_sig_info:'F/AB-001'}, 'SOTA', 'F/AB-001')") is True
    assert ctx.eval("M({my_sig:'sota', my_sig_info:'f/ab-001'}, 'SOTA', 'F/AB-001')") is True
    # Mauvaise référence, mauvais programme, ou champ absent → False
    assert ctx.eval("M({my_sig:'SOTA', my_sig_info:'F/AB-002'}, 'SOTA', 'F/AB-001')") is False
    assert ctx.eval("M({my_sig:'POTA', my_sig_info:'F/AB-001'}, 'SOTA', 'F/AB-001')") is False
    assert ctx.eval("M({sig:'SOTA', sig_info:'F/AB-001'}, 'SOTA', 'F/AB-001')") is False


def test_position_prefere_le_locator_precis():
    ctx = _ctx()
    ctx.eval("""
      var locR = function(loc){ return loc === 'IO91WM' ? {lat:51.5, lon:-0.1} : null; };
      var dx = {'G4XYZ': {lat:54.0, lon:-2.0, country:'England'}};
      var r = window.LogxCarteSortie.positionStation({call:'G4XYZ', locator:'IO91WM'}, dx, locR);
    """)
    assert ctx.eval("r.approx") is False
    assert ctx.eval("r.lat") == 51.5
    assert ctx.eval("r.source") == 'locator'


def test_position_repli_sur_indicatif_si_pas_de_locator():
    ctx = _ctx()
    ctx.eval("""
      var locR = function(loc){ return null; };
      var dx = {'G4XYZ': {lat:54.0, lon:-2.0, country:'England'}};
      var r = window.LogxCarteSortie.positionStation({call:'g4xyz', locator:''}, dx, locR);
    """)
    assert ctx.eval("r.approx") is True
    assert ctx.eval("r.lat") == 54.0
    assert ctx.eval("r.source") == 'indicatif'


def test_position_null_si_ni_locator_ni_dxcc():
    ctx = _ctx()
    ctx.eval("var r = window.LogxCarteSortie.positionStation({call:'XX9ZZ', locator:''}, {}, function(){return null;});")
    assert ctx.eval("r") is None


def test_stats_pays_distincts_et_bandes_triees_numeriquement():
    ctx = _ctx()
    ctx.eval("""
      var paysDe = function(q){ return q.pays || ''; };
      var qsos = [
        {band:'144', pays:'France'}, {band:'14', pays:'France'},
        {band:'7', pays:'Italie'},   {band:'14', pays:''}];
      var s = window.LogxCarteSortie.statsSortie(qsos, paysDe);
    """)
    assert ctx.eval("s.nQso") == 4
    assert ctx.eval("s.nPays") == 2          # France + Italie ('' non compté)
    # Tri NUMÉRIQUE : 7, 14, 144 (pas 14,144,7 lexical)
    assert ctx.eval("s.bandes.join(',')") == '7,14,144'
