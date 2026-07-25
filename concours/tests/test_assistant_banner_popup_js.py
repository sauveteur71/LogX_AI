# -*- coding: utf-8 -*-
"""Non-régression : assistant NOUVEAU CONCOURS invisible (migration hub/popups).

handleContestParam() (concours/logx_configuration.html), déclenché à l'arrivée
depuis logx_calendrier.html avec ?contest=ID, remplit #assistantBanner et le
passe en display:block. Or depuis la migration hub/popups (tâches 46-54), la
bannière vit DANS la popup #catmodal_contest, masquée par la règle CSS
.cat-modal{display:none} : sans un appel explicite à openCategoryPopup(
'contest'), la bannière est remplie mais INVISIBLE (offsetParent null), et le
message d'erreur « Concours introuvable » l'est tout autant. Les boutons
'▶ DÉMARRER CE CONCOURS' / '▶ PRÉPARER' du calendrier aboutissaient donc sur
le hub sans aucun retour visuel.

Ce module exécute le VRAI code de handleContestParam(), goStep() et
openCategoryPopup() — extrait tel quel du fichier source par comptage
d'accolades, pas retapé — dans un moteur JS réel (V8 via py_mini_racer, même
technique que tests/test_config_html_sota_qrz_race.py), avec un DOM minimal
qui reproduit l'état CSS initial de la page (.cat-modal en display:none,
#assistantBanner en display:none inline). Sans le correctif, la popup
#catmodal_contest reste en display:none et ces tests échouent."""
import os
import re

import pytest

py_mini_racer = pytest.importorskip(
    'py_mini_racer', reason='py_mini_racer absent (voir requirements.txt) — test JS réel ignoré')

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML_PATH = os.path.join(BASE, 'logx_configuration.html')


def _extract_function(src, name):
    """Extrait le texte complet `function <name>(){...}` par comptage
    d'accolades (les accolades présentes dans les template literals des
    fonctions ciblées sont toutes appariées — vérifié à la main) : on
    récupère le VRAI code du fichier, pas une réécriture."""
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

_HANDLE_SRC = _extract_function(_HTML_SRC, 'handleContestParam')
_GOSTEP_SRC = _extract_function(_HTML_SRC, 'goStep')
_OPENCAT_SRC = _extract_function(_HTML_SRC, 'openCategoryPopup')

# ─── DOM minimal fidèle à l'état CSS initial de la page ──────────────────────
# .cat-modal{display:none} (règle CSS) et #assistantBanner style="display:none"
# (inline). Chaque élément journalise ses écritures de style.display.
_DOM_PREAMBLE = r"""
function makeEl(id, initDisplay){
  var el = { id:id, innerHTML:'', value:'',
    classList:{ add:function(){}, remove:function(){}, toggle:function(){}, contains:function(){return false;} },
    scrollIntoView:function(){} };
  var disp = initDisplay, bc = '';
  var style = {};
  Object.defineProperty(style, 'display', {
    get:function(){ return disp; }, set:function(v){ disp = v; } });
  Object.defineProperty(style, 'borderColor', {
    get:function(){ return bc; }, set:function(v){ bc = v; } });
  el.style = style;
  return el;
}
var _els = {
  assistantBanner:    makeEl('assistantBanner', 'none'),
  catmodal_contest:   makeEl('catmodal_contest', 'none'),
  usage_mode:         makeEl('usage_mode', ''),
  contest_start_date: makeEl('contest_start_date', ''),
  contest_end_date:   makeEl('contest_end_date', ''),
  card_TEST_ID:       makeEl('card_TEST_ID', '')
};
_els.usage_mode.value = 'contest';

var document = {
  getElementById: function(id){ return _els[id] || null; },
  querySelectorAll: function(){ return []; },
  querySelector: function(){ return null; }
};
var window = { scrollTo:function(){} };
var localStorage = { getItem:function(){ return null; }, setItem:function(){} };

function URLSearchParams(s){
  this._m = {};
  var q = String(s).replace(/^\?/, '').split('&');
  for (var i = 0; i < q.length; i++){
    if(!q[i]) continue;
    var kv = q[i].split('=');
    this._m[decodeURIComponent(kv[0])] = decodeURIComponent(kv[1] || '');
  }
}
URLSearchParams.prototype.get = function(k){ return (k in this._m) ? this._m[k] : null; };

// État + dépendances de la page (stubs neutres)
var state = { step: 1, contest: null, datesAutoFor: null, toggles: {} };
var CONTESTS = [{ id:'TEST_ID', name:'Test Contest', external:false, rules:'' }];
var _filtersAppliedFor = null;
function getUiMode(){ return 'expert'; }
function getUsageMode(){ return 'contest'; }
function applyUsageMode(){}
function applyContestFilters(){}
function buildSummary(){}
function selectContest(id){ state.contest = id; }
function _missingStationFields(){ return []; }
function _warnMissingStation(){}
function refreshShiftOperatorSelect(){}
function loadShifts(){}
function renderHub(){}
function alert(){}
"""


