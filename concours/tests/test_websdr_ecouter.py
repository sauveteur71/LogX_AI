# -*- coding: utf-8 -*-
"""L'endpoint /data/websdr/ecouter : le geste « écouter » traverse-t-il le serveur ?

Le module (deux tris, URL d'écoute) est testé dans test_websdr_annuaire.py ;
ici c'est la couche HTTP qui est visée, avec un annuaire FIXE substitué à la
source (aucun cache disque, aucun réseau — la CI n'a ni l'un ni l'autre) :

  - le ROUTAGE : /data/websdr/ecouter est un préfixe de /data/websdr — servi
    par une route « startswith », il renverrait les ~880 stations au lieu du
    récepteur choisi, et le bouton du logbook ouvrirait un onglet vide ;
  - les deux gestes : sans lat/lon le meilleur SNR près du QTH, avec lat/lon
    la proximité du DX d'abord — et la distance RENDUE est celle au DX, pas
    celle au QTH restée dans le dict station ;
  - le refus propre (ok: False) quand rien n'est en ligne dans le rayon.
"""
import http.server
import json
import os
import sys
import threading
import urllib.request

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CONCOURS not in sys.path:
    sys.path.insert(0, CONCOURS)

import logx_http as httpmod   # noqa: E402
import logx_websdr as wmod    # noqa: E402

# Un parc minuscule mais discriminant. dist_km = distance au QTH (posée par
# annuaire() en vrai) ; lat/lon autour d'un DX fictif en Écosse (55.5, -4.5).
STATIONS = [
    {'nom': 'PRES_QTH_FAIBLE', 'url': 'http://a.example:8073', 'type': 'kiwi',
     'en_ligne': True, 'users': 0, 'users_max': 4, 'snr': 10,
     'lat': 45.0, 'lon': 3.0, 'dist_km': 50},
    {'nom': 'PRES_QTH_FORT', 'url': 'http://b.example:8073', 'type': 'kiwi',
     'en_ligne': True, 'users': 1, 'users_max': 4, 'snr': 35,
     'lat': 47.0, 'lon': 5.0, 'dist_km': 300},
    {'nom': 'PRES_DX', 'url': 'http://c.example:8073', 'type': 'kiwi',
     'en_ligne': True, 'users': 0, 'users_max': 8, 'snr': 5,
     'lat': 55.6, 'lon': -4.4, 'dist_km': 1200},
    {'nom': 'PRES_DX_HORS_LIGNE', 'url': 'http://d.example:8073', 'type': 'kiwi',
     'en_ligne': False, 'users': None, 'users_max': None, 'snr': 40,
     'lat': 55.5, 'lon': -4.5, 'dist_km': 1200},
]


@pytest.fixture(autouse=True)
def _annuaire_fixe(monkeypatch):
    """Substitue l'annuaire complet : le handler fait « import logx_websdr »
    en local, mais c'est le même objet module — le setattr le couvre."""
    monkeypatch.setattr(
        wmod, 'annuaire',
        lambda cfg=None, dossier=None: {'stations': [dict(s) for s in STATIONS],
                                        'age': None})


@pytest.fixture
def server():
    srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), httpmod.Handler)
    port = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        yield f'http://127.0.0.1:{port}'
    finally:
        srv.shutdown()
        srv.server_close()
        t.join(timeout=5)


def _get(base, path):
    with urllib.request.urlopen(base + path, timeout=30) as r:
        return json.loads(r.read().decode('utf-8'))


def test_la_route_n_est_pas_avalee_par_l_annuaire(server):
    """/data/websdr/ecouter commence par /data/websdr : une route en
    startswith le sert en premier et le bouton du logbook reçoit ~880
    stations là où il attend UN récepteur."""
    d = _get(server, '/data/websdr/ecouter?khz=14074')
    assert 'stations' not in d
    assert d.get('ok') is True
    a = _get(server, '/data/websdr')
    assert 'stations' in a and len(a['stations']) == len(STATIONS)


def test_s_ecouter_prend_le_meilleur_snr_pres_du_qth(server):
    d = _get(server, '/data/websdr/ecouter?khz=14074&mode=FT8')
    assert d['ok'] is True
    assert d['nom'] == 'PRES_QTH_FORT'          # SNR 35 > 10, tous deux < 1500 km
    assert d['dist_km'] == 300                   # celle au QTH, posée par annuaire()
    assert d['url'] == 'http://b.example:8073/?f=14074.0usb'   # FT8 = USB


def test_ecouter_un_spot_prefere_la_proximite_du_dx(server):
    d = _get(server, '/data/websdr/ecouter?khz=7021.3&mode=CW&lat=55.5&lon=-4.5')
    assert d['ok'] is True
    # PRES_QTH_FORT a le meilleur SNR du parc mais il est à ~1000 km du DX :
    # c'est la station voisine du DX qui doit gagner, hors-ligne exclue.
    assert d['nom'] == 'PRES_DX'
    assert d['url'] == 'http://c.example:8073/?f=7021.3cw'
    # La distance rendue est celle AU DX (~14 km), pas les 1200 km au QTH
    # restés dans le dict station.
    assert d['dist_km'] < 50


def test_refus_propre_quand_rien_dans_le_rayon(server):
    d = _get(server, '/data/websdr/ecouter?khz=14020&lat=-10&lon=-140')
    assert d == {'ok': False}


def test_une_url_au_schema_refuse_ne_sort_jamais_du_serveur(monkeypatch, server):
    """websdr_cures.json est un fichier éditable à la main : une URL
    « javascript:… » servie dans un href s'exécuterait au clic. url_ecoute la
    rejette — l'endpoint doit alors répondre ok:False, PAS ok:True avec une
    URL vide (qui ouvrirait un onglet sur la page courante)."""
    piege = [{'nom': 'PIEGE', 'url': 'javascript:alert(1)', 'type': 'kiwi',
              'en_ligne': True, 'users': 0, 'users_max': 4, 'snr': 99,
              'lat': 45.0, 'lon': 3.0, 'dist_km': 10}]
    monkeypatch.setattr(wmod, 'annuaire',
                        lambda cfg=None, dossier=None: {'stations': [dict(s) for s in piege],
                                                        'age': None})
    d = _get(server, '/data/websdr/ecouter?khz=7021&mode=CW')
    assert d == {'ok': False}


def test_sans_frequence_l_url_reste_bonne(server):
    """khz absent (pas de CAT) : le récepteur s'ouvre sur sa fréquence par
    défaut — une URL nue, pas une URL avec « ?f=None »."""
    d = _get(server, '/data/websdr/ecouter')
    assert d['ok'] is True
    assert d['url'] == 'http://b.example:8073'
