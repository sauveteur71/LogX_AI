# -*- coding: utf-8 -*-
"""XSS stockée par la version déclarée d'un poste voisin (?ver=) — chaîne
complète du point d'injection au sink HTML.

Le bug : GET /log/list?ver=X est servi par do_GET SANS aucune authentification
(n'importe quel appareil du LAN peut l'appeler), et la valeur était stockée
telle quelle dans logx_http.peer_versions puis restituée brute par /log/status
→ peer_list, que chaque poste polle toutes les ~60 s. Côté client,
showChecklist() (bouton « ✅ CHECKLIST » du logbook, typiquement ouvert avant
un concours multi-poste) interpolait cette chaîne dans `label`, lui-même
injecté dans `inner.innerHTML` SANS escHtml — seul chemin réseau du fichier à
avoir été oublié (bandmap, callbook, chat et validation passent tous par
escHtml). Un `<img src=x onerror=...>` déposé sans jeton s'exécutait donc dans
l'origine de logx_logbook.html, page qui porte le cookie de session rc_token :
le script obtenait de fait /log/reset, /config/save, /auth/set_password...

Deux verrous sont testés indépendamment, car chacun doit tenir seul :
  1. SERVEUR — une version au format invalide n'entre jamais en mémoire
     (PEER_VERSION_RE), ce qui borne aussi la taille stockée.
  2. CLIENT — même si une valeur hostile arrivait (serveur plus ancien, poste
     relais, /log/status d'un autre hôte), le VRAI showChecklist() l'échappe.
"""
import http.server
import json
import os
import sys
import threading
import urllib.parse
import urllib.request
from html.parser import HTMLParser

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_http as httpmod
from logx_version import APP_VERSION

PAYLOAD = '<img src=x onerror="alert(document.cookie)">'


# ═══════════════════════════════════════════════════════════════════════════
# 1. VERROU SERVEUR : la valeur hostile n'est jamais stockée
# ═══════════════════════════════════════════════════════════════════════════

@pytest.fixture
def server(monkeypatch):
    # peer_versions/connected_peers sont des globals partagés par tout le
    # process : repli à vide pour que l'ordre des autres tests ne pollue pas
    # les assertions (même isolation que tests/test_peer_versions_http.py).
    monkeypatch.setattr(httpmod, 'peer_versions', {})
    monkeypatch.setattr(httpmod, 'connected_peers', set())
    srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), httpmod.Handler)
    port = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        yield f'http://127.0.0.1:{port}'
    finally:
        srv.shutdown()
        srv.server_close()
        t.join(timeout=5)


def _get(base, path):
    with urllib.request.urlopen(base + path, timeout=5) as r:
        return json.loads(r.read().decode('utf-8'))


def test_version_avec_html_jamais_stockee_ni_restituee(server):
    """Scénario exact du bug, requête SANS cookie ni jeton : le payload est
    refusé à l'entrée, donc /log/status ne le sert à personne. Échouait avant
    le correctif — la chaîne était stockée verbatim et renvoyée telle quelle
    dans peer_list."""
    _get(server, '/log/list?ver=' + urllib.parse.quote(PAYLOAD))
    status = _get(server, '/log/status')
    assert status['peer_list'] == [], (
        "version hostile stockée puis servie à tous les postes : "
        + json.dumps(status['peer_list']))
    with httpmod.peer_versions_lock:
        assert httpmod.peer_versions == {}
    # Aucun fragment du payload ne doit subsister nulle part dans la réponse.
    assert '<img' not in json.dumps(status) and 'onerror' not in json.dumps(status)


@pytest.mark.parametrize('hostile', [
    '<img src=x onerror="alert(1)">',
    '"><script>alert(1)</script>',
    "0.9-beta4<svg/onload=alert(1)>",     # préfixe légitime + charge utile
    "0.9 beta4",                          # espace : hors format admis
    'A' * 33,                             # au-delà de la borne de longueur
])
def test_versions_non_conformes_rejetees(server, hostile):
    _get(server, '/log/list?ver=' + urllib.parse.quote(hostile))
    assert _get(server, '/log/status')['peer_list'] == []


