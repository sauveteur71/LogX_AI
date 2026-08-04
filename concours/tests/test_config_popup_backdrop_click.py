# -*- coding: utf-8 -*-
"""Non-régression : clic sur le FOND d'un popup CONFIG (l'overlay
`.cat-modal`, pas la boîte `.cat-modal-box` à l'intérieur) doit fermer le
popup — comme le bouton « Fermer », jamais « Enregistrer » (retour F4GLD
04/08/2026 : avant ce correctif, cliquer à côté d'un popup ne faisait
STRICTEMENT RIEN, aucun raccourci de fermeture n'existait).

Ce module exécute le VRAI code de bindCatModalBackdropClose(),
closeCategoryPopup() (via closeConfigPopup()/_currentOpenCat()) et
closeSummaryPopup() — extrait tel quel du fichier source par comptage
d'accolades, même technique que tests/test_assistant_banner_popup_js.py —
dans un moteur JS réel (V8 via py_mini_racer)."""
import os
import re

import pytest

py_mini_racer = pytest.importorskip(
    'py_mini_racer', reason='py_mini_racer absent (voir requirements.txt) — test JS réel ignoré')

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML_PATH = os.path.join(BASE, 'logx_configuration.html')


def _extract_function(src, name):
    """Extrait le texte complet `function <name>(){...}` par comptage
    d'accolades — le VRAI code du fichier, pas une réécriture."""
    m = re.search(r'^function %s\(' % re.escape(name), src, re.M)
    assert m, 'fonction %s introuvable dans %s' % (name, HTML_PATH)
    depth = 0
    i = src.index('{', m.start())
    while True:
        c = src[i]
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                return src[m.start():i + 1]
        i += 1


with open(HTML_PATH, encoding='utf-8') as _f:
    _HTML_SRC = _f.read()

_BIND_SRC = _extract_function(_HTML_SRC, 'bindCatModalBackdropClose')
_CURRENTOPENCAT_SRC = _extract_function(_HTML_SRC, '_currentOpenCat')
_CLOSECONFIGPOPUP_SRC = _extract_function(_HTML_SRC, 'closeConfigPopup')
_CLOSESUMMARY_SRC = _extract_function(_HTML_SRC, 'closeSummaryPopup')

# ─── DOM minimal : des .cat-modal factices qui enregistrent leurs écouteurs
# de clic et savent simuler un clic sur le FOND (target === l'overlay
# lui-même) ou un clic PROPAGÉ depuis un enfant (target === un autre objet) —
# c'est exactement la distinction que event.target===this doit faire.
_DOM_PREAMBLE = r"""
function makeModalEl(id, initDisplay){
  var disp = initDisplay;
  var listeners = [];
  var style = {};
  Object.defineProperty(style, 'display', {
    get:function(){ return disp; }, set:function(v){ disp = v; } });
  var el = {
    id:id, style: style,
    addEventListener: function(type, fn){ listeners.push(fn); },
    _listenerCount: function(){ return listeners.length; },
    _fireBackdropClick: function(){
      var self = el;
      listeners.forEach(function(fn){ fn({target: self}); });
    },
    _fireInsideClick: function(){
      var other = { id: 'une-boite-enfant' };
      listeners.forEach(function(fn){ fn({target: other}); });
    }
  };
  return el;
}

var CONFIG_SECTIONS = [['radio'], ['identity']];

var _els = {
  catmodal_radio:    makeModalEl('catmodal_radio', 'none'),
  catmodal_identity: makeModalEl('catmodal_identity', 'none'),
  catmodal_summary:  makeModalEl('catmodal_summary', 'none'),
  configSidebar:     makeModalEl('configSidebar', 'none'),
};

var document = {
  getElementById: function(id){ return _els[id] || null; },
  querySelectorAll: function(sel){
    if (sel === '.cat-modal') return [_els.catmodal_radio, _els.catmodal_identity, _els.catmodal_summary];
    return [];
  },
  body: { classList: {
    _tabbed: false,
    add: function(c){ if(c === 'config-tabbed') this._tabbed = true; },
    remove: function(c){ if(c === 'config-tabbed') this._tabbed = false; },
    contains: function(c){ return c === 'config-tabbed' && this._tabbed; }
  } }
};

var renderHubCalled = 0;
function renderHub(){ renderHubCalled++; }
var buildSummaryCalled = 0;
function buildSummary(){ buildSummaryCalled++; }
"""


