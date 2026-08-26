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
import urllib.parse
import urllib.request

BEACON_PORT = 8073          # port UDP fixe de découverte LogX
BEACON_INTERVAL_S = 15      # émission du beacon
PEER_TTL_S = 60             # un pair muet depuis plus longtemps est oublié
PULL_TIMEOUT_S = 4          # tirage HTTP d'un pair
MAX_PULL_BYTES = 2_000_000  # borne dure sur la taille d'une réponse /log/lan/export
MAX_QSOS_PER_PULL = 500     # borne dure sur le nb de QSO traités par pair et par cycle

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


def _lan_token(cfg):
    """Jeton partagé optionnel (config `lan_sync_token`) : credential RÉEL,
    présenté en ?token= sur GET /log/lan/export (voir logx_http.py) et vérifié
    côté serveur par hmac.compare_digest. Ne JAMAIS le transmettre tel quel
    sur le réseau — voir _discovery_proof() pour ce qui circule dans le
    beacon UDP broadcast (non chiffré, lisible par quiconque sur le LAN)."""
    return str((cfg or {}).get('lan_sync_token', '') or '')


# Preuve HORODATÉE : granularité de la fenêtre temporelle (secondes). La preuve
# est recalculée à chaque créneau -> une preuve sniffée expire au créneau suivant.
_FENETRE_S = 30


