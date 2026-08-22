# -*- coding: utf-8 -*-
"""Repli RPH de getContestEndUTC() (commit f6bfabc) — deux angles :

1) f6bfabc a remplacé la date RPH figée par un calcul dynamique
   (nextRPHWeekendUTC()), mais le repli restait déclenché dès que
   cfg.contest_end_date/contest_end_utc étaient absents, SANS jamais vérifier
   cfg.contest. Beaucoup de concours du sélecteur (CS_DATA, ex.
   REF_CHALLENGE_THF, REF_CCD_JAN1...) n'ont aucune entrée dans
   CONTEST_SCHEDULE : pour eux, contest_end_date n'est JAMAIS renseigné
   automatiquement (cf. la garde `if(sched && sched.start && ...)` à la
   sélection du concours) — le countdown affichait donc une date RPH sans
   aucun rapport avec le concours réellement choisi.

2) nextRPHWeekendUTC() fait de l'arithmétique de dates (jour de la semaine,
   bascule d'année) : vérifiée ici sur plusieurs années via une
   réimplémentation Python INDÉPENDANTE (recherche linéaire du 1er samedi,
   pas la même formule modulaire que le JS) plutôt qu'une simple relecture.

Exécute le VRAI logx_logbook.js dans un moteur JS réel (V8 via
py_mini_racer), même préambule DOM minimal que
test_logbook_render_window_reset.py, pour reproduire le scénario
concrètement plutôt que de grepper une chaîne dans le fichier source."""
import datetime
import os
import subprocess

import pytest

py_mini_racer = pytest.importorskip(
    'py_mini_racer', reason='py_mini_racer absent (voir requirements.txt) — test JS réel ignoré')

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS_PATH = os.path.join(BASE, 'logx_logbook.js')
RULES_JS_PATH = os.path.join(BASE, 'logx_contest_rules.js')
# EV-7 19e incrément : appel TOP-LEVEL renderVoiceDynPanel() dans
# logx_logbook.js -- ReferenceError au parse sans ce fichier chargé avant.
ESM_CALLBOT_JS_PATH = os.path.join(BASE, 'logx_esm_callbot.js')
# EV-7 20e incrément : appel TOP-LEVEL voiceRefreshSlots() dans
# logx_logbook.js -- même piège que renderVoiceDynPanel() (19e incrément).
VOICE_KEYER_JS_PATH = os.path.join(BASE, 'logx_voice_keyer.js')
# EV-7 33e incrément : appel TOP-LEVEL setInterval(refreshBandMap,...) dans
# logx_logbook.js -- ReferenceError au parse sans ce fichier chargé avant.
FILTRE_SPOTS_JS_PATH = os.path.join(BASE, 'logx_filtre_spots.js')

# ─── DOM minimal (identique à test_logbook_render_window_reset.py) ───────────
# logx_logbook.js est un script de page (pas un module) : il référence document/
# window/localStorage/fetch/confirm/prompt/... à la volée. Un Proxy générique
# pour les éléments DOM (getElementById) évite d'avoir à lister tous les id du
# fichier — n'importe quelle propriété lue/écrite est simplement mémorisée.
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
    commit f6bfabc) pour rejouer le scénario tel qu'il était sur ce commit."""
    if rev is None:
        with open(RULES_JS_PATH, encoding='utf-8') as f:
            src = f.read()
        with open(ESM_CALLBOT_JS_PATH, encoding='utf-8') as f:
            src += '\n' + f.read()
        with open(VOICE_KEYER_JS_PATH, encoding='utf-8') as f:
            src += '\n' + f.read()
        with open(FILTRE_SPOTS_JS_PATH, encoding='utf-8') as f:
            src += '\n' + f.read()
        with open(JS_PATH, encoding='utf-8') as f:
            return src + '\n' + f.read()
    out = subprocess.run(
        ['git', 'show', f'{rev}:concours/logx_logbook.js'],
        cwd=BASE, capture_output=True, text=True, encoding='utf-8', check=True)
    return out.stdout


