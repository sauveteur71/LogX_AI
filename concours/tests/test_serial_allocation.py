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
import urllib.error
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


# ─── Portée concours (contest+année) : chaque édition repart de 001 ──────────
# shared_log est UN log global (log simple + tous les concours/années, voir
# logx_storage section PORTÉE CONCOURS) et /log/archive ne purge que sur
# clear=true : des QSO d'un concours précédent restent NORMALEMENT en log.
# Sans filtre de portée dans _serial_max_used_locked, le 1er QSO du concours
# suivant sur la même bande recevait max_historique+1 (ex. 801) au lieu de 1 —
# numéro d'échange faux transmis sur l'air, sans recours opérateur (champ
# readOnly, allocation serveur). Régression vs l'ancien compteur client
# (logx_logbook.js:nextSerial comptait sur /log/list DÉJÀ filtré par portée).

def test_nouveau_concours_repart_de_1_malgre_concours_precedent():
    """Scénario exact du bug : concours précédent non purgé (num_sent 800 sur
    40 m), nouveau concours actif -> le 1er numéro doit être 1, pas 801."""
    _reset()
    storage.shared_log[:] = [{'call': 'DL1AA', 'band': '40', 'mode': 'SSB',
                              'contest': 'REF_CDF_HF_SSB', 'date': '20260125',
                              'time': '12:00', 'num_sent': '800'}]
    assert storage.allocate_next_serial('40', 'CQ_WPX_SSB#2026') == 1
    assert storage.peek_next_serial('40', 'CQ_WPX_SSB#2026') == 2


def test_meme_concours_edition_precedente_repart_de_1():
    """Même concours, édition 2025 restée en log : l'édition 2026 est une
    portée DISTINCTE (contest#année) et repart de 1."""
    _reset()
    storage.shared_log[:] = [{'call': 'DL1AA', 'band': '40', 'mode': 'SSB',
                              'contest': 'CQ_WPX_SSB', 'date': '20250329',
                              'time': '12:00', 'num_sent': '800'}]
    assert storage.peek_next_serial('40', 'CQ_WPX_SSB#2026') == 1
    assert storage.allocate_next_serial('40', 'CQ_WPX_SSB#2026') == 1


def test_log_perso_non_tague_ignore_en_mode_concours():
    """Import ADIF avec STX (num_sent) dans le log perso NON tagué : ne doit
    jamais compter pour un concours précis (qso_scope_id='' ne matche aucune
    portée non vide)."""
    _reset()
    storage.shared_log[:] = [{'call': 'F5ABC', 'band': '40', 'num_sent': '057'}]
    assert storage.allocate_next_serial('40', 'CQ_WPX_SSB#2026') == 1


def test_meme_portee_reprend_bien_apres_le_max_du_concours():
    """Le filtre de portée ne doit PAS casser la reprise : un QSO du MÊME
    concours/édition déjà loggué (autre poste, redémarrage) compte toujours."""
    _reset()
    storage.shared_log[:] = [
        {'call': 'DL1AA', 'band': '40', 'contest': 'CQ_WPX_SSB',
         'date': '20260328', 'num_sent': '005'},
        {'call': 'DL2BB', 'band': '40', 'contest': 'REF_CDF_HF_SSB',
         'date': '20260125', 'num_sent': '800'},   # autre concours : ignoré
    ]
    assert storage.allocate_next_serial('40', 'CQ_WPX_SSB#2026') == 6


def test_haute_eau_isolee_par_portee_sans_redemarrage():
    """Changement de concours SANS redémarrage serveur : la haute-eau mémoire
    du concours A (clé (scope, bande)) ne doit pas contaminer le concours B."""
    _reset()
    assert storage.allocate_next_serial('40', 'REF_CDF_HF_SSB#2026') == 1
    assert storage.allocate_next_serial('40', 'REF_CDF_HF_SSB#2026') == 2
    assert storage.allocate_next_serial('40', 'CQ_WPX_SSB#2026') == 1   # pas 3
    # Retour au concours A : sa propre séquence continue, pas de retour à 1
    assert storage.allocate_next_serial('40', 'REF_CDF_HF_SSB#2026') == 3


