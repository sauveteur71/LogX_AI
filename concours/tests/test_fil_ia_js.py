# -*- coding: utf-8 -*-
"""Fil IA unifié « Ce que l'IA remarque » (logx_fil_ia.js) — testé en V8.

Le fil AGRÈGE des signaux poussés par les modules sources (opportunités,
validation, après-QSO, busted) en une liste priorisée. Ici : la fusion/priorité/
plafond (_construire, pur), le rendu (XSS, caché si vide), et le remplacement
d'une source par pousser().
"""
import os

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS = os.path.join(CONCOURS, 'logx_fil_ia.js')
py_mini_racer = pytest.importorskip('py_mini_racer')


def _ctx():
    ctx = py_mini_racer.MiniRacer()
    ctx.eval("""
      var window = {};
      var __panel = { hidden: false };
      var __corps = { innerHTML: '', hidden: false };
      var document = { getElementById: function(id){
          if(id==='filIaPanel') return __panel;
          if(id==='filIaCorps') return __corps;
          return null; } };
    """)
    with open(JS, encoding='utf-8') as f:
        ctx.eval(f.read())
    return ctx


def test_construire_priorise_attention_proposition_info():
    ctx = _ctx()
    ctx.eval("""
      window.LogxFilIA.pousser('apres_qso', [{texte:'+1 carré', type:'info'}]);
      window.LogxFilIA.pousser('opportunites', [{texte:'JA1XYZ', type:'proposition'}]);
      window.LogxFilIA.pousser('validation', [{texte:'2 à vérifier', type:'attention'}]);
      window.__l = window.LogxFilIA._construire();
    """)
    types = ctx.eval("window.__l.map(function(e){return e.type;}).join(',')")
    assert types == 'attention,proposition,info'


def test_construire_plafonne_a_six():
    ctx = _ctx()
    ctx.eval("""
      var arr = [];
      for(var i=0;i<10;i++) arr.push({texte:'x'+i, type:'info'});
      window.LogxFilIA.pousser('opportunites', arr);
      window.__l = window.LogxFilIA._construire();
    """)
    assert ctx.eval("window.__l.length") == 6


def test_pousser_remplace_les_entrees_dune_source():
    ctx = _ctx()
    ctx.eval("window.LogxFilIA.pousser('validation', [{texte:'2 à vérifier', type:'attention'}]);")
    assert ctx.eval("window.LogxFilIA._construire().length") == 1
    ctx.eval("window.LogxFilIA.pousser('validation', []);")   # log redevenu propre
    assert ctx.eval("window.LogxFilIA._construire().length") == 0


def test_rendre_vide_cache_le_panneau():
    ctx = _ctx()
    ctx.eval("window.LogxFilIA._rendre([]);")
    assert ctx.eval("__panel.hidden") is True
    assert ctx.eval("__corps.innerHTML") == ''


def test_rendre_affiche_et_montre_le_panneau():
    ctx = _ctx()
    ctx.eval("window.LogxFilIA._rendre([{icone:'⚠', texte:'2 à vérifier', type:'attention'}]);")
    assert ctx.eval("__panel.hidden") is False
    html = ctx.eval("__corps.innerHTML")
    assert 'fil-item' in html and 'fil-attention' in html and '2 à vérifier' in html


def test_rendre_echappe_le_texte_xss():
    ctx = _ctx()
    ctx.eval("window.LogxFilIA._rendre([{texte:'<img src=x onerror=1>', type:'info'}]);")
    html = ctx.eval("__corps.innerHTML")
    assert '<img' not in html and '&lt;img' in html


def test_busted_call_alimente_et_retire_du_fil():
    """logx_busted_call pousse la suggestion au fil, et la retire à la fermeture."""
    ctx = py_mini_racer.MiniRacer()
    ctx.eval("""
      var __filPush = [];
      var window = { LogxFilIA: { pousser: function(s, e){ __filPush.push({source: s, n: (e||[]).length}); } } };
      function escHtml(s){ return String(s==null?'':s); }
      function trT(k){ return k; }
      function trF(k){ return k; }
      var __zone = { style:{display:''}, innerHTML:'' };
      var document = { getElementById: function(id){ return id==='bustedPastille' ? __zone : null; } };
    """)
    with open(os.path.join(CONCOURS, 'logx_busted_call.js'), encoding='utf-8') as f:
        ctx.eval(f.read())
    ctx.eval("afficherPastilleBusted({id:1, call:'F4GLDD'}, {call:'F4GLD', qso_count:12});")
    assert ctx.eval("__filPush[__filPush.length-1].source") == 'busted'
    assert ctx.eval("__filPush[__filPush.length-1].n") == 1
    ctx.eval("fermerPastilleBusted();")
    assert ctx.eval("__filPush[__filPush.length-1].n") == 0   # retiré à la fermeture


def test_cablage_logbook():
    with open(os.path.join(CONCOURS, 'logx_logbook.html'), encoding='utf-8') as f:
        h = f.read()
    assert 'src="logx_fil_ia.js"' in h
    assert 'id="filIaCorps"' in h and 'id="filIaPanel"' in h
