# -*- coding: utf-8 -*-
"""L'attribut <html lang> suit la langue AFFICHÉE (WCAG 3.1.1).

Défaut : applyLang() posait `document.documentElement.lang = 'fr'` EN DUR même
en langue étrangère (commentaire « aide le navigateur ») — un lecteur d'écran
lisait alors l'allemand/l'espagnol… avec une voix française. Correctif :
`lang = <langue cible>` + `translate="no"` (LogX gère sa propre i18n ; on
interdit l'auto-traduction du navigateur qui re-mangerait le DOM déjà traduit).

On rejoue le VRAI logx_i18n.js dans V8 (même harnais que
test_i18n_dynamic_retranslation) : rc_lang posé avant init() → applyLang() joue
la langue, et on lit document.documentElement.lang — ce que voit le lecteur
d'écran.
"""
import os
import sys

import pytest

pytest.importorskip('py_mini_racer', reason='py_mini_racer absent — test JS réel ignoré')

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
if TESTS_DIR not in sys.path:
    sys.path.insert(0, TESTS_DIR)

from test_i18n_dynamic_retranslation import _make_ctx, _real_source  # noqa: E402


def _ctx_pour_langue(lang):
    ctx = _make_ctx()
    ctx.eval("localStorage.setItem('rc_lang', %r);" % lang)
    ctx.eval(_real_source())   # init() → applyLang(lang)
    return ctx


def test_lang_suit_la_langue_etrangere():
    ctx = _ctx_pour_langue('de')
    assert ctx.eval("String(document.documentElement.lang)") == 'de', \
        "documentElement.lang doit valoir 'de' quand la page est affichée en allemand"


def test_translate_no_pose_pour_bloquer_l_auto_traduction():
    ctx = _ctx_pour_langue('de')
    assert ctx.eval("String(document.documentElement.getAttribute('translate'))") == 'no', \
        "translate='no' doit être posé (LogX gère sa propre i18n)"


def test_une_autre_langue_espagnol():
    ctx = _ctx_pour_langue('es')
    assert ctx.eval("String(document.documentElement.lang)") == 'es'
