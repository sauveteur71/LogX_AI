# -*- coding: utf-8 -*-
"""Non-régression : changement de catégorie dans l'arborescence CONFIG
(refonte sidebar du 08/08/2026, remplace le hub de cartes + popup plein
écran par catégorie — voir CLAUDE.md/mémoire du chantier).

Remplace tests/test_config_popup_backdrop_click.py : ce dernier testait le
clic sur le FOND d'un popup (.cat-modal, overlay plein écran) pour le
fermer — mécanisme entièrement retiré avec la refonte (plus de backdrop,
panneau docké en permanence, openCategoryPopup() gère lui-même la fermeture
de la section précédente). Ce module teste donc directement openCategoryPopup()
et son garde de modifications non enregistrées (_confirmDiscardCatChanges),
sur le MÊME motif que l'ancien fichier : exécution du VRAI code (extrait tel
quel du fichier source par comptage d'accolades) dans un moteur JS réel
(V8 via py_mini_racer), pas une réécriture ni un mock du comportement testé.

Cas central couvert (trouvé par la revue adversariale du 08/08/2026, avant
la refonte sidebar) : changer de catégorie alors que la section actuellement
ouverte a des modifications non enregistrées doit avertir via confirm(), et
un refus doit annuler TOUT le changement (ni fermeture de l'ancienne section,
ni ouverture de la nouvelle) — pas seulement bloquer un des deux effets."""
import json
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
    # (?:async\s+)? : plusieurs fonctions sont devenues async (chantier
    # dialogues non bloquants, 10/08/2026 -- _confirmDupBanner()/
    # _confirmConfigBanner() remplacent confirm() natif, ce qui nécessite
    # await donc async).
    m = re.search(r'^(?:async\s+)?function %s\(' % re.escape(name), src, re.M)
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
# Script inline extrait vers logx_configuration.js (10/08/2026) -- concaténer
# pour que les extractions de fonctions ci-dessous continuent de les trouver.
_JS_PATH = os.path.join(BASE, 'logx_configuration.js')
if os.path.exists(_JS_PATH):
    with open(_JS_PATH, encoding='utf-8') as _f:
        _HTML_SRC += '\n' + _f.read()

_OPENCAT_SRC = _extract_function(_HTML_SRC, 'openCategoryPopup')
_CURRENTOPENCAT_SRC = _extract_function(_HTML_SRC, '_currentOpenCat')
_SNAPSHOTCATFORM_SRC = _extract_function(_HTML_SRC, '_snapshotCatForm')
_CATHASUNSAVED_SRC = _extract_function(_HTML_SRC, '_catHasUnsavedChanges')
_CONFIRMDISCARD_SRC = _extract_function(_HTML_SRC, '_confirmDiscardCatChanges')
_CLOSECATPANEL_SRC = _extract_function(_HTML_SRC, 'closeCategoryPanel')

