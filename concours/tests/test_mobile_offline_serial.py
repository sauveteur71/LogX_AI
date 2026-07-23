# -*- coding: utf-8 -*-
"""Revue adversariale du commit b783405 (« Parité mobile : scoring serveur,
n° de série centralisé, file hors-ligne ») — trois défauts vérifiés sur
logx_mobile.html :

1) trySendQso() confondait « réseau injoignable » et « réponse HTTP reçue
   mais non-ok » : `return res.ok ? 'ok' : 'queue'` traitait un 400 (erreur
   serveur légitime, ex. requête malformée) EXACTEMENT comme une coupure
   réseau — mis en file d'attente hors-ligne et retenté silencieusement
   toutes les 5s, sans jamais afficher le message d'erreur réel à
   l'opérateur.

2) refreshSuggestedSerial() appelait /log/next_serial — qui ALLOUE réellement
   (voir logx_storage.allocate_next_serial) — à chaque rafraîchissement
   d'écran (changement de bande, après chaque QSO, chargement de page) juste
   pour PRÉ-REMPLIR une suggestion : chaque interaction UI brûlait un numéro
   même si aucun QSO n'était jamais soumis avec.

3) syncOfflineQueue() (resynchronisation de la file hors-ligne) renvoyait le
   numéro de série déjà choisi localement sans jamais le renégocier — une
   collision entre deux postes restait possible précisément dans le scénario
   terrain (un poste hors ligne pendant qu'un autre logue réellement sur la
   même bande) que ce commit dit corriger.

Ce module exécute le VRAI script de logx_mobile.html dans un moteur JS réel
(V8 via py_mini_racer), avec un DOM/fetch minimal, pour reproduire chaque
scénario concrètement plutôt que de grepper une chaîne dans le fichier
(même approche que tests/test_logbook_render_window_reset.py pour
logx_logbook.js)."""
import json
import os
import re

import pytest

py_mini_racer = pytest.importorskip(
    'py_mini_racer', reason='py_mini_racer absent (voir requirements.txt) — test JS réel ignoré')

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML_PATH = os.path.join(BASE, 'logx_mobile.html')

# ─── DOM minimal ──────────────────────────────────────────────────────────────
# logx_mobile.html est un script de page (pas un module) : Proxy générique
# pour les éléments DOM (getElementById), comme dans test_logbook_render_
# window_reset.py — évite d'avoir à lister tous les id du fichier.
_DOM_PREAMBLE = r"""
var __store = {};
function ElProxy(){
  var s = {value:'', textContent:'', innerHTML:'', style:{}, checked:false, disabled:false};
  var cls = {_s:new Set(), add:function(){for(var i=0;i<arguments.length;i++) this._s.add(arguments[i]);},
             remove:function(){for(var i=0;i<arguments.length;i++) this._s.delete(arguments[i]);},
             contains:function(c){return this._s.has(c);},
             toggle:function(c){ if(this._s.has(c)) this._s.delete(c); else this._s.add(c); return this._s.has(c);}};
  var handler = {
    get:function(target, prop){
      if(prop === 'classList') return cls;
      if(prop === 'style') return s.style;
      if(prop === 'focus') return function(){};
      if(prop === 'addEventListener') return function(){};
      return s[prop];
    },
    set:function(target, prop, val){ s[prop] = val; return true; }
  };
  return new Proxy({}, handler);
}
var document = {
  getElementById: function(id){ if(!__store[id]) __store[id] = ElProxy(); return __store[id]; },
  body: ElProxy(),
  addEventListener: function(){},
};
var window = this;
window.addEventListener = function(){};
function setInterval(){ return 0; }
function setTimeout(){ return 0; }
function clearInterval(){}
function clearTimeout(){}
var localStorage = {
  _d:{}, getItem:function(k){ return (k in this._d)? this._d[k] : null; },
  setItem:function(k,v){ this._d[k]=String(v); }, removeItem:function(k){ delete this._d[k]; }
};
// Repli par défaut (réponse jamais ok) — chaque test remplace `fetch` par le
// scénario qu'il veut vérifier.
function fetch(url, opts){
  return Promise.resolve({ ok:false, status:0, json:function(){ return Promise.resolve({}); } });
}
function confirm(){ return true; }
var navigator = { serviceWorker: { register: function(){ return Promise.resolve({}); } } };
"""


