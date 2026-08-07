# -*- coding: utf-8 -*-
"""Écran d'accueil (première visite de CONFIG) : deux questions -- niveau
(débutant/expert, via l'expérience préalable d'un logiciel de log/concours)
et usage visé (mappé sur le sélecteur MODE D'UTILISATION déjà existant).

Avant ce lot, getUiMode() devinait le niveau en SILENCE (aucun indicatif
configuré -> débutant, sinon expert) -- ce module rend la question EXPLICITE,
posée une seule fois (jamais reposée une fois rc_ui_mode présent en
localStorage, que ce soit par cet écran ou par une visite antérieure à son
ajout). Demandé par F4GLD (07/08/2026) : "il faudra ameliorer l'intuitivite
au maximum... peutetre mettre en place a la premiere ouverture 2-3 questions
pour connaitre le niveau et le passer en mode expert ou debutant".

Ce module exécute le VRAI code de onbPick()/submitOnboarding()/
skipOnboarding()/maybeShowOnboarding() -- extrait tel quel du fichier source
par comptage d'accolades, même technique que
tests/test_config_popup_backdrop_click.py -- dans un moteur JS réel
(V8 via py_mini_racer)."""
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


def _extract_const(src, name):
    """Extrait `const <name> = {...};` — même motif que _extract_function
    mais pour une déclaration de variable au lieu d'une fonction."""
    m = re.search(r'^const %s = \{' % re.escape(name), src, re.M)
    assert m, 'const %s introuvable dans %s' % (name, HTML_PATH)
    depth = 0
    i = src.index('{', m.start())
    while True:
        c = src[i]
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                return src[m.start():i + 2]  # inclut le ';' qui suit '}'
        i += 1


with open(HTML_PATH, encoding='utf-8') as _f:
    _HTML_SRC = _f.read()

_ONBSTATE_SRC = _extract_const(_HTML_SRC, '_onbState')
_ONBPICK_SRC = _extract_function(_HTML_SRC, 'onbPick')
_CLOSEONB_SRC = _extract_function(_HTML_SRC, '_closeOnboarding')
_SUBMITONB_SRC = _extract_function(_HTML_SRC, 'submitOnboarding')
_SKIPONB_SRC = _extract_function(_HTML_SRC, 'skipOnboarding')
_MAYBESHOWONB_SRC = _extract_function(_HTML_SRC, 'maybeShowOnboarding')


def test_onboarding_cablee_dans_init_avant_applyUiMode():
    """Garde-fou de câblage : sans le `await maybeShowOnboarding()` en tête
    d'init(), l'écran serait défini mais jamais montré au bon moment (avant
    que le reste de la page ne s'appuie sur rc_ui_mode/usage_mode)."""
    m = re.search(r'^async function init\(\) \{', _HTML_SRC, re.M)
    assert m, 'init() introuvable'
    bloc = _HTML_SRC[m.start():m.start() + 400]
    assert 'await maybeShowOnboarding()' in bloc
    # Dans l'ORDRE : avant applyUiMode(), pas après (sinon un premier rendu
    # se ferait sur le niveau devine par erreur avant que la question soit posee).
    assert bloc.index('maybeShowOnboarding') < bloc.index('applyUiMode')


# ─── DOM minimal ──────────────────────────────────────────────────────────────

