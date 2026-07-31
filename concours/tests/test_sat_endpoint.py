# -*- coding: utf-8 -*-
"""L'endpoint /data/sat : la prédiction traverse-t-elle vraiment le serveur ?

POURQUOI CE FICHIER EXISTE. Quatre fois dans la même journée, un défaut est
resté invisible parce que la valeur calculée n'était lue par personne :
popoutBandes() sans appelant, usage_mode qui n'atteignait jamais le prompt,
path_loss_db fausse de 123 dB, a_index récupéré puis jeté. Un module de
prédiction parfait et non branché serait le cinquième.

CE QUI EST VÉRIFIÉ ICI : que l'endpoint réponde, qu'il porte TOUJOURS l'âge du
jeu TLE — une prédiction sans son âge est une prédiction dont on ignore si elle
vaut quelque chose — et qu'il ne tombe pas quand le cache manque, ce qui est
l'état normal d'une première installation ou d'une expédition sans réseau.
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


def test_l_endpoint_repond(server):
    d = _get(server, '/data/sat')
    assert isinstance(d, dict)
    assert 'available' in d


def test_l_AGE_DU_TLE_est_TOUJOURS_present(server):
    """Même sans cache. Un client qui doit tester l'existence de la clé avant
    de la lire finit par ne pas la lire du tout — et la prédiction s'affiche
    alors sans dire sur quoi elle repose."""
    for q in ('', '?sat=ISS', '?sat=INCONNU', '?hours=48'):
        d = _get(server, '/data/sat' + q)
        assert 'tle_age' in d, q


def test_le_satellite_demande_est_renvoye(server):
    d = _get(server, '/data/sat?sat=AO-7')
    assert d['sat'] == 'AO-7'


def test_sans_cache_TLE_on_explique_au_lieu_de_planter(server):
    """État normal d'une première installation : le téléchargement se fait en
    tâche de fond au démarrage, il n'est pas encore arrivé."""
    d = _get(server, '/data/sat')
    if d.get('tle_age') is None and not d.get('passages'):
        assert d.get('error'), d
        assert 'TLE' in d['error']


def test_la_liste_des_satellites_connus_est_servie(server):
    """Sans elle, l'écran ne peut proposer qu'un champ libre — et une faute de
    frappe ne se révèle qu'au moment du passage manqué."""
    d = _get(server, '/data/sat')
    assert isinstance(d.get('satellites'), list)


@pytest.mark.parametrize('q', [
    '?hours=0', '?hours=-5', '?hours=99999', '?hours=abc',
    '?min_el=-10', '?min_el=200', '?min_el=xx',
    '?freq=0', '?freq=abc', '?sat=', '?sat=' + 'x' * 300,
    '?sat=<script>', '?hours=24&hours=48',
])
def test_une_requete_douteuse_ne_fait_pas_tomber_l_endpoint(server, q):
    """Les bornes viennent d'une URL tapée à la main ou d'un vieux favori."""
    d = _get(server, '/data/sat' + q)
    assert isinstance(d, dict)


def test_la_reponse_reste_LEGERE(server):
    """Cet écran se rafraîchit pendant un passage, toutes les quelques
    secondes. Le panneau coach envoyait 5,5 Mo à chaque fois pour une donnée
    que personne n'affichait : on ne recommence pas."""
    with urllib.request.urlopen(server + '/data/sat?hours=168', timeout=30) as r:
        taille = len(r.read())
    assert taille < 200_000, '%d octets' % taille


def test_le_module_est_bien_CABLE():
    """Le test qui compte : logx_sat_passes doit être appelé par le serveur.
    Quatre fonctions justes et non branchées ont déjà coûté cher aujourd'hui."""
    with open(os.path.join(CONCOURS, 'logx_http.py'), encoding='utf-8') as f:
        assert 'logx_sat_passes' in f.read()


def test_le_telechargement_est_lance_au_demarrage():
    """Sans lui, l'endpoint n'aurait jamais de cache à lire — et il
    répondrait poliment « aucun jeu TLE » pour toujours."""
    with open(os.path.join(CONCOURS, 'logx_serveur.py'), encoding='utf-8') as f:
        src = f.read()
    assert 'rafraichir_tle' in src, 'le telechargement TLE n a aucun appelant'
    # Le fil doit être un DÉMON : sur une expédition sans réseau, un fil non
    # démon empêcherait le serveur de s'arrêter proprement.
    assert 'threading.Thread(target=_maj_tle, daemon=True).start()' in src, (
        'le telechargement TLE doit tourner en tache de fond, en demon')
