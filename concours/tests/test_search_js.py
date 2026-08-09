# -*- coding: utf-8 -*-
"""Recherche plein-texte côté NAVIGATEUR (logx_search.js) — constat de la
passe de vérification complète du 09/08/2026 : seule la partie backend
(logx_search.py, couverte par test_search.py) avait des tests ; toute la
logique DOM (findMatch, highlightFromQuery avec sa boucle de retentative
~2.4s, nettoyage d'URL ?rcq= via cleanUrl) n'en avait aucun.

Le fichier source est un IIFE qui ne fuit rien vers le global scope — un
export CommonJS conditionnel (`if (typeof module !== 'undefined')`, no-op en
navigateur réel) a été ajouté pour exercer le VRAI code dans py_mini_racer,
plutôt que d'en réimplémenter une copie côté test (voir le même patron déjà
en place pour logx_cwdecoder.js/logx_rttydecoder.js).

DOM minimal mais FONCTIONNEL (TreeWalker sur de vrais nœuds texte, closest()
avec un vrai algorithme de remontée d'ancêtres, classList réel) -- on
observe le comportement RÉEL des fonctions sur des données construites, pas
une relecture du source."""
import json
import os

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS = os.path.join(CONCOURS, 'logx_search.js')

py_mini_racer = pytest.importorskip('py_mini_racer')

# ─── DOM minimal : TreeWalker(SHOW_TEXT) + closest() + classList + scrollIntoView
_DOM_PREAMBLE = r"""
var module = {};   // déclenche l'export conditionnel en fin de fichier
var window = {};

function _mkEl(tag, className, children){
  var el = {
    tag: tag, className: className || '', parent: null, children: [],
    _classes: {}, scrollCalls: [],
  };
  el.classList = {
    add: function(c){ el._classes[c] = true; },
    remove: function(c){ delete el._classes[c]; },
    contains: function(c){ return !!el._classes[c]; },
  };
  el.scrollIntoView = function(opts){ el.scrollCalls.push(opts || {}); };
  el.closest = function(selector){
    var sels = selector.split(',').map(function(s){ return s.trim(); });
    var cur = el;
    while(cur){
      for(var i=0;i<sels.length;i++){
        var s = sels[i];
        if(s.charAt(0) === '.'){
          if(cur.tag && (' ' + (cur.className||'') + ' ').indexOf(' ' + s.slice(1) + ' ') >= 0) return cur;
        } else if(cur.tag === s){
          return cur;
        }
      }
      cur = cur.parent;
    }
    return null;
  };
  (children || []).forEach(function(c){
    if(typeof c === 'string'){
      el.children.push({ nodeValue: c, parentElement: el, isText: true });
    } else {
      c.parent = el;
      el.children.push(c);
    }
  });
  return el;
}

function _collectTextNodes(root){
  var out = [];
  (function walk(node){
    (node.children || []).forEach(function(c){
      if(c.isText) out.push(c); else walk(c);
    });
  })(root);
  return out;
}

var NodeFilter = { SHOW_TEXT: 4 };

var _historyReplaceCalls = [];
var history = { replaceState: function(state, title, url){ _historyReplaceCalls.push(url); } };

var _locationSearch = '';
var location = {
  protocol: 'http:',
  get search(){ return _locationSearch; },
  href: 'http://localhost/page.html',
  pathname: '/page.html',
  hash: '',
};

function URLSearchParams(search){
  var params = {};
  (search || '').replace(/^\?/, '').split('&').forEach(function(pair){
    if(!pair) return;
    var idx = pair.indexOf('=');
    var k = decodeURIComponent(idx >= 0 ? pair.slice(0, idx) : pair);
    var v = idx >= 0 ? decodeURIComponent(pair.slice(idx + 1)) : '';
    params[k] = v;
  });
  this.get = function(k){ return params.hasOwnProperty(k) ? params[k] : null; };
}

function URL(href){
  var qIdx = href.indexOf('?');
  var qs = qIdx >= 0 ? href.slice(qIdx) : '';
  var deleted = {};
  this.pathname = '/page.html';
  this.hash = '';
  this.searchParams = { delete: function(k){ deleted[k] = true; } };
  Object.defineProperty(this, 'search', { get: function(){
    var kept = qs.replace(/^\?/, '').split('&').filter(function(pair){
      if(!pair) return false;
      var k = decodeURIComponent(pair.split('=')[0]);
      return !deleted[k];
    });
    return kept.length ? '?' + kept.join('&') : '';
  }});
}

// document : juste assez pour que le module se charge (init() se no-op
// faute de 'nav.app-nav') et pour que highlightFromQuery()/findMatch()
// disposent d'un vrai arbre à parcourir.
var _body = _mkEl('body', '', []);
var document = {
  readyState: 'complete',
  protocol: 'http:',
  head: { appendChild: function(){} },
  createElement: function(){ return { textContent: '', setAttribute: function(){} }; },
  querySelector: function(){ return null; },   // pas de nav -> init() no-op
  addEventListener: function(){},
  body: _body,
  createTreeWalker: function(root){
    var nodes = _collectTextNodes(root);
    var idx = -1;
    return { nextNode: function(){ idx++; return idx < nodes.length ? nodes[idx] : null; } };
  },
};

// setTimeout : les retentatives de highlightFromQuery() utilisent un délai
// de 300ms (tryOnce) -- déclenché SYNCHRONEMENT pour que la boucle converge
// dans le même appel Python. Le délai de 2700ms (retrait du flash après
// affichage) n'est PAS déclenché : sans ça, le test ne pourrait jamais
// observer la classe de surbrillance, retirée avant même la fin de l'appel.
function setTimeout(fn, delay){
  if(delay <= 300) fn();
  return 0;
}
"""


