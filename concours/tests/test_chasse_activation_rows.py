# -*- coding: utf-8 -*-
"""renderActivationRows (fusion D2, incr. 4b) : rendu PUR des lignes d'un panneau
d'activation « en direct » (POTA/SOTA/WWFF/WCA), format sr-act commun, la ligne
« lieu » fournie par opts.place(s) (park_name / summit_name+alt+pts / …). Champs
issus de services tiers publics -> tout passe par esc(). Exécuté en V8.
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


def test_expose_render_activation_rows():
    ctx = _ctx()
    assert ctx.eval("typeof window.LogxChassePanneaux.renderActivationRows") == 'function'


def test_rend_call_band_freq_mode():
    ctx = _ctx()
    html = ctx.eval("""window.LogxChassePanneaux.renderActivationRows([
        {call:'F4ABC', band:'14', freq:14285, mode:'SSB', reference:'FF-0001'}
    ])""")
    assert 'F4ABC' in html and 'sr-act' in html
    assert '14.285 MHz' in html          # freq kHz -> MHz, 3 décimales
    assert 'SSB' in html


def test_place_fn_utilisee():
    ctx = _ctx()
    html = ctx.eval("""window.LogxChassePanneaux.renderActivationRows(
        [{call:'F4ABC', reference:'F/AB-421'}],
        {place:function(s){ return 'SOMMET ' + s.reference; }}
    )""")
    assert 'SOMMET F/AB-421' in html


def test_echappe_les_champs_tiers():
    ctx = _ctx()
    html = ctx.eval("window.LogxChassePanneaux.renderActivationRows([{call:'<x>', band:'14', comment:'<b>hi</b>'}])")
    assert '<x>' not in html and '&lt;x&gt;' in html
    assert '<b>hi</b>' not in html and '&lt;b&gt;' in html


def test_respecte_le_max():
    ctx = _ctx()
    n = ctx.eval("""(function(){
        var s=[]; for(var i=0;i<40;i++) s.push({call:'C'+i});
        return (window.LogxChassePanneaux.renderActivationRows(s,{max:10}).match(/sr-act/g)||[]).length;
    })()""")
    assert n == 10


# ═══════════════════════════════════════════════════════════════════════════
# État vide (écart de comportement signalé le 12/09/2026, fusion CHASSE→
# activité incr. 4b : l'ancienne page CHASSE affichait un message par
# programme, perdu à la fusion -- panneau simplement vide sans texte).
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize('programme,attendu', [
    ('POTA', "Aucun trafic POTA signalé pour l'instant."),
    ('SOTA', "Aucun trafic SOTA signalé pour l'instant."),
    ('WWFF', "Aucun trafic WWFF signalé pour l'instant."),
])
def test_etat_vide_par_programme(programme, attendu):
    ctx = _ctx()
    html = ctx.eval(
        "window.LogxChassePanneaux.renderActivationRows([], {programme:'%s'})" % programme)
    assert 'ck-need-empty' in html
    assert attendu in html


def test_etat_vide_sans_programme_repli_generique():
    ctx = _ctx()
    html = ctx.eval("window.LogxChassePanneaux.renderActivationRows([])")
    assert 'ck-need-empty' in html
    assert "Aucun trafic signalé pour l'instant." in html


def test_etat_vide_programme_inconnu_repli_generique():
    ctx = _ctx()
    html = ctx.eval(
        "window.LogxChassePanneaux.renderActivationRows([], {programme:'AUTRE'})")
    assert "Aucun trafic signalé pour l'instant." in html


def test_liste_non_vide_naffiche_pas_le_message_vide():
    ctx = _ctx()
    html = ctx.eval(
        "window.LogxChassePanneaux.renderActivationRows([{call:'F4ABC'}], {programme:'POTA'})")
    assert 'ck-need-empty' not in html
    assert 'F4ABC' in html
