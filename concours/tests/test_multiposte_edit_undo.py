# -*- coding: utf-8 -*-
"""Audit : en multi-poste, deleteQSOSilent diffusait 'delete' (bcBroadcast) mais
saveEdit (édition) et undoLastQSO (annulation) ne diffusaient RIEN -> les autres
postes ne voyaient ni l'édition ni l'annulation. saveEdit diffuse désormais
'update', undoLastQSO diffuse 'delete'. Exécution du VRAI code dans V8."""
import os
import re

import pytest

py_mini_racer = pytest.importorskip('py_mini_racer')

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS = os.path.join(BASE, 'logx_edit_qso.js')


def _fn(src, nom):
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


_STUBS = """
var _bc = [];
function bcBroadcast(type, data){ _bc.push({type: type, id: data && data.id}); }
var _f = {editId:'1', editCall:'F4NEW', editDate:'20260101', editTime:'10:00',
          editBand:'20', editMode:'SSB', editLocator:'', editRSTsent:'59',
          editNumSent:'', editRSTrcvd:'59', editNumRcvd:'', editFreq:''};
var document = { getElementById: function(id){ return {value: (_f[id] || '')}; } };
var qsoLog = [{id:1, call:'OLD', band:'20', mode:'SSB', time:'09:00'}];
var currentExchange = {pad_r:false};
var editExtraFields = [];
function calcDist(){ return 0; }
function calcPoints(){ return 0; }
function fetch(){ return Promise.resolve({ok:true}); }
function notify(){}
function closeEdit(){}
function renderLog(){}
function updateStats(){}
function nowDateUTC(){ return '20260101'; }
function nowUTC(){ return '10:00'; }
function trF(s){ return s; }
function _confirmDupBanner(){ return Promise.resolve(true); }
"""


def _ctx():
    src = open(JS, encoding='utf-8').read()
    c = py_mini_racer.MiniRacer()
    c.eval(_STUBS)
    c.eval(_fn(src, 'saveEdit'))
    c.eval(_fn(src, 'undoLastQSO'))
    return c


def _drain(c):
    for _ in range(8):
        c.eval("0")   # draine la file de microtâches (promesses) entre les eval


def test_saveEdit_diffuse_update():
    c = _ctx()
    c.eval("_bc = []; saveEdit();")
    _drain(c)
    types = c.eval("JSON.stringify(_bc.map(function(x){return x.type;}))")
    assert 'update' in types, "saveEdit doit diffuser 'update' (multi-poste) : %s" % types


def test_undoLastQSO_diffuse_delete():
    c = _ctx()
    c.eval("_bc = []; undoLastQSO();")
    _drain(c)
    got = c.eval("JSON.stringify(_bc)")
    assert '"type":"delete"' in got and '"id":1' in got, \
        "undoLastQSO doit diffuser 'delete' avec l'id : %s" % got
