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

_OPENCAT_SRC = _extract_function(_HTML_SRC, 'openCategoryPopup')
_CURRENTOPENCAT_SRC = _extract_function(_HTML_SRC, '_currentOpenCat')
_SNAPSHOTCATFORM_SRC = _extract_function(_HTML_SRC, '_snapshotCatForm')
_CATHASUNSAVED_SRC = _extract_function(_HTML_SRC, '_catHasUnsavedChanges')
_CONFIRMDISCARD_SRC = _extract_function(_HTML_SRC, '_confirmDiscardCatChanges')

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

var _els = {
  catmodal_identity: makeModalEl('catmodal_identity', 'none'),
  catmodal_contest:  makeModalEl('catmodal_contest', 'none'),
  catmodal_filters:  makeModalEl('catmodal_filters', 'none'),
  catmodal_summary:  makeModalEl('catmodal_summary', 'none'),
  catbody_identity:  makeCatBody('catbody_identity', _inputsIdentity),
  catbody_contest:   makeCatBody('catbody_contest', _inputsContest),
  catbody_filters:   makeCatBody('catbody_filters', _inputsFilters),
  catbody_summary:   makeCatBody('catbody_summary', _inputsSummary),
};

var document = {
  getElementById: function(id){ return (id in _els) ? _els[id] : null; },
  querySelectorAll: function(){ return []; }
};

var _catFormSnapshots = {};
var _confirmResult = true;
var _confirmCalls = 0;
function confirm(msg){ _confirmCalls++; return _confirmResult; }
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
    return ctx


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
    solliciter confirm() ni la fermer puis rouvrir inutilement."""
    ctx = _make_ctx()
    ctx.eval("openCategoryPopup('identity');")
    ctx.eval("_inputsIdentity[0].value = 'F4MODIFIE';")
    ctx.eval("openCategoryPopup('identity');")
    assert ctx.eval("_confirmCalls") == 0
    assert ctx.eval("_els.catmodal_identity.style.display") == 'block'
