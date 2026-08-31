# -*- coding: utf-8 -*-
"""Thème haut-contraste (accessibilité, décision F4GLD « auto + manuel »).
Résolution : réglage EXPLICITE (localStorage rc_contrast) prioritaire, sinon
préférence SYSTÈME (prefers-contrast: more). La classe body.high-contrast pilote
les tokens haut-contraste de logx_theme.css (superposés au jour comme à la nuit).
Le manuel OFF surpasse donc l'auto ON."""
import os
import re

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SB = os.path.join(CONCOURS, 'logx_statusbar.js')
THEME = os.path.join(CONCOURS, 'logx_theme.css')
CONFIG = os.path.join(CONCOURS, 'logx_configuration.html')


def _fn(src, nom):
    m = re.search(r'\n\s*function ' + re.escape(nom) + r'\s*\(', src)
    assert m, 'fonction %s introuvable' % nom
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
    raise AssertionError('accolade fermante introuvable')


def _ctx(rc_contrast, os_more):
    racer = pytest.importorskip('py_mini_racer')
    c = racer.MiniRacer()
    src = open(SB, encoding='utf-8').read()
    c.eval("""
      var _store = %s;
      var localStorage = { getItem:function(k){ return (k in _store)?_store[k]:null; } };
      var _cls = { _s:{}, toggle:function(n,on){ this._s[n]=!!on; },
                   contains:function(n){ return !!this._s[n]; } };
      var _btn = { attrs:{}, setAttribute:function(k,v){ this.attrs[k]=v; } };
      function _stubEl(){ return { style:{}, innerHTML:'', appendChild:function(){},
        querySelector:function(){ return {addEventListener:function(){}}; },
        addEventListener:function(){} }; }
      var document = { body:{classList:_cls, appendChild:function(){}},
        createElement:function(){ return _stubEl(); },
        getElementById:function(id){ return id==='contrastToggle'?_btn:null; } };
      var window = { matchMedia:function(q){ return { matches:%s }; } };
      var _contrastHintEl = null;
    """ % ('{"rc_contrast":%r}' % rc_contrast if rc_contrast is not None else '{}',
           'true' if os_more else 'false'))
    c.eval(_fn(src, 'contrasteEleve'))
    c.eval(_fn(src, '_contrasteAuto'))
    c.eval(_fn(src, '_doitAfficherRepere'))
    c.eval(_fn(src, 'majContrastHint'))
    c.eval(_fn(src, 'applyContraste'))
    return c


def test_reglage_high_force_le_contraste_meme_sans_os():
    assert _ctx('high', False).eval("contrasteEleve()") is True


def test_reglage_normal_desactive_meme_si_os_le_demande():
    # Le manuel OFF surpasse l'auto ON.
    assert _ctx('normal', True).eval("contrasteEleve()") is False


def test_absent_suit_le_systeme_actif():
    assert _ctx(None, True).eval("contrasteEleve()") is True


def test_absent_suit_le_systeme_inactif():
    assert _ctx(None, False).eval("contrasteEleve()") is False


def test_applyContraste_pose_la_classe_body():
    c = _ctx('high', False)
    c.eval("applyContraste()")
    assert c.eval("_cls.contains('high-contrast')") is True
    c.eval("_store.rc_contrast='normal'; applyContraste()")
    assert c.eval("_cls.contains('high-contrast')") is False


def test_theme_css_definit_les_tokens_haut_contraste():
    css = open(THEME, encoding='utf-8').read()
    assert 'body.high-contrast {' in css or 'body.high-contrast{' in css
    assert 'body.high-contrast.day-mode' in css
    # noyau surchargé en HC (fonds/texte extrêmes)
    m = re.search(r'body\.high-contrast\s*\{([^}]*)\}', css)
    assert m and '--bg:#000000' in m.group(1).replace(' ', '')
    assert '--text:#FFFFFF' in m.group(1).replace(' ', '')


def test_config_a_le_bouton_contraste_relie_a_l_api():
    html = open(CONFIG, encoding='utf-8').read()
    assert 'id="contrastToggle"' in html
    assert 'LogxContraste.basculer' in html


# ── Repère découvrable : signaler quand le HC est AUTO (système) ──────────────

def _ctx_repere(rc_contrast, os_more, dismissed=False):
    """Contexte évaluant _contrasteAuto + _doitAfficherRepere (décision d'afficher
    le repère). Store avec rc_contrast et l'éventuel drapeau d'écart."""
    racer = pytest.importorskip('py_mini_racer')
    c = racer.MiniRacer()
    src = open(SB, encoding='utf-8').read()
    store = {}
    if rc_contrast is not None:
        store['rc_contrast'] = rc_contrast
    if dismissed:
        store['rc_contrast_hint_off'] = '1'
    import json
    c.eval("""
      var _store = %s;
      var localStorage = { getItem:function(k){ return (k in _store)?_store[k]:null; } };
      var window = { matchMedia:function(q){ return { matches:%s }; } };
    """ % (json.dumps(store), 'true' if os_more else 'false'))
    c.eval(_fn(src, '_contrasteAuto'))
    c.eval(_fn(src, '_doitAfficherRepere'))
    return c


def test_repere_affiche_si_contraste_auto_systeme():
    # rc_contrast absent + système le demande + pas écarté -> on affiche le repère.
    c = _ctx_repere(None, True)
    assert c.eval("_contrasteAuto()") is True
    assert c.eval("_doitAfficherRepere()") is True


def test_repere_absent_si_choix_manuel_high():
    # Contraste choisi MANUELLEMENT -> pas une surprise système, pas de repère.
    c = _ctx_repere('high', True)
    assert c.eval("_contrasteAuto()") is False
    assert c.eval("_doitAfficherRepere()") is False


def test_repere_absent_si_systeme_ne_demande_pas():
    assert _ctx_repere(None, False).eval("_doitAfficherRepere()") is False


def test_repere_absent_si_deja_ecarte():
    # Auto-système mais l'utilisateur a fait « × » -> on n'en reparle plus.
    c = _ctx_repere(None, True, dismissed=True)
    assert c.eval("_contrasteAuto()") is True         # le HC est bien auto...
    assert c.eval("_doitAfficherRepere()") is False   # ...mais le repère est écarté
