# -*- coding: utf-8 -*-
"""Incrément 2 — presets d'affichage PAR ACTIVITÉ (menu ⚙ AFFICHAGE).

Une activité (localStorage.logx_activity) propose un jeu d'affichage sensé,
appliqué par un BOUTON dans le menu AFFICHAGE (jamais forcé — clic délibéré).
applyActivityDisplayPreset(id) fixe les préférences des bascules concernées puis
ré-applique. Le CONTENU des presets est une donnée à ajuster ; ces tests
vérifient le MÉCANISME (bon routage vers setStatusbarPref, activité sans preset
= aucun effet, bouton câblé), pas les valeurs de contenu.
"""
import json
import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS = open(os.path.join(BASE, 'logx_statusbar.js'), encoding='utf-8').read()


def _bloc_presets():
    # Tranche depuis les données presets jusqu'au marqueur suivant (renderDisplayDD).
    i = JS.index('const ACTIVITY_LABELS')
    j = JS.index('function renderDisplayDD', i)
    return JS[i:j]


def _ctx():
    from py_mini_racer import py_mini_racer as m
    c = m.MiniRacer()
    c.eval('var _set = {}; function setStatusbarPref(id, v){ _set[id] = v; }')
    c.eval('var _applied = 0; function applyStatusbarPrefs(){ _applied++; }')
    c.eval('var localStorage = { _v:{}, getItem:function(k){ return this._v[k]||null; }, setItem:function(k,v){ this._v[k]=v; } };')
    c.eval(_bloc_presets())
    return c


def test_preset_concours_route_les_bonnes_bascules():
    c = _ctx()
    c.eval("applyActivityDisplayPreset('concours')")
    got = json.loads(c.eval('JSON.stringify(_set)'))
    assert got.get('opStatsBar') is True
    assert got.get('weatherWidget') is False
    assert got.get('rcsbRateItem') is True
    assert c.eval('_applied') >= 1, "applyStatusbarPrefs doit être rappelé"


def test_preset_terrain_rallume_la_meteo():
    c = _ctx()
    c.eval("applyActivityDisplayPreset('iota_pota')")
    got = json.loads(c.eval('JSON.stringify(_set)'))
    assert got.get('weatherWidget') is True, "activation terrain -> météo (sécurité mât)"


def test_activite_sans_preset_ne_fait_rien():
    c = _ctx()
    c.eval("applyActivityDisplayPreset('normal')")   # normal : pas de preset
    assert c.eval('JSON.stringify(_set)') == '{}'
    assert c.eval('_applied') == 0


def test_bouton_preset_cable_dans_le_menu():
    # le bouton n'apparaît que si l'activité courante a un preset, et le clic
    # est routé vers applyActivityDisplayPreset.
    assert 'class="rcsb-preset-btn" data-preset="' in JS
    assert "e.target.closest('[data-preset]')" in JS
    assert 'applyActivityDisplayPreset(presetBtn.getAttribute' in JS


def test_menu_affichage_est_expert_only():
    # Directive F4GLD : personnalisation = expert. Le débutant garde sa base
    # minimale ; le menu ⚙ AFFICHAGE n'apparaît qu'en mode expert (comme DISPOSITION).
    assert 'class="rcsb-item expert-only" id="rcsbDisplayItem"' in JS


def test_auto_application_une_fois_par_changement_activite():
    c = _ctx()
    c.eval("localStorage.setItem('logx_activity','concours')")
    c.eval("maybeApplyActivityPresetOnChange()")
    assert json.loads(c.eval('JSON.stringify(_set)')).get('opStatsBar') is True, "1re fois -> preset appliqué"
    # même activité au rechargement -> NE PAS ré-appliquer (tweaks manuels préservés)
    c.eval("_set = {}")
    c.eval("maybeApplyActivityPresetOnChange()")
    assert c.eval('JSON.stringify(_set)') == '{}', "même activité -> pas de ré-application"
    # changement d'activité -> ré-application
    c.eval("localStorage.setItem('logx_activity','iota_pota')")
    c.eval("maybeApplyActivityPresetOnChange()")
    assert json.loads(c.eval('JSON.stringify(_set)')).get('weatherWidget') is True, "nouvelle activité -> preset appliqué"
