# -*- coding: utf-8 -*-
"""XSS DOM réfléchi dans logx_scope.html via le paramètre d'URL ?band=.

`band` vient de l'URL (URLSearchParams.get('band')). Pour une bande inconnue,
bandLabel(band) renvoie la valeur brute (`b+' MHz'`), et le message « Aucun spot
sur {bande} » est injecté dans list.innerHTML via rcTf — qui ne fait qu'une
substitution de placeholders, SANS échappement HTML. La valeur doit donc être
passée à esc() (comme les valeurs voisines esc(s.call)/esc(s.info)).

Test 1 (structurel) : le point d'injection enveloppe bandLabel(band) dans esc().
Test 2 (comportemental) : les VRAIES fonctions esc/bandLabel de la page,
extraites et exécutées, échappent bien une charge malveillante.
"""
import json
import os
import re

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML = open(os.path.join(BASE, 'logx_scope.html'), encoding='utf-8').read()


def test_point_injection_band_echappe():
    # Le message « Aucun spot » ne doit PAS injecter bandLabel(band) brut.
    assert 'esc(bandLabel(band))' in HTML, "bandLabel(band) doit être passé à esc() à l'injection"
    # et il ne reste pas d'injection brute {bande: bandLabel(band)} sans esc
    assert not re.search(r"\{\s*bande\s*:\s*bandLabel\(band\)\s*\}", HTML), \
        "injection brute {bande: bandLabel(band)} encore présente"


def _extraire_fn(src, nom):
    """Extrait `function nom(...) { ... }` par comptage d'accolades."""
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


def test_esc_bandlabel_echappent_une_charge_malveillante():
    from py_mini_racer import py_mini_racer as m
    ctx = m.MiniRacer()
    # BAND_LABELS existe dans la page ; on fournit un objet vide (bande inconnue
    # -> bandLabel renvoie b+' MHz', le cas vulnérable) puis les vraies fonctions.
    ctx.eval('var BAND_LABELS = {};')
    ctx.eval(_extraire_fn(HTML, 'esc'))
    ctx.eval(_extraire_fn(HTML, 'bandLabel'))
    payload = '<img src=x onerror=alert(document.domain)>'
    out = ctx.eval('esc(bandLabel(%s))' % json.dumps(payload))
    assert '<img' not in out and '&lt;img' in out, "la charge doit être échappée : %r" % out
