# -*- coding: utf-8 -*-
"""Page CHASSE : filtre CW / Phonie / Data + bandes, pleine largeur
(demande F4GLD, 28/10/2026).

Le classement d'un spot (mode_cat) est fait UNE fois côté serveur
(logx_chasse_filtre.py) ; le navigateur compare seulement. On teste :
  - la classification (mode annoncé prioritaire, repli plan de bande) ;
  - le filtre serveur appliqué AVANT la coupe de /data/spots_ranked ;
  - l'annotation des trois endpoints d'activation ;
  - le module JS réel (garder / requete / clic / mémorisation) ;
  - le câblage de la page (panneaux filtrés, need-list filtrée, largeur).
"""
import os
import re
from urllib.parse import parse_qs

import pytest

import logx_chasse_filtre as cf

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _src(nom):
    with open(os.path.join(CONCOURS, nom), encoding='utf-8') as f:
        return f.read()


def _sans_commentaires_js(s):
    s = re.sub(r'/\*.*?\*/', '', s, flags=re.S)
    return re.sub(r'(?m)(^|[^:\'"\\])//.*$', r'\1', s)


def _sans_commentaires_py(s):
    return re.sub(r'(?m)#.*$', '', s)


# ── classification serveur ───────────────────────────────────────────────────

@pytest.mark.parametrize('mode,freq,attendu', [
    ('CW', None, 'cw'), ('SSB', None, 'phonie'), ('USB', None, 'phonie'),
    ('FM', None, 'phonie'), ('FT8', None, 'data'), ('RTTY', None, 'data'),
    ('PSK31', None, 'data'),
    ('', 14020, 'cw'), ('', 14250, 'phonie'),     # repli plan de bande
    ('', None, ''), ('XYZ', None, ''),
])
def test_categorie_mode(mode, freq, attendu):
    assert cf.categorie_mode(mode, freq) == attendu


def test_mode_annonce_prime_sur_le_plan_de_bande():
    # CW annoncé dans le segment phonie : c'est CW.
    assert cf.categorie_mode('CW', 14250) == 'cw'


def test_lire_choix_bands_modes_et_ancien_band():
    b, c = cf.lire_choix(parse_qs('bands=7,14&modes=CW,phonie,inconnu'))
    assert b == {'7', '14'} and c == {'cw', 'phonie'}
    b, c = cf.lire_choix(parse_qs('band=144'))       # Band Map (#481)
    assert b == {'144'} and c == set()


def test_filtrer_mode_inconnu_ecarte_seulement_si_filtre_actif():
    spots = cf.annoter([{'call': 'A', 'band': '7', 'freq': 7020, 'mode': 'CW'},
                        {'call': 'B', 'band': '14', 'freq': 14250, 'mode': 'SSB'},
                        {'call': 'C', 'band': '7', 'freq': 0, 'mode': ''}])
    assert [s['call'] for s in cf.filtrer(spots, set(), set())] == ['A', 'B', 'C']
    assert [s['call'] for s in cf.filtrer(spots, set(), {'cw'})] == ['A']
    assert [s['call'] for s in cf.filtrer(spots, {'7'}, set())] == ['A', 'C']
    assert [s['call'] for s in cf.filtrer(spots, {'14'}, {'phonie', 'cw'})] == ['B']


# ── câblage serveur ──────────────────────────────────────────────────────────

def _bloc_ranked():
    s = _sans_commentaires_py(_src('logx_http.py'))
    bloc = s[s.index("if path == '/data/spots_ranked':"):]
    return bloc[:bloc.index("self._json({'spots': visibles")]


def test_spots_ranked_filtre_avant_la_coupe():
    bloc = _bloc_ranked()
    i_ann = bloc.index('_cf.annoter(visibles)')
    i_lire = bloc.index('_cf.lire_choix(')
    i_filt = bloc.index('visibles = _cf.filtrer(visibles, _bandes, _cats)')
    assert i_ann < i_filt and i_lire < i_filt
    assert re.search(r'if _bandes or _cats:\s*\n\s*visibles = _cf\.filtrer', bloc)


@pytest.mark.parametrize('endpoint,appel', [
    ('/data/pota_spots', r'_cf\.annoter\(pota\.fetch_pota_spots\(\)\)'),
    ('/data/sota_spots', r'_cf\.annoter\(sota\.fetch_sota_spots\('),
    ('/data/wwff_spots', r'_cf\.annoter\(wwff\.fetch_wwff_spots\(\)\)'),
])
def test_endpoints_activation_annotent_mode_cat(endpoint, appel):
    s = _sans_commentaires_py(_src('logx_http.py'))
    bloc = s[s.index("if path == '%s':" % endpoint):]
    bloc = bloc[:bloc.index('return')]
    assert re.search(appel, bloc)


# ── module JS réel ───────────────────────────────────────────────────────────

py_mini_racer = pytest.importorskip('py_mini_racer')