@pytest.mark.parametrize('legitime', [
    APP_VERSION,          # la vraie version courante doit évidemment passer
    '0.9-beta3',
    '1.0',
    '1.2.3+build.7',      # métadonnée de build semver
    'v2.0_rc1',
])
def test_versions_legitimes_toujours_acceptees(server, legitime):
    """Garde-fou inverse : le filtre ne doit pas casser l'affichage normal du
    badge de version entre postes (le vrai service rendu par ?ver=)."""
    _get(server, '/log/list?ver=' + urllib.parse.quote(legitime))
    peer_list = _get(server, '/log/status')['peer_list']
    assert len(peer_list) == 1 and peer_list[0]['version'] == legitime


def test_version_geante_non_stockee(server):
    """Effet de bord du même code : peer_versions stockait verbatim tout ce
    que la ligne de requête HTTP acceptait (~64 Ko par entrée, jamais borné)."""
    _get(server, '/log/list?ver=' + 'a' * 5000)
    with httpmod.peer_versions_lock:
        assert httpmod.peer_versions == {}


# ═══════════════════════════════════════════════════════════════════════════
# 2. VERROU CLIENT : le VRAI showChecklist() échappe la version d'un pair
# ═══════════════════════════════════════════════════════════════════════════
# Exécute le VRAI logx_logbook.js dans un moteur JS réel (V8 via py_mini_racer,
# même technique que tests/test_awards_clublog_realtime_blocked_js.py) plutôt
# que de grepper `escHtml` dans la source : c'est le HTML RÉELLEMENT affecté à
# innerHTML qui est inspecté.

py_mini_racer = pytest.importorskip(
    'py_mini_racer', reason='py_mini_racer absent (voir requirements.txt) — test JS réel ignoré')

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS_PATH = os.path.join(BASE, 'logx_logbook.js')
# EV-7 : showChecklist() (avec son échappement escHtml testé ici) a été
# extraite vers ce fichier -- doit être chargée AVANT logx_logbook.js, même
# convention que tests/test_cw_panel_consolidation.py.
VERIF_PANEL_JS_PATH = os.path.join(BASE, 'logx_verif_panel.js')
# EV-7 17e incrément : showChecklist() lit callDB directement
# (Object.keys(callDB).length) -- callDB vit désormais dans logx_lookup.js,
# à charger AVANT logx_logbook.js comme VERIF_PANEL_JS_PATH. Sans lui,
# ReferenceError: callDB is not defined (trouvé en lançant réellement ce
# test après extraction, pas par grep préalable -- callDB n'apparaît nulle
# part comme texte dans ce fichier, seul showChecklist() la lit en corps de
# fonction).
LOOKUP_JS_PATH = os.path.join(BASE, 'logx_lookup.js')
# EV-7 19e incrément : logx_logbook.js contient un appel TOP-LEVEL
# renderVoiceDynPanel(); juste après le bloc CALLBOT/ESM extrait -- sûr
# uniquement si logx_esm_callbot.js (qui définit cette fonction) est chargé
# AVANT logx_logbook.js. Sans lui, ReferenceError au PARSE de logx_logbook.js
# lui-même (avant même l'exécution d'un test), trouvé en lançant réellement
# ce fichier après extraction.
ESM_CALLBOT_JS_PATH = os.path.join(BASE, 'logx_esm_callbot.js')
# EV-7 20e incrément : appel TOP-LEVEL voiceRefreshSlots() dans
# logx_logbook.js -- même piège que renderVoiceDynPanel() (19e incrément).
VOICE_KEYER_JS_PATH = os.path.join(BASE, 'logx_voice_keyer.js')
# EV-7 33e incrément : appel TOP-LEVEL setInterval(refreshBandMap,...) dans
# logx_logbook.js -- ReferenceError au parse sans ce fichier chargé avant.
FILTRE_SPOTS_JS_PATH = os.path.join(BASE, 'logx_filtre_spots.js')
# EV-7 35e incrément : updateVersionStatus()/_versionMismatches() ont été
# extraites vers ce fichier -- ce test appelle directement updateVersionStatus()
# (voir _checklist_html ci-dessous) et showChecklist() (VERIF_PANEL_JS_PATH)
# appelle _versionMismatches() en corps de fonction : les deux ont besoin que
# ce fichier soit chargé avant elles.
VERSION_BADGE_JS_PATH = os.path.join(BASE, 'logx_version_badge.js')

