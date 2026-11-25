# -*- coding: utf-8 -*-
"""Échange reçu vide en concours : confirmation avant d'enregistrer
(audit 25/11/2026 : 6 QSO du CQ WW 2026 sans zone reçue).

submitQSO() est EXTRAITE de logx_logbook.js et exécutée jusqu'au point de
décision ; tout ce qui suit est arrêté par un marqueur (nextSerial)."""
import os
import re

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
py_mini_racer = pytest.importorskip('py_mini_racer')


def _fn(src, nom):
    m = re.search(r'\n\s*async function ' + nom + r'\s*\(', src)
    i = src.index('async', m.start())
    j, prof = src.index('{', i), 0
    for k in range(j, len(src)):
        prof += {'{': 1, '}': -1}.get(src[k], 0)
        if prof == 0:
            return src[i:k + 1]


_SRC = open(os.path.join(CONCOURS, 'logx_logbook.js'), encoding='utf-8').read()


def _soumettre(num_rcvd='', concours=True, usage='contest', expedition=False,
               no_exchange=False, reponse=False):
    c = py_mini_racer.MiniRacer()
    c.eval("""
      var __v = {inputCall:'DL1XYZ', inputRSTsent:'59', inputRSTrcvd:'59', inputNumRcvd:%r,
                 inputLocator:'JN58', inputFreq:'14200', inputNumSent:'14'};
      var __focus = '', __banniere = [], __suite = false;
      var document = {getElementById: function(id){ return {value: __v[id] || '',
          focus: function(){ __focus = id; }}; }};
      var currentExchange = {label_r:'ZONE RCU', no_exchange:%s};
      var usageMode = %r, expeditionMode = %s, currentBand = '14', currentMode = 'SSB';
      var rigState = {enabled:false};
      function _rstParDefaut(){ return '59'; } function notify(){} function validateLocator(){ return true; }
      function contestRequiresLocator(){ return false; } function isDup(){ return false; }
      function contestActif(){ return %s; }
      function trT(s){ return s; } function trF(s, p){ return s.replace(/\\{(\\w+)\\}/g, function(_, k){ return p[k]; }); }
      function _confirmDupBanner(m, o, n){ __banniere.push(m + '|' + o + '|' + n); return Promise.resolve(%s); }
      function nextSerial(){ __suite = true; throw new Error('suite'); }
      function calcDist(){ __suite = true; throw new Error('suite'); }
      function calcPoints(){ __suite = true; throw new Error('suite'); }
    """ % (num_rcvd, 'true' if no_exchange else 'false', usage, 'true' if expedition else 'false',
           'true' if concours else 'false', 'true' if reponse else 'false'))
    c.eval(_fn(_SRC, 'submitQSO'))
    c.eval("submitQSO().catch(function(){})")
    for _ in range(10):
        c.eval('0')
    return c


def test_echange_vide_en_concours_demande_confirmation_et_rend_la_main():
    c = _soumettre()
    ban = c.eval("__banniere.join('/')")
    assert 'ZONE RCU vide pour DL1XYZ' in ban and 'Compléter' in ban
    assert c.eval("__suite") is False and c.eval("__focus") == 'inputNumRcvd'


def test_enregistrer_quand_meme_continue():
    c = _soumettre(reponse=True)
    assert c.eval("__banniere.length") == 1 and c.eval("__suite") is True


@pytest.mark.parametrize('kw', [dict(num_rcvd='14'), dict(concours=False), dict(usage='simple'),
                                dict(expedition=True), dict(no_exchange=True)])
def test_pas_de_question_hors_cas(kw):
    c = _soumettre(**kw)
    assert c.eval("__banniere.length") == 0 and c.eval("__suite") is True
