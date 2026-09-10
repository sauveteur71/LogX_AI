# -*- coding: utf-8 -*-
"""Corbeille de QSO côté LOGBOOK (fonctions PURES de logx_logbook.js :
_cbAge/_cbEsc/renderCorbeilleList) + câblage (menu, overlay, fonctions show/
close/restaurer). Exécute le VRAI logx_logbook.js en V8 (py_mini_racer),
fonctions extraites par comptage d'accolades (même technique que
test_logbook_menu_debut_fin.py::_bloc_menu — le fichier entier a des accès
DOM top-level qui plantent un V8 nu)."""
import os
import re

import pytest

py_mini_racer = pytest.importorskip('py_mini_racer')

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS = os.path.join(CONCOURS, 'logx_logbook.js')
HTML = os.path.join(CONCOURS, 'logx_logbook.html')


def _lire(p):
    with open(p, encoding='utf-8') as f:
        return f.read()


def _bloc_fonction(src, nom):
    """Extrait `function nom(...) { ... }` telle quelle, par comptage
    d'accolades (une fonction peut contenir des chaînes avec des accolades
    déséquilibrées en théorie, mais aucune ici)."""
    m = re.search(r'function %s\([^)]*\)\s*\{' % re.escape(nom), src)
    assert m, 'fonction introuvable dans le source : ' + nom
    ouv = src.index('{', m.start())
    prof, i = 0, ouv
    while True:
        c = src[i]
        if c == '{':
            prof += 1
        elif c == '}':
            prof -= 1
            if prof == 0:
                return src[m.start():i + 1]
        i += 1


def _ctx():
    src = _lire(JS)
    ctx = py_mini_racer.MiniRacer()
    for nom in ('_cbEsc', '_cbAge', 'renderCorbeilleList'):
        ctx.eval(_bloc_fonction(src, nom))
    return ctx


# ─── _cbAge ──────────────────────────────────────────────────────────────

def test_age_minutes():
    ctx = _ctx()
    assert ctx.eval("_cbAge(0, 300)") == 'il y a 5 min'


def test_age_moins_dune_minute_arrondit_a_1():
    ctx = _ctx()
    assert ctx.eval("_cbAge(0, 10)") == 'il y a 1 min'


def test_age_heures():
    ctx = _ctx()
    assert ctx.eval("_cbAge(0, 7200)") == 'il y a 2 h'


def test_age_jours():
    ctx = _ctx()
    assert ctx.eval("_cbAge(0, 3 * 86400)") == 'il y a 3 j'


def test_age_negatif_ne_produit_jamais_de_duree_negative():
    """`now` avant `deleted_at` (horloge client légèrement en retard sur le
    serveur) : la branche <3600s capture TOUT négatif (pas de borne basse),
    et son Math.max(1, ...) plancher protège déjà l'affichage — vérifié avec
    un écart largement supérieur à 1 minute pour que la protection soit
    seule responsable du résultat, pas un arrondi qui tombe à 1 par hasard."""
    ctx = _ctx()
    assert ctx.eval("_cbAge(1000, 700)") == 'il y a 1 min'   # -300s -> plancher à 1 min


# ─── renderCorbeilleList ────────────────────────────────────────────────

def test_liste_vide_message():
    ctx = _ctx()
    assert 'cb-empty' in ctx.eval("renderCorbeilleList([], 0)")


def test_rend_call_bande_mode_age():
    ctx = _ctx()
    html = ctx.eval("""renderCorbeilleList(
        [{id:1, call:'F4ABC', band:'14', mode:'SSB', deleted_at:0}], 300
    )""")
    assert 'F4ABC' in html and '14' in html and 'SSB' in html
    assert 'il y a 5 min' in html


def test_bouton_restaurer_porte_lid():
    ctx = _ctx()
    html = ctx.eval("renderCorbeilleList([{id:7, call:'F4ABC', deleted_at:0}], 0)")
    assert 'restaurerCorbeilleQso' in html and '"7"' in html


def test_echappe_les_champs_contre_injection():
    ctx = _ctx()
    html = ctx.eval("renderCorbeilleList([{id:1, call:'<script>', band:'<b>x</b>', deleted_at:0}], 0)")
    assert '<script>' not in html and '&lt;script&gt;' in html
    assert '<b>x</b>' not in html and '&lt;b&gt;' in html


def test_plusieurs_entrees_toutes_rendues():
    ctx = _ctx()
    html = ctx.eval("""renderCorbeilleList(
        [{id:1, call:'A'}, {id:2, call:'B'}, {id:3, call:'C'}], 0
    )""")
    assert (html.count('cb-row')) == 3


# ─── Câblage (structure statique, sans DOM/fetch) ──────────────────────

def test_menu_expose_corbeille_pas_expert_only():
    src = _lire(JS)
    assert "'showCorbeille'" in src, "entrée de menu 'showCorbeille' introuvable"
    m = re.search(r'MENU_LB_EXPERT_ONLY_FN = new Set\(\[([^\]]*)\]\)', src)
    assert m, 'MENU_LB_EXPERT_ONLY_FN introuvable'
    assert 'showCorbeille' not in m.group(1), (
        'la corbeille ne doit JAMAIS être expert-only — sûreté pour tous, pas un outil avancé')


def test_les_fonctions_montrer_fermer_restaurer_existent():
    src = _lire(JS)
    for fn in ('showCorbeille', 'closeCorbeille', 'restaurerCorbeilleQso'):
        assert 'function %s(' % fn in src, fn


def test_loverlay_existe_dans_la_page_et_pas_expert_only():
    html = _lire(HTML)
    m = re.search(r'<div class="shortcuts-overlay[^"]*"\s+id="corbeilleOverlay"', html)
    assert m, 'corbeilleOverlay introuvable'
    assert 'expert-only' not in m.group(0), (
        'la corbeille ne doit JAMAIS être expert-only — sûreté pour tous, pas un outil avancé')


def test_loverlay_pointe_vers_showcorbeille_close_et_restaurer():
    html = _lire(HTML)
    bloc_debut = html.index('id="corbeilleOverlay"')
    bloc = html[bloc_debut:bloc_debut + 1500]
    assert 'closeCorbeille()' in bloc
    assert 'id="cbList"' in bloc
