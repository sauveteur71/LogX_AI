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

_FT2_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         'logx_rigs', 'ft2_decodium_4_0.json')
_ft2_cache = None


def _load():
    global _cache
    if _cache is None:
        with open(_FILE, encoding='utf-8') as f:
            _cache = json.load(f).get('frequences', [])
    return _cache


def ft2_decodium():
    """Profil FT2 Decodium 4.0 — EXPÉRIMENTAL et SÉPARÉ (jamais mêlé au plan de
    bande IARU : aucun sous-segment FT2 dédié en R1). Renvoie le dict complet :
    métadonnées (status/regulatory_status/tx_confirmation_required),
    avertissements et frequencies[{band, dial_hz, note?, warning_fort?}].
    Lecture seule. Ces fréquences sont des conventions du projet, pas un
    plan de bande — l'appelant DOIT afficher les avertissements avant émission."""
    global _ft2_cache
    if _ft2_cache is None:
        with open(_FT2_FILE, encoding='utf-8') as f:
            _ft2_cache = json.load(f)
    return _ft2_cache


def digital_table(region='IARU_R1'):
    """Table pour le bouton QSY du hub numérique :
    {'bands': [...ordre...], 'modes': [...], 'table': {band: {mode: {'dial_mhz','radio_mode'}}}}.
    Ne conserve que l'entrée PRINCIPALE (sans variante) par (band, mode)."""
    table, bands, modes = {}, [], []
    for e in _load():
        if e.get('region') != region or 'variant' in e:
            continue
        b, m = e['band'], e['mode']
        if b not in table:
            table[b] = {}
            bands.append(b)
        if m not in modes:
            modes.append(m)
        table[b][m] = {'dial_mhz': e['dial_mhz'], 'radio_mode': e.get('radio_mode', 'USB-DATA')}
    return {'bands': bands, 'modes': modes, 'table': table}


# Correspondance clé de bande INTERNE (MHz, ex. '14' — celle de _mhz_to_band /
# _band_from_freq / la page FT8) -> label longueur d'onde des données ('20m').
# Les données frequences_iaru_r1.json sont indexées par label ; le reste du dépôt
# manipule la clé interne. UN seul point de correspondance, ici, à côté des
# données — jamais une table dupliquée dans une page.
_BANDE_INTERNE_VERS_LABEL = {
    '1.8': '160m', '3.5': '80m', '7': '40m', '10.1': '30m', '14': '20m',
    '18': '17m', '21': '15m', '24': '12m', '28': '10m', '50': '6m',
    '70': '4m', '144': '2m', '432': '70cm', '1296': '23cm',
}


def label_bande(band_interne):
    """Clé interne ('14') -> label longueur d'onde ('20m'). Idempotent : un label
    déjà correct ('20m') est rendu tel quel."""
    return _BANDE_INTERNE_VERS_LABEL.get(str(band_interne), str(band_interne))


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


# ─── Bandplan IARU R1 (plages + segments) ───────────────────────────────────
_BANDPLAN_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              'logx_rigs', 'bandplan_iaru_r1.json')
_bandplan = None


def _bp():
    global _bandplan
    if _bandplan is None:
        with open(_BANDPLAN_FILE, encoding='utf-8') as f:
            _bandplan = json.load(f)
    return _bandplan


def band_range(band):
    """(début_MHz, fin_MHz) de la bande selon le bandplan IARU R1, ou None."""
    b = str(band).lower()
    for e in _bp()['inventaire']:
        if e['band'].lower() == b:
            return (e['start_mhz'], e['end_mhz'])
    return None


def en_bande_amateur(freq_khz):
    """True si `freq_khz` tombe dans UNE bande amateur de l'inventaire IARU R1
    (2200 m → 1 mm, HF/VHF/UHF/SHF). Sert au garde-fou d'émission CW : ne pas
    keyer hors bande. `freq_khz` illisible/absente -> None (indéterminé :
    l'appelant ne bloque PAS dessus, ex. pas de CAT pour donner la fréquence)."""
    try:
        f = float(freq_khz)
    except (TypeError, ValueError):
        return None
    for e in _bp()['inventaire']:
        if e['start_mhz'] * 1000.0 <= f < e['end_mhz'] * 1000.0:
            return True
    return False
