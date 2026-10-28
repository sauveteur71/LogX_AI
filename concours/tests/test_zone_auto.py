# -*- coding: utf-8 -*-
"""Zone CQ reçue pré-remplie d'après cty.dat (demande F4GLD 24/10/2026, CQ WW).

Exécute le VRAI logx_zone_auto.js en V8 (DOM minimal + fetch simulé qui rend
la forme RÉELLE de /exchange/check — vérifiée sur le serveur : {"match": null,
"expected": 25, "entity": "Japan", ...}). Propriétés verrouillées :
  - remplit un champ vide avec la zone attendue ;
  - suit une correction d'indicatif tant que la valeur est encore « auto » ;
  - n'écrase JAMAIS une zone tapée par l'opérateur ;
  - ignore une réponse arrivée après un changement d'indicatif ;
  - ne fait rien hors concours à zone CQ, n'invente rien si l'indicatif est inconnu."""
import json
import os

import pytest

py_mini_racer = pytest.importorskip('py_mini_racer')
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODULE = open(os.path.join(BASE, 'logx_zone_auto.js'), encoding='utf-8').read()

DOM = r"""
function Champ(id){ this.id=id; this.value=''; this.dataset={}; this.title='';
  var c={}; this.classList={add:function(k){c[k]=1;},remove:function(k){delete c[k];},
  contains:function(k){return !!c[k];}}; this._l={};
  this.addEventListener=function(t,f){ this._l[t]=f; }; }
var _els={inputCall:new Champ('inputCall'), inputNumRcvd:new Champ('inputNumRcvd')};
var document={readyState:'complete', getElementById:function(i){return _els[i]||null;},
  addEventListener:function(){}};
var currentExchange={check:'cq_zone'};
var ZONES={'JA1ABC':25,'W1AW':5,'UA9ABC':17};
var _attente=[];
function fetch(url){ var m=/call=([^&]*)/.exec(url); var call=decodeURIComponent(m[1]);
  var d={match:null, expected:(ZONES[call]===undefined?null:ZONES[call]), kind:'cq_zone', ok:true};
  return new Promise(function(res){ _attente.push(function(){
    res({ok:true, json:function(){ return Promise.resolve(d); }}); }); }); }
function setTimeout(f){ f(); return 1; } function clearTimeout(){}
var window=this; var module=undefined;
function reponses(){ while(_attente.length) _attente.shift()(); }
function tape(call){ _els.inputCall.value=call; _els.inputCall._l.input(); }
function etat(){ var z=_els.inputNumRcvd; return [z.value, z.classList.contains('zone-auto')]; }
"""


def _ctx():
    ctx = py_mini_racer.MiniRacer()
    ctx.eval(DOM)
    ctx.eval(MODULE)
    return ctx


def _pas(ctx, *etapes):
    """Chaque étape dans son propre eval : les promesses (réponses réseau) sont
    traitées entre deux étapes, comme dans le navigateur entre deux frappes."""
    for e in etapes:
        ctx.eval(e)
        ctx.eval('0')


def _etat(ctx):
    ctx.eval('0')
    return json.loads(ctx.eval('JSON.stringify(etat())'))


def test_remplit_un_champ_vide():
    ctx = _ctx()
    _pas(ctx, "tape('JA1ABC')", "reponses()")
    assert _etat(ctx) == ['25', True]


def test_suit_la_correction_d_indicatif():
    ctx = _ctx()
    _pas(ctx, "tape('JA1ABC')", "reponses()")
    assert _etat(ctx) == ['25', True]                     # déjà pré-rempli…
    _pas(ctx, "tape('W1AW')", "reponses()")
    assert _etat(ctx) == ['5', True]                      # …et remplacé, car encore « auto »


def test_n_ecrase_jamais_une_zone_tapee():
    ctx = _ctx()
    _pas(ctx, "tape('JA1ABC')", "reponses()",
         "_els.inputNumRcvd.value='4'; _els.inputNumRcvd._l.input();",
         "tape('W1AW')", "reponses()")
    assert _etat(ctx) == ['4', False]


def test_zone_tapee_avant_l_indicatif_conservee():
    ctx = _ctx()
    _pas(ctx, "_els.inputNumRcvd.value='3'; _els.inputNumRcvd._l.input();", "tape('JA1ABC')", "reponses()")
    assert _etat(ctx) == ['3', False]


def test_zone_tapee_pendant_la_requete_conservee():
    """L'opérateur tape la zone PENDANT que la réponse réseau est en route."""
    ctx = _ctx()
    _pas(ctx, "tape('JA1ABC')",
         "_els.inputNumRcvd.value='26'; _els.inputNumRcvd._l.input();",
         "reponses()")
    assert _etat(ctx) == ['26', False]


def test_reponse_perimee_ignoree():
    """Réponse pour JA1ABC arrivée APRÈS que l'indicatif est devenu W1AW."""
    ctx = _ctx()
    _pas(ctx, "tape('JA1ABC')", "_els.inputCall.value='W1AW'", "reponses()")
    assert _etat(ctx) == ['', False]


def test_indicatif_inconnu_n_invente_rien():
    ctx = _ctx()
    _pas(ctx, "tape('JA1ABC')", "reponses()", "tape('XX9ZZZ')", "reponses()")
    assert _etat(ctx) == ['', False]


def test_rien_hors_concours_a_zone_cq():
    ctx = _ctx()
    _pas(ctx, "currentExchange={check:undefined}", "tape('JA1ABC')", "reponses()")
    assert _etat(ctx) == ['', False]


def test_charge_dans_le_logbook_et_style_present():
    html = open(os.path.join(BASE, 'logx_logbook.html'), encoding='utf-8').read()
    assert '<script src="logx_zone_auto.js"></script>' in html
    assert '#inputNumRcvd.zone-auto{' in html
