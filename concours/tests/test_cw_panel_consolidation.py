# -*- coding: utf-8 -*-
"""Consolidation du décodeur CW (page de saisie, logx_logbook.html/js) :

1) BUG RÉEL — logx_logbook.js déclarait DEUX fonctions `toggleCwDecoder()` :
   une pour l'ancien panneau compact (#cwDecodePanel, dans .saisie-secondary),
   une pour le panneau flottant (#cwPanel). En JS, la seconde déclaration
   écrase silencieusement la première — le bouton du panneau compact pilotait
   donc en réalité les éléments DOM du panneau flottant, jamais les siens.
   Corrigé en supprimant le panneau compact (doublon d'UI) : un seul
   toggleCwDecoder(), un seul panneau CW dans toute l'appli.

2) BUG DE LAYOUT — _reserveBottomSpace() posait un padding-bottom sur
   .saisie-panel (le conteneur EXTERNE) pour compenser le panneau CW flottant
   (position:fixed), alors que #qsoRecPanel/#lastQsoList vivent dans
   .saisie-secondary, un conteneur ENFANT avec SA PROPRE zone de scroll
   (overflow-y:auto indépendant) — le padding ne compensait donc rien pour ce
   scroll-là. Corrigé en réduisant max-height sur le BON conteneur
   (.saisie-secondary) au lieu d'ajouter un padding-bottom : un padding-bottom
   plus grand que la boîte la force à GRANDIR pour pouvoir le contenir (CSS ne
   rend jamais une boîte plus petite que ses propres marges internes), ce qui
   la faisait déborder de .saisie-panel — voir le commentaire de
   _reserveBottomSpace() dans logx_logbook.js pour le détail vérifié
   empiriquement dans un vrai navigateur.

Ce module exécute le VRAI logx_logbook.js dans un moteur JS réel (V8 via
py_mini_racer), comme tests/test_partner_view_closed_panel.py, pour les
comportements JS ; les deux premiers points (1 = plus qu'une seule fonction
déclarée, plus de panneau compact dans le HTML) sont vérifiés par simple
lecture du source — plus robuste qu'une exécution DOM pour ce genre de
« ne doit plus jamais réapparaître »."""
import os
import re

import pytest

py_mini_racer = pytest.importorskip(
    'py_mini_racer', reason='py_mini_racer absent (voir requirements.txt) — test JS réel ignoré')

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS_PATH = os.path.join(BASE, 'logx_logbook.js')
HTML_PATH = os.path.join(BASE, 'logx_logbook.html')


def _read(path):
    with open(path, encoding='utf-8') as f:
        return f.read()


# ─── Vérifications structurelles (lecture de source, pas d'exécution) ───────

def test_un_seul_toggleCwDecoder_declare():
    """Garde-fou direct contre le bug #1 : une SEULE déclaration de fonction
    toggleCwDecoder dans tout le fichier (la seconde écrasait silencieusement
    la première). Les commentaires `//` sont retirés avant comptage — le
    commentaire expliquant CE bug cite justement le motif littéral
    "function toggleCwDecoder(" à titre d'exemple, qui matcherait sinon à
    tort comme une deuxième déclaration."""
    src_sans_commentaires = re.sub(r'//[^\n]*', '', _read(JS_PATH))
    occurrences = re.findall(r'function\s+toggleCwDecoder\s*\(', src_sans_commentaires)
    assert len(occurrences) == 1, (
        f"{len(occurrences)} déclarations de toggleCwDecoder trouvées — "
        "une seconde déclaration écraserait silencieusement la première.")


def test_pas_de_panneau_cw_compact_dans_le_html():
    """L'ancien panneau CW compact (#cwDecodePanel, dans .saisie-secondary)
    a été retiré — un seul panneau CW doit exister désormais (#cwPanel,
    flottant)."""
    html = _read(HTML_PATH)
    assert 'id="cwDecodePanel"' not in html
    assert 'id="cwDecodeBtn"' not in html
    assert 'id="cwDecodeOut"' not in html
    assert 'id="cwPanel"' in html   # le panneau flottant, lui, doit rester


