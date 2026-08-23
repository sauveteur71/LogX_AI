# -*- coding: utf-8 -*-
"""Soundcard CW (Web Audio) : cœur schedule PUR + lecteurs de config.

Le timing (schedule) et la lecture de config sont testables en V8 (py_mini_racer)
sans Web Audio (AudioContext absent -> cwSoundcardPlay se replie silencieusement).
"""
import json
import os

import pytest

py_mini_racer = pytest.importorskip('py_mini_racer', reason='py_mini_racer absent')

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
with open(os.path.join(BASE, 'logx_cw_soundcard.js'), encoding='utf-8') as f:
    _SRC = f.read()

_PRE = r"""
var _ls = {};
var localStorage = { getItem:function(k){ return (k in _ls)?_ls[k]:null; },
                     setItem:function(k,v){ _ls[k]=String(v); } };
var window = {};                 // pas d'AudioContext -> play() se replie
function setTimeout(f){ return 0; }
"""


def _ctx(config=None):
    c = py_mini_racer.MiniRacer()
    c.eval(_PRE)
    c.eval(_SRC)
    if config is not None:
        c.eval("_ls['logx_config'] = " + json.dumps(json.dumps(config)) + ";")
    return c


def _sched(c, texte, wpm):
    return json.loads(c.eval("JSON.stringify(cwSoundcardSchedule(%s, %d))"
                             % (json.dumps(texte), wpm)))


def test_lettre_E_un_seul_point():
    c = _ctx()
    assert _sched(c, 'E', 20) == [{'onset': 0, 'duree': 60}]   # dit = 1200/20 = 60


def test_lettre_A_point_gap_trait():
    c = _ctx()
    # A = '.-' : point à 0 (60 ms), gap 1 dit, trait à 120 (180 ms)
    assert _sched(c, 'A', 20) == [{'onset': 0, 'duree': 60}, {'onset': 120, 'duree': 180}]


def test_gap_inter_mot_7_dits():
    c = _ctx()
    # 'E E' : E à 0, silence inter-mot 7 dits (420 ms), E à 480
    assert _sched(c, 'E E', 20) == [{'onset': 0, 'duree': 60}, {'onset': 480, 'duree': 60}]


def test_caractere_inconnu_ignore():
    c = _ctx()
    assert _sched(c, 'E§', 20) == _sched(c, 'E', 20)
    assert _sched(c, '§', 20) == []


def test_config_actif_hz_wpm():
    c = _ctx({'soundcard_cw_enabled': '1', 'soundcard_cw_hz': 600, 'soundcard_cw_wpm': 28})
    assert c.eval('cwSoundcardActif()') is True
    assert c.eval('cwSoundcardHz()') == 600
    assert c.eval('cwSoundcardWpm()') == 28


def test_config_defauts_et_desactive():
    c = _ctx({})
    assert c.eval('cwSoundcardActif()') is False
    assert c.eval('cwSoundcardHz()') == 700          # défaut
    assert c.eval('cwSoundcardWpm()') == 20          # défaut
    # hors plage -> repli sur le défaut
    c2 = _ctx({'soundcard_cw_enabled': '1', 'soundcard_cw_hz': 99, 'soundcard_cw_wpm': 999})
    assert c2.eval('cwSoundcardHz()') == 700 and c2.eval('cwSoundcardWpm()') == 20


def test_play_sans_audiocontext_ne_leve_pas():
    c = _ctx()
    # window sans AudioContext -> promesse résolue, aucun oscillateur
    assert c.eval("(function(){ var p = cwSoundcardPlay('CQ', 20, 700); return p && typeof p.then==='function'; })()") is True
