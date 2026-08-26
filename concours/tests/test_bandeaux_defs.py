# -*- coding: utf-8 -*-
"""Bandeaux défilants — étape 2 : DÉFINITIONS concrètes (logx_bandeaux_defs.js).

Ces bandeaux transforment les données DÉJÀ récupérées par la page (forme réelle
des endpoints /data/dxpeditions_active et /data/propagation) en items de ticker.
Règle de contenu F4GLD : diffuser du LIVE en priorité ; DXpéditions filtrées aux
7 prochains jours. Testé en V8 comme le framework (tests/test_bandeaux.py).

Les résultats JS transitent par JSON.stringify -> json.loads : py_mini_racer
rend sinon un JSObject opaque (pas de len(), pas d'indexation Python)."""
import json
import os

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRAMEWORK = os.path.join(CONCOURS, 'logx_bandeaux.js')
DEFS = os.path.join(CONCOURS, 'logx_bandeaux_defs.js')
py_mini_racer = pytest.importorskip('py_mini_racer')

NOW_MS = 1_756_000_000_000  # ancrage fixe (~2025-08-24) pour un filtre 7j déterministe
JOUR = 86_400_000


def _ctx():
    ctx = py_mini_racer.MiniRacer()
    ctx.eval("var window = {}; var module = undefined;")
    with open(FRAMEWORK, encoding='utf-8') as f:
        ctx.eval(f.read())
    with open(DEFS, encoding='utf-8') as f:
        ctx.eval(f.read())
    return ctx


def _j(ctx, expr):
    """Évalue `expr` (qui rend un objet/tableau JS) et le ramène en Python."""
    return json.loads(ctx.eval("JSON.stringify(" + expr + ")"))


def _dxped_expr(expeditions, now=NOW_MS):
    return ("window.LogxBandeaux.REGISTRE.dxped.construire({maintenant:%d},"
            "{dxpeditions:{expeditions:%s}})" % (now, json.dumps(expeditions)))


def test_les_deux_bandeaux_sont_enregistres():
    ctx = _ctx()
    assert ctx.eval("typeof window.LogxBandeaux.REGISTRE.dxped") == 'object'
    assert ctx.eval("typeof window.LogxBandeaux.REGISTRE.propag") == 'object'


def test_dxped_live_dabord_meme_sans_date_lisible():
    """Une expédition ACTIVE (repérée sur le cluster) doit passer même si ses
    dates NG3K sont illisibles : le LIVE prime (règle F4GLD)."""
    ctx = _ctx()
    items = _j(ctx, _dxped_expr([
        {'callsign': 'TX9A', 'entity': 'Chatham', 'status': 'active',
         'starts': None, 'ends': None, 'freq_khz': 14074, 'spot_band': '20m'},
    ]))
    assert len(items) == 1
    assert 'TX9A' in items[0]['texte']
    assert '14.074' in items[0]['texte']      # fréquence live affichée


def test_dxped_a_venir_dans_7_jours_gardee_au_dela_ecartee():
    ctx = _ctx()
    # Dates ISO calculées en JS relativement à NOW pour éviter toute dépendance
    # au fuseau : proche = +3 j (gardée), loin = +30 j (écartée).
    js = (
        "(function(){var now=%d;var iso=function(off){return new Date(now+off*%d)"
        ".toISOString().slice(0,10);};"
        "var d=[{callsign:'A1B',entity:'Proche',status:'upcoming',starts:iso(3),ends:iso(9)},"
        "{callsign:'C2D',entity:'Loin',status:'upcoming',starts:iso(30),ends:iso(40)}];"
        "return window.LogxBandeaux.REGISTRE.dxped.construire({maintenant:now},"
        "{dxpeditions:{expeditions:d}});})()" % (NOW_MS, JOUR)
    )
    items = json.loads(ctx.eval("JSON.stringify(" + js + ")"))
    calls = ''.join(i['texte'] for i in items)
    assert 'A1B' in calls        # commence dans 3 jours -> gardée
    assert 'C2D' not in calls    # commence dans 30 jours -> écartée


def test_dxped_terminee_exclue():
    ctx = _ctx()
    items = _j(ctx, _dxped_expr([
        {'callsign': 'END', 'entity': 'Finie', 'status': 'ended',
         'starts': '2025-01-01', 'ends': '2025-01-10'},
    ]))
    assert items == []


def test_dxped_echappe_le_contenu_reseau():
    """entity vient d'un flux externe (NG3K) : passé en {texte}, le framework
    doit l'échapper au rendu (pas d'injection)."""
    ctx = _ctx()
    d = [{'callsign': 'X', 'entity': '<img src=x onerror=alert(1)>',
          'status': 'active', 'freq_khz': 0}]
    html = ctx.eval(
        "window.LogxBandeaux.rendreTicker(['dxped'],{maintenant:%d},"
        "{dxpeditions:{expeditions:%s}})" % (NOW_MS, json.dumps(d))
    )
    assert '<img' not in html           # échappé
    assert '&lt;img' in html            # présent sous forme échappée


def _propag_expr(bandes):
    return ("window.LogxBandeaux.REGISTRE.propag.construire({},"
            "{propagation:{etat_bandes:{bandes:%s,muf_mhz:21.0,soleil_deg:30}}})"
            % json.dumps(bandes))


def test_propag_ne_montre_que_les_bandes_exploitables():
    ctx = _ctx()
    items = _j(ctx, _propag_expr([
        {'band': '20', 'etat': 'ouverte', 'score': 80, 'raison': 'DX'},
        {'band': '40', 'etat': 'possible', 'score': 50, 'raison': 'régional'},
        {'band': '10', 'etat': 'fermee', 'score': 10, 'raison': 'au-dessus MUF'},
    ]))
    txt = ''.join(i['texte'] for i in items)
    assert '20' in txt        # ouverte -> montrée
    assert '40' in txt        # possible -> montrée
    assert '10' not in txt    # fermee -> masquée


def test_propag_aucune_bande_ouverte_pas_de_ligne_morte():
    ctx = _ctx()
    items = _j(ctx, _propag_expr([
        {'band': '10', 'etat': 'fermee', 'score': 5, 'raison': 'nuit'},
    ]))
    assert items == []