_DOM_PREAMBLE = r"""
function makeChoiceBtn(onclickAttr){
  var cls = new Set();
  return {
    _onclick: onclickAttr,
    getAttribute: function(name){ return name === 'onclick' ? this._onclick : null; },
    classList: {
      toggle: function(c, force){
        var on = (force !== undefined) ? force : !cls.has(c);
        if (on) cls.add(c); else cls.delete(c);
        return on;
      },
      contains: function(c){ return cls.has(c); },
    },
  };
}

var _expBtns = [
  makeChoiceBtn("onbPick('experience','non')"),
  makeChoiceBtn("onbPick('experience','oui')"),
];
var _usageBtns = [
  makeChoiceBtn("onbPick('usage','simple')"),
  makeChoiceBtn("onbPick('usage','contest')"),
  makeChoiceBtn("onbPick('usage','expedition')"),
  makeChoiceBtn("onbPick('usage','radioclub')"),
];

var _usageModeSel = { value: 'contest' };
var _startBtn = { disabled: true };
var _overlay = { style: { display: 'none' } };

var onUsageModeChangeCalls = 0;
function onUsageModeChange(){ onUsageModeChangeCalls++; }

var _localStorageStore = {};
var localStorage = {
  getItem: function(k){ return (k in _localStorageStore) ? _localStorageStore[k] : null; },
  setItem: function(k, v){ _localStorageStore[k] = String(v); },
  removeItem: function(k){ delete _localStorageStore[k]; },
};

var document = {
  getElementById: function(id){
    if (id === 'onboardingOverlay') return _overlay;
    if (id === 'onbStartBtn') return _startBtn;
    if (id === 'usage_mode') return _usageModeSel;
    return null;
  },
  querySelectorAll: function(sel){
    if (sel === '#onbExperienceChoices .onb-choice') return _expBtns;
    if (sel === '#onbUsageChoices .onb-choice') return _usageBtns;
    return [];
  },
};
"""


def _make_ctx():
    ctx = py_mini_racer.MiniRacer()
    ctx.eval(_DOM_PREAMBLE)
    ctx.eval(_ONBSTATE_SRC)
    ctx.eval(_ONBPICK_SRC)
    ctx.eval(_CLOSEONB_SRC)
    ctx.eval(_SUBMITONB_SRC)
    ctx.eval(_SKIPONB_SRC)
    ctx.eval(_MAYBESHOWONB_SRC)
    return ctx


# ─── onbPick() : sélection visuelle + activation du bouton ──────────────────

def test_onbPick_marque_le_bon_choix_selectionne():
    ctx = _make_ctx()
    ctx.eval("onbPick('experience', 'oui');")
    assert ctx.eval("_expBtns[1].classList.contains('selected')") is True
    assert ctx.eval("_expBtns[0].classList.contains('selected')") is False


def test_onbPick_rebascule_la_selection_precedente_du_meme_groupe():
    """Un second clic sur l'AUTRE choix du même groupe doit désélectionner
    le premier -- sinon les deux resteraient visuellement cochés."""
    ctx = _make_ctx()
    ctx.eval("onbPick('experience', 'non');")
    ctx.eval("onbPick('experience', 'oui');")
    assert ctx.eval("_expBtns[0].classList.contains('selected')") is False
    assert ctx.eval("_expBtns[1].classList.contains('selected')") is True


def test_bouton_commencer_reste_desactive_tant_que_les_deux_questions_ne_sont_pas_repondues():
    ctx = _make_ctx()
    ctx.eval("onbPick('experience', 'oui');")
    assert ctx.eval("_startBtn.disabled") is True, (
        'la question usage n\'a pas encore de réponse -- le bouton doit rester désactivé')
    ctx.eval("onbPick('usage', 'contest');")
    assert ctx.eval("_startBtn.disabled") is False


# ─── submitOnboarding() : applique le niveau + l'usage choisis ──────────────

def test_submit_oui_pose_le_mode_expert():
    ctx = _make_ctx()
    ctx.eval("onbPick('experience', 'oui'); onbPick('usage', 'contest'); submitOnboarding();")
    assert ctx.eval("localStorage.getItem('rc_ui_mode')") == 'expert'


def test_submit_non_pose_le_mode_simple():
    ctx = _make_ctx()
    ctx.eval("onbPick('experience', 'non'); onbPick('usage', 'contest'); submitOnboarding();")
    assert ctx.eval("localStorage.getItem('rc_ui_mode')") == 'simple'


