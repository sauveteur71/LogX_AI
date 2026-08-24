# -*- coding: utf-8 -*-
"""Incrément 3 — profils d'affichage nommés + export/import JSON.

Un profil = instantané des préférences AFFICHAGE (rc_statusbar_prefs) sous un
nom. Export/import JSON = partage entre postes/clubs SANS serveur. Ne touche que
l'affichage. Tests comportementaux sur les fonctions PURES (save/load/export/
import, round-trip) + structurels (UI câblée, noms échappés = anti-injection).
"""
import json
import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS = open(os.path.join(BASE, 'logx_statusbar.js'), encoding='utf-8').read()


def _bloc():
    i = JS.index('function getDisplayProfiles')
    j = JS.index('function renderDisplayDD', i)
    return JS[i:j]


def _ctx():
    from py_mini_racer import py_mini_racer as m
    c = m.MiniRacer()
    c.eval('var _store = {}; var localStorage = {getItem:function(k){return _store[k]||null;},'
           'setItem:function(k,v){_store[k]=v;}};')
    c.eval('function getStatusbarPrefs(){ return {weatherWidget:true, opStatsBar:false}; }')
    c.eval('var _applied = 0; function applyStatusbarPrefs(){ _applied++; }')
    c.eval('function renderDisplayDD(){}')          # référencé par l'import (stub)
    c.eval('var document = {createElement:function(){return {click:function(){},style:{}};},'
           'body:{appendChild:function(){},removeChild:function(){}}};')  # stubs DOM inertes
    c.eval(_bloc())
    return c


def test_save_puis_recuperation():
    c = _ctx()
    assert c.eval("saveDisplayProfile('Concours F6KJS')") is True
    profs = json.loads(c.eval('JSON.stringify(getDisplayProfiles())'))
    assert 'Concours F6KJS' in profs
    assert profs['Concours F6KJS']['prefs']['weatherWidget'] is True


def test_load_applique_les_prefs():
    c = _ctx()
    c.eval("saveDisplayProfile('P1')")
    c.eval("_applied = 0")
    assert c.eval("loadDisplayProfile('P1')") is True
    prefs = json.loads(c.eval("_store['rc_statusbar_prefs']"))
    assert prefs['weatherWidget'] is True
    assert c.eval('_applied') == 1
    assert c.eval("loadDisplayProfile('inexistant')") is False


def test_export_import_round_trip():
    c = _ctx()
    c.eval("saveDisplayProfile('Club 144')")
    export = c.eval("exportDisplayProfiles()")
    assert 'logx_display_profiles' in export and 'Club 144' in export
    c.eval("setDisplayProfiles({})")                          # on vide
    assert c.eval("Object.keys(getDisplayProfiles()).length") == 0
    n = c.eval("importDisplayProfiles(" + json.dumps(export) + ")")
    assert n == 1
    assert c.eval("Object.keys(getDisplayProfiles()).indexOf('Club 144')") >= 0


def test_import_rejette_le_garbage():
    c = _ctx()
    assert c.eval("importDisplayProfiles('pas du json')") == 0
    assert c.eval("importDisplayProfiles('{\"x\":1}')") == 0   # pas de .prefs -> ignoré


def test_ui_et_echappement_des_noms():
    # boutons câblés
    for h in ('data-prof-load', 'data-prof-del', 'data-prof-save', 'data-prof-export', 'data-prof-import'):
        assert h in JS, h
    assert 'loadDisplayProfile(pLoad.getAttribute' in JS
    assert '_downloadDisplayProfiles()' in JS and '_importDisplayProfilesViaFile()' in JS
    # les noms de profils (saisie utilisateur) sont échappés avant injection
    assert "data-prof-load=\"'\n        + esc(nm) +" in JS or 'esc(nm)' in JS
