# -*- coding: utf-8 -*-
"""Trois demandes F4GLD du 28/10/2026, testées sur le VRAI code extrait :

1. Spot FT8 cliqué alors qu'on est en SSB : proposer « Passer en FT8 ? »
   (logx_mode_spot.js) au lieu de laisser le carnet en SSB ; et la bande 30 m
   suivie (radio sur 10,136 MHz, carnet resté sur 40 m).
2. Page CHASSE : DXpéditions (et activations) cliquables -> QSY.
3. CARTE IA lisible : choix des QSO du carnet affichés, masquer les spots
   déjà loggés.
"""
import calendar
import os
import re
import time

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


def _drain(c):
    for _ in range(10):
        c.eval('0')


# ── 1. « Passer en FT8 ? » ───────────────────────────────────────────────────

def _ctx_mode(courant='SSB', rig=True):
    c = py_mini_racer.MiniRacer()
    c.eval("""
      var __el = {innerHTML:'', classList:{_s:{}, add:function(k){this._s[k]=1;}, remove:function(k){delete this._s[k];}},
                  setAttribute:function(){}};
      var document = {getElementById: function(id){ return __cree ? __el : null; },
                      createElement: function(){ __cree = true; return __el; },
                      body: {appendChild: function(){}}};
      var __cree = false;
      function setTimeout(){ return 0; } function clearTimeout(){}
      var __picks = [], __bodies = [], __notes = [];
      var window = {currentMode: %r, rigState: {enabled: %s},
        pickMode: function(m, o){ __picks.push(m + (o && o.fromRig ? ':fromRig' : '')); window.currentMode = m; },
        notify: function(m){ __notes.push(m); }};
      function fetch(u, o){ __bodies.push(JSON.parse(o.body));
        return Promise.resolve({json: function(){ return Promise.resolve({ok:true}); }}); }
    """ % (courant, 'true' if rig else 'false'))
    c.eval(_src('logx_mode_spot.js'))
    return c


@pytest.mark.parametrize('m,attendu', [
    ('FT8', 'FT8'), ('ft4', 'FT4'), ('USB', 'SSB'), ('LSB', 'SSB'), ('CW-R', 'CW'),
    ('PSK31', 'PSK'), ('DIGITAL', ''), ('DATA', ''), ('', ''),
])
def test_normaliser(m, attendu):
    c = _ctx_mode()
    assert c.eval("window.LogxModeSpot.normaliser(%r)" % m) == attendu


def test_pas_de_question_meme_mode_ou_mode_flou():
    c = _ctx_mode('SSB')
    assert c.eval("window.LogxModeSpot.proposer('USB', 7100000, 'EA8XX')") is False
    assert c.eval("window.LogxModeSpot.proposer('DIGITAL', 7065000, 'EA8XX')") is False
    assert c.eval("__cree") is False


def test_question_puis_oui_bascule_carnet_et_radio():
    c = _ctx_mode('SSB')
    assert c.eval("window.LogxModeSpot.proposer('FT8', 10136000, '3D2USU')") is True
    html = c.eval("__el.innerHTML")
    assert 'Passer en FT8' in html and 'Rester en SSB' in html and '3D2USU' in html
    assert c.eval("__el.classList._s.show") == 1
    assert c.eval("__bodies.length") == 0           # rien ne bouge avant le OUI
    c.eval("window.LogxModeSpot.accepter()")
    _drain(c)
    assert c.eval("__picks.join(',')") == 'FT8:fromRig'
    assert c.eval("JSON.stringify(__bodies[0])") == '{"freq_hz":10136000,"mode":"FT8"}'
    assert 'FT8' in c.eval("__notes.join('|')")


def test_oui_sans_cat_change_seulement_le_carnet():
    c = _ctx_mode('SSB', rig=False)
    c.eval("window.LogxModeSpot.proposer('CW', 14025000, 'JA1AA'); window.LogxModeSpot.accepter();")
    _drain(c)
    assert c.eval("__picks.join(',')") == 'CW:fromRig'
    assert c.eval("__bodies.length") == 0


def _ctx_bandmap(question):
    c = py_mini_racer.MiniRacer()
    c.eval("""
      var __bodies = [], __props = [];
      function fetch(u, o){ __bodies.push(JSON.parse(o.body)); return {catch: function(){}}; }
      var __inp = {value:'', focus:function(){}};
      var document = {getElementById: function(){ return __inp; }};
      function onCallInput(){}
      var rigState = {enabled:true};
      var currentMode = 'SSB';
      var window = {LogxModeSpot: {proposer: function(m, f, c){ __props.push(m + '@' + f); return %s; }}};
      var LogxModeSpot = window.LogxModeSpot;
    """ % ('true' if question else 'false'))
    c.eval(_fn(_src('logx_logbook.js'), 'bandmapClick'))
    return c