# DOM minimal (Proxy permissif — voir tests/test_logbook_render_window_reset.py
# pour la version commentée de ce Proxy).
_DOM_PREAMBLE = r"""
var __store = {};
function ElProxy(){
  var s = {value:'', textContent:'', innerHTML:'', style:{}, checked:false, disabled:false, files:[], children:[]};
  var cls = {_s:new Set(), add:function(){for(var i=0;i<arguments.length;i++) this._s.add(arguments[i]);},
             remove:function(){for(var i=0;i<arguments.length;i++) this._s.delete(arguments[i]);},
             contains:function(c){return this._s.has(c);},
             toggle:function(c){ if(this._s.has(c)) this._s.delete(c); else this._s.add(c); return this._s.has(c);}};
  var handler = {
    get:function(target, prop){
      if(prop === 'classList') return cls;
      if(prop === 'style') return s.style;
      if(prop === 'dataset') return (s.dataset = s.dataset || {});
      if(prop === 'addEventListener') return function(){};
      if(prop === 'removeEventListener') return function(){};
      if(prop === 'appendChild') return function(c){ s.children.push(c); return c; };
      if(prop === 'insertBefore') return function(c){ s.children.unshift(c); return c; };
      if(prop === 'removeChild') return function(c){ var i=s.children.indexOf(c); if(i>=0) s.children.splice(i,1); };
      if(prop === 'querySelector') return function(){ return ElProxy(); };
      if(prop === 'querySelectorAll') return function(){ return []; };
      if(prop === 'focus') return function(){};
      if(prop === 'click') return function(){};
      if(prop === 'getContext') return function(){ return null; };
      if(prop === 'getBoundingClientRect') return function(){ return {top:0,left:0,width:0,height:0,bottom:0,right:0}; };
      if(prop === 'setAttribute') return function(){};
      if(prop === 'getAttribute') return function(){ return null; };
      if(prop === 'remove') return function(){};
      if(prop === 'scrollIntoView') return function(){};
      return s[prop];
    },
    set:function(target, prop, val){ s[prop] = val; return true; }
  };
  return new Proxy({}, handler);
}
var document = {
  getElementById: function(id){ if(!__store[id]) __store[id] = ElProxy(); return __store[id]; },
  addEventListener: function(){}, removeEventListener: function(){},
  createElement: function(){ return ElProxy(); },
  querySelectorAll: function(){ return []; },
  querySelector: function(){ return ElProxy(); },
  body: ElProxy(), documentElement: ElProxy(),
};
var window = this;
window.addEventListener = function(){};
window.removeEventListener = function(){};
function setInterval(){ return 0; }
function setTimeout(){ return 0; }
function clearInterval(){}
function clearTimeout(){}
var localStorage = {
  _d:{}, getItem:function(k){ return (k in this._d)? this._d[k] : null; },
  setItem:function(k,v){ this._d[k]=String(v); }, removeItem:function(k){ delete this._d[k]; }
};
function alert(){}
function confirm(){ return false; }
function prompt(){ return null; }
var navigator = { userAgent:'test', mediaDevices: { enumerateDevices: function(){ return Promise.resolve([]); } }, clipboard:{} };
var location = { protocol:'http:', hostname:'127.0.0.1', href:'http://127.0.0.1/', search:'', reload:function(){} };
window.location = location;
function Notification(){}
Notification.permission = 'denied';
Notification.requestPermission = function(){ return Promise.resolve('denied'); };
function WebSocket(){ this.close = function(){}; }
function Blob(parts, opts){ this.parts = parts; }
window.URL = { createObjectURL:function(){ return 'blob:x'; }, revokeObjectURL:function(){} };
function Image(){ this.src = ''; }
function AudioContext(){}
function MediaRecorder(){}
var L = new Proxy({}, { get:function(){ return function(){ return new Proxy({}, {get:function(){ return function(){ return new Proxy({},{get:function(){ return function(){}; }}); }; }}); }; } });
// showChecklist() fait un seul appel réseau (/config, pour comparer l'heure
// serveur via l'en-tête Date) : réponse minimale suffisante.
function fetch(url){
  return Promise.resolve({ ok:true,
    headers:{ get:function(){ return new Date().toUTCString(); } },
    json:function(){ return Promise.resolve({}); } });
}
"""


