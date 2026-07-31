# -*- coding: utf-8 -*-
"""Détacher PLUSIEURS band maps à la fois, un par bande.

DEMANDE UTILISATEUR : « je veux pouvoir détacher 5 band maps pour les
surveiller en simultané sur un autre écran ; le top pour moi c'est 3 écrans
pour tout voir. »

LE DÉFAUT : `openPanel()` nommait la fenêtre « rc_panel_bandmap », SANS la
bande. Or `window.open(url, nom)` ne crée pas de fenêtre quand une fenêtre
porte déjà ce nom : elle la RÉUTILISE et y charge la nouvelle URL. Détacher le
band map du 20 m puis celui du 15 m ne donnait donc pas deux fenêtres — la
première changeait de bande. Aucune erreur, aucun message : juste une fenêtre
qui saute d'une bande à l'autre pendant qu'on croit en avoir ouvert deux.
`popoutScope()` avait le même défaut avec son nom fixe « rc_scope ».

Le même nommage cassait l'enregistrement des DISPOSITIONS : `saveLayout()`
parcourait les TYPES de panneaux (`PANEL_DEFAULTS`), donc cinq band maps
n'entraient qu'une fois dans la disposition, et la recharger n'en rouvrait
qu'un seul.

CE QUI EST TESTÉ : le VRAI bloc de gestion des panneaux, extrait tel quel de
logx_statusbar.js par comptage d'accolades et exécuté dans V8 avec un
`window.open` factice qui enregistre les noms — même technique que
tests/test_report_issue_form_prefill.py. On observe donc le comportement, pas
une reformulation du code qui pourrait diverger de lui.
"""
import json
import os
import re
import sys

import pytest

py_mini_racer = pytest.importorskip(
    'py_mini_racer', reason='py_mini_racer absent (voir requirements.txt)')

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CONCOURS not in sys.path:
    sys.path.insert(0, CONCOURS)

STATUSBAR = os.path.join(CONCOURS, 'logx_statusbar.js')
LOGBOOK_JS = os.path.join(CONCOURS, 'logx_logbook.js')


def _lire(p):
    with open(p, encoding='utf-8') as f:
        return f.read()


def _bloc_panneaux(src):
    """De `const PANEL_DEFAULTS` à la fin de `resetLayout()`, accolades
    comptées — on prend le vrai code, pas une copie."""
    debut = src.index('const PANEL_DEFAULTS')
    fin_fn = src.index('function resetLayout(', debut)
    ouv = src.index('{', fin_fn)
    prof, i = 0, ouv
    while True:
        c = src[i]
        if c == '{':
            prof += 1
        elif c == '}':
            prof -= 1
            if prof == 0:
                return src[debut:i + 1]
        i += 1


# `renderLayoutDD` touche au DOM : on la neutralise, elle n'a rien à voir avec
# le nommage des fenêtres. Tout le reste est le code de production.
_HARNESS = r"""
var screen = {width: 1920, height: 1080};
var _fenetres = [];      // {nom, url, closed}
var window = {
  open: function(url, nom){
    // Reproduit la règle du navigateur : un nom DÉJÀ OUVERT est réutilisé,
    // la fenêtre existante navigue vers la nouvelle URL. C'est précisément ce
    // qui faisait disparaître le 2e band map.
    for (var i = 0; i < _fenetres.length; i++){
      if (_fenetres[i].nom === nom && !_fenetres[i].closed){
        _fenetres[i].url = url;
        return _fenetres[i];
      }
    }
    var w = {nom: nom, url: url, closed: false,
             outerWidth: 260, outerHeight: 640, screenX: 0, screenY: 0,
             close: function(){ this.closed = true; }};
    _fenetres.push(w);
    return w;
  }
};
var _stockage = {};
var localStorage = {
  getItem: function(k){ return (k in _stockage) ? _stockage[k] : null; },
  setItem: function(k, v){ _stockage[k] = String(v); }
};
function renderLayoutDD(){}
function ouvertes(){
  return _fenetres.filter(function(w){ return !w.closed; });
}
"""


def _ctx():
    c = py_mini_racer.MiniRacer()
    c.eval(_HARNESS)
    c.eval(_bloc_panneaux(_lire(STATUSBAR)))
    return c


def _ouvrir_cinq_bandes(ctx, bandes=('28', '21', '14', '7', '3.5')):
    for b in bandes:
        ctx.eval("openPanel('bandmap', {band: %s});" % json.dumps(b))
    return bandes


