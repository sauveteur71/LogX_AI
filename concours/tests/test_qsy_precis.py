# -*- coding: utf-8 -*-
"""QSY précis et saisie d'indicatif fluide (F4GLD, 28/10/2026).

1. Clic band map sur un spot à 7143,5 kHz : la radio se calait sur 7143
   (Math.round(mhz*1000)) — 500 Hz à côté en SSB.
2. Clic sur une station phonie à 7,06x : le mode DÉDUIT du plan de bande
   (« DIGITAL ») commandait la radio, l'IC-7300 passait en USB-DATA.
3. Indicatif saisi en commençant par la fin (« OQU » puis « F4 » au début) :
   la réécriture en majuscules renvoyait le curseur en fin de champ.
4. CARTE IA : cliquer une station doit permettre de caler la radio dessus.

Les fonctions testées sont EXTRAITES des sources (pas réimplémentées) ; les
propriétés tenues par du HTML généré sont vérifiées sur la STRUCTURE du code,
commentaires retirés.
"""
import os
import re

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
py_mini_racer = pytest.importorskip('py_mini_racer')


def _src(nom):
    with open(os.path.join(CONCOURS, nom), encoding='utf-8') as f:
        return f.read()


def _sans_commentaires_js(s):
    s = re.sub(r'/\*.*?\*/', '', s, flags=re.S)
    return re.sub(r'(?m)(^|[^:\'"\\])//.*$', r'\1', s)


def _fn(src, nom):
    m = re.search(r'\n\s*(async\s+)?function ' + re.escape(nom) + r'\s*\(', src)
    assert m, 'fonction %s introuvable' % nom
    i = src.index('function', m.start())
    j = src.index('{', i)
    prof = 0
    for k in range(j, len(src)):
        if src[k] == '{':
            prof += 1
        elif src[k] == '}':
            prof -= 1
            if prof == 0:
                return ('async ' if m.group(1) else '') + src[i:k + 1]
    raise AssertionError('accolade fermante introuvable')


# ── 1 + 2 : bandmapClick ─────────────────────────────────────────────────────

def _ctx_bandmap():
    c = py_mini_racer.MiniRacer()
    c.eval("""
      var __bodies = [];
      function fetch(u, o){ __bodies.push(JSON.parse(o.body)); return {catch: function(){}}; }
      var __inp = {value:'', focus:function(){}};
      var document = {getElementById: function(){ return __inp; }};
      function onCallInput(){}
      var rigState = {enabled:true};
      var currentMode = 'SSB';
      var window = {};   // page réelle : LogxModeSpot absent ici -> pas de question
    """)
    c.eval(_fn(_src('logx_logbook.js'), 'bandmapClick'))
    return c


def test_bandmap_qsy_au_hertz_pres():
    c = _ctx_bandmap()
    c.eval("bandmapClick('EA8XX', 7.1435, '')")
    corps = c.eval("JSON.stringify(__bodies[0])")
    assert '"freq_hz":7143500' in corps, corps


def test_bandmap_mode_vide_retombe_sur_le_mode_de_saisie():
    c = _ctx_bandmap()
    c.eval("bandmapClick('EA8XX', 7.065, '')")
    assert c.eval("__bodies[0].mode") == 'SSB'


def test_mode_deduit_jamais_envoye_a_la_radio_depuis_la_liste():
    s = _sans_commentaires_js(_src('logx_filtre_spots.js'))
    assert re.search(r"const\s+modeQsy\s*=\s*s\.mode_deduit\s*\?\s*''\s*:\s*modeSpot", s)
    assert re.search(r"onclick=\"bandmapClick\('\$\{jsCall\}',\$\{f\},'\$\{modeQsy\}'\)\"", s)


def test_mode_deduit_jamais_envoye_depuis_bandscope_et_navigation():
    s = _sans_commentaires_js(_src('logx_bandscope_waterfall.js'))
    assert re.search(r"const\s+safeMode\s*=\s*s\.mode_deduit\s*\?\s*''\s*:", s)
    s = _sans_commentaires_js(_src('logx_bandmap_sp.js'))
    assert re.search(r"bandmapClick\([^;]*cible\.mode_deduit\s*\?\s*''\s*:", s, re.S)


