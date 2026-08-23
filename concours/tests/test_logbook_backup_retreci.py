# -*- coding: utf-8 -*-
"""backupLog() ne doit pas écraser le filet rc_log_backup avec un carnet
BRUTALEMENT RÉTRÉCI (axe « carnet perdu »).

Le seul garde-fou était `if(!qsoLog.length) return;` : il protège contre un log
VIDE mais PAS contre un log rétréci. Or fetchLog() peut remplacer qsoLog par une
liste complète PLUS COURTE (redémarrage serveur / boot-token périmé / chargement
disque incomplet / perte massive). Au tick backupLog suivant, rc_log_backup était
alors écrasé par ce carnet amputé — le filet détruit précisément quand il sert.
Aucun équivalent client du garde-fou serveur _SEUIL_PERTE_MASSIVE=25.

Correctif : si le carnet a rétréci de >= 25 QSO par rapport au backup existant,
backupLog() PRÉSERVE l'ancien backup (et journalise) au lieu de l'écraser.

Le VRAI code de backupLog() est extrait du fichier source par comptage
d'accolades et exécuté dans V8 (py_mini_racer), pas réécrit — même technique que
tests/test_assistant_banner_popup_js.py.
"""
import os
import re

import pytest

py_mini_racer = pytest.importorskip(
    'py_mini_racer', reason='py_mini_racer absent — test JS réel ignoré')

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS_PATH = os.path.join(BASE, 'logx_logbook.js')


def _extract_function(src, name):
    m = re.search(r'^(?:async\s+)?function %s\(' % re.escape(name), src, re.M)
    assert m, 'fonction %s introuvable' % name
    depth = 0
    i = src.index('{', m.start())
    while True:
        c = src[i]
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                return src[m.start():i + 1]
        i += 1


with open(JS_PATH, encoding='utf-8') as _f:
    _BACKUPLOG_SRC = _extract_function(_f.read(), 'backupLog')

_PREAMBLE = r"""
var _ls = {};
var localStorage = {
  getItem: function(k){ return (k in _ls) ? _ls[k] : null; },
  setItem: function(k,v){ _ls[k] = String(v); }
};
var document = { getElementById: function(){ return null; } };
var console = { warn: function(){}, log: function(){} };
var qsoLog = [];
function _seedBackup(n){ _ls['rc_log_backup'] = JSON.stringify(_mk(n)); }
function _mk(n){ var a=[]; for(var i=0;i<n;i++) a.push({id:i}); return a; }
function _backupLen(){ return _ls['rc_log_backup'] ? JSON.parse(_ls['rc_log_backup']).length : -1; }
"""


def _ctx():
    c = py_mini_racer.MiniRacer()
    c.eval(_PREAMBLE + '\n' + _BACKUPLOG_SRC)
    return c


def _backup_len_apres(backup_n, qsolog_n):
    c = _ctx()
    if backup_n is not None:
        c.eval('_seedBackup(%d);' % backup_n)
    c.eval('qsoLog = _mk(%d);' % qsolog_n)
    c.eval('backupLog();')
    return c.eval('_backupLen();')


def test_carnet_retreci_preserve_le_filet():
    # backup de 100, resync serveur partiel -> qsoLog=30 (chute de 70 >= 25)
    assert _backup_len_apres(100, 30) == 100, \
        "un carnet rétréci ne doit PAS écraser le filet rc_log_backup"


def test_petite_variation_met_a_jour_le_filet():
    # chute de 10 (< 25) : mise à jour normale
    assert _backup_len_apres(100, 90) == 90


def test_premier_backup_toujours_ecrit():
    # pas de backup préalable -> toujours écrit
    assert _backup_len_apres(None, 50) == 50


def test_log_vide_ne_touche_a_rien():
    # qsoLog vide -> return, backup inchangé
    assert _backup_len_apres(100, 0) == 100


def test_croissance_met_a_jour():
    assert _backup_len_apres(100, 140) == 140
