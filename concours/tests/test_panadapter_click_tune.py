# -*- coding: utf-8 -*-
"""Panadapter : click-to-tune sur le spectre/waterfall — QSY sur N'IMPORTE
QUEL signal vu, pas seulement les spots cluster (fonction phare d'un
panadapter, absente jusqu'ici : seuls les marqueurs de spots etaient
cliquables).

- freqAuClic(frac, plage) : mapping PUR x(0..1) -> Hz, inversion-safe (hzW peut
  etre < hz0 en LSB). Extrait du fichier LIVRE et execute en V8 reel (meme
  patron que test_panadapter_spots_overlay.py) : jamais recopie.
- Cablage : specCanvas ET waterCanvas QSY via plageHzActuelle()+freqAuClic,
  seulement si une vraie plage RF existe, et SANS toucher l'indicatif saisi
  (contrairement au clic sur un spot).
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


def _extraire(nom):
    """Extrait le corps d'une fonction indentee 2 espaces dans l'IIFE."""
    src = _lire()
    m = re.search(r'  function %s\(.*?\n  \}' % re.escape(nom), src, re.S)
    assert m, '%s introuvable' % nom
    return m.group(0).strip()


# ─── freqAuClic() : mapping pur, teste en V8 reel ──────────────────────────

def _ctx():
    ctx = py_mini_racer.MiniRacer()
    ctx.eval(_extraire('freqAuClic'))
    return ctx


def test_mapping_usb_croissant():
    ctx = _ctx()
    # USB : hz0=14195000 (x=0), hzW=14198000 (x=1) — axe croissant
    assert ctx.eval("freqAuClic(0, {hz0:14195000, hzW:14198000})") == 14195000
    assert ctx.eval("freqAuClic(0.5, {hz0:14195000, hzW:14198000})") == 14196500
    assert ctx.eval("freqAuClic(1, {hz0:14195000, hzW:14198000})") == 14198000


def test_mapping_lsb_inverse():
    ctx = _ctx()
    # LSB : hz0=7130000 (x=0), hzW=7127000 (x=1) — axe DECROISSANT (inversion)
    assert ctx.eval("freqAuClic(0, {hz0:7130000, hzW:7127000})") == 7130000
    assert ctx.eval("freqAuClic(0.5, {hz0:7130000, hzW:7127000})") == 7128500
    assert ctx.eval("freqAuClic(1, {hz0:7130000, hzW:7127000})") == 7127000


# ─── Cablage : les deux canvas QSY, sans toucher l'indicatif ───────────────

def test_les_deux_canvas_sont_cliquables():
    src = _lire()
    assert "clicCanvas(e, _specCv)" in src, 'clic specCanvas non cable'
    assert "clicCanvas(e, _waterCv)" in src, 'clic waterCanvas non cable'


def test_clic_canvas_qsy_via_plage_et_freq_au_clic():
    corps = _extraire('clicCanvas')
    assert 'plageHzActuelle()' in corps          # la vraie plage RF de l'axe
    assert 'freqAuClic(' in corps                # le mapping x->Hz
    assert 'qsyHz(' in corps                     # QSY reel
    # early-return si aucune plage RF absolue (pas de QSY accidentel en audio brut)
    assert re.search(r'if\(!plage\)\s*return', corps), 'garde plage null absente'
    # NE touche PAS l'indicatif (contrairement au clic-spot)
    assert 'prefill_call' not in corps and 'BroadcastChannel' not in corps


def test_qsy_hz_poste_bien_rig_qsy():
    corps = _extraire('qsyHz')
    assert "/rig/qsy" in corps and 'freq_khz' in corps


def test_clic_spot_utilise_toujours_qsy_hz():
    # le clic sur un spot QSY par le meme helper + pre-remplit l'indicatif
    corps = _extraire('clicSpotOverlay')
    assert 'qsyHz(' in corps
    assert 'prefill_call' in corps