def test_sans_portee_comportement_historique_conserve():
    """scope_id vide (mode simple / aucun concours sélectionné) : tout le log
    compte, exactement comme avant (même règle que /log/list non filtré)."""
    _reset()
    storage.shared_log[:] = [{'call': 'DL1AA', 'band': '40',
                              'contest': 'CQ_WPX_SSB', 'date': '20260328',
                              'num_sent': '042'}]
    assert storage.allocate_next_serial('40') == 43


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
    srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), httpmod.Handler)
    port = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        yield f'http://127.0.0.1:{port}'
    finally:
        srv.shutdown()
        srv.server_close()   # libere la socket d ecoute
        t.join(timeout=5)


def _get(base, path):
    # Correctif audit sécurité (logx_http.py) : consommer réellement un n° de
    # série (hors ?peek=1) exige désormais le jeton de session — même
    # démarche que les autres tests qui exercent le VRAI serveur HTTP.
    req = urllib.request.Request(base + path,
                                 headers={'Cookie': 'rc_token=%s' % httpmod.AUTH_TOKEN})
    with urllib.request.urlopen(req, timeout=5) as r:
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


def test_endpoint_nouveau_concours_repart_de_001(server):
    """Bout en bout via le VRAI endpoint (celui appelé par logx_logbook.js:
    nextSerial et logx_mobile.html) : concours précédent resté dans shared_log
    (num_sent 800 sur 40 m), concours actif différent dans la config serveur
    -> le handler doit transmettre la portée active (cfg_scope_id) et
    renvoyer 001, pas 801."""
    _reset()
    storage.shared_log[:] = [{'call': 'DL1AA', 'band': '40', 'mode': 'SSB',
                              'contest': 'REF_CDF_HF_SSB', 'date': '20260125',
                              'time': '12:00', 'num_sent': '800'}]
    with httpmod.config_lock:
        saved_cfg = dict(httpmod.current_config)
        httpmod.current_config.clear()
        httpmod.current_config.update({'contest': 'CQ_WPX_SSB',
                                       'contest_start_date': '2026-03-28',
                                       'usage_mode': 'contest'})
    try:
        assert _get(server, '/log/next_serial?band=40&peek=1')['serial'] == '001'
        assert _get(server, '/log/next_serial?band=40')['serial'] == '001'
        assert _get(server, '/log/next_serial?band=40')['serial'] == '002'
    finally:
        with httpmod.config_lock:
            httpmod.current_config.clear()
            httpmod.current_config.update(saved_cfg)


def test_endpoint_sans_jeton_refuse_403_et_ne_consomme_rien(server):
    """Correctif audit sécurité (logx_http.py:_require_auth) testé seulement
    dans le sens positif jusqu'ici (_get() ci-dessus fournit toujours un
    jeton valide) : une consommation réelle (hors ?peek=1) SANS jeton doit
    être rejetée en 403 — pas seulement acceptée faute de test dans ce sens."""
    _reset()
    req = urllib.request.Request(server + '/log/next_serial?band=144')
    try:
        urllib.request.urlopen(req, timeout=5)
        assert False, "la requête sans jeton aurait dû être rejetée (403)"
    except urllib.error.HTTPError as e:
        assert e.code == 403
    # Rien n'a dû être consommé : le premier VRAI appel authentifié reste 001
    assert _get(server, '/log/next_serial?band=144')['serial'] == '001'


def test_endpoint_peek_sans_jeton_reste_accepte(server):
    """Exception volontaire documentée dans logx_http.py : ?peek=1 est sans
    effet de bord (aucune consommation du compteur) et reste donc ouvert au
    LAN sans jeton de session, contrairement à l'allocation réelle testée
    juste au-dessus."""
    _reset()
    req = urllib.request.Request(server + '/log/next_serial?band=144&peek=1')
    with urllib.request.urlopen(req, timeout=5) as r:
        res = json.loads(r.read().decode('utf-8'))
    assert res['serial'] == '001'


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
