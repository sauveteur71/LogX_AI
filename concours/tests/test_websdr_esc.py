# -*- coding: utf-8 -*-
"""logx_websdr.html — échapper aussi les champs numériques dans innerHTML.

Les noms (s.nom/s.lieu/s.grid/s.antenne/s.note) étaient échappés via esc(),
mais les champs venant du récepteur externe (snr, users, users_max, dist_km,
azimut) étaient injectés BRUTS dans le popup carte et la carte liste. Cohérence
défensive : les passer aussi par esc() (aucune régression si numériques, ferme
l'injection si l'un d'eux est un jour une chaîne).
"""
import json
import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML = open(os.path.join(BASE, 'logx_websdr.html'), encoding='utf-8').read()


def test_champs_numeriques_echappes():
    for champ in ('esc(s.snr)', 'esc(s.users)', 'esc(s.users_max)',
                  'esc(s.dist_km)', 'esc(s.azimut)'):
        assert champ in HTML, "champ non échappé : %s" % champ
    # plus aucune injection brute résiduelle de ces champs
    for brut in ('+ s.snr +', '+ s.dist_km +', '+ s.azimut +', '${s.snr}', '${s.dist_km}'):
        assert brut not in HTML, "injection brute encore présente : %s" % brut


def _extraire_fn(src, entete):
    i = src.index(entete)
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
    raise AssertionError('fonction introuvable')


def test_esc_echappe_reellement():
    from py_mini_racer import py_mini_racer as m
    c = m.MiniRacer()
    c.eval(_extraire_fn(HTML, 'function esc('))
    out = c.eval('esc(%s)' % json.dumps('<img src=x onerror=alert(1)>'))
    assert '<img' not in out and '&lt;img' in out, out
