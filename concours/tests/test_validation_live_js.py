# -*- coding: utf-8 -*-
"""Badge de validation LIVE (logx_validation_live.js) — testé en V8.

La logique de validation est côté serveur (logx_validator, testée ailleurs) ;
ici on vérifie le BADGE discret : caché si log propre, jaune sur attentions,
rouge sur erreur, texte du compte. Sans fetch dans le harnais -> pas de
démarrage auto (le module ne le lance qu'en vrai navigateur).
"""
import os

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS = os.path.join(CONCOURS, 'logx_validation_live.js')
py_mini_racer = pytest.importorskip('py_mini_racer')


def _ctx():
    ctx = py_mini_racer.MiniRacer()
    ctx.eval("""
      var window = {};
      window.__filPush = [];
      window.LogxFilIA = { pousser: function(s, e){ window.__filPush.push({source: s, n: (e||[]).length}); } };
      var __b = { hidden: true, textContent: '', _s: {},
        classList: { toggle:function(c,v){ __b._s[c]=v; }, contains:function(c){ return !!__b._s[c]; } },
        setAttribute:function(){} };
      var document = { getElementById:function(id){ return id==='validationBadge' ? __b : null; }, readyState:'complete' };
    """)
    with open(JS, encoding='utf-8') as f:
        ctx.eval(f.read())
    return ctx


def test_badge_cache_si_log_propre():
    ctx = _ctx()
    ctx.eval("window.LogxValidationLive._rendre({erreur:0, attention:0})")
    assert ctx.eval("__b.hidden") is True


def test_badge_jaune_sur_attentions():
    ctx = _ctx()
    ctx.eval("window.LogxValidationLive._rendre({erreur:0, attention:3})")
    assert ctx.eval("__b.hidden") is False
    assert ctx.eval("__b.classList.contains('vl-erreur')") is False   # pas d'erreur -> jaune
    assert '3' in ctx.eval("__b.textContent") and 'vérifier' in ctx.eval("__b.textContent")


def test_badge_rouge_sur_erreur():
    ctx = _ctx()
    ctx.eval("window.LogxValidationLive._rendre({erreur:1, attention:2})")
    assert ctx.eval("__b.hidden") is False
    assert ctx.eval("__b.classList.contains('vl-erreur')") is True     # au moins 1 erreur -> rouge
    assert '3' in ctx.eval("__b.textContent")                          # 1 + 2 à vérifier


def test_alimente_le_fil_ia():
    ctx = _ctx()
    ctx.eval("window.LogxValidationLive._rendre({erreur:1, attention:2})")
    assert ctx.eval("window.__filPush[window.__filPush.length-1].source") == 'validation'
    assert ctx.eval("window.__filPush[window.__filPush.length-1].n") == 1   # une entrée attention
    ctx.eval("window.LogxValidationLive._rendre({erreur:0, attention:0})")
    assert ctx.eval("window.__filPush[window.__filPush.length-1].n") == 0   # log propre -> retiré


def test_cablage_logbook():
    with open(os.path.join(CONCOURS, 'logx_logbook.html'), encoding='utf-8') as f:
        h = f.read()
    assert 'src="logx_validation_live.js"' in h        # module chargé (alimente le fil IA)
    # Le badge d'en-tête a été RETIRÉ (le fil IA « Ce que l'IA remarque » le
    # résume, avec la même action ouvrir VÉRIFIER au clic).
    assert 'id="validationBadge"' not in h
