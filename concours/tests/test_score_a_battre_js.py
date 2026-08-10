# -*- coding: utf-8 -*-
"""refreshContestBestScore() (concours/logx_configuration.html) : bandeau
« score à battre » affiché à la sélection d'un concours ayant déjà été
archivé lors d'éditions passées (voir logx_archive.best_for_contest() et
tests/test_score_a_battre.py pour la logique serveur).

Exécute le VRAI code extrait tel quel du fichier source (même technique que
tests/test_config_html_sota_qrz_race.py) dans un moteur JS réel (V8 via
py_mini_racer), avec un fetch() mocké contrôlable et un DOM minimal."""
import os

import pytest

py_mini_racer = pytest.importorskip(
    'py_mini_racer', reason='py_mini_racer absent (voir requirements.txt) — test JS réel ignoré')

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML_PATH = os.path.join(BASE, 'logx_configuration.html')

with open(HTML_PATH, encoding='utf-8') as _f:
    _HTML_SRC = _f.read()


def _extract_function(src, name):
    start = src.index(f'async function {name}(')
    brace_open = src.index('{', start)
    depth = 0
    i = brace_open
    while True:
        c = src[i]
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                return src[start:i + 1]
        i += 1


_REFRESH_SRC = _extract_function(_HTML_SRC, 'refreshContestBestScore')
assert "fetch('/log/archives/best" in _REFRESH_SRC

_DOM_PREAMBLE = r"""
var __store = {};
function ElProxy(){
  var s = {value:'', textContent:'', innerHTML:'', style:{display:''}};
  var handler = {
    get:function(target, prop){
      if(prop === 'style') return s.style;
      return s[prop];
    },
    set:function(target, prop, val){ s[prop] = val; return true; }
  };
  return new Proxy({}, handler);
}
var document = {
  getElementById: function(id){ if(!__store[id]) __store[id] = ElProxy(); return __store[id]; },
};
function escC(v){ return String(v==null?'':v).replace(/[&<>"']/g,
  c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
"""


def _make_ctx(fetch_impl):
    ctx = py_mini_racer.MiniRacer()
    ctx.eval(_DOM_PREAMBLE)
    ctx.eval(f"var fetch = {fetch_impl};")
    ctx.eval(_REFRESH_SRC)
    return ctx


def _pump(ctx):
    """Laisse le microtask queue des promesses se vider (même astuce que
    test_config_html_sota_qrz_race.py)."""
    ctx.eval("undefined")


def test_sans_concours_masque_et_ne_fetch_pas():
    ctx = _make_ctx("function(){ throw new Error('fetch ne doit pas être appelé'); }")
    ctx.eval("document.getElementById('contest_best_score').style.display = 'block';")
    ctx.eval("refreshContestBestScore(null);")
    assert ctx.eval("document.getElementById('contest_best_score').style.display") == 'none'
    assert ctx.eval("document.getElementById('contest_best_score').innerHTML") == ''


def test_aucune_archive_masque_le_bandeau():
    ctx = _make_ctx("""function(url){
      return Promise.resolve({ json: function(){ return Promise.resolve({ok:false}); } });
    }""")
    ctx.eval("refreshContestBestScore('REF_160M');")
    _pump(ctx)
    assert ctx.eval("document.getElementById('contest_best_score').style.display") == 'none'


def test_avec_archives_affiche_qso_et_points():
    ctx = _make_ctx("""function(url){
      return Promise.resolve({ json: function(){ return Promise.resolve({
        ok:true, contest:'REF_160M', editions:2,
        best_qso:42, best_qso_year:'2025',
        best_points:1234, best_points_year:'2024'
      }); } });
    }""")
    ctx.eval("refreshContestBestScore('REF_160M');")
    _pump(ctx)
    el_display = ctx.eval("document.getElementById('contest_best_score').style.display")
    html = ctx.eval("document.getElementById('contest_best_score').innerHTML")
    assert el_display == 'block'
    assert '42' in html and '2025' in html
    assert '1234' in html and '2024' in html


def test_requete_porte_bien_le_concours_en_query_param():
    fetched_url = []
    ctx = _make_ctx("""function(url){
      __fetchedUrl = url;
      return Promise.resolve({ json: function(){ return Promise.resolve({ok:false}); } });
    }""")
    ctx.eval("var __fetchedUrl = null;")
    ctx.eval("refreshContestBestScore('REF/160M');")
    _pump(ctx)
    assert ctx.eval("__fetchedUrl") == '/log/archives/best?contest=REF%2F160M'


def test_pas_de_qso_director():
    assert 'QSO Director' not in _HTML_SRC