# ─── DOM minimal : 4 catégories factices (identity/contest/filters/summary),
# chacune avec un panneau (.cat-modal_<cat>, style.display suivi) et un corps
# de formulaire (.catbody_<cat>) contenant un champ éditable — juste assez
# pour que _snapshotCatForm() détecte un changement de valeur, comme le
# ferait un vrai <input> du fichier source.
_DOM_PREAMBLE = r"""
function makeModalEl(id, initDisplay){
  var disp = initDisplay;
  var style = {};
  Object.defineProperty(style, 'display', {
    get:function(){ return disp; }, set:function(v){ disp = v; } });
  return { id:id, style: style };
}
function makeCatBody(id, inputs){
  return { id:id, querySelectorAll: function(){ return inputs; } };
}

var CONFIG_SECTIONS = [['identity'], ['contest'], ['filters'], ['summary']];

var _inputsIdentity = [{ id:'callsign', type:'text', value:'F4TEST' }];
var _inputsContest  = [];
var _inputsFilters  = [];
var _inputsSummary  = [];

// Boutons factices de #configSidebar -- juste assez de classList (contains/
// add/remove/toggle) pour que closeCategoryPanel() puisse désélectionner
// l'entrée active sans planter, sur le MÊME motif que le vrai DOM
// (nav.querySelectorAll('.config-sidebar-item').forEach(b => b.classList...)).
function makeSidebarButton(cat, active){
  var classes = ['config-sidebar-item'];
  if(active) classes.push('active');
  return {
    dataset: {cat: cat},
    classList: {
      contains: function(c){ return classes.indexOf(c) !== -1; },
      add: function(c){ if(classes.indexOf(c) === -1) classes.push(c); },
      remove: function(c){ var i = classes.indexOf(c); if(i !== -1) classes.splice(i, 1); },
      toggle: function(c, force){
        var has = classes.indexOf(c) !== -1;
        var want = (force === undefined) ? !has : force;
        if(want && !has) classes.push(c);
        if(!want && has) classes.splice(classes.indexOf(c), 1);
      }
    }
  };
}
var _sidebarButtons = [
  makeSidebarButton('identity', true),
  makeSidebarButton('contest', false),
];
var _configSidebarEl = {
  querySelectorAll: function(sel){
    return (sel === '.config-sidebar-item') ? _sidebarButtons : [];
  }
};

var _els = {
  catmodal_identity: makeModalEl('catmodal_identity', 'none'),
  catmodal_contest:  makeModalEl('catmodal_contest', 'none'),
  catmodal_filters:  makeModalEl('catmodal_filters', 'none'),
  catmodal_summary:  makeModalEl('catmodal_summary', 'none'),
  catbody_identity:  makeCatBody('catbody_identity', _inputsIdentity),
  catbody_contest:   makeCatBody('catbody_contest', _inputsContest),
  catbody_filters:   makeCatBody('catbody_filters', _inputsFilters),
  catbody_summary:   makeCatBody('catbody_summary', _inputsSummary),
  configSidebar:     _configSidebarEl,
};

var document = {
  getElementById: function(id){ return (id in _els) ? _els[id] : null; },
  querySelectorAll: function(){ return []; }
};

// closeCategoryPanel() navigue désormais vers LOGBOOK (revirement du
// 16/08/2026, voir son commentaire dans logx_configuration.js) -- stub
// minimal juste assez riche pour capturer la destination sans qu'un vrai
// changement de page n'ait de sens dans ce moteur JS isolé.
var window = { location: { href: '' } };

var _catFormSnapshots = {};
var _confirmResult = true;
var _confirmCalls = 0;
// _confirmDiscardCatChanges() appelle désormais _confirmConfigBanner() (bandeau
// non bloquant, chantier dialogues non bloquants, 10/08/2026) au lieu de
// confirm() natif -- stub Promise plutôt que valeur synchrone.
function _confirmConfigBanner(msg){ _confirmCalls++; return Promise.resolve(_confirmResult); }
function T(s){ return s; }
function buildSummary(){}
function refreshShiftOperatorSelect(){}
function loadShifts(){}
"""


def _make_ctx():
    ctx = py_mini_racer.MiniRacer()
    ctx.eval(_DOM_PREAMBLE)
    ctx.eval(_SNAPSHOTCATFORM_SRC)
    ctx.eval(_CATHASUNSAVED_SRC)
    ctx.eval(_CONFIRMDISCARD_SRC)
    ctx.eval(_CURRENTOPENCAT_SRC)
    ctx.eval(_OPENCAT_SRC)
    ctx.eval(_CLOSECATPANEL_SRC)
    return ctx


# ─── buildConfigSidebar() : chemin de succès réel, jamais exécuté ailleurs ──
# Trouvé par la revue adversariale du 08/08/2026 : buildConfigSidebar() est
# désormais le SEUL mécanisme de navigation entre catégories (le hub de
# cartes a disparu), appelée dans openCategoryPopup() sous un try/catch(e){}
# vide préexistant qui avale toute exception -- les tests ci-dessus stubbent
# un `document` sans createElement/body, donc buildConfigSidebar() y lève
# systématiquement (avalée par le catch) et son chemin de succès n'est
# jamais exercé nulle part. Une régression réelle (ex. faute de frappe
# `_EXPERT_ONLY_CATS.hax(cat)` au lieu de `.has(cat)`) passerait donc TOUS
# les tests existants inchangée. Ci-dessous : DOM minimal mais FONCTIONNEL
# (createElement + un parseur regex volontairement simple pour innerHTML,
# pas un vrai moteur HTML) qui exécute le VRAI CONFIG_SECTIONS/
# _EXPERT_ONLY_CATS/buildConfigSidebar() du fichier source et vérifie le
# HTML RÉELLEMENT généré, pas seulement sa présence littérale dans la source.
_ICO_CONSTS_SRC = '\n'.join(re.findall(r"^const _ICO_\w+ = '.*';$", _HTML_SRC, re.M))
assert _ICO_CONSTS_SRC.count('const _ICO_') >= 15, "constantes _ICO_* introuvables"
_CONFIG_SECTIONS_SRC = re.search(r'^const CONFIG_SECTIONS = \[.*?\];', _HTML_SRC, re.S | re.M).group(0)
_EXPERT_ONLY_CATS_SRC = re.search(r'^const _EXPERT_ONLY_CATS = .*?;$', _HTML_SRC, re.M).group(0)
_BUILDSIDEBAR_SRC = _extract_function(_HTML_SRC, 'buildConfigSidebar')