def test_bandmap_spot_ft8_pose_la_question_et_garde_le_mode_de_saisie():
    c = _ctx_bandmap(True)
    c.eval("bandmapClick('3D2USU', 10.136, 'FT8')")
    assert c.eval("__props.join(',')") == 'FT8@10136000'
    assert c.eval("__bodies[0].mode") == 'SSB'
    assert c.eval("__bodies[0].freq_hz") == 10136000


def test_bandmap_sans_question_garde_le_mode_du_spot():
    c = _ctx_bandmap(False)
    c.eval("bandmapClick('EA8XX', 7.143, 'SSB')")
    assert c.eval("__bodies[0].mode") == 'SSB'


def test_opportunites_transmet_le_mode_annonce_seulement():
    c = py_mini_racer.MiniRacer()
    c.eval("""
      var window = {}; var __hud = {innerHTML:''}; var __props = [];
      window.LogxModeSpot = {proposer: function(m, f, c){ __props.push(m + '@' + f + '@' + c); return true; }};
      var __call = {value:'', focus:function(){}, dispatchEvent:function(){ return true; }};
      var document = {getElementById: function(id){ return id === 'opportunitesCorps' ? __hud : (id === 'inputCall' ? __call : null); }};
      function Event(){} function setInterval(){ return 0; }
      function fetch(){ return Promise.resolve({ok:false, json: function(){ return Promise.resolve({ok:true}); }}); }
    """)
    c.eval(_src('logx_opportunites.js'))
    _drain(c)
    c.eval("""window.LogxOpportunites._rendre([
      {call:'3D2USU', freq:10136, band:'10.1', mode:'FT8', mode_deduit:false, credit_score:900, credit_raison:'r'},
      {call:'EA8XX', freq:7065, band:'7', mode:'DIGITAL', mode_deduit:true, credit_score:800, credit_raison:'r'}], true)""")
    html = c.eval("__hud.innerHTML")
    assert "appeler('3D2USU',10136,'FT8')" in html
    assert "appeler('EA8XX',7065,'')" in html             # mode déduit jamais transmis
    c.eval("window.LogxOpportunites.appeler('3D2USU', 10136, 'FT8')")
    assert c.eval("__props.join(',')") == 'FT8@10136000@3D2USU'


def test_logbook_charge_le_module_avant_opportunites():
    h = _src('logx_logbook.html')
    assert h.index('src="logx_mode_spot.js"') < h.index('src="logx_opportunites.js"')


@pytest.mark.parametrize('khz,bande', [(10136, '10.1'), (18100, '18'), (24915, '24'),
                                       (7100, '7'), (70200, '70')])
def test_bande_radio_suivie_y_compris_warc(khz, bande):
    c = py_mini_racer.MiniRacer()
    c.eval("""var currentBand = '7'; var __picks = [];
              function pickBand(b){ __picks.push(b); currentBand = b; }""")
    c.eval(_fn(_src('logx_hardware_cat.js'), '_rigModeVersLog'))
    c.eval(_fn(_src('logx_hardware_cat.js'), 'syncBandModeFromRig'))
    c.eval("currentBand = 'xx'; syncBandModeFromRig(%d, '')" % khz)
    assert c.eval("currentBand") == bande


# ── 2. CHASSE : DXpéditions et activations cliquables ────────────────────────

def _ctx_panneaux():
    c = py_mini_racer.MiniRacer()
    c.eval("var window = {};")
    c.eval(_src('logx_chasse_panneaux.js'))
    return c


def test_dxpedition_active_spottee_a_un_bouton_qsy_avec_son_mode():
    c = _ctx_panneaux()
    html = c.eval("""window.LogxChassePanneaux.renderDxRows([
      {callsign:'C5R', status:'active', freq_khz:14075, spot_mode:'FT8', entity:'Gambia'},
      {callsign:'XX0X', status:'upcoming', entity:'Nowhere'}])""")
    assert "qsyTo(14075,'C5R','FT8')" in html
    assert html.count('qsy-btn') == 1                     # pas de fréquence -> pas de bouton


def test_activation_a_un_bouton_qsy():
    c = _ctx_panneaux()
    html = c.eval("""window.LogxChassePanneaux.renderActivationRows([
      {call:'F4ABC', band:'7', freq:7150.5, mode:'SSB', reference:'FR-0001'}], {programme:'POTA'})""")
    assert "qsyTo(7150.5,'F4ABC','SSB')" in html


def test_needlist_ne_transmet_pas_un_mode_deduit():
    c = _ctx_panneaux()
    html = c.eval("""window.LogxChassePanneaux.renderNeedList([
      {call:'EA8XX', band:'7', freq:7065, mode:'DIGITAL', mode_deduit:true}], {rigEnabled:true})""")
    assert "qsyTo(7065,'EA8XX','')" in html


