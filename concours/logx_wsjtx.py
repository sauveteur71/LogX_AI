# -*- coding: utf-8 -*-
"""Pont WSJT-X → LogX : auto-log FT8/FT4 en temps réel.

WSJT-X diffuse toute son activité en UDP (protocole Qt QDataStream, gros-boutien,
port 2237 par défaut). Deux messages nous intéressent :
  - type 1 « Status »   : bande/fréquence/mode courants → indicateur de liaison.
  - type 5 « QSO Logged » : émis quand l'opérateur valide un QSO dans WSJT-X
    → le contact atterrit AUTOMATIQUEMENT dans le logbook partagé (call, grid,
    bande, mode, rapports, heure), sans ressaisie.

Côté WSJT-X : Réglages → Rapports → « UDP Server » = adresse du PC LogX,
port 2237. Fonctionnalité désactivée par défaut ; activée dans CONFIG.

L'insertion dans le log réutilise la même logique (dédup + scoring) que la
saisie manuelle, via un callback fourni par le serveur.
"""
import re
import socket
import struct
import threading
import datetime

MAGIC = 0xADBCCBDA
DEFAULT_PORT = 2237

# État partagé pour l'indicateur de liaison (widget logbook)
status = {'connected': False, 'last_seen': 0, 'dial_mhz': 0, 'mode': '',
          'tx_mode': '', 'de_call': '', 'logged_total': 0}
_status_lock = threading.Lock()
_listener_started = False
_listener_lock = threading.Lock()


# ─── LECTEUR QDataStream (gros-boutien) ──────────────────────────────────────
class _Reader:
    def __init__(self, data):
        self.d = data
        self.i = 0

    def u32(self):
        v = struct.unpack_from('>I', self.d, self.i)[0]
        self.i += 4
        return v

    def u64(self):
        v = struct.unpack_from('>Q', self.d, self.i)[0]
        self.i += 8
        return v

    def i64(self):
        v = struct.unpack_from('>q', self.d, self.i)[0]
        self.i += 8
        return v

    def i32(self):
        v = struct.unpack_from('>i', self.d, self.i)[0]
        self.i += 4
        return v

    def f64(self):
        v = struct.unpack_from('>d', self.d, self.i)[0]
        self.i += 8
        return v

    def u8(self):
        v = self.d[self.i]
        self.i += 1
        return v

    def utf8(self):
        """Chaîne Qt : longueur u32 (0xffffffff = null) puis octets UTF-8."""
        n = self.u32()
        if n == 0xFFFFFFFF:
            return ''
        s = self.d[self.i:self.i + n].decode('utf-8', 'replace')
        self.i += n
        return s

    def datetime(self):
        """QDateTime Qt : QDate (jour julien i64) + QTime (ms u32) + timespec u8."""
        jdn = self.i64()
        ms = self.u32()
        spec = self.u8()
        if spec == 2:      # OffsetFromUTC : + offset i32
            self.i += 4
        return _jdn_to_datetime(jdn, ms)