def test_submit_reporte_lusage_choisi_sur_le_selecteur_existant():
    """La question 2 n'est pas une question redondante : elle POSE
    directement la valeur du sélecteur MODE D'UTILISATION déjà présent plus
    bas dans la page -- pas de second choix à refaire."""
    ctx = _make_ctx()
    ctx.eval("onbPick('experience', 'oui'); onbPick('usage', 'expedition'); submitOnboarding();")
    assert ctx.eval("_usageModeSel.value") == 'expedition'
    assert ctx.eval("onUsageModeChangeCalls") == 1, (
        'onUsageModeChange() doit être rappelée -- sinon les champs dépendants '
        '(ex. saisie simplifiée en expédition) ne se mettent pas à jour')


def test_submit_ferme_lecran():
    ctx = _make_ctx()
    ctx.eval("_overlay.style.display = 'flex';")
    ctx.eval("onbPick('experience', 'oui'); onbPick('usage', 'contest'); submitOnboarding();")
    assert ctx.eval("_overlay.style.display") == 'none'


def test_submit_sans_reponse_ne_fait_rien():
    """Filet de sécurité si submitOnboarding() était appelée autrement que
    par le bouton (déjà désactivé tant que non répondu) : ne doit RIEN
    écrire ni fermer l'écran plutôt que de figer un niveau au hasard."""
    ctx = _make_ctx()
    ctx.eval("submitOnboarding();")
    assert ctx.eval("localStorage.getItem('rc_ui_mode')") is None
    assert ctx.eval("_overlay.style.display") == 'none'   # état initial du mock, inchangé


# ─── skipOnboarding() : ferme SANS rien figer ────────────────────────────────

def test_skip_ferme_sans_poser_rc_ui_mode():
    """« Passer » doit laisser getUiMode() retomber sur son heuristique
    existante (silencieuse) -- jamais forcer une valeur au hasard."""
    ctx = _make_ctx()
    ctx.eval("_overlay.style.display = 'flex';")
    ctx.eval("skipOnboarding();")
    assert ctx.eval("localStorage.getItem('rc_ui_mode')") is None
    assert ctx.eval("_overlay.style.display") == 'none'
    assert ctx.eval("_usageModeSel.value") == 'contest', (
        'passer ne doit pas non plus toucher au sélecteur usage_mode')


# ─── maybeShowOnboarding() : Promise résolue par submit/skip, jamais reposée ─

def test_maybeShowOnboarding_attend_que_lecran_soit_repondu():
    ctx = _make_ctx()
    ctx.eval("var resolved = false;")
    ctx.eval("maybeShowOnboarding().then(function(){ resolved = true; });")
    # L'écran doit s'être ouvert...
    assert ctx.eval("_overlay.style.display") == 'flex'
    # ...et la promesse ne doit PAS s'être résolue toute seule.
    assert ctx.eval("resolved") is False

    ctx.eval("onbPick('experience', 'oui'); onbPick('usage', 'contest'); submitOnboarding();")
    ctx.eval("undefined")  # laisse le microtask queue de la promesse se vider
    assert ctx.eval("resolved") is True


def test_maybeShowOnboarding_se_resout_immediatement_si_deja_repondu():
    """Une visite ultérieure (rc_ui_mode déjà en localStorage, qu'il vienne
    de cet écran ou de l'ancienne heuristique silencieuse) ne doit JAMAIS
    rouvrir l'écran d'accueil."""
    ctx = _make_ctx()
    ctx.eval("localStorage.setItem('rc_ui_mode', 'expert');")
    ctx.eval("var resolved = false;")
    ctx.eval("maybeShowOnboarding().then(function(){ resolved = true; });")
    ctx.eval("undefined")
    assert ctx.eval("resolved") is True
    assert ctx.eval("_overlay.style.display") == 'none', (
        "l'écran ne doit jamais s'ouvrir quand rc_ui_mode existe déjà")


def test_maybeShowOnboarding_se_resout_apres_un_skip():
    ctx = _make_ctx()
    ctx.eval("var resolved = false;")
    ctx.eval("maybeShowOnboarding().then(function(){ resolved = true; });")
    ctx.eval("skipOnboarding();")
    ctx.eval("undefined")
    assert ctx.eval("resolved") is True