def test_qsyto_envoie_hertz_et_mode_et_affiche_le_resultat():
    c = py_mini_racer.MiniRacer()
    c.eval("""
      var __bodies = [], __t = null;
      var document = {getElementById: function(id){ return id === 'xotaToast' ? __t : null; },
        createElement: function(){ __t = {id:'', className:'', textContent:'', setAttribute:function(){}}; return __t; },
        body: {appendChild: function(){}}};
      function setTimeout(){ return 0; } function clearTimeout(){}
      var __rep = {ok:false, error:'Port série non configuré'};
      function fetch(u, o){ __bodies.push(JSON.parse(o.body));
        return Promise.resolve({json: function(){ return Promise.resolve(__rep); }}); }
    """)
    src = _src('logx_accueil.js')
    c.eval(_fn(src, '_afficherStatutQsy'))
    c.eval(_fn(src, 'qsyTo'))
    c.eval("qsyTo(14075.5, 'C5R', 'FT8')")
    _drain(c)
    assert c.eval("JSON.stringify(__bodies[0])") == '{"freq_hz":14075500,"mode":"FT8"}'
    assert 'Port série non configuré' in c.eval("__t.textContent")
    assert 'err' in c.eval("__t.className")


# ── 3. CARTE IA lisible ──────────────────────────────────────────────────────

def _ctx_carte(stock='null'):
    c = py_mini_racer.MiniRacer()
    c.eval("""var __st = {'logx_carte_affichage': %s};
              var localStorage = {getItem: function(k){ return __st[k] === undefined ? null : __st[k]; },
                                  setItem: function(k, v){ __st[k] = v; }};""" % (
        stock if stock == 'null' else repr(stock)))
    src = _src('logx_carte.html')
    debut = src.index("const _AFF_CLE = 'logx_carte_affichage';")
    fin = src.index('let _derniersSpotsCarte')
    c.eval(src[debut:fin])
    return c


def _ms(y, mo, d, h=0, mi=0):
    return calendar.timegm((y, mo, d, h, mi, 0)) * 1000


def test_carte_defaut_24h_et_valeur_stockee_invalide():
    c = _ctx_carte()
    assert c.eval("_affichageCarte().qso") == '24h'
    assert c.eval("_affichageCarte().spots") is True
    c = _ctx_carte('{"qso":"n_importe","masquerFaits":true}')
    assert c.eval("_affichageCarte().qso") == '24h'
    assert c.eval("_affichageCarte().masquerFaits") is True


def test_carte_filtre_qso_par_periode_et_formats_de_date():
    c = _ctx_carte()
    maintenant = _ms(2026, 10, 28, 7, 0)
    c.eval("""var Q = [{call:'A', date:'20261028', time:'0600'},
                       {call:'B', date:'2026-10-27', time:'08:00'},
                       {call:'F', date:'20261027', time:'0300'},
                       {call:'C', date:'20261025', time:'0800'},
                       {call:'D', date:'20261001', time:'1200'},
                       {call:'E', date:'', time:''}];""")
    def calls(choix):
        return c.eval("filtrerQsoAffiches(Q, %r, %d).map(function(q){return q.call;}).join('')" % (choix, maintenant))
    assert calls('24h') == 'AB'          # F (-28 h) exclu
    assert calls('48h') == 'ABF'
    assert calls('7j') == 'ABFC'
    assert calls('tous') == 'ABFCDE'
    assert calls('aucun') == ''


def test_carte_masquer_spots_deja_logges():
    c = _ctx_carte()
    c.eval("var S = [{call:'X', done:true}, {call:'Y', done:false}];")
    assert c.eval("filtrerSpotsAffiches(S, {spots:true, masquerFaits:true}).length") == 1
    assert c.eval("filtrerSpotsAffiches(S, {spots:true, masquerFaits:false}).length") == 2
    assert c.eval("filtrerSpotsAffiches(S, {spots:false, masquerFaits:false}).length") == 0


def test_carte_cablage():
    s = _sans_commentaires_js(_src('logx_carte.html'))
    m = re.search(r'<div id="affichageControl"([^>]*)>', s)
    assert m and 'expert-only' not in m.group(1)            # jamais caché en mode simple
    for ident in ('affSpots', 'affMasquerFaits', 'affQso'):
        assert re.search(r'id="%s"[^>]*onchange="majAffichageCarte\(\)"' % ident, s), ident
    corps = _fn(s, 'updateMapStations')
    assert re.search(r'stns\s*=\s*filtrerSpotsAffiches\(_derniersSpotsCarte,\s*_affichageCarte\(\)\)', corps)
    corps = _fn(s, 'drawLoggedQSOs')
    assert re.search(r'const qsoLog = filtrerQsoAffiches\(tousQso, _affichageCarte\(\)\.qso, Date\.now\(\)\)', corps)
