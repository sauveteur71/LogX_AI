# -*- coding: utf-8 -*-
"""renderNeedList : rendu de la need-list (fusion D2, incr. 3 + 4d). Fonction
pure du module logx_chasse_panneaux.js, réutilise esc/creditBadge/splitBadge/
PRIO_COLORS. Lecture seule par défaut (cockpit d'accueil) ; les boutons
QSY/rotor apparaissent seulement si opts.rigEnabled/opts.rotorEnabled valent
vrai (vue activité complète, état lu côté appelant comme logx_chasse.html).
Exécuté en V8.
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


# ─── QSY / rotor (fusion incr. 4d) ──────────────────────────────────────────

def test_pas_de_qsy_ni_rotor_par_defaut():
    ctx = _ctx()
    html = ctx.eval("window.LogxChassePanneaux.renderNeedList([{call:'F4XYZ', band:'14', freq:14285, bearing:120}])")
    assert 'qsy-btn' not in html and 'point-btn' not in html


def test_qsy_absent_meme_active_si_pas_de_freq():
    ctx = _ctx()
    html = ctx.eval("window.LogxChassePanneaux.renderNeedList([{call:'F4XYZ', band:'14'}], {rigEnabled:true})")
    assert 'qsy-btn' not in html


def test_qsy_present_si_active_et_freq_connue():
    ctx = _ctx()
    html = ctx.eval("window.LogxChassePanneaux.renderNeedList([{call:'F4XYZ', band:'14', freq:14285}], {rigEnabled:true})")
    assert 'qsy-btn' in html and "qsyTo(14285,'F4XYZ')" in html


def test_rotor_absent_meme_active_si_pas_de_bearing():
    ctx = _ctx()
    html = ctx.eval("window.LogxChassePanneaux.renderNeedList([{call:'F4XYZ', band:'14'}], {rotorEnabled:true})")
    assert 'point-btn' not in html


def test_rotor_present_si_active_et_bearing_connu():
    # L'azimut BRUT part dans l'appel (comme logx_chasse.html) ; seul
    # l'affichage (🧭 120°) est arrondi.
    ctx = _ctx()
    html = ctx.eval("window.LogxChassePanneaux.renderNeedList([{call:'F4XYZ', band:'14', bearing:120.4}], {rotorEnabled:true})")
    assert 'point-btn' in html and "pointTo(120.4,'F4XYZ','14')" in html and '120°' in html


def test_qsy_rotor_echappent_indicatif_et_bande_contre_injection_js():
    # Le TEXTE AFFICHÉ (esc()) peut légitimement contenir des parenthèses --
    # seule la valeur imbriquée dans onclick="...'...'" doit être neutralisée
    # (jsCall/jsBand suppriment guillemets/parenthèses/point-virgule : aucune
    # évasion possible de la chaîne JS entre apostrophes).
    import re
    ctx = _ctx()
    html = ctx.eval("""window.LogxChassePanneaux.renderNeedList(
        [{call:\"F4X');alert(1);//\", band:\"14');alert(2);//\", freq:14285, bearing:10}],
        {rigEnabled:true, rotorEnabled:true}
    )""")
    onclicks = re.findall(r'onclick="([^"]*)"', html)
    assert len(onclicks) == 2
    for oc in onclicks:
        assert "alert(1)" not in oc and "alert(2)" not in oc
        assert "');" not in oc


# ─── Stratégie pile-up FT8 (fusion incr. 4f) ────────────────────────────────

def test_strat_btn_absent_par_defaut():
    ctx = _ctx()
    html = ctx.eval("window.LogxChassePanneaux.renderNeedList([{call:'F4XYZ', band:'14', mode:'SSB'}])")
    assert 'strat-btn' not in html


def test_strat_btn_present_sur_spot_ft8():
    ctx = _ctx()
    html = ctx.eval("window.LogxChassePanneaux.renderNeedList([{call:'F4XYZ', band:'14', mode:'FT8'}])")
    assert 'strat-btn' in html and "ft8Strategy('F4XYZ')" in html


def test_strat_btn_present_sur_spot_ft4_insensible_a_la_casse():
    ctx = _ctx()
    html = ctx.eval("window.LogxChassePanneaux.renderNeedList([{call:'F4XYZ', band:'14', mode:'ft4'}])")
    assert 'strat-btn' in html


def test_strat_btn_absent_sur_autre_mode_numerique():
    ctx = _ctx()
    html = ctx.eval("window.LogxChassePanneaux.renderNeedList([{call:'F4XYZ', band:'14', mode:'RTTY'}])")
    assert 'strat-btn' not in html


def test_strat_btn_echappe_indicatif_contre_injection_js():
    ctx = _ctx()
    html = ctx.eval("window.LogxChassePanneaux.renderNeedList([{call:\"F4X');alert(1);//\", band:'14', mode:'FT8'}])")
    import re
    onclicks = re.findall(r'onclick="([^"]*)"', html)
    strat = [oc for oc in onclicks if oc.startswith('ft8Strategy')]
    assert strat and 'alert(1)' not in strat[0] and "');" not in strat[0]


# ─── jsCall / jsBand ────────────────────────────────────────────────────────

def test_jscall_retire_les_caracteres_dangereux():
    # Le '/' est un caractère VALIDE d'indicatif portable (F4XYZ/P) : conservé.
    ctx = _ctx()
    assert ctx.eval("window.LogxChassePanneaux.jsCall(\"F4X');alert(1)//\")") == 'F4Xalert1//'


def test_jsband_retire_les_caracteres_dangereux():
    ctx = _ctx()
    assert ctx.eval("window.LogxChassePanneaux.jsBand(\"14');alert(1)//\")") == '14alert1'
