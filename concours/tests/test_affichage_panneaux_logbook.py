# -*- coding: utf-8 -*-
"""Étape 1 — panneaux du LOGBOOK togglables via le menu ⚙ AFFICHAGE.

Généralise le patron STATUSBAR_TOGGLES (déjà éprouvé pour la barre de statut) aux
panneaux du LOGBOOK : l'opérateur montre/cache ce qu'il veut. Points de sûreté :
- ON par défaut (default:true) pour les panneaux -> AUCUN changement de
  comportement tant que l'opérateur n'y touche pas ;
- `layered:true` -> la bascule ne FORCE pas le display (d'autres règles — mode
  radio, mode d'usage — continuent de décider) ; seul OFF verrouille le masquage
  via la classe !important ;
- le chemin critique (saisie QSO) n'est JAMAIS listé ;
- la bascule n'apparaît que si l'élément existe sur la page (renderDisplayDD).

Test structurel ; le rendu visuel (2 thèmes) reste à vérifier en navigateur.
"""
import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS = open(os.path.join(BASE, 'logx_statusbar.js'), encoding='utf-8').read()
HTML = open(os.path.join(BASE, 'logx_logbook.html'), encoding='utf-8').read()

_PANNEAUX = ('bandRecapBar', 'opStatsBar', 'hourChartBar', 'bandmapPanel', 'keyerDock')


def test_panneaux_logbook_dans_le_registre_on_par_defaut():
    for pid in _PANNEAUX:
        i = JS.find("id: '%s'" % pid)
        assert i != -1, "panneau absent du registre : %s" % pid
        entree = JS[i:i + 140]
        assert 'default: true' in entree, "%s doit être ON par défaut (pas de régression)" % pid
        assert 'layered: true' in entree, "%s doit être layered (ne pas forcer display)" % pid


def test_saisie_qso_jamais_togglable():
    # le chemin critique ne doit JAMAIS être une bascule
    assert "id: 'saisie-panel'" not in JS and "'saisiePanel'" not in JS


def test_apply_respecte_layered():
    # les items layered ne forcent pas el.style.display
    assert 'if (!t.layered) el.style.display = shown' in JS


def test_menu_a_un_sous_titre_panneaux():
    assert "sec === 'logbook'" in JS
    assert 'rcsb-dd-sub' in JS
    assert '#rcsbDisplayDD .rcsb-dd-sub{' in JS


def test_bandmap_a_bien_un_id():
    assert 'id="bandmapPanel"' in HTML
    # la saisie QSO reste identifiée par sa classe, hors bascules
    assert 'class="saisie-panel"' in HTML
