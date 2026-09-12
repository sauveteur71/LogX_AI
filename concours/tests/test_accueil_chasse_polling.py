# -*- coding: utf-8 -*-
"""Rafraîchissement automatique de la need-list + des panneaux d'activation
dans l'activité « activation portable » (logx_accueil.js) -- écart de
comportement signalé le 12/09/2026, corrigé : l'ancienne page CHASSE
(avant fusion, incr. 5c) pollait en continu (rcPollOr, cadences par
ressource) ; la fusion avait perdu ce rafraîchissement, ne rechargeant plus
que sur clic/changement d'objectif.

`_demarrerPollingChasse()` reproduit les MÊMES cadences que l'ancienne
implémentation (`git show 989d79d~1:concours/logx_chasse.html`) : need-list
60 s, POTA 2 min, SOTA 60 s, WWFF 60 s, WCA 5 min, DXpéditions 2 min.

Exécute le VRAI logx_accueil.js en V8 (py_mini_racer). `window.rcPoll` est
stubbé pour ENREGISTRER les inscriptions (fn, ms) sans les exécuter --
aucun vrai minuteur dans le test, chaque fn capturée peut être invoquée
directement pour vérifier QUELLE ressource elle recharge (via `fetch`,
lui aussi stubbé pour enregistrer les URL appelées)."""
import os

import pytest

py_mini_racer = pytest.importorskip(
    'py_mini_racer', reason='py_mini_racer absent (voir requirements.txt) — test JS réel ignoré')

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS_PATH = os.path.join(BASE, 'logx_accueil.js')

_DOM_PREAMBLE = r"""
var __store = {};
var __redirected = null;
function ElProxy(){
  var s = {value:'', textContent:'', innerHTML:''};
  return new Proxy({}, {
    get:function(target, prop){ return s[prop]; },
    set:function(target, prop, val){ s[prop] = val; return true; }
  });
}
var document = {
  getElementById: function(id){ if(!__store[id]) __store[id] = ElProxy(); return __store[id]; },
};
var location = { href:'', search:'' };
Object.defineProperty(location, 'href', {
  get: function(){ return this._href || ''; },
  set: function(v){ this._href = v; __redirected = v; }
});
var window = { location: location };
var localStorage = {
  _d:{}, getItem:function(k){ return (k in this._d)? this._d[k] : null; },
  setItem:function(k,v){ this._d[k]=String(v); }, removeItem:function(k){ delete this._d[k]; }
};
function URLSearchParams(qs){
  var params = {};
  String(qs||'').replace(/^\?/, '').split('&').forEach(function(pair){
    if(!pair) return;
    var kv = pair.split('=');
    params[decodeURIComponent(kv[0])] = decodeURIComponent(kv[1]||'');
  });
  return { get: function(k){ return (k in params) ? params[k] : null; } };
}

// ── Stubs propres à ce fichier (fetch réseau + réseau de rendu chasse) ──────
var __fetchCalls = [];
function fetch(url){ __fetchCalls.push(url); return new Promise(function(){}); }  // jamais résolue : suffisant, on ne teste QUE l'enregistrement fetch(url), pas la suite de la chaîne .then()

var __rcPollCalls = [];
window.rcPoll = function(fn, ms){ __rcPollCalls.push({fn: fn, ms: ms}); return __rcPollCalls.length; };

window.LogxChassePanneaux = {
  esc: function(s){ return String(s == null ? '' : s); },
  renderActivationRows: function(){ return ''; },
  renderNeedList: function(){ return ''; },
  renderWcaRows: function(){ return ''; },
  renderDxRows: function(){ return ''; }
};

// Même stub que test_accueil_chasse_needlist_4a.py : un rôle 'chasse'/'mixte'
// révèle les cibles sans naviguer.
var LogxXotaRole = {
  setRole: function(){},
  getRole: function(){ return 'chasse'; },
  roleConfig: function(r){ return {chasse: (r === 'chasse' || r === 'mixte'),
                                    portable: (r === 'portable' || r === 'mixte')}; },
  ROLES: []
};
window.LogxXotaRole = LogxXotaRole;
"""


def _ctx():
    ctx = py_mini_racer.MiniRacer()
    ctx.eval(_DOM_PREAMBLE)
    with open(JS_PATH, encoding='utf-8') as f:
        ctx.eval(f.read())
    return ctx


