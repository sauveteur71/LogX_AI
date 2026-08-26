# -*- coding: utf-8 -*-
"""TX audio — txAudioPtt doit fermer son AudioContext MÊME quand l'émission
échoue (audit STRATE-3). Le ctx.close() était sur le chemin heureux
uniquement ; une erreur entre la création du contexte (l.38) et le close
(l.61) — ex. setSinkId qui rejette sur un périphérique de sortie mal
configuré — partait par le catch sans fermer. Chaque émission ratée fuyait
alors un AudioContext ; le pool navigateur (~6 sous Chrome) s'épuise après
quelques essais et plus aucune émission audio ne démarre. txAudioPtt est le
chemin TX partagé (keyer CW, RTTY, keyer vocal, SSTV)."""
import os
import re

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS = os.path.join(CONCOURS, 'logx_tx_audio.js')


def _fn(nom):
    src = open(JS, encoding='utf-8').read()
    m = re.search(r'\n\s*(async\s+)?function ' + re.escape(nom) + r'\s*\(', src)
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


# AudioContext factice : compte les créations et les fermetures. createBuffer
# renvoie un tampon dont copyToChannel LÈVE -> simule un échec d'émission
# survenant après la création du contexte, avant le close.
_HARNESS = """
var created = 0, closed = 0;
function _FakeCtx(opts){
  created++;
  this.destination = {};
  this.close = function(){ closed++; };
  this.createBuffer = function(){ return { copyToChannel: function(){ throw new Error('emission KO'); } }; };
  this.createBufferSource = function(){ return { connect:function(){}, start:function(){}, onended:null }; };
  this.createMediaStreamDestination = function(){ return { stream:{} }; };
}
var window = { AudioContext:_FakeCtx, webkitAudioContext:_FakeCtx };
var HTMLMediaElement = { prototype: {} };   // pas de setSinkId -> branche simple
function fetch(url, opt){ return Promise.resolve({ json:function(){ return Promise.resolve({ok:true}); } }); }
var _res = null;
"""


def _run():
    racer = pytest.importorskip('py_mini_racer')
    c = racer.MiniRacer()
    c.eval(_HARNESS)
    c.eval(_fn('txAudioPtt'))
    # Émission qui va échouer (copyToChannel lève). On stocke le résultat.
    c.eval("txAudioPtt(new Float32Array(8), 44100, '').then(function(r){ _res = r; });")
    # Pompe les microtâches (fetch PTT + chaîne d'await) entre eval.
    for _ in range(5):
        c.eval("0")
    return c


def test_contexte_ferme_meme_si_emission_echoue():
    c = _run()
    assert c.eval("created") == 1, "le contexte n'a pas été créé (test mal câblé)"
    assert c.eval("closed") == 1, "fuite : AudioContext non fermé sur le chemin d'erreur"


def test_resultat_signale_l_echec():
    c = _run()
    assert c.eval("_res && _res.ok === false") is True


# Harnais chemin heureux : copyToChannel ne lève pas, onended est déclenché
# tout de suite pour que l'await se résolve.
_HARNESS_OK = """
var created = 0, closed = 0;
function _FakeCtx(opts){
  created++;
  this.destination = {};
  this.close = function(){ closed++; };
  this.createBuffer = function(){ return { copyToChannel: function(){} }; };
  this.createBufferSource = function(){
    var s = { connect:function(){}, onended:null };
    // onended est assigné APRÈS start() dans le code (await new Promise(...)) :
    // on le déclenche via une microtâche, une fois l'assignation faite.
    s.start = function(){ Promise.resolve().then(function(){ if(s.onended) s.onended(); }); };
    return s;
  };
  this.createMediaStreamDestination = function(){ return { stream:{} }; };
}
var window = { AudioContext:_FakeCtx, webkitAudioContext:_FakeCtx };
var HTMLMediaElement = { prototype: {} };
function fetch(url, opt){ return Promise.resolve({ json:function(){ return Promise.resolve({ok:true}); } }); }
var _res = null;
"""


def test_chemin_heureux_ferme_le_contexte_exactement_une_fois():
    racer = pytest.importorskip('py_mini_racer')
    c = racer.MiniRacer()
    c.eval(_HARNESS_OK)
    c.eval(_fn('txAudioPtt'))
    c.eval("txAudioPtt(new Float32Array(8), 44100, '').then(function(r){ _res = r; });")
    for _ in range(5):
        c.eval("0")
    assert c.eval("_res && _res.ok === true") is True
    assert c.eval("closed") == 1, "le contexte doit être fermé une seule fois (ni fuite, ni double close)"