def _make_ctx(search):
    ctx = py_mini_racer.MiniRacer()
    ctx.eval(_DOM_PREAMBLE)
    ctx.eval("var location = { search: %r };" % search)
    # Le VRAI openCategoryPopup est injecté : le test vérifie le comportement
    # de bout en bout (la popup passe réellement en display:block), pas
    # seulement qu'un appel a eu lieu.
    ctx.eval(_OPENCAT_SRC)
    ctx.eval(_GOSTEP_SRC)
    ctx.eval(_HANDLE_SRC)
    return ctx


def test_handleContestParam_ouvre_la_popup_contest():
    """Le correctif doit être présent dans le source : sans lui, aucune autre
    fonction du flux ?contest=ID n'affiche #catmodal_contest (échec lisible)."""
    assert "openCategoryPopup('contest')" in _HANDLE_SRC, (
        "handleContestParam() n'ouvre pas la popup #catmodal_contest : la "
        "bannière assistant y est rendue mais reste invisible "
        "(.cat-modal{display:none})")


def test_banniere_assistant_visible_apres_arrivee_du_calendrier():
    """?contest=ID connu : la bannière ET son ancêtre popup doivent être
    affichés — c'est la conjonction des deux qui rend l'assistant visible."""
    ctx = _make_ctx('?contest=TEST_ID')
    ctx.eval("handleContestParam();")
    assert ctx.eval("_els.assistantBanner.style.display") == 'block'
    assert ctx.eval(
        "_els.assistantBanner.innerHTML.indexOf('ASSISTANT NOUVEAU CONCOURS')>=0")
    assert ctx.eval("_els.assistantBanner.innerHTML.indexOf('TOUT EST BON')>=0")
    # Cœur du bug : sans openCategoryPopup('contest'), la popup restait 'none'
    # et la bannière (pourtant en display:block) avait offsetParent === null.
    assert ctx.eval("_els.catmodal_contest.style.display") == 'block', (
        "#catmodal_contest est resté masqué : l'assistant NOUVEAU CONCOURS "
        "est rempli mais invisible")


def test_erreur_concours_introuvable_visible():
    """?contest=ID inconnu : le message « introuvable » vit dans la même
    popup — lui aussi doit être réellement visible."""
    ctx = _make_ctx('?contest=INCONNU')
    ctx.eval("handleContestParam();")
    assert ctx.eval("_els.assistantBanner.style.display") == 'block'
    assert ctx.eval("_els.assistantBanner.innerHTML.indexOf('introuvable')>=0")
    assert ctx.eval("_els.catmodal_contest.style.display") == 'block', (
        "#catmodal_contest est resté masqué : l'erreur « Concours "
        "introuvable » est invisible pour l'utilisateur")


def test_sans_parametre_contest_la_popup_reste_fermee():
    """Garde-fou inverse : ouvrir configuration.html SANS ?contest ne doit pas
    ouvrir la popup CONCOURS toute seule (handleContestParam sort tout de
    suite) — le correctif ne doit s'appliquer qu'au flux lien profond."""
    ctx = _make_ctx('')
    ctx.eval("handleContestParam();")
    assert ctx.eval("_els.catmodal_contest.style.display") == 'none'
    assert ctx.eval("_els.assistantBanner.style.display") == 'none'