# ─── Le cœur de la demande ───────────────────────────────────────────────────

def test_CINQ_BAND_MAPS_FONT_CINQ_FENETRES():
    """Cinq bandes détachées doivent donner cinq fenêtres. Avant le correctif,
    il n'y en avait qu'UNE, qui changeait de bande à chaque clic."""
    ctx = _ctx()
    bandes = _ouvrir_cinq_bandes(ctx)
    assert ctx.eval('ouvertes().length') == len(bandes)


def test_chaque_band_map_porte_un_nom_de_fenetre_DISTINCT():
    """C'est le nom qui décide : deux fenêtres de même nom n'en font qu'une."""
    ctx = _ctx()
    _ouvrir_cinq_bandes(ctx)
    noms = json.loads(ctx.eval('JSON.stringify(ouvertes().map(function(w){return w.nom;}))'))
    assert len(set(noms)) == 5, noms


def test_chaque_fenetre_vise_SA_bande():
    """Cinq fenêtres identiques ne serviraient à rien : ce qu'on veut, c'est
    voir cinq bandes en même temps."""
    ctx = _ctx()
    bandes = _ouvrir_cinq_bandes(ctx)
    urls = json.loads(ctx.eval('JSON.stringify(ouvertes().map(function(w){return w.url;}))'))
    for b in bandes:
        assert any('band=' + b.replace('.', '%2E') in u or 'band=' + b in u
                   for u in urls), 'aucune fenetre pour la bande %s : %s' % (b, urls)


def test_le_point_d_une_bande_decimale_ne_casse_pas_le_nom():
    """« 10.1 » et « 3.5 » sont des noms de bande légitimes ; un point dans un
    nom de fenêtre est au mieux ignoré, au pire refusé selon le navigateur."""
    ctx = _ctx()
    ctx.eval("openPanel('bandmap', {band: '10.1'});")
    nom = json.loads(ctx.eval('JSON.stringify(ouvertes()[0].nom)'))
    assert '.' not in nom, nom
    assert '10_1' in nom, nom


def test_redemander_LA_MEME_bande_ne_cree_pas_de_doublon():
    """Le pendant du correctif : une fenêtre PAR BANDE, pas une par clic.
    Recliquer sur 20 m doit ramener la fenêtre 20 m au premier plan, pas en
    empiler une deuxième identique."""
    ctx = _ctx()
    ctx.eval("openPanel('bandmap', {band: '14'});")
    ctx.eval("openPanel('bandmap', {band: '14'});")
    assert ctx.eval('ouvertes().length') == 1


def test_les_AUTRES_panneaux_restent_a_une_seule_fenetre():
    """Le coach ou la météo solaire n'ont pas de déclinaison par bande : en
    ouvrir deux n'aurait aucun sens, et le comportement d'origine est le bon."""
    ctx = _ctx()
    for _ in range(3):
        ctx.eval("openPanel('coach');")
        ctx.eval("openPanel('solarweather');")
    assert ctx.eval('ouvertes().length') == 2


# ─── Les dispositions enregistrées ───────────────────────────────────────────

def test_une_disposition_MEMORISE_LES_CINQ_band_maps():
    """saveLayout() parcourait les TYPES de panneaux : cinq band maps n'y
    entraient qu'une seule fois, et recharger la disposition n'en rouvrait
    qu'un. Tout l'intérêt d'une disposition multi-écrans disparaissait."""
    ctx = _ctx()
    _ouvrir_cinq_bandes(ctx)
    ctx.eval("saveLayout('3 ecrans');")
    d = json.loads(ctx.eval("localStorage.getItem('rc_layouts')"))
    assert len(d['3 ecrans']['panels']) == 5, d['3 ecrans']['panels']


def test_recharger_la_disposition_rouvre_les_cinq_BONNES_bandes():
    ctx = _ctx()
    bandes = _ouvrir_cinq_bandes(ctx)
    ctx.eval("saveLayout('3 ecrans');")
    ctx.eval("Object.keys(_openWindows).forEach(closePanel);")
    assert ctx.eval('ouvertes().length') == 0
    ctx.eval("loadLayout('3 ecrans');")
    assert ctx.eval('ouvertes().length') == 5
    urls = json.loads(ctx.eval('JSON.stringify(ouvertes().map(function(w){return w.url;}))'))
    for b in bandes:
        assert any('band=' + b in u.replace('%2E', '.') for u in urls), (b, urls)


