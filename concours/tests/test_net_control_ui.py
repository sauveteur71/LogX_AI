# -*- coding: utf-8 -*-
"""Net Control — page UI (tranche 2). La page logx_net_control.html branche la
maquette validée (#306) sur les endpoints serveur (tranche 1, #308) et tient la
FILE de passage du micro côté client. Ce test vérifie en V8 la logique PURE de
session (mêmes règles que le serveur logx_net_control.py) exposée par
logx_net_control.js, plus le câblage structurel de la page (scripts, endpoints).
"""
import os
import re

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS = os.path.join(CONCOURS, 'logx_net_control.js')
HTML = os.path.join(CONCOURS, 'logx_net_control.html')
py_mini_racer = pytest.importorskip('py_mini_racer')


def _ctx():
    ctx = py_mini_racer.MiniRacer()
    ctx.eval("var window = {}; var document = {}; var module = undefined;")
    with open(JS, encoding='utf-8') as f:
        ctx.eval(f.read())
    return ctx


def _j(ctx, expr):
    import json
    return json.loads(ctx.eval("JSON.stringify(" + expr + ")"))


# ── Logique de session (pure, exposée sur window.NetControl) ───────────────
def test_mettre_a_l_air_dedupe_et_normalise():
    ctx = _ctx()
    s = _j(ctx, "(function(){var s={on_air:[],logged:[]};"
                "s=window.NetControl.mettreALAir(s,'f5abc');"
                "s=window.NetControl.mettreALAir(s,'F6DEF');"
                "s=window.NetControl.mettreALAir(s,'F5ABC');return s;})()")
    assert s['on_air'] == ['F5ABC', 'F6DEF']       # normalisé, sans doublon


def test_passer_au_suivant_rotation():
    ctx = _ctx()
    s = _j(ctx, "window.NetControl.passerAuSuivant({on_air:['A','B','C'],logged:[]})")
    assert s['on_air'] == ['B', 'C', 'A']


def test_loguer_courant_sort_de_la_file():
    ctx = _ctx()
    s = _j(ctx, "window.NetControl.loguerCourant({on_air:['A','B'],logged:[]})")
    assert s['on_air'] == ['B'] and s['logged'] == ['A']


def test_loguer_courant_file_vide_sans_casse():
    ctx = _ctx()
    s = _j(ctx, "window.NetControl.loguerCourant({on_air:[],logged:['A']})")
    assert s['on_air'] == [] and s['logged'] == ['A']


# ── Câblage de la page (structure, pas mannequin) ─────────────────────────
def test_html_charge_le_js_et_a_les_conteneurs():
    h = open(HTML, encoding='utf-8').read()
    assert 'src="logx_net_control.js"' in h
    assert re.search(r'id="netSelect"', h)      # sélecteur de réseau
    assert re.search(r'id="micWrap"', h)         # zone AU MICRO
    assert re.search(r'id="roster"', h)          # répertoire


def test_js_appelle_les_endpoints_tranche1():
    js = open(JS, encoding='utf-8').read()
    for ep in ('/data/nets', '/nets/create', '/nets/delete',
               '/nets/roster/add', '/nets/roster/remove'):
        assert ep in js, f"endpoint manquant dans le câblage : {ep}"


# ── Tranche 3 : log dans le carnet UNIQUE ─────────────────────────────────
def test_construire_qso_depuis_le_reseau():
    """La station au micro devient un vrai QSO : indicatif normalisé, bande +
    mode + fréquence du réseau, RST par défaut, commentaire tagué réseau."""
    ctx = _ctx()
    q = _j(ctx, "window.NetControl.construireQso('f5abc',"
                "{nom:'Dimanche',bande:'3.5',mode:'SSB',freq:'3.650'})")
    assert q['call'] == 'F5ABC'
    assert q['band'] == '3.5' and q['mode'] == 'SSB' and q['freq'] == '3.650'
    assert q['rst_sent'] == '59' and q['rst_rcvd'] == '59'
    assert 'Dimanche' in q['comment']


def test_construire_qso_mode_par_defaut_ssb():
    ctx = _ctx()
    q = _j(ctx, "window.NetControl.construireQso('A',{bande:'14'})")
    assert q['mode'] == 'SSB'          # réseau sans mode -> SSB (phonie)


def test_js_logue_dans_le_carnet_unique_via_log_add():
    js = open(JS, encoding='utf-8').read()
    assert '/log/add' in js            # le vrai chemin d'ajout au carnet unique


def test_html_a_les_selects_bande_mode_et_loguer_tout():
    h = open(HTML, encoding='utf-8').read()
    assert re.search(r'id="netBande"', h)     # select bande (création réseau)
    assert re.search(r'id="netMode"', h)      # select mode
    assert 'loguerTout' in h                   # bouton « loguer tout le réseau »
