# -*- coding: utf-8 -*-
"""Barre de statut : le chrono ⏱ (compte à rebours d'épreuve) ne doit PAS
s'afficher hors mode concours.

DÉFAUT F4GLD (27/08/2026, capture) : « ce qui est en jaune n'a rien à faire là
si je ne suis pas en mode concours ! » — le chrono affichait un « — » permanent
même sans concours choisi, encombrant la barre. Cohérent avec la doctrine
« l'axe est l'activité » (CLAUDE.md) : un outil de concours n'apparaît que
lorsqu'un concours est actif.

On charge le VRAI logx_statusbar.js dans V8 (même harnais que
test_pastille_orage_cache_froid) et on regarde `style.display` de l'item chrono
— ce que voit l'opérateur — selon que la config contient un concours ou non.
Grepper « display » ne prouverait rien : c'est l'ENCHAÎNEMENT getConfig() →
refreshCountdown() → item masqué qu'on veut tenir.
"""
import json
import os
import sys

import pytest

py_mini_racer = pytest.importorskip(
    'py_mini_racer', reason='py_mini_racer absent — test JS réel ignoré')

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
if TESTS_DIR not in sys.path:
    sys.path.insert(0, TESTS_DIR)

# Réutilise le bac à sable navigateur + le chargeur de source déjà éprouvés.
from test_pastille_orage_cache_froid import _PREAMBULE, _source  # noqa: E402


def _load(cfg):
    """Charge la barre (donc boot() → refreshCountdown()) avec `cfg` déjà posé
    dans localStorage sous la clé lue par getConfig()."""
    ctx = py_mini_racer.MiniRacer()
    ctx.eval(_PREAMBULE)
    # getConfig() fait JSON.parse(localStorage.getItem('logx_config')) : on stocke
    # donc la CHAÎNE JSON de la config (double json.dumps : objet -> JSON, puis
    # littéral JS).
    ctx.eval("localStorage.setItem('logx_config', %s);" % json.dumps(json.dumps(cfg)))
    ctx.eval(_source())
    return ctx


def _display(ctx):
    return ctx.eval("String(document.getElementById('rcsbTimeItem').style.display)")


def test_chrono_masque_sans_concours():
    ctx = _load({'contest': ''})
    assert _display(ctx) == 'none'


def test_chrono_masque_si_config_vide():
    ctx = _load({})
    assert _display(ctx) == 'none'


def test_chrono_visible_avec_concours():
    ctx = _load({'contest': 'CQ_WW_SSB', 'contest_end_date': '2026-12-31',
                 'contest_end_utc': '23:59', 'usage_mode': 'expert'})
    # Visible = display remis à '' (l'éventuel masque AFFICHAGE, lui, agit via
    # une classe !important, pas via ce display inline).
    assert _display(ctx) == ''


def test_chrono_visible_meme_si_dates_incompletes_mais_concours_choisi():
    """Un concours est CHOISI mais sans date de fin : l'item reste visible (le
    chrono montrera « — »), car un concours est bien actif. Le masquage ne vise
    QUE l'absence totale de concours."""
    ctx = _load({'contest': 'CQ_WW_SSB'})
    assert _display(ctx) != 'none'
