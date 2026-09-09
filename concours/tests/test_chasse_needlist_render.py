# -*- coding: utf-8 -*-
"""renderNeedList : rendu COMPACT de la need-list (fusion D2, incr. 3), pour le
cockpit d'accueil. Fonction pure du module logx_chasse_panneaux.js, réutilise
esc/creditBadge/splitBadge/PRIO_COLORS. Lecture seule : pas de boutons QSY/rotor
(réservés à la vue activité complète). Exécuté en V8.
"""
import os

import pytest

py_mini_racer = pytest.importorskip(
    'py_mini_racer', reason='py_mini_racer absent — test JS réel ignoré')

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS_PATH = os.path.join(BASE, 'logx_chasse_panneaux.js')


def _ctx():
    ctx = py_mini_racer.MiniRacer()
    ctx.eval("var window = this;")
    with open(JS_PATH, encoding='utf-8') as f:
        ctx.eval(f.read())
    return ctx


def test_expose_render_need_list():
    ctx = _ctx()
    assert ctx.eval("typeof window.LogxChassePanneaux.renderNeedList") == 'function'


def test_liste_vide_message():
    ctx = _ctx()
    html = ctx.eval("window.LogxChassePanneaux.renderNeedList([])")
    assert 'ck-need-empty' in html


def test_rend_call_bande_et_credit():
    ctx = _ctx()
    html = ctx.eval("""window.LogxChassePanneaux.renderNeedList([
        {call:'F4XYZ', band:'14', freq:'14285', priority:1, credit_classe:'atno', credit_score:5}
    ])""")
    assert 'F4XYZ' in html and '14' in html
    assert 'cr-atno' in html            # badge crédit réutilisé du module


def test_respecte_le_max():
    ctx = _ctx()
    n = ctx.eval("""(function(){
        var spots=[]; for(var i=0;i<30;i++) spots.push({call:'C'+i, band:'14'});
        var html = window.LogxChassePanneaux.renderNeedList(spots, {max:5});
        return (html.match(/ck-need-row/g)||[]).length;
    })()""")
    assert n == 5                        # tronqué au max


def test_call_echappe_xss():
    ctx = _ctx()
    html = ctx.eval("window.LogxChassePanneaux.renderNeedList([{call:'<script>', band:'14'}])")
    assert '<script>' not in html and '&lt;script&gt;' in html
