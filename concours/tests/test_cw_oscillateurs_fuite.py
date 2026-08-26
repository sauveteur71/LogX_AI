# -*- coding: utf-8 -*-
"""École CW — jouer() ne doit pas accumuler indéfiniment les oscillateurs
terminés dans sourceEnCours (audit STRATE-3 logx_cw.html:184). Chaque élément
morse crée un oscillateur poussé dans sourceEnCours ; couperSon() vide le
tableau, mais pendant une série CONTINUE (jouer appelé caractère après
caractère sans arrêt), les oscillateurs déjà terminés n'étaient jamais retirés
— le tableau grossissait sans borne pendant tout l'entraînement. La correction
retire chaque oscillateur de sourceEnCours quand il se termine (onended)."""
import os
import re

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML = os.path.join(CONCOURS, 'logx_cw.html')


def _fn(nom):
    src = open(HTML, encoding='utf-8').read()
    m = re.search(r'\n\s*(?:async\s+)?function ' + re.escape(nom) + r'\s*\(', src)
    assert m, 'fonction %s introuvable' % nom
    i = src.index('function', m.start())
    j = src.index('{', i)
    prof = 0
    for k in range(j, len(src)):
        if src[k] == '{':
            prof += 1
        elif src[k] == '}':
            prof -= 1
            if prof == 0:
                return src[i:k + 1]
    raise AssertionError('accolade fermante introuvable')


_HARNESS = """
var MORSE = { 'E': '.' };   // un seul point -> un seul oscillateur
var sourceEnCours = [];
var ctxAudio = null;
function _FakeOsc(){ return { frequency:{value:0}, type:'', connect:function(){ return this; },
  start:function(){}, stop:function(){}, onended:null }; }
function _FakeGain(){ return { gain:{setValueAtTime:function(){}, linearRampToValueAtTime:function(){}},
  connect:function(){ return { destination:true }; } }; }
function _FakeCtx(){ this.currentTime=0; this.state='running'; this.destination={};
  this.createOscillator=function(){ return _FakeOsc(); };
  this.createGain=function(){ return _FakeGain(); };
  this.resume=function(){ this.state='running'; }; this.close=function(){}; }
var window = { AudioContext:_FakeCtx, webkitAudioContext:_FakeCtx };
function animerOnde(ms){}
function setTimeout(fn, ms){ return 0; }
function ditMs(wpm){ return 1200 / Math.max(8, Math.min(40, wpm)); }
"""


def _ctx():
    racer = pytest.importorskip('py_mini_racer')
    c = racer.MiniRacer()
    c.eval(_HARNESS)
    c.eval(_fn('jouer'))
    return c


def test_les_oscillateurs_termines_sont_retires_de_sourceEnCours():
    c = _ctx()
    c.eval("jouer('EEE', 20, 600);")           # 3 caractères 'E' -> 3 oscillateurs
    assert c.eval("sourceEnCours.length") == 3
    # Tous les oscillateurs se terminent (onended tiré par le navigateur).
    c.eval("sourceEnCours.slice().forEach(function(o){ if(typeof o.onended === 'function') o.onended(); });")
    assert c.eval("sourceEnCours.length") == 0, \
        "oscillateurs terminés jamais retirés : sourceEnCours grossit sans borne"


def test_contexte_reveille_si_suspendu():
    c = _ctx()
    c.eval("ctxAudio = new _FakeCtx(); ctxAudio.state = 'suspended';")
    c.eval("jouer('E', 20, 600);")
    assert c.eval("ctxAudio.state") == 'running', \
        "AudioContext suspendu jamais réveillé (autoplay policy) -> aucun son"
