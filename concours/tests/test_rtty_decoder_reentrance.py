# -*- coding: utf-8 -*-
"""RTTY — toggleRttyDecoder ne doit pas se saborder sur un double-clic pendant
le démarrage async (audit STRATE-3 logx_rtty.html:326). _rttyDecoder était
posé SYNCHRONEMENT (l.326) avant `await start()` (l.335). Un 2e clic pendant le
start voyait _rttyDecoder truthy et entrait dans la branche STOP : stop() +
_rttyDecoder=null sur un décodeur ENCORE en démarrage (course, flux micro
orphelin, UI qui affiche « en cours » alors que _rttyDecoder est null). Même
classe que toggleRx FT8 (#326). Fix : n'assigner _rttyDecoder qu'après succès
du start + garde de démarrage.

La garde vit DANS toggleRttyDecoder : on teste le vrai toggleRttyDecoder avec
un RttyAudioDecoder factice (compteur constructions/start/stop)."""
import os
import re

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML = os.path.join(CONCOURS, 'logx_rtty.html')


def _fn(nom):
    src = open(HTML, encoding='utf-8').read()
    m = re.search(r'\n\s*window\.' + re.escape(nom) + r'\s*=\s*(async\s+)?function', src)
    assert m, 'fonction %s introuvable' % nom
    prefix = 'window.%s = %sfunction' % (nom, 'async ' if m.group(1) else '')
    i = src.index('function', m.start())
    j = src.index('{', i)
    prof = 0
    for k in range(j, len(src)):
        if src[k] == '{':
            prof += 1
        elif src[k] == '}':
            prof -= 1
            if prof == 0:
                return prefix + src[src.index('(', i):k + 1]
    raise AssertionError('accolade fermante introuvable')


_HARNESS = """
var _rttyDecoder = null;
var _rttyDecoderDemarrageEnCours = false;   // garde à ajouter
var _rttyTexte = '';
var ctorCount = 0, startCount = 0, stopCount = 0;
var _resolveStart = null, _rejectStart = null;
function RttyAudioDecoder(opts){
  ctorCount++;
  this.start = function(dev){ startCount++; return new Promise(function(res, rej){ _resolveStart = res; _rejectStart = rej; }); };
  this.stop = function(){ stopCount++; };
  this.setShift = function(){};
}
function rttyTons(){ return {mark:2125, space:2295}; }
function rttyRender(t){}
function notify(m){}
function trF(s, o){ return s; }
var _el = { textContent:'', value:'', classList:{ add:function(){}, remove:function(){} } };
var document = { getElementById:function(){ return _el; } };
var window = {};
"""


def _ctx():
    racer = pytest.importorskip('py_mini_racer')
    c = racer.MiniRacer()
    c.eval(_HARNESS)
    c.eval(_fn('toggleRttyDecoder'))
    return c


def test_double_clic_pendant_le_demarrage_ne_stoppe_pas_le_decodeur():
    c = _ctx()
    c.eval("window.toggleRttyDecoder();")   # clic 1 : démarre (start en attente)
    assert c.eval("ctorCount") == 1 and c.eval("startCount") == 1
    c.eval("window.toggleRttyDecoder();")   # clic 2 pendant l'invite : ne doit RIEN saborder
    assert c.eval("stopCount") == 0, "ré-entrance : le décodeur en démarrage a été stoppé par le 2e clic"
    assert c.eval("ctorCount") == 1, "un second décodeur a été construit"


def test_demarrage_reussi_active_le_decodeur():
    c = _ctx()
    c.eval("window.toggleRttyDecoder();")
    c.eval("if(_resolveStart) _resolveStart();")
    for _ in range(4):
        c.eval("0")
    assert c.eval("_rttyDecoder !== null") is True, "après succès du start, _rttyDecoder doit être actif"


def test_redemarrable_apres_echec_du_demarrage():
    c = _ctx()
    c.eval("window.toggleRttyDecoder();")
    c.eval("if(_rejectStart) _rejectStart(new Error('micro indisponible'));")
    for _ in range(4):
        c.eval("0")
    c.eval("window.toggleRttyDecoder();")   # doit pouvoir relancer
    assert c.eval("ctorCount") == 2, "garde coincée après échec : impossible de relancer le décodeur"
