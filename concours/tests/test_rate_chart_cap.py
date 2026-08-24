# -*- coding: utf-8 -*-
"""Graphe de rythme (logx_rate_panel.js) : borne défensive du nombre de barres.

renderRateChart comble les heures sans QSO d'un zéro, en itérant de la PREMIÈRE
à la DERNIÈRE heure trouvée dans qsoLog. Or qsoLog est le carnet UNIQUE et
chronologique (toutes bandes/années). Deux QSO éloignés (reprise le lendemain,
import d'un log ancien) ou une date corrompue (99991231) généraient des
milliers de barres vides, voire un gel du navigateur (boucle horaire non bornée).

Correctif : plafonner à MAX_HEURES (un mois) ; au-delà, n'afficher que la
fenêtre la plus récente. Une session réelle n'en approche jamais.

Test comportemental (vraie fonction extraite, Chart stubbé pour capturer la
config) : carnet étalé sur ~1 an -> nb de barres borné ; petit concours intact.
"""
import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS = open(os.path.join(BASE, 'logx_rate_panel.js'), encoding='utf-8').read()
MAX_HEURES = 24 * 31


def _extraire_fn(src, nom):
    i = src.index('function ' + nom)
    j = src.index('{', i)
    prof, k = 0, j
    while k < len(src):
        if src[k] == '{':
            prof += 1
        elif src[k] == '}':
            prof -= 1
            if prof == 0:
                return src[i:k + 1]
        k += 1
    raise AssertionError('fonction %s introuvable' % nom)


def _ctx():
    from py_mini_racer import py_mini_racer as m
    c = m.MiniRacer()
    c.eval('var _cfg = null;')
    c.eval('function Chart(ctx, cfg){ _cfg = cfg; }')
    c.eval('var document = { getElementById: function(){ return {}; } };')
    c.eval('var window = {};')
    c.eval('function _qsoHourKey(q){ return q.h; }')   # fournit la clé d'heure
    c.eval(_extraire_fn(JS, 'renderRateChart'))
    return c


def test_borne_le_nombre_de_barres():
    c = _ctx()
    # deux QSO à ~1 an d'écart -> sans borne : ~8760 barres
    c.eval("var qsoLog = [{h:'2025080100'}, {h:'2026080100'}];")
    c.eval('renderRateChart();')
    n = c.eval('_cfg.data.labels.length')
    assert n <= MAX_HEURES, "nb de barres non borné (anti-gel) : %d" % n


def test_cas_normal_intact():
    c = _ctx()
    # petit concours : 3 heures consécutives -> 3 barres, comportement inchangé
    c.eval("var qsoLog = [{h:'2026080110'}, {h:'2026080111'}, {h:'2026080112'}];")
    c.eval('renderRateChart();')
    assert c.eval('_cfg.data.labels.length') == 3
