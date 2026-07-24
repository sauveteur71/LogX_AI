# -*- coding: utf-8 -*-
"""i18n (logx_i18n.js) : deux lacunes structurelles qui empêchaient certains
textes DYNAMIQUES d'être retraduits — ou de l'être correctement — même quand
leur clé figure dans le dictionnaire T :

1) Le MutationObserver n'observait QUE childList (ajout de nouveaux nœuds
   ÉLÉMENTS). Un texte posé via `el.textContent = msg` sur un nœud DÉJÀ présent
   (ex. notify() qui réutilise le même nœud toast #macroToast pour chaque
   nouveau message, logx_logbook.js) ne déclenchait donc JAMAIS de
   retraduction : le message restait figé dans la langue où il a été écrit.

2) Même en observant characterData, retraduire un nœud dont le texte change
   correspond mal si le moteur continue de comparer au dictionnaire le
   PREMIER texte français jamais vu sur ce nœud (mémorisé dans ORIG) au lieu du
   texte ACTUELLEMENT affiché : un nœud toast réutilisé pour un second message
   se serait vu réafficher la traduction du PREMIER message, par-dessus le
   second — pire que ne rien traduire du tout. Corrigé via LAST_OUT (dernière
   valeur écrite PAR LE MOTEUR), qui permet de détecter qu'un nœud a été
   modifié par l'application depuis et de réarmer ORIG dessus.

Un troisième risque, introduit par le correctif lui-même et donc vérifié ici
aussi : observer characterData signifie qu'une traduction RÉUSSIE (qui modifie
nodeValue) génère elle-même une mutation — sans garde-fou, cela redéclencherait
une traduction, qui regénère une mutation, etc. (boucle infinie). LAST_OUT sert
aussi de détecteur « cette mutation est-elle NOTRE PROPRE écriture ? » pour
casser la boucle. Et les nœuds qui changent en boucle sans être du texte à
traduire (horloge, chrono, score…) doivent rester exclus, marqués par la
classe .rc-i18n-live.

Ce module exécute le VRAI logx_i18n.js dans un moteur JS réel (V8 via
py_mini_racer), comme tests/test_partner_view_closed_panel.py, avec un DOM
minimal mais réel (vrais nœuds texte/éléments chaînés par parentNode, un vrai
petit TreeWalker, un MutationObserver dont on capture le callback pour le
déclencher nous-mêmes avec des mutations synthétiques — py_mini_racer est du
V8 pur, sans DOM, donc rien ne se déclenche tout seul)."""
import os

import pytest

py_mini_racer = pytest.importorskip(
    'py_mini_racer', reason='py_mini_racer absent (voir requirements.txt) — test JS réel ignoré')

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS_PATH = os.path.join(BASE, 'logx_i18n.js')

