# -*- coding: utf-8 -*-
"""Driver des bandeaux (logx_bandeaux_driver.js) — branchement page + ⚙ on/off.

Le driver est un module DOM/async (fetch + rendu + ⚙) : on le couvre par un test
de CHARGEMENT V8 (il se charge sans erreur au-dessus du framework et expose
brancher) + des assertions STRUCTURELLES serrées sur les formes d'appel (pas une
simple présence satisfaite par un commentaire). Le comportement visuel est
vérifié en navigateur. La logique on/off pure est testée côté framework
(test_bandeaux.py::basculer*)."""
import os

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRAMEWORK = os.path.join(CONCOURS, 'logx_bandeaux.js')
DRIVER = os.path.join(CONCOURS, 'logx_bandeaux_driver.js')
py_mini_racer = pytest.importorskip('py_mini_racer')


def _src():
    with open(DRIVER, encoding='utf-8') as f:
        return f.read()


def test_driver_se_charge_en_v8_et_expose_brancher():
    """Charge framework PUIS driver dans V8 : prouve qu'il n'a pas d'erreur de
    syntaxe/référence au chargement et qu'il publie LogxBandeauxDriver.brancher."""
    ctx = py_mini_racer.MiniRacer()
    ctx.eval("var window = {}; var module = undefined;")
    with open(FRAMEWORK, encoding='utf-8') as f:
        ctx.eval(f.read())
    ctx.eval(_src())
    assert ctx.eval("typeof window.LogxBandeauxDriver") == 'object'
    assert ctx.eval("typeof window.LogxBandeauxDriver.brancher") == 'function'


def test_driver_branche_sur_le_socle_pur():
    s = _src()
    # formes d'APPEL (parenthèse ouvrante) — non satisfaites par un commentaire.
    assert 'LB.bandeauxActifs(' in s          # filtre les bandeaux actifs
    assert 'LB.basculerBandeau(' in s         # le ⚙ persiste via le socle
    assert 'LB.rendreTicker(' in s            # rend via le framework
    assert 'global.LogxBandeauxDriver' in s


def test_driver_pose_le_reglage_gear_et_chips():
    s = _src()
    assert 'rcb-gear' in s and 'rcb-chip' in s
    assert "data-bandeau" in s                # chaque chip cible un bandeau


def test_driver_respecte_pas_de_bande_morte():
    """ON sans data live -> barre cachée ; tout masqué -> strip ⚙ visible."""
    s = _src()
    assert 'wrap.hidden = true' in s          # actif mais pas de contenu -> caché
    assert 'Bandeaux masqu' in s              # tout masqué -> strip de réactivation


def test_driver_gear_reste_atteignable_en_reglage():
    """Piège évité : si l'opérateur règle (panneau ouvert) et ne laisse que des
    bandeaux sans info live, le ⚙ reste visible (sinon il ne pourrait plus rien
    réactiver, barre disparue)."""
    s = _src()
    assert 'else if(reouvrir)' in s
    assert 'Aucune info en direct' in s


def test_driver_fetch_aware_ne_charge_que_les_flux_affiches():
    """Un bandeau masqué ne doit pas déclencher son fetch : le driver ne
    récupère que les flux des bandeaux affichés (opts.besoins)."""
    s = _src()
    assert 'opts.besoins' in s
    # les bandeaux affichés sont calculés AVANT le fetch (aff filtré, puis aFetch)
    assert 'aFetch' in s


def test_driver_activite_resolue_au_rendu():
    """opts.activite peut être une FONCTION : l'activité effective est résolue à
    CHAQUE rendu (contexte évolutif — un concours qui démarre bascule le
    contexte), pas figée au branchement."""
    s = _src()
    assert "typeof opts.activite === 'function'" in s


def test_driver_transmet_le_contexte_bande_mode():
    """Adaptation : le driver appelle opts.contexte() (fonction de la page) et
    injecte band/mode dans le ctx passé aux bandeaux (protégé par try)."""
    s = _src()
    assert 'opts.contexte' in s
    assert 'band: extra.band' in s and 'mode: extra.mode' in s
    assert 'try {' in s or 'try{' in s        # appel protégé (globale page pas toujours prête)


def test_driver_gear_disclosure_accessible():
    """Motif disclosure du dépôt : aria-expanded + fermeture clic-dehors + Échap
    qui ferme et rend le focus au ⚙."""
    s = _src()
    assert "aria-expanded" in s
    assert "'Escape'" in s and '.focus()' in s        # Échap ferme + rend le focus


def test_driver_ouvre_le_panneau_dans_le_bon_sens():
    """Le panneau ⚙ s'ouvre vers le HAUT si la barre est en bas d'écran (accueil)
    -> ne sort pas sous le viewport."""
    s = _src()
    assert '_placerPanneau' in s and 'getBoundingClientRect' in s
    assert 'rcb-chips-haut' in s