def test_updateKeyerPanels_ne_reference_plus_cwDecodePanel():
    """updateKeyerPanels() ne doit plus manipuler #cwDecodePanel (élément
    supprimé) — sinon getElementById('cwDecodePanel') renverrait toujours
    null silencieusement (le piège classique déjà rencontré sur ce projet :
    un id renommé/supprimé + `if(el)` masque la panne sans jamais planter)."""
    src = _read(JS_PATH)
    m = re.search(r'function\s+updateKeyerPanels\s*\([^)]*\)\s*\{(.*?)\n\}', src, re.S)
    assert m, "updateKeyerPanels() introuvable"
    assert 'cwDecodePanel' not in m.group(1)


def test_pas_de_qso_director():
    """Interdiction absolue (nom d'un concurrent) — jamais dans le code."""
    assert 'QSO Director' not in _read(JS_PATH)
    assert 'QSO Director' not in _read(HTML_PATH)


# ─── DOM minimal (V8 réel via py_mini_racer) ─────────────────────────────────
# Même modèle que tests/test_partner_view_closed_panel.py : querySelector
# mémoïsé par sélecteur, et getBoundingClientRect() lit un _mockHeight
# settable — nécessaire ici pour exercer _reserveBottomSpace(), qui mesure
# désormais la hauteur naturelle via getBoundingClientRect() (voir bug #2).
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


def _make_ctx():
    ctx = py_mini_racer.MiniRacer()
    ctx.eval(_DOM_PREAMBLE)
    ctx.eval(_read(JS_PATH))
    return ctx


# ─── Bug #2 : _reserveBottomSpace() sur .saisie-secondary ────────────────────

def test_reserve_bottom_space_reduit_max_height_sur_saisie_secondary():
    """_reserveBottomSpace(cwPanel, .saisie-secondary) doit RÉDUIRE max-height
    de (hauteur naturelle - hauteur du panneau flottant), jamais ajouter de
    padding — sinon un padding plus grand que la boîte la force à grandir
    (voir le commentaire de la fonction) et .saisie-secondary déborderait de
    .saisie-panel, ce qui ferait défiler la zone de SAISIE elle-même hors
    champ (interdit — cf. "ZONE SECONDAIRE ... ne rogne jamais la saisie")."""
    ctx = _make_ctx()
    ctx.eval("""
    document.querySelector('.saisie-secondary')._mockHeight = 400;
    document.getElementById('cwPanel').offsetHeight = 36;   // replié
    _reserveBottomSpace(document.getElementById('cwPanel'), document.querySelector('.saisie-secondary'));
    """)
    assert ctx.eval("document.querySelector('.saisie-secondary').style.maxHeight") == '364px'
    # jamais posé du tout (contrairement à l'ancienne implémentation) : le mock
    # de style ne connaît pas paddingBottom tant que rien ne l'a écrit -> undefined/None
    assert ctx.eval("document.querySelector('.saisie-secondary').style.paddingBottom") in (None, '', '0px')

    ctx.eval("""
    document.getElementById('cwPanel').offsetHeight = 386;  // ouvert
    _reserveBottomSpace(document.getElementById('cwPanel'), document.querySelector('.saisie-secondary'));
    """)
    assert ctx.eval("document.querySelector('.saisie-secondary').style.maxHeight") == '14px'


def test_reserve_bottom_space_ne_devient_jamais_negatif():
    """Quand le panneau flottant est PLUS HAUT que la place naturellement
    disponible (petite fenêtre, tableau de bord chargé…), max-height doit
    tomber à 0 — jamais une valeur négative (invalide en CSS, et signe d'un
    calcul non borné)."""
    ctx = _make_ctx()
    ctx.eval("""
    document.querySelector('.saisie-secondary')._mockHeight = 100;
    document.getElementById('cwPanel').offsetHeight = 386;
    _reserveBottomSpace(document.getElementById('cwPanel'), document.querySelector('.saisie-secondary'));
    """)
    assert ctx.eval("document.querySelector('.saisie-secondary').style.maxHeight") == '0px'