# Ordre d'inscription dans _demarrerPollingChasse() (logx_accueil.js) --
# reflète l'ordre des appels poll(...) dans le source, documenté ici pour
# que le test explique CE QU'IL suppose plutôt que de le deviner en silence.
_ORDRE = ['needlist', 'pota', 'sota', 'wwff', 'wca', 'dx']
_CADENCE_ATTENDUE = {
    'needlist': 60 * 1000, 'pota': 2 * 60 * 1000, 'sota': 60 * 1000,
    'wwff': 60 * 1000, 'wca': 5 * 60 * 1000, 'dx': 2 * 60 * 1000,
}
_URL_ATTENDUE = {
    'needlist': '/data/spots_ranked', 'pota': '/data/pota_spots', 'sota': '/data/sota_spots',
    'wwff': '/data/wwff_spots', 'wca': '/data/wca_planned', 'dx': '/data/dxpeditions_active',
}


def test_polling_demarre_avec_les_6_ressources_attendues():
    ctx = _ctx()
    ctx.eval("_choisirRoleXota('chasse');")
    assert ctx.eval("__rcPollCalls.length") == 6


def test_polling_utilise_les_memes_cadences_que_lancienne_page_chasse():
    ctx = _ctx()
    ctx.eval("_choisirRoleXota('chasse');")
    for i, cle in enumerate(_ORDRE):
        assert ctx.eval("__rcPollCalls[%d].ms" % i) == _CADENCE_ATTENDUE[cle]


@pytest.mark.parametrize('index,cle', list(enumerate(_ORDRE)))
def test_chaque_tick_de_poll_recharge_la_bonne_ressource(index, cle):
    """Ne se contente pas de compter les inscriptions : invoque CHAQUE
    fonction capturée par rcPoll et vérifie qu'elle appelle fetch() sur
    l'URL attendue -- une cadence correcte mais associée à la mauvaise
    ressource (ex. POTA recharge en fait /data/sota_spots) passerait le
    test précédent sans être détectée ici."""
    ctx = _ctx()
    ctx.eval("_choisirRoleXota('chasse');")
    ctx.eval("__fetchCalls.length = 0;")   # ignore les appels du chargement initial
    ctx.eval("__rcPollCalls[%d].fn();" % index)
    assert ctx.eval("__fetchCalls[0]") == _URL_ATTENDUE[cle]


def test_polling_ne_senregistre_pas_deux_fois_sur_double_appel():
    """Garde d'idempotence (_xotaPollingDemarre) : un second appel à
    _revelerCiblesChasse() (hypothétique double-clic/double-route) ne doit
    pas doubler les minuteurs enregistrés."""
    ctx = _ctx()
    ctx.eval("_choisirRoleXota('chasse');")
    assert ctx.eval("__rcPollCalls.length") == 6
    ctx.eval("_revelerCiblesChasse();")
    assert ctx.eval("__rcPollCalls.length") == 6


def test_objectifs_ne_sont_pas_repolles():
    """L'ancienne page ne pollait PAS le profil d'objectifs (chargé une
    fois au démarrage) -- aucune des 6 inscriptions ne doit cibler
    /data/operator_goals."""
    ctx = _ctx()
    ctx.eval("_choisirRoleXota('chasse');")
    for i in range(6):
        ctx.eval("__fetchCalls.length = 0;")
        ctx.eval("__rcPollCalls[%d].fn();" % i)
        assert ctx.eval("__fetchCalls[0]") != '/data/operator_goals'


# ═══════════════════════════════════════════════════════════════════════════
# Message d'état vide par programme (écart de comportement signalé le
# 12/09/2026, corrigé dans logx_chasse_panneaux.renderActivationRows -- voir
# test_chasse_activation_rows.py pour le rendu lui-même). Ici : câblage
# SOURCE (pas exécuté via le harnais fetch/Promise, jamais résolu dans ce
# fichier -- voir le commentaire sur le stub `fetch` en tête) : chaque
# loader doit passer le bon `programme` à renderActivationRows.
@pytest.mark.parametrize('fonction,programme', [
    ('function _chargerPota', 'POTA'),
    ('function _chargerSota', 'SOTA'),
    ('function _chargerWwff', 'WWFF'),
])
def test_chaque_loader_passe_son_propre_programme(fonction, programme):
    """Précis fonction par fonction -- un test qui grepperait juste les 3
    littéraux 'POTA'/'SOTA'/'WWFF' n'importe où dans le fichier passerait
    même si les 3 loaders pointaient tous vers le même programme."""
    with open(JS_PATH, encoding='utf-8') as f:
        js = f.read()
    i = js.index(fonction)
    corps = js[i:js.index('\n', i)]   # chaque loader tient sur UNE ligne
    assert "programme:'%s'" % programme in corps
