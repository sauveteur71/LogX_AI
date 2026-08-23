# -*- coding: utf-8 -*-
"""Pilotage CAT du transceiver via Hamlib rigctld (protocole réseau texte).

rigctld est LE standard multi-marques (Icom/Yaesu/Kenwood/Elecraft...) :
il tourne sur le PC relié à la radio (port 4532 par défaut) — qui peut être
un AUTRE poste du LAN — et parle un protocole texte trivial :
    f            → lit la fréquence (Hz)
    F 14032000   → règle la fréquence
    m            → lit mode + passband
    M CW 500     → règle le mode
    b TEXTE      → manipule le TEXTE en CW (keyer de la radio)
    \\stop_morse  → stoppe l'envoi CW

Fonctionnalité DÉSACTIVÉE par défaut : activer dans CONFIG (mode expert),
ou section "rig" de config.json. Toute erreur réseau retourne un dict
{'ok': False, 'error': ...} — jamais d'exception vers le serveur HTTP.

Connexion TCP persistante (une par (host, port), réutilisée entre commandes)
plutôt qu'une connexion neuve à chaque appel : le polling bande/mode
(adaptivePoll côté client, plusieurs fois par minute) ouvrait et fermait
2 connexions à chaque cycle, doublant inutilement la latence handshake TCP.
En cas d'erreur (rigctld redémarré, câble débranché...), la connexion en
cache est abandonnée et UNE reconnexion est tentée avant d'abandonner —
au-delà, l'appelant revoit exactement le même {'ok': False, 'error': ...}
qu'avant ce changement.
"""
import socket
import threading
import concurrent.futures as _cf

from logx_utils import _rprt_ok

DEFAULT_HOST = '127.0.0.1'
DEFAULT_PORT = 4532
TIMEOUT_S = 2.0

_lock = threading.Lock()  # une commande CAT à la fois (rigctld est séquentiel)
_EXECUTOR = _cf.ThreadPoolExecutor(max_workers=2, thread_name_prefix='rig_cat')
_sockets = {}  # (host, port) -> socket connecté, protégé par _lock


def rig_settings(cfg):
    """Réglages rig depuis la config CLIENT (prioritaire) puis config.json."""
    cfg = cfg or {}
    enabled = bool(cfg.get('rig_enabled'))
    host = (cfg.get('rig_host') or '').strip()
    port = cfg.get('rig_port')
    if not host or not port:
        try:
            import json
            with open('config.json', encoding='utf-8') as f:
                rig = (json.load(f).get('rig', {}) or {})
            enabled = enabled or bool(rig.get('enabled'))
            host = host or rig.get('host', '')
            port = port or rig.get('port')
        except Exception:
            pass
    try:
        port = int(port)
    except (TypeError, ValueError):
        port = DEFAULT_PORT
    return {'enabled': enabled, 'host': host or DEFAULT_HOST, 'port': port}


def _drop_socket(host, port):
    """Referme et oublie la connexion en cache pour (host, port) — appelé
    dès qu'un échange échoue, pour qu'un prochain appel en ouvre une neuve
    plutôt que de retenter sur un socket dans un état inconnu."""
    s = _sockets.pop((host, port), None)
    if s is not None:
        try:
            s.close()
        except OSError:
            pass


def _get_socket(host, port):
    """Connexion en cache pour (host, port), ou nouvelle connexion si aucune
    n'existe encore (première commande, ou après un _drop_socket() suite à
    une erreur). create_connection() ne borne pas la résolution DNS
    (getaddrinfo) — un hôte LAN mal résolu bloquerait indéfiniment ce thread,
    d'où l'exécution dans l'executor borné de _command() ci-dessous, comme
    avant ce changement."""
    s = _sockets.get((host, port))
    if s is not None:
        return s
    s = socket.create_connection((host, port), timeout=TIMEOUT_S)
    s.settimeout(TIMEOUT_S)
    _sockets[(host, port)] = s
    return s


def _command(host, port, cmd, _retry=True):
    """Envoie UNE commande rigctld et retourne ses lignes de réponse.
    Le protocole répond soit des valeurs (une par ligne), soit 'RPRT n'
    (n=0 succès) pour les commandes de réglage.

    _retry : une seule reconnexion automatique est tentée si la connexion en
    cache s'avère morte (rigctld redémarré, câble débranché puis rebranché,
    timeout réseau) -- pas de boucle de retentatives, une commande CAT ne
    doit jamais rester bloquée en attente sur un lien mort."""
    def _do():
        s = _get_socket(host, port)
        try:
            s.sendall((cmd + '\n').encode('ascii', errors='replace'))
            buf = b''
            while b'\n' not in buf or (cmd[0] in 'Ff mM' and not _complete(cmd, buf)):
                chunk = s.recv(256)
                if not chunk:
                    raise ConnectionError('rigctld a fermé la connexion')
                buf = buf + chunk
                if buf.endswith(b'\n') and _complete(cmd, buf):
                    break
            return [l.strip() for l in buf.decode('ascii', errors='replace').splitlines() if l.strip()]
        except (OSError, ConnectionError):
            _drop_socket(host, port)
            raise
    with _lock:
        fut = _EXECUTOR.submit(_do)
        try:
            return fut.result(timeout=TIMEOUT_S + 3)
        except (OSError, ConnectionError):
            # _do() a déjà nettoyé (_drop_socket) avant de relever -- le
            # thread est terminé, aucune ambiguïté sur l'état du cache : le
            # prochain _get_socket() ouvrira forcément une connexion neuve.
            if not _retry:
                raise
        except _cf.TimeoutError:
            # Résolution DNS bloquée au-delà du timeout socket (le seul cas
            # non couvert par s.settimeout()) : le thread _do() peut rester
            # coincé indéfiniment. Ne PAS retenter dans l'immédiat -- une 2e
            # tentative concurrente sur l'executor à 2 workers finirait par
            # les épuiser tous les deux si l'hôte reste injoignable en DNS.
            # Comportement inchangé par rapport à avant ce changement.
            raise
    # Reconnexion HORS du `with _lock:` ci-dessus (sinon deadlock : _command()
    # reprend le verrou lui-même) -- une seule tentative, jamais en boucle.
    return _command(host, port, cmd, _retry=False)


