# -*- coding: utf-8 -*-
"""RBN (Reverse Beacon Network) — « où mon signal CW est entendu ».

Complément CW/RTTY du PSK Reporter (qui, lui, ne couvre que le numérique). Le
RBN est un réseau de récepteurs (« skimmers ») qui décodent en continu les
appels CW/RTTY et publient qui ils entendent, avec le rapport signal (SNR) et
la vitesse. On s'y connecte en telnet, on lit quelques secondes, et on garde
les lignes où la station SPOTTÉE est la nôtre → la carte de « qui me reçoit ».

Telnet telnet.reversebeacon.net:7000 (flux CW/RTTY). Réutilise le même modèle
que le cluster DX. Dégrade proprement : si le réseau/telnet est bloqué,
retourne {'ok': False, 'error': ...} sans jamais lever d'exception.
"""
import re
import socket
import time
import threading
import concurrent.futures as _cf

RBN_HOST = 'telnet.reversebeacon.net'
RBN_PORT = 7000            # 7000 = CW/RTTY, 7001 = numérique (redondant avec PSK)

_cache = {'ts': 0, 'data': None, 'call': ''}
CACHE_S = 120
_lock = threading.Lock()
# s.settimeout() borne connect()/recv() mais PAS la résolution DNS de RBN_HOST
# (getaddrinfo(), appel système bloquant hors du socket) : sur un réseau sans
# résolveur joignable (/P, box captive), cette étape peut durer bien plus que
# `timeout` avant même la tentative de connexion. On exécute donc tout le
# dialogue réseau dans un thread jetable et on borne l'ATTENTE du résultat.
_EXECUTOR = _cf.ThreadPoolExecutor(max_workers=2, thread_name_prefix='rbn')

# "DX de F4ABC-#:  14025.0  DL9XYZ  CW    18 dB  28 wpm  CQ    1432Z"
_LINE_RE = re.compile(
    r'DX de\s+([\w/]+?)-?#?\s*[:>]\s*([\d.]+)\s+([\w/]+)\s+(\w+)\s+(\d+)\s*dB'
    r'(?:\s+(\d+)\s*wpm)?', re.IGNORECASE)


def _band_from_khz(khz):
    try:
        from logx_scoring import _band_from_freq
        return _band_from_freq(khz / 1000.0)
    except Exception:
        return ''


def where_heard(my_call, timeout=9):
    """Skimmers RBN qui ont entendu `my_call` récemment. Retourne
    {'ok', 'call', 'count', 'spots':[{spotter, freq_khz, band, mode, snr, wpm}],
    'best_snr', 'bands'} ou {'ok': False, 'error'}."""
    my_call = (my_call or '').upper().strip()
    if not my_call:
        return {'ok': False, 'error': 'Indicatif station non défini'}
    base = my_call.split('/')[0]

    with _lock:
        if (_cache['data'] and _cache['call'] == my_call
                and time.time() - _cache['ts'] < CACHE_S):
            return _cache['data']

    def _dialog():
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        s.connect((RBN_HOST, RBN_PORT))
        # Prompt de login. Recalcule le timeout du socket sur la deadline
        # RÉELLEMENT restante à chaque recv() — sinon un seul recv() peut
        # dépasser à lui seul le budget de la phase (5s ici) jusqu'au timeout
        # du socket (`timeout`, réglé plus large pour la lecture principale).
        buf = b''
        deadline = time.time() + 5
        while time.time() < deadline:
            try:
                s.settimeout(max(0.05, deadline - time.time()))
                chunk = s.recv(1024)
                if not chunk:
                    break
                buf += chunk
                if b'call' in buf.lower() or b'login' in buf.lower() or b'>' in buf:
                    break
            except socket.timeout:
                break
        s.sendall((base + '\r\n').encode())
        # Écoute le flux quelques secondes (même correction de deadline)
        raw = b''
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                s.settimeout(max(0.05, deadline - time.time()))
                chunk = s.recv(4096)
                if not chunk:
                    break
                raw += chunk
            except socket.timeout:
                break
        try:
            s.sendall(b'bye\r\n')
        except Exception:
            pass
        s.close()
        return raw

    try:
        raw = _EXECUTOR.submit(_dialog).result(timeout=timeout + 3)
    except _cf.TimeoutError:
        return {'ok': False, 'error': 'RBN injoignable (délai dépassé, résolution réseau lente)'}
    except Exception as e:
        return {'ok': False, 'error': f'RBN injoignable ({e})'}

    text = raw.decode('utf-8', errors='replace')
    spots = parse_rbn(text, base)
    result = {
        'ok': True, 'call': my_call, 'count': len(spots),
        'spots': spots[:30],
        'best_snr': max((s['snr'] for s in spots), default=None),
        'bands': sorted({s['band'] for s in spots if s['band']}),
    }
    with _lock:
        _cache.update(ts=time.time(), data=result, call=my_call)
    return result


def parse_rbn(text, my_base):
    """Extrait les spots RBN où la station entendue est la mienne
    (déterministe, testable sans réseau)."""
    out = []
    seen = set()
    for m in _LINE_RE.finditer(text or ''):
        spotter, freq_str, call, mode, snr, wpm = m.groups()
        if call.upper().split('/')[0] != my_base:
            continue
        try:
            khz = float(freq_str)
        except ValueError:
            continue
        key = (spotter.upper(), round(khz, 1))
        if key in seen:
            continue
        seen.add(key)
        out.append({
            'spotter': spotter.upper(),
            'freq_khz': khz,
            'band': _band_from_khz(khz),
            'mode': mode.upper(),
            'snr': int(snr),
            'wpm': int(wpm) if wpm else None,
        })
    out.sort(key=lambda x: -x['snr'])
    return out
