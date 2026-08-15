# -*- coding: utf-8 -*-
"""Retour F4GLD (15/08/2026) : « est-ce qu'il est possible d'avoir un rapport
automatique de bug, genre une demande d'un utilisateur qui n'aboutit pas et
hop direct un rapport automatique ». Décision : jamais d'ENVOI silencieux
vers GitHub (window.open() de openReportIssue() reste un clic explicite de
l'opérateur), mais un bandeau non bloquant apparaît dès qu'une requête a
échoué pour de bon (IA dans CARTE IA, commande CAT), avec le contexte de
l'échec déjà rédigé dans le brouillon.

Trois volets testés ici, même patron que les autres tests de
concours/logx_statusbar.js (VRAI code extrait par comptage d'accolades,
exécuté dans un moteur JS réel via py_mini_racer) :

1. showReportBanner()/hideReportBanner() (logx_statusbar.js) : DOM auto-
   injecté, bouton "Signaler" -> openReportIssue(prefill) puis fermeture.
2. openReportIssue(prefillDescription) (logx_statusbar.js) : le nouveau
   paramètre optionnel saute le prompt() natif quand fourni (bouton MANUEL
   de la barre continue d'utiliser prompt(), appelé sans argument).
3. Câblage statique (regex sur le vrai code source, comme
   test_cat_radio_suggestions.py) : les points d'échec identifiés dans
   logx_carte.html et logx_hardware_cat.js appellent bien la nouvelle
   fonction, avec le contexte disponible à cet endroit (message d'erreur,
   question posée le cas échéant)."""
import json
import os
import urllib.parse

import pytest

py_mini_racer = pytest.importorskip(
    'py_mini_racer', reason='py_mini_racer absent (voir requirements.txt) — test JS réel ignoré')

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATUSBAR_JS = os.path.join(BASE, 'logx_statusbar.js')
CARTE_HTML = os.path.join(BASE, 'logx_carte.html')
HARDWARE_CAT_JS = os.path.join(BASE, 'logx_hardware_cat.js')


def _lire(path):
    with open(path, encoding='utf-8') as f:
        return f.read()


# ─── Volet 1 : bandeau non bloquant ─────────────────────────────────────────

def _extract_banner_block(src):
    """De 'let _reportBannerEl' à la fin de
    'window.rcShowReportBanner = showReportBanner;' inclus — comptage
    d'accolades pour la fonction showReportBanner(), le reste est linéaire."""
    start = src.index('let _reportBannerEl = null;')
    end_marker = 'window.rcShowReportBanner = showReportBanner;'
    end = src.index(end_marker) + len(end_marker)
    return src[start:end]


_BANNER_HARNESS_PREAMBLE = r"""
function rcT(s){ return s; }
var __store = {};
function ElProxy(){
  var s = {value:'', textContent:'', innerHTML:'', title:'', style:{}, children:[]};
  var cls = {_s:new Set(), add:function(){for(var i=0;i<arguments.length;i++) this._s.add(arguments[i]);},
             remove:function(){for(var i=0;i<arguments.length;i++) this._s.delete(arguments[i]);},
             contains:function(c){return this._s.has(c);}};
  var listeners = {};
  var handler = {
    get:function(target, prop){
      if(prop === 'classList') return cls;
      if(prop === 'style') return s.style;
      if(prop === 'addEventListener') return function(evt, fn){ listeners[evt] = fn; };
      if(prop === '__fire') return function(evt){ if(listeners[evt]) listeners[evt](); };
      if(prop === 'querySelector') return function(sel){
        var id = sel.replace('#', '');
        return __store[id] || (__store[id] = ElProxy());
      };
      if(prop === 'appendChild') return function(c){ s.children.push(c); return c; };
      return s[prop];
    },
    set:function(target, prop, val){
      if(prop === 'innerHTML'){
        // Simule l'analyse du markup pour peupler __store des ids référencés
        // par le vrai HTML (rcsbReportBannerMsg/Dismiss/Signal) -- suffisant
        // pour ce test, pas un vrai parseur DOM.
        var re = /id="([^"]+)"/g; var m;
        while((m = re.exec(val))){ if(!__store[m[1]]) __store[m[1]] = ElProxy(); }
      }
      s[prop] = val; return true;
    }
  };
  return new Proxy({}, handler);
}
var document = {
  createElement: function(){ return ElProxy(); },
  getElementById: function(id){ if(!__store[id]) __store[id] = ElProxy(); return __store[id]; },
  body: { appendChild: function(el){ __store['rcsbReportBanner'] = el; } },
};
var window = this;
function setTimeout(fn, ms){ return 0; }
function clearTimeout(id){}
var _openReportIssueCalls = [];
function openReportIssue(prefill){ _openReportIssueCalls.push(prefill); }
"""


