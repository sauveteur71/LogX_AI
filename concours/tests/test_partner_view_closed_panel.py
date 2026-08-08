# -*- coding: utf-8 -*-
"""Vue PARTNER (saisie en direct, commit cb89dfc) : elle est censée être utile
PRÉCISÉMENT quand le panneau CHAT est fermé (bandeau discret visible sans
ouvrir le panneau pendant un pile-up). Deux défauts trouvés par revue
adversariale de ce commit montraient le contraire :

1) renderPartnerTyping() affiche/masque le bandeau sans jamais être soumis à
   la classe .open, mais le recalcul de la marge réservée sous le tableau de
   log (_reserveBottomSpace) était gardé par 'if(panel.classList.contains
   ("open"))' — panneau fermé, le bandeau grandit sans jamais agrandir la
   marge réservée : les dernières lignes du log se retrouvent chevauchées.

2) Le poll /chat/list (adaptivePoll) ne restait rapide (3s) QUE panneau
   ouvert, ralentissant à 15s dès qu'il est fermé — exactement l'état où la
   vue Partner doit pourtant réagir vite.

Ce module exécute le VRAI logx_logbook.js dans un moteur JS réel (V8 via
py_mini_racer), comme tests/test_logbook_render_window_reset.py, pour
reproduire les deux scénarios concrètement plutôt que de grepper une chaîne
dans le fichier source."""
import os
import subprocess

import pytest

py_mini_racer = pytest.importorskip(
    'py_mini_racer', reason='py_mini_racer absent (voir requirements.txt) — test JS réel ignoré')

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS_PATH = os.path.join(BASE, 'logx_logbook.js')
# EV-7 19e incrément : appel TOP-LEVEL renderVoiceDynPanel() dans
# logx_logbook.js -- ReferenceError au parse sans ce fichier chargé avant.
ESM_CALLBOT_JS_PATH = os.path.join(BASE, 'logx_esm_callbot.js')
# EV-7 20e incrément : appel TOP-LEVEL voiceRefreshSlots() dans
# logx_logbook.js -- même piège que renderVoiceDynPanel() (19e incrément).
VOICE_KEYER_JS_PATH = os.path.join(BASE, 'logx_voice_keyer.js')

# ─── DOM minimal ──────────────────────────────────────────────────────────────
# Même modèle que test_logbook_render_window_reset.py, avec UNE différence :
# document.querySelector() est ici mémoïsé par sélecteur (comme getElementById
# l'est déjà par id) — sans ça, chaque appel renvoie un nouveau Proxy vierge et
# on ne peut plus observer un style posé par un appel précédent (_reserveBottomSpace
# écrit sur l'objet renvoyé par un querySelector, un autre le relit via un
# second querySelector : il faut que ce soit LE MÊME objet).
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
      if(prop === 'getBoundingClientRect') return function(){ var h = s._mockHeight || 0; return {top:0,left:0,width:0,height:h,bottom:h,right:0}; };
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
  querySelector: function(sel){ var k='qs:'+sel; if(!__store[k]) __store[k] = ElProxy(); return __store[k]; },
  addEventListener: function(){}, removeEventListener: function(){},
  createElement: function(){ return ElProxy(); },
  querySelectorAll: function(){ return []; },
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
function fetch(){ return Promise.resolve({ ok:false, json: function(){ return Promise.resolve({}); } }); }
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
"""


def _real_source(rev=None):
    """Source réelle de logx_logbook.js : HEAD par défaut, ou `rev` (ex. le
    commit cb89dfc, celui qui introduit le bug) pour rejouer le scénario tel
    qu'il était avant ce correctif."""
    if rev is None:
        with open(ESM_CALLBOT_JS_PATH, encoding='utf-8') as f:
            src = f.read()
        with open(VOICE_KEYER_JS_PATH, encoding='utf-8') as f:
            src += '\n' + f.read()
        with open(JS_PATH, encoding='utf-8') as f:
            return src + '\n' + f.read()
    out = subprocess.run(
        ['git', 'show', f'{rev}:concours/logx_logbook.js'],
        cwd=BASE, capture_output=True, text=True, encoding='utf-8', check=True)
    return out.stdout


def _make_ctx(rev=None):
    ctx = py_mini_racer.MiniRacer()
    ctx.eval(_DOM_PREAMBLE)
    ctx.eval(_real_source(rev))
    return ctx


# ─── Problème 1 : marge réservée sous le tableau, panneau CHAT fermé ─────────

def test_reproduction_bug_sur_cb89dfc_bandeau_ferme_ne_reserve_pas():
    """Garde-fou : sur le commit d'origine, le bandeau Partner grandit
    (panneau toujours fermé) sans jamais faire grandir la marge réservée."""
    ctx = _make_ctx(rev='cb89dfc')
    ctx.eval("""
    myOp = 'OP1';
    document.getElementById('chatPanel').offsetHeight = 40;   // replié, juste l'en-tête
    _reserveBottomSpace(document.getElementById('chatPanel'), document.querySelector('.log-table-wrap'));
    """)
    assert ctx.eval("document.querySelector('.log-table-wrap').style.paddingBottom") == '40px'
    assert ctx.eval("document.getElementById('chatPanel').classList.contains('open')") is False
    ctx.eval("""
    document.getElementById('chatPanel').offsetHeight = 150;  // grandit : bandeau Partner rempli
    renderPartnerTyping([{op:'OP2', label:'OP2', band:'14', mode:'CW', text:'F5ABC'}]);
    """)
    # Le bug : la marge réservée reste à l'ancienne hauteur alors que le
    # panneau (donc le bandeau visible dessus) occupe maintenant 150px.
    assert ctx.eval("document.querySelector('.log-table-wrap').style.paddingBottom") == '40px'


