# -*- coding: utf-8 -*-
"""A05 (docs/FEUILLE_DE_ROUTE.md) : le miroir JS des barèmes de scoring
(evalPointsFromDef, logx_logbook.js) ignorait silencieusement tout ce qu'il
ne reconnaissait pas, avec deux conséquences réelles trouvées en creusant
ce point (pas seulement le risque théorique décrit par l'audit) :

1. `when` en LISTE combinée (ex. REF §6 : ['my_is_french_all','is_french_all',
   'same_continent']) n'était pas géré DU TOUT -- BRICK_PREDICATES[la_liste]
   indexait avec un tableau converti en chaîne, toujours absent de la table,
   donc retombait sur 'always'=true. Pour REF_CDF_HF (dont TOUTES les règles
   sauf la dernière utilisent ce format), la boucle retournait alors la
   PREMIÈRE règle ('is_maritime_mobile', 3 pts) sans condition -- chaque QSO
   affichait 3 pts côté client, quel que soit le QSO réel.
2. is_french_all/my_is_french_all/is_maritime_mobile étaient absents de
   BRICK_PREDICATES alors qu'ils sont RÉELLEMENT utilisés par REF_CDF_HF_SSB/
   CW (le concours phare du logiciel) -- corrigés ici avec les mêmes sources
   que le reste du miroir (CTY_PREFIX pour les DOM-TOM, suffixe /MM pour
   maritime mobile, miroir exact de logx_scoring.py:calc_qso_value).
   same_itu_zone (IARU HF) reste volontairement NON implémenté : aucune
   donnée de zone ITU n'existe côté client -- le signal bruyant ajouté ici
   couvre ce cas plutôt qu'une fausse implémentation.

Exécute le VRAI logx_logbook.js (V8 réel, py_mini_racer), même patron que
tests/test_qso_champs_obligatoires.py (repris pour rester indépendant)."""
import os

import pytest

py_mini_racer = pytest.importorskip(
    'py_mini_racer', reason='py_mini_racer absent (voir requirements.txt) — test JS réel ignoré')

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS_PATH = os.path.join(BASE, 'logx_logbook.js')
RULES_JS_PATH = os.path.join(BASE, 'logx_contest_rules.js')
HARDWARE_JS_PATH = os.path.join(BASE, 'logx_hardware_cat.js')
DXCC_JS_PATH = os.path.join(BASE, 'logx_dxcc_lookup.js')
CALLBOOK_JS_PATH = os.path.join(BASE, 'logx_callbook.js')
LOOKUP_JS_PATH = os.path.join(BASE, 'logx_lookup.js')
ESM_CALLBOT_JS_PATH = os.path.join(BASE, 'logx_esm_callbot.js')
VOICE_KEYER_JS_PATH = os.path.join(BASE, 'logx_voice_keyer.js')
LOCATOR_REVERSE_JS_PATH = os.path.join(BASE, 'logx_locator_reverse.js')
MACROS_JS_PATH = os.path.join(BASE, 'logx_macros.js')
FILTRE_SPOTS_JS_PATH = os.path.join(BASE, 'logx_filtre_spots.js')
OUTILS_DIVERS_JS_PATH = os.path.join(BASE, 'logx_outils_divers.js')