# ─── DOM minimal mais réel (nœuds chaînés, vrai TreeWalker texte) ────────────
# À la différence du Proxy générique de test_partner_view_closed_panel.py
# (suffisant pour un DOM « à plat », getElementById/querySelector isolés),
# logx_i18n.js a besoin de PARCOURIR l'arbre (createTreeWalker) et de REMONTER
# les ancêtres (closest) : les nœuds sont donc de vrais objets avec
# parentNode/childNodes, pas des Proxy indépendants.
_DOM_PREAMBLE = r"""
function matchSel(n, sel){
  if(!n || !sel) return false;
  if(sel[0]==='#') return n.id === sel.slice(1);
  if(sel[0]==='.') return (' '+(n.className||'')+' ').indexOf(' '+sel.slice(1)+' ') >= 0;
  return (n.tagName||'').toLowerCase() === sel.toLowerCase();
}
function makeText(value){
  return {nodeType:3, nodeValue:value, parentNode:null, parentElement:null};
}
function makeEl(tag){
  var node = {nodeType:1, tagName:(tag||'DIV').toUpperCase(), id:'', className:'',
              parentNode:null, parentElement:null, childNodes:[], style:{}};
  node.nodeName = node.tagName;
  node.appendChild = function(child){ child.parentNode = node; child.parentElement = node; node.childNodes.push(child); return child; };
  node.insertBefore = function(child){ child.parentNode = node; child.parentElement = node; node.childNodes.unshift(child); return child; };
  node.setAttribute = function(k,v){ node[k]=v; };
  node.getAttribute = function(k){ return (k in node) ? node[k] : null; };
  node.addEventListener = function(){};
  node.removeEventListener = function(){};
  node.querySelector = function(){ return null; };
  node.querySelectorAll = function(){ return []; };
  node.closest = function(sel){
    var n = node;
    while(n){ if(matchSel(n, sel)) return n; n = n.parentNode; }
    return null;
  };
  Object.defineProperty(node, 'textContent', {
    get: function(){
      var s = '';
      (function walk(n){ (n.childNodes||[]).forEach(function(c){ if(c.nodeType===3) s+=c.nodeValue; else walk(c); }); })(node);
      return s;
    },
    set: function(v){
      node.childNodes = [];
      var t = makeText(String(v));
      t.parentNode = node; t.parentElement = node;
      node.childNodes.push(t);
    }
  });
  return node;
}
var NodeFilter = {SHOW_TEXT:4, FILTER_ACCEPT:1, FILTER_REJECT:2, FILTER_SKIP:3};

var __observerCallback = null;
var __observeOptions = null;
function MutationObserver(cb){ this._cb = cb; __observerCallback = cb; }
MutationObserver.prototype.observe = function(root, opts){ __observeOptions = opts; };
MutationObserver.prototype.disconnect = function(){};

var __timers = [];
function setTimeout(fn, ms){ __timers.push(fn); return __timers.length; }
function clearTimeout(id){ if(id>=1 && id<=__timers.length) __timers[id-1] = null; }
function __flushTimers(){ var t = __timers; __timers = []; t.forEach(function(fn){ if(fn) fn(); }); }

var localStorage = {
  _d:{},
  getItem:function(k){ return (k in this._d) ? this._d[k] : null; },
  setItem:function(k,v){ this._d[k]=String(v); },
  removeItem:function(k){ delete this._d[k]; },
  key:function(i){ return Object.keys(this._d)[i]; }
};
Object.defineProperty(localStorage, 'length', {get:function(){ return Object.keys(this._d).length; }});

var document = {
  readyState: 'complete',
  documentElement: makeEl('html'),
  body: makeEl('body'),
  createElement: function(tag){ return makeEl(tag); },
  getElementById: function(id){ return null; },
  querySelector: function(sel){ return null; },
  querySelectorAll: function(sel){ return []; },
  addEventListener: function(){},
  removeEventListener: function(){},
  createTreeWalker: function(root, whatToShow, filterObj){
    var out = [];
    (function collect(n){
      (n.childNodes||[]).forEach(function(c){
        if(c.nodeType === 3) out.push(c); else collect(c);
      });
    })(root);
    var idx = -1;
    return {
      nextNode: function(){
        while(true){
          idx++;
          if(idx >= out.length) return null;
          var n = out[idx];
          var res = (filterObj && filterObj.acceptNode) ? filterObj.acceptNode(n) : NodeFilter.FILTER_ACCEPT;
          if(res === NodeFilter.FILTER_ACCEPT) return n;
        }
      }
    };
  }
};
var window = this;
window.addEventListener = function(){};
window.removeEventListener = function(){};
"""


def _real_source():
    with open(JS_PATH, encoding='utf-8') as f:
        return f.read()


def _make_ctx():
    ctx = py_mini_racer.MiniRacer()
    ctx.eval(_DOM_PREAMBLE)
    return ctx


# ─── 1) Un nœud réutilisé (toast) pour DEUX messages successifs ─────────────
# Vérifié en navigateur réel (pas seulement en théorie) : `el.textContent = x`
# sur un nœud qui a déjà un enfant texte ne modifie PAS ce nœud en place — le
# DOM le REMPLACE (retrait de l'ancien nœud texte + ajout d'un nouveau), donc
# une mutation childList avec un nœud AJOUTÉ de type TEXTE (nodeType 3), PAS
# une mutation characterData. C'est exactement ce que fait notify() (`t.
# textContent = msg` sur #macroToast, réutilisé à chaque message).

