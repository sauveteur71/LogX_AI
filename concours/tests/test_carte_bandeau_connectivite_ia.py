# -*- coding: utf-8 -*-
"""Bandeau de connectivité IA persistant sur CARTE IA (logx_carte.html) --
tâche de backlog #117 (refonte CARTE IA, phase 2+ : "repli auto hors-ligne,
bandeau de connectivité"). Le repli hors-ligne lui-même (offlineFallback())
existait déjà et fonctionne, mais réagissait seulement APRÈS un échec IA,
via un badge DANS la bulle de réponse -- aucun bandeau persistant, et aucune
détection PROACTIVE d'une coupure réseau (navigator.onLine).

_setAiOffline() centralise l'état sur 2 déclencheurs (évènements
online/offline du navigateur, et offlineFallback() lors d'un échec IA) et
1 seule résolution (finalizeAgentReply(), commun à tous les chemins de
succès IA) plutôt que de dupliquer l'état sur chacun des 6 sites d'appel à
offlineFallback().

Ce module exécute le VRAI code extrait du fichier source (comptage
d'accolades, même technique que tests/test_carte_applyconfig_avertissement.py)
dans un moteur JS réel (V8 via py_mini_racer), pas une réécriture qui
pourrait diverger.
"""
import os
import re

import pytest

py_mini_racer = pytest.importorskip(
    'py_mini_racer', reason='py_mini_racer absent (voir requirements.txt) — test JS réel ignoré')

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML_PATH = os.path.join(BASE, 'logx_carte.html')

with open(HTML_PATH, encoding='utf-8') as _f:
    _SRC = _f.read()


def _extract_function(src, name):
    """Extrait `[async ]function <name>(...){...}` par comptage d'accolades."""
    m = re.search(r'^(?:async )?function %s\(' % re.escape(name), src, re.M)
    assert m, 'fonction %s introuvable dans %s' % (name, HTML_PATH)
    i = src.index('{', m.start())
    depth = 0
    while True:
        c = src[i]
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                return src[m.start():i + 1]
        i += 1


_SET_AI_OFFLINE_SRC = _extract_function(_SRC, '_setAiOffline')
_OFFLINE_FALLBACK_SRC = _extract_function(_SRC, 'offlineFallback')
_FINALIZE_REPLY_SRC = _extract_function(_SRC, 'finalizeAgentReply')

# DOM minimal : juste ce dont _setAiOffline()/offlineFallback()/
# finalizeAgentReply() ont besoin. basiqueAnswer/parseScores/
# refreshRankedStations/addSpeakIcon sont stubbés -- ce ne sont pas l'objet
# de ce test, seuls _setAiOffline()/offlineFallback()/finalizeAgentReply()
# doivent être du VRAI code.
_PREAMBLE = r"""
var __navigatorOnLine = true;
var navigator = { get onLine(){ return __navigatorOnLine; } };
function _makeClassList(el){
  return {
    add: function(c){ if(el._classes.indexOf(c)===-1) el._classes.push(c); },
    remove: function(c){ var i=el._classes.indexOf(c); if(i!==-1) el._classes.splice(i,1); },
    contains: function(c){ return el._classes.indexOf(c) !== -1; }
  };
}
var _els = {
  aiConnectivityBanner: {_classes: []},
  aiConnectivityBannerText: {textContent: ''},
  chatMsgs: {scrollTop: 0, scrollHeight: 0}
};
Object.keys(_els).forEach(function(id){ _els[id].classList = _makeClassList(_els[id]); });
var document = {
  getElementById: function(id){ return _els[id] || null; }
};
var __listeners = {};
window = {
  addEventListener: function(evt, fn){ __listeners[evt] = fn; }
};
function rcT(s){ return s; }

// Stubs des dépendances de offlineFallback()/finalizeAgentReply() -- non
// testées ici, seul l'appel à _setAiOffline() doit être vérifié.
var __basiqueAnswerCalls = [];
function basiqueAnswer(topic, bub, badge){ __basiqueAnswerCalls.push({topic: topic}); return true; }
function offlineBadge(){ return {}; }
var conversationHistory = [];
function parseScores(){}
function refreshRankedStations(){}
function addSpeakIcon(){}
"""


def _make_ctx():
    ctx = py_mini_racer.MiniRacer()
    ctx.eval(_PREAMBLE)
    ctx.eval(_SET_AI_OFFLINE_SRC)
    ctx.eval(_OFFLINE_FALLBACK_SRC)
    ctx.eval(_FINALIZE_REPLY_SRC)
    return ctx


def _banner_shown(ctx):
    return ctx.eval("_els.aiConnectivityBanner._classes.indexOf('show')") != -1


def _banner_text(ctx):
    return ctx.eval("_els.aiConnectivityBannerText.textContent")


# ─── _setAiOffline() : le cœur du mécanisme ────────────────────────────────

def test_set_ai_offline_true_affiche_le_bandeau_avec_le_message():
    ctx = _make_ctx()
    ctx.eval("_setAiOffline(true, 'Pas de connexion réseau');")
    assert _banner_shown(ctx)
    assert _banner_text(ctx) == 'Pas de connexion réseau'


def test_set_ai_offline_true_sans_message_utilise_le_repli_par_defaut():
    ctx = _make_ctx()
    ctx.eval("_setAiOffline(true);")
    assert _banner_shown(ctx)
    assert _banner_text(ctx), 'un message par défaut doit être affiché'


def test_set_ai_offline_false_masque_le_bandeau():
    ctx = _make_ctx()
    ctx.eval("_setAiOffline(true, 'x'); _setAiOffline(false);")
    assert not _banner_shown(ctx)


# ─── offlineFallback() : déclenche le bandeau (échec IA) ───────────────────

def test_offline_fallback_declenche_le_bandeau():
    ctx = _make_ctx()
    ctx.eval("offlineFallback('score', {});")
    assert _banner_shown(ctx)
    assert 'IA' in _banner_text(ctx)


def test_offline_fallback_delegue_toujours_a_basique_answer():
    """Le bandeau est un AJOUT -- le vrai repli déterministe existant
    (basiqueAnswer) ne doit ni être court-circuité, ni recevoir d'argument
    différent de before."""
    ctx = _make_ctx()
    ctx.eval("offlineFallback('score', {});")
    calls = ctx.eval("JSON.stringify(__basiqueAnswerCalls)")
    assert '"topic":"score"' in calls


# ─── finalizeAgentReply() : résout le bandeau (succès IA) ──────────────────

def test_finalize_agent_reply_masque_le_bandeau():
    ctx = _make_ctx()
    ctx.eval("_setAiOffline(true, 'IA indisponible');")
    assert _banner_shown(ctx)
    ctx.eval("var bub = {classList: _makeClassList({_classes: []})};"
              "finalizeAgentReply(bub, 'Réponse normale');")
    assert not _banner_shown(ctx)


def test_finalize_agent_reply_ne_leve_pas_quand_deja_en_ligne():
    """Le chemin nominal (jamais passé par un repli) appelle aussi
    finalizeAgentReply() à chaque réponse -- _setAiOffline(false) doit être
    un no-op silencieux dans ce cas, pas une erreur."""
    ctx = _make_ctx()
    ctx.eval("var bub = {classList: _makeClassList({_classes: []})};"
              "finalizeAgentReply(bub, 'Réponse normale');")
    assert not _banner_shown(ctx)