def _make_ctx():
    ctx = py_mini_racer.MiniRacer()
    ctx.eval(_DOM_PREAMBLE)
    ctx.eval(_CURRENTOPENCAT_SRC)
    ctx.eval(_CLOSECONFIGPOPUP_SRC)
    ctx.eval(_CLOSESUMMARY_SRC)
    ctx.eval(_BIND_SRC)
    ctx.eval("bindCatModalBackdropClose();")
    return ctx


def test_bindCatModalBackdropClose_attache_bien_un_ecouteur_par_modal():
    """Garde-fou du garde-fou : si querySelectorAll('.cat-modal') ne
    remontait plus rien, tous les tests ci-dessous passeraient sans rien
    vérifier."""
    ctx = _make_ctx()
    assert ctx.eval("_els.catmodal_radio._listenerCount()") == 1
    assert ctx.eval("_els.catmodal_identity._listenerCount()") == 1
    assert ctx.eval("_els.catmodal_summary._listenerCount()") == 1


def test_clic_sur_le_fond_ferme_le_popup_categorie():
    ctx = _make_ctx()
    ctx.eval("_els.catmodal_radio.style.display = 'block';")
    ctx.eval("document.body.classList.add('config-tabbed');")
    ctx.eval("_els.catmodal_radio._fireBackdropClick();")
    assert ctx.eval("_els.catmodal_radio.style.display") == 'none', (
        "clic sur le fond de #catmodal_radio n'a pas fermé le popup")
    assert ctx.eval("document.body.classList.contains('config-tabbed')") is False


def test_clic_a_linterieur_de_la_boite_ne_ferme_RIEN():
    """C'est LE piège que event.target===this évite : un clic sur un champ/
    bouton À L'INTÉRIEUR de la boîte se propage (bubbling) jusqu'à l'overlay,
    mais ne doit jamais être confondu avec un clic sur le fond lui-même."""
    ctx = _make_ctx()
    ctx.eval("_els.catmodal_radio.style.display = 'block';")
    ctx.eval("_els.catmodal_radio._fireInsideClick();")
    assert ctx.eval("_els.catmodal_radio.style.display") == 'block', (
        "un clic PROPAGÉ depuis un enfant (la boîte, un champ...) a fermé le "
        "popup à tort — event.target===this doit distinguer les deux cas")


def test_clic_sur_le_fond_du_popup_resume_utilise_closeSummaryPopup():
    """#catmodal_summary n'est pas une catégorie CONFIG_SECTIONS normale —
    elle a sa propre fonction de fermeture, le bandeau ne doit pas se
    tromper de chemin (closeConfigPopup() n'aurait aucun effet dessus,
    _currentOpenCat() ne la connaît pas)."""
    ctx = _make_ctx()
    ctx.eval("_els.catmodal_summary.style.display = 'block';")
    ctx.eval("_els.catmodal_summary._fireBackdropClick();")
    assert ctx.eval("_els.catmodal_summary.style.display") == 'none', (
        "clic sur le fond de #catmodal_summary n'a pas fermé le popup résumé "
        "(chemin closeSummaryPopup() manquant ou mal aiguillé)")


def test_fermer_par_le_fond_rappelle_bien_renderHub():
    """Même comportement observable que le bouton « Fermer » explicite —
    sinon le hub resterait dans un état visuel périmé après fermeture."""
    ctx = _make_ctx()
    ctx.eval("_els.catmodal_identity.style.display = 'block';")
    ctx.eval("_els.catmodal_identity._fireBackdropClick();")
    assert ctx.eval("renderHubCalled") == 1
