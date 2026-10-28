# -*- coding: utf-8 -*-
"""« ▶ Appeler » ne déplace pas la radio alors que le CAT se dit actif
(F4GLD, 28/10/2026, IC-7300 en CAT natif).

Cause mesurée sur sa config : cat_enabled=True mais cat_port=''. Trois défauts
enchaînés, chacun contraint ici sur le VRAI code (fonctions extraites des
sources, pas réimplémentées) :

1. refreshCatPorts()/refreshCatPttPorts() (CONFIG) perdaient le port enregistré
   quand il était absent de la liste (radio éteinte à l'ouverture de CONFIG) ;
   le <select> tombait sur une valeur vide et ENREGISTRER écrivait cat_port=''.
2. appeler() (HUD Opportunités) jetait la réponse de /rig/qsy : l'erreur
   « Port série non configuré » ne s'affichait nulle part.
3. applyRigState() affichait « rigctld injoignable » en dur au lieu de la cause
   renvoyée par le serveur (faux en CAT natif).
+ libellé de bande du HUD : la clé MHz était suffixée « m » (« 7 m »).
"""
import os
import re

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
py_mini_racer = pytest.importorskip('py_mini_racer')


def _src(nom):
    with open(os.path.join(CONCOURS, nom), encoding='utf-8') as f:
        return f.read()


def _fn(src, nom):
    m = re.search(r'\n\s*(async\s+)?function ' + re.escape(nom) + r'\s*\(', src)
    assert m, 'fonction %s introuvable' % nom
    prefix = 'async ' if m.group(1) else ''
    i = src.index('function', m.start())
    j = src.index('{', i)
    prof = 0
    for k in range(j, len(src)):
        if src[k] == '{':
            prof += 1
        elif src[k] == '}':
            prof -= 1
            if prof == 0:
                return prefix + src[i:k + 1]
    raise AssertionError('accolade fermante introuvable')


def _drain(c):
    for _ in range(10):
        c.eval("0")


# <select> minimal mais FIDÈLE sur le point qui compte : poser .value sur une
# valeur absente des <option> laisse la valeur vide (comportement navigateur).
_SELECT = r"""
function FauxSelect(){ this._html = ''; this._v = ''; }
Object.defineProperty(FauxSelect.prototype, 'innerHTML', {
  get: function(){ return this._html; },
  set: function(h){ this._html = h; var m = /<option value="([^"]*)"/.exec(h); this._v = m ? m[1] : ''; }
});
Object.defineProperty(FauxSelect.prototype, 'value', {
  get: function(){ return this._v; },
  set: function(v){
    var re = /<option value="([^"]*)"/g, m, vals = [];
    while((m = re.exec(this._html))) vals.push(m[1]);
    this._v = vals.indexOf(v) >= 0 ? v : '';
  }
});
"""


def _ctx_ports(fonction, ports, port_enregistre, ok=True):
    c = py_mini_racer.MiniRacer()
    c.eval(_SELECT)
    c.eval("""
      var __sel = new FauxSelect();
      var window = {_cfgRestauree: {cat_port: %(p)r, cat_ptt_port: %(p)r}};
      var document = {getElementById: function(id){ return __sel; }};
      function escC(s){ return String(s); }
      var __ok = %(ok)s;
      function fetch(u){
        if(!__ok) return Promise.reject(new Error('down'));
        return Promise.resolve({json: function(){ return Promise.resolve({ports: %(ports)s}); }});
      }
    """ % {'p': port_enregistre, 'ports': ports, 'ok': 'true' if ok else 'false'})
    c.eval(_fn(_src('logx_configuration.js'), fonction))
    return c


@pytest.mark.parametrize('ports', ['[]', '[{device:"COM3", description:"BT"}]'])
def test_port_cat_enregistre_absent_reste_choisi(ports):
    c = _ctx_ports('refreshCatPorts', ports, 'COM20')
    c.eval("refreshCatPorts()")
    _drain(c)
    assert c.eval("__sel.value") == 'COM20'
    assert 'non détecté' in c.eval("__sel.innerHTML")


def test_port_cat_present_reste_choisi_sans_doublon():
    c = _ctx_ports('refreshCatPorts', '[{device:"COM3"},{device:"COM20"}]', 'COM20')
    c.eval("refreshCatPorts()")
    _drain(c)
    assert c.eval("__sel.value") == 'COM20'
    assert c.eval("__sel.innerHTML").count('value="COM20"') == 1


def test_port_cat_garde_si_serveur_injoignable():
    c = _ctx_ports('refreshCatPorts', '[]', 'COM20', ok=False)
    c.eval("refreshCatPorts()")
    _drain(c)
    assert c.eval("__sel.value") == 'COM20'