@pytest.fixture
def ctx():
    c = py_mini_racer.MiniRacer()
    c.eval(_DOM_PREAMBLE)
    with open(JS, encoding='utf-8') as f:
        src = f.read()
    c.eval(src)
    # Le fichier source est une IIFE : rien ne fuit vers le global scope à
    # part `module.exports` (voir la fin du fichier). Alias pratiques pour
    # que les tests appellent esc()/findMatch()/highlightFromQuery()
    # directement, comme le ferait n'importe quel appelant réel du module.
    c.eval("var esc = module.exports.esc, findMatch = module.exports.findMatch, "
           "highlightFromQuery = module.exports.highlightFromQuery;")
    return c


def _set_body(ctx, children_json):
    """children_json : structure JSON {tag, className, children:[str|dict]}
    reconstruite côté JS en vrais éléments _mkEl -- construit l'arbre AVANT
    d'appeler findMatch()/highlightFromQuery() (déjà chargées, donc déjà
    liées à `document.body` = `_body`, un objet MUTABLE)."""
    ctx.eval(f"""
    (function rebuild(spec){{
      function build(s){{
        if(typeof s === 'string') return s;
        return _mkEl(s.tag, s.className || '', (s.children||[]).map(build));
      }}
      var fresh = build(spec);
      _body.tag = fresh.tag; _body.className = fresh.className; _body.children = fresh.children;
      fresh.children.forEach(function(c){{ if(!c.isText) c.parent = _body; }});
    }})({json.dumps(children_json)})
    """)


# ─── esc() : échappement HTML (rendu des résultats, surface XSS) ───────────

def test_esc_echappe_les_caracteres_html(ctx):
    out = ctx.eval("esc('<script>alert(1)</script> & \"quote\" \\'apos\\'')")
    assert '<' not in out and '>' not in out
    assert '&lt;script&gt;' in out
    assert '&amp;' in out
    assert '&quot;' in out
    assert '&#39;' in out


# ─── findMatch() : traversée du texte, exclusion script/panneau de recherche ─

def test_findmatch_trouve_le_texte_visible(ctx):
    _set_body(ctx, {
        'tag': 'body', 'children': [
            {'tag': 'div', 'className': 'page-content',
             'children': ['Bienvenue sur la page SSTV de LogX AI']},
        ],
    })
    result = ctx.eval("(function(){ var el = findMatch('sstv'); return el ? el.tag + '|' + el.className : null; })()")
    assert result == 'div|page-content'