def _checklist_html(peer_version, server_version='0.9-beta4'):
    """Rend la CHECKLIST via le VRAI showChecklist() et renvoie le HTML
    réellement affecté à #checklistInner.innerHTML.

    Le snapshot des pairs est posé par le VRAI updateVersionStatus() (chemin
    nominal : c'est refreshCluster() qui l'appelle avec la réponse de
    /log/status), pas par une écriture directe dans les variables internes."""
    ctx = py_mini_racer.MiniRacer()
    ctx.eval(_DOM_PREAMBLE)
    with open(VERIF_PANEL_JS_PATH, encoding='utf-8') as f:
        ctx.eval(f.read())
    with open(LOOKUP_JS_PATH, encoding='utf-8') as f:
        ctx.eval(f.read())
    with open(ESM_CALLBOT_JS_PATH, encoding='utf-8') as f:
        ctx.eval(f.read())
    with open(VOICE_KEYER_JS_PATH, encoding='utf-8') as f:
        ctx.eval(f.read())
    with open(FILTRE_SPOTS_JS_PATH, encoding='utf-8') as f:
        ctx.eval(f.read())
    with open(VERSION_BADGE_JS_PATH, encoding='utf-8') as f:
        ctx.eval(f.read())
    with open(JS_PATH, encoding='utf-8') as f:
        ctx.eval(f.read())
    ctx.eval('updateVersionStatus(%s);' % json.dumps({
        'app_version': server_version,
        'peer_list': [{'ip': '192.168.1.66', 'version': peer_version,
                       'last_seen': 0}],
    }))
    ctx.eval("""
    var _testDone = false, _testError = null;
    showChecklist().then(function(){ _testDone = true; })
                   .catch(function(e){ _testError = String(e && e.stack || e); _testDone = true; });
    """)
    for _ in range(50):
        if ctx.eval('_testDone'):
            break
        ctx.eval('undefined')
    err = ctx.eval('_testError')
    assert ctx.eval('_testDone') is True and not err, \
        f"showChecklist() n'a jamais terminé (erreur : {err})"
    return ctx.eval("document.getElementById('checklistInner').innerHTML")


class _TagCollector(HTMLParser):
    """Reconstruit l'arbre d'éléments que le navigateur bâtirait à partir de
    cette chaîne : c'est ce que fait innerHTML. On n'inspecte donc pas du
    texte, mais les BALISES réellement créées et leurs attributs — un
    `&lt;img ...&gt;` échappé n'y apparaît pas, une vraie balise si."""

    def __init__(self):
        super().__init__()
        self.tags = []
        self.attrs = []

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        self.attrs.extend(name.lower() for name, _ in attrs)


def test_checklist_echappe_la_version_dun_pair_hostile():
    """Cœur du correctif : aucune balise vivante ne doit naître de la version
    déclarée par le pair. Échoue sans le correctif — `<img src=x onerror=...>`
    se retrouvait intact dans innerHTML, et innerHTML déclenche bien les
    attributs gestionnaires d'événement d'un <img> inséré (contrairement à un
    <script>, qui lui ne s'exécute pas par cette voie)."""
    html = _checklist_html(PAYLOAD)
    assert 'Versions différentes' in html, \
        "le scénario ne passe pas par la branche testée : " + html

    parser = _TagCollector()
    parser.feed(html)
    assert 'img' not in parser.tags, \
        f'balise <img> vivante dans le DOM (tags={parser.tags}) : {html}'
    handlers = [a for a in parser.attrs if a.startswith('on')]
    assert not handlers, \
        f'attribut gestionnaire d\'événement vivant ({handlers}) : {html}'
    # Les seules balises produites sont celles du gabarit de la checklist.
    assert set(parser.tags) <= {'div', 'span'}, parser.tags

    # Et le texte reste lisible pour l'opérateur, simplement neutralisé.
    assert '&lt;img' in html and '192.168.1.66' in html


def test_checklist_affiche_normalement_une_version_legitime():
    """Garde-fou inverse : l'échappement ne doit pas abîmer l'affichage
    normal (le badge doit rester lisible, c'est son seul intérêt)."""
    html = _checklist_html('0.9-beta3')
    assert 'Versions différentes : 192.168.1.66 v0.9-beta3' in html
    assert '&lt;' not in html and '&amp;' not in html


def test_checklist_version_coherente_inchangee():
    """Cas nominal (toutes les versions alignées) : message intact, aucun
    artefact d'échappement."""
    html = _checklist_html('0.9-beta4', server_version='0.9-beta4')
    assert 'Version cohérente sur tous les postes (v0.9-beta4)' in html
    assert 'Versions différentes' not in html