_DOM_PREAMBLE = r"""
var __store = {};
function ElProxy(){
  var s = {value:'', textContent:'', innerHTML:'', title:'', style:{}, checked:false, disabled:false, files:[], children:[]};
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
      if(prop === 'closest') return function(){ return ElProxy(); };
      if(prop === 'contains') return function(){ return false; };
      if(prop === 'focus') return function(){};
      if(prop === 'select') return function(){};
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
var __consoleErrors = [];
var console = {log:function(){}, warn:function(){}, error:function(){ __consoleErrors.push(Array.prototype.slice.call(arguments).join(' ')); }, info:function(){}, debug:function(){}};
function setInterval(){ return 0; }
function setTimeout(){ return 0; }
function clearInterval(){}
function clearTimeout(){}
var localStorage = {
  _d:{}, getItem:function(k){ return (k in this._d)? this._d[k] : null; },
  setItem:function(k,v){ this._d[k]=String(v); }, removeItem:function(k){ delete this._d[k]; }
};
function fetch(){ return Promise.resolve({ ok:false, status:0, json: function(){ return Promise.resolve({}); } }); }
function alert(){}
function confirm(){ return false; }
function prompt(){ return null; }
var navigator = { userAgent:'test', mediaDevices: { enumerateDevices: function(){ return Promise.resolve([]); } },
                  clipboard:{ writeText:function(){ return Promise.resolve(); } } };
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


def _real_source():
    parts = []
    for path in (RULES_JS_PATH, HARDWARE_JS_PATH, DXCC_JS_PATH, CALLBOOK_JS_PATH, LOOKUP_JS_PATH, ESM_CALLBOT_JS_PATH,
                 VOICE_KEYER_JS_PATH, LOCATOR_REVERSE_JS_PATH, MACROS_JS_PATH,
                 FILTRE_SPOTS_JS_PATH, OUTILS_DIVERS_JS_PATH, JS_PATH):
        with open(path, encoding='utf-8') as f:
            parts.append(f.read())
    return '\n'.join(parts)


def _make_ctx():
    ctx = py_mini_racer.MiniRacer()
    ctx.eval(_DOM_PREAMBLE)
    ctx.eval(_real_source())
    ctx.eval("myCall = 'F4TEST'; myLocator = 'JN18CX';")
    return ctx


# Barème réel REF_CDF_HF_SSB/CW (logx_definitions.py), reproduit tel quel.
REF_BRICKS = {
    'bricks': {
        'points': [
            {'when': 'is_maritime_mobile', 'points': 3},
            {'when': ['my_is_french_all', 'is_french_all', 'same_continent'], 'points': 6},
            {'when': ['my_is_french_all', 'is_french_all', 'different_continent'], 'points': 15},
            {'when': ['my_is_french_all', 'same_continent'], 'points': 1},
            {'when': ['my_is_french_all', 'different_continent'], 'points': 2},
            {'when': ['is_french_all', 'same_continent'], 'points': 1},
            {'when': ['is_french_all', 'different_continent'], 'points': 3},
            {'when': 'always', 'points': 0},
        ],
    },
}


def _eval(ctx, callDX, band='14', mode='SSB', dist=0, locDX=None, myLoc=None):
    import json
    js = f"""evalPointsFromDef({json.dumps(REF_BRICKS)}, {json.dumps(callDX)},
        {json.dumps(band)}, {json.dumps(mode)}, {dist}, {json.dumps(locDX)}, {json.dumps(myLoc)})"""
    return ctx.eval(js)


def test_when_liste_combinee_deux_francais_meme_continent_6pts():
    """Le coeur du défaut : avant ce correctif, TOUTE règle à when combiné
    était acquise sans condition dès la 1re (is_maritime_mobile, 3 pts) --
    chaque QSO REF affichait 3 pts, quel que soit le QSO réel."""
    ctx = _make_ctx()
    assert _eval(ctx, 'F5ABC') == 6   # F4TEST (France) <-> F5ABC (France), même continent


def test_when_liste_combinee_francais_vers_etranger_meme_continent_1pt():
    ctx = _make_ctx()
    assert _eval(ctx, 'DL1ABC') == 1   # France -> Allemagne, même continent (EU)


def test_when_liste_combinee_francais_vers_etranger_autre_continent_2pts():
    ctx = _make_ctx()
    assert _eval(ctx, 'W1ABC') == 2   # France -> USA, autre continent


def test_dom_tom_reconnu_via_repli_prefixe():
    """FJ (Saint-Barthélemy) absent de CTY_PREFIX -- doit passer par le repli
    préfixe explicite, même motif que TK dans is_french."""
    ctx = _make_ctx()
    assert _eval(ctx, 'FJ/W1ABC') == 6   # DOM-TOM français <-> France, même continent


def test_maritime_mobile_detecte_sur_le_suffixe_mm():
    ctx = _make_ctx()
    assert _eval(ctx, 'W1ABC/MM') == 3


def test_predicat_inconnu_signale_une_seule_fois_en_console():
    """same_itu_zone (IARU HF) : aucune donnée de zone ITU côté client --
    doit signaler bruyamment plutôt que fausser silencieusement le score."""
    ctx = _make_ctx()
    bricks_itu = {'bricks': {'points': [{'when': 'same_itu_zone', 'points': 1}]}}
    import json
    ctx.eval(f"""
    evalPointsFromDef({json.dumps(bricks_itu)}, 'DL1ABC', '14', 'SSB', 0, null, null);
    evalPointsFromDef({json.dumps(bricks_itu)}, 'W1ABC', '14', 'SSB', 0, null, null);
    """)
    erreurs = ctx.eval("__consoleErrors.filter(e => e.indexOf('same_itu_zone') >= 0).length")
    assert erreurs == 1, "un prédicat déjà signalé ne doit pas re-spammer la console à chaque QSO"
    # document.getElementById() du stub DOM est une registry par nom d'id, pas
    # une simulation d'arborescence réelle -- on vérifie donc l'élément
    # RÉELLEMENT ajouté à document.body.children (appendChild), pas retrouvé
    # par un id qu'aucun mécanisme du stub ne relie à cet ajout.
    assert ctx.eval("document.body.children.length") == 1
    assert 'same_itu_zone' in ctx.eval("document.body.children[0].textContent")
    assert ctx.eval("document.body.children[0].id") == 'scoringPredicatInconnuBanner'
