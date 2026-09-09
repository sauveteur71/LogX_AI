# -*- coding: utf-8 -*-
"""Sélecteur de bandes du LOGBOOK pour l'activité « activation portable »
(A3, id d'activité `iota_pota`).

Même principe que l'activité V/UHF (test_logbook_band_picker_vuhf) : quand
AUCUN concours ne restreint les bandes (QSO occasionnel = axe libre), l'activité
choisie sur l'accueil doit donner un repli PERTINENT plutôt que ALL_BANDS —
sinon choisir « activation portable » ne changerait rien au sélecteur pour
l'usage le plus courant (pas de concours actif). Pour l'activation POTA/SOTA/
XOTA : bandes déca SSB/CW courantes + V/UHF portable.

Réutilise le harnais V8 (DOM minimal + chargement du vrai logx_logbook.js) du
test V/UHF, pour ne pas dupliquer 100 lignes de préambule.
"""
import json

import pytest

py_mini_racer = pytest.importorskip(
    'py_mini_racer', reason='py_mini_racer absent — test JS réel ignoré')

from test_logbook_band_picker_vuhf import _make_ctx

XOTA_BANDS = {'7', '14', '21', '28', '50', '144', '432'}


def test_activation_portable_axe_libre_propose_bandes_portables():
    """logx_activity='iota_pota' + aucun concours -> bandes portables, pas ALL_BANDS."""
    ctx = _make_ctx()
    ctx.eval("localStorage.setItem('logx_activity', 'iota_pota');")
    ctx.eval("renderBandButtons('CUSTOM');")
    bands = json.loads(ctx.eval("JSON.stringify(_currentVisibleBands)"))
    assert set(bands) == XOTA_BANDS


def test_activation_portable_pas_de_bandes_micro_ondes_par_defaut():
    ctx = _make_ctx()
    ctx.eval("localStorage.setItem('logx_activity', 'iota_pota');")
    ctx.eval("renderBandButtons('CUSTOM');")
    bands = json.loads(ctx.eval("JSON.stringify(_currentVisibleBands)"))
    assert '1296' not in bands and '2320' not in bands  # micro-ondes rares en portable


def test_concours_reel_prime_sur_le_defaut_activation():
    """Un vrai concours choisi explicitement garde son règlement, jamais
    écrasé par le repli d'activité (l'activité n'influence QUE l'axe libre)."""
    ctx = _make_ctx()
    ctx.eval("localStorage.setItem('logx_activity', 'iota_pota');")
    ctx.eval("renderBandButtons('REF_MARCONI');")  # 144 MHz uniquement
    assert json.loads(ctx.eval("JSON.stringify(_currentVisibleBands)")) == ['144']