_SIDEBAR_DOM_PREAMBLE = r"""
function makeFakeNav(){
  var _html = '';
  return {
    id: '', className: '',
    set innerHTML(v){ _html = v; },
    get innerHTML(){ return _html; },
    _rawHtml: function(){ return _html; },
    querySelectorAll: function(sel){
      if(sel !== '.config-sidebar-item') return [];
      var items = [];
      var re = /<button type="button" class="config-sidebar-item( expert-only)?" data-cat="(\w+)"/g;
      var m;
      while((m = re.exec(_html))){
        items.push({ dataset:{cat:m[2]}, _expertOnly: !!m[1] });
      }
      return items;
    }
  };
}
var _bodyChildren = [];
var document = {
  getElementById: function(id){
    for(var i=0;i<_bodyChildren.length;i++){ if(_bodyChildren[i].id === id) return _bodyChildren[i]; }
    return null;
  },
  createElement: function(tag){ return makeFakeNav(); },
  body: { appendChild: function(el){ _bodyChildren.push(el); } }
};
"""


def _make_sidebar_ctx():
    ctx = py_mini_racer.MiniRacer()
    ctx.eval(_SIDEBAR_DOM_PREAMBLE)
    ctx.eval(_ICO_CONSTS_SRC)
    ctx.eval(_CONFIG_SECTIONS_SRC)
    ctx.eval(_EXPERT_ONLY_CATS_SRC)
    ctx.eval(_BUILDSIDEBAR_SRC)
    ctx.eval("buildConfigSidebar();")
    return ctx


def test_build_config_sidebar_genere_19_entrees():
    ctx = _make_sidebar_ctx()
    cats = json.loads(ctx.eval(
        "JSON.stringify(document.getElementById('configSidebar')"
        ".querySelectorAll('.config-sidebar-item').map(function(b){return b.dataset.cat;}))"))
    # 18 catégories + résumé. PowerGenius XL/ACOM fusionnés dans 'amp' le
    # 15/08/2026 (rejet du schéma 6b/6c par F4GLD) : ne sont plus des
    # entrées de sidebar séparées, d'où 19 au lieu des 21 précédentes.
    assert len(cats) == 19, "buildConfigSidebar() n'a pas généré les 19 entrées attendues (18 catégories + résumé)"
    assert cats[-1] == 'summary', "'summary' doit être la dernière entrée (après le séparateur)"


def test_build_config_sidebar_marque_exactement_les_3_categories_expert_only():
    """Reproduit précisément le scénario de régression cité par la revue
    (une faute de frappe dans _EXPERT_ONLY_CATS.has() ferait échouer CE
    test, alors qu'aucun test existant avant ce correctif ne l'aurait vu)."""
    ctx = _make_sidebar_ctx()
    flagged = set(json.loads(ctx.eval(
        "JSON.stringify(document.getElementById('configSidebar')"
        ".querySelectorAll('.config-sidebar-item')"
        ".filter(function(b){return b._expertOnly;})"
        ".map(function(b){return b.dataset.cat;}))")))
    assert flagged == {'relay', 'autostart', 'telemetry'}, (
        f"catégories marquées expert-only dans le HTML RÉELLEMENT généré : {flagged}")


def test_build_config_sidebar_contient_le_divider_et_le_bouton_logger():
    ctx = _make_sidebar_ctx()
    html = ctx.eval("document.getElementById('configSidebar')._rawHtml()")
    assert 'config-sidebar-divider' in html
    assert 'config-sidebar-launch' in html and "onclick=\"launchApp()\"" in html


def test_build_config_sidebar_est_idempotente():
    """Deuxième appel (garde `if(document.getElementById('configSidebar')) return;`)
    ne doit pas dupliquer le nœud ni relever d'exception."""
    ctx = _make_sidebar_ctx()
    ctx.eval("buildConfigSidebar();")
    count = ctx.eval("_bodyChildren.length")
    assert count == 1, "un 2e appel a créé un 2e nœud #configSidebar au lieu d'être un no-op"