def test_sans_port_enregistre_ni_detecte_reste_vide():
    c = _ctx_ports('refreshCatPorts', '[]', '')
    c.eval("refreshCatPorts()")
    _drain(c)
    assert c.eval("__sel.value") == ''
    assert 'Aucun port détecté' in c.eval("__sel.innerHTML")


def test_port_ptt_enregistre_absent_reste_choisi():
    c = _ctx_ports('refreshCatPttPorts', '[]', 'COM7')
    c.eval("refreshCatPttPorts()")
    _drain(c)
    assert c.eval("__sel.value") == 'COM7'


# ── appeler() : le résultat du QSY doit être VISIBLE ─────────────────────────

def _ctx_opp(reponse_qsy):
    c = py_mini_racer.MiniRacer()
    c.eval("""
      var window = {};
      var __notes = [];
      window.notify = function(m){ __notes.push(String(m)); };
      var __call = {value:'', focus:function(){}, dispatchEvent:function(){ return true; }};
      var __hud = {innerHTML:''};
      var document = {getElementById: function(id){
        return id === 'inputCall' ? __call : (id === 'opportunitesCorps' ? __hud : null); }};
      function Event(t){ this.type = t; }
      function setInterval(){ return 0; }
      var __rep = %s;
      var __qsy = [];
      function fetch(u, o){
        if(u === '/rig/qsy'){ __qsy.push(o.body);
          return Promise.resolve({status: 400, json: function(){ return Promise.resolve(__rep); }}); }
        return Promise.resolve({ok: false, json: function(){ return Promise.resolve(null); }});
      }
    """ % reponse_qsy)
    c.eval(_src('logx_opportunites.js'))
    _drain(c)
    c.eval("window.LogxOpportunites._rendre([], true)")   # CAT activé
    return c


def test_appeler_affiche_l_erreur_du_serveur():
    c = _ctx_opp("{ok:false, error:'Port série non configuré'}")
    c.eval("window.LogxOpportunites.appeler('EA8XX', 7123.5)")
    _drain(c)
    assert c.eval("__call.value") == 'EA8XX'
    notes = c.eval("__notes.join('|')")
    assert 'Port série non configuré' in notes and 'impossible' in notes


def test_appeler_confirme_le_qsy_reussi():
    c = _ctx_opp("{ok:true}")
    c.eval("window.LogxOpportunites.appeler('EA8XX', 7123.5)")
    _drain(c)
    assert '7123.5' in c.eval("JSON.parse(__qsy[0]).freq_khz + ''")
    notes = c.eval("__notes.join('|')")
    assert '7123.5' in notes and 'impossible' not in notes


# ── libellé de bande du HUD ──────────────────────────────────────────────────

def test_bande_du_hud_en_longueur_d_onde_reelle():
    c = _ctx_opp("{ok:true}")
    c.eval("var BAND_LABELS = {'7':'40m','3.5':'80m'};")
    c.eval("""window.LogxOpportunites._rendre([{call:'EA8XX', freq:7123, band:'7',
             mode:'SSB', dx_country:'Canary Is.', credit_classe:'new_band',
             credit_score:600, credit_raison:'r'}], true)""")
    html = c.eval("__hud.innerHTML")
    assert '40m' in html and '7 m' not in html


def test_bande_inconnue_montree_en_mhz_pas_en_metres():
    c = _ctx_opp("{ok:true}")
    c.eval("""window.LogxOpportunites._rendre([{call:'EA8XX', freq:3700, band:'3.5',
             mode:'SSB', dx_country:'X', credit_classe:'new_band',
             credit_score:600, credit_raison:'r'}], true)""")
    html = c.eval("__hud.innerHTML")
    assert '3.5 MHz' in html and '3.5 m' not in html


# ── applyRigState : la vraie cause, pas « rigctld injoignable » ──────────────

def test_etat_rig_affiche_la_cause_serveur():
    c = py_mini_racer.MiniRacer()
    c.eval("""
      var __el = {};
      function el(id){ if(!__el[id]) __el[id] = {textContent:'', style:{}, title:'',
          classList:{add:function(){}, remove:function(){}}, setAttribute:function(){}};
        return __el[id]; }
      var document = {getElementById: el};
      var rigState = {enabled:false, mode:'', freq_khz:0};
    """)
    c.eval(_fn(_src('logx_hardware_cat.js'), 'applyRigState'))
    c.eval("applyRigState({enabled:true, ok:false, error:'Port série non configuré'})")
    assert 'Port série non configuré' in c.eval("__el.rigFreq.textContent")
