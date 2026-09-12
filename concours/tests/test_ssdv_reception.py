# -*- coding: utf-8 -*-
"""Tests du client KISS live (SSDV Phase 2, réception) -- logx_ssdv_reception.

Validation « flux simulé » demandée par F4GLD : un vrai serveur TCP local
(socket) tient lieu de Direwolf dans ces tests -- même charge KISS/AX.25/
SSDV qu'un vrai poste enverrait, aucun matériel radio requis. La
validation « flux radio réel » (carte son + TNC/Direwolf effectif) reste
hors de portée de ce dépôt de code (question 2 du cadrage, pas bloquante).
"""
import os
import socket
import sys
import threading
import time

import pytest

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE not in sys.path:
    sys.path.insert(0, BASE)

import logx_ax25 as ax25          # noqa: E402
import logx_kiss as kiss          # noqa: E402
import logx_ssdv as ssdv          # noqa: E402
import logx_ssdv_reception as rx  # noqa: E402


def _champ_adresse(indicatif, ssid=0, dernier=False):
    indicatif = indicatif.upper().ljust(6)[:6]
    lettres = bytes((ord(c) << 1) & 0xFF for c in indicatif)
    ssid_octet = 0x60 | ((ssid & 0x0F) << 1) | (1 if dernier else 0)
    return lettres + bytes([ssid_octet])


def _paquet_ssdv(packet_id=0, indicatif='F4GLD', image_id=1, eoi=False):
    valeur = ssdv.encoder_indicatif_base40(indicatif)
    fanions = ((4 ^ 4) << 3) | ((1 if eoi else 0) << 2)
    entete = bytes([
        ssdv.SYNC, 0x66 + ssdv.TYPE_NOFEC,
        (valeur >> 24) & 0xFF, (valeur >> 16) & 0xFF, (valeur >> 8) & 0xFF, valeur & 0xFF,
        image_id & 0xFF, (packet_id >> 8) & 0xFF, packet_id & 0xFF,
        320 // 16, 240 // 16, fanions, 0, 0xFF, 0xFF,
    ])
    return entete + bytes(ssdv.TAILLE_PAQUET - len(entete))


def _trame_kiss_ssdv(paquet_ssdv, destination='APRS', source='F4GLD'):
    trame_ax25 = (_champ_adresse(destination) + _champ_adresse(source, dernier=True)
                  + bytes([ax25.CONTROLE_UI, ax25.PID_PAS_DE_COUCHE_3]) + paquet_ssdv)
    return kiss.encadrer(trame_ax25)


class _FauxDirewolf:
    """Serveur TCP local minimal : accepte une connexion, envoie les octets
    qu'on lui donne via .envoyer(), reste ouvert jusqu'à .fermer()."""

    def __init__(self):
        self._srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._srv.bind(('127.0.0.1', 0))
        self._srv.listen(1)
        self.port = self._srv.getsockname()[1]
        self._conn = None
        self._th = threading.Thread(target=self._accepter, daemon=True)
        self._th.start()

    def _accepter(self):
        try:
            self._conn, _ = self._srv.accept()
        except OSError:
            pass

    def attendre_connexion(self, timeout=5):
        fin = time.time() + timeout
        while time.time() < fin:
            if self._conn is not None:
                return True
            time.sleep(0.02)
        return False

    def envoyer(self, octets):
        assert self._conn is not None, "aucun client connecté"
        self._conn.sendall(octets)

    def fermer_connexion_client(self):
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def fermer(self):
        self.fermer_connexion_client()
        self._srv.close()
        self._th.join(timeout=2)   # ne rend la main qu'une fois le thread d'accept() réellement mort


@pytest.fixture(autouse=True)
def _stop_apres_chaque_test():
    yield
    # attendre=True : rejoint réellement le thread avant le test suivant --
    # sans ce join, un thread de reconnexion pouvait encore être vivant au
    # moment où un fichier de test SANS RAPPORT tournait plus loin dans une
    # suite complète, causant un timeout socket ailleurs (régression réelle,
    # voir docstring d'arreter_client_kiss).
    rx.arreter_client_kiss(attendre=True)
    with rx._lock:
        rx._started = False


