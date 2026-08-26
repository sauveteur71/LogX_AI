# -*- coding: utf-8 -*-
"""Affichage du crédit CHASSE (badge « pourquoi » + score) sur chaque ligne de
spot. creditBadge extrait du fichier LIVRÉ et exécuté en V8 (esc stubé)."""
import os
import re

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHASSE = os.path.join(CONCOURS, 'logx_chasse.html')
py_mini_racer = pytest.importorskip('py_mini_racer')


def _lire():
    with open(CHASSE, encoding='utf-8') as f:
        return f.read()


def _ctx():
    src = _lire()
    labels = re.search(r'const CREDIT_LABELS = \{.*?\};', src, re.S)
    fn = re.search(r'function creditBadge\(s\)\{.*?\n\}', src, re.S)
    assert labels and fn, 'CREDIT_LABELS/creditBadge introuvables'
    ctx = py_mini_racer.MiniRacer()
    ctx.eval("function esc(x){return String(x==null?'':x);}")   # stub
    ctx.eval(labels.group(0))
    ctx.eval(fn.group(0))
    return ctx


def _spot(cl, raison='parce que', score=0):
    return "{credit_classe:'%s', credit_raison:'%s', credit_score:%d}" % (cl, raison, score)


def test_badge_atno():
    ctx = _ctx()
    html = ctx.eval("creditBadge(%s)" % _spot('atno', 'Nouvelle entité', 1000))
    assert 'ATNO' in html and 'cr-atno' in html and 'Nouvelle entité' in html and '+1000' in html


def test_badge_new_band_mode():
    ctx = _ctx()
    assert 'cr-new_band' in ctx.eval("creditBadge(%s)" % _spot('new_band', 'x', 600))
    assert 'cr-new_mode' in ctx.eval("creditBadge(%s)" % _spot('new_mode', 'x', 500))


def test_needed_confirm_affiche():
    ctx = _ctx()
    assert 'cr-needed_confirm' in ctx.eval("creditBadge(%s)" % _spot('needed_confirm', 'x', 200))


def test_badge_new_grid():
    ctx = _ctx()
    html = ctx.eval("creditBadge(%s)" % _spot('new_grid', 'Nouveau carré', 450))
    assert 'cr-new_grid' in html and 'CARR' in html.upper() and '+450' in html


def test_confirme_et_inconnu_rien():
    ctx = _ctx()
    assert ctx.eval("creditBadge(%s)" % _spot('confirmed', 'déjà fait', 0)) == ''
    assert ctx.eval("creditBadge(%s)" % _spot('inconnu')) == ''
    assert ctx.eval("creditBadge({})") == ''       # spot sans crédit (API ancienne) : rien


def test_objectif_desactive_masque_le_badge():
    # Un objectif décoché -> score 0 côté serveur (score_classe neutralise le
    # crédit). La classe reste factuelle, mais le badge ne doit PAS s'afficher :
    # sinon le profil d'objectifs n'aurait AUCUN effet visible sur le need-list
    # (l'intention de l'option b : « le moteur ajuste score ET badges »).
    ctx = _ctx()
    assert ctx.eval("creditBadge(%s)" % _spot('atno', 'Nouvelle entité', 0)) == ''
    assert ctx.eval("creditBadge(%s)" % _spot('new_grid', 'Nouveau carré', 0)) == ''
    # mais un objectif ACTIF (score > 0) reste affiché
    assert 'cr-atno' in ctx.eval("creditBadge(%s)" % _spot('atno', 'x', 1000))


def test_cable_dans_le_gabarit_et_css():
    src = _lire()
    assert '${creditBadge(s)}' in src                        # appelé dans la ligne de spot
    assert '.sr-credit-badge' in src and '.cr-atno' in src   # styles présents
    assert '.cr-new_grid' in src                             # style du crédit carré VHF
