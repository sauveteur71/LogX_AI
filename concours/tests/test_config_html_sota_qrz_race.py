# -*- coding: utf-8 -*-
"""connectSota() / testQrzLogbook() (concours/logx_configuration.html, commit
1720e6b) sauvegardaient la config (saveConfig(true), fire-and-forget) puis
utilisaient IMMÉDIATEMENT le résultat côté serveur (ouverture de la fenêtre
OAuth SOTA, ou appel /qrz_logbook/test) SANS attendre que le serveur ait
effectivement reçu cette config — contrairement à testVoiceKeyer(), qui a
déjà le bon pattern (saveConfig(true); await _lastConfigSavePromise;) plus
loin dans le même fichier.

Scénario concret reproduit : un opérateur tape un nouveau clientId/une
nouvelle clé API puis clique tout de suite sur « Se connecter à SOTA » /
« Tester ». Si l'ouverture de la fenêtre OAuth (ou l'appel réseau de test)
part avant que /config/save ait fini, le serveur peut encore avoir l'ANCIEN
clientId/l'ancienne clé au moment où il en a besoin (course entre les deux
requêtes réseau).

Ce module exécute le VRAI code de connectSota()/testQrzLogbook() — extrait
tel quel du fichier source par comptage d'accolades, pas retapé — dans un
moteur JS réel (V8 via py_mini_racer, même technique que
tests/test_qtc_panel_js.py et tests/test_logbook_render_window_reset.py),
avec saveConfig()/_lastConfigSavePromise remplacés par un mock qui simule un
/config/save asynchrone contrôlable (on décide nous-même quand le serveur
"reçoit" la config), pour rendre la course reproductible de façon fiable
plutôt que de dépendre du timing réel du réseau."""
import os
import re

import pytest

py_mini_racer = pytest.importorskip(
    'py_mini_racer', reason='py_mini_racer absent (voir requirements.txt) — test JS réel ignoré')

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML_PATH = os.path.join(BASE, 'logx_configuration.html')


def _extract_function(src, name):
    """Extrait le texte complet `async function <name>(){...}` par comptage
    d'accolades (aucune des deux fonctions ciblées ne contient de `{`/`}`
    dans une chaîne ou un commentaire — vérifié à la main) : on récupère le
    VRAI code du fichier, pas une réécriture qui pourrait diverger du bug."""
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


with open(HTML_PATH, encoding='utf-8') as _f:
    _HTML_SRC = _f.read()

_CONNECT_SOTA_SRC = _extract_function(_HTML_SRC, 'connectSota')
_TEST_QRZ_LOGBOOK_SRC = _extract_function(_HTML_SRC, 'testQrzLogbook')

# Les deux fonctions doivent contenir le pattern déjà établi par
# testVoiceKeyer() plus loin dans le même fichier — vérifié explicitement
# (et pas seulement via l'exécution ci-dessous) pour que ce test échoue de
# façon lisible si le await disparaît un jour d'un refactor.
assert 'await _lastConfigSavePromise' in _CONNECT_SOTA_SRC
assert 'await _lastConfigSavePromise' in _TEST_QRZ_LOGBOOK_SRC

# ─── DOM minimal (Proxy permissif, voir tests/test_qtc_panel_js.py) ──────────
_DOM_PREAMBLE = r"""
var __store = {};
function ElProxy(){
  var s = {value:'', textContent:'', innerHTML:'', style:{}, checked:false, disabled:false};
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
var window = this;
function setTimeout(){ return 0; }
function alert(){}
"""


def _make_ctx(extra_fn_src):
    ctx = py_mini_racer.MiniRacer()
    ctx.eval(_DOM_PREAMBLE)
    ctx.eval(extra_fn_src)
    return ctx


# ─── connectSota() ────────────────────────────────────────────────────────────

def test_connectSota_attend_la_sauvegarde_avant_douvrir_la_fenetre_oauth():
    ctx = _make_ctx(_CONNECT_SOTA_SRC)
    ctx.eval(r"""
    // Simule /config/save : asynchrone, contrôlable depuis le test (on décide
    // nous-même du moment où le "serveur" a fini de recevoir la config).
    var serverClientId = 'STALE';
    var resolveSave = null;
    var saveConfigCalls = 0;
    function saveConfig(silent){
      saveConfigCalls++;
      _lastConfigSavePromise = new Promise(function(resolve){
        resolveSave = function(){
          serverClientId = document.getElementById('sota_client_id').value;
          resolve();
        };
      });
      return true;
    }
    var _lastConfigSavePromise = Promise.resolve();
    var openedWithClientId = null;
    window.open = function(){ openedWithClientId = serverClientId; return {}; };
    function refreshSotaStatus(){}

    document.getElementById('sota_client_id').value = 'NEWID';
    """)
    ctx.eval("connectSota();")
    # saveConfig(true) a été appelé de façon synchrone...
    assert ctx.eval("saveConfigCalls") == 1
    # ...mais la fenêtre OAuth ne doit PAS s'être ouverte avant que le
    # "serveur" ait fini de recevoir le nouveau clientId : sans le
    # `await _lastConfigSavePromise`, window.open() serait déjà appelé ICI,
    # avec le serveur encore sur l'ANCIEN clientId ('STALE').
    assert ctx.eval("openedWithClientId") is None

    # Le "serveur" reçoit enfin la config sauvegardée.
    ctx.eval("resolveSave();")
    ctx.eval("undefined")  # laisse le microtask queue de la promesse se vider

    assert ctx.eval("openedWithClientId") == 'NEWID'


# ─── testQrzLogbook() ─────────────────────────────────────────────────────────

def test_testQrzLogbook_attend_la_sauvegarde_avant_dappeler_le_serveur():
    ctx = _make_ctx(_TEST_QRZ_LOGBOOK_SRC)
    ctx.eval(r"""
    var serverKey = 'STALE-KEY';
    var resolveSave = null;
    var saveConfigCalls = 0;
    function saveConfig(silent){
      saveConfigCalls++;
      _lastConfigSavePromise = new Promise(function(resolve){
        resolveSave = function(){
          serverKey = document.getElementById('qrz_logbook_key').value;
          resolve();
        };
      });
      return true;
    }
    var _lastConfigSavePromise = Promise.resolve();
    var fetchedWithKey = null;
    function fetch(url, opts){
      fetchedWithKey = serverKey;
      return Promise.resolve({ json: function(){ return Promise.resolve({ok:true}); } });
    }

    document.getElementById('qrz_logbook_key').value = 'NEWKEY';
    """)
    ctx.eval("testQrzLogbook();")
    assert ctx.eval("saveConfigCalls") == 1
    # Sans le await, fetch('/qrz_logbook/test') serait déjà parti ICI avec le
    # serveur encore sur l'ancienne clé ('STALE-KEY').
    assert ctx.eval("fetchedWithKey") is None

    ctx.eval("resolveSave();")
    ctx.eval("undefined")

    assert ctx.eval("fetchedWithKey") == 'NEWKEY'


def test_pas_de_qso_director():
    """Interdiction absolue (nom d'un concurrent) — jamais dans le code."""
    assert 'QSO Director' not in _HTML_SRC
