# -*- coding: utf-8 -*-
"""Tests de fetch_dxheat() (logx_clusters.py) — source cluster DXHeat
(dxheat.com/source/spots/), API JSON publique vérifiée en direct le
24/07/2026 : content-type application/json, header 'server: gunicorn',
aucune authentification requise. Champs réels observés : Nr, Spotter,
Frequency (kHz, ex. "7175.0"), DXCall, Time, Date, Comment, Flag, Band
(en MÈTRES, ex. 40.0 pour la bande 40m), Mode (USB/LSB/CW/DIGITAL),
Continent_dx, Continent_spotter, DXLocator (grille Maidenhead structurée)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json

import logx_clusters as clusters


# ─── Échantillon réaliste (mêmes champs qu'une réponse réelle capturée) ──────
_SAMPLE_RESPONSE = json.dumps([
    {
        "Nr": 67429325, "Spotter": "hz1bh", "Frequency": "14021.0",
        "DXCall": "dl3amb", "Time": "15:40", "Date": "24/07/26",
        "Beacon": False, "MM": False, "AM": False, "Valid": True,
        "DXHomecall": "DL3AMB", "Comment": "CW tu Fred 559 in jeddah GDX & 73s",
        "Flag": "de", "Band": 20.0, "Mode": "CW",
        "Continent_dx": "EU", "Continent_spotter": "AS", "DXLocator": "JO51AA",
    },
    {
        "Nr": 67429343, "Spotter": "F1HDE", "Frequency": "50324.0",
        "DXCall": "NM6V", "Time": "15:43", "Date": "24/07/26",
        "Beacon": False, "MM": False, "AM": False, "Valid": True,
        "DXHomecall": "NM6V", "Comment": "FT8 Arizona DM43di88go -13dB",
        "Flag": "us", "Band": 6.0, "Mode": "DIGITAL",
        "Continent_dx": "NA", "Continent_spotter": "EU", "DXLocator": "DM43DI",
    },
    {
        "Nr": 67429186, "Spotter": "UA3ARC", "Frequency": "144174.0",
        "DXCall": "EU6AX", "Time": "15:19", "Date": "24/07/26",
        "Beacon": False, "MM": False, "AM": False, "Valid": True,
        "DXHomecall": "EU6AX", "Comment": "<TR> FT8 -19 dB 1303 Hz CQ",
        "Flag": "by", "Band": 2.0, "Mode": "DIGITAL",
        "Continent_dx": "EU", "Continent_spotter": "EU", "DXLocator": "KO33SV",
    },
    {
        "Nr": 67429331, "Spotter": "PD3RL", "Frequency": "7148.0",
        "DXCall": "F4NBH/P", "Time": "15:40", "Date": "24/07/26",
        "Beacon": False, "MM": False, "AM": False, "Valid": True,
        "DXHomecall": "F4NBH", "Comment": "", "Flag": "fr", "Band": 40.0,
        "Mode": "LSB", "Continent_dx": "EU", "Continent_spotter": "EU",
        "DXLocator": "JN16AA",
    },
])


def _stub_fetch_url(monkeypatch, content):
    monkeypatch.setattr(clusters, 'fetch_url', lambda *a, **k: content)


# ─── Parsing de base ─────────────────────────────────────────────────────────

def test_fetch_dxheat_parse_basique(monkeypatch):
    _stub_fetch_url(monkeypatch, _SAMPLE_RESPONSE)
    spots = clusters.fetch_dxheat(filter_digital=False)
    calls = {s['dx'] for s in spots}
    # Le suffixe portable (/P) est gardé tel quel ici — le split() se fait plus
    # tard dans build_ranked_spots (logx_scoring.py), comme pour fetch_dxsummit_hf.
    assert calls == {'DL3AMB', 'NM6V', 'EU6AX', 'F4NBH/P'}


def test_fetch_dxheat_champs_normalises(monkeypatch):
    _stub_fetch_url(monkeypatch, _SAMPLE_RESPONSE)
    spots = clusters.fetch_dxheat(filter_digital=False)
    dl3amb = next(s for s in spots if s['dx'] == 'DL3AMB')
    assert dl3amb['spotter'] == 'HZ1BH'
    assert dl3amb['freq'] == 14021.0
    assert dl3amb['mode'] == 'CW'
    assert dl3amb['locator'] == 'JO51AA'
    assert dl3amb['source'] == 'dxheat'


# ─── Locator : DXLocator utilisé directement, pas de regex sur le commentaire

def test_fetch_dxheat_utilise_dxlocator_pas_le_commentaire(monkeypatch):
    """Le commentaire ne contient explicitement AUCUNE grille (juste du texte
    libre) — si le locator remonté n'était pas DXLocator mais un pattern extrait
    du Comment, il serait vide ici. DXHeat fournit un vrai champ structuré,
    contrairement à DXWatch/F5LEN/Telnet qui obligent à parser le commentaire."""
    _stub_fetch_url(monkeypatch, _SAMPLE_RESPONSE)
    spots = clusters.fetch_dxheat(filter_digital=False)
    nm6v = next(s for s in spots if s['dx'] == 'NM6V')
    assert nm6v['locator'] == 'DM43DI'


# ─── Bande déduite de la fréquence (Frequency, kHz), pas du champ Band (m) ───

def test_fetch_dxheat_bande_deduite_de_la_frequence(monkeypatch):
    """_band_from_freq() (logx_scoring.py) doit être appliqué à Frequency —
    pas au champ Band (en mètres, moins précis pour distinguer les bandes
    WARC : ex. 17m/12m auraient la même valeur générique si on utilisait une
    table mètres->MHz approximative au lieu de la vraie fréquence)."""
    _stub_fetch_url(monkeypatch, _SAMPLE_RESPONSE)
    spots = clusters.fetch_dxheat(filter_digital=False)
    by_call = {s['dx']: s for s in spots}
    assert by_call['DL3AMB']['band'] == '14'    # 14021 kHz -> 20m
    assert by_call['F4NBH/P']['band'] == '7'    # 7148 kHz -> 40m
    assert by_call['NM6V']['band'] == '50'      # 50324 kHz -> 6m
    assert by_call['EU6AX']['band'] == '144'    # 144174 kHz -> 2m (VHF via le même appel)


# ─── Filtre numérique (mode 'DIGITAL' générique DXHeat) ──────────────────────

def test_fetch_dxheat_filtre_digital_exclut_ft8(monkeypatch):
    _stub_fetch_url(monkeypatch, _SAMPLE_RESPONSE)
    spots = clusters.fetch_dxheat(filter_digital=True)
    calls = {s['dx'] for s in spots}
    # NM6V (FT8/DIGITAL) et EU6AX (FT8/DIGITAL) écartés ; CW et LSB conservés
    assert calls == {'DL3AMB', 'F4NBH/P'}


def test_fetch_dxheat_sans_filtre_garde_le_numerique(monkeypatch):
    _stub_fetch_url(monkeypatch, _SAMPLE_RESPONSE)
    spots = clusters.fetch_dxheat(filter_digital=False)
    assert len(spots) == 4


# ─── Robustesse réseau / JSON ─────────────────────────────────────────────────

def test_fetch_dxheat_reseau_indisponible(monkeypatch):
    _stub_fetch_url(monkeypatch, None)
    assert clusters.fetch_dxheat() == []


def test_fetch_dxheat_json_invalide(monkeypatch):
    _stub_fetch_url(monkeypatch, "<html>pas du JSON</html>")
    assert clusters.fetch_dxheat() == []


def test_fetch_dxheat_liste_vide(monkeypatch):
    _stub_fetch_url(monkeypatch, "[]")
    assert clusters.fetch_dxheat() == []


def test_fetch_dxheat_entree_sans_dxcall_ignoree(monkeypatch):
    content = json.dumps([{"Spotter": "F1ABC", "Frequency": "14021.0", "DXCall": "",
                            "Mode": "CW", "DXLocator": "JN15XC"}])
    _stub_fetch_url(monkeypatch, content)
    assert clusters.fetch_dxheat(filter_digital=False) == []


def test_fetch_dxheat_frequence_invalide_ignoree(monkeypatch):
    content = json.dumps([{"Spotter": "F1ABC", "Frequency": "n/a", "DXCall": "W1AW",
                            "Mode": "CW", "DXLocator": "FN31PR"}])
    _stub_fetch_url(monkeypatch, content)
    assert clusters.fetch_dxheat(filter_digital=False) == []