def _extract_main_script(html):
    """Le plus long bloc <script> inline de la page — le petit bloc
    d'enregistrement du service worker (tout début du <head>) n'est qu'une
    ligne, sans rapport avec ce qui est testé ici."""
    blocks = re.findall(r'<script[^>]*>(.*?)</script>', html, re.DOTALL)
    return max(blocks, key=len)


def _make_ctx():
    with open(HTML_PATH, encoding='utf-8') as f:
        html = f.read()
    ctx = py_mini_racer.MiniRacer()
    ctx.eval(_DOM_PREAMBLE)
    ctx.eval(_extract_main_script(html))
    return ctx


def _call_async(ctx, js_call):
    """Exécute un appel à une fonction async du script et renvoie sa valeur
    de résolution. JSON.stringify + json.loads plutôt que le retour brut de
    ctx.eval() : un JSObject de py_mini_racer n'est pas subscriptable."""
    ctx.eval(f"""
    var __out = undefined;
    ({js_call}).then(function(r){{ __out = (r === undefined ? null : r); }});
    """)
    return json.loads(ctx.eval('JSON.stringify(__out)'))


# ─── Problème 1 : trySendQso() doit distinguer réseau/5xx (retry) d'un 4xx
# définitif (message réel, jamais mis en file) ────────────────────────────────

def test_trysendqso_reseau_injoignable_renvoie_queue():
    ctx = _make_ctx()
    ctx.eval("fetch = function(){ return Promise.reject(new Error('down')); };")
    result = _call_async(ctx, "trySendQso({call:'F4TEST', band:'14'})")
    assert result['outcome'] == 'queue'


def test_trysendqso_erreur_serveur_5xx_renvoie_queue():
    """Erreur serveur TRANSITOIRE (5xx) : à retenter, comme une coupure réseau."""
    ctx = _make_ctx()
    ctx.eval("""
    fetch = function(){ return Promise.resolve({ ok:false, status:503,
      json:function(){ return Promise.resolve({error:'indisponible'}); } }); };
    """)
    result = _call_async(ctx, "trySendQso({call:'F4TEST', band:'14'})")
    assert result['outcome'] == 'queue'


def test_trysendqso_erreur_definitive_400_nest_plus_mise_en_file():
    """Reproduction directe du bug : avant ce correctif,
    `return res.ok ? 'ok' : 'queue'` traitait ce 400 EXACTEMENT comme la
    coupure réseau ci-dessus — jamais affiché à l'opérateur, silencieusement
    mis en file et retenté toutes les 5s."""
    ctx = _make_ctx()
    ctx.eval("""
    fetch = function(){ return Promise.resolve({ ok:false, status:400,
      json:function(){ return Promise.resolve({error:'Indicatif invalide'}); } }); };
    """)
    result = _call_async(ctx, "trySendQso({call:'F4TEST', band:'14'})")
    assert result['outcome'] == 'error'
    assert result['message'] == 'Indicatif invalide'


def test_trysendqso_ok_inchange():
    ctx = _make_ctx()
    ctx.eval("""
    fetch = function(){ return Promise.resolve({ ok:true, status:200,
      json:function(){ return Promise.resolve({}); } }); };
    """)
    result = _call_async(ctx, "trySendQso({call:'F4TEST', band:'14'})")
    assert result['outcome'] == 'ok'


# ─── Problème 2 : le simple aperçu (peek) ne doit jamais consommer le compteur ─

def test_refresh_suggested_serial_utilise_le_mode_peek():
    """refreshSuggestedSerial() est appelée à chaque changement de bande,
    après chaque QSO et au chargement de page — bien plus souvent qu'un QSO
    n'est réellement soumis. Elle doit toujours utiliser peek=1 (qui ne
    consomme pas le compteur, voir logx_storage.peek_next_serial), jamais une
    allocation réelle."""
    ctx = _make_ctx()
    ctx.eval("""
    var __fetchCalls = [];
    fetch = function(url){ __fetchCalls.push(url);
      return Promise.resolve({ ok:true, json:function(){ return Promise.resolve({serial:'007'}); } }); };
    """)
    _call_async(ctx, "refreshSuggestedSerial()")
    calls = json.loads(ctx.eval('JSON.stringify(__fetchCalls)'))
    assert len(calls) == 1
    assert 'peek=1' in calls[0]
    assert ctx.eval("document.getElementById('inNumS').value") == '007'


# ─── Problème 4 : la resynchronisation doit renégocier un n° jamais confirmé ──

