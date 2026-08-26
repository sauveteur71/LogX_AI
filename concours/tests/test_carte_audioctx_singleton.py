# -*- coding: utf-8 -*-
"""Carte — les sons d'alerte ne doivent pas fuir un AudioContext par appel
(audit STRATE-3). playAlertSound() (l.2916) et alertBeep() (l.3060) créaient
un `new AudioContext()` neuf à CHAQUE alerte sans jamais le fermer ; sur une
veille DX de plusieurs heures avec des alertes répétées, le pool de contextes
du navigateur (~6 max sous Chrome) s'épuise et le constructeur finit par
lever — plus aucun son (avalé par le catch). Un contexte partagé réutilisé
corrige la fuite."""
import os
import re

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML = os.path.join(CONCOURS, 'logx_carte.html')


def _fn(nom):
    """Extrait une fonction par appariement d'accolades, ou None si absente."""
    src = open(HTML, encoding='utf-8').read()
    m = re.search(r'\n\s*(?:async\s+)?function ' + re.escape(nom) + r'\s*\(', src)
    if not m:
        return None
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
    raise AssertionError('accolade fermante introuvable pour %s' % nom)


_HARNESS = """
var ctxCount = 0;
function _FakeNode(){ return { frequency:{setValueAtTime:function(){},value:0},
  gain:{setValueAtTime:function(){},exponentialRampToValueAtTime:function(){},value:0},
  type:'', connect:function(){}, start:function(){}, stop:function(){} }; }
function _FakeCtx(){ ctxCount++; this.currentTime=0; this.state='running';
  this.destination={}; this.createOscillator=function(){return _FakeNode();};
  this.createGain=function(){return _FakeNode();}; this.resume=function(){this.state='running';};
  this.close=function(){this.state='closed';}; }
var window = { AudioContext:_FakeCtx, webkitAudioContext:_FakeCtx };
var localStorage = { getItem:function(){ return '{}'; } };
var _alertAudioCtx = null;   // état module réel, déclaré hors des fonctions extraites
"""


def _ctx():
    racer = pytest.importorskip('py_mini_racer')
    c = racer.MiniRacer()
    c.eval(_HARNESS)
    for nom in ('alertAudioCtx', 'alertSettings', 'playAlertSound', 'alertBeep'):
        src = _fn(nom)
        if src:
            c.eval(src)
    return c


def test_playAlertSound_reutilise_un_seul_contexte():
    c = _ctx()
    c.eval("playAlertSound(); playAlertSound(); playAlertSound();")
    assert c.eval("ctxCount") == 1, "un AudioContext neuf est créé à chaque son (fuite)"


def test_alertBeep_partage_le_meme_contexte_que_playAlertSound():
    c = _ctx()
    c.eval("playAlertSound(); alertBeep('mult'); alertBeep('mention');")
    assert c.eval("ctxCount") == 1, "playAlertSound et alertBeep doivent partager un seul contexte"
