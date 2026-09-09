# -*- coding: utf-8 -*-
"""« + autres bandes » : ajouter une bande hors du défaut d'activité, qui reste
visible pour la session (choix F4GLD, « masquer ≠ bloquer »).

Le défaut d'activité (ex. activation portable) ne propose qu'un sous-ensemble de
bandes ; une bande absente (ex. 18 MHz WARC) doit pouvoir être ajoutée FACILEMENT
et rester dans le sélecteur jusqu'au changement d'activité / rechargement. Un
règlement de concours, lui, reste PRIORITAIRE et n'est jamais élargi par ce
mécanisme. Test sur le VRAI logx_logbook.js en V8.
"""
import json

import pytest

py_mini_racer = pytest.importorskip(
    'py_mini_racer', reason='py_mini_racer absent — test JS réel ignoré')

from test_logbook_band_picker_vuhf import _make_ctx


def _bands(ctx):
    return json.loads(ctx.eval("JSON.stringify(_currentVisibleBands)"))


def test_ajouter_bande_hors_defaut_reste_dans_la_session():
    ctx = _make_ctx()
    ctx.eval("localStorage.setItem('logx_activity', 'iota_pota');")
    ctx.eval("currentContest = 'CUSTOM';")
    ctx.eval("renderBandButtons('CUSTOM');")
    assert '18' not in _bands(ctx)          # 18 MHz absent du défaut activation
    ctx.eval("_ajouterBande('18');")
    assert '18' in _bands(ctx)              # ajoutée -> reste visible pour la session


def test_bande_ajoutee_persiste_apres_re_render():
    ctx = _make_ctx()
    ctx.eval("localStorage.setItem('logx_activity', 'iota_pota');")
    ctx.eval("currentContest = 'CUSTOM';")
    ctx.eval("renderBandButtons('CUSTOM');")
    ctx.eval("_ajouterBande('18');")
    ctx.eval("renderBandButtons('CUSTOM');")   # un re-render ne doit PAS la perdre
    assert '18' in _bands(ctx)


def test_concours_reel_jamais_elargi_par_ajout():
    """Un vrai concours garde son règlement : « + autres » n'ajoute rien."""
    ctx = _make_ctx()
    ctx.eval("localStorage.setItem('logx_activity', 'iota_pota');")
    ctx.eval("currentContest = 'REF_MARCONI';")
    ctx.eval("renderBandButtons('REF_MARCONI');")
    assert _bands(ctx) == ['144']
    ctx.eval("_ajouterBande('18');")
    ctx.eval("renderBandButtons('REF_MARCONI');")
    assert _bands(ctx) == ['144']              # règlement inchangé