def test_textcontent_replace_reused_node_is_translated_via_childlist():
    """Reproduit le cas RÉEL de notify() : #macroToast affiche un premier
    message français (traduit à l'affichage), puis un SECOND message français
    différent posé via `.textContent = msg` — qui REMPLACE le nœud texte
    (childList : ancien retiré, nouveau ajouté), pas characterData. Le second
    message doit lui aussi être retraduit sur SA PROPRE clé (le nouveau nœud
    n'a aucun historique ORIG/LAST_OUT, donc aucun risque de réafficher la
    traduction périmée du premier message par-dessus)."""
    ctx = _make_ctx()
    ctx.eval("""
    localStorage.setItem('rc_lang', 'en');
    var toastDiv = document.createElement('div');
    toastDiv.id = 'macroToast';
    toastDiv.textContent = 'Règlement';   // 1er message, clé connue du dictionnaire
    document.body.appendChild(toastDiv);
    """)
    ctx.eval(_real_source())   # init() tourne immédiatement (readyState = 'complete')
    assert ctx.eval("toastDiv.childNodes[0].nodeValue") == 'Rules'

    ctx.eval("""
    var oldNode = toastDiv.childNodes[0];
    toastDiv.textContent = 'Postes connectés :';   // notify() : nouveau message, même nœud CONTENEUR
    var newNode = toastDiv.childNodes[0];
    __observerCallback([{type:'childList', addedNodes:[newNode], removedNodes:[oldNode]}]);
    """)
    ctx.eval("__flushTimers();")
    assert ctx.eval("toastDiv.childNodes[0].nodeValue") == 'Connected stations:', (
        "le second message (nouveau nœud texte remplaçant l'ancien) doit être "
        "retraduit sur sa propre clé")


def test_toast_reused_node_second_message_is_translated():
    """Variante avec un code qui manipule node.nodeValue DIRECTEMENT (nœud
    texte dont l'IDENTITÉ ne change pas, contrairement à .textContent= ci-
    dessus) : génère une vraie mutation characterData. Le second message doit,
    là aussi, être retraduit — et ne doit JAMAIS se faire écraser par la
    traduction PÉRIMÉE du premier message mémorisée dans ORIG (le rôle précis
    de LAST_OUT, voir logx_i18n.js)."""
    ctx = _make_ctx()
    ctx.eval("""
    localStorage.setItem('rc_lang', 'en');
    var toastDiv = document.createElement('div');
    toastDiv.id = 'macroToast';
    toastDiv.textContent = 'Règlement';   // 1er message, clé connue du dictionnaire
    document.body.appendChild(toastDiv);
    """)
    ctx.eval(_real_source())   # init() tourne immédiatement (readyState = 'complete')
    assert ctx.eval("toastDiv.childNodes[0].nodeValue") == 'Rules'

    # Code (hypothétique) qui modifie directement le nœud texte EXISTANT,
    # sans changer son identité — contrairement à .textContent= (voir test
    # ci-dessus). Le navigateur générerait ici une mutation characterData.
    ctx.eval("toastDiv.childNodes[0].nodeValue = 'Postes connectés :';")
    ctx.eval("__observerCallback([{type:'characterData', target: toastDiv.childNodes[0]}]);")
    ctx.eval("__flushTimers();")
    assert ctx.eval("toastDiv.childNodes[0].nodeValue") == 'Connected stations:', (
        "le second message doit être retraduit sur sa PROPRE clé, pas remplacé "
        "par la traduction périmée du premier message mémorisée dans ORIG")


def test_observer_configure_childlist_et_characterData():
    """Garde-fou de configuration : AVANT ce correctif, seul childList était
    observé ET seuls les nœuds ÉLÉMENTS ajoutés comptaient (voir le
    commentaire retiré de logx_i18n.js) — un nœud TEXTE ajouté (le cas de
    .textContent=, cf. test précédent) était ignoré, et characterData n'était
    pas du tout observé. Les deux doivent maintenant être actifs."""
    ctx = _make_ctx()
    ctx.eval(_real_source())
    assert ctx.eval("__observeOptions.characterData") is True
    assert ctx.eval("__observeOptions.childList") is True


