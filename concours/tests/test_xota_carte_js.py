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


def test_lister_sorties_regroupe_par_programme_et_ref_et_trie_par_date_desc():
    ctx = _ctx()
    ctx.eval("""
      var log = [
        {my_sig:'SOTA', my_sig_info:'F/AB-001', date:'20260810'},
        {my_sig:'sota', my_sig_info:'f/ab-001', date:'20260812'},   // même sortie, casse différente
        {my_sig:'POTA', my_sig_info:'F-1234', date:'20260701'},
        {my_sig:'POTA', my_sig_info:'F-1234', date:'20260705'},
        {sig:'SOTA', sig_info:'F/CD-002', date:'20260901'},         // CHASSÉ (sig, pas my_sig) -> ignoré
        {my_sig:'SOTA', my_sig_info:'', date:'20260101'},           // réf vide -> ignoré
        {my_sig:'', my_sig_info:'F/EF-003', date:'20260101'},       // programme vide -> ignoré
      ];
      var out = window.LogxCarteSortie.listerSorties(log);
    """)
    assert ctx.eval("out.length") == 2
    # La sortie SOTA F/AB-001 a son dernier QSO le 12/08 -> plus récente que
    # POTA F-1234 (05/07) -> arrive en premier.
    assert ctx.eval("out[0].program") == 'SOTA'
    assert ctx.eval("out[0].ref") == 'F/AB-001'
    assert ctx.eval("out[0].count") == 2
    assert ctx.eval("out[0].dateMin") == '20260810'
    assert ctx.eval("out[0].dateMax") == '20260812'
    assert ctx.eval("out[1].program") == 'POTA'
    assert ctx.eval("out[1].ref") == 'F-1234'
    assert ctx.eval("out[1].count") == 2
    assert ctx.eval("out[1].dateMin") == '20260701'
    assert ctx.eval("out[1].dateMax") == '20260705'


def test_lister_sorties_vide_si_aucun_qso_my_sig():
    ctx = _ctx()
    ctx.eval("""
      var log = [{call:'F5XYZ', sig:'SOTA', sig_info:'F/AB-001'}, {call:'F6ABC'}];
      var out = window.LogxCarteSortie.listerSorties(log);
    """)
    assert ctx.eval("out.length") == 0


def test_lister_sorties_sans_date_connue_relegue_en_fin_de_liste():
    ctx = _ctx()
    ctx.eval("""
      var log = [
        {my_sig:'SOTA', my_sig_info:'F/AB-001'},              // pas de date
        {my_sig:'POTA', my_sig_info:'F-9999', date:'20260501'},
      ];
      var out = window.LogxCarteSortie.listerSorties(log);
    """)
    assert ctx.eval("out[0].program") == 'POTA'
    assert ctx.eval("out[1].program") == 'SOTA'
    assert ctx.eval("out[1].dateMin") == ''
    assert ctx.eval("out[1].dateMax") == ''


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
