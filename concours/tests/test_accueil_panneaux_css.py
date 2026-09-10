# -*- coding: utf-8 -*-
"""Garde-fou du défaut « inexploitable » (09/09/2026) : la fusion CHASSE avait
extrait le JS des panneaux (logx_chasse_panneaux.js) mais PAS le CSS — les spots
se déversaient en texte brut non mis en page sur l'accueil.

Ce test vérifie que (1) l'accueil charge bien logx_chasse_panneaux.css, et
(2) ce CSS définit CHAQUE classe que le JS de rendu émet. Sans lui, une classe
émise sans style repasserait inaperçue (les tests structurels ne regardent que
le HTML/JS, pas la présence de style).
"""
import os
import re

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _lire(nom):
    with open(os.path.join(BASE, nom), encoding='utf-8') as f:
        return f.read()


def test_accueil_charge_le_css_des_panneaux():
    html = _lire('logx_accueil.html')
    assert re.search(r'<link[^>]+href="logx_chasse_panneaux\.css"', html), \
        "logx_accueil.html doit charger logx_chasse_panneaux.css (sinon spots non stylés)"


def test_le_css_definit_les_classes_emises_par_le_js():
    css = _lire('logx_chasse_panneaux.css')
    # Classes réellement produites par renderNeedList / renderActivationRows /
    # la mise en page de _revelerCiblesChasse.
    for cls in ('.spot-row', '.sr-act', '.sr-wca', '.sr-head', '.sr-call', '.sr-band',
                '.sr-qrg', '.sr-mode', '.sr-ref', '.sr-place', '.sr-note',
                '.sr-credit-badge', '.sr-split-badge',
                '.xota-panneaux', '.xota-pan', '.xota-pan-h',
                '.ck-needlist', '.ck-need-row', '.ck-need-call', '.ck-need-prio'):
        assert cls in css, "classe non stylée dans logx_chasse_panneaux.css : " + cls


def test_les_listes_sont_bornees_en_hauteur():
    """Sans max-height, la liste allongeait la page à l'infini (cf. capture)."""
    css = _lire('logx_chasse_panneaux.css')
    assert 'max-height' in css and 'overflow-y:auto' in css
