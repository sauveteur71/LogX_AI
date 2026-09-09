# -*- coding: utf-8 -*-
"""Module partagé logx_chasse_panneaux.js (fusion D2, incr. 1) : fonctions PURES
de rendu de spot extraites de logx_chasse.html, réutilisables par le cockpit
d'accueil. Aucune dépendance DOM. Exécuté en V8.

CHASSE (logx_chasse.html) N'EST PAS modifiée à cet incrément — le module est
purement additif ; ses garde-fous (test_page_chasse_split, test_chasse_affiche_credit)
restent verts.
"""
import os

import pytest

py_mini_racer = pytest.importorskip(
    'py_mini_racer', reason='py_mini_racer absent — test JS réel ignoré')

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS_PATH = os.path.join(BASE, 'logx_chasse_panneaux.js')


def _ctx():
    ctx = py_mini_racer.MiniRacer()
    ctx.eval("var window = this;")   # le module s'auto-monte sur window
    with open(JS_PATH, encoding='utf-8') as f:
        ctx.eval(f.read())
    return ctx


def test_module_expose_l_api():
    ctx = _ctx()
    assert ctx.eval("typeof window.LogxChassePanneaux") == 'object'
    for fn in ('esc', 'splitBadge', 'creditBadge'):
        assert ctx.eval("typeof window.LogxChassePanneaux.%s" % fn) == 'function', fn


def test_esc_echappe_le_html():
    ctx = _ctx()
    assert ctx.eval("window.LogxChassePanneaux.esc('<a>&\"')") == '&lt;a&gt;&amp;&quot;'


def test_credit_badge_atno_score_positif():
    ctx = _ctx()
    html = ctx.eval("window.LogxChassePanneaux.creditBadge({credit_classe:'atno', credit_score:5, credit_raison:'nouveau pays'})")
    assert 'cr-atno' in html and 'ATNO' in html
    assert 'cr-off' not in html          # score > 0 -> pas atténué
    assert '(+5)' in html                # score dans le title


def test_credit_badge_score_nul_est_attenue():
    ctx = _ctx()
    html = ctx.eval("window.LogxChassePanneaux.creditBadge({credit_classe:'atno', credit_score:0})")
    assert 'cr-off' in html              # objectif désactivé -> atténué (pas masqué)


def test_credit_badge_sans_credit_rien():
    ctx = _ctx()
    assert ctx.eval("window.LogxChassePanneaux.creditBadge({})") == ''
    assert ctx.eval("window.LogxChassePanneaux.creditBadge({credit_classe:'inconnu'})") == ''


def test_split_badge_up_offset():
    ctx = _ctx()
    html = ctx.eval("window.LogxChassePanneaux.splitBadge({split:{split:true, direction:'up', offset_khz:5}})")
    assert '↑' in html and 'UP' in html and '5' in html
