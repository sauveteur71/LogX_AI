# -*- coding: utf-8 -*-
"""Pastille foudre/orage : visible tout de suite, pas au bout de 5 minutes.

Le serveur ne préchauffe JAMAIS son cache météo : get_weather_cached()
(logx_weather.py) répond `{'ok': False, 'stale': True}` au tout premier appel
d'un process — et à tout changement de locator — en se contentant de lancer un
rafraîchissement en tâche de fond ; la donnée n'arrive qu'une à deux secondes
plus tard (comportement serveur déjà figé par tests/test_wall_conditions.py).

Côté client, refreshStorm() masquait la pastille sur `ok:false` et n'avait
aucun autre déclencheur que rcPoll(..., 5 min). Résultat : à CHAQUE démarrage
de LogX AI, la pastille d'alerte orage — celle qui dit « débranche les
antennes » — restait absente de la barre de statut pendant 5 minutes, sur
toutes les pages, sans une seule erreur console (`.catch` vide + sortie par
`return`). C'est exactement la fenêtre pendant laquelle l'opérateur installe
sa station. Même trou, et même moment critique, quand on saisit son locator /P
en arrivant sur site : la clé de cache change, la pastille disparaît 5 min.

Pourquoi ces tests exécutent le JS au lieu de grepper une chaîne : le défaut
n'est visible que dans l'ENCHAÎNEMENT (réponse ok:false → rien de reprogrammé
→ prochain tic à 5 min). Un grep sur « setTimeout » passerait au vert avec
n'importe quelle reprise, y compris une qui ne rappellerait jamais la météo.
On charge donc le VRAI logx_statusbar.js dans V8 (py_mini_racer), avec un DOM
minimal, une horloge virtuelle et un /data/weather qui se réchauffe à une date
choisie, puis on regarde `style.display` de la pastille — ce que voit
l'opérateur.
"""
import os
import re
import subprocess

import pytest

py_mini_racer = pytest.importorskip(
    'py_mini_racer', reason='py_mini_racer absent (voir requirements.txt) — test JS réel ignoré')

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS_PATH = os.path.join(BASE, 'logx_statusbar.js')

# Commit d'AVANT le correctif (barre de statut sans reprise sur cache froid),
# pris sur main pour rester atteignable quelle que soit la vie de la branche.
# Sert à prouver que ces tests échouent bien sur le code fautif : sans ça, un
# test de non-régression n'est qu'une description de l'existant.
REV_AVANT_FIX = '09db25a'