def _jdn_to_datetime(jdn, ms):
    """Jour julien + millisecondes → datetime UTC (None si invalide)."""
    try:
        # Algorithme standard (Fliegel & Van Flandern)
        a = jdn + 32044
        b = (4 * a + 3) // 146097
        c = a - (146097 * b) // 4
        d = (4 * c + 3) // 1461
        e = c - (1461 * d) // 4
        m = (5 * e + 2) // 153
        day = e - (153 * m + 2) // 5 + 1
        month = m + 3 - 12 * (m // 10)
        year = 100 * b + d - 4800 + m // 10
        sec = ms // 1000
        return datetime.datetime(year, month, day, sec // 3600,
                                 (sec % 3600) // 60, sec % 60)
    except Exception:
        return None


# ─── PARSING DES MESSAGES ────────────────────────────────────────────────────
def parse_message(data):
    """Retourne un dict décrivant le message, ou None si non pertinent/illisible.
    Types gérés : 1 (Status), 2 (Decode) et 5 (QSO Logged)."""
    if len(data) < 12:
        return None
    r = _Reader(data)
    # TOUTE la lecture — en-tête compris — est protégée : un datagramme avec le
    # bon MAGIC mais tronqué (12 octets pile, ou coupé au milieu de l'id) faisait
    # lever struct.error/IndexError DÈS l'en-tête, hors du try, ce qui remontait
    # jusqu'à la boucle _run et TUAIT le thread d'écoute (plus aucun auto-log
    # jusqu'au redémarrage). N'importe quel logiciel parlant sur le port suffisait.
    try:
        if r.u32() != MAGIC:
            return None
        r.u32()                 # schema version
        mtype = r.u32()
        r.utf8()                # id (nom de l'instance WSJT-X)
        if mtype == 1:      # Status
            dial_hz = r.u64()
            mode = r.utf8()
            r.utf8()        # dx_call
            r.utf8()        # report
            tx_mode = r.utf8()
            return {'type': 'status', 'dial_mhz': round(dial_hz / 1e6, 4),
                    'mode': mode, 'tx_mode': tx_mode}
        if mtype == 2:      # Decode : un décodage affiché dans le waterfall (PAS un QSO)
            r.u8()          # 'new' (bool) — pas utilisé
            r.u32()         # heure du jour (QTime, ms depuis minuit) — IGNORÉE : le
                            # cache recent_decodes() se base sur l'horloge du serveur
                            # pour sa fraîcheur (TTL), inutile de gérer le passage de
                            # minuit UTC d'un QTime qui ne porte pas la date.
            r.i32()         # SNR — pas utilisé (alerte binaire, pas de tri par signal)
            r.f64()         # delta temps (s) — idem
            delta_hz = r.u32()
            mode = r.utf8()
            message = r.utf8()
            return {'type': 'decode', 'mode': mode, 'message': message, 'delta_hz': delta_hz}
        if mtype == 5:      # QSO Logged
            time_off = r.datetime()
            call = r.utf8()
            grid = r.utf8()
            dial_hz = r.u64()
            mode = r.utf8()
            rpt_sent = r.utf8()
            rpt_recv = r.utf8()
            r.utf8()        # tx_power
            r.utf8()        # comments
            r.utf8()        # name
            time_on = r.datetime()
            return {'type': 'qso_logged', 'call': call, 'grid': grid,
                    'dial_mhz': round(dial_hz / 1e6, 4), 'mode': mode,
                    'rpt_sent': rpt_sent, 'rpt_recv': rpt_recv,
                    'time_on': time_on or time_off}
    except (struct.error, IndexError):
        return None
    return None


def _mhz_to_band(mhz):
    """Fréquence dial (MHz) → bande interne."""
    # Bandes WARC (30/17/12 m) mappées sur LEUR propre code interne — pas sur
    # la bande contest voisine : un QSO 30 m rabattu sur '7' (40 m) faussait la
    # déduplication, la Worked Matrix, les diplômes DXCC par bande et l'export.
    for lo, hi, b in ((1.8, 2.0, '1.8'), (3.5, 4.0, '3.5'), (7.0, 7.3, '7'),
                      (10.1, 10.15, '10.1'), (14.0, 14.35, '14'), (18.0, 18.2, '18'),
                      (21.0, 21.45, '21'), (24.8, 25.0, '24'), (28.0, 29.7, '28'),
                      (50, 54, '50'), (70, 71, '70'), (144, 148, '144'),
                      (430, 440, '432')):
        if lo <= mhz <= hi:
            return b
    return str(int(mhz)) if mhz else ''


# ─── ALERTE « DXCC/DÉPARTEMENT MANQUANT » (façon GridTracker) ────────────────
# GridTracker (référence de l'écosystème FT8) colore/alerte un décodage qui
# correspond à un pays/département JAMAIS travaillé — sa fonction la plus
# plébiscitée. Ici : on extrait le(s) indicatif(s) de chaque message Decode
# (type 2, un par station ENTENDUE dans le waterfall — pas un QSO) et on les
# garde en cache le temps qu'ils restent "actifs". Le croisement avec le log
# (DXCC déjà travaillé/confirmé à VIE) est fait côté logx_http.py via
# logx_awards.spotted_new_ones() — déjà écrite pour exactement la même
# question posée aux spots du cluster DX, pas de logique dupliquée ici.
_GRID_RE = re.compile(r'^[A-X]{2}\d{2}([A-X]{2})?$')
_CALL_RE = re.compile(r'^[0-9A-Z]{1,4}\d[A-Z]{1,4}(?:/[0-9A-Z]{1,4})?$')
_REPORT_RE = re.compile(r'^R?[+-]\d{2}$')
_DECODE_SKIP_TOKENS = {'CQ', 'QRZ', 'DE', 'RRR', 'RR73', '73', 'TNX', 'TU',
                       'DX', 'TEST', 'POTA', 'SOTA', 'WWFF', 'IOTA', 'AGN'}
_DECODE_TTL = 300     # 5 min : au-delà, une station décodée n'est plus "active"

_decodes = {}         # call -> {'band','freq_mhz','mode','last_seen'}
_decodes_lock = threading.Lock()


def extract_calls(message, my_call=''):
    """Indicatifs plausibles dans un message décodé FT8/FT4 (ex. « CQ F4ABC
    JN18 », « F4ABC F5XYZ +05 », « F4ABC F5XYZ RR73 ») — exclut les grilles
    Maidenhead, les rapports, les jokers usuels (CQ/DX/POTA...) et mon propre
    indicatif. Parsing volontairement simple (PAS un décodeur FT8 complet
    comme WSJT-X lui-même) : suffisant pour savoir QUI est entendu, pas pour
    rejouer tout l'échange."""
    my = (my_call or '').upper().strip()
    out = []
    for tok in (message or '').upper().replace('<', '').replace('>', '').split():
        if tok in _DECODE_SKIP_TOKENS or _REPORT_RE.match(tok) or _GRID_RE.match(tok):
            continue
        base = tok.split('/')[0]
        if my and (tok == my or base == my):
            continue
        if _CALL_RE.match(tok):
            out.append(tok)
    return out


def _decode_freq_mhz(msg):
    """Fréquence réelle du décodage (MHz) = dial courant (dernier message
    Status reçu) + décalage audio (delta_hz) du décodage. 0 si le dial n'est
    pas encore connu (aucun Status reçu depuis le démarrage de l'écoute)."""
    with _status_lock:
        dial = status.get('dial_mhz') or 0
    if not dial:
        return 0
    return round(dial + (msg.get('delta_hz', 0) or 0) / 1e6, 4)


def record_decode(msg, my_call=''):
    """Message Decode (type 2) -> enregistre le(s) indicatif(s) entendus dans
    le cache des décodages récents (voir recent_decodes()). Isolé de _run()
    pour rester testable sans socket UDP. Purge au passage les entrées
    expirées (cache borné : pas de fuite mémoire sur une session de plusieurs
    jours d'activité FT8/FT4 continue)."""
    calls = extract_calls(msg.get('message', ''), my_call)
    if not calls:
        return []
    import time
    freq_mhz = _decode_freq_mhz(msg)
    band = _mhz_to_band(freq_mhz) if freq_mhz else ''
    mode = msg.get('mode') or ''
    now = time.time()
    with _decodes_lock:
        for c in calls:
            _decodes[c] = {'band': band, 'freq_mhz': freq_mhz, 'mode': mode, 'last_seen': now}
        cutoff = now - _DECODE_TTL
        for k in [k for k, v in _decodes.items() if v['last_seen'] < cutoff]:
            del _decodes[k]
    return calls


def recent_decodes(max_age=_DECODE_TTL):
    """Décodages FT8/FT4 encore « actifs » (call, band, freq_mhz, mode,
    last_seen) — consommé par _wsjtx_state_dict() (logx_http.py) pour
    l'alerte DXCC/département manquant façon GridTracker."""
    import time
    cutoff = time.time() - max_age
    with _decodes_lock:
        return [dict(call=c, **v) for c, v in _decodes.items() if v['last_seen'] >= cutoff]


def _my_call(cfg):
    """Indicatif réellement émis par la station (celui que WSJT-X transmet),
    PAS op_call (opérateur responsable du log, souvent différent en
    multi-opérateurs) — repli sur l'indicatif personnel si aucun indicatif de
    concours n'est renseigné."""
    cfg = cfg or {}
    return (cfg.get('callsign_contest') or cfg.get('callsign') or '').upper().strip()


def qso_from_logged(msg, cfg):
    """Message QSO Logged → dict QSO prêt pour le log partagé."""
    from logx_utils import locator_to_latlon, haversine
    dt = msg.get('time_on') or datetime.datetime.utcnow()
    my_loc = (cfg or {}).get('locator', '')
    grid = (msg.get('grid') or '').upper()
    dist = 0
    if grid:
        # WSJT-X envoie une grille 4 caractères (FT8) : la compléter au CENTRE
        # du carré ('FN31' → 'FN31MM') pour la distance ; la grille d'origine
        # reste stockée telle quelle dans le log.
        g6 = grid if len(grid) >= 6 else (grid + 'MM')[:6]
        a, b = locator_to_latlon(my_loc), locator_to_latlon(g6)
        if a[0] is not None and b[0] is not None:
            dist = haversine(a[0], a[1], b[0], b[1])
    return {
        'call': (msg.get('call') or '').upper(),
        'band': _mhz_to_band(msg.get('dial_mhz', 0)),
        'mode': (msg.get('mode') or 'FT8').upper(),
        'date': dt.strftime('%Y%m%d'), 'time': dt.strftime('%H:%M'),
        'rst_sent': msg.get('rpt_sent', ''), 'rst_rcvd': msg.get('rpt_recv', ''),
        'locator': (msg.get('grid') or '').upper(), 'dist': dist,
        'my_locator': my_loc, 'contest': (cfg or {}).get('contest', ''),
        'source': 'wsjtx', 'operator': (cfg or {}).get('op_call', ''),
    }


# ─── ÉCOUTEUR UDP ─────────────────────────────────────────────────────────────
def wsjtx_settings(cfg):
    cfg = cfg or {}
    enabled = bool(cfg.get('wsjtx_enabled'))
    port = cfg.get('wsjtx_port')
    if not enabled or not port:
        try:
            import json
            with open('config.json', encoding='utf-8') as f:
                w = (json.load(f).get('wsjtx', {}) or {})
            enabled = enabled or bool(w.get('enabled'))
            port = port or w.get('port')
        except Exception:
            pass
    try:
        port = int(port)
    except (TypeError, ValueError):
        port = DEFAULT_PORT
    return {'enabled': enabled, 'port': port}


def start_listener(get_cfg, add_qso, port=DEFAULT_PORT):
    """Démarre l'écouteur UDP en thread de fond (idempotent).
    get_cfg() -> config courante ; add_qso(qso_dict) -> insère dans le log."""
    global _listener_started
    # Check-then-set sous verrou : deux /wsjtx/state simultanés ne peuvent plus
    # lancer deux threads sur le même port.
    with _listener_lock:
        if _listener_started:
            return
        _listener_started = True

    def _run():
        global _listener_started
        import time
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(('0.0.0.0', port))
            sock.settimeout(1.0)
            print(f"[WSJTX] Ecoute UDP sur le port {port}")
        except Exception as e:
            print(f"[WSJTX] Impossible d'ecouter le port {port}: {e}")
            # Bind raté : on relâche le drapeau pour qu'une tentative ultérieure
            # (port libéré entre-temps) puisse redémarrer l'écouteur.
            with _listener_lock:
                _listener_started = False
            return
        while True:
            try:
                data, _ = sock.recvfrom(8192)
            except socket.timeout:
                continue
            except Exception:
                continue
            msg = parse_message(data)
            if not msg:
                continue
            with _status_lock:
                status['connected'] = True
                status['last_seen'] = time.time()
                if msg.get('dial_mhz'):
                    status['dial_mhz'] = msg['dial_mhz']
                if msg.get('mode'):
                    status['mode'] = msg['mode']
            if msg['type'] == 'qso_logged':
                try:
                    qso = qso_from_logged(msg, get_cfg() or {})
                    if qso['call']:
                        res = add_qso(qso)
                        if res:
                            with _status_lock:
                                status['logged_total'] += 1
                            print(f"[WSJTX] +QSO auto {qso['call']} {qso['band']}MHz {qso['mode']}")
                except Exception as e:
                    print(f"[WSJTX] Erreur auto-log: {e}")
            elif msg['type'] == 'decode':
                # Alerte DXCC/département manquant (voir recent_decodes()) —
                # le croisement avec le log se fait côté logx_http.py, ici on
                # ne fait qu'alimenter le cache des décodages entendus.
                try:
                    record_decode(msg, _my_call(get_cfg() or {}))
                except Exception as e:
                    print(f"[WSJTX] Erreur decode: {e}")

    threading.Thread(target=_run, daemon=True).start()


def current_status():
    import time
    with _status_lock:
        s = dict(status)
    # « connecté » = un datagramme reçu il y a moins de 30 s
    s['connected'] = s['connected'] and (time.time() - s['last_seen'] < 30)
    return s
