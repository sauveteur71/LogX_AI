# -*- coding: utf-8 -*-
"""Écran « Santé de la station » (logx_diagnostic.js) — testé en V8.

Les états viennent d'endpoints EXISTANTS (/hardware/state, /data/network_status,
/tx/audit, /dxcc/status) — lecture seule. Ici on teste la couche présentation :
construireTuiles() traduit ces états bruts en tuiles {id, couleur, detail}, et
_rendre() produit un HTML XSS-safe. Aucun démarrage auto dans le harnais.
"""
import os

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS = os.path.join(CONCOURS, 'logx_diagnostic.js')
py_mini_racer = pytest.importorskip('py_mini_racer')


def _ctx():
    ctx = py_mini_racer.MiniRacer()
    ctx.eval("""
      var window = {};
      var __c = { innerHTML: '' };
      var document = { getElementById: function(id){ return id === 'diagTuiles' ? __c : null; } };
    """)
    with open(JS, encoding='utf-8') as f:
        ctx.eval(f.read())
    return ctx


_DATA_OK = """{
  hardware: {rig:{enabled:true, ok:true, freq_khz:14074, mode:'USB'},
             rotor:{enabled:false}, wsjtx:{enabled:true, connected:true}},
  network:  {callbook:{open:false, wait_s:0}, cloudsync:{enabled:true, last_error:null},
             mysql_sync:{enabled:false}},
  tx:       {tx_locked:false},
  dxcc:     {available:true}
}"""


def _couleur(ctx, tid):
    return ctx.eval(
        "(function(){var t=window.LogxDiagnostic.construireTuiles(%s);"
        "for(var i=0;i<t.length;i++){if(t[i].id==='%s')return t[i].couleur;}return null;})()"
        % (_DATA_OK, tid))


def test_radio_verte_si_cat_repond():
    ctx = _ctx()
    assert _couleur(ctx, 'radio') == 'green'


def test_radio_rouge_si_activee_mais_muette():
    ctx = _ctx()
    c = ctx.eval("window.LogxDiagnostic.construireTuiles({hardware:{rig:{enabled:true, ok:false}}}).filter(function(t){return t.id==='radio';})[0].couleur")
    assert c == 'red'


def test_radio_muette_si_non_configuree():
    ctx = _ctx()
    c = ctx.eval("window.LogxDiagnostic.construireTuiles({hardware:{rig:{enabled:false}}}).filter(function(t){return t.id==='radio';})[0].couleur")
    assert c == 'muted'


def test_ft8_jaune_si_active_sans_decodage():
    ctx = _ctx()
    c = ctx.eval("window.LogxDiagnostic.construireTuiles({hardware:{wsjtx:{enabled:true, connected:false}}}).filter(function(t){return t.id==='ft8';})[0].couleur")
    assert c == 'yellow'


def test_tx_rouge_si_verrouille():
    ctx = _ctx()
    c = ctx.eval("window.LogxDiagnostic.construireTuiles({tx:{tx_locked:true}}).filter(function(t){return t.id==='tx';})[0].couleur")
    assert c == 'red'


def test_dxcc_rouge_si_indisponible():
    ctx = _ctx()
    c = ctx.eval("window.LogxDiagnostic.construireTuiles({dxcc:{available:false}}).filter(function(t){return t.id==='dxcc';})[0].couleur")
    assert c == 'red'


def test_callbook_jaune_si_disjoncteur_ouvert():
    ctx = _ctx()
    c = ctx.eval("window.LogxDiagnostic.construireTuiles({network:{callbook:{open:true, wait_s:30}}}).filter(function(t){return t.id==='callbook';})[0].couleur")
    assert c == 'yellow'


def test_rendre_produit_les_tuiles_et_echappe():
    ctx = _ctx()
    ctx.eval("window.LogxDiagnostic._rendre(window.LogxDiagnostic.construireTuiles(%s));" % _DATA_OK)
    html = ctx.eval("__c.innerHTML")
    assert 'diag-tuile' in html and 'diag-dot' in html
    # détail radio (fréquence) présent
    assert '14074' in html


def test_rendre_echappe_le_detail_xss():
    ctx = _ctx()
    ctx.eval("window.LogxDiagnostic._rendre([{id:'x', nom:'X', couleur:'green', detail:'<img src=x onerror=1>'}]);")
    html = ctx.eval("__c.innerHTML")
    assert '<img' not in html and '&lt;img' in html


def test_cablage_page():
    with open(os.path.join(CONCOURS, 'logx_diagnostic.html'), encoding='utf-8') as f:
        h = f.read()
    assert 'src="logx_diagnostic.js"' in h
    assert 'id="diagTuiles"' in h
    assert 'logx_theme.css' in h            # tokens mutualisés
    assert 'logx_statusbar.js' in h         # barre de statut + expert-only