def _make_ctx(rev=None, contest=None, extra_cfg=None):
    """Contexte V8 avec logx_logbook.js chargé ; si `contest` est fourni,
    pré-remplit localStorage['logx_config'] AVANT le chargement du script
    (comme un onglet rouvert avec une config déjà enregistrée) — le script ne
    lit logx_config qu'à la demande (getContestEndUTC), donc l'ordre importe
    peu ici, mais on reste cohérent avec le vrai cycle de vie de la page."""
    ctx = py_mini_racer.MiniRacer()
    ctx.eval(_DOM_PREAMBLE)
    if contest is not None or extra_cfg:
        cfg = dict(extra_cfg or {})
        if contest is not None:
            cfg['contest'] = contest
        import json
        ctx.eval(f"localStorage.setItem('logx_config', {json.dumps(json.dumps(cfg))});")
    ctx.eval(_real_source(rev))
    return ctx


# ─── Reproduction du bug SUR f6bfabc (garde-fou de non-régression) ───────────
# Sert de garde-fou : si cette assertion passait déjà sur f6bfabc, ce ne
# serait pas un vrai test de non-régression.

def test_reproduction_bug_sur_f6bfabc_concours_sans_dates_prend_la_date_rph():
    """Sur le commit d'origine : un concours SANS entrée CONTEST_SCHEDULE (donc
    sans contest_end_date auto-rempli) et sans dates explicites retombe à tort
    sur la date de fin RPH — alors que REF_CHALLENGE_THF n'a rien à voir avec
    le RPH (concours de juillet)."""
    ctx = _make_ctx(rev='f6bfabc', contest='REF_CHALLENGE_THF')
    rph_end = ctx.eval("nextRPHWeekendUTC().end.toISOString()")
    got = ctx.eval("getContestEndUTC().toISOString()")
    # Le bug : getContestEndUTC() renvoie la date RPH pour un concours qui n'est pas RPH.
    assert got == rph_end


# ─── Le même scénario, sur le code ACTUEL : plus de contamination RPH ────────

def test_getContestEndUTC_ne_retombe_plus_sur_rph_pour_un_autre_concours():
    """Un concours sans dates configurées (ni explicites, ni via
    CONTEST_SCHEDULE) doit renvoyer un état neutre (null) — jamais la date
    RPH, qui n'a de sens que pour REF_RPH."""
    ctx = _make_ctx(contest='REF_CHALLENGE_THF')
    assert ctx.eval("getContestEndUTC()") is None


def test_getContestEndUTC_ignore_aussi_les_autres_concours_hors_schedule():
    for contest in ('REF_CCD_JAN1', 'REF_CDF_HF_CW', 'REF_PRINTEMPS', 'CUSTOM'):
        ctx = _make_ctx(contest=contest)
        assert ctx.eval("getContestEndUTC()") is None, f"attendu null pour {contest}"


def test_getContestEndUTC_garde_le_repli_rph_si_le_concours_est_bien_rph():
    """Le repli dynamique doit rester actif pour REF_RPH lui-même (c'est le
    cas d'usage réel du fix f6bfabc : countdown RPH avant toute config)."""
    ctx = _make_ctx(contest='REF_RPH')
    rph_end = ctx.eval("nextRPHWeekendUTC().end.toISOString()")
    got = ctx.eval("getContestEndUTC().toISOString()")
    assert got == rph_end


def test_getContestEndUTC_garde_le_repli_rph_si_aucun_concours_selectionne():
    """Avant toute sélection de concours (logx_config vide/absent), le repli
    RPH reste le comportement par défaut (état initial de la page)."""
    ctx = _make_ctx()  # pas de logx_config du tout
    rph_end = ctx.eval("nextRPHWeekendUTC().end.toISOString()")
    got = ctx.eval("getContestEndUTC().toISOString()")
    assert got == rph_end


def test_getContestEndUTC_respecte_les_dates_explicites_quel_que_soit_le_concours():
    """Sanity check : la lecture des dates explicites (le cas normal, cf.
    CONTEST_SCHEDULE rempli à la sélection) n'est pas affectée par le fix."""
    ctx = _make_ctx(contest='CQ_WW_SSB', extra_cfg={
        'contest_end_date': '2026-10-26', 'contest_end_utc': '00:00'})
    got = ctx.eval("getContestEndUTC().toISOString()")
    assert got == '2026-10-26T00:00:00.000Z'


