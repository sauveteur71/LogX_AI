# -*- coding: utf-8 -*-
"""Coach : fréquence lisible avec unité ; CARTE IA : fiche station dans un coin
(F4GLD, 28/10/2026).

- « C5R 50.314099999999996 spotté » (flottant brut, source VHF en MHz) et
  « je ne sais pas sur quelle fréquence » -> « (50314.1 kHz) ».
- « le popup s'ouvre en plein milieu » -> coin haut-droit de la carte, ou
  haut-gauche si la station cliquée tomberait dessous.
"""
import os
import re

import pytest

import logx_coach

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.mark.parametrize('freq,band,attendu', [
    (50.314099999999996, '', ' (50314.1 kHz)'),      # source VHF en MHz
    ('10136.0', '', ' (10136 kHz)'),
    (21382.3, '21', ' (21382.3 kHz)'),
    (14195.55, '14', ' (14195.55 kHz)'),
    (None, '', ''), ('', '', ''), ('abc', '', ''),
])
def test_texte_freq(freq, band, attendu):
    assert logx_coach.texte_freq(freq, band) == attendu


def test_nudge_affiche_la_frequence_avec_unite():
    state = {'clock': {'status': 'en_cours'},
             'new_targets': [{'call': 'C5R', 'type': 'dxcc', 'label': 'The Gambia',
                              'freq': 50.314099999999996}]}
    n = logx_coach.coach_nudge(state, 'fr')
    assert '(50314.1 kHz)' in n['text'] and '50.3140999' not in n['text']


def test_hints_serveur_passent_par_texte_freq():
    with open(os.path.join(CONCOURS, 'logx_http.py'), encoding='utf-8') as f:
        s = f.read()
    assert re.search(r"freq_txt = texte_freq\(n\.get\('freq'\), n\.get\('band', ''\)\)", s)
    assert "freq_txt = f\" {n['freq']}\"" not in s


py_mini_racer = pytest.importorskip('py_mini_racer')


def _fn(src, nom):
    m = re.search(r'\nfunction ' + re.escape(nom) + r'\s*\(', src)
    i = src.index('function', m.start())
    j = src.index('{', i)
    prof = 0
    for k in range(j, len(src)):
        if src[k] == '{':
            prof += 1
        elif src[k] == '}':
            prof -= 1
            if prof == 0:
                return src[i:k + 1]


def _ctx(prop_visible=True):
    c = py_mini_racer.MiniRacer()
    c.eval("""
      var window = {innerWidth: 1920, innerHeight: 1032};
      function el(r, vis){ return {offsetParent: vis ? {} : null, getBoundingClientRect: function(){ return r; }}; }
      var __map = el({left:500, top:300, right:1920, bottom:1032}, true);
      var __prop = el({left:1686, top:310, right:1910, bottom:345}, %s);
      var __carres = el({left:510, top:356, right:746, bottom:430}, true);
      var document = {
        querySelector: function(s){ return s === '.map-container' ? __map : null; },
        getElementById: function(id){ return id === 'propControl' ? __prop : (id === 'carresControl' ? __carres : null); }};
    """ % ('true' if prop_visible else 'false'))
    with open(os.path.join(CONCOURS, 'logx_carte.html'), encoding='utf-8') as f:
        c.eval(_fn(f.read(), 'positionFicheStation'))
    return c


def test_fiche_dans_le_coin_haut_droit_sous_propagation():
    c = _ctx()
    p = c.eval("JSON.stringify(positionFicheStation(1050, 560))")   # clic au milieu
    assert p == '{"left":1670,"top":355}'


def test_fiche_sans_panneau_propagation_colle_au_haut_de_la_carte():
    c = _ctx(prop_visible=False)
    assert c.eval("positionFicheStation(1050, 560).top") == 310


def test_fiche_bascule_a_gauche_si_la_station_est_dessous():
    c = _ctx()
    p = c.eval("JSON.stringify(positionFicheStation(1800, 400))")   # station en haut à droite
    assert p == '{"left":756,"top":355}'


def test_show_tooltip_utilise_la_position_de_coin():
    with open(os.path.join(CONCOURS, 'logx_carte.html'), encoding='utf-8') as f:
        corps = _fn(f.read(), 'showTooltip')
    assert re.search(r'const coin=positionFicheStation\(ev\.clientX, ev\.clientY\);\s*tt\.style\.left=coin\.left', corps)
    assert 'ev.clientX+16' not in corps


def test_scripts_de_la_carte_compilent():
    """Garde-fou : une redéclaration (« Identifier 'pos' has already been
    declared ») cassait TOUTE la page carte — vu en navigateur, invisible pour
    les tests qui extraient une seule fonction."""
    with open(os.path.join(CONCOURS, 'logx_carte.html'), encoding='utf-8') as f:
        html = f.read()
    blocs = re.findall(r'<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>', html, flags=re.S)
    assert blocs
    c = py_mini_racer.MiniRacer()
    for i, b in enumerate(blocs):
        c.eval('var __src = ' + __import__('json').dumps(b) + ';')
        err = c.eval("(function(){ try{ new Function(__src); return ''; }catch(e){ return String(e); } })()")
        assert err == '', 'bloc <script> n°%d : %s' % (i, err)