def test_traiter_trame_kiss_appelle_le_rappel_sur_paquet_valide():
    paquet = _paquet_ssdv(packet_id=7)
    trame = _trame_kiss_ssdv(paquet)
    trames, _ = kiss.extraire_trames(trame)
    recus = []
    rx._traiter_trame_kiss(trames[0], recus.append)
    assert recus == [paquet]


def test_traiter_trame_kiss_ignore_trame_non_ssdv_silencieusement():
    # une trame AX.25 ordinaire (message texte court, pas 256 octets)
    trame_ax25 = (_champ_adresse('APRS') + _champ_adresse('F4GLD', dernier=True)
                  + bytes([ax25.CONTROLE_UI, ax25.PID_PAS_DE_COUCHE_3]) + b'CQ CQ DE F4GLD')
    trame_kiss = kiss.encadrer(trame_ax25)
    trames, _ = kiss.extraire_trames(trame_kiss)
    recus = []
    rx._traiter_trame_kiss(trames[0], recus.append)   # ne doit pas lever
    assert recus == []


def test_traiter_trame_kiss_commande_non_donnees_ignoree():
    recus = []
    rx._traiter_trame_kiss(bytes([0x01]) + bytes(300), recus.append)
    assert recus == []


def test_traiter_trame_kiss_vide_ne_leve_pas():
    rx._traiter_trame_kiss(b'', lambda p: None)   # ne doit pas lever


def test_client_kiss_recoit_un_paquet_sur_flux_simule():
    """Bout-en-bout complet : vrai socket TCP -> extraction KISS -> AX.25
    -> SSDV, sur un serveur local qui simule Direwolf."""
    faux = _FauxDirewolf()
    recus = []
    try:
        rx.demarrer_client_kiss(lambda: {}, recus.append, host='127.0.0.1', port=faux.port)
        assert faux.attendre_connexion(), "le client ne s'est pas connecté"
        paquet = _paquet_ssdv(packet_id=3)
        faux.envoyer(_trame_kiss_ssdv(paquet))

        fin = time.time() + 5
        while time.time() < fin and not recus:
            time.sleep(0.02)
        assert recus == [paquet]
        with rx._status_lock:
            assert rx.status['connected'] is True
            assert rx.status['paquets_recus'] >= 1
    finally:
        faux.fermer()


def test_client_kiss_trame_coupee_sur_deux_envois_reste_reconstituee():
    """Le tampon TCP peut couper une trame en deux paquets réseau -- le
    client doit la reconstituer (même garantie que logx_kiss.extraire_
    trames testée en isolation, vérifiée ici bout-en-bout sur un vrai
    socket)."""
    faux = _FauxDirewolf()
    recus = []
    try:
        rx.demarrer_client_kiss(lambda: {}, recus.append, host='127.0.0.1', port=faux.port)
        assert faux.attendre_connexion()
        trame = _trame_kiss_ssdv(_paquet_ssdv(packet_id=9))
        coupe = len(trame) - 5
        faux.envoyer(trame[:coupe])
        time.sleep(0.2)
        faux.envoyer(trame[coupe:])

        fin = time.time() + 5
        while time.time() < fin and not recus:
            time.sleep(0.02)
        assert len(recus) == 1
    finally:
        faux.fermer()


def test_client_kiss_idempotent_deux_demarrages(monkeypatch):
    """Vacant une première fois (constaté en mutant la garde check-then-set :
    la suite restait verte) -- renforcé pour compter les VRAIES tentatives
    de connexion plutôt que de ne relire que le drapeau interne."""
    appels = []
    orig = rx.socket.create_connection

    def _compte(*a, **k):
        appels.append(1)
        return orig(*a, **k)
    monkeypatch.setattr(rx.socket, 'create_connection', _compte)

    faux = _FauxDirewolf()
    try:
        rx.demarrer_client_kiss(lambda: {}, lambda p: None, host='127.0.0.1', port=faux.port)
        rx.demarrer_client_kiss(lambda: {}, lambda p: None, host='127.0.0.1', port=faux.port)
        assert faux.attendre_connexion()
        time.sleep(0.3)
        assert len(appels) == 1, "un 2e démarrage a déclenché une 2e tentative de connexion"
    finally:
        faux.fermer()