@pytest.fixture
def moteur_bandeau():
    ctx = py_mini_racer.MiniRacer()
    ctx.eval(_BANNER_HARNESS_PREAMBLE)
    ctx.eval(_extract_banner_block(_lire(STATUSBAR_JS)))
    return ctx


def test_banniere_exposee_globalement():
    assert 'window.rcShowReportBanner = showReportBanner;' in _lire(STATUSBAR_JS)


def test_afficher_le_bandeau_pose_le_message_et_ouvre_letat_visible(moteur_bandeau):
    moteur_bandeau.eval("showReportBanner('Un message', 'contexte pré-rempli');")
    assert moteur_bandeau.eval("document.getElementById('rcsbReportBannerMsg').textContent") == 'Un message'
    assert moteur_bandeau.eval(
        "document.getElementById('rcsbReportBanner').classList.contains('show')") is True


def test_clic_ignorer_masque_sans_appeler_openreportissue(moteur_bandeau):
    moteur_bandeau.eval("showReportBanner('Un message', 'contexte');")
    moteur_bandeau.eval("document.getElementById('rcsbReportBannerDismiss').__fire('click');")
    assert moteur_bandeau.eval(
        "document.getElementById('rcsbReportBanner').classList.contains('show')") is False
    assert moteur_bandeau.eval("_openReportIssueCalls.length") == 0


def test_clic_signaler_appelle_openreportissue_avec_le_prefill_et_masque(moteur_bandeau):
    moteur_bandeau.eval("showReportBanner('Un message', 'contexte pré-rempli exact');")
    moteur_bandeau.eval("document.getElementById('rcsbReportBannerSignal').__fire('click');")
    assert moteur_bandeau.eval("_openReportIssueCalls[0]") == 'contexte pré-rempli exact'
    assert moteur_bandeau.eval(
        "document.getElementById('rcsbReportBanner').classList.contains('show')") is False


# ─── Volet 2 : openReportIssue(prefillDescription) ─────────────────────────
# Même technique d'extraction que test_report_issue_form_prefill.py.

def _extract_report_block(src):
    start = src.index('const REPORT_REPO_FALLBACK')
    func_start = src.index('function openReportIssue(', start)
    brace_open = src.index('{', func_start)
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


_REPORT_HARNESS_PREAMBLE = r"""
function rcT(s){ return s; }
var navigator = { platform: 'Win32', userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)' };
var openedUrl = null;
var window = { open: function(url){ openedUrl = url; return {}; } };
var promptCalled = false;
var promptReturn = '';
function prompt(msg, def){ promptCalled = true; return promptReturn; }
var _updState = { current: '0.9-beta2', repo: 'octo/repo' };
var _fastVersion = null;
function fetch(){ return Promise.resolve({ ok:false }); }
"""


@pytest.fixture
def moteur_report():
    ctx = py_mini_racer.MiniRacer()
    ctx.eval(_REPORT_HARNESS_PREAMBLE)
    ctx.eval(_extract_report_block(_lire(STATUSBAR_JS)))
    return ctx


def _query_params(url):
    parsed = urllib.parse.urlsplit(url)
    return dict(urllib.parse.parse_qsl(parsed.query, keep_blank_values=True))