def test_findmatch_ignore_script_et_panneau_recherche(ctx):
    """Un texte présent DANS <script> ou .nav-search-panel ne doit jamais
    être retourné (closest() les exclut explicitement, ligne 160 du
    fichier) -- sinon le clic sur un résultat de recherche pourrait faire
    défiler vers du code JS caché ou vers le panneau lui-même."""
    _set_body(ctx, {
        'tag': 'body', 'children': [
            {'tag': 'script', 'children': ["var sstv = 'texte caché dans le code';"]},
            {'tag': 'div', 'className': 'nav-search-panel',
             'children': ['Rechercher sstv ici']},
            {'tag': 'div', 'className': 'page-content',
             'children': ['La page SSTV visible, le VRAI résultat']},
        ],
    })
    result = ctx.eval("(function(){ var el = findMatch('sstv'); return el ? el.className : null; })()")
    assert result == 'page-content'


def test_findmatch_retourne_null_si_aucune_correspondance(ctx):
    _set_body(ctx, {'tag': 'body', 'children': [
        {'tag': 'div', 'children': ['Rien à voir ici']},
    ]})
    assert ctx.eval("findMatch('sstv') === null")


# ─── highlightFromQuery() : défilement + surbrillance + nettoyage d'URL ────

def test_highlightfromquery_defile_surligne_et_nettoie_url(ctx):
    ctx.eval("_locationSearch = '?rcq=sstv'; location.href = 'http://localhost/page.html?rcq=sstv';")
    _set_body(ctx, {'tag': 'body', 'children': [
        {'tag': 'div', 'className': 'page-content',
         'children': ['La page SSTV de LogX AI']},
    ]})
    ctx.eval("highlightFromQuery()")

    flashed = ctx.eval("_body.children[0].classList.contains('rc-search-hit-flash')")
    scroll_calls = ctx.eval("_body.children[0].scrollCalls.length")
    history_calls = json.loads(ctx.eval("JSON.stringify(_historyReplaceCalls)"))

    assert flashed is True
    assert scroll_calls == 1
    assert len(history_calls) == 1
    assert 'rcq' not in history_calls[0]


def test_highlightfromquery_sans_parametre_rcq_ne_fait_rien(ctx):
    ctx.eval("_locationSearch = ''; location.href = 'http://localhost/page.html';")
    _set_body(ctx, {'tag': 'body', 'children': [
        {'tag': 'div', 'className': 'page-content', 'children': ['La page SSTV']},
    ]})
    ctx.eval("highlightFromQuery()")

    scroll_calls = ctx.eval("_body.children[0].scrollCalls.length")
    history_calls = json.loads(ctx.eval("JSON.stringify(_historyReplaceCalls)"))
    assert scroll_calls == 0
    assert history_calls == []


def test_highlightfromquery_abandonne_apres_8_tentatives_et_nettoie_quand_meme(ctx):
    """Aucune correspondance trouvée : la boucle de retentative (~2.4s,
    MAX_ATTEMPTS=8) doit finir par abandonner ET nettoyer l'URL malgré tout
    (« rien trouvé : au moins ne pas garder un paramètre mort », commentaire
    ligne 192 du fichier) -- sinon ?rcq= resterait collé à l'URL pour
    toujours sur une page qui ne contient jamais le terme cherché."""
    ctx.eval("_locationSearch = '?rcq=introuvable'; location.href = 'http://localhost/page.html?rcq=introuvable';")
    _set_body(ctx, {'tag': 'body', 'children': [
        {'tag': 'div', 'className': 'page-content', 'children': ['Rien de pertinent ici']},
    ]})
    ctx.eval("highlightFromQuery()")

    history_calls = json.loads(ctx.eval("JSON.stringify(_historyReplaceCalls)"))
    assert len(history_calls) == 1
    assert 'rcq' not in history_calls[0]


def test_highlightfromquery_terme_trop_court_ne_fait_rien(ctx):
    """needle.length < 2 (garde ligne 176) : un caractère isolé dans ?rcq=
    ne doit déclencher ni recherche ni nettoyage d'URL."""
    ctx.eval("_locationSearch = '?rcq=s'; location.href = 'http://localhost/page.html?rcq=s';")
    _set_body(ctx, {'tag': 'body', 'children': [
        {'tag': 'div', 'className': 'page-content', 'children': ['s']},
    ]})
    ctx.eval("highlightFromQuery()")
    history_calls = json.loads(ctx.eval("JSON.stringify(_historyReplaceCalls)"))
    assert history_calls == []