def test_bandeau_partner_reserve_la_marge_meme_panneau_ferme():
    """Sur le code actuel : la marge doit suivre la hauteur du bandeau, que le
    panneau CHAT soit ouvert ou fermé — le panneau reste fermé du début à la
    fin de ce scénario.

    _reserveBottomSpace() ne pose plus de padding-bottom (voir son commentaire
    dans logx_logbook.js : un padding-bottom plus grand que la boîte la force
    à GRANDIR pour pouvoir le contenir, au lieu de rétrécir — repéré sur
    .saisie-secondary/panneau CW, cf. logx_logbook.html). Elle réduit
    désormais max-height d'après la hauteur NATURELLE (sans réservation),
    mesurée via getBoundingClientRect() — d'où le mock _mockHeight ci-dessous,
    qui simule cette hauteur naturelle (800px, une valeur arbitraire —
    seule l'arithmétique importe ici, pas la valeur en soi)."""
    ctx = _make_ctx()
    ctx.eval("""
    myOp = 'OP1';
    document.querySelector('.log-table-wrap')._mockHeight = 800;
    document.getElementById('chatPanel').offsetHeight = 40;
    _reserveBottomSpace(document.getElementById('chatPanel'), document.querySelector('.log-table-wrap'));
    """)
    assert ctx.eval("document.querySelector('.log-table-wrap').style.maxHeight") == '760px'
    ctx.eval("""
    document.getElementById('chatPanel').offsetHeight = 150;
    renderPartnerTyping([{op:'OP2', label:'OP2', band:'14', mode:'CW', text:'F5ABC'}]);
    """)
    assert ctx.eval("document.querySelector('.log-table-wrap').style.maxHeight") == '650px'
    assert ctx.eval("document.getElementById('chatPanel').classList.contains('open')") is False

    # Le bandeau se vide (plus aucune saisie distante) : la marge redescend.
    ctx.eval("""
    document.getElementById('chatPanel').offsetHeight = 40;
    renderPartnerTyping([]);
    """)
    assert ctx.eval("document.querySelector('.log-table-wrap').style.maxHeight") == '760px'


# ─── Problème 3 : cadence du poll /chat/list en multi-op, panneau fermé ──────

def _capture_is_active(ctx):
    """Remplace adaptivePoll par un espion qui capture juste le callback
    isActive passé par startChat(), sans jamais lancer de véritable poll (pas
    besoin d'exécuter pollChat pour ce test)."""
    ctx.eval("""
    var __capturedIsActive = null;
    adaptivePoll = function(fn, fastMs, slowMs, isActive){ __capturedIsActive = isActive; };
    startChat();
    """)


def test_reproduction_bug_sur_cb89dfc_poll_lent_en_multi_op_panneau_ferme():
    """Garde-fou : sur le commit d'origine, la cadence rapide dépend UNIQUEMENT
    de l'ouverture du panneau — un multi-op actif, panneau fermé, retombe à
    tort sur la cadence lente (15s)."""
    ctx = _make_ctx(rev='cb89dfc')
    _capture_is_active(ctx)
    ctx.eval("""
    localStorage.setItem('logx_config', JSON.stringify({usage_mode:'contest', operators:['OP1','OP2']}));
    document.getElementById('chatPanel').classList.remove('open');
    """)
    assert ctx.eval('__capturedIsActive()') is False


def test_poll_reste_rapide_en_multi_op_meme_panneau_ferme():
    """Sur le code actuel : la cadence rapide (3s) doit être maintenue en
    multi-op même panneau fermé (c'est l'état où la vue Partner doit rester
    réactive) ; comportement solo/panneau-ouvert inchangé par ailleurs."""
    ctx = _make_ctx()
    _capture_is_active(ctx)
    ctx.eval("""
    localStorage.setItem('logx_config', JSON.stringify({usage_mode:'contest', operators:['OP1','OP2']}));
    document.getElementById('chatPanel').classList.remove('open');
    """)
    assert ctx.eval('__capturedIsActive()') is True

    # Solo (un seul opérateur déclaré) + panneau fermé : cadence lente, comme avant.
    ctx.eval("""
    localStorage.setItem('logx_config', JSON.stringify({usage_mode:'contest', operators:['OP1']}));
    """)
    assert ctx.eval('__capturedIsActive()') is False

    # Panneau ouvert : toujours rapide quel que soit le mode (non régressé).
    ctx.eval("document.getElementById('chatPanel').classList.add('open');")
    assert ctx.eval('__capturedIsActive()') is True


def test_pas_de_qso_director():
    """Interdiction absolue (nom d'un concurrent) — jamais dans le code."""
    with open(JS_PATH, encoding='utf-8') as f:
        assert 'QSO Director' not in f.read()
