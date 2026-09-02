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
        classList: { toggle:function(c,v){ __b._s[c]=v; }, contains:function(c){ return !!__b._s[c]; },
          add:function(c){ __b._s[c]=true; }, remove:function(c){ __b._s[c]=false; } },
        setAttribute:function(){} };
      var document = { getElementById:function(id){ return id==='validationBadge' ? __b : null; }, readyState:'complete' };
    """)
    with open(JS, encoding='utf-8') as f:
        ctx.eval(f.read())
    return ctx


# _rendre reçoit la RÉPONSE COMPLÈTE de /log/validate (compteurs ventilés
# saisi/importé). Aides pour construire des réponses de test.
def _resp(es=0, as_=0, ns=0, ni=0):
    return ("{counts_saisi:{erreur:%d,attention:%d,info:0}, "
            "qso_a_verifier_saisi:%d, qso_a_verifier_importe:%d}" % (es, as_, ns, ni))


def test_badge_cache_si_log_propre():
    ctx = _ctx()
    ctx.eval("window.LogxValidationLive._rendre(%s)" % _resp(0, 0, 0, 0))
    assert ctx.eval("__b.hidden") is True


def test_badge_jaune_sur_attentions_saisies():
    ctx = _ctx()
    ctx.eval("window.LogxValidationLive._rendre(%s)" % _resp(es=0, as_=3, ns=3))
    assert ctx.eval("__b.hidden") is False
    assert ctx.eval("__b.classList.contains('vl-erreur')") is False   # pas d'erreur -> jaune
    assert '3' in ctx.eval("__b.textContent") and 'vérifier' in ctx.eval("__b.textContent")


def test_badge_rouge_sur_erreur_saisie():
    ctx = _ctx()
    ctx.eval("window.LogxValidationLive._rendre(%s)" % _resp(es=1, as_=2, ns=3))
    assert ctx.eval("__b.hidden") is False
    assert ctx.eval("__b.classList.contains('vl-erreur')") is True     # au moins 1 erreur -> rouge
    assert '3' in ctx.eval("__b.textContent")                          # 3 QSO saisis à vérifier


def test_badge_suffixe_importes_quand_saisi_et_importe():
    ctx = _ctx()
    ctx.eval("window.LogxValidationLive._rendre(%s)" % _resp(es=0, as_=2, ns=2, ni=19647))
    t = ctx.eval("__b.textContent")
    assert '2 à vérifier' in t and '19647' in t and 'importés' in t   # « 2 à vérifier (+19647 importés) »
    assert ctx.eval("__b.classList.contains('vl-importe')") is False  # l'alarme reste sur le saisi


def test_badge_neutre_si_uniquement_importes():
    ctx = _ctx()
    ctx.eval("window.LogxValidationLive._rendre(%s)" % _resp(es=0, as_=0, ns=0, ni=5))
    assert ctx.eval("__b.hidden") is False
    assert ctx.eval("__b.classList.contains('vl-erreur')") is False   # PAS d'alarme
    assert ctx.eval("__b.classList.contains('vl-importe')") is True   # état neutre
    assert '5' in ctx.eval("__b.textContent") and 'importés' in ctx.eval("__b.textContent")


def test_fil_ia_ne_pousse_que_le_saisi():
    ctx = _ctx()
    ctx.eval("window.LogxValidationLive._rendre(%s)" % _resp(es=1, as_=2, ns=1, ni=9))
    assert ctx.eval("window.__filPush[window.__filPush.length-1].source") == 'validation'
    assert ctx.eval("window.__filPush[window.__filPush.length-1].n") == 1   # une entrée (saisis à vérifier)
    # Uniquement des importés -> RIEN dans le fil IA (historique, pas actionnable).
    ctx.eval("window.LogxValidationLive._rendre(%s)" % _resp(es=0, as_=0, ns=0, ni=9))
    assert ctx.eval("window.__filPush[window.__filPush.length-1].n") == 0


def test_retrocompat_serveur_sans_ventilation():
    # Serveur ancien : pas de counts_saisi/qso_a_verifier_saisi -> repli sur les
    # compteurs globaux, tout traité comme « saisi ».
    ctx = _ctx()
    ctx.eval("window.LogxValidationLive._rendre({counts:{erreur:0,attention:3,info:0}, qso_a_verifier:3})")
    assert ctx.eval("__b.hidden") is False
    assert '3' in ctx.eval("__b.textContent") and 'vérifier' in ctx.eval("__b.textContent")


def test_cablage_logbook():
    with open(os.path.join(CONCOURS, 'logx_logbook.html'), encoding='utf-8') as f:
        h = f.read()
    assert 'src="logx_validation_live.js"' in h        # module chargé (alimente le fil IA)
    # Le badge d'en-tête a été RETIRÉ (le fil IA « Ce que l'IA remarque » le
    # résume, avec la même action ouvrir VÉRIFIER au clic).
    assert 'id="validationBadge"' not in h
