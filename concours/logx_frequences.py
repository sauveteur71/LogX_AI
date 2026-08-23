# -*- coding: utf-8 -*-
"""Fréquences conventionnelles de cadran (dial) par bande × mode — IARU R1.

Lecture seule de logx_rigs/frequences_iaru_r1.json (données sourcées, voir ce
fichier). Sert d'enabler à l'auto-QSY : « l'opérateur choisit FT8 sur 20 m ->
quelle fréquence de cadran afficher/proposer ? ». Ce module NE commande PAS la
radio : la décision d'envoyer un QSY (auto vs bouton) et son exécution CAT
restent à câbler séparément, en supervisé (émission).
"""
import json
import os

_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     'logx_rigs', 'frequences_iaru_r1.json')
_cache = None


def _load():
    global _cache
    if _cache is None:
        with open(_FILE, encoding='utf-8') as f:
            _cache = json.load(f).get('frequences', [])
    return _cache


def dial_freq(band, mode, region='IARU_R1', variant=None):
    """Fréquence de cadran (MHz) pour (band, mode), ou None si non définie
    (ex. 'local'/'selon autorisation' non renseignés). `variant` sélectionne une
    variante précise (ex. 'DX_intercontinental' pour 50.323 en 6 m FT8) ; sans
    variante, rend l'entrée principale (sans champ 'variant')."""
    b, m = str(band).lower(), str(mode).upper()
    matches = [e for e in _load()
               if e['band'].lower() == b and e['mode'].upper() == m
               and e.get('region') == region]
    if not matches:
        return None
    if variant is not None:
        for e in matches:
            if e.get('variant') == variant:
                return e['dial_mhz']
        return None
    principal = [e for e in matches if 'variant' not in e]
    return (principal[0] if principal else matches[0])['dial_mhz']


def modes_de_bande(band, region='IARU_R1'):
    """Modes numériques ayant une fréquence conventionnelle sur cette bande."""
    b = str(band).lower()
    return sorted({e['mode'] for e in _load()
                   if e['band'].lower() == b and e.get('region') == region})
