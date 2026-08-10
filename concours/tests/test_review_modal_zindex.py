# -*- coding: utf-8 -*-
"""Non-régression : #reviewModal (résultat de l'analyse IA du règlement,
voir analyzeRules()/openReviewModal() dans logx_configuration.html) doit
avoir un z-index STRICTEMENT SUPÉRIEUR à celui de .cat-modal et de
.config-sidebar.

analyzeRules() est appelé DEPUIS le popup catmodal_ai, qui reste ouvert
pendant les 30-90s d'analyse (il n'y a pas de fermeture avant l'ouverture
du modal de relecture). Si #reviewModal a un z-index inférieur à l'overlay
.cat-modal qui le recouvre, le résultat s'affiche bien (display:block) mais
reste visuellement invisible tant que le popup n'est pas fermé — bug réel
signalé par F4GLD le 08/08/2026 (z-index:1000 vs .cat-modal:9000)."""
import os
import re

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML_PATH = os.path.join(BASE, 'logx_configuration.html')

with open(HTML_PATH, encoding='utf-8') as _f:
    _HTML_SRC = _f.read()
# Script inline extrait vers logx_configuration.js (10/08/2026) -- concaténer
# pour que les recherches ci-dessous continuent de le trouver.
_JS_PATH = os.path.join(BASE, 'logx_configuration.js')
if os.path.exists(_JS_PATH):
    with open(_JS_PATH, encoding='utf-8') as _f:
        _HTML_SRC += '\n' + _f.read()


def _zindex_of(selector_pattern):
    m = re.search(selector_pattern + r'[^}]*?z-index:\s*(\d+)', _HTML_SRC)
    assert m, 'z-index introuvable pour le motif %r dans %s' % (selector_pattern, HTML_PATH)
    return int(m.group(1))


def test_review_modal_zindex_devant_cat_modal_et_sidebar():
    z_review = _zindex_of(r'id="reviewModal"\s+style="')
    z_catmodal = _zindex_of(r'\.cat-modal\{')
    z_sidebar = _zindex_of(r'\.config-sidebar\{')
    assert z_review > z_catmodal, (
        '#reviewModal (z-index:%d) doit passer au-dessus de .cat-modal '
        '(z-index:%d) : analyzeRules() est lancé depuis catmodal_ai qui '
        'reste ouvert pendant l\'analyse.' % (z_review, z_catmodal))
    assert z_review > z_sidebar, (
        '#reviewModal (z-index:%d) doit aussi passer au-dessus de '
        '.config-sidebar (z-index:%d), visible en même temps que catmodal_ai.'
        % (z_review, z_sidebar))
