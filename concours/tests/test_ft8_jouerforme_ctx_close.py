# -*- coding: utf-8 -*-
"""FT8 — jouerForme doit fermer son AudioContext TX et retirer la source de
sourcesTxVivantes MÊME quand l'émission échoue (audit STRATE-3). Le
txCtx.close() (l.3211) était sur le chemin heureux uniquement, sans try/finally :
une erreur entre la création du contexte (l.3182) et ce close — ex. setSinkId
qui rejette sur un périphérique de sortie mal configuré — sortait de jouerForme
sans fermer le contexte NI retirer src de sourcesTxVivantes. FT8 émet toutes
les 15 s ; sur un périphérique mal réglé, chaque trame ratée fuit un
AudioContext et le pool navigateur (~6 sous Chrome) s'épuise en ~1 min ; la
source fantôme reste par ailleurs dans le Set que couperAudioTx balaie."""
import os
import re

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML = os.path.join(CONCOURS, 'logx_ft8.html')


def _fn(nom):
    src = open(HTML, encoding='utf-8').read()
    m = re.search(r'\n\s*(?:window\.\w+\s*=\s*)?(async\s+)?function ' + re.escape(nom) + r'\s*\(', src)
    assert m, 'fonction %s introuvable' % nom
    prefix = 'async ' if m.group(1) else ''
    i = src.index('function', m.start())
    j = src.index('{', i)
    prof = 0
    for k in range(j, len(src)):
        if src[k] == '{':
            prof += 1
        elif src[k] == '}':
            prof -= 1
            if prof == 0:
                return prefix + src[i:k + 1]
    raise AssertionError('accolade fermante introuvable')


# setSinkId rejette -> échec d'émission APRÈS création du contexte, avant close.
_HARNESS_ERR = """
var created = 0, closed = 0;
function _mkSrc(){ var s = { buffer:null, connect:function(){}, onended:null };
  s.start = function(){ Promise.resolve().then(function(){ if(s.onended) s.onended(); }); };
  s.stop = function(){}; return s; }
function _FakeCtx(opts){ created++;
  this.destination = {};
  this.close = function(){ closed++; };
  this.createBuffer = function(){ return { copyToChannel:function(){} }; };
  this.createBufferSource = function(){ return _mkSrc(); };
  this.createMediaStreamDestination = function(){ return { stream:{} }; };
}
var window = { AudioContext:_FakeCtx, webkitAudioContext:_FakeCtx };
var HTMLMediaElement = { prototype: { setSinkId:function(){} } };
function Audio(){ return { srcObject:null, play:function(){}, pause:function(){},
  setSinkId:function(){ return Promise.reject(new Error('périphérique inconnu')); } }; }
var document = { getElementById:function(){ return { value:'sortie-cassee' }; } };
var sourcesTxVivantes = new Set();
"""


def _run(harness):
    racer = pytest.importorskip('py_mini_racer')
    c = racer.MiniRacer()
    c.eval(harness)
    c.eval(_fn('jouerForme'))
    c.eval("jouerForme(new Float32Array(8), 12000).then(function(){}, function(){});")
    for _ in range(6):
        c.eval("0")
    return c


def test_contexte_ferme_et_source_retiree_sur_echec():
    c = _run(_HARNESS_ERR)
    assert c.eval("created") == 1, "contexte non créé (test mal câblé)"
    assert c.eval("closed") == 1, "fuite : txCtx non fermé quand setSinkId rejette"
    assert c.eval("sourcesTxVivantes.size") == 0, "source fantôme laissée dans sourcesTxVivantes"


# Chemin heureux (pas de sortie précise -> branche destination directe).
_HARNESS_OK = """
var created = 0, closed = 0;
function _mkSrc(){ var s = { buffer:null, connect:function(){}, onended:null };
  s.start = function(){ Promise.resolve().then(function(){ if(s.onended) s.onended(); }); };
  s.stop = function(){}; return s; }
function _FakeCtx(opts){ created++;
  this.destination = {};
  this.close = function(){ closed++; };
  this.createBuffer = function(){ return { copyToChannel:function(){} }; };
  this.createBufferSource = function(){ return _mkSrc(); };
  this.createMediaStreamDestination = function(){ return { stream:{} }; };
}
var window = { AudioContext:_FakeCtx, webkitAudioContext:_FakeCtx };
var HTMLMediaElement = { prototype: {} };
function Audio(){ return {}; }
var document = { getElementById:function(){ return { value:'' }; } };
var sourcesTxVivantes = new Set();
"""


def test_chemin_heureux_ferme_une_fois_et_vide_le_set():
    c = _run(_HARNESS_OK)
    assert c.eval("closed") == 1, "txCtx doit être fermé exactement une fois"
    assert c.eval("sourcesTxVivantes.size") == 0