def test_syncofflinequeue_renegocie_le_numero_non_confirme():
    """Reproduction directe du scénario terrain : poste hors ligne, num_sent
    encore un aperçu jamais confirmé (`_serial_pending`). Un autre poste a
    entretemps réellement obtenu ce numéro pour un QSO différent — la
    resynchronisation doit demander un numéro FRAIS avant le renvoi effectif,
    jamais renvoyer aveuglément l'ancien (collision)."""
    ctx = _make_ctx()
    ctx.eval("""
    localStorage.setItem('rc_offline_queue', JSON.stringify([
      {id:1, call:'F4TEST', band:'14', num_sent:'005', _serial_pending:true}
    ]));
    var __addBodies = [];
    fetch = function(url, opts){
      if (url.indexOf('/log/next_serial') === 0){
        return Promise.resolve({ ok:true, json:function(){ return Promise.resolve({serial:'009'}); } });
      }
      if (url === '/log/add'){
        __addBodies.push(JSON.parse(opts.body));
        return Promise.resolve({ ok:true, json:function(){ return Promise.resolve({}); } });
      }
      return Promise.resolve({ ok:false, status:0, json:function(){ return Promise.resolve({}); } });
    };
    """)
    _call_async(ctx, "syncOfflineQueue()")
    bodies = json.loads(ctx.eval('JSON.stringify(__addBodies)'))
    assert len(bodies) == 1
    assert bodies[0]['num_sent'] == '009'    # renégocié, plus l'ancien '005'
    assert '_serial_pending' not in bodies[0]   # métadonnée locale, jamais envoyée
    remaining = json.loads(ctx.eval("localStorage.getItem('rc_offline_queue')"))
    assert remaining == []   # QSO bien retiré de la file après renvoi réussi


def test_syncofflinequeue_ne_renegocie_pas_un_numero_deja_confirme():
    """Un QSO en file dont le n° a DÉJÀ été confirmé par une vraie allocation
    (pas de `_serial_pending`, ex. échec réseau juste après un
    /log/next_serial réussi) doit être renvoyé tel quel — pas de nouvelle
    allocation inutile (qui brûlerait un numéro pour rien)."""
    ctx = _make_ctx()
    ctx.eval("""
    localStorage.setItem('rc_offline_queue', JSON.stringify([
      {id:1, call:'F4TEST', band:'14', num_sent:'005'}
    ]));
    var __nextSerialCalls = 0;
    var __addBodies = [];
    fetch = function(url, opts){
      if (url.indexOf('/log/next_serial') === 0){
        __nextSerialCalls++;
        return Promise.resolve({ ok:true, json:function(){ return Promise.resolve({serial:'009'}); } });
      }
      if (url === '/log/add'){
        __addBodies.push(JSON.parse(opts.body));
        return Promise.resolve({ ok:true, json:function(){ return Promise.resolve({}); } });
      }
      return Promise.resolve({ ok:false, status:0, json:function(){ return Promise.resolve({}); } });
    };
    """)
    _call_async(ctx, "syncOfflineQueue()")
    assert ctx.eval('__nextSerialCalls') == 0
    bodies = json.loads(ctx.eval('JSON.stringify(__addBodies)'))
    assert bodies[0]['num_sent'] == '005'


def test_syncofflinequeue_rejet_definitif_nest_pas_retente_indefiniment():
    """Même principe que trySendQso() : un 4xx définitif pendant la
    resynchronisation ne doit pas rester en file pour toujours (silencieux) —
    il est abandonné avec un message, pas gardé indéfiniment."""
    ctx = _make_ctx()
    ctx.eval("""
    localStorage.setItem('rc_offline_queue', JSON.stringify([
      {id:1, call:'F4TEST', band:'14', num_sent:'005'}
    ]));
    fetch = function(url, opts){
      if (url === '/log/add'){
        return Promise.resolve({ ok:false, status:400,
          json:function(){ return Promise.resolve({error:'contest invalide'}); } });
      }
      return Promise.resolve({ ok:false, status:0, json:function(){ return Promise.resolve({}); } });
    };
    """)
    _call_async(ctx, "syncOfflineQueue()")
    remaining = json.loads(ctx.eval("localStorage.getItem('rc_offline_queue')"))
    assert remaining == []   # abandonné, pas gardé en file indéfiniment


def test_pas_de_qso_director():
    """Interdiction absolue (nom d'un concurrent) — jamais dans le code."""
    with open(HTML_PATH, encoding='utf-8') as f:
        assert 'QSO Director' not in f.read()
