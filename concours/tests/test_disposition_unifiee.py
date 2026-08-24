# -*- coding: utf-8 -*-
"""Incrément 4 — une DISPOSITION capture/restaure aussi l'affichage in-page.

Avant : une disposition nommée ne mémorisait QUE les fenêtres détachées. Désormais
elle capture AUSSI les préférences AFFICHAGE (bascules des panneaux de page) ->
un vrai « espace de travail » complet. Rétro-compat : une disposition sans champ
`display` ne touche pas l'affichage courant.

Test comportemental sur les vraies fonctions saveLayout/loadLayout extraites,
avec les dépendances stubées (aucune fenêtre popout réelle).
"""
import json
import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS = open(os.path.join(BASE, 'logx_statusbar.js'), encoding='utf-8').read()


def _bloc_layout():
    i = JS.index('function saveLayout')
    j = JS.index('function deleteLayout', i)
    return JS[i:j]


def _ctx():
    from py_mini_racer import py_mini_racer as m
    c = m.MiniRacer()
    c.eval('var _store = {}; var localStorage = {getItem:function(k){return _store[k]||null;},'
           'setItem:function(k,v){_store[k]=v;}};')
    c.eval('var _layouts = {}; function getLayouts(){ return _layouts; } function setLayouts(o){ _layouts = o; }')
    c.eval('var _openWindows = {};')                       # aucune fenêtre ouverte
    c.eval('function renderLayoutDD(){}; function closePanel(){}; function openPanel(){};'
           'function isPanelOpen(){ return false; } function panelId(k){ return k; } function panelBand(){ return null; }')
    c.eval('function getStatusbarPrefs(){ return {weatherWidget:true, opStatsBar:false, bandmapPanel:false}; }')
    c.eval('var _applied = 0; function applyStatusbarPrefs(){ _applied++; }')
    c.eval(_bloc_layout())
    return c


def test_savelayout_capture_l_affichage():
    c = _ctx()
    c.eval("saveLayout('Espace Concours')")
    lay = json.loads(c.eval('JSON.stringify(getLayouts())'))
    assert 'Espace Concours' in lay
    assert lay['Espace Concours']['display']['weatherWidget'] is True
    assert lay['Espace Concours']['display']['bandmapPanel'] is False


def test_loadlayout_restaure_l_affichage():
    c = _ctx()
    c.eval("saveLayout('WS')")
    c.eval("_applied = 0")
    c.eval("loadLayout('WS')")
    prefs = json.loads(c.eval("_store['rc_statusbar_prefs']"))
    assert prefs['weatherWidget'] is True and prefs['opStatsBar'] is False
    assert c.eval('_applied') >= 1


def test_retrocompat_disposition_sans_display():
    c = _ctx()
    # ancienne disposition : seulement des fenêtres, pas de champ display
    c.eval("setLayouts({'Vieux': {panels: {}}})")
    c.eval("_applied = 0")
    c.eval("loadLayout('Vieux')")
    # aucun rc_statusbar_prefs écrit, applyStatusbarPrefs pas appelé pour l'affichage
    assert c.eval("_store['rc_statusbar_prefs'] || ''") == ''
