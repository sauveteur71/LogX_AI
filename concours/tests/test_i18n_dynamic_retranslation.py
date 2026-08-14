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
  // Sélecteur d'attribut « [title] » : indispensable pour que le bloc
  // title/placeholder de walk() tourne pour de vrai. Un querySelectorAll qui
  // renvoyait [] en dur (l'état antérieur de ce faux DOM) rendait ce bloc
  // INEXÉCUTABLE en test — c'est précisément pour ça que l'oscillation
  // fr ⇄ langue cible des infobulles n'a jamais été vue ici.
  if(sel[0]==='[' && sel[sel.length-1]===']'){
    var a = sel.slice(1, -1);
    return n.nodeType === 1 && !!n.getAttribute && n.getAttribute(a) !== null;
  }
  return (n.tagName||'').toLowerCase() === sel.toLowerCase();
}
// Liste de sélecteurs séparés par des virgules, comme « [title],[placeholder] ».
function matchSelAny(n, sel){
  return String(sel).split(',').some(function(s){ return matchSel(n, s.trim()); });
}
function makeText(value){
  return {nodeType:3, nodeValue:value, parentNode:null, parentElement:null};
}
// `dataset` n'est PAS un objet ordinaire : c'est un DOMStringMap, qui REFUSE
// tout nom contenant un tiret suivi d'une minuscule (il servirait à écrire un
// attribut data-* ambigu). Le stub qui écrivait `dataset:{}` acceptait tout,
// et c'est exactement ce qui a laissé passer le défaut de l'attribut
// `aria-label` : translateAttr construisait la clé « __i18n_aria-label », le
// navigateur levait « is not a valid property name », l'exception avortait la
// boucle des attributs — et la suite restait verte parce qu'ICI rien ne
// protestait. Un faux DOM plus PERMISSIF que le vrai ne fait pas que rater un
// défaut : il certifie du code qui ne peut pas tourner.
function makeDataset(){
  return new Proxy({}, {
    set: function(cible, nom, valeur){
      if(typeof nom === 'string' && /-[a-z]/.test(nom))
        throw new SyntaxError("Failed to set a named property '" + nom +
          "' on 'DOMStringMap': '" + nom + "' is not a valid property name.");
      cible[nom] = valeur;
      return true;
    }
  });
}
function makeEl(tag){
  var node = {nodeType:1, tagName:(tag||'DIV').toUpperCase(), id:'', className:'',
              parentNode:null, parentElement:null, childNodes:[], style:{},
              dataset:makeDataset()};
  node.nodeName = node.tagName;
  node.appendChild = function(child){ child.parentNode = node; child.parentElement = node; node.childNodes.push(child); return child; };
  node.insertBefore = function(child){ child.parentNode = node; child.parentElement = node; node.childNodes.unshift(child); return child; };
  node.setAttribute = function(k,v){ node[k]=String(v); };
  node.getAttribute = function(k){ return (k in node) ? node[k] : null; };
  node.addEventListener = function(){};
  node.removeEventListener = function(){};
  node.querySelector = function(){ return null; };
  // Parcours réel du sous-arbre (éléments seulement), au lieu du [] en dur.
  node.querySelectorAll = function(sel){
    var out = [];
    (function collect(n){
      (n.childNodes||[]).forEach(function(c){
        if(c.nodeType !== 1) return;
        if(matchSelAny(c, sel)) out.push(c);
        collect(c);
      });
    })(node);
    return out;
  };
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
  // Un vrai document a TOUJOURS un titre (chaine, vide au pire) : l'omettre
  // rendait ce faux DOM infidele, et translateTitle() — appelee par init() —
  // levait alors une exception qui faisait avorter toute la passe de
  // traduction, faisant echouer les 6 tests de ce fichier pour une raison
  // etrangere a ce qu'ils verifient.
  title: 'LogX AI — Test',
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
// Le listener `storage` est capturé (comme le callback du MutationObserver) :
// c'est le seul chemin exposé qui rejoue applyLang() avec une langue
// arbitraire — dont 'fr', que window.rcTranslate() refuse par conception.
// Réaliste : c'est ce qui se produit quand la langue est changée dans un AUTRE
// onglet de l'application.
var __storageCb = null;
window.addEventListener = function(type, cb){ if(type === 'storage') __storageCb = cb; };
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


# ─── 4) Passe de comblement des traductions manquantes (24/07/2026) ─────────
# Le bouton ✅ ENREGISTRER LE QSO (submitBtn, logx_logbook.html) restait
# TOUJOURS en français quelle que soit la langue choisie : défaut le plus
# visible signalé par l'utilisateur, aucune des 7 langues traduites n'avait
# d'entrée pour ce texte dans T. Corrigé par ajout d'entrées dans le
# dictionnaire (pas de changement de logique ici) — testé pour éviter une
# régression silencieuse (clé renommée/mal orthographiée dans une des 7
# traductions, par exemple).

def test_enregistrer_le_qso_traduit_dans_les_7_langues():
    """Vérifie qu'une traduction RÉELLE (différente du français source) existe
    désormais pour ENREGISTRER LE QSO dans chacune des 7 langues traduites."""
    ctx = _make_ctx()
    ctx.eval(_real_source())
    for lang in ['en', 'de', 'es', 'it', 'pt', 'nl', 'pl']:
        ctx.eval("localStorage.setItem('rc_lang', %r);" % lang)
        translated = ctx.eval("window.rcT('ENREGISTRER LE QSO')")
        assert translated != 'ENREGISTRER LE QSO', (
            "pas de traduction pour la langue %r (clé manquante dans T)" % lang)


# ─── 5) OPTION n'est plus exclu du parcours de texte (24/07/2026) ───────────
# `<option>` était exclu du TreeWalker SHOW_TEXT de walk() (même liste que
# SCRIPT/STYLE), alors que son texte est un nœud ordinaire — sans effet sur
# option.value, donc sans risque pour la logique qui lit la valeur
# sélectionnée. Conséquence AVANT correctif : toute liste déroulante
# traduisible (sélecteur d'opérateur, de continent, de périphérique audio par
# défaut...) restait bloquée en français quelle que soit la langue choisie,
# MÊME quand sa clé existe dans le dictionnaire T — trouvé en vérifiant en
# direct dans un navigateur réel (logx_logbook.html : "— périphérique par
# défaut —" ne changeait jamais de langue).

def test_option_text_est_traduit_par_walk():
    """Un <option> dont le texte correspond à une clé du dictionnaire doit être
    traduit comme n'importe quel autre nœud texte."""
    ctx = _make_ctx()
    ctx.eval("""
    localStorage.setItem('rc_lang', 'en');
    var sel = document.createElement('select');
    var opt = document.createElement('option');
    opt.textContent = 'Règlement';   // clé connue du dictionnaire (déjà utilisée ailleurs dans ce fichier)
    sel.appendChild(opt);
    document.body.appendChild(sel);
    """)
    ctx.eval(_real_source())   # init() tourne immédiatement (readyState = 'complete')
    assert ctx.eval("opt.childNodes[0].nodeValue") == 'Rules', (
        "le texte d'un <option> doit être traduit comme un nœud texte ordinaire")


# ─── 3) Traduction du titre de l'onglet (translateTitle) ────────────────────
# Fonctionnalite livree SANS aucun test : elle a fait echouer les 6 tests
# ci-dessus (translateTitle() appelee par init() levait une exception sur un
# document sans titre, ce qui faisait avorter TOUTE la passe de traduction).
# Le defaut n'etait pas dans ce qu'elle traduit, mais dans sa capacite a
# casser tout le reste — c'est donc surtout ca qu'on fige ici.

def test_titre_traduit_via_le_suffixe_apres_le_separateur():
    """Les pages s'intitulent « LogX AI — <section> » : c'est le suffixe apres
    le tiret cadratin qui porte le sens et doit etre traduit, la marque
    restant intacte."""
    ctx = _make_ctx()
    ctx.eval("""
    localStorage.setItem('rc_lang', 'en');
    document.title = 'LogX AI — Règlement';
    """)
    ctx.eval(_real_source())
    assert ctx.eval('document.title') == 'LogX AI — Rules', (
        'le suffixe du titre doit etre traduit, la marque conservee')


def test_titre_absent_ne_casse_pas_la_traduction_de_la_page():
    """LE garde-fou : un document sans titre exploitable ne doit JAMAIS
    interrompre la passe de traduction. translateTitle() est appelee par
    init() ; si elle leve, plus une seule chaine de la page n'est traduite —
    l'utilisateur voit une interface entierement en francais sans le moindre
    message d'erreur. C'est exactement ce qui s'est produit."""
    ctx = _make_ctx()
    ctx.eval("""
    localStorage.setItem('rc_lang', 'en');
    delete document.title;               // document minimal : aucun titre
    var p = document.createElement('p');
    p.textContent = 'Règlement';         // cle connue du dictionnaire
    document.body.appendChild(p);
    """)
    ctx.eval(_real_source())             # ne doit PAS lever
    assert ctx.eval('p.childNodes[0].nodeValue') == 'Rules', (
        "un titre absent a fait avorter la traduction du reste de la page")


def test_titre_sans_correspondance_reste_inchange():
    """Non-regression inverse : un titre dont rien ne correspond au
    dictionnaire doit rester tel quel, pas devenir vide."""
    ctx = _make_ctx()
    ctx.eval("""
    localStorage.setItem('rc_lang', 'en');
    document.title = 'Titre sans correspondance possible';
    """)
    ctx.eval(_real_source())
    assert ctx.eval('document.title') == 'Titre sans correspondance possible'


# ─── 4) title / placeholder : oscillation fr ⇄ langue cible (26/07/2026) ────
# Défaut PRÉ-EXISTANT, mesuré en navigateur réel (Chrome headless, CDP) sur
# logx_propagation.html en rc_lang=de : les infobulles OSCILLAIENT entre le
# français et l'allemand — français à t+0..2s, allemand à t+3..7s, français à
# t+8..11s — et, de façon déterministe, 4 appels consécutifs à rcTranslate()
# donnaient DE, FR, DE, FR.
#
# Cause : le bloc « Attributs title / placeholder » de walk() partait de la
# valeur COURANTE de l'attribut au lieu du français mémorisé. Passe 1 : valeur =
# français, clé trouvée → allemand écrit. Passe 2 : valeur = allemand,
# dict['<allemand>'] est undefined → la branche de restauration remettait le
# français. Etc. Comme le MutationObserver relance une passe toutes les ~800 ms
# sur une page qui mute en permanence (barre de statut, panneaux), le
# clignotement était perpétuel. C'est exactement le piège que translateText()
# évitait déjà pour les nœuds texte via ORIG (« toujours partir du FRANÇAIS
# d'origine ») : le bloc attributs n'appliquait pas cette règle.
#
# UNE SEULE passe ne reproduit pas le défaut — d'où la double passe systématique
# ci-dessous. Portée : TOUS les title/placeholder de TOUTES les pages
# (22 éléments porteurs de title sur la seule page propagation).

# Vraie infobulle de logx_propagation.html (#propTabBtn-heard), celle sur
# laquelle l'oscillation a été mesurée ; présente dans les 7 langues.
TOOLTIP_FR = "Où mon signal est réellement décodé : PSK Reporter et skimmers RBN"


def _page_avec_infobulle(lang, titre=TOOLTIP_FR):
    """DOM minimal reproduisant un onglet porteur d'un `title` traduisible."""
    ctx = _make_ctx()
    ctx.eval("""
    localStorage.setItem('rc_lang', %r);
    var btn = document.createElement('button');
    btn.id = 'propTabBtn-heard';
    btn.setAttribute('title', %r);
    document.body.appendChild(btn);
    """ % (lang, titre))
    ctx.eval(_real_source())   # init() → applyLang() : 1re passe
    return ctx


def test_title_ne_revient_pas_au_francais_a_la_seconde_passe():
    """LE test de non-régression : quatre passes consécutives doivent toutes
    laisser l'infobulle dans la langue choisie. AVANT correctif la séquence
    était DE, FR, DE, FR."""
    ctx = _page_avec_infobulle('de')
    attendu = ctx.eval("(window.rcT(%r))" % TOOLTIP_FR)
    assert attendu != TOOLTIP_FR, "prérequis : la clé doit être traduite en allemand"
    assert ctx.eval("btn.getAttribute('title')") == attendu
    for passe in range(2, 6):
        ctx.eval("window.rcTranslate();")
        assert ctx.eval("btn.getAttribute('title')") == attendu, (
            "passe %d : le title est retombé en français (oscillation)" % passe)


def test_placeholder_ne_revient_pas_au_francais_a_la_seconde_passe():
    """Même défaut, même bloc de code : `placeholder` doit rester traduit d'une
    passe à l'autre (champs de saisie du log, de la config…).

    Le contrôle est fait après CHAQUE passe, jamais seulement à la fin : le
    défaut inversant la valeur à chaque passe, un nombre PAIR de passes
    retombait sur la bonne valeur et le test passait alors qu'il clignotait —
    la même raison, exactement, qui a fait que personne n'a jamais vu ce
    défaut."""
    ctx = _make_ctx()
    ctx.eval("""
    localStorage.setItem('rc_lang', 'en');
    var inp = document.createElement('input');
    inp.setAttribute('placeholder', 'Règlement');   // clé connue du dictionnaire
    document.body.appendChild(inp);
    """)
    ctx.eval(_real_source())
    assert ctx.eval("inp.getAttribute('placeholder')") == 'Rules'
    for passe in range(2, 6):
        ctx.eval("window.rcTranslate();")
        assert ctx.eval("inp.getAttribute('placeholder')") == 'Rules', (
            "passe %d : le placeholder est retombé en français (oscillation)" % passe)


def test_title_reecrit_en_francais_par_lapplication_est_retraduit():
    """Piège du mémo PÉRIMÉ (même raisonnement que LAST_OUT côté texte) :
    certains `title` sont RÉÉCRITS dynamiquement en français par l'application
    (item.title = … dans refreshBeacon()/refreshStorm() de logx_statusbar.js,
    badge/bouton/peers dans logx_logbook.js). La passe suivante doit traduire ce
    NOUVEAU libellé, et surtout PAS restaurer l'ancien français mémorisé
    par-dessus — ce qui afficherait une infobulle sans rapport avec l'état
    courant, pire que pas de traduction du tout."""
    ctx = _page_avec_infobulle('en', 'Règlement')
    assert ctx.eval("btn.getAttribute('title')") == 'Rules'

    # L'application pose un nouveau libellé français sur le MÊME élément.
    ctx.eval("btn.setAttribute('title', 'Postes connectés :');")
    ctx.eval("window.rcTranslate();")
    assert ctx.eval("btn.getAttribute('title')") == 'Connected stations:', (
        "le nouveau libellé doit être traduit sur SA PROPRE clé, pas remplacé "
        "par la traduction (ou le français) du libellé précédent")
    # Et il ne doit pas osciller non plus.
    ctx.eval("window.rcTranslate(); window.rcTranslate();")
    assert ctx.eval("btn.getAttribute('title')") == 'Connected stations:'


def test_title_non_traduisible_reecrit_par_lapplication_nest_pas_ecrase():
    """Variante du mémo périmé sans traduction disponible : un `title` posé par
    l'application et absent du dictionnaire doit rester TEL QUEL, et non se
    faire remplacer par l'ancien français mémorisé."""
    ctx = _page_avec_infobulle('en', 'Règlement')
    assert ctx.eval("btn.getAttribute('title')") == 'Rules'
    ctx.eval("btn.setAttribute('title', 'Balises actives : DL0IGI, 4U1UN');")
    ctx.eval("window.rcTranslate(); window.rcTranslate();")
    assert ctx.eval("btn.getAttribute('title')") == 'Balises actives : DL0IGI, 4U1UN', (
        "un libellé hors dictionnaire posé par l'application a été écrasé par "
        "le mémo périmé")


def test_changement_de_langue_traduit_depuis_le_francais_pas_depuis_la_precedente():
    """Le corollaire direct de la règle : après en → de, la cible doit être
    l'allemand. Traduire depuis la valeur courante (l'anglais) ne trouverait
    aucune clé et laisserait l'attribut en anglais ou le renverrait au
    français."""
    ctx = _page_avec_infobulle('en')
    en = ctx.eval("(window.rcT(%r))" % TOOLTIP_FR)
    ctx.eval("localStorage.setItem('rc_lang', 'de');")
    de = ctx.eval("(window.rcT(%r))" % TOOLTIP_FR)
    assert de != en, "prérequis : les traductions en et de doivent différer"
    ctx.eval("window.rcTranslate();")
    assert ctx.eval("btn.getAttribute('title')") == de


def test_retour_au_francais_restaure_le_title_dorigine_et_sy_tient():
    """Le retour à 'fr' (dictionnaire vide) doit restaurer le français source —
    et rester stable, sans repartir dans l'autre sens."""
    ctx = _page_avec_infobulle('de')
    assert ctx.eval("btn.getAttribute('title')") != TOOLTIP_FR
    # Langue repassée à 'fr' (ici via l'événement storage : un autre onglet).
    ctx.eval("localStorage.setItem('rc_lang', 'fr'); __storageCb({key:'rc_lang', newValue:'fr'});")
    assert ctx.eval("btn.getAttribute('title')") == TOOLTIP_FR
    ctx.eval("__storageCb({key:'rc_lang', newValue:'fr'});")
    assert ctx.eval("btn.getAttribute('title')") == TOOLTIP_FR


def test_title_hors_dictionnaire_reste_intact_sur_plusieurs_passes():
    """Non-régression inverse : un `title` sans correspondance ne doit être ni
    vidé, ni modifié, quel que soit le nombre de passes."""
    ctx = _page_avec_infobulle('de', 'Infobulle sans aucune correspondance')
    for _ in range(3):
        ctx.eval("window.rcTranslate();")
        assert ctx.eval("btn.getAttribute('title')") == 'Infobulle sans aucune correspondance'


# ─── 5) Préfixe emoji sur title / placeholder (27/07/2026) ──────────────────
# Seconde moitié du même défaut structurel : translateText() savait isoler le
# cœur alphabétique après un préfixe emoji (« 🗺️ CARTE IA ») pour ne traduire
# que lui et garder l'emoji, mais le bloc des attributs ne connaissait QUE la
# correspondance directe. Les deux règles sont désormais dans translateKey(),
# point unique appelé par les nœuds texte ET par les attributs : la divergence
# qui a produit successivement le clignotement fr ⇄ langue cible puis
# l'absence de cas n°2 côté attributs n'est plus reproductible.
#
# Effet réel : `🔍  Rechercher : Field Day, VHF, RPH, CQ WW…`
# (logx_configuration.html) était le SEUL title/placeholder à préfixe emoji de
# toute l'application sans aucune traduction — il restait en français dans les
# 7 langues. Sa clé est maintenant dans T SANS le 🔍, que le cas n°2 remet.

# Valeur exacte du placeholder de logx_configuration.html (deux espaces après
# l'emoji : c'est aussi ce que la mise en forme d'origine doit préserver).
PH_CONFIG_FR = '🔍  Rechercher : Field Day, VHF, RPH, CQ WW…'
PH_CONFIG_CORE = 'Rechercher : Field Day, VHF, RPH, CQ WW…'


def _page_avec_placeholder(lang, valeur):
    ctx = _make_ctx()
    ctx.eval("""
    localStorage.setItem('rc_lang', %r);
    var inp = document.createElement('input');
    inp.setAttribute('placeholder', %r);
    document.body.appendChild(inp);
    """ % (lang, valeur))
    ctx.eval(_real_source())
    return ctx


@pytest.mark.parametrize('lang', ['en', 'de', 'es', 'it', 'pt', 'nl', 'pl'])
def test_placeholder_a_prefixe_emoji_traduit_en_gardant_lemoji(lang):
    """Le cœur alphabétique doit être traduit et le préfixe emoji conservé tel
    quel, espaces compris — dans chacune des 7 langues."""
    ctx = _page_avec_placeholder(lang, PH_CONFIG_FR)
    coeur_traduit = ctx.eval("window.rcT(%r)" % PH_CONFIG_CORE)
    assert coeur_traduit != PH_CONFIG_CORE, (
        "prérequis : le cœur doit avoir une traduction en %r" % lang)
    assert ctx.eval("inp.getAttribute('placeholder')") == '🔍  ' + coeur_traduit, (
        "le préfixe emoji (et ses deux espaces) doit être conservé et le cœur traduit")


def test_placeholder_a_prefixe_emoji_ne_clignote_pas():
    """Le cas n°2 doit obéir à la même règle que le cas n°1 : repartir du
    français mémorisé. Sinon il rouvre exactement l'oscillation corrigée pour la
    correspondance directe — la valeur traduite ne contient plus la clé, donc la
    passe suivante ne trouverait rien et restaurerait le français."""
    ctx = _page_avec_placeholder('de', PH_CONFIG_FR)
    attendu = ctx.eval("inp.getAttribute('placeholder')")
    assert attendu != PH_CONFIG_FR
    for passe in range(2, 6):
        ctx.eval("window.rcTranslate();")
        assert ctx.eval("inp.getAttribute('placeholder')") == attendu, (
            "passe %d : le placeholder à préfixe emoji a clignoté" % passe)


def test_title_a_prefixe_emoji_traduit_via_le_coeur():
    """Même mécanisme sur `title` (et non seulement `placeholder`), avec une clé
    du dictionnaire de base préfixée d'un emoji absent de T."""
    ctx = _page_avec_infobulle('en', '🔍 Règlement')
    assert ctx.eval("btn.getAttribute('title')") == '🔍 Rules'


def test_correspondance_directe_prioritaire_sur_le_prefixe_emoji():
    """Non-régression sur les DEUX placeholders « 🔍 Rechercher … » de
    logx_logbook.html, dont la clé complète (emoji INCLUS) est dans T : la
    correspondance directe est essayée avant le cas n°2 et doit gagner, sinon
    leur traduction actuelle changerait de forme."""
    ctx = _page_avec_placeholder('de', '🔍 Rechercher un concours...')
    assert ctx.eval("inp.getAttribute('placeholder')") == '🔍 Contest suchen...'


def test_retour_au_francais_pour_un_prefixe_emoji():
    """Le retour à 'fr' doit restaurer la valeur française COMPLÈTE, emoji et
    espaces d'origine compris."""
    ctx = _page_avec_placeholder('de', PH_CONFIG_FR)
    assert ctx.eval("inp.getAttribute('placeholder')") != PH_CONFIG_FR
    ctx.eval("localStorage.setItem('rc_lang', 'fr'); __storageCb({key:'rc_lang', newValue:'fr'});")
    assert ctx.eval("inp.getAttribute('placeholder')") == PH_CONFIG_FR


def test_placeholder_technique_a_prefixe_non_lettre_reste_intact():
    """Garde-fou du cas n°2 : il déclenche sur TOUT préfixe non-lettre, pas
    seulement sur un emoji. Aucun cœur de ces 3 valeurs synthétiques n'est
    dans T, donc elles doivent rester strictement intactes : ce test se
    déclenchera si une future entrée de dictionnaire vient à en traduire un
    morceau par accident.
    Historique des témoins invalidés par un audit i18n qui les a ENSUITE
    légitimement traduits (recyclés comme placeholders réels sur
    logx_configuration.html) : « 9600 à 38400 selon marque » (amp_baudrate,
    13/08/2026), « 127.0.0.1 (ou IP du poste radio) » et « 14,21 (vide =
    toutes) » (audit statique global 18 pages, 14/08/2026). Ne PAS reprendre
    de vrai texte de l'app comme témoin ici : utiliser uniquement des valeurs
    synthétiques inventées pour ce test, garanties de ne jamais apparaître
    ailleurs dans le dictionnaire."""
    for valeur in ['127.0.0.1 (ou IP hypothétique de test, jamais dans T)',
                   '14,21 (plage hypothétique de test, jamais dans T)',
                   '42 valeur technique de test (jamais dans T)']:
        ctx = _page_avec_placeholder('de', valeur)
        for _ in range(3):
            ctx.eval("window.rcTranslate();")
            assert ctx.eval("inp.getAttribute('placeholder')") == valeur, (
                "placeholder technique %r modifié par le cas n°2" % valeur)


# ─── Un attribut à TIRET fait exploser translateAttr ─────────────────────────
# TROUVÉ À L'ÉCRAN, pas ici. En allemand, `alt` et `aria-label` restaient en
# français alors que le dictionnaire les contenait et que le moteur les
# demandait. La console disait tout :
#   Failed to set a named property '__i18n_aria-label' on 'DOMStringMap':
#   '__i18n_aria-label' is not a valid property name.
# translateAttr mémorise le français d'origine dans `dataset`, sous une clé
# fabriquée à partir du NOM de l'attribut. Un DOMStringMap refuse le tiret.
# L'exception n'était rattrapée nulle part : elle avortait le forEach, donc la
# traduction des attributs des éléments SUIVANTS aussi. Un seul `aria-label`
# suffisait à faire tomber le reste de la page.

def _page_deux_attributs(lang):
    """Un aria-label AVANT un title : si le premier lève, le second témoigne."""
    ctx = _make_ctx()
    ctx.eval("""
    localStorage.setItem('rc_lang', '%s');
    var boite = document.createElement('div');
    boite.setAttribute('aria-label', 'Vues de la propagation');
    document.body.appendChild(boite);
    var bouton = document.createElement('button');
    bouton.setAttribute('title', 'Règlement');
    document.body.appendChild(bouton);
    """ % lang)
    ctx.eval(_real_source())
    return ctx


def test_aria_label_est_traduit():
    """L'attribut au tiret lui-même."""
    ctx = _page_deux_attributs('en')
    assert ctx.eval("boite.getAttribute('aria-label')") == 'Propagation views'


def test_un_attribut_a_tiret_n_interrompt_PAS_les_suivants():
    """Le vrai dégât : ce n'est pas l'attribut fautif qui manque à l'appel,
    c'est TOUT CE QUI VIENT APRÈS. Sans le correctif, ce title reste français
    alors qu'il n'a rien à voir avec l'histoire — le genre de symptôme qu'on
    va chercher dans le dictionnaire pendant une heure."""
    ctx = _page_deux_attributs('en')
    assert ctx.eval("bouton.getAttribute('title')") == 'Rules'


def test_le_retour_au_francais_marche_aussi_pour_un_attribut_a_tiret():
    """La clé dataset sert à MÉMORISER le français : si elle n'est pas écrite,
    on traduit une fois et on ne revient jamais."""
    ctx = _page_deux_attributs('de')
    assert ctx.eval("boite.getAttribute('aria-label')") == 'Ausbreitungsansichten'
    ctx.eval("localStorage.setItem('rc_lang','fr'); __storageCb({key:'rc_lang', newValue:'fr'});")
    assert ctx.eval("boite.getAttribute('aria-label')") == 'Vues de la propagation'


def test_LE_FAUX_DOM_REFUSE_LE_TIRET_COMME_LE_VRAI():
    """Garde-fou du garde-fou, et la vraie leçon de la journée.

    Les trois tests ci-dessus ne valent QUE si ce banc d'essai est aussi
    sévère que le navigateur. Tant que le stub écrivait `dataset:{}`, un objet
    JavaScript ordinaire acceptait n'importe quelle clé : le code fautif
    passait ici et échouait chez l'utilisateur. Si quelqu'un « simplifie » un
    jour makeDataset(), c'est ce test qui tombera — pas les autres, qui
    redeviendraient silencieusement incapables de voir le défaut."""
    ctx = _make_ctx()
    assert ctx.eval("""(function(){
      var el = document.createElement('div');
      try { el.dataset['x-y'] = '1'; return 'ACCEPTE'; }
      catch(e){ return e.name; }
    })()""") == 'SyntaxError'
    # ...et une clé légitime doit toujours passer, sinon on aurait juste
    # remplacé un stub trop permissif par un stub trop strict.
    assert ctx.eval("""(function(){
      var el = document.createElement('div');
      el.dataset.__i18n_ariaLabel = 'ok';
      return el.dataset.__i18n_ariaLabel;
    })()""") == 'ok'