def test_prefill_fourni_saute_le_prompt_natif(moteur_report):
    moteur_report.eval("openReportIssue('Contexte auto-rédigé — échec détecté');")
    assert moteur_report.eval('promptCalled') is False
    url = moteur_report.eval('openedUrl')
    params = _query_params(url)
    assert params.get('description') == 'Contexte auto-rédigé — échec détecté'


def test_sans_argument_le_bouton_manuel_utilise_toujours_le_prompt(moteur_report):
    moteur_report.eval("promptReturn = 'Décrit au clavier par l\\'opérateur';")
    moteur_report.eval('openReportIssue();')
    assert moteur_report.eval('promptCalled') is True
    url = moteur_report.eval('openedUrl')
    params = _query_params(url)
    assert params.get('description') == "Décrit au clavier par l'opérateur"


def test_prefill_reste_borne_par_report_field_max(moteur_report):
    """Le contexte auto-rédigé passe par la MÊME troncature encodée que la
    saisie manuelle -- un message d'erreur anormalement long ne doit pas
    produire une URL au-delà de la marge de sécurité GitHub (414)."""
    long_ctx = 'É' * 3000  # accentué : gonfle fort une fois encodeURIComponent()
    moteur_report.eval('openReportIssue(' + json.dumps(long_ctx) + ');')
    url = moteur_report.eval('openedUrl')
    params = _query_params(url)
    assert len(urllib.parse.quote(params['description'])) <= 1500 + 50  # marge de troncature + suffixe


# ─── Volet 3 : câblage statique aux points d'échec identifiés ──────────────

def test_carte_ia_appelle_reportaifailure_apres_echec_du_lancement():
    src = _lire(CARTE_HTML)
    assert 'function reportAiFailure(errMessage, userText)' in src
    m = src.index("bub.textContent=`❌ ${err.message}")
    fenetre = src[m:m + 400]
    assert 'reportAiFailure(err.message, text)' in fenetre


def test_freetextoffline_point_dacchroche_unique_pour_sse_et_polling():
    """freeTextOffline() est le SEUL point d'affichage final partagé par le
    flux SSE ('failed') et le repli polling (status==='error') -- y accrocher
    reportAiFailure() une seule fois couvre les deux chemins sans dupliquer
    l'appel à chaque site."""
    src = _lire(CARTE_HTML)
    m = src.index('function freeTextOffline(bub,err){')
    fin = src.index('\n}', m)
    corps = src[m:fin]
    assert 'reportAiFailure(err);' in corps
    # Les deux VRAIS appelants passent bien par cette fonction (pas un doublon
    # d'affichage direct qui contournerait le nouveau hook).
    assert 'else{freeTextOffline(bub,err);}' in src  # SSE 'failed'
    assert 'freeTextOffline(bub,s.error);' in src  # pollAnalyze


def test_cat_notifierechecCat_definie_et_appelee_aux_3_commandes():
    src = _lire(HARDWARE_CAT_JS)
    assert 'function notifierEchecCat(contexte, errMsg)' in src
    assert "notifierEchecCat('armer une réponse WSJT-X'" in src
    assert "notifierEchecCat('armer l'" in src or "armer l\\'appel automatique" in src
    assert "notifierEchecCat('couper l" in src


def test_notifierechecCat_notifie_meme_sans_rcshowreportbanner_disponible():
    """rcShowReportBanner (logx_statusbar.js) est optionnel -- si absent
    (page qui ne l'aurait pas chargé), notifierEchecCat() doit encore
    notifier normalement, juste sans le bandeau."""
    src = _lire(HARDWARE_CAT_JS)
    m = src.index('function notifierEchecCat(contexte, errMsg){')
    fin = src.index('\n}', m)
    corps = src[m:fin]
    # La notification usuelle est appelée AVANT le test de disponibilité du
    # bandeau -- jamais conditionnée à sa présence.
    idx_notify = corps.index('notify(')
    idx_check = corps.index("typeof window.rcShowReportBanner")
    assert idx_notify < idx_check
