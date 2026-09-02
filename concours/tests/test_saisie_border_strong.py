# -*- coding: utf-8 -*-
"""Les champs de saisie du carnet utilisent --border-strong au repos (a11y).

Audit contraste (mgifford/color-contrast) : la bordure au repos des champs de
saisie était `var(--border)` (1.97 nuit / 1.80 jour), sous le seuil non-textuel
3:1 de WCAG 1.4.11 — or pour un champ, le contour EST le repère du composant.
On bascule la bordure AU REPOS de `.field-input` (34 champs = toute la saisie
QSO) et `.edit-input` sur `--border-strong` (≥3:1, défini dans logx_theme.css,
verrouillé par tests/test_theme_contrast.py). Le `:focus` reste en accent cuivre
(déjà >4.5:1), inchangé.

Assertion STRUCTURELLE sur le bloc de règle exact (pas une présence de chaîne).
"""
import os
import re

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML = os.path.join(BASE, 'logx_logbook.html')


def _regle(selecteur):
    """Corps `{…}` de la règle CSS `selecteur{…}` dans logx_logbook.html."""
    css = open(HTML, encoding='utf-8').read()
    m = re.search(re.escape(selecteur) + r'\s*\{([^}]*)\}', css)
    assert m, f'règle {selecteur!r} introuvable'
    return m.group(1)


def test_field_input_bordure_repos_en_border_strong():
    corps = _regle('.field-input')
    assert re.search(r'border\s*:\s*1px\s+solid\s+var\(--border-strong\)', corps), \
        ".field-input doit utiliser var(--border-strong) au repos"
    # PAS l'ancien --border faible.
    assert 'var(--border)' not in corps, \
        ".field-input ne doit plus utiliser le --border faible au repos"


def test_edit_input_bordure_repos_en_border_strong():
    corps = _regle('.edit-input')
    assert re.search(r'border\s*:\s*1px\s+solid\s+var\(--border-strong\)', corps), \
        ".edit-input doit utiliser var(--border-strong) au repos"
    assert 'var(--border)' not in corps


def test_focus_reste_en_accent_inchange():
    """Le focus garde le repère cuivre (accent), déjà conforme — on ne l'a pas
    remplacé par la bordure au repos."""
    assert re.search(r'\.field-input:focus\{[^}]*var\(--accent2?\)',
                     open(HTML, encoding='utf-8').read()), \
        "le :focus de .field-input doit rester en accent"