def test_client_kiss_reconnecte_apres_coupure(monkeypatch):
    """Backoff : après une coupure, le client retente -- vérifié avec un
    délai minimal réduit pour ne pas ralentir la suite."""
    monkeypatch.setattr(rx, 'DELAI_RECONNEXION_MIN', 0.05)
    monkeypatch.setattr(rx, 'DELAI_RECONNEXION_MAX', 0.2)
    faux = _FauxDirewolf()
    recus = []
    try:
        rx.demarrer_client_kiss(lambda: {}, recus.append, host='127.0.0.1', port=faux.port)
        assert faux.attendre_connexion()
        faux.fermer_connexion_client()   # coupe la connexion du côté serveur

        # le client doit se reconnecter tout seul
        faux._th = threading.Thread(target=faux._accepter, daemon=True)
        faux._th.start()
        assert faux.attendre_connexion(timeout=5), "le client ne s'est pas reconnecté"

        paquet = _paquet_ssdv(packet_id=1)
        faux.envoyer(_trame_kiss_ssdv(paquet))
        fin = time.time() + 5
        while time.time() < fin and not recus:
            time.sleep(0.02)
        assert recus == [paquet]
    finally:
        faux.fermer()


def test_client_kiss_backoff_croit_et_plafonne(monkeypatch):
    """Chaque échec de connexion doit DOUBLER le délai avant la prochaine
    tentative (jusqu'au plafond) -- sans ça, un Direwolf indisponible ferait
    boucler le client en tentatives serrées, inutilement bruyant. Aucune
    vraie attente : `_arret.wait` est intercepté pour enregistrer les
    délais demandés sans jamais réellement dormir."""
    monkeypatch.setattr(rx, 'DELAI_RECONNEXION_MIN', 1.0)
    monkeypatch.setattr(rx, 'DELAI_RECONNEXION_MAX', 5.0)
    delais_demandes = []
    appels = {'n': 0}

    def _connexion_qui_echoue_toujours(*a, **k):
        raise ConnectionRefusedError("port fermé, volontairement, pour ce test")
    monkeypatch.setattr(rx.socket, 'create_connection', _connexion_qui_echoue_toujours)

    orig_wait = rx._arret.wait

    def _wait_intercepte(delai):
        delais_demandes.append(delai)
        appels['n'] += 1
        if appels['n'] >= 5:
            rx._arret.set()   # arrête le test après 5 tentatives, pas avant
            return True
        return False   # ne dort jamais réellement -- juste enregistre et continue
    monkeypatch.setattr(rx._arret, 'wait', _wait_intercepte)

    try:
        rx.demarrer_client_kiss(lambda: {}, lambda p: None, host='127.0.0.1', port=1)
        fin = time.time() + 5
        while time.time() < fin and appels['n'] < 5:
            time.sleep(0.02)
        assert delais_demandes == [1.0, 2.0, 4.0, 5.0, 5.0], delais_demandes
    finally:
        monkeypatch.setattr(rx._arret, 'wait', orig_wait)


def test_kiss_settings_lit_la_config():
    cfg = {'ssdv': {'kiss_enabled': True, 'kiss_host': '10.0.0.5', 'kiss_port': 9001}}
    r = rx.kiss_settings(cfg)
    assert r == {'enabled': True, 'host': '10.0.0.5', 'port': 9001}


def test_kiss_settings_valeurs_par_defaut():
    r = rx.kiss_settings({})
    assert r['enabled'] is False
    assert r['host'] == rx.DEFAULT_HOST
    assert r['port'] == rx.DEFAULT_PORT
