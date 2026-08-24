# -*- coding: utf-8 -*-
"""Trois bugs d'affichage (Strate 2 de l'audit), re-vérifiés vivants.

1) logx_panel.html — horloge « 1h60 » : Math.round peut porter les minutes à 60
   (remaining_h=1.999 -> 1 h + round(59.94)=60) au lieu de 2h00. Fix : retenue
   dans _resteHM.
2) logx_carte.html refreshTiles — setUrl sans resynchroniser options.subdomains
   (les fonds jour/nuit diffèrent : 'abc' vs 'abcd') -> tuiles 404 après bascule.
3) logx_carte.html parseScores — regex \\d{3,4} tronque un DX >= 10000 km
   (« 12345 km » lu « 2345 km »). Fix : \\d{3,5}.

Tests comportementaux sur les VRAIES fonctions extraites (py_mini_racer).
"""
import json
import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PANEL = open(os.path.join(BASE, 'logx_panel.html'), encoding='utf-8').read()
CARTE = open(os.path.join(BASE, 'logx_carte.html'), encoding='utf-8').read()


def _extraire_fn(src, nom):
    i = src.index('function ' + nom)
    j = src.index('{', i)
    prof, k = 0, j
    while k < len(src):
        if src[k] == '{':
            prof += 1
        elif src[k] == '}':
            prof -= 1
            if prof == 0:
                return src[i:k + 1]
        k += 1
    raise AssertionError('fonction %s introuvable' % nom)


def test_horloge_pas_de_1h60():
    from py_mini_racer import py_mini_racer as m
    c = m.MiniRacer()
    c.eval(_extraire_fn(PANEL, '_resteHM'))
    assert c.eval('JSON.stringify(_resteHM(1.999))') == '{"h":2,"m":0}'    # pas 1h60
    assert c.eval('JSON.stringify(_resteHM(1.5))') == '{"h":1,"m":30}'
    assert c.eval('JSON.stringify(_resteHM(0))') == '{"h":0,"m":0}'
    assert c.eval('JSON.stringify(_resteHM(2.0))') == '{"h":2,"m":0}'


def test_refresh_tiles_resynchronise_subdomains():
    from py_mini_racer import py_mini_racer as m
    c = m.MiniRacer()
    c.eval('var leafletTile = { options:{subdomains:"abc"}, setUrl:function(u){ this._u=u; } };')
    c.eval('function getTileConfig(){ return {url:"http://x/{s}", sub:"abcd"}; }')
    c.eval(_extraire_fn(CARTE, 'refreshTiles'))
    c.eval('refreshTiles();')
    assert c.eval('leafletTile.options.subdomains') == 'abcd', "subdomains doit suivre le fond courant"
    assert c.eval('leafletTile._u') == 'http://x/{s}'


def test_parse_scores_dx_5_chiffres():
    from py_mini_racer import py_mini_racer as m
    c = m.MiniRacer()
    c.eval('var _els = {}; var document = { getElementById:function(id){ return (_els[id] = _els[id] || {textContent:""}); } };')
    c.eval('function rcT(s){ return s; }')
    c.eval(_extraire_fn(CARTE, 'parseScores'))
    c.eval('parseScores(%s)' % json.dumps('Meilleur DX 12345 km'))
    assert c.eval('_els["scoreBestDX"].textContent') == '12345 km', "un DX de 12345 km doit être lu entier"
