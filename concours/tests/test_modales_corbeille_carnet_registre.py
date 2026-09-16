# -*- coding: utf-8 -*-
"""CORBEILLE et le panneau de questions C1 doivent être reconnus comme des
modales par logx_theme_shortcuts.js -- diagnostic complet du 16/09/2026.

Défaut trouvé : ces deux panneaux (les plus récemment construits, 10-12/09)
n'avaient jamais été ajoutés aux DEUX registres qui protègent les autres
overlays du carnet :
  1. _elementModaleOuverte() -- sans lui, F1-F8 (macros CW/vocal, voir
     test_macros_au_clavier.py) restent actives au clavier PENDANT que le
     panneau est ouvert : une macro peut partir en émission alors que
     l'opérateur croit être dans un dialogue, pas sur le clavier de la
     station. C'est exactement le défaut déjà corrigé une fois pour
     voacapOverlay/bulkResolveOverlay (voir leur commentaire dans le
     fichier) -- non reproduit sur ces deux-là au moment de leur
     construction.
  2. Le bloc Échap -- sans lui, aucun moyen clavier de fermer ces panneaux
     (même trou que l'audit accessibilité du 09/08/2026 avait déjà comblé
     pour 6 autres overlays).

Ces tests EXÉCUTENT le vrai gestionnaire keydown (pas une recopie) dans un
moteur V8 avec un DOM minimal -- même esprit que test_macros_au_clavier.py.
"""
import os

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
THEME_SHORTCUTS_JS = os.path.join(CONCOURS, 'logx_theme_shortcuts.js')

py_mini_racer = pytest.importorskip('py_mini_racer')

_DOM_PREAMBLE = r"""
var __store = {};
function ElProxy(id){
  var s = {id:id, style:{}};
  var cls = {_s:new Set(), add:function(){for(var i=0;i<arguments.length;i++) this._s.add(arguments[i]);},
             remove:function(){for(var i=0;i<arguments.length;i++) this._s.delete(arguments[i]);},
             contains:function(c){return this._s.has(c);}};
  var handler = {
    get:function(target, prop){
      if(prop === 'classList') return cls;
      if(prop === 'style') return s.style;
      if(prop === 'addEventListener') return function(){};
      if(prop === 'querySelectorAll') return function(){ return []; };
      return s[prop];
    },
    set:function(target, prop, val){ s[prop] = val; return true; }
  };
  return new Proxy({}, handler);
}
var __keydownHandlers = [];
var document = {
  getElementById: function(id){ if(!__store[id]) __store[id] = ElProxy(id); return __store[id]; },
  addEventListener: function(type, fn){ if(type === 'keydown') __keydownHandlers.push(fn); },
  querySelector: function(){ return null; },
  readyState: 'complete',
};
var window = this;
window.addEventListener = function(){};
function MutationObserver(cb){ this.observe = function(){}; this.disconnect = function(){}; }
var journal = {corbeilleFermee: 0, carnetFerme: 0};
function closeCorbeille(){ journal.corbeilleFermee++; document.getElementById('corbeilleOverlay').classList.remove('show'); }
function closeCarnetQuestions(){ journal.carnetFerme++; document.getElementById('carnetQuestionsOverlay').classList.remove('show'); }
var isSetupDone = true;
function cwPiloteDisponible(){ return false; }
function _cancelPendingDupConfirm(){}
var localStorage = {
  _d:{}, getItem:function(k){ return (k in this._d)? this._d[k] : null; },
  setItem:function(k,v){ this._d[k]=String(v); }, removeItem:function(k){ delete this._d[k]; }
};
"""


def _ctx():
    ctx = py_mini_racer.MiniRacer()
    ctx.eval(_DOM_PREAMBLE)
    with open(THEME_SHORTCUTS_JS, encoding='utf-8') as f:
        ctx.eval(f.read())
    # setupModal fermé par défaut -- un ElProxy neuf a style.display
    # indéfini, que _elementModaleOuverte() lirait comme "ouvert" (ni
    # 'none' ni '').
    ctx.eval("document.getElementById('setupModal').style.display = 'none';")
    return ctx


def _appuyer(ctx, key):
    ctx.eval("__keydownHandlers[0]({key:%r, ctrlKey:false, altKey:false, "
              "metaKey:false, shiftKey:false, preventDefault:function(){}, "
              "target:{tagName:'BODY'}})" % key)


@pytest.mark.parametrize('overlay_id', ['corbeilleOverlay', 'carnetQuestionsOverlay'])
def test_ouvert_est_reconnu_comme_modale(overlay_id):
    """_elementModaleOuverte() doit retrouver le panneau quand il est ouvert
    -- propriété structurelle : sans ça, F1-F8 resteraient actives au
    clavier pendant que ce panneau est affiché (voir docstring)."""
    ctx = _ctx()
    ctx.eval("document.getElementById(%r).classList.add('show');" % overlay_id)
    assert ctx.eval('_modaleOuverte()') is True


def test_aucun_des_deux_ouvert_ne_declenche_de_faux_positif():
    ctx = _ctx()
    assert ctx.eval('_modaleOuverte()') is False


def test_echap_ferme_corbeille_via_sa_fonction_dediee():
    ctx = _ctx()
    ctx.eval("document.getElementById('corbeilleOverlay').classList.add('show');")
    _appuyer(ctx, 'Escape')
    assert ctx.eval('journal.corbeilleFermee') == 1
    assert ctx.eval("document.getElementById('corbeilleOverlay').classList.contains('show')") is False


def test_echap_ferme_carnet_questions_via_sa_fonction_dediee():
    ctx = _ctx()
    ctx.eval("document.getElementById('carnetQuestionsOverlay').classList.add('show');")
    _appuyer(ctx, 'Escape')
    assert ctx.eval('journal.carnetFerme') == 1


def test_echap_ne_ferme_rien_quand_aucun_des_deux_n_est_ouvert():
    ctx = _ctx()
    _appuyer(ctx, 'Escape')
    assert ctx.eval('journal.corbeilleFermee') == 0
    assert ctx.eval('journal.carnetFerme') == 0


def test_watchedids_focus_auto_contient_les_deux_panneaux():
    """3e registre trouvé en creusant (focus automatique à l'ouverture,
    MutationObserver) -- structure, pas juste une chaîne : extrait le
    tableau réel watchedIds du fichier et vérifie qu'il contient bien les
    deux id. Sans focus initial posé dedans, le piège Tab/Shift+Tab
    (également dans ce fichier) n'a rien à attraper."""
    with open(THEME_SHORTCUTS_JS, encoding='utf-8') as f:
        src = f.read()
    i = src.index('const watchedIds = [')
    bloc = src[i:src.index('];', i)]
    assert "'corbeilleOverlay'" in bloc
    assert "'carnetQuestionsOverlay'" in bloc
