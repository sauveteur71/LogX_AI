# -*- coding: utf-8 -*-
"""SSTV — toggleSstvDecoder ne doit pas lancer deux démarrages concurrents
(même classe que toggleRx FT8 #326 et toggleRttyDecoder #327). _sstvDecoder
n'est assigné qu'APRÈS `await dec.start()`, donc pendant l'invite de permission
il reste null : un 2e clic ne tombe pas dans la branche STOP mais construit un
SECOND décodeur et démarre un second pipeline — le premier (flux micro +
AudioContext) est orphelin quand son start se résout et se fait écraser.

La garde vit DANS toggleSstvDecoder : test du vrai code avec un
SstvAudioDecoder factice compteur."""
import os
import re

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS = os.path.join(CONCOURS, 'logx_sstv_panel.js')


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


_HARNESS = """
var _sstvDecoder = null;
var _sstvDecoderDemarrageEnCours = false;   // garde à ajouter
var _sstvLignesRecues = 0;
var ctorCount = 0, startCount = 0, stopCount = 0;
var _resolveStart = null, _rejectStart = null;
function SstvAudioDecoder(opts){ ctorCount++;
  this.start = function(dev){ startCount++; return new Promise(function(res, rej){ _resolveStart = res; _rejectStart = rej; }); };
  this.stop = function(){ stopCount++; };
}
var _canvasCtx = { fillStyle:'', fillRect:function(){}, putImageData:function(){} };
var _el = { textContent:'', value:'', width:0, height:0,
  classList:{ add:function(){}, remove:function(){} },
  getContext:function(){ return _canvasCtx; } };
var document = { getElementById:function(){ return _el; } };
function notify(m){}
function trF(s, o){ return s; }
"""


def _ctx():
    racer = pytest.importorskip('py_mini_racer')
    c = racer.MiniRacer()
    c.eval(_HARNESS)
    c.eval(_fn('toggleSstvDecoder'))
    return c


def test_double_clic_pendant_le_demarrage_ne_construit_pas_deux_decodeurs():
    c = _ctx()
    c.eval("toggleSstvDecoder();")           # clic 1 : démarre (start en attente)
    assert c.eval("ctorCount") == 1 and c.eval("startCount") == 1
    c.eval("toggleSstvDecoder();")           # clic 2 pendant l'invite : ignoré
    assert c.eval("ctorCount") == 1, "ré-entrance : un second décodeur SSTV a été construit"
    assert c.eval("stopCount") == 0


def test_demarrage_reussi_active_le_decodeur():
    c = _ctx()
    c.eval("toggleSstvDecoder();")
    c.eval("if(_resolveStart) _resolveStart();")
    for _ in range(4):
        c.eval("0")
    assert c.eval("_sstvDecoder !== null") is True


def test_redemarrable_apres_echec_du_demarrage():
    c = _ctx()
    c.eval("toggleSstvDecoder();")
    c.eval("if(_rejectStart) _rejectStart(new Error('micro indisponible'));")
    for _ in range(4):
        c.eval("0")
    c.eval("toggleSstvDecoder();")
    assert c.eval("ctorCount") == 2, "garde coincée après échec : impossible de relancer"