def test_openCategoryPopup_ouvre_la_cible_et_ferme_la_precedente():
    ctx = _make_ctx()
    ctx.eval("openCategoryPopup('identity');")
    assert ctx.eval("_els.catmodal_identity.style.display") == 'block'
    assert ctx.eval("_currentOpenCat()") == 'identity'
    # Pas de modification depuis l'ouverture -> pas de confirm() sollicité.
    ctx.eval("openCategoryPopup('contest');")
    assert ctx.eval("_confirmCalls") == 0
    assert ctx.eval("_els.catmodal_identity.style.display") == 'none', (
        "openCategoryPopup() doit refermer la section précédente")
    assert ctx.eval("_els.catmodal_contest.style.display") == 'block'
    assert ctx.eval("_currentOpenCat()") == 'contest'


def test_switch_avec_modifications_non_enregistrees_et_refus_annule_tout():
    """Cas trouvé par la revue adversariale du 08/08/2026 (avant la refonte
    sidebar) : un refus de confirm() doit annuler la fermeture ET
    l'ouverture — pas seulement l'une des deux."""
    ctx = _make_ctx()
    ctx.eval("openCategoryPopup('identity');")
    ctx.eval("_inputsIdentity[0].value = 'F4MODIFIE';")  # édition non enregistrée
    ctx.eval("_confirmResult = false;")
    ctx.eval("openCategoryPopup('contest');")
    assert ctx.eval("_confirmCalls") == 1, "le garde doit solliciter confirm() une fois"
    assert ctx.eval("_els.catmodal_identity.style.display") == 'block', (
        "un refus doit laisser la section identity OUVERTE")
    assert ctx.eval("_els.catmodal_contest.style.display") == 'none', (
        "un refus ne doit PAS ouvrir la section cible")
    assert ctx.eval("_currentOpenCat()") == 'identity'


def test_switch_avec_modifications_non_enregistrees_et_acceptation_bascule():
    ctx = _make_ctx()
    ctx.eval("openCategoryPopup('identity');")
    ctx.eval("_inputsIdentity[0].value = 'F4MODIFIE';")
    ctx.eval("_confirmResult = true;")
    ctx.eval("openCategoryPopup('contest');")
    assert ctx.eval("_confirmCalls") == 1
    assert ctx.eval("_els.catmodal_identity.style.display") == 'none'
    assert ctx.eval("_els.catmodal_contest.style.display") == 'block'
    assert ctx.eval("_currentOpenCat()") == 'contest'


def test_summary_participe_a_currentOpenCat_comme_les_autres_categories():
    """'summary' (ex-popup Résumé séparée, catmodal_summary/openSummaryPopup)
    est désormais une entrée CONFIG_SECTIONS ordinaire — _currentOpenCat() et
    le garde de modifications non enregistrées doivent la traiter pareil
    qu'identity/contest/filters, plus de mécanisme parallèle."""
    ctx = _make_ctx()
    ctx.eval("openCategoryPopup('summary');")
    assert ctx.eval("_els.catmodal_summary.style.display") == 'block'
    assert ctx.eval("_currentOpenCat()") == 'summary'
    ctx.eval("openCategoryPopup('identity');")
    assert ctx.eval("_els.catmodal_summary.style.display") == 'none', (
        "quitter summary pour une autre catégorie doit la refermer comme "
        "n'importe quelle autre section")
    assert ctx.eval("_currentOpenCat()") == 'identity'


def test_rouvrir_la_meme_categorie_est_un_no_op_silencieux():
    """Cliquer sur l'entrée déjà active de l'arborescence ne doit ni
    solliciter confirm() ni la fermer puis rouvrir inutilement -- ET ne doit
    PAS effacer le marqueur de modifications non enregistrées (régression
    trouvée par la revue adversariale du 08/08/2026 : la ligne finale de
    openCategoryPopup() réécrivait _catFormSnapshots[cat] avec l'état
    COURANT même dans ce cas, rendant _catHasUnsavedChanges() aveugle à
    l'édition en cours dès le changement de section suivant)."""
    ctx = _make_ctx()
    ctx.eval("openCategoryPopup('identity');")
    ctx.eval("_inputsIdentity[0].value = 'F4MODIFIE';")
    ctx.eval("openCategoryPopup('identity');")
    assert ctx.eval("_confirmCalls") == 0
    assert ctx.eval("_els.catmodal_identity.style.display") == 'block'
    assert ctx.eval("_catHasUnsavedChanges('identity')") is True, (
        "réouvrir la MÊME catégorie a effacé le marqueur de modifications "
        "non enregistrées -- la perte de données ne sera plus jamais "
        "signalée, même en quittant ensuite vers une autre catégorie")