def test_noeud_texte_ajoute_dans_un_conteneur_live_reste_ignore():
    """Un nœud TEXTE ajouté par childList (.textContent= sur un affichage
    « chaud ») ne doit PAS déclencher de retraduction s'il est posé dans un
    conteneur .rc-i18n-live (l'horloge, par exemple, se met aussi à jour via
    `.textContent = ...` — voir logx_logbook.js updateClockAndCountdown)."""
    ctx = _make_ctx()
    ctx.eval("""
    localStorage.setItem('rc_lang', 'en');
    var clockDiv = document.createElement('div');
    clockDiv.className = 'clock rc-i18n-live';
    document.body.appendChild(clockDiv);
    """)
    ctx.eval(_real_source())
    ctx.eval("""
    clockDiv.textContent = '12:34:56 UTC';
    __observerCallback([{type:'childList', addedNodes:[clockDiv.childNodes[0]], removedNodes:[]}]);
    """)
    assert ctx.eval("__timers.length") == 0


# ─── 2) Exclusion des nœuds « chauds » (.rc-i18n-live) ──────────────────────

def test_noeud_marque_live_jamais_traduit_ni_source_de_retraduction():
    """Un texte marqué .rc-i18n-live (horloge/chrono/score) ne doit JAMAIS être
    comparé au dictionnaire (walk() doit l'ignorer), et une mutation dessus ne
    doit JAMAIS programmer de retraduction (sinon : parcours complet du DOM à
    chaque tic de l'horloge — le clignotement que le design original évitait)."""
    ctx = _make_ctx()
    ctx.eval("""
    localStorage.setItem('rc_lang', 'en');
    var clockDiv = document.createElement('div');
    clockDiv.className = 'clock rc-i18n-live';
    clockDiv.textContent = 'Règlement';   // valeur choisie exprès : traduisible SI le moteur y touchait
    document.body.appendChild(clockDiv);
    """)
    ctx.eval(_real_source())
    # walk() initial (déclenché par applyLang('en') dans init()) ne doit PAS
    # avoir traduit ce nœud malgré une clé valide dans le dictionnaire.
    assert ctx.eval("clockDiv.childNodes[0].nodeValue") == 'Règlement'

    ctx.eval("clockDiv.childNodes[0].nodeValue = 'Postes connectés :';")
    ctx.eval("__observerCallback([{type:'characterData', target: clockDiv.childNodes[0]}]);")
    assert ctx.eval("__timers.length") == 0, (
        "une mutation sur un nœud .rc-i18n-live ne doit jamais programmer de retraduction")
    # Et un nouvel élément ajouté À L'INTÉRIEUR d'un conteneur .rc-i18n-live
    # (cas d'un futur widget « chaud » qui re-render son propre sous-arbre)
    # ne doit pas non plus déclencher de retraduction.
    ctx.eval("""
    var childEl = document.createElement('span');
    clockDiv.appendChild(childEl);
    __observerCallback([{type:'childList', addedNodes:[childEl]}]);
    """)
    assert ctx.eval("__timers.length") == 0


# ─── 3) Anti-boucle : ignorer nos propres écritures ─────────────────────────

def test_propre_ecriture_ne_reprogramme_pas_une_traduction_boucle_infinie():
    """Observer characterData veut dire qu'une traduction RÉUSSIE (qui modifie
    nodeValue) génère elle-même une mutation. Sans garde-fou anti-boucle, cette
    mutation redéclencherait rcTranslate(), qui réécrirait (même valeur) donc
    regénérerait une mutation, indéfiniment. Vérifie qu'une mutation dont la
    valeur actuelle est déjà celle que LE MOTEUR a lui-même écrite en dernier
    est ignorée (aucune nouvelle traduction programmée)."""
    ctx = _make_ctx()
    ctx.eval("""
    localStorage.setItem('rc_lang', 'en');
    var toastDiv = document.createElement('div');
    toastDiv.textContent = 'Règlement';
    document.body.appendChild(toastDiv);
    """)
    ctx.eval(_real_source())
    assert ctx.eval("toastDiv.childNodes[0].nodeValue") == 'Rules'

    # Mutation « en écho » de NOTRE PROPRE écriture ci-dessus : le nodeValue
    # actuel est encore exactement ce que le moteur vient d'écrire.
    ctx.eval("__observerCallback([{type:'characterData', target: toastDiv.childNodes[0]}]);")
    assert ctx.eval("__timers.length") == 0, (
        "une mutation qui ne fait que refléter notre propre traduction précédente "
        "ne doit jamais reprogrammer une nouvelle passe (boucle infinie sinon)")
