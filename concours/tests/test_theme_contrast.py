# -*- coding: utf-8 -*-
"""Verrou de contraste WCAG de la palette « graphite & cuivre » (logx_theme.css).

Audit du 27/08/2026 (skill mgifford/color-contrast) : la palette passe l'AA
partout SAUF `--border` (contour), sous le seuil non-textuel 3:1 dans les 2
thèmes standard (1.97 nuit / 1.80 jour). `--border` reste tel quel (séparateurs
décoratifs, exemptés WCAG 1.4.11) ; on introduit `--border-strong` (≥3:1)
réservé aux CONTOURS DE COMPOSANTS INTERACTIFS (champs de saisie), là où le
contour est le seul repère du composant.

Ce test VERROUILLE le contraste de la palette : toute évolution future d'un
token qui casserait l'AA (texte/accent) ou le 3:1 (border-strong, sémantiques
en UI) fait rougir la CI. Ratios calculés selon WCAG 2.x (luminance relative),
pas estimés.
"""
import os
import re

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSS = os.path.join(BASE, 'logx_theme.css')


def _lin(c):
    c /= 255.0
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def _lum(hexs):
    h = hexs.lstrip('#')
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return 0.2126 * _lin(r) + 0.7152 * _lin(g) + 0.0722 * _lin(b)


def _ratio(a, b):
    la, lb = _lum(a), _lum(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def _tokens(selector):
    """Tokens {nom: #hex} du bloc CSS `selector { … }` de logx_theme.css."""
    css = open(CSS, encoding='utf-8').read()
    m = re.search(re.escape(selector) + r'\s*\{([^}]*)\}', css)
    assert m, f'bloc {selector!r} introuvable dans logx_theme.css'
    return dict(re.findall(r'(--[\w-]+)\s*:\s*(#[0-9A-Fa-f]{6})', m.group(1)))


# Thèmes STANDARD (les haut-contraste sont trivialement conformes : noir/blanc).
STD = {'NUIT': ':root', 'JOUR': 'body.day-mode'}


def test_texte_muted_accent_passent_AA():
    """Texte normal / muted / accent cuivre >= 4.5:1 sur le fond, 2 thèmes."""
    for nom, sel in STD.items():
        t = _tokens(sel)
        for cle in ('--text', '--muted', '--accent'):
            r = _ratio(t[cle], t['--bg'])
            assert r >= 4.5, f'{nom} {cle}/bg = {r:.2f} < 4.5 (AA texte)'


def test_border_strong_passe_le_non_textuel():
    """--border-strong >= 3:1 (WCAG 1.4.11) — contours de champs interactifs."""
    for nom, sel in STD.items():
        t = _tokens(sel)
        assert '--border-strong' in t, f'{nom} : --border-strong absent'
        r = _ratio(t['--border-strong'], t['--bg'])
        assert r >= 3.0, f'{nom} --border-strong/bg = {r:.2f} < 3.0'


def test_couleurs_semantiques_passent_le_seuil_UI():
    """green/red/yellow/purple/orange >= 3:1 sur le fond (élément UI / gros)."""
    for nom, sel in STD.items():
        t = _tokens(sel)
        for cle in ('--green', '--red', '--yellow', '--purple', '--orange'):
            r = _ratio(t[cle], t['--bg'])
            assert r >= 3.0, f'{nom} {cle}/bg = {r:.2f} < 3.0 (non-textuel/UI)'


def test_border_strong_present_dans_les_4_variantes():
    """Y compris les 2 haut-contraste, pour qu'un composant qui l'utilise ne
    perde jamais son contour selon le thème actif."""
    for sel in (':root', 'body.day-mode', 'body.high-contrast',
                'body.high-contrast.day-mode'):
        assert '--border-strong' in _tokens(sel), f'{sel} : --border-strong absent'
