# -*- coding: utf-8 -*-
"""École CW — valider() sans garde de ré-entrance (audit 22/08 logx_cw.html:288,
re-vérifié vivant le 26/08). passer() est ASYNC (await rejouer -> await jouer =
audio) mais valider() ne l'attend pas : une 2e Entrée rapide, pendant la lecture
de la station SUIVANTE (déjà avancée par idx++), la valide avec le champ VIDE ->
la note faux (❌) et saute une station, en chevauchant le son.

Ce test exécute les VRAIES fonctions valider()/passer()/rejouer() extraites de
logx_cw.html, sous stubs (jouer/document/globals). Propriété : deux valider()
enchaînés (le 2e avant que le 1er n'ait fini) ne produisent QU'UNE réponse et
n'avancent idx que d'UN. py_mini_racer draine les microtâches entre les eval."""
import os
import re

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML = os.path.join(CONCOURS, 'logx_cw.html')
py_mini_racer = pytest.importorskip('py_mini_racer')


def _extraire(nom):
    """Texte exact d'une fonction (async) `function nom(` .. accolade fermante."""
    src = open(HTML, encoding='utf-8').read()
    m = re.search(r'\n(async\s+)?function ' + re.escape(nom) + r'\s*\(', src)
    assert m, 'fonction %s introuvable' % nom
    i = m.start() + 1
    j = src.index('{', i)
    prof = 0
    for k in range(j, len(src)):
        if src[k] == '{':
            prof += 1
        elif src[k] == '}':
            prof -= 1
            if prof == 0:
                return src[i:k + 1]
    raise AssertionError('accolade fermante de %s introuvable' % nom)


_STUBS = r"""
  var enCours = true, idx = 0, reponses = [], _validation = false;
  var serie = [{call:'A',echange:''},{call:'B',echange:''},{call:'C',echange:''}];
  var _elts = {};
  function _el(id){
    if(!_elts[id]) _elts[id] = {value:'', textContent:'', className:'', disabled:false};
    return _elts[id];
  }
  var document = { getElementById:_el };
  function T(s){ return s; }
  function Tf(s){ return s; }
  function couperSon(){}
  var _joue = 0;
  // jouer = audio : asynchrone, ne résout PAS immédiatement dans le même eval
  // (comme le vrai son). On garde la promesse ouverte pour simuler « pendant la
  // lecture », puis on la résoudra au prochain eval.
  var _resoudreJouer = null;
  function jouer(texte, wpm, hz){ _joue++; return new Promise(function(r){ _resoudreJouer = r; }); }
  function terminer(){ enCours = false; return Promise.resolve(); }
"""


def _ctx():
    ctx = py_mini_racer.MiniRacer()
    ctx.eval(_STUBS)
    for nom in ('rejouer', 'passer', 'valider'):
        ctx.eval(_extraire(nom))
    return ctx


def test_double_entree_ne_valide_quune_station():
    ctx = _ctx()
    # station 0 en cours de lecture ; l'opérateur tape sa réponse
    ctx.eval("_el('saisie').value = 'A';")
    # DEUX Entrées rapides : le 2e appel arrive AVANT que passer()/jouer() du 1er
    # n'ait fini (la promesse jouer reste ouverte).
    ctx.eval("valider(); valider();")
    # Une seule réponse enregistrée, idx avancé d'UN seul cran.
    assert ctx.eval("reponses.length") == 1
    assert ctx.eval("idx") == 1
    assert ctx.eval("reponses[0]") == 'A'


def test_apres_lecture_terminee_on_peut_revalider():
    """Non-régression : une fois le son de la station suivante terminé, une
    nouvelle validation est de nouveau possible (la garde se relâche)."""
    ctx = _ctx()
    ctx.eval("_el('saisie').value = 'A';")
    ctx.eval("valider();")                 # station 0 -> B en lecture (jouer ouvert)
    ctx.eval("if(_resoudreJouer) _resoudreJouer();")   # le son de B se termine
    ctx.eval("_el('saisie').value = 'B';")
    ctx.eval("valider();")                 # station 1 -> validable
    assert ctx.eval("reponses.length") == 2
    assert ctx.eval("idx") == 2
