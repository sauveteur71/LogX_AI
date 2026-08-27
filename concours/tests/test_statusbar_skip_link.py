# -*- coding: utf-8 -*-
"""Skip-link « Aller au contenu » (WCAG 2.4.1 Bypass Blocks).

Défaut a11y constaté (27/08/2026, skill mgifford/keyboard) : AUCUNE page LogX
n'a de skip-link ni de <main>. Un utilisateur clavier doit donc tabuler toute
la nav (11 liens) à chaque page. `logx_statusbar.js` (chargé par ~20 pages)
injecte désormais le skip-link comme PREMIER enfant du body (premier arrêt de
Tab), caché hors focus, visible au focus.

On charge le VRAI logx_statusbar.js dans V8 (même harnais que
test_pastille_orage_cache_froid) et on regarde le 1er enfant du body après
boot() — ce que rencontre l'utilisateur clavier.
"""
import os
import sys

import pytest

py_mini_racer = pytest.importorskip(
    'py_mini_racer', reason='py_mini_racer absent — test JS réel ignoré')

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
if TESTS_DIR not in sys.path:
    sys.path.insert(0, TESTS_DIR)

from test_pastille_orage_cache_froid import _PREAMBULE, _source  # noqa: E402


def _boot():
    ctx = py_mini_racer.MiniRacer()
    ctx.eval(_PREAMBULE)
    ctx.eval(_source())
    return ctx


def test_skip_link_est_le_premier_enfant_du_body():
    ctx = _boot()
    assert ctx.eval("String(document.body.firstChild.className)") == 'rcsb-skip'


def test_skip_link_cible_le_contenu_et_a_le_bon_libelle():
    ctx = _boot()
    href = ctx.eval("String(document.body.firstChild.href)")
    assert href.startswith('#'), "le skip-link doit pointer vers une ancre interne"
    assert href == '#main-content'
    assert ctx.eval("String(document.body.firstChild.textContent)") == 'Aller au contenu'


def test_skip_link_est_un_lien():
    """Élément natif <a> (focusable, activable clavier sans ARIA)."""
    ctx = _boot()
    # createElement('a') dans le bac à sable -> l'élément a un href défini.
    assert ctx.eval("String(typeof document.body.firstChild.href)") == 'string'
