# -*- coding: utf-8 -*-
"""Garde-fou de thème (logx_theme_guard.js) : détecte logx_theme.css NON appliqué
(bloqué/tronqué par un antivirus/proxy — cas Avast) et affiche un bandeau
explicite, au lieu de laisser l'opérateur découvrir des symptômes épars (police
serif, texte invisible, barre de cycle FT8 sans couleur…).

On exécute le VRAI script dans un moteur JS réel avec un DOM/getComputedStyle
stubés — le token cœur --accent est contrôlé pour simuler les deux cas."""
import json
import os

import pytest

py_mini_racer = pytest.importorskip(
    'py_mini_racer', reason='py_mini_racer absent — test JS réel ignoré')

GUARD = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     'logx_theme_guard.js')


def _ctx(accent_value):
    ctx = py_mini_racer.MiniRacer()
    ctx.eval('''
    var __banner = null;
    var __accent = %s;
    var getComputedStyle = function(){
      return {getPropertyValue: function(){ return __accent; }};
    };
    var document = {
      documentElement: {},
      body: {appendChild: function(el){ __banner = el; }},
      getElementById: function(id){
        return (__banner && __banner.id === id) ? __banner : null;
      },
      createElement: function(){
        return {style:{cssText:''}, setAttribute:function(){}, id:'', textContent:''};
      }
    };
    // Pas de addEventListener défini -> pas d'auto-armement : on appelle verifier() nous-mêmes.
    ''' % json.dumps(accent_value))
    with open(GUARD, encoding='utf-8') as f:
        ctx.eval(f.read())
    return ctx


def test_theme_applique_aucun_bandeau():
    ctx = _ctx('#E8964A')                       # token présent -> thème OK
    assert ctx.eval('LogxThemeGuard.themeApplique()') is True
    ctx.eval('LogxThemeGuard.verifier();')
    assert ctx.eval('__banner === null') is True, 'aucun bandeau si le thème est appliqué'


def test_theme_absent_affiche_le_bandeau():
    ctx = _ctx('')                              # token vide -> thème NON appliqué
    assert ctx.eval('LogxThemeGuard.themeApplique()') is False
    ctx.eval('LogxThemeGuard.verifier();')
    assert ctx.eval('__banner !== null') is True, 'un bandeau doit apparaître'
    assert ctx.eval("__banner.id") == 'themeGuardBanner'
    txt = ctx.eval('__banner.textContent')
    assert 'antivirus' in txt.lower() and 'logx_theme.css' in txt, txt


def test_bandeau_non_duplique():
    ctx = _ctx('')
    ctx.eval('LogxThemeGuard.verifier(); LogxThemeGuard.verifier();')
    # getElementById renvoie le bandeau existant -> pas de second
    assert ctx.eval("__banner.id") == 'themeGuardBanner'


def test_sans_getcomputedstyle_ne_signale_rien():
    """Banc/headless sans getComputedStyle : ne pas crier au loup (themeApplique
    doit renvoyer true par défaut, pas afficher un bandeau à tort)."""
    ctx = py_mini_racer.MiniRacer()
    ctx.eval('var document = {documentElement:{}};')   # pas de getComputedStyle
    with open(GUARD, encoding='utf-8') as f:
        ctx.eval(f.read())
    assert ctx.eval('LogxThemeGuard.themeApplique()') is True