# ─── Bug #3 : le plafond restait FIGÉ sur une mise en page transitoire ───────
# Signalé par l'utilisateur (« pourquoi ce scroll en bas avec une partie
# blanche inutile ? »), puis reproduit à la mesure sur le serveur réel.
#
# _reserveBottomSpace() pose un plafond en PIXELS ABSOLUS, mesuré à un instant
# donné. Les deux appels ne se faisaient qu'au DOMContentLoaded — donc AVANT
# que init() (asynchrone : config serveur, log, calldb) ait fini de peupler et
# d'afficher les panneaux. Le plafond était calculé sur une mise en page qui
# n'existait déjà plus, puis gardé tel quel pour toute la session.
#
# Mesure sur la page réelle, fenêtre 1400 px, panneau CW flottant FERMÉ (donc
# strictement rien à réserver) : plafond figé à 257 px alors que la zone
# pouvait occuper 366 px. Conséquences visibles, exactement celles décrites :
#   * une BANDE VIDE de 109 px sous le keyer vocal, dans le panneau de saisie ;
#   * une barre de défilement sur une zone qui aurait tenu sans.
# Après correction, même fenêtre : bande vide 0 px.
#
# Et aucun recalcul au redimensionnement : agrandir la fenêtre ne rendait
# jamais la hauteur gagnée.

def _ctx_avec_ecouteurs():
    """Comme _make_ctx(), mais window.addEventListener ENREGISTRE les
    écouteurs au lieu de les jeter — sans quoi on ne peut pas vérifier que le
    recalcul est bien reprogrammé."""
    ctx = py_mini_racer.MiniRacer()
    ctx.eval(_DOM_PREAMBLE)
    ctx.eval("window.__ecouteurs = [];"
             "window.addEventListener = function(ev){ window.__ecouteurs.push(ev); };")
    ctx.eval(_read(JS_PATH))
    return ctx


def test_le_plafond_suit_la_mise_en_page_au_lieu_de_rester_fige():
    """LE défaut. Un plafond calculé une fois pour toutes devient faux dès que
    la page finit de se construire ou que la fenêtre change de taille."""
    ctx = _make_ctx()
    ctx.eval("""
    document.querySelector('.saisie-secondary')._mockHeight = 200;
    document.getElementById('cwPanel').offsetHeight = 0;   // panneau fermé
    _majReservesBas();
    """)
    assert ctx.eval("document.querySelector('.saisie-secondary').style.maxHeight") == '200px'
    # La fenêtre grandit : la zone peut occuper davantage. Sans recalcul, elle
    # resterait bridée à 200 px et laisserait une bande vide en dessous.
    ctx.eval("""
    document.querySelector('.saisie-secondary')._mockHeight = 500;
    _majReservesBas();
    """)
    assert ctx.eval("document.querySelector('.saisie-secondary').style.maxHeight") == '500px', (
        'le plafond est reste fige sur la mesure precedente : c est exactement '
        'ce qui produisait la bande vide sous le keyer vocal')


def test_maj_reserves_bas_couvre_les_DEUX_zones():
    """Les deux panneaux flottants (CHAT en bas-droite sur le tableau du log,
    CW en bas-gauche sur la zone secondaire) doivent être traités ensemble :
    n'en recalculer qu'un laisserait l'autre figé."""
    ctx = _make_ctx()
    ctx.eval("""
    document.querySelector('.saisie-secondary')._mockHeight = 300;
    document.querySelector('.log-table-wrap')._mockHeight = 400;
    document.getElementById('cwPanel').offsetHeight = 50;
    document.getElementById('chatPanel').offsetHeight = 60;
    _majReservesBas();
    """)
    assert ctx.eval("document.querySelector('.saisie-secondary').style.maxHeight") == '250px'
    assert ctx.eval("document.querySelector('.log-table-wrap').style.maxHeight") == '340px'


