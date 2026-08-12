# -*- coding: utf-8 -*-
"""Réseau ADIF générique : interopérabilité UDP avec les loggers de concours
tiers (N1MM Logger+, DXLog.net, et tout logiciel qui parle le même protocole).

N1MM et DXLog (en mode « style N1MM », coché dans Options|Broadcast) diffusent
chaque QSO validé sous forme d'un datagramme UDP XML <contactinfo> (port par
défaut 12060). C'est le format de facto pour l'interopérabilité temps réel
entre loggers de concours tiers — DXLog l'implémente explicitement pour rester
compatible avec N1MM et les outils qui l'écoutent.

Deux sens, indépendants (mode off/listen/send/both) :
  - RÉCEPTION : on écoute ce port, on parse les <contactinfo> reçus et on les
    insère dans le log partagé via add_qso_to_log (même dédup que la saisie
    manuelle et le pont WSJT-X).
  - ÉMISSION : chaque QSO qu'on ajoute nous-même est rediffusé en <contactinfo>
    (broadcast UDP) pour qu'un N1MM/DXLog voisin (ou tout autre outil à
    l'écoute) le voie apparaître en temps réel.
"""
import socket
import threading
import datetime
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape as _xml_escape
from logx_utils import utcnow, CALL_RE as _CALL_RE, clean_text as _clean_text
from logx_export import resolve_operator_callsign

DEFAULT_PORT = 12060


status = {'listening': False, 'last_seen': 0, 'received_total': 0, 'sent_total': 0}
_status_lock = threading.Lock()
_listener_started = False
_listener_lock = threading.Lock()

_CONTACTINFO_FIELDS = (
    'app', 'contestname', 'contestnr', 'timestamp', 'mycall', 'band',
    'rxfreq', 'txfreq', 'operator', 'mode', 'call', 'gridsquare',
    'snt', 'rcv', 'comment',
)


# ─── RÉGLAGES ─────────────────────────────────────────────────────────────────
def adifnet_settings(cfg):
    cfg = cfg or {}
    mode = str(cfg.get('adifnet_mode', 'off')).strip().lower()
    if mode not in ('off', 'listen', 'send', 'both'):
        mode = 'off'
    try:
        port = int(cfg.get('adifnet_port') or DEFAULT_PORT)
    except (TypeError, ValueError):
        port = DEFAULT_PORT
    target = str(cfg.get('adifnet_target') or '').strip() or '255.255.255.255'
    app_name = str(cfg.get('adifnet_app_name') or '').strip() or 'LogXAI'
    return {
        'mode': mode, 'port': port, 'target': target, 'app_name': app_name,
        'listen': mode in ('listen', 'both'), 'send': mode in ('send', 'both'),
    }