# ─── Bac à sable navigateur ───────────────────────────────────────────────────
# Horloge virtuelle : setTimeout/setInterval sont mis en file, __advance(ms)
# fait avancer le temps et déclenche les échéances. Aucune attente réelle, et
# surtout un contrôle exact de « quand » le serveur devient chaud.
_PREAMBULE = r"""
var __now = 0, __tid = 0, __timers = [];
function setTimeout(fn, ms){ __tid++; __timers.push({id:__tid, fn:fn, at:__now + (ms||0), every:0}); return __tid; }
function setInterval(fn, ms){ __tid++; __timers.push({id:__tid, fn:fn, at:__now + (ms||0), every:(ms||0)}); return __tid; }
function clearTimeout(id){ __timers = __timers.filter(function(t){ return t.id !== id; }); }
function clearInterval(id){ clearTimeout(id); }
function __advance(ms){
  var fin = __now + ms;
  for (var garde = 0; garde < 100000; garde++){
    var du = __timers.filter(function(t){ return t.at <= fin; })
                     .sort(function(a, b){ return a.at - b.at; });
    if (!du.length) break;
    var t = du[0];
    __now = t.at;
    if (t.every) t.at = __now + t.every;
    else __timers = __timers.filter(function(x){ return x.id !== t.id; });
    try { t.fn(); } catch(e){}
  }
  __now = fin;
}

// /data/weather : froid (ok:false) jusqu'à __meteoChaudeA, chaud ensuite.
var __fetches = [];
var __meteoChaudeA = Infinity;    // date virtuelle (ms) de disponibilité
var __orage = false;
function __reponseMeteo(){
  if (__now >= __meteoChaudeA)
    return {ok:true, storm:__orage, stale:false, desc:'Ciel clair', warn:''};
  return {ok:false, error:'Meteo en cours de recuperation...', stale:true};
}
function fetch(url){
  __fetches.push({url:String(url), t:__now});
  var corps = String(url).indexOf('/data/weather') === 0 ? __reponseMeteo() : {};
  return Promise.resolve({ok:true, status:200,
    json:function(){ return Promise.resolve(corps); },
    text:function(){ return Promise.resolve(''); }});
}
function __fetchesMeteo(){
  return __fetches.filter(function(f){ return f.url.indexOf('/data/weather') === 0; });
}

// DOM permissif : n'importe quelle propriété lue/écrite est mémorisée, ce qui
// évite d'énumérer les dizaines d'id de la barre.
var __els = {};
function El(id){
  var s = {value:'', textContent:'', innerHTML:'', title:'', style:{}, id:id||''};
  var cls = {_s:{},
    add:function(){ for(var i=0;i<arguments.length;i++) this._s[arguments[i]]=1; },
    remove:function(){ for(var i=0;i<arguments.length;i++) delete this._s[arguments[i]]; },
    contains:function(c){ return !!this._s[c]; },
    toggle:function(c,f){ var on = (f===undefined) ? !this._s[c] : !!f;
                          if(on) this._s[c]=1; else delete this._s[c]; return on; }};
  var kids = [];
  return new Proxy({}, {
    get:function(t, p){
      if (p === 'classList') return cls;
      if (p === 'style') return s.style;
      if (p === 'dataset') return (s.dataset = s.dataset || {});
      if (p === 'addEventListener' || p === 'removeEventListener') return function(){};
      if (p === 'appendChild' || p === 'prepend') return function(c){ kids.push(c); return c; };
      if (p === 'insertBefore') return function(c){ kids.unshift(c); return c; };
      if (p === 'removeChild') return function(c){ return c; };
      if (p === 'querySelector' || p === 'closest') return function(){ return null; };
      if (p === 'querySelectorAll') return function(){ return []; };
      if (p === 'contains') return function(){ return false; };
      if (p === 'setAttribute') return function(k, v){ s[k] = v; };
      if (p === 'getAttribute') return function(k){ return s[k] === undefined ? null : s[k]; };
      if (p === 'focus' || p === 'blur' || p === 'click' || p === 'remove'
          || p === 'scrollIntoView') return function(){};
      if (p === 'firstChild') return kids[0] || null;
      if (p === 'children') return kids;
      if (p === 'getBoundingClientRect')
        return function(){ return {top:0,left:0,width:0,height:0,bottom:0,right:0}; };
      return s[p];
    },
    set:function(t, p, v){ s[p] = v; return true; }
  });
}
var document = {
  readyState:'complete', hidden:false,
  getElementById:function(id){ if(!__els[id]) __els[id] = El(id); return __els[id]; },
  createElement:function(){ return El(); },
  addEventListener:function(){}, removeEventListener:function(){},
  querySelector:function(){ return null; }, querySelectorAll:function(){ return []; },
  dispatchEvent:function(){ return true; },
  body: El('body'), documentElement: El('html'), head: El('head')
};
function CustomEvent(n, o){ this.type = n; this.detail = (o||{}).detail; }
var window = this;
window.addEventListener = function(){};
window.removeEventListener = function(){};
window.open = function(){ return null; };
var localStorage = {_d:{},
  getItem:function(k){ return (k in this._d) ? this._d[k] : null; },
  setItem:function(k, v){ this._d[k] = String(v); },
  removeItem:function(k){ delete this._d[k]; }};
var location = {protocol:'http:', hostname:'127.0.0.1',
                href:'http://127.0.0.1/logx_propagation.html',
                pathname:'/logx_propagation.html', search:'', reload:function(){}};
window.location = location;
var navigator = {userAgent:'test', onLine:true};
function alert(){} function confirm(){ return false; } function prompt(){ return null; }
"""


def _source(rev=None):
    """Source réelle de logx_statusbar.js : copie de travail, ou celle d'un
    commit donné pour rejouer le scénario sur le code fautif."""
    if rev is None:
        with open(JS_PATH, encoding='utf-8') as f:
            return f.read()
    out = subprocess.run(['git', 'show', '%s:concours/logx_statusbar.js' % rev],
                         cwd=BASE, capture_output=True, text=True,
                         encoding='utf-8', check=True)
    return out.stdout


def _demarrer(meteo_chaude_a=None, orage=False, rev=None):
    """Charge la barre (donc boot() : insert() puis refreshStorm()) sur un
    serveur dont /data/weather ne devient chaud qu'à `meteo_chaude_a` ms."""
    ctx = py_mini_racer.MiniRacer()
    ctx.eval(_PREAMBULE)
    if meteo_chaude_a is not None:
        ctx.eval('__meteoChaudeA = %d;' % meteo_chaude_a)
    if orage:
        ctx.eval('__orage = true;')
    ctx.eval(_source(rev))
    return ctx


def _avancer(ctx, ms, pas=1000):
    """Avance l'horloge virtuelle par petits pas : chaque ctx.eval() vide la
    file de micro-tâches de V8, donc les promesses `fetch` d'une reprise sont
    résolues avant que le pas suivant ne déclenche la reprise d'après."""
    reste = ms
    while reste > 0:
        d = min(pas, reste)
        ctx.eval('__advance(%d);' % d)
        reste -= d


def _affichage(ctx):
    return ctx.eval("String(document.getElementById('rcsbStormItem').style.display)")


def _texte(ctx):
    return ctx.eval("String(document.getElementById('rcsbStorm').textContent)")


def _nb_appels_meteo(ctx):
    return ctx.eval('__fetchesMeteo().length')


def _budget_reprises():
    """(nb max de reprises, délai) lus dans la source — l'assertion suit le
    réglage réel au lieu de figer un 5 × 3 s qui vieillirait mal."""
    src = _source()
    mx = re.search(r'STORM_RETRY_MAX\s*=\s*(\d+)', src)
    ms = re.search(r'STORM_RETRY_MS\s*=\s*(\d+)', src)
    assert mx and ms, "constantes de reprise de la pastille orage introuvables"
    return int(mx.group(1)), int(ms.group(1))


