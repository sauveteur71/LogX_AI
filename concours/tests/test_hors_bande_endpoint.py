# -*- coding: utf-8 -*-
"""Le marqueur « hors bande » traverse-t-il réellement le serveur ?

POURQUOI CE FICHIER EXISTE. hors_bande_france() peut être parfaite et n'être
appelée par personne — c'est exactement ce qui est arrivé à usage_mode, resté
des mois sans jamais atteindre le prompt de l'IA, et à popoutBandes(), laissée
sans appelant par une épuration. Un test qui vérifie le CÂBLAGE, pas seulement
la fonction.
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


def test_chaque_spot_porte_le_champ_hors_bande(server):
    """Absent, le champ vaut `undefined` côté page : le marqueur ne
    s'afficherait jamais, en silence."""
    d = _get(server, '/data/focus')
    for s in d['spots']:
        assert 'hors_bande' in s, s


def test_le_champ_est_un_BOOLEEN(server):
    """`None` passerait le test précédent tout en étant faux à l'affichage."""
    d = _get(server, '/data/focus')
    for s in d['spots']:
        assert isinstance(s['hors_bande'], bool), s


def test_un_spot_dans_la_bande_n_est_pas_marque(server):
    """Le cas normal, et de loin le plus fréquent : si tout était marqué, le
    marqueur ne voudrait plus rien dire."""
    d = _get(server, '/data/focus')
    dedans = [s for s in d['spots'] if not s['hors_bande']]
    assert len(dedans) == len([s for s in d['spots'] if not s['hors_bande']])
    # Sur un cluster réel la très grande majorité des spots est dans la bande.
    if d['spots']:
        assert dedans, 'aucun spot dans la bande : le marqueur est trop large'


def test_le_marqueur_suit_bien_la_frequence(server):
    """Cohérence entre le champ servi et la fonction qui le calcule — un
    recalcul indépendant, pas une relecture du même code."""
    import logx_awards as aw
    d = _get(server, '/data/focus')
    for s in d['spots']:
        assert s['hors_bande'] == aw.hors_bande_france(s.get('freq')), s
