# -*- coding: utf-8 -*-
"""Synchro LAN directe entre postes LogX — SANS dossier cloud.

Deux postes LogX sur le même réseau se DÉCOUVRENT (beacon UDP diffusé) puis
échangent leurs QSO en HTTP (chacun tire le log de l'autre et fusionne). C'est
l'alternative à logx_cloudsync (qui, lui, passe par un dossier partagé
Dropbox/Synology) quand les postes n'ont qu'un WiFi commun.

CONTRAINTE EXPÉDITION (15 jours 24/7) : tout est borné pour ne jamais fuir.
  - UN seul thread de fond (le même émet le beacon ET écoute), une seule socket.
  - Registre de pairs BORNÉ par TTL (purge à chaque lecture) — un poste éteint
    disparaît tout seul, aucune accumulation.
  - Tirage HTTP borné par timeout ; les pairs sont des IP (pas de DNS non borné).
  - Aucun thread par pair, aucune connexion persistante.

Best-effort de bout en bout : jamais d'exception vers l'appelant. Désactivé par
défaut (config `lan_sync_enabled`).
"""
import json
import socket
import threading
import time
import urllib.request

BEACON_PORT = 8073          # port UDP fixe de découverte LogX
BEACON_INTERVAL_S = 15      # émission du beacon
PEER_TTL_S = 60             # un pair muet depuis plus longtemps est oublié
PULL_TIMEOUT_S = 4          # tirage HTTP d'un pair

_peers = {}                 # ip -> {http_port, callsign, iid, last_seen}
_peers_lock = threading.Lock()
_started = False
_start_lock = threading.Lock()
_get_cfg = None             # fourni par start()
_HTTP_PORT = 8080           # port HTTP réel de CE serveur (annoncé dans le beacon)

# Identifiant de CETTE machine — réutilise celui de cloudsync (persistant, unique
# par installation) pour qu'un poste ne se synchronise jamais avec lui-même.
def _my_iid():
    try:
        import logx_cloudsync as cs
        return cs._instance_id()
    except Exception:
        return 'local'


def _lan_enabled(cfg):
    return str((cfg or {}).get('lan_sync_enabled', '')) in ('1', 'true', 'True', 'on', True)


def _my_beacon(cfg):
    return json.dumps({
        'logx': 1,
        'iid': _my_iid(),
        'http_port': _HTTP_PORT,
        'call': (cfg or {}).get('callsign_contest') or (cfg or {}).get('callsign') or '',
    }).encode('utf-8')


# ─── REGISTRE DES PAIRS ──────────────────────────────────────────────────────

def note_beacon(ip, raw):
    """Enregistre un beacon reçu (ip = émetteur). Ignore le nôtre et le bruit.
    Séparé de la boucle réseau pour être testable sans socket."""
    try:
        d = json.loads(raw.decode('utf-8') if isinstance(raw, (bytes, bytearray)) else raw)
    except Exception:
        return
    if not isinstance(d, dict) or d.get('logx') != 1:
        return
    iid = str(d.get('iid') or '')
    if not iid or iid == _my_iid():
        return                       # notre propre beacon (diffusion revient à nous)
    try:
        port = int(d.get('http_port') or 8080)
    except (TypeError, ValueError):
        port = 8080
    with _peers_lock:
        _peers[ip] = {'http_port': port, 'callsign': str(d.get('call') or ''),
                      'iid': iid, 'last_seen': time.time()}


def peers():
    """Pairs vivants (purge le TTL au passage). Liste de dicts avec 'ip'."""
    now = time.time()
    with _peers_lock:
        for ip in [ip for ip, p in _peers.items() if now - p['last_seen'] > PEER_TTL_S]:
            del _peers[ip]
        return [dict(ip=ip, **p) for ip, p in _peers.items()]


# ─── TIRAGE + FUSION ─────────────────────────────────────────────────────────

def _key(q):
    return (str(q.get('call', '')).upper().strip(), str(q.get('band', '')),
            str(q.get('mode', '')).upper(), str(q.get('date', '')), str(q.get('time', '')))


def _http_get_json(url, timeout):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return json.loads(r.read().decode('utf-8', 'replace'))
    except Exception:
        return None


def pull_and_merge(get_log, add_qso, timeout=PULL_TIMEOUT_S):
    """Tire le log de chaque pair et fusionne les QSO NEUFS via add_qso.

    Pré-filtre par clé (call/bande/mode/date/heure) contre notre log AVANT
    d'appeler add_qso : évite de repayer le scoring + l'écriture disque pour un
    QSO qu'on a déjà (add_qso reste l'autorité de déduplication par portée).
    Retourne {'peers', 'pulled'}."""
    peers_now = peers()
    if not peers_now:
        return {'peers': 0, 'pulled': 0}
    existing = set(_key(q) for q in (get_log() or []))
    pulled = 0
    for p in peers_now:
        data = _http_get_json('http://%s:%d/log/lan/export' % (p['ip'], p['http_port']), timeout)
        if not data:
            continue
        for q in (data.get('qsos') or []):
            if not isinstance(q, dict):
                continue
            k = _key(q)
            if k in existing:
                continue
            try:
                ok = add_qso(dict(q))
            except Exception:
                ok = False
            if ok:
                existing.add(k)
                pulled += 1
    return {'peers': len(peers_now), 'pulled': pulled}


# ─── BOUCLE RÉSEAU (beacon + écoute, un seul thread) ─────────────────────────

def _run():
    sock = None
    last_beacon = 0.0
    while True:
        try:
            cfg = (_get_cfg() if _get_cfg else {}) or {}
        except Exception:
            cfg = {}
        if not _lan_enabled(cfg):
            # Désactivé (ou plus activé) : on ferme la socket et on dort. Réactivé
            # plus tard, la boucle la rouvrira toute seule.
            if sock is not None:
                try:
                    sock.close()
                except Exception:
                    pass
                sock = None
            time.sleep(5)
            continue
        if sock is None:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                sock.bind(('', BEACON_PORT))
                sock.settimeout(1.0)
            except Exception:
                sock = None
                time.sleep(5)
                continue
        # Émission périodique du beacon
        now = time.time()
        if now - last_beacon >= BEACON_INTERVAL_S:
            last_beacon = now
            try:
                sock.sendto(_my_beacon(cfg), ('255.255.255.255', BEACON_PORT))
            except Exception:
                pass
        # Écoute (bornée par settimeout) — met à jour le registre des pairs
        try:
            raw, addr = sock.recvfrom(2048)
            note_beacon(addr[0], raw)
        except socket.timeout:
            pass
        except Exception:
            time.sleep(1)


def start(get_cfg, http_port=8080):
    """Démarre la découverte LAN (idempotent). `get_cfg` : callable -> config ;
    `http_port` : le port HTTP réel de CE serveur, annoncé dans le beacon."""
    global _started, _get_cfg, _HTTP_PORT
    _get_cfg = get_cfg
    try:
        _HTTP_PORT = int(http_port) or 8080
    except (TypeError, ValueError):
        _HTTP_PORT = 8080
    with _start_lock:
        if _started:
            return
        _started = True
        threading.Thread(target=_run, name='lan-sync-discovery', daemon=True).start()
        print('[LAN-SYNC] Découverte démarrée (UDP %d)' % BEACON_PORT)