def _ctx(stock='null'):
    c = py_mini_racer.MiniRacer()
    c.eval("""
      var __st = {'logx_chasse_filtre': %s};
      var window = {localStorage: {getItem: function(k){ return __st[k] === undefined ? null : __st[k]; },
                                   setItem: function(k, v){ __st[k] = v; }}};
      var __hote = {innerHTML: '', addEventListener: function(){}};
      var __changes = 0;
    """ % (stock if stock == 'null' else repr(stock)))
    c.eval(_src('logx_chasse_filtre.js'))
    c.eval("window.LogxChasseFiltre.monter(__hote, function(){ __changes++; });")
    return c


def _clic(c, g, v):
    c.eval("""window.LogxChasseFiltre._clic({target: {closest: function(){ return {
      getAttribute: function(a){ return a === 'data-g' ? %r : %r; } }; }}});""" % (g, v))


def test_js_sans_choix_tout_passe_et_pas_de_requete():
    c = _ctx()
    assert c.eval("window.LogxChasseFiltre.requete()") == ''
    assert c.eval("window.LogxChasseFiltre.garder({band:'7', mode_cat:''})") is True


def test_js_clic_filtre_memorise_et_notifie():
    c = _ctx()
    _clic(c, 'cat', 'cw')
    _clic(c, 'bande', '7')
    assert c.eval("__changes") == 2
    assert c.eval("window.LogxChasseFiltre.requete()") == '?bands=7&modes=cw'
    assert c.eval("window.LogxChasseFiltre.garder({band:'7', mode_cat:'cw'})") is True
    assert c.eval("window.LogxChasseFiltre.garder({band:'14', mode_cat:'cw'})") is False
    assert c.eval("window.LogxChasseFiltre.garder({band:'7', mode_cat:'phonie'})") is False
    assert c.eval("window.LogxChasseFiltre.garder({band:'7', mode_cat:''})") is False
    assert '"cats":["cw"]' in c.eval("__st['logx_chasse_filtre']")
    assert 'cf-puce on' in c.eval("__hote.innerHTML")


def test_js_tous_vide_le_groupe_et_reclic_decoche():
    c = _ctx()
    _clic(c, 'cat', 'cw'); _clic(c, 'cat', 'data')
    _clic(c, 'cat', 'cw')                       # re-clic : décoché
    assert c.eval("window.LogxChasseFiltre.etat().cats.join(',')") == 'data'
    _clic(c, 'cat', '*')
    assert c.eval("window.LogxChasseFiltre.etat().cats.length") == 0


def test_js_relit_le_choix_memorise_et_ignore_l_inconnu():
    c = _ctx('{"bandes":["14","999"],"cats":["phonie","xx"]}')
    assert c.eval("window.LogxChasseFiltre.requete()") == '?bands=14&modes=phonie'


def test_js_stockage_qui_jette_ne_casse_rien():
    c = py_mini_racer.MiniRacer()
    c.eval("""var window = {localStorage: {getItem: function(){ throw new Error('x'); },
                                         setItem: function(){ throw new Error('x'); }}};
              var __hote = {innerHTML:'', addEventListener: function(){}};""")
    c.eval(_src('logx_chasse_filtre.js'))
    c.eval("window.LogxChasseFiltre.monter(__hote, null);")
    assert 'cf-puce' in c.eval("__hote.innerHTML")


# ── câblage de la page ───────────────────────────────────────────────────────

def test_page_charge_le_module_et_passe_en_pleine_largeur():
    h = _src('logx_accueil.html')
    assert h.index('src="logx_chasse_filtre.js"') < h.index('src="logx_accueil.js"')
    assert re.search(r'\.intro\.intro-large\{max-width:none\}', h)
    js = _sans_commentaires_js(_src('logx_accueil.js'))
    corps = js[js.index('function _revelerCiblesChasse'):js.index('function _rafraichirNeedList')]
    assert re.search(r"intro\.classList\.add\('intro-large'\)", corps)
    assert 'id="chasseFiltre"' in corps
    assert re.search(r"LogxChasseFiltre\.monter\(document\.getElementById\('chasseFiltre'\)", corps)


def test_page_panneaux_et_needlist_filtres():
    js = _sans_commentaires_js(_src('logx_accueil.js'))
    for prog in ('Pota', 'Sota', 'Wwff'):
        ligne = re.search(r'function _charger%s\(\)\{[^\n]*' % prog, js).group(0)
        assert '_rendreActivations(d,' in ligne, prog
    corps = js[js.index('function _rendreActivations'):]
    corps = corps[:corps.index('\n}\n')]
    assert re.search(r'var gardes = F \? F\.filtrer\(tous\) : tous;', corps)
    assert 'P.renderActivationRows(gardes, opts)' in corps
    nl = js[js.index('function _rafraichirNeedList'):]
    nl = nl[:nl.index('\n}\n')]
    assert re.search(r"'/data/spots_ranked' \+ \(F \? F\.requete\(\) : ''\)", nl)


def test_libelle_de_bande_partage():
    s = _sans_commentaires_js(_src('logx_bandeaux_defs.js'))
    assert 'LB.libBande = _libBande;' in s