def _complete(cmd, buf):
    """La réponse est complète ? get freq: 1 ligne ; get mode: 2 lignes ;
    set/morse: 1 ligne RPRT."""
    lines = [l for l in buf.decode('ascii', errors='replace').splitlines() if l.strip()]
    if not lines:
        return False
    if lines[-1].startswith('RPRT'):
        return True
    expected = {'f': 1, 'm': 2}.get(cmd.split()[0], 1)
    return len(lines) >= expected


def get_state(host, port):
    """État courant : fréquence (Hz) + mode. {'ok', 'freq_hz', 'freq_khz', 'mode'}"""
    try:
        freq_lines = _command(host, port, 'f')
        freq = int(freq_lines[0])
        mode_lines = _command(host, port, 'm')
        mode = mode_lines[0] if mode_lines and not mode_lines[0].startswith('RPRT') else ''
        return {'ok': True, 'freq_hz': freq,
                'freq_khz': round(freq / 1000.0, 2), 'mode': mode}
    except Exception as e:
        return {'ok': False, 'error': f'rigctld injoignable ({e})'}


def set_freq(host, port, freq_hz, mode=None):
    """QSY : règle la fréquence (et le mode si fourni)."""
    try:
        lines = _command(host, port, f'F {int(freq_hz)}')
        if not _rprt_ok(lines):
            return {'ok': False, 'error': f'Refus rigctld : {lines}'}
        if mode:
            # Neutralise tout caractère de contrôle : sans ça, un '\n' dans
            # `mode` ferait exécuter à rigctld une commande supplémentaire
            # ('M CW\nT 1' -> QSY puis PTT ON = émission NON demandée) — même
            # injection que send_morse() neutralise déjà (l.188-189).
            mode = ''.join(c if ord(c) >= 0x20 else ' ' for c in str(mode)).strip()
        if mode:
            # passband 0 = défaut de la radio pour ce mode
            _command(host, port, f'M {mode} 0')
        return {'ok': True}
    except Exception as e:
        return {'ok': False, 'error': f'rigctld injoignable ({e})'}


def send_morse(host, port, text):
    """Envoie le texte en CW via le keyer de la radio (rigs compatibles)."""
    text = (text or '').strip()
    if not text:
        return {'ok': False, 'error': 'Texte vide'}
    # Le protocole rigctld sépare les commandes par '\n'. Un texte CW contenant
    # un retour à la ligne ('CQ TEST\nF 7000000\nT 1') ferait exécuter à la radio
    # un QSY et un passage en émission non demandés (injection de commandes).
    # On neutralise tout caractère de contrôle (CR/LF et < 0x20).
    text = ''.join(c if ord(c) >= 0x20 else ' ' for c in text).strip()
    if not text:
        return {'ok': False, 'error': 'Texte vide'}
    try:
        lines = _command(host, port, f'b {text}')
        if not _rprt_ok(lines):
            return {'ok': False, 'error': f'CW refusé par la radio : {lines}'}
        return {'ok': True}
    except Exception as e:
        return {'ok': False, 'error': f'rigctld injoignable ({e})'}


def stop_morse(host, port):
    try:
        lines = _command(host, port, '\\stop_morse')
        if not _rprt_ok(lines):
            return {'ok': False, 'error': f'Arrêt CW refusé par rigctld : {lines}'}
        return {'ok': True}
    except Exception as e:
        return {'ok': False, 'error': f'rigctld injoignable ({e})'}


def set_ptt(host, port, on):
    """Bascule PTT (commande Hamlib standard 'T 1'/'T 0') — pour le keyer
    vocal (logx_voicekeyer.py), même signature que
    logx_cat.set_ptt/logx_tci.set_ptt."""
    try:
        lines = _command(host, port, f"T {1 if on else 0}")
        if not _rprt_ok(lines):
            return {'ok': False, 'error': f'PTT refusé par rigctld : {lines}'}
        return {'ok': True}
    except Exception as e:
        return {'ok': False, 'error': f'rigctld injoignable ({e})'}
