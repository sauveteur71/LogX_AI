# -*- coding: utf-8 -*-
"""L'entrée EME est présente dans le menu Outils de TOUTES les pages qui le portent."""
import glob
import os

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _pages_avec_menu_outils():
    out = []
    for p in glob.glob(os.path.join(CONCOURS, '*.html')):
        with open(p, encoding='utf-8') as f:
            if 'navToolsMenu' in f.read():
                out.append(p)
    return out


def test_toutes_les_pages_a_menu_outils_ont_l_entree_EME():
    manquantes = []
    for p in _pages_avec_menu_outils():
        with open(p, encoding='utf-8') as f:
            if 'logx_eme.html' not in f.read():
                manquantes.append(os.path.basename(p))
    assert not manquantes, 'pages sans entrée EME : %s' % manquantes


def test_il_y_a_bien_des_pages_a_menu_outils():
    # Garde-fou : si le sélecteur ne trouve rien, le test ci-dessus est vacant.
    assert _pages_avec_menu_outils()