def test_une_disposition_ENREGISTREE_AVANT_le_correctif_se_recharge_encore():
    """Compatibilité : les anciennes entrées valent `{bandmap: {w,h,x,y}}`,
    sans `id` ni `band`. Elles doivent continuer à s'ouvrir plutôt que d'être
    silencieusement ignorées — c'est la disposition que l'utilisateur a peut-
    être enregistrée il y a des mois."""
    ctx = _ctx()
    ancienne = {'ancienne': {'panels': {
        'coach': {'w': 420, 'h': 620, 'x': 0, 'y': 0},
        'bandmap': {'w': 260, 'h': 640, 'x': 300, 'y': 0},
    }}}
    ctx.eval("_stockage['rc_layouts'] = %s;" % json.dumps(json.dumps(ancienne)))
    ctx.eval("loadLayout('ancienne');")
    assert ctx.eval('ouvertes().length') == 2


# ─── Le compteur affiché dans le menu ────────────────────────────────────────

def test_le_menu_sait_combien_de_band_maps_sont_ouverts():
    ctx = _ctx()
    _ouvrir_cinq_bandes(ctx)
    assert ctx.eval("openInstances('bandmap').length") == 5
    assert ctx.eval("openInstances('coach').length") == 0


def test_fermer_le_type_ferme_TOUTES_ses_fenetres():
    """Le menu affiche « fermer (5) » : s'il n'en fermait qu'une, il en
    resterait quatre à fermer à la main, une par une."""
    ctx = _ctx()
    _ouvrir_cinq_bandes(ctx)
    ctx.eval("openInstances('bandmap').forEach(closePanel);")
    assert ctx.eval('ouvertes().length') == 0


# ─── Le bandscope, même défaut ───────────────────────────────────────────────

def test_le_bandscope_a_UN_NOM_DE_FENETRE_PAR_BANDE():
    """popoutScope() utilisait « rc_scope » en dur : détacher le bandscope sur
    une 2e bande faisait changer de bande le premier au lieu d'en ouvrir un
    second. Surveiller 20 m et 2 m côte à côte était impossible."""
    src = _lire(LOGBOOK_JS)
    bloc = src[src.index('function popoutScope('):]
    bloc = bloc[:bloc.index('\n}')]
    assert "'rc_scope'" not in bloc, 'nom de fenetre fixe : une seule fenetre possible'
    assert "'rc_scope_'" in bloc


def test_le_bandscope_neutralise_le_point_des_bandes_decimales():
    src = _lire(LOGBOOK_JS)
    bloc = src[src.index('function popoutScope('):]
    bloc = bloc[:bloc.index('\n}')]
    assert re.search(r"replace\(/\\\.\/g,\s*'_'\)", bloc), bloc


# ─── Garde-fou du banc d'essai ───────────────────────────────────────────────

def test_LE_FAUX_window_open_REPRODUIT_LA_REGLE_DU_NAVIGATEUR():
    """Tout ce fichier ne vaut que si le stub réutilise bien une fenêtre de
    même nom — sinon chaque appel créerait une fenêtre et les tests ci-dessus
    passeraient même sur le code fautif. On le vérifie explicitement."""
    ctx = _ctx()
    ctx.eval("window.open('/a.html', 'meme_nom');")
    ctx.eval("window.open('/b.html', 'meme_nom');")
    assert ctx.eval('ouvertes().length') == 1
    assert json.loads(ctx.eval('JSON.stringify(ouvertes()[0].url)')) == '/b.html'
    ctx.eval("window.open('/c.html', 'autre_nom');")
    assert ctx.eval('ouvertes().length') == 2


def test_le_bloc_extrait_est_bien_le_vrai_code():
    """Garde-fou du garde-fou : si l'extraction cassait, le contexte JS
    n'exposerait plus openPanel et tous les tests tomberaient en erreur — mais
    une extraction TROP COURTE pourrait passer inaperçue."""
    bloc = _bloc_panneaux(_lire(STATUSBAR))
    for attendu in ('PANEL_DEFAULTS', 'function openPanel(', 'function closePanel(',
                    'function openInstances(', 'function saveLayout(',
                    'function loadLayout(', 'function resetLayout('):
        assert attendu in bloc, attendu