def test_rouvrir_la_meme_categorie_puis_changer_avertit_bien():
    """Scénario complet bout en bout du bug ci-dessus : édition -> re-clic
    sur la même entrée (réflexe/double-clic) -> clic vers une AUTRE
    catégorie doit toujours solliciter confirm(), pas seulement au moment
    du re-clic lui-même."""
    ctx = _make_ctx()
    ctx.eval("openCategoryPopup('identity');")
    ctx.eval("_inputsIdentity[0].value = 'F4MODIFIE';")
    ctx.eval("openCategoryPopup('identity');")  # re-clic sur l'entrée déjà active
    ctx.eval("_confirmResult = false;")
    ctx.eval("openCategoryPopup('contest');")
    assert ctx.eval("_confirmCalls") == 1, (
        "aucune confirmation sollicitée en quittant identity malgré une "
        "édition jamais enregistrée -- le re-clic précédent a fait perdre "
        "la trace de la modification")
    assert ctx.eval("_els.catmodal_identity.style.display") == 'block', (
        "le refus doit laisser identity ouverte (comme tout refus de "
        "changement de section avec modifications non enregistrées)")


# ─── closeCategoryPanel() : clic à côté / ✕ / Échap, direction LOGBOOK ──────
# REVIREMENT ASSUMÉ (16/08/2026, avec l'agrandissement du panneau en pleine
# page) : « dès que c'est fermé on doit revenir directement sur logbook » --
# closeCategoryPanel() naviguait AUPARAVANT sur place (retour F4GLD du
# 11/08/2026 : « je veux pas directement repartir dans logbook »), elle
# navigue maintenant vers logx_logbook.html, comme launchApp(). Seule règle
# qui SURVIT aux deux versions : « fermer ne sauvegarde jamais » (règle
# F4GLD du 04/08/2026 déjà documentée au-dessus de _catFormSnapshots) --
# c'est ce qui la distingue encore de launchApp() malgré la même destination.

def test_close_navigue_vers_logbook():
    ctx = _make_ctx()
    ctx.eval("openCategoryPopup('identity');")
    ctx.eval("closeCategoryPanel();")
    assert ctx.eval("window.location.href") == 'logx_logbook.html'


def test_close_sans_categorie_ouverte_navigue_quand_meme():
    """Plus un no-op depuis le revirement du 16/08/2026 : les 4 déclencheurs
    (clic à côté, ✕, Échap, LOGGER) doivent tous mener à LOGBOOK, qu'une
    catégorie soit ouverte ou non -- en pratique une catégorie est toujours
    ouverte par défaut (openCategoryPopup('identity') dans init()), mais rien
    ne doit dépendre de cet état pour se comporter correctement."""
    ctx = _make_ctx()
    ctx.eval("closeCategoryPanel();")
    assert ctx.eval("_confirmCalls") == 0, "rien à confirmer sans modification en cours"
    assert ctx.eval("window.location.href") == 'logx_logbook.html'


def test_close_avec_modifications_non_enregistrees_et_refus_ne_navigue_pas():
    """Même garde que le changement de section (_confirmDiscardCatChanges) --
    un refus doit annuler la navigation, pas naviguer quand même."""
    ctx = _make_ctx()
    ctx.eval("openCategoryPopup('identity');")
    ctx.eval("_inputsIdentity[0].value = 'F4MODIFIE';")
    ctx.eval("_confirmResult = false;")
    ctx.eval("closeCategoryPanel();")
    assert ctx.eval("_confirmCalls") == 1
    assert ctx.eval("window.location.href") == '', "un refus ne doit déclencher aucune navigation"
    assert ctx.eval("_currentOpenCat()") == 'identity', "un refus doit laisser identity ouverte"


def test_close_avec_modifications_non_enregistrees_et_acceptation_navigue():
    ctx = _make_ctx()
    ctx.eval("openCategoryPopup('identity');")
    ctx.eval("_inputsIdentity[0].value = 'F4MODIFIE';")
    ctx.eval("_confirmResult = true;")
    ctx.eval("closeCategoryPanel();")
    assert ctx.eval("_confirmCalls") == 1
    assert ctx.eval("window.location.href") == 'logx_logbook.html'


def test_close_navigue_mais_ne_sauvegarde_jamais():
    """Vérification directe du texte source : closeCategoryPanel() doit
    naviguer (contrairement à sa version du 11/08/2026) mais ne doit
    toujours contenir aucun appel à saveConfig() -- c'est cette dernière
    règle, pas l'absence de navigation, qui la distingue de launchApp()."""
    assert 'window.location' in _CLOSECATPANEL_SRC
    assert 'saveConfig(' not in _CLOSECATPANEL_SRC