# ─── RÉCEPTION : PARSING <contactinfo> ───────────────────────────────────────
def parse_contactinfo(xml_text):
    """<contactinfo>...</contactinfo> (N1MM/DXLog) -> dict de champs (minuscules),
    ou None si ce n'est pas un message reconnu."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return None
    if root.tag.lower() != 'contactinfo':
        return None
    return {child.tag.lower(): (child.text or '').strip() for child in root}


def _band_from_field(band_str):
    """Le tag <band> de N1MM/DXLog est déjà une valeur MHz proche de notre
    convention interne ('3.5', '7', '14', '144'...) : on la fait passer par
    la même table de plages que le pont WSJT-X pour couvrir les variantes."""
    b = (band_str or '').strip()
    if not b:
        return ''
    try:
        mhz = float(b)
    except ValueError:
        return b
    from logx_wsjtx import _mhz_to_band
    return _mhz_to_band(mhz)


def _parse_timestamp(ts):
    """'2020-01-17 16:43:38' (UTC, format N1MM/DXLog) -> datetime, ou None."""
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M'):
        try:
            return datetime.datetime.strptime(ts, fmt)
        except (ValueError, TypeError):
            continue
    return None


def qso_from_contactinfo(fields, cfg):
    """Champs <contactinfo> bruts -> dict QSO prêt pour le log partagé, ou None
    si le champ 'call' n'a pas la forme d'un indicatif (défense contre un
    datagramme UDP forgé — ce port n'est pas authentifié).
    Le concours (contest) reste celui configuré ICI (comme le pont WSJT-X) :
    le champ contestname du logger tiers est purement informatif, l'insertion
    doit rejoindre le concours actif de CETTE instance pour que le scoring
    (rules_db) s'applique correctement."""
    from logx_utils import locator_to_latlon, haversine
    call = _clean_text(fields.get('call'), 15).upper()
    if not _CALL_RE.match(call):
        return None
    dt = _parse_timestamp(fields.get('timestamp', '')) or utcnow()
    my_loc = (cfg or {}).get('locator', '')
    grid = _clean_text(fields.get('gridsquare'), 8).upper()
    dist = 0
    if grid:
        g6 = grid if len(grid) >= 6 else (grid + 'MM')[:6]
        a, b = locator_to_latlon(my_loc), locator_to_latlon(g6)
        if a[0] is not None and b[0] is not None:
            dist = haversine(a[0], a[1], b[0], b[1])
    return {
        'call': call,
        'band': _band_from_field(fields.get('band', '')),
        'mode': _clean_text(fields.get('mode'), 16).upper(),
        'date': dt.strftime('%Y%m%d'), 'time': dt.strftime('%H:%M'),
        'rst_sent': _clean_text(fields.get('snt'), 8), 'rst_rcvd': _clean_text(fields.get('rcv'), 8),
        'locator': grid, 'dist': dist, 'my_locator': my_loc,
        'contest': (cfg or {}).get('contest', ''),
        'source': 'adifnet:' + (_clean_text(fields.get('app'), 32) or '?'),
        'operator': _clean_text(fields.get('operator'), 32),
        'comment': _clean_text(fields.get('comment'), 128),
    }


# ─── ÉMISSION : CONSTRUCTION <contactinfo> ───────────────────────────────────
def build_contactinfo_xml(qso, cfg):
    """QSO (dict interne) -> XML <contactinfo> (mêmes tags que N1MM/DXLog)."""
    cfg = cfg or {}
    s = adifnet_settings(cfg)
    date = str(qso.get('date', '')).replace('-', '')[:8]
    time_ = str(qso.get('time', '')).replace(':', '')[:4]
    ts = ''
    if date and time_:
        try:
            ts = datetime.datetime.strptime(date + time_, '%Y%m%d%H%M').strftime('%Y-%m-%d %H:%M:%S')
        except ValueError:
            ts = ''
    values = {
        'app': s['app_name'],
        'contestname': cfg.get('contest', ''),
        'contestnr': '', 'timestamp': ts,
        'mycall': cfg.get('callsign_contest', ''),
        'band': qso.get('band', ''), 'rxfreq': '', 'txfreq': '',
        # Jamais l'ID de créneau brut ('OP1') vers un poste N1MM/DXLog voisin —
        # même bug que LOGBOOK/export ADIF, voir resolve_operator_callsign.
        'operator': resolve_operator_callsign(qso.get('operator', ''), cfg),
        'mode': qso.get('mode', ''),
        'call': qso.get('call', ''), 'gridsquare': qso.get('locator', ''),
        'snt': qso.get('rst_sent', ''), 'rcv': qso.get('rst_rcvd', ''),
        'comment': qso.get('comment', ''),
    }
    parts = ['<?xml version="1.0" encoding="utf-8"?>', '<contactinfo>']
    for k in _CONTACTINFO_FIELDS:
        parts.append('<%s>%s</%s>' % (k, _xml_escape(str(values.get(k, ''))), k))
    parts.append('</contactinfo>')
    return ''.join(parts)


def broadcast_qso(qso, cfg):
    """Diffuse un QSO en <contactinfo> UDP (fire-and-forget). Ne lève jamais."""
    s = adifnet_settings(cfg)
    if not s['send']:
        return False
    try:
        xml_text = build_contactinfo_xml(qso, cfg).encode('utf-8')
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.sendto(xml_text, (s['target'], s['port']))
        finally:
            sock.close()
        with _status_lock:
            status['sent_total'] += 1
        return True
    except Exception:
        return False


# ─── ÉCOUTEUR UDP (réception) ─────────────────────────────────────────────────
def start_listener(get_cfg, add_qso, port=DEFAULT_PORT):
    """Démarre l'écouteur UDP en thread de fond (idempotent).
    get_cfg() -> config courante ; add_qso(qso_dict) -> insère dans le log."""
    global _listener_started
    with _listener_lock:
        if _listener_started:
            return
        _listener_started = True

    def _run():
        global _listener_started
        import time
        RATE_WINDOW = 1.0
        RATE_MAX_PER_SOURCE = 20   # paquets/s max par source — un vrai N1MM en envoie quelques-uns/minute
        GLOBAL_RATE_MAX = 100      # plafond agrégé, toutes sources confondues
        PRUNE_EVERY = 60.0         # purge périodique de last_by_addr (évite une fuite mémoire sur 15 j)
        last_by_addr = {}
        global_bucket = []
        last_prune = time.time()
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(('0.0.0.0', port))
            sock.settimeout(1.0)
            print(f"[ADIFNET] Ecoute UDP sur le port {port}")
        except Exception as e:
            print(f"[ADIFNET] Impossible d'ecouter le port {port}: {e}")
            # Bind raté : on relâche le drapeau (même correctif que
            # logx_wsjtx.py) pour qu'une tentative ultérieure (port libéré
            # entre-temps) puisse redémarrer l'écouteur — sinon plus JAMAIS,
            # même si le port se libère, tant que le process tourne.
            with _listener_lock:
                _listener_started = False
            return
        while True:
            try:
                data, addr = sock.recvfrom(8192)
            except socket.timeout:
                continue
            except Exception:
                continue
            now = time.time()

            # Purge périodique : sans ça, last_by_addr grossit indéfiniment sur
            # une expédition de 15 jours si de nombreuses IPs sources distinctes
            # (légitimes ou usurpées — l'usurpation UDP intra-LAN ne demande pas
            # de privilège particulier) sont vues au moins une fois.
            if now - last_prune > PRUNE_EVERY:
                last_by_addr = {k: v for k, v in last_by_addr.items()
                                 if v and now - v[-1] < RATE_WINDOW}
                last_prune = now

            # Plafond agrégé : borne le coût total (scan log + scoring + écriture
            # disque, tous sous log_lock partagé avec le serveur HTTP) même si de
            # nombreuses sources distinctes restent chacune sous leur seuil.
            global_bucket[:] = [t for t in global_bucket if now - t < RATE_WINDOW]
            if len(global_bucket) >= GLOBAL_RATE_MAX:
                continue

            bucket = last_by_addr.setdefault(addr[0], [])
            bucket[:] = [t for t in bucket if now - t < RATE_WINDOW]
            if len(bucket) >= RATE_MAX_PER_SOURCE:
                continue
            bucket.append(now)
            global_bucket.append(now)

            fields = parse_contactinfo(data.decode('utf-8', 'replace'))
            if not fields or not fields.get('call'):
                continue
            with _status_lock:
                status['listening'] = True
                status['last_seen'] = time.time()
            try:
                qso = qso_from_contactinfo(fields, get_cfg() or {})
                if qso is None:
                    continue
                res = add_qso(qso)
                if res:
                    with _status_lock:
                        status['received_total'] += 1
                    print(f"[ADIFNET] +QSO recu {qso['call']} {qso['band']} {qso['mode']} "
                          f"(source={fields.get('app', '?')})")
            except Exception as e:
                print(f"[ADIFNET] Erreur auto-log: {e}")

    threading.Thread(target=_run, daemon=True).start()


def current_status():
    import time
    with _status_lock:
        s = dict(status)
    s['listening'] = s['listening'] and (time.time() - s['last_seen'] < 30)
    return s