def test_updateClockAndCountdown_etat_neutre_sans_crash_ni_nan():
    """Le countdown ne doit ni planter ni afficher NaN quand la date de fin
    est inconnue (contestEndUTC === null) — régression possible introduite
    par le fix si le null n'est pas géré dans updateClockAndCountdown()."""
    ctx = _make_ctx(contest='REF_CHALLENGE_THF')
    ctx.eval("""
    contestEndUTC = getContestEndUTC();
    contestStartUTC = getContestStartUTC();
    isSetupDone = true;
    updateClockAndCountdown();
    """)
    txt = ctx.eval("document.getElementById('sbCountdown').textContent")
    assert 'NaN' not in txt
    assert txt != ''


# ─── Arithmétique de dates de nextRPHWeekendUTC() : vérification indépendante ─

def _reference_first_saturday_of_july(year):
    """Réimplémentation Python INDÉPENDANTE (recherche linéaire jour par jour)
    du 1er samedi de juillet — algorithme différent de la formule modulaire
    utilisée côté JS (nextRPHWeekendUTC/firstSaturdayOfJulyUTC), pour une
    vraie vérification croisée plutôt qu'un simple portage 1:1."""
    d = datetime.date(year, 7, 1)
    while d.weekday() != 5:  # Python: lundi=0 .. dimanche=6, samedi=5
        d += datetime.timedelta(days=1)
    return d


def _reference_rph_weekend(year):
    d = _reference_first_saturday_of_july(year)
    start = datetime.datetime(d.year, d.month, d.day, 14, 0, 0, tzinfo=datetime.timezone.utc)
    end = start + datetime.timedelta(hours=24)
    return start, end


def _iso(dt):
    return dt.strftime('%Y-%m-%dT%H:%M:%S.000Z')


@pytest.mark.parametrize('year', [2024, 2025, 2026, 2027, 2028, 2029, 2030, 2031])
def test_nextRPHWeekendUTC_correspond_a_la_reimplementation_python(year):
    """Couvre les 7 décalages possibles du 1er juillet dans la semaine (2024
    à 2031 fait passer par les 7 jours de la semaine pour le 1er juillet)."""
    ctx = _make_ctx()
    ref_start, ref_end = _reference_rph_weekend(year)
    # 'now' choisi tôt dans l'année : garantit qu'on lit bien l'édition DE CETTE ANNÉE.
    now_iso = f'{year}-01-15T00:00:00Z'
    got_start = ctx.eval(f"nextRPHWeekendUTC(new Date('{now_iso}')).start.toISOString()")
    got_end = ctx.eval(f"nextRPHWeekendUTC(new Date('{now_iso}')).end.toISOString()")
    assert got_start == _iso(ref_start)
    assert got_end == _iso(ref_end)


def test_nextRPHWeekendUTC_bascule_sur_lannee_suivante_apres_la_fin():
    """now = pile la fin de l'édition N (limite '<=' du code JS) doit renvoyer
    l'édition N+1, pas une édition N déjà terminée."""
    ctx = _make_ctx()
    _, ref_end_2026 = _reference_rph_weekend(2026)
    ref_start_2027, _ = _reference_rph_weekend(2027)
    now_iso = _iso(ref_end_2026)
    got_start = ctx.eval(f"nextRPHWeekendUTC(new Date('{now_iso}')).start.toISOString()")
    assert got_start == _iso(ref_start_2027)


def test_nextRPHWeekendUTC_ne_bascule_pas_juste_avant_la_fin():
    """now = 1 seconde avant la fin de l'édition N : doit encore renvoyer
    l'édition N (pas de bascule anticipée)."""
    ctx = _make_ctx()
    ref_start_2026, ref_end_2026 = _reference_rph_weekend(2026)
    now = ref_end_2026 - datetime.timedelta(seconds=1)
    got_start = ctx.eval(f"nextRPHWeekendUTC(new Date('{_iso(now)}')).start.toISOString()")
    assert got_start == _iso(ref_start_2026)


def test_pas_de_qso_director():
    """Interdiction absolue (nom d'un concurrent) — jamais dans le code."""
    with open(JS_PATH, encoding='utf-8') as f:
        assert 'QSO Director' not in f.read()