# ─── Le défaut, rejoué sur le code d'avant le correctif ──────────────────────

def test_reproduction_pastille_invisible_5_minutes_sur_le_commit_davant():
    """Sur 09db25a : la donnée est dispo côté serveur à t+2 s, la pastille
    reste pourtant masquée jusqu'au tic de rcPoll, 5 minutes plus tard."""
    ctx = _demarrer(meteo_chaude_a=2000, rev=REV_AVANT_FIX)
    assert _affichage(ctx) == 'none'          # cache froid : rien affiché, correct
    assert _nb_appels_meteo(ctx) == 1

    _avancer(ctx, 6000)                       # le serveur répond ok:true depuis 4 s
    assert _affichage(ctx) == 'none', \
        "ce test doit ECHOUER sur le code d'avant le correctif"
    assert _nb_appels_meteo(ctx) == 1, "aucune nouvelle tentative n'était programmée"

    _avancer(ctx, 300000)                     # premier tic rcPoll
    assert _affichage(ctx) == 'flex'          # ... enfin visible, 5 minutes trop tard
    assert _texte(ctx) == "pas d'orage"


# ─── Le même scénario sur le code actuel ─────────────────────────────────────

def test_pastille_visible_des_que_le_cache_serveur_est_chaud():
    ctx = _demarrer(meteo_chaude_a=2000)
    assert _affichage(ctx) == 'none'          # toujours pas de « — » trompeur

    _avancer(ctx, 6000)
    assert _affichage(ctx) == 'flex', \
        "la pastille orage doit apparaître en quelques secondes, pas en 5 minutes"
    assert _texte(ctx) == "pas d'orage"
    assert _nb_appels_meteo(ctx) > 1, "la reprise n'a pas eu lieu"


def test_orage_reel_detecte_des_le_demarrage():
    """Le cas qui compte vraiment : il y a de l'orage AU MOMENT où l'opérateur
    lance le logiciel et branche ses antennes."""
    ctx = _demarrer(meteo_chaude_a=2000, orage=True)
    _avancer(ctx, 6000)
    assert _affichage(ctx) == 'flex'
    assert _texte(ctx) == 'ORAGE'
    titre = ctx.eval("String(document.getElementById('rcsbStormItem').title)")
    assert 'débranche les antennes' in titre


def test_reprises_bornees_si_la_meteo_reste_indisponible():
    """La reprise ne doit pas se transformer en martèlement : serveur
    définitivement muet (ok:false), on plafonne au budget prévu et on rend la
    main au tic normal de 5 min."""
    maxi, delai = _budget_reprises()
    ctx = _demarrer()                          # __meteoChaudeA = Infinity
    _avancer(ctx, 60000)
    assert _affichage(ctx) == 'none'
    assert _nb_appels_meteo(ctx) == 1 + maxi, \
        "1 appel initial + %d reprises attendus, pas de boucle sans fin" % maxi
    # Vérifie aussi l'espacement : des reprises collées seraient une rafale.
    ts = ctx.eval('JSON.stringify(__fetchesMeteo().map(function(f){ return f.t; }))')
    ts = [int(x) for x in re.findall(r'\d+', ts)]
    assert ts == [i * delai for i in range(1 + maxi)]


def test_changement_de_locator_ne_masque_pas_la_pastille_5_minutes():
    """Deuxième occurrence du même trou : get_weather_cached() repasse à
    ok:false dès que la clé lat/lon change (locator /P saisi en arrivant sur
    site). Sans reprise, la pastille disparaît pendant 5 min en pleine
    installation d'antennes — pile quand l'alerte sert."""
    ctx = _demarrer(meteo_chaude_a=0)
    assert _affichage(ctx) == 'flex'

    # Nouveau locator : le cache serveur redevient froid, chaud 2 s plus tard.
    ctx.eval('__meteoChaudeA = 302000;')
    _avancer(ctx, 300000)                      # tic rcPoll -> réponse ok:false
    assert _affichage(ctx) == 'none'
    _avancer(ctx, 6000)
    assert _affichage(ctx) == 'flex', \
        "après un changement de locator la pastille doit revenir en secondes"


def test_le_budget_de_reprises_est_rearme_a_chaque_tic():
    """Sinon le premier démarrage épuiserait les reprises une fois pour toutes
    et le changement de locator ci-dessus retomberait dans le trou de 5 min."""
    maxi, _ = _budget_reprises()
    ctx = _demarrer()                          # jamais chaud : budget épuisé
    _avancer(ctx, 60000)
    assert _nb_appels_meteo(ctx) == 1 + maxi
    _avancer(ctx, 260000)                      # tic rcPoll à 300 s + sa reprise
    assert _nb_appels_meteo(ctx) == 2 * (1 + maxi)


def test_pas_de_qso_director():
    """Interdiction absolue (nom d'un concurrent) — jamais dans le code."""
    assert 'QSO Director' not in _source()
