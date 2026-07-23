# -*- coding: utf-8 -*-
"""Allocation serveur des n° de série par bande (logx_storage.
allocate_next_serial / logx_http.py:/log/next_serial).

Avant : le PC incrémentait son propre compteur CÔTÉ CLIENT (logx_logbook.js:
nextSerial) et la mobile n'avait qu'un champ texte libre — deux postes qui
logueraient au même instant sur la même bande pouvaient émettre le MÊME
numéro. Le serveur est désormais seul à distribuer un numéro, dérivé de
l'état réel de shared_log et jamais d'un compteur local."""
import http.server
import json
import os
import sys
import threading
import urllib.request

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_storage as storage
import logx_http as httpmod


def _reset():
    storage.shared_log[:] = []
    storage._serial_high_water.clear()


# ─── logx_storage.allocate_next_serial (fonction pure) ───────────────────────

def test_premier_numero_est_1():
    _reset()
    assert storage.allocate_next_serial('144') == 1


def test_incremente_a_chaque_appel():
    _reset()
    assert storage.allocate_next_serial('144') == 1
    assert storage.allocate_next_serial('144') == 2
    assert storage.allocate_next_serial('144') == 3


def test_bandes_independantes():
    _reset()
    assert storage.allocate_next_serial('144') == 1
    assert storage.allocate_next_serial('432') == 1   # bande différente : compteur séparé
    assert storage.allocate_next_serial('144') == 2


def test_reprend_apres_le_plus_grand_deja_loggue():
    """Un poste qui redémarre (ou un second poste qui n'a jamais réservé lui-
    même) ne doit jamais répéter un numéro déjà présent dans shared_log."""
    _reset()
    storage.shared_log[:] = [
        {'band': '144', 'num_sent': '005'},
        {'band': '144', 'num_sent': '003'},
        {'band': '432', 'num_sent': '099'},
    ]
    assert storage.allocate_next_serial('144') == 6
    assert storage.allocate_next_serial('432') == 100


def test_num_sent_non_numerique_ignore():
    """Un num_sent non numérique (exchange fixe type '1D' Field Day, ou champ
    laissé vide) ne doit jamais faire planter le calcul du plus grand n°."""
    _reset()
    storage.shared_log[:] = [{'band': '144', 'num_sent': '1D'},
                             {'band': '144', 'num_sent': ''}]
    assert storage.allocate_next_serial('144') == 1


def test_reservation_abandonnee_laisse_un_trou_tolere():
    """Une réservation jamais suivie d'un /log/add (saisie abandonnée) ne doit
    pas faire reculer ni répéter le prochain numéro — trou toléré, exactement
    comme l'ancien compteur côté client (voir logx_logbook.js:
    updateSerialDisplay)."""
    _reset()
    assert storage.allocate_next_serial('144') == 1   # réservé, jamais utilisé
    assert storage.allocate_next_serial('144') == 2   # pas de retour à 1


def test_peek_ne_consomme_pas_le_compteur():
    """Reproduction directe du bug : la mobile appelait allocate_next_serial()
    (bump réel) à chaque rafraîchissement d'affichage (changement de bande,
    après chaque QSO, chargement de page) juste pour PRÉ-REMPLIR une
    suggestion — chaque interaction UI brûlait un numéro même si aucun QSO
    n'était jamais soumis avec. peek_next_serial() doit pouvoir être appelé
    autant de fois que voulu sans jamais faire avancer la séquence réelle."""
    _reset()
    for _ in range(10):
        assert storage.peek_next_serial('144') == 1   # jamais consommé
    assert storage.allocate_next_serial('144') == 1    # 1er VRAI numéro, inchangé
    for _ in range(10):
        assert storage.peek_next_serial('144') == 2
    assert storage.allocate_next_serial('144') == 2


def test_peek_reflete_les_qso_deja_loggues():
    """peek_next_serial() doit rester dérivé du même état réel que
    allocate_next_serial() (shared_log + high-water), pas d'un calcul figé."""
    _reset()
    storage.shared_log[:] = [{'band': '144', 'num_sent': '005'}]
    assert storage.peek_next_serial('144') == 6
    assert storage.allocate_next_serial('144') == 6   # cohérent avec le peek précédent


def test_appels_concurrents_jamais_le_meme_numero():
    """Simule PC + mobile qui réservent au même instant : deux threads
    concurrents ne doivent jamais recevoir la même valeur (log_lock)."""
    _reset()
    results = []
    results_lock = threading.Lock()

    def worker():
        n = storage.allocate_next_serial('144')
        with results_lock:
            results.append(n)

    threads = [threading.Thread(target=worker) for _ in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(results) == list(range(1, 21))   # aucun doublon, aucun trou


# ─── /log/next_serial (endpoint HTTP, voir logx_http.py) ────────────────────

@pytest.fixture
def server():
    srv = http.server.HTTPServer(('127.0.0.1', 0), httpmod.Handler)
    port = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        yield f'http://127.0.0.1:{port}'
    finally:
        srv.shutdown()
        t.join(timeout=5)


def _get(base, path):
    with urllib.request.urlopen(base + path, timeout=5) as r:
        return json.loads(r.read().decode('utf-8'))


def test_endpoint_renvoie_un_serial_zero_pad(server):
    _reset()
    res = _get(server, '/log/next_serial?band=144')
    assert res['serial'] == '001'


def test_endpoint_incremente_a_chaque_appel(server):
    _reset()
    assert _get(server, '/log/next_serial?band=144')['serial'] == '001'
    assert _get(server, '/log/next_serial?band=144')['serial'] == '002'


def test_endpoint_peek_ne_consomme_pas(server):
    """/log/next_serial?peek=1 : même reproduction que
    test_peek_ne_consomme_pas_le_compteur mais via le VRAI endpoint HTTP
    (celui appelé par logx_mobile.html:refreshSuggestedSerial)."""
    _reset()
    assert _get(server, '/log/next_serial?band=144&peek=1')['serial'] == '001'
    assert _get(server, '/log/next_serial?band=144&peek=1')['serial'] == '001'
    assert _get(server, '/log/next_serial?band=144&peek=1')['serial'] == '001'
    # Sans peek : première VRAIE allocation, toujours 001 (rien consommé avant)
    assert _get(server, '/log/next_serial?band=144')['serial'] == '001'
    assert _get(server, '/log/next_serial?band=144&peek=1')['serial'] == '002'


def test_endpoint_deux_postes_concurrents_pas_de_collision(server):
    """Reproduction directe du scénario PC + mobile : deux requêtes HTTP
    concurrentes sur la même bande ne doivent jamais recevoir le même n°."""
    _reset()
    results = []
    results_lock = threading.Lock()

    def worker():
        res = _get(server, '/log/next_serial?band=144')
        with results_lock:
            results.append(res['serial'])

    threads = [threading.Thread(target=worker) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(set(results)) == 10   # 10 requêtes -> 10 numéros distincts