def _discovery_proof(cfg, fenetre=None):
    """Dérivé du jeton d'équipe, mis dans le beacon UDP BROADCAST (donc lisible
    par tout appareil du réseau — visiteur WiFi inclus) pour filtrer la liste
    de pairs découverts. Volontairement DIFFÉRENT de _lan_token() : le jeton
    réel ne doit jamais transiter en clair sur le réseau, seulement une
    preuve de possession à sens unique (HMAC-SHA256, non inversible).

    ANTI-REJEU (audit :100) : le message haché inclut le CRÉNEAU temporel
    (`fenetre` = time // _FENETRE_S). La preuve change donc à chaque créneau de
    30 s ; une preuve sniffée sur le beacon et REJOUÉE plus tard n'est plus
    valable. Avant, le message était constant -> preuve fixe rejouable pour
    toujours. `fenetre` explicite = injectable par les tests (déterministe)."""
    token = _lan_token(cfg)
    if not token:
        return ''
    if fenetre is None:
        fenetre = int(time.time() // _FENETRE_S)
    import hmac as _hmac
    msg = ('logx-lan-discovery:%d' % int(fenetre)).encode('utf-8')
    return _hmac.new(token.encode('utf-8'), msg, 'sha256').hexdigest()


def _proofs_acceptables(cfg, maintenant=None):
    """Ensemble des preuves qu'un récepteur accepte MAINTENANT : créneau courant
    ET ±1 (tolérance de décalage d'horloge entre postes). Vide si aucun jeton
    configuré (LAN de confiance ouvert, comportement historique)."""
    if not _lan_token(cfg):
        return set()
    maintenant = time.time() if maintenant is None else maintenant
    w = int(maintenant // _FENETRE_S)
    return {_discovery_proof(cfg, w + d) for d in (-1, 0, 1)}


def _my_beacon(cfg):
    return json.dumps({
        'logx': 1,
        'iid': _my_iid(),
        'http_port': _HTTP_PORT,
        'call': (cfg or {}).get('callsign_contest') or (cfg or {}).get('callsign') or '',
        'token': _discovery_proof(cfg),
    }).encode('utf-8')


# ─── REGISTRE DES PAIRS ──────────────────────────────────────────────────────

def note_beacon(ip, raw, expected_token=''):
    """Enregistre un beacon reçu (ip = émetteur). Ignore le nôtre, le bruit, et
    tout pair qui ne présente pas le jeton partagé attendu (si configuré).
    Séparé de la boucle réseau pour être testable sans socket."""
    try:
        d = json.loads(raw.decode('utf-8') if isinstance(raw, (bytes, bytearray)) else raw)
    except Exception:
        return
    if not isinstance(d, dict) or d.get('logx') != 1:
        return
    # expected_token : '' / ensemble vide -> ouvert (LAN de confiance) ; une
    # chaîne (rétro-compat) OU un ENSEMBLE de preuves acceptables (créneau
    # courant ±1, anti-rejeu -- voir _proofs_acceptables). On refuse tout beacon
    # dont la preuve n'est dans aucun créneau valide.
    if isinstance(expected_token, str):
        attendus = {expected_token} if expected_token else set()
    else:
        attendus = {t for t in (expected_token or ()) if t}
    if attendus and str(d.get('token') or '') not in attendus:
        return                       # preuve absente/périmée/erronée : ignoré
    iid = str(d.get('iid') or '')
    if not iid or iid == _my_iid():
        return                       # notre propre beacon (diffusion revient à nous)
    try:
        port = int(d.get('http_port') or 8080)
    except (TypeError, ValueError):
        port = 8080
    if not (1 <= port <= 65535):
        return
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
            raw = r.read(MAX_PULL_BYTES + 1)
            if len(raw) > MAX_PULL_BYTES:
                return None            # réponse démesurée : rejetée plutôt que tronquée
            return json.loads(raw.decode('utf-8', 'replace'))
    except Exception:
        return None


def _valid_qso(q):
    """Rejette ce qu'aucun /log/add légitime ne produirait, sans bloquer un
    pair valide (validation de forme minimale, pas de déduplication ici)."""
    if not isinstance(q, dict):
        return False
    call = q.get('call')
    if not isinstance(call, str) or not (1 <= len(call) <= 20):
        return False
    for field in ('band', 'mode', 'date', 'time'):
        v = q.get(field)
        if not isinstance(v, str) or len(v) > 20:
            return False
    return True


def pull_and_merge(get_log, add_qso, timeout=PULL_TIMEOUT_S, token=''):
    """Tire le log de chaque pair et fusionne les QSO NEUFS via add_qso.

    Pré-filtre par clé (call/bande/mode/date/heure) contre notre log AVANT
    d'appeler add_qso : évite de repayer le scoring + l'écriture disque pour un
    QSO qu'on a déjà (add_qso reste l'autorité de déduplication par portée).
    Réponse bornée en taille (MAX_PULL_BYTES) et en nombre de QSO traités par
    pair (MAX_QSOS_PER_PULL) : un pair malveillant ne peut infliger qu'un coût
    borné par cycle, même s'il répond avec des dizaines de milliers d'entrées.

    `token` : jeton d'équipe optionnel (voir _lan_token) — transmis en query
    string au pair, qui le vérifie côté serveur avant de répondre (voir
    logx_http.py /log/lan/export). Vide par défaut : rétro-compatible avec un
    pair qui n'a pas encore configuré de jeton.

    Filtre aussi tout QSO distant dont l'id figure dans logx_storage.deleted_qsos
    (suppression locale via /log/delete) — sinon un QSO supprimé ici ressuscite
    au cycle suivant depuis un pair qui l'a encore dans SON log, tant que ce
    pair ne l'a pas supprimé aussi. Même filtre, même mémoire de SESSION que
    logx_cloudsync/logx_mysql_sync pour ce problème identique ; pas de
    tombstone persistant ici (suffisant : la boucle LAN ne tourne que tant
    que le process est vivant).
    Retourne {'peers', 'pulled'}."""
    peers_now = peers()
    if not peers_now:
        return {'peers': 0, 'pulled': 0}
    existing = set(_key(q) for q in (get_log() or []))
    try:
        import logx_storage as storage
        deleted_ids = {d.get('id') for d in list(storage.deleted_qsos)} - {None}
    except Exception:
        deleted_ids = set()
    pulled = 0
    qs = ('?token=' + urllib.parse.quote(token, safe='')) if token else ''
    for p in peers_now:
        data = _http_get_json('http://%s:%d/log/lan/export%s' % (p['ip'], p['http_port'], qs), timeout)
        if not isinstance(data, dict):
            continue
        raw_qsos = data.get('qsos')
        if not isinstance(raw_qsos, list):
            continue
        for q in raw_qsos[:MAX_QSOS_PER_PULL]:
            if not _valid_qso(q):
                continue
            qid = q.get('id')
            if qid is not None and qid in deleted_ids:
                continue                # supprimé localement : jamais ré-importé
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
            note_beacon(addr[0], raw, expected_token=_proofs_acceptables(cfg))
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
