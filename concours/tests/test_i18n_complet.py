# -*- coding: utf-8 -*-
"""Complétude i18n : aucune langue ne doit manquer une clé traduite ailleurs
(sinon repli SILENCIEUX sur le français -> texte non traduit à l'écran).

Vérifie le dictionnaire EFFECTIF tel que le runtime le construit : T[lang] est
fusionné avec T_I18N_AUDIT_FIX[lang] (Object.assign, voir logx_i18n.js). On
teste donc l'union T ∪ T_I18N_AUDIT_FIX, plus T_AGENT. Garde-fou permanent :
toute future clé ajoutée dans une seule langue fait ROUGIR ce test.
"""
import json
import os
import re

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
I18N = os.path.join(CONCOURS, 'logx_i18n.js')
py_mini_racer = pytest.importorskip('py_mini_racer')


def _extraire(src, nom):
    m = re.search(r'const %s\s*=\s*\{' % re.escape(nom), src)
    assert m, nom
    i = src.index('{', m.start())
    d = 0
    j = i
    while j < len(src):
        if src[j] == '{':
            d += 1
        elif src[j] == '}':
            d -= 1
            if d == 0:
                return src[i:j + 1]
        j += 1
    raise AssertionError('accolade non fermée: ' + nom)


def _ctx():
    src = open(I18N, encoding='utf-8').read()
    ctx = py_mini_racer.MiniRacer()
    for nom in ('T', 'T_AGENT', 'T_I18N_AUDIT_FIX'):
        ctx.eval('var %s = %s;' % (nom, _extraire(src, nom)))
    return ctx


def _keys(ctx, expr):
    return set(json.loads(ctx.eval('JSON.stringify(%s)' % expr)))


def _manquants_effectif_T(ctx):
    """T[lang] ∪ T_I18N_AUDIT_FIX[lang] pour chaque langue, puis clés manquantes
    vs l'union globale."""
    ctx.eval("""
      var _eff = {};
      Object.keys(T).forEach(function(l){
        _eff[l] = {};
        Object.keys(T[l]).forEach(function(k){ _eff[l][k]=1; });
        if(T_I18N_AUDIT_FIX[l]) Object.keys(T_I18N_AUDIT_FIX[l]).forEach(function(k){ _eff[l][k]=1; });
      });
    """)
    langs = json.loads(ctx.eval('JSON.stringify(Object.keys(_eff))'))
    union = set()
    par_lang = {}
    for l in langs:
        ks = _keys(ctx, "_eff['%s']" % l)
        par_lang[l] = ks
        union |= ks
    return {l: sorted(union - ks) for l, ks in par_lang.items()}


def test_T_effectif_complet_dans_toutes_les_langues():
    ctx = _ctx()
    manque = {l: ks for l, ks in _manquants_effectif_T(ctx).items() if ks}
    assert not manque, "clés traduites ailleurs mais manquantes :\n" + json.dumps(
        {l: v[:20] for l, v in manque.items()}, ensure_ascii=False, indent=1)


def test_T_AGENT_complet():
    ctx = _ctx()
    langs = json.loads(ctx.eval('JSON.stringify(Object.keys(T_AGENT))'))
    union = set()
    par = {}
    for l in langs:
        ks = _keys(ctx, "T_AGENT['%s']" % l)
        par[l] = ks
        union |= ks
    manque = {l: sorted(union - ks) for l, ks in par.items() if union - ks}
    assert not manque, "T_AGENT incomplet : " + json.dumps(manque, ensure_ascii=False)
