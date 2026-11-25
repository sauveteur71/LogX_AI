# -*- coding: utf-8 -*-
"""Audit 25/11/2026, section 3 (intuitivité) — vérifié en navigateur :
  3.5  en-tête « CQ World Wide DX — SSB » (et non CQ_WW_SSB), CONFIG « v1.2-beta11 » ;
  3.6  compteur « incomplet(s) » cliquable (8 QSO affichés, re-clic : tout) ;
  3.7  CHASSE : need-list en tête, onglet « Chasse » ;
  3.11 FT8/RTTY/SSTV : lien « ← LOGBOOK » hors fenêtre détachée seulement.
Modules exécutés tels quels ou fonctions extraites ; le reste sur la structure.
"""
import os
import re

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
py_mini_racer = pytest.importorskip('py_mini_racer')


def _src(nom):
    with open(os.path.join(CONCOURS, nom), encoding='utf-8') as f:
        return f.read()


def _sans_commentaires_js(s):
    s = re.sub(r'/\*.*?\*/', '', s, flags=re.S)
    return re.sub(r'(?m)(^|[^:\'"\\])//.*$', r'\1', s)


def _fn(src, nom):
    m = re.search(r'\n\s*function ' + re.escape(nom) + r'\s*\(', src)
    assert m, nom
    i = src.index('function', m.start())
    j, prof = src.index('{', i), 0
    for k in range(j, len(src)):
        prof += {'{': 1, '}': -1}.get(src[k], 0)
        if prof == 0:
            return src[i:k + 1]


# ── 3.11 retour au LOGBOOK ───────────────────────────────────────────────────

def _retour(nom_fenetre='', opener='null'):
    c = py_mini_racer.MiniRacer()
    c.eval("""
      var __hote = {enfants: [], appendChild: function(e){ this.enfants.push(e); }};
      var document = {readyState: 'complete',
        querySelector: function(s){ return s === 'header .logo-wrap' ? __hote : null; },
        getElementById: function(id){ return __hote.enfants.filter(function(e){ return e.id === id; })[0] || null; },
        createElement: function(){ return {style:{}}; }};
      var window = {name: %r, opener: %s};
    """ % (nom_fenetre, opener))
    c.eval(_src('logx_retour_logbook.js'))
    return c


def test_page_en_plein_onglet_a_un_lien_retour():
    c = _retour()
    assert c.eval('__hote.enfants.length') == 1
    assert c.eval('__hote.enfants[0].href') == '/logx_logbook.html'


@pytest.mark.parametrize('nom,opener', [('rc_ft8', 'null'), ('rc_rtty', 'null'), ('', '{closed:false}')])
def test_fenetre_detachee_sans_lien(nom, opener):
    assert _retour(nom, opener).eval('__hote.enfants.length') == 0


@pytest.mark.parametrize('page', ['logx_ft8.html', 'logx_rtty.html', 'logx_sstv.html'])
def test_pages_detachables_chargent_le_lien(page):
    assert '<script src="logx_retour_logbook.js"></script>' in _src(page)


# ── 3.5 nom du concours et version ───────────────────────────────────────────

def test_entete_logbook_nom_lisible():
    js = _sans_commentaires_js(_src('logx_logbook.js'))
    assert re.search(r"_hdrC\.textContent = cont \? \(\(window\.LogxNomsConcours \|\| \{\}\)\[cont\] \|\| cont\) : 'LOGBOOK';", js)
    sb = _sans_commentaires_js(_src('logx_statusbar.js'))
    assert 'window.LogxNomsConcours = contestNames;' in sb


def test_config_affiche_la_vraie_version():
    h = _src('logx_configuration.html')
    assert 'v3.0' not in h and 'id="cfgVersion"' in h
    sb = _sans_commentaires_js(_src('logx_statusbar.js'))
    assert re.search(r"cv\.textContent = 'v' \+ d\.app_version;", sb)


# ── 3.6 compteur d'incomplets ────────────────────────────────────────────────

def test_bascule_incomplets():
    c = py_mini_racer.MiniRacer()
    c.eval("""
      var __rendus = 0; function renderLog(){ __rendus++; }
      var __btns = [{dataset:{f:'all'}, cl:{}, classList:{toggle:function(k,v){ this.o = v; }}},
                    {dataset:{f:'144'}, classList:{toggle:function(k,v){ this.o = v; }}}];
      var document = {querySelectorAll: function(){ return __btns; }};
      var currentFilter = '144';
    """)
    c.eval(_fn(_src('logx_logbook.js'), 'basculerFiltreIncomplets'))
    c.eval('basculerFiltreIncomplets()')
    assert c.eval('currentFilter') == 'incomplets' and c.eval('__btns[0].classList.o') is False
    c.eval('basculerFiltreIncomplets()')
    assert c.eval('currentFilter') == 'all' and c.eval('__btns[0].classList.o') is True
    assert c.eval('__rendus') == 2


def test_filtre_incomplets_et_bouton_cables():
    js = _sans_commentaires_js(_fn(_src('logx_logbook.js'), 'renderLog'))
    assert "if(currentFilter==='incomplets' && isValidQSO(q)) return false;" in js
    assert 'b.onclick = basculerFiltreIncomplets;' in js


# ── 3.7 CHASSE ───────────────────────────────────────────────────────────────

def test_chasse_need_list_en_tete_et_titre():
    corps = _sans_commentaires_js(_fn(_src('logx_accueil.js'), '_revelerCiblesChasse'))
    assert corps.index('id="ckNeedList"') < corps.index('id="panPota"') < corps.index('id="objectifsList"')
    assert "document.title = 'LogX AI — Chasse';" in corps
