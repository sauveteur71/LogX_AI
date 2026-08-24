# -*- coding: utf-8 -*-
"""Deux injections HTML (Strate 2 de l'audit), même classe : donnée injectée
dans du HTML sans neutralisation.

1) logx_configuration.js:applyContestFilters — le NOM du concours (contest.name,
   potentiellement importé/custom donc influençable) était injecté brut dans
   note.innerHTML via `<strong>${name}</strong>`. Fix : escC(name).
2) logx_propagation.html — la valeur N0NBH `v` était injectée brute dans un
   attribut de CLASSE `bc-${v.toLowerCase()}` (le texte, lui, était déjà
   échappé). Une valeur contenant un guillemet/espace sort de l'attribut.
   Fix : assainir la classe aux lettres (`.replace(/[^a-z]/g,'')`).

Tests structurels (le point d'injection est neutralisé) + comportementaux (les
vraies primitives échappent/assainissent une charge malveillante).
"""
import json
import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG = open(os.path.join(BASE, 'logx_configuration.js'), encoding='utf-8').read()
PROP = open(os.path.join(BASE, 'logx_propagation.html'), encoding='utf-8').read()


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


# ─── 1) Nom de concours (configuration.js) ───────────────────────────────────
def test_nom_concours_echappe_a_l_injection():
    assert '<strong>${escC(name)}</strong>' in CONFIG, "le nom de concours doit passer par escC()"
    assert '<strong>${name}</strong>' not in CONFIG, "injection brute du nom encore présente"


def test_escC_echappe_reellement():
    from py_mini_racer import py_mini_racer as m
    c = m.MiniRacer()
    c.eval(_extraire_fn(CONFIG, 'escC'))
    out = c.eval('escC(%s)' % json.dumps('<img src=x onerror=alert(1)>'))
    assert '<img' not in out and '&lt;img' in out, out


# ─── 2) Classe N0NBH (propagation.html) ──────────────────────────────────────
def test_classe_n0nbh_assainie():
    assert "bc-${(v||'').toLowerCase().replace(/[^a-z]/g,'')}" in PROP, \
        "la classe N0NBH doit être assainie aux lettres"
    assert "bc-${(v||'').toLowerCase()}\"" not in PROP, "classe brute encore présente"


def test_classe_assainie_neutralise_une_charge():
    from py_mini_racer import py_mini_racer as m
    c = m.MiniRacer()
    payload = 'good" onmouseover=alert(1) x'
    out = c.eval("(%s).toLowerCase().replace(/[^a-z]/g,'')" % json.dumps(payload))
    # plus aucun guillemet, espace ou parenthèse -> impossible de sortir de l'attribut
    assert '"' not in out and ' ' not in out and '(' not in out, out
    assert out == 'goodonmouseoveralertx'