def test_serveur_signale_le_mode_deduit():
    s = _src('logx_http.py')
    bloc = s[s.index("if path == '/data/spots_ranked':"):]
    bloc = bloc[:bloc.index("self._json({'spots': visibles")]
    assert re.search(r"'mode_deduit':\s*not\s+s\.get\('mode'\)", bloc)


def test_panadapter_qsy_en_hertz():
    s = _sans_commentaires_js(_src('logx_panadapter.html'))
    corps = _fn(s, 'qsyHz')
    assert 'freq_hz: Math.round(freqHz)' in corps
    assert 'freqHz/1000' not in corps


# ── 3 : curseur de l'indicatif ───────────────────────────────────────────────

def test_majuscules_sans_deplacer_le_curseur():
    c = py_mini_racer.MiniRacer()
    # Champ FIDÈLE au point mesuré dans Chromium : réécrire .value renvoie le
    # curseur en fin de champ (vérifié en navigateur réel le 28/10/2026 :
    # « FOQU4 » avant correctif, « F4OQU » après).
    c.eval("""
      var __inp = {_v:'fOQU', selectionStart:1, selectionEnd:1,
        setSelectionRange: function(a, b){ this.selectionStart = a; this.selectionEnd = b; }};
      Object.defineProperty(__inp, 'value', {
        get: function(){ return this._v; },
        set: function(v){ this._v = v; this.selectionStart = this.selectionEnd = v.length; }});
      var document = {getElementById: function(){ return __inp; }};
    """)
    c.eval(_fn(_src('logx_logbook.js'), 'onCallInput'))
    # La suite de la fonction appelle des dizaines de services de la page :
    # seule compte la réécriture, faite en tête.
    c.eval("try{ onCallInput(); }catch(e){}")
    assert c.eval("__inp.value") == 'FOQU'
    assert c.eval("__inp.selectionStart") == 1


# ── 4 : CARTE IA, QSY depuis l'infobulle ─────────────────────────────────────

def _ctx_carte(rep):
    c = py_mini_racer.MiniRacer()
    c.eval("""
      var __bodies = [], __bc = [];
      var __box = {textContent:'', style:{}};
      var document = {getElementById: function(id){ return id === 'ttQsy' ? __box : null; }};
      var __rep = %s;
      function fetch(u, o){ __bodies.push(JSON.parse(o.body));
        return Promise.resolve({json: function(){ return Promise.resolve(__rep); }}); }
      function BroadcastChannel(n){ this.postMessage = function(m){ __bc.push(m); }; this.close = function(){}; }
      var lastTooltipSpot = null;
    """ % rep)
    c.eval(_fn(_src('logx_carte.html'), 'qsyDepuisCarte'))
    return c


def _drain(c):
    for _ in range(10):
        c.eval('0')


def test_carte_qsy_freq_exacte_mode_annonce_et_indicatif():
    c = _ctx_carte("{ok:true}")
    c.eval("lastTooltipSpot = {call:'EA8XX', freq:7143.5, mode:'CW', mode_deduit:false}; qsyDepuisCarte();")
    _drain(c)
    assert c.eval("__bodies[0].freq_hz") == 7143500
    assert c.eval("__bodies[0].mode") == 'CW'
    assert c.eval("__bc[0].type") == 'prefill_call' and c.eval("__bc[0].data.call") == 'EA8XX'
    assert '7143.5' in c.eval("__box.textContent")


def test_carte_qsy_n_envoie_pas_un_mode_deduit():
    c = _ctx_carte("{ok:true}")
    c.eval("lastTooltipSpot = {call:'EA8XX', freq:7065, mode:'DIGITAL', mode_deduit:true}; qsyDepuisCarte();")
    _drain(c)
    assert c.eval("__bodies[0].mode === undefined") is True


def test_carte_qsy_affiche_l_erreur():
    c = _ctx_carte("{ok:false, error:'Port série non configuré'}")
    c.eval("lastTooltipSpot = {call:'EA8XX', freq:7065}; qsyDepuisCarte();")
    _drain(c)
    assert 'Port série non configuré' in c.eval("__box.textContent")


def test_carte_cablage_bouton_et_mode_transmis():
    s = _sans_commentaires_js(_src('logx_carte.html'))
    assert re.search(r'id="ttQsyBtn"[^>]*onclick="qsyDepuisCarte\(\)"', s, re.S)
    corps = _fn(s, 'refreshRankedStations')
    assert re.search(r'mode_deduit:\s*s\.mode_deduit', corps)
