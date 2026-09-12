# -*- coding: utf-8 -*-
"""Client KISS live -- SSDV Phase 2, réception (cadrage
docs/superpowers/specs/2026-09-11-ssdv-phase2-transport-cadrage.md, validé
par F4GLD : Direwolf + client KISS maison).

LogX AI est CLIENT TCP d'un port que Direwolf expose (contrairement à
WSJT-X, UDP, où LogX AI ÉCOUTE -- voir logx_wsjtx.start_listener) : une
reconnexion avec recul exponentiel est donc nécessaire (Direwolf peut ne
pas encore tourner, ou redémarrer). Idempotence et thread démon : même
patron que start_listener().

Port par défaut : 8001, exemple conventionnel documenté dans les
commentaires de configuration du code source de Direwolf lui-même
(`KISSPORT 8001 1`, src/kissnet.c, wb2osz/direwolf) -- pas un défaut
figé garanti si `KISSPORT` est omis côté Direwolf, mais l'usage
conventionnel du projet. Toujours réglable via config (ssdv.kiss_port).

Validation faite dans ce dépôt : bout-en-bout contre un flux SIMULÉ (faux
serveur TCP local qui rejoue exactement ce qu'un vrai Direwolf enverrait,
voir test_ssdv_reception.py). Validation contre un flux radio RÉEL
(carte son + TNC/Direwolf effectif) hors de portée de ce dépôt de code --
question 2 du cadrage, non bloquante."""
import socket
import threading
import time

import logx_ax25 as ax25
import logx_kiss as kiss
import logx_ssdv as ssdv

DEFAULT_HOST = '127.0.0.1'
DEFAULT_PORT = 8001
DELAI_RECONNEXION_MIN = 2.0
DELAI_RECONNEXION_MAX = 30.0

_lock = threading.Lock()
_started = False
_arret = threading.Event()
_thread = None

_status_lock = threading.Lock()
status = {
    'connected': False,
    'host': None,
    'port': None,
    'last_seen': None,
    'paquets_recus': 0,
    'trames_ignorees': 0,
    'derniere_erreur': '',
}


def kiss_settings(cfg):
    ssdv_cfg = (cfg or {}).get('ssdv', {}) or {}
    try:
        port = int(ssdv_cfg.get('kiss_port') or DEFAULT_PORT)
    except (TypeError, ValueError):
        port = DEFAULT_PORT
    return {
        'enabled': bool(ssdv_cfg.get('kiss_enabled')),
        'host': ssdv_cfg.get('kiss_host') or DEFAULT_HOST,
        'port': port,
    }


def _traiter_trame_kiss(corps_kiss, on_paquet_ssdv):
    """corps_kiss : octet de commande KISS + charge, déjà dé-encadré par
    logx_kiss.extraire_trames(). Ignore silencieusement tout ce qui n'est
    pas une trame de données SSDV valide -- Direwolf transporte aussi de
    l'APRS ordinaire sur le même port, ce n'est jamais une erreur."""
    if not corps_kiss:
        return
    commande = corps_kiss[0] & 0x0F
    if commande != 0x00:
        return
    try:
        entete_ax25 = ax25.parser_entete(corps_kiss[1:])
    except ValueError:
        with _status_lock:
            status['trames_ignorees'] += 1
        return
    paquet = ssdv.paquet_depuis_trame_ax25(entete_ax25)
    if paquet is None:
        with _status_lock:
            status['trames_ignorees'] += 1
        return
    try:
        ssdv.parser_entete(paquet)   # validation structurelle complète avant d'accepter
    except ValueError:
        with _status_lock:
            status['trames_ignorees'] += 1
        return
    with _status_lock:
        status['paquets_recus'] += 1
        status['last_seen'] = time.time()
    on_paquet_ssdv(paquet)


def _boucle_connexion(host, port, on_paquet_ssdv):
    """Une connexion TCP, jusqu'à coupure ou arrêt demandé. Lève OSError/
    ConnectionError sur toute coupure anormale -- l'appelant décide de la
    reconnexion, cette fonction ne fait qu'UNE session."""
    with socket.create_connection((host, port), timeout=10) as sock:
        sock.settimeout(1.0)
        with _status_lock:
            status.update(connected=True, host=host, port=port, derniere_erreur='')
        tampon = b''
        while not _arret.is_set():
            try:
                morceau = sock.recv(4096)
            except socket.timeout:
                continue
            if not morceau:
                raise ConnectionError("Direwolf a fermé la connexion")
            tampon += morceau
            trames, tampon = kiss.extraire_trames(tampon)
            for corps in trames:
                _traiter_trame_kiss(corps, on_paquet_ssdv)


def demarrer_client_kiss(get_cfg, on_paquet_ssdv, host=None, port=None):
    """Démarre le client KISS en thread de fond (idempotent). `get_cfg()`
    n'est pas encore consulté à chaque reconnexion dans cet incrément
    (host/port figés au démarrage) -- relire la config en direct est un
    raffinement possible, pas nécessaire pour la validation sur flux
    simulé ni pour un premier usage réel."""
    global _started, _thread
    with _lock:
        if _started:
            return
        _started = True
    _arret.clear()

    def _run():
        global _started
        h = host or DEFAULT_HOST
        p = port or DEFAULT_PORT
        delai = DELAI_RECONNEXION_MIN
        try:
            while not _arret.is_set():
                try:
                    _boucle_connexion(h, p, on_paquet_ssdv)
                    delai = DELAI_RECONNEXION_MIN   # session propre -> le backoff repart de zéro
                except (OSError, ConnectionError) as e:
                    with _status_lock:
                        status['connected'] = False
                        status['derniere_erreur'] = str(e)
                    print(f"[SSDV/KISS] connexion a {h}:{p} echouee : {e} "
                          f"-- nouvelle tentative dans {delai:.1f}s")
                if _arret.is_set():
                    break
                if _arret.wait(delai):
                    break
                delai = min(delai * 2, DELAI_RECONNEXION_MAX)
        finally:
            with _status_lock:
                status['connected'] = False
            with _lock:
                _started = False

    _thread = threading.Thread(target=_run, daemon=True)
    _thread.start()


def arreter_client_kiss(attendre=False):
    """Signale l'arrêt propre. En production le thread démon meurt avec le
    process, cet appel n'est pas nécessaire.

    `attendre=True` (utilisé par les tests, PAS par le serveur en
    production) rejoint réellement le thread avant de rendre la main --
    sans ça, le thread reste vivant jusqu'à ~1 s de plus (timeout du
    `recv()` en cours), et un test suivant qui redémarre le client, ou
    même un tout autre fichier de test plus loin dans une suite complète,
    peut se retrouver en concurrence avec ce thread mourant pour des
    ressources socket/OS -- régression réellement observée : la suite
    complète restait verte SANS ce fichier de tests, et échouait de façon
    reproductible AVEC lui sur un test HTTP sans rapport
    (test_theme_inline.py, timeout socket) tant que ce join manquait."""
    _arret.set()
    if attendre and _thread is not None:
        _thread.join(timeout=5)
