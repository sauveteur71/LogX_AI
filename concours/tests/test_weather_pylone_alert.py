# -*- coding: utf-8 -*-
"""Alerte SÉCURITÉ pylône (vent/rafales) escaladée + accessible (Lot B3).

Refonte cockpit, session navigateur F4GLD (27/08). L'alerte vent/rafales
(« surveille le pylône ») était noyée en rouge dans le widget météo, sans
role="alert" ni escalade. On l'extrait dans un nœud dédié :
  - #weatherAlert role="alert" (stable, vide au repos) -> annoncé par les
    lecteurs d'écran quand il s'active (WCAG 4.1.3) ;
  - clignotement pour s'imposer à l'œil, AVEC repli prefers-reduced-motion ;
  - la météo de ROUTINE (température/vent) n'est PLUS en role="alert"
    (sinon bruit assertif à chaque tic — skill aria-live).

Assertions structurelles ciblées (pas satisfaites par un simple commentaire).
"""
import os
import re

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML = open(os.path.join(BASE, 'logx_logbook.html'), encoding='utf-8').read()
JS = open(os.path.join(BASE, 'logx_outils_autonomes.js'), encoding='utf-8').read()


def test_noeud_alerte_dedie_role_alert():
    assert re.search(r'id="weatherAlert"[^>]*\brole="alert"', HTML), \
        "#weatherAlert doit porter role=alert (annonce lecteur d'écran)"


def test_clignotement_avec_repli_reduced_motion():
    # animation active…
    assert re.search(r'\.weather-alert\.on\{[^}]*animation:', HTML), \
        ".weather-alert.on doit avoir une animation (clignotement)"
    # …mais coupée sous prefers-reduced-motion.
    m = re.search(r'@media\s*\(prefers-reduced-motion:reduce\)\{([^@]*)\}', HTML)
    assert m and 'weather-alert' in m.group(1) and 'animation:none' in m.group(1), \
        "prefers-reduced-motion doit couper le clignotement de l'alerte"


def test_refreshweather_route_lalerte_vers_le_noeud_dedie():
    # d.warn va dans #weatherAlert (textContent + classe .on), pas dans le widget.
    assert "getElementById('weatherAlert')" in JS
    assert re.search(r"classList\.toggle\('on',\s*!!warn\)", JS), \
        "l'alerte doit basculer la classe .on selon d.warn"


def test_meteo_routine_nest_plus_taggee_alerte():
    """La météo de routine ne doit plus injecter d.warn en rouge dans le widget
    (ancien chemin retiré) — sinon double affichage + pas d'escalade a11y."""
    assert 'd.warn ? ` <b' not in JS and "d.warn ? ' <b" not in JS, \
        "l'ancien d.warn en <b> rouge dans le widget doit être retiré"
