# -*- coding: utf-8 -*-
"""Fenêtre SAISIE QSO détachée (demande F4GLD 23/10/2026 : « détacher la zone
de saisie de QSO pour n'avoir que ça sur un écran séparé »).

Conception (voir logx_saisie_detachee.js) : la fenêtre détachée est LA MÊME
page logbook ouverte avec ?vue=saisie -> masquage CSS pur, AUCUNE deuxième
implémentation de submitQSO(). Ce que ces tests verrouillent :
  1. le bouton existe et ouvre bien logx_logbook.html?vue=saisie (V8, vrai code) ;
  2. la classe est posée dans le <head> AVANT le premier rendu ;
  3. le masquage n'atteint JAMAIS le chemin critique (saisie, indicatif,
     bouton d'enregistrement, en-tête, dock de macros) ;
  4. il masque bien ce qui doit l'être (tableau du log, band map, nav…).
Vérifié aussi en navigateur réel (Playwright, serveur réel) : QSO saisi dans
la fenêtre détachée -> présent aussitôt dans le tableau de la principale."""
import os
import re

import pytest

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML = open(os.path.join(BASE, 'logx_logbook.html'), encoding='utf-8').read()
MODULE = os.path.join(BASE, 'logx_saisie_detachee.js')


def _sans_commentaires_css(s):
    return re.sub(r'/\*.*?\*/', '', s, flags=re.S)


def _selecteurs_masques():
    """Sélecteurs de la règle html.vue-saisie …{display:none!important}."""
    css = _sans_commentaires_css(HTML)
    regles = re.findall(r'([^{}]+)\{\s*display\s*:\s*none\s*!important\s*\}', css)
    sel = []
    for bloc in regles:
        for s in bloc.split(','):
            s = s.strip()
            if s.startswith('html.vue-saisie '):
                sel.append(s[len('html.vue-saisie '):].strip())
    return sel


def test_classe_posee_dans_le_head_avant_le_rendu():
    head = HTML.split('</head>', 1)[0]
    scripts = re.findall(r'<script>(.*?)</script>', head, flags=re.S)
    code = [re.sub(r'/\*.*?\*/', '', s, flags=re.S) for s in scripts]
    assert any("get('vue') === 'saisie'" in c and "classList.add('vue-saisie')" in c
               for c in code), 'la classe vue-saisie doit être posée par un script du <head>'


def test_masquage_ne_touche_jamais_le_chemin_critique():
    masques = _selecteurs_masques()
    assert masques, 'règle de masquage html.vue-saisie introuvable'
    critiques = ['.saisie-panel', '#inputCall', '#submitBtn', 'header', '.keyer-dock',
                 '#keyerDock', '.main', '#setupModal', '#editOverlay', '#macroToast']
    for c in critiques:
        assert c not in masques, '%s ne doit JAMAIS être masqué en vue saisie' % c
    for m in masques:   # aucun sélecteur ne doit viser un descendant de la saisie
        assert 'saisie-panel' not in m and 'inputCall' not in m and 'submit' not in m.lower(), m


def test_masquage_retire_bien_le_reste():
    masques = set(_selecteurs_masques())
    for attendu in ['.log-panel', '.bandmap-panel', '.app-nav', '#rcStatusBar', '#bandeaux',
                    '.score-banner', '#btnDetacherSaisie', '#occupationToggle']:
        assert attendu in masques, attendu


def test_saisie_en_pleine_largeur():
    css = _sans_commentaires_css(HTML)
    m = re.search(r'html\.vue-saisie\s+\.saisie-panel\s*\{([^}]*)\}', css)
    assert m and 'width:100%' in m.group(1).replace(' ', '') and 'max-width:none' in m.group(1).replace(' ', '')


def test_bouton_detacher_dans_le_titre_de_la_saisie():
    bloc = HTML[HTML.index('<div class="saisie-panel">'):]
    bloc = bloc[:bloc.index('</div>', bloc.index('ESM'))]
    assert re.search(r'<button[^>]*id="btnDetacherSaisie"[^>]*onclick="detacherSaisie\(\)"', bloc)
    assert '<script src="logx_saisie_detachee.js"></script>' in HTML


def test_detacher_ouvre_la_vue_saisie_dans_une_fenetre_unique():
    py_mini_racer = pytest.importorskip('py_mini_racer')
    ctx = py_mini_racer.MiniRacer()
    ctx.eval("var _ouvertures=[]; var window={screen:{availHeight:1040},"
             "open:function(u,n,o){_ouvertures.push([u,n,o]);return {focus:function(){}};}};"
             "var document={documentElement:{classList:{contains:function(){return false;}}}};"
             "var module=undefined;")
    ctx.eval(open(MODULE, encoding='utf-8').read())
    ctx.eval("window.detacherSaisie(); window.detacherSaisie();")
    import json
    ouv = json.loads(ctx.eval("JSON.stringify(_ouvertures)"))
    assert len(ouv) == 2
    for url, nom, _ in ouv:
        assert url == 'logx_logbook.html?vue=saisie'
        assert nom == 'rc_saisie_detachee'   # même nom -> le navigateur réutilise la fenêtre
