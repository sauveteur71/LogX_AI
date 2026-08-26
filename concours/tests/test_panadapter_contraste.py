# -*- coding: utf-8 -*-
"""Panadapter : contraste réglable (waterfall relative vs calibrée), reco F4GLD.
Les 3 sources (audio/CI-V/TCI) produisent du 0-255 -> un remap CLIENT commun
suffit. Fonctions extraites du fichier LIVRÉ et exécutées en V8 réel.

- remapContraste(v, lo, hi) : PUR, remappe [lo,hi] -> [0,255], clampé ; hi<=lo
  renvoie v (garde-fou division par zéro).
- bornesContraste(arr) : relatif -> [min,max] de la trame ; calibré -> plancher/
  plafond fixes.
"""
import os
import re

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PANADAPTER = os.path.join(CONCOURS, 'logx_panadapter.html')
py_mini_racer = pytest.importorskip('py_mini_racer')


def _lire():
    with open(PANADAPTER, encoding='utf-8') as f:
        return f.read()


def _bloc_contraste():
    src = _lire()
    i = src.index('let contrasteMode =')
    j = src.index('function binsAffiches(')
    bloc = src[i:j]
    assert 'function remapContraste' in bloc and 'function bornesContraste' in bloc
    return bloc


_STUB = "var _ls={}; var localStorage={getItem:function(k){return _ls[k]||null;}," \
        "setItem:function(k,v){_ls[k]=String(v);}};\n"


def _ctx():
    ctx = py_mini_racer.MiniRacer()
    ctx.eval(_STUB)
    ctx.eval(_bloc_contraste())
    return ctx


# ─── remapContraste : pur ──────────────────────────────────────────────────

def test_remap_lineaire_et_bornes():
    ctx = _ctx()
    assert ctx.eval("remapContraste(0, 0, 255)") == 0
    assert ctx.eval("remapContraste(255, 0, 255)") == 255
    assert ctx.eval("remapContraste(128, 0, 256)") == 128        # ~milieu
    # [40,230] : 40 -> 0, 230 -> 255, 135 (milieu) -> ~128
    assert ctx.eval("remapContraste(40, 40, 230)") == 0
    assert ctx.eval("remapContraste(230, 40, 230)") == 255
    assert ctx.eval("remapContraste(135, 40, 230)") == 128


def test_remap_clampe():
    ctx = _ctx()
    assert ctx.eval("remapContraste(10, 40, 230)") == 0          # sous plancher -> 0
    assert ctx.eval("remapContraste(250, 40, 230)") == 255       # au-dessus plafond -> 255


def test_remap_degenere_hi_le_lo_renvoie_v():
    ctx = _ctx()
    assert ctx.eval("remapContraste(77, 100, 100)") == 77        # évite /0
    assert ctx.eval("remapContraste(77, 200, 100)") == 77


# ─── bornesContraste : relatif vs calibré ──────────────────────────────────

def test_bornes_relatif_min_max_de_la_trame():
    ctx = _ctx()
    ctx.eval("contrasteMode='relatif';")
    assert ctx.eval("JSON.stringify(bornesContraste([10,20,200,50]))") == '[10,200]'


def test_bornes_relatif_garantit_hi_sup_lo():
    ctx = _ctx()
    ctx.eval("contrasteMode='relatif';")
    # trame plate -> hi forcé à lo+1 (jamais hi<=lo)
    assert ctx.eval("JSON.stringify(bornesContraste([80,80,80]))") == '[80,81]'


def test_bornes_relatif_borne_aux_bins_affiches():
    # En audio, dataArray porte TOUTE la FFT mais seuls nBinsActuel() bins sont
    # affichés. Le contraste auto doit se baser sur les bins VISIBLES : une
    # porteuse forte hors span (ici 200 au 3e bin) ne doit pas assombrir le
    # spectre visible. n=2 -> min/max sur [10,20] seulement.
    ctx = _ctx()
    ctx.eval("contrasteMode='relatif';")
    assert ctx.eval("JSON.stringify(bornesContraste([10,20,200,50], 2))") == '[10,20]'
    # n absent/0 -> compat : scan complet (CI-V/TCI affichent tout le tableau)
    assert ctx.eval("JSON.stringify(bornesContraste([10,20,200,50]))") == '[10,200]'
    assert ctx.eval("JSON.stringify(bornesContraste([10,20,200,50], 0))") == '[10,200]'


def test_bornes_calibre_valeurs_fixes():
    ctx = _ctx()
    ctx.eval("contrasteMode='calibre'; contrasteFloor=40; contrasteCeil=230;")
    assert ctx.eval("JSON.stringify(bornesContraste([10,20,200,50]))") == '[40,230]'


# ─── Câblage : le rendu applique le contraste ──────────────────────────────

def test_rendu_applique_le_contraste():
    src = _lire()
    m = re.search(r'function dessinerSpectre\(.*?\n  \}', src, re.S)
    assert m and 'remapContraste(dataArray[bin]' in m.group(0) and 'bornesContraste(dataArray, nBins)' in m.group(0)
    w = re.search(r'function dessinerWaterfall\(.*?\n  \}', src, re.S)
    assert w and 'remapContraste(dataArray[bin]' in w.group(0) and 'bornesContraste(dataArray, nBins)' in w.group(0)


def test_controle_ui_present():
    src = _lire()
    assert 'id="paContraste"' in src and 'id="paFloor"' in src and 'id="paCeil"' in src
