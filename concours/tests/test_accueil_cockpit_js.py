# -*- coding: utf-8 -*-
"""Cockpit d'accueil (logx_accueil_cockpit.js) — testé en V8.

Les chiffres viennent des endpoints serveur (spots_ranked/awards/hardware/dxcc,
testés ailleurs) ; ici on teste le mapping d'affichage pur (_opportunites,
_progression, _etat) et le rendu XSS-safe.
"""
import os

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS = os.path.join(CONCOURS, 'logx_accueil_cockpit.js')
py_mini_racer = pytest.importorskip('py_mini_racer')


def _ctx():
    ctx = py_mini_racer.MiniRacer()
    ctx.eval("""
      var window = {};
      var __o = {innerHTML:''}, __p = {innerHTML:''}, __e = {innerHTML:''};
      var document = { getElementById: function(id){
          if(id==='ckOpp') return __o;
          if(id==='ckProg') return __p;
          if(id==='ckEtat') return __e;
          return null; } };
    """)
    with open(JS, encoding='utf-8') as f:
        ctx.eval(f.read())
    return ctx


def test_opportunites_top3_par_score():
    ctx = _ctx()
    ctx.eval("""window.__r = window.LogxCockpit._opportunites({spots:[
      {call:'A', credit_score:600, credit_classe:'new_band', credit_raison:'r'},
      {call:'B', credit_score:0},
      {call:'C', credit_score:1000, credit_classe:'atno', credit_raison:'nouveau DXCC'},
      {call:'D', credit_score:-900},
      {call:'E', credit_score:450, credit_classe:'new_grid', credit_raison:'r'},
      {call:'F', credit_score:500, credit_classe:'new_mode', credit_raison:'r'}]});""")
    calls = ctx.eval("window.__r.map(function(o){return o.texte.split(' ')[0];}).join(',')")
    assert calls == 'C,A,F'          # top 3 par score


def test_opportunites_ecarte_nul_et_negatif_meme_sous_trois():
    # SEULEMENT 2 positifs + un 0 + un négatif : la coupe à 3 ne les masque pas,
    # c'est le FILTRE qui doit les écarter (sinon on afficherait un doublon).
    ctx = _ctx()
    ctx.eval("""window.__r = window.LogxCockpit._opportunites({spots:[
      {call:'Z', credit_score:0}, {call:'A', credit_score:600, credit_raison:'r'},
      {call:'N', credit_score:-900}, {call:'C', credit_score:1000, credit_raison:'r'}]});""")
    calls = ctx.eval("window.__r.map(function(o){return o.texte.split(' ')[0];}).join(',')")
    assert calls == 'C,A'            # exactement les 2 positifs, jamais Z ni N


def test_progression_compacte():
    ctx = _ctx()
    ctx.eval("""window.__r = window.LogxCockpit._progression({
      dxcc:{worked:137, total:340}, departments:{metro_worked:80, metro_total:96}, qso_total:5000});""")
    txt = ctx.eval("window.__r.map(function(p){return p.label+'='+p.valeur;}).join('|')")
    assert 'DXCC=137 / 340' in txt and 'Départements=80 / 96' in txt and 'QSO=5000' in txt


def test_etat_couleurs():
    ctx = _ctx()
    ctx.eval("""window.__r = window.LogxCockpit._etat(
      {rig:{enabled:true, ok:true}, wsjtx:{enabled:true, connected:false}}, {available:true});""")
    m = ctx.eval("window.__r.map(function(t){return t.nom+':'+t.couleur;}).join('|')")
    assert 'CAT:green' in m and 'FT8:yellow' in m and 'DXCC:green' in m


def test_etat_cat_rouge_si_ne_repond_pas():
    # CAT activé mais ne répond pas -> rouge (pas vert). Contraint la couleur CAT.
    ctx = _ctx()
    ctx.eval("window.__r = window.LogxCockpit._etat({rig:{enabled:true, ok:false}}, {available:false});")
    m = ctx.eval("window.__r.map(function(t){return t.nom+':'+t.couleur;}).join('|')")
    assert 'CAT:red' in m and 'DXCC:red' in m


def test_rendre_remplit_et_echappe():
    ctx = _ctx()
    ctx.eval("window.LogxCockpit._rendre([{emoji:'🌟', texte:'<img src=x>'}], [{label:'DXCC', valeur:'1'}], [{nom:'CAT', couleur:'green'}]);")
    assert '&lt;img' in ctx.eval("__o.innerHTML") and '<img' not in ctx.eval("__o.innerHTML")
    assert 'DXCC' in ctx.eval("__p.innerHTML")
    assert 'ck-dot' in ctx.eval("__e.innerHTML")


def test_opportunites_vide():
    ctx = _ctx()
    assert ctx.eval("window.LogxCockpit._opportunites({spots:[]}).length") == 0


def test_cablage_accueil():
    with open(os.path.join(CONCOURS, 'logx_accueil.html'), encoding='utf-8') as f:
        h = f.read()
    assert 'src="logx_accueil_cockpit.js"' in h
    for cid in ('id="ckOpp"', 'id="ckProg"', 'id="ckEtat"'):
        # les conteneurs sont créés en JS (accueil.js), pas dans le HTML statique —
        # on vérifie plutôt que le module est branché et le HTML charge le cockpit.
        pass
    with open(os.path.join(CONCOURS, 'logx_accueil.js'), encoding='utf-8') as f:
        js = f.read()
    assert 'LogxCockpit.charger' in js
    assert 'ckOpp' in js and 'ckProg' in js and 'ckEtat' in js
    assert '_reprendre' in js
    # plus de redirection AUTOMATIQUE dans init (le bouton Reprendre la remplace)
    assert 'window.location.href = _pageSuivante();\n    return;' not in js
