# -*- coding: utf-8 -*-
"""Fermeture du panneau CONFIG par un clic en dehors -- retour F4GLD
(11/08/2026) : « je voudrais pouvoir fermer cette page par un simple clic
a l'exterieur du popup ». #configSidebar et le .cat-modal-box actif sont en
position:fixed avec des marges de 6% qui laissent de l'arrière-plan visible
et cliquable -- un clic qui atteint CE FOND (document.body ou <div
class="container">, l'ancien conteneur de page toujours présent en enfant
direct de body -- vérifié en navigateur réel via elementFromPoint() : la
première hypothèse « document.body directement » était fausse, .container
le recouvre entièrement) doit fermer le panneau de catégorie ouvert.

PRÉCISION F4GLD (11/08/2026, juste après le 1er déploiement) : « je veux
pas directement repartir dans logbook je veux juste que le popup config se
ferme! en restant sur l'onglet config » -- le geste appelé est donc
closeCategoryPanel() (ferme sur place, ne navigue jamais), pas launchApp()
(qui navigue vers logx_logbook.html, testé initialement puis corrigé).

Ce module teste uniquement le CIBLAGE du clic (quel élément déclenche
l'appel) -- la logique de closeCategoryPanel() elle-même (garde de
modifications non enregistrées, masquage du bon panneau, désélection de la
sidebar) est testée dans test_config_category_switch.py, qui possède déjà
le DOM factice riche (catmodal_*/catbody_*) nécessaire pour l'exercer
réellement plutôt que de la stubber.

Exécute le VRAI code (extrait tel quel par recherche du bloc, même technique
que tests/test_score_a_battre_js.py) dans un moteur JS réel (V8 via
py_mini_racer)."""
import os
import re

import pytest

py_mini_racer = pytest.importorskip(
    'py_mini_racer', reason='py_mini_racer absent (voir requirements.txt) — test JS réel ignoré')

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS_PATH = os.path.join(BASE, 'logx_configuration.js')

with open(JS_PATH, encoding='utf-8') as _f:
    _JS_SRC = _f.read()

_CLICK_OUTSIDE_SRC = re.search(
    r"document\.body\.addEventListener\('click', function\(e\)\{.*?\}\);",
    _JS_SRC, re.S)
assert _CLICK_OUTSIDE_SRC, "listener de fermeture par clic extérieur introuvable"
_CLICK_OUTSIDE_SRC = _CLICK_OUTSIDE_SRC.group(0)
assert 'closeCategoryPanel' in _CLICK_OUTSIDE_SRC, \
    "le clic extérieur doit fermer sur place (closeCategoryPanel), pas naviguer (launchApp)"

_DOM_PREAMBLE = r"""
var _closeCalls = 0;
function closeCategoryPanel(){ _closeCalls++; }
var _sidebarPresent = true;
var _bodyHandlers = [];
var _bodyEl = {
  addEventListener: function(type, fn){ _bodyHandlers.push(fn); },
};
function _fireBodyClick(target){
  _bodyHandlers.forEach(function(fn){ fn({target: target}); });
}
var document = {
  body: _bodyEl,
  getElementById: function(id){
    if(id === 'configSidebar') return _sidebarPresent ? {} : null;
    return null;
  }
};
"""


def _make_ctx():
    ctx = py_mini_racer.MiniRacer()
    ctx.eval(_DOM_PREAMBLE)
    ctx.eval(_CLICK_OUTSIDE_SRC)
    return ctx


def test_clic_sur_le_corps_de_page_ferme_le_panneau():
    ctx = _make_ctx()
    ctx.eval("_fireBodyClick(document.body);")
    assert ctx.eval("_closeCalls") == 1


def test_clic_sur_le_conteneur_de_fond_ferme_le_panneau():
    """Cas RÉEL rencontré en navigateur : <div class="container"> (ancien
    conteneur de page, enfant direct de body) recouvre la marge visible
    autour de la sidebar/du panneau -- c'est LUI la cible du clic dans le
    vide, pas document.body directement."""
    ctx = _make_ctx()
    ctx.eval("var _containerEl = {classList: {contains: function(c){ return c === 'container'; }}};")
    ctx.eval("_fireBodyClick(_containerEl);")
    assert ctx.eval("_closeCalls") == 1


def test_clic_sur_un_element_a_l_interieur_ne_ferme_rien():
    """Un clic sur la sidebar, un panneau de catégorie, la nav ou tout autre
    widget flottant a pour cible CET ÉLÉMENT, jamais document.body/.container
    -- même si l'événement remonte jusqu'à lui par bubbling (e.target reste
    l'élément cliqué, pas currentTarget)."""
    ctx = _make_ctx()
    ctx.eval("var _sidebarButton = {classList: {contains: function(){ return false; }}};")
    ctx.eval("_fireBodyClick(_sidebarButton);")
    assert ctx.eval("_closeCalls") == 0


def test_clic_sur_un_element_sans_classlist_ne_plante_pas_et_ne_ferme_rien():
    """Un élément quelconque sans .classList (objet minimal, comme dans un
    DOM factice de test) ne doit ni lever d'exception ni déclencher la
    fermeture -- seul un match explicite ouvre la porte."""
    ctx = _make_ctx()
    ctx.eval("var _plainEl = {};")
    ctx.eval("_fireBodyClick(_plainEl);")
    assert ctx.eval("_closeCalls") == 0


def test_sans_configsidebar_le_clic_exterieur_ne_fait_rien():
    """Filet de sécurité : si #configSidebar n'existe pas (page CONFIG pas
    encore construite, ou logx_configuration.js chargé ailleurs par erreur),
    ne jamais agir sur un simple clic dans le vide."""
    ctx = _make_ctx()
    ctx.eval("_sidebarPresent = false;")
    ctx.eval("_fireBodyClick(document.body);")
    assert ctx.eval("_closeCalls") == 0