def test_un_recalcul_est_reprogramme_apres_le_chargement_et_au_redimensionnement():
    """Sans ces deux reprogrammations, le plafond du DOMContentLoaded reste
    celui de toute la session — le défaut d'origine."""
    ctx = _ctx_avec_ecouteurs()
    ecouteurs = ctx.eval("JSON.stringify(window.__ecouteurs)")
    assert 'load' in ecouteurs, (
        'la mise en page n est pas encore finale au DOMContentLoaded : il faut '
        'refaire le calcul une fois la page terminee')
    assert 'resize' in ecouteurs, (
        'sans ecoute du redimensionnement, agrandir la fenetre ne rend jamais '
        'la hauteur gagnee')


def test_les_deux_reprogrammations_appellent_bien_le_recalcul():
    """Garde-fou de câblage : les écouteurs peuvent exister et ne rien faire
    d'utile. On vérifie dans la source qu'ils mènent au recalcul."""
    src = _read(JS_PATH)
    bloc_load = src[src.index("window.addEventListener('load'"):]
    bloc_load = bloc_load[:400]
    assert '_majReservesBas' in bloc_load

    bloc_resize = src[src.index("window.addEventListener('resize'"):]
    bloc_resize = bloc_resize[:400]
    assert '_majReservesBas' in bloc_resize
    assert 'clearTimeout' in bloc_resize, (
        'un redimensionnement a la souris emet des dizaines d evenements et '
        'chaque recalcul force une mesure de mise en page : il faut les grouper')


# ─── Amélioration : DERNIERS QSO SAISIS repliable ────────────────────────────

def test_toggle_last_qso_replie_et_deplie():
    """toggleLastQso() bascule .collapsed sur le titre et .hidden sur la
    liste, comme toggleSoapbox() pour REMARQUES EDI (même schéma)."""
    ctx = _make_ctx()
    ctx.eval("""
    document.getElementById('lastQsoToggle').classList.add('collapsed');
    document.getElementById('lastQsoList').classList.add('hidden');
    """)
    ctx.eval('toggleLastQso();')
    assert ctx.eval("document.getElementById('lastQsoToggle').classList.contains('collapsed')") is False
    assert ctx.eval("document.getElementById('lastQsoList').classList.contains('hidden')") is False

    ctx.eval('toggleLastQso();')
    assert ctx.eval("document.getElementById('lastQsoToggle').classList.contains('collapsed')") is True
    assert ctx.eval("document.getElementById('lastQsoList').classList.contains('hidden')") is True


# ─── Bug latent introduit puis corrigé pendant la consolidation ──────────────

def test_clear_cw_output_reinitialise_le_texte_cumule():
    """Le panneau CW flottant construit sa sortie en re-rendant tout le texte
    cumulé à chaque caractère décodé (pour permettre les mots cliquables
    hérités de l'ancien panneau compact — cf. cwToCall). clearCwOutput() doit
    donc remettre à zéro CE texte cumulé (_cwOutText), pas seulement vider le
    DOM visuellement — sinon le prochain caractère décodé referait réapparaître
    tout l'ancien texte par-dessus le champ pourtant vidé à l'écran."""
    ctx = _make_ctx()
    ctx.eval("""
    _cwOutText = 'ANCIEN TEXTE ACCUMULE';
    document.getElementById('cwOutput').textContent = 'ANCIEN TEXTE ACCUMULE';
    clearCwOutput();
    """)
    assert ctx.eval('_cwOutText') == ''
    assert ctx.eval("document.getElementById('cwOutput').textContent") == ''
