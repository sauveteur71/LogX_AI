# -*- coding: utf-8 -*-
"""Pilotage du rotor d'antenne — DEUX protocoles.

1. rotctld (Hamlib) : le protocole réseau texte universel. rotctld tourne sur
   le PC relié au boîtier (port 4533 par défaut) et parle un protocole trivial :
       p            → lit la position → "azimut\\nélévation"
       P 120 0      → pointe l'antenne sur azimut 120°, élévation 0°
       S            → stoppe le mouvement
   C'est la couche qui pilote TOUTES les marques (Yaesu, SPID, Pro.Sis.Tel,
   Hy-Gain, M2…) dès qu'on lance `rotctl -l` pour trouver le n° de son modèle.

2. GS-232 (natif, TCP) : le protocole ASCII des boîtiers Yaesu GS-232A/B et
   Kenpro, et surtout celui que PstRotator, microHam et la plupart des boîtiers
   exposent sur un port TCP. LogX le parle DIRECTEMENT, sans rotctld :
       C   / C2         → lit l'azimut (et l'élévation) → "+0aaa" ou "AZ=aaa"
       Maaa             → pointe l'azimut aaa (000-360/450)
       Waaa eee         → pointe azimut + élévation (boîtiers Az/El, ex. G-5500)
       S                → stoppe

L'azimut est DÉJÀ calculé partout dans l'app (boussole du logbook, cap sur
chaque spot) : le rotor ne fait que l'appliquer. Le décalage mécanique du
pylône (offset_deg) est appliqué en amont, côté appelant.

Fonctionnalité DÉSACTIVÉE par défaut. Toute erreur réseau retourne un dict
{'ok': False, 'error': ...} — jamais d'exception vers le serveur HTTP.
"""
import re
import socket
import threading
import concurrent.futures as _cf

from logx_utils import _rprt_ok

DEFAULT_HOST = '127.0.0.1'
DEFAULT_PORT = 4533        # rotctld ; un serveur GS-232 TCP est souvent en 4001
TIMEOUT_S = 3.0            # un rotor peut être lent à répondre

_lock = threading.Lock()   # rotctld/GS-232 sont séquentiels
_EXECUTOR = _cf.ThreadPoolExecutor(max_workers=2, thread_name_prefix='rotor_cat')


# ─── CATALOGUE DES MARQUES ───────────────────────────────────────────────────
# But : que l'opérateur RECONNAISSE son rotor et sache comment le brancher,
# plutôt que de deviner un numéro de modèle Hamlib. Chaque modèle porte son
# protocole conseillé et s'il gère l'ÉLÉVATION (satellite/EME) — ce qui décide
# l'affichage du champ élévation et de la commande envoyée (W plutôt que M).
#
# Volontairement SANS numéro de modèle Hamlib codé en dur : ils changent d'une
# version de Hamlib à l'autre, et une valeur fausse enverrait l'opérateur lancer
# le mauvais `-m`. La bonne source est `rotctl -l` sur SON installation — c'est
# ce que dit la note. Les modèles 'gs232' sont pilotés en natif : aucun numéro
# n'est alors nécessaire.
ROTOR_BRANDS = [
    {'brand': 'Yaesu', 'proto': 'gs232', 'note':
        "Protocole GS-232 : pilotage DIRECT par LogX (boîtier GS-232A/B, ou "
        "via un serveur TCP type ser2net). Le G-5500 gère l'élévation "
        "(satellite/EME).",
     'models': [
        {'model': 'G-450 / G-550', 'elevation': False},
        {'model': 'G-800DXA / G-1000DXC', 'elevation': False},
        {'model': 'G-2800DXC', 'elevation': False},
        {'model': 'G-5500 (Az + El)', 'elevation': True},
        {'model': 'GS-232A / GS-232B (boîtier)', 'elevation': True},
     ]},
    {'brand': 'Kenpro', 'proto': 'gs232', 'note':
        "Compatible GS-232 (l'ancêtre des Yaesu) — pilotage natif.",
     'models': [
        {'model': 'KR-2000 / KR-2400', 'elevation': False},
        {'model': 'KR-5400 / KR-5600 (Az + El)', 'elevation': True},
     ]},
    {'brand': 'Hy-Gain', 'proto': 'rotctld', 'note':
        "Protocole DCU-1 (ou contrôleur Green Heron). Pilotage via Hamlib "
        "rotctld : lance `rotctl -l` pour le n° de ton modèle. Azimut seul.",
     'models': [
        {'model': 'Ham-IV', 'elevation': False},
        {'model': 'T2X Tailtwister', 'elevation': False},
        {'model': 'DCU-1 (contrôleur)', 'elevation': False},
     ]},
    {'brand': 'SPID', 'proto': 'rotctld', 'note':
        "Vis sans fin autobloquante, protocole binaire ROT2PROG/ROT1PROG. "
        "Pilotage via Hamlib rotctld (`rotctl -l`). Le ROT2 gère l'élévation "
        "(satellite/EME).",
     'models': [
        {'model': 'BIG-RAS/HR', 'elevation': False},
        {'model': 'ROT1PROG', 'elevation': False},
        {'model': 'ROT2PROG (Az + El)', 'elevation': True},
        {'model': 'RAU / RAK', 'elevation': False},
     ]},
    {'brand': 'Pro.Sis.Tel', 'proto': 'rotctld', 'note':
        "Haut de gamme / contest, protocole Prosistel « D ». Pilotage via "
        "Hamlib rotctld (`rotctl -l`).",
     'models': [
        {'model': 'PST-2051D', 'elevation': False},
        {'model': 'PST-61', 'elevation': False},
        {'model': 'PST-641', 'elevation': False},
        {'model': 'Combo Az/El (Big/Small)', 'elevation': True},
     ]},
    {'brand': 'M2 Antenna Systems', 'proto': 'rotctld', 'note':
        "Très robuste (tempêtes, EME). Contrôleur RC2800 via Hamlib rotctld.",
     'models': [
        {'model': 'RC2800', 'elevation': False},
        {'model': 'RC2800PX (Az + El)', 'elevation': True},
     ]},
    {'brand': 'Alfa Radio', 'proto': 'rotctld', 'note':
        "AlfaSpid, dérivés du protocole SPID ROT2. Pilotage via Hamlib rotctld.",
     'models': [
        {'model': 'AlfaSpid RAK', 'elevation': False},
        {'model': 'AlfaSpid RAS (Az + El)', 'elevation': True},
     ]},
    {'brand': 'Autre / générique', 'proto': 'rotctld', 'note':
        "PstRotator, microHam et la plupart des boîtiers exposent un serveur "
        "GS-232 en TCP : choisis alors le protocole GS-232 et l'IP:port du "
        "serveur. Sinon, Hamlib rotctld couvre tout le reste (`rotctl -l`).",
     'models': [
        {'model': 'Serveur GS-232 en TCP (PstRotator/microHam)', 'elevation': True},
        {'model': 'via Hamlib rotctld', 'elevation': False},
     ]},
]

PROTOS = ('rotctld', 'gs232')


def catalog():
    """Le catalogue des marques/modèles, pour l'UI CONFIG (/rotor/models)."""
    return ROTOR_BRANDS


def model_info(brand, model):
    """{'proto', 'elevation'} d'un couple marque/modèle, ou None si inconnu.
    Sert à décider la commande (W avec élévation, sinon M) et l'affichage."""
    b = str(brand or '').strip().lower()
    m = str(model or '').strip().lower()
    for br in ROTOR_BRANDS:
        if br['brand'].lower() != b:
            continue
        for md in br['models']:
            if md['model'].lower() == m:
                return {'proto': br['proto'], 'elevation': bool(md['elevation'])}
        return {'proto': br['proto'], 'elevation': False}
    return None


def _norm_proto(proto):
    p = str(proto or '').strip().lower()
    return p if p in PROTOS else 'rotctld'


def rotor_settings(cfg):
    """Réglages rotor depuis la config CLIENT (prioritaire) puis config.json."""
    cfg = cfg or {}
    enabled = bool(cfg.get('rotor_enabled'))
    host = (cfg.get('rotor_host') or '').strip()
    port = cfg.get('rotor_port')
    proto = cfg.get('rotor_proto')
    brand = cfg.get('rotor_brand')
    model = cfg.get('rotor_model')
    if not host or not port:
        try:
            import json
            with open('config.json', encoding='utf-8') as f:
                rot = (json.load(f).get('rotor', {}) or {})
            enabled = enabled or bool(rot.get('enabled'))
            host = host or rot.get('host', '')
            port = port or rot.get('port')
            proto = proto or rot.get('proto')
            brand = brand or rot.get('brand')
            model = model or rot.get('model')
        except Exception:
            pass
    try:
        port = int(port)
    except (TypeError, ValueError):
        port = DEFAULT_PORT
    return {'enabled': enabled, 'host': host or DEFAULT_HOST, 'port': port,
            'proto': _norm_proto(proto), 'brand': str(brand or '').strip(),
            'model': str(model or '').strip()}


# ─── rotctld (Hamlib) ────────────────────────────────────────────────────────

_ROTCTLD_MAX_BUF = 4096  # une réponse rotctld légitime tient sur quelques
                          # lignes très courtes ; au-delà, le serveur ne
                          # répond pas comme prévu — mieux vaut échouer que de
                          # laisser `buf` grossir tant qu'il reçoit des octets
                          # avant le timeout TIMEOUT_S (même garde-fou que
                          # _gs232_txrx pour l'autre transport).


def _rotctld_command(host, port, cmd, expect_lines=1):
    """Envoie UNE commande rotctld et retourne ses lignes de réponse."""
    def _do():
        with socket.create_connection((host, port), timeout=TIMEOUT_S) as s:
            s.settimeout(TIMEOUT_S)
            s.sendall((cmd + '\n').encode('ascii', errors='replace'))
            buf = b''
            while True:
                lines = [l for l in buf.decode('ascii', 'replace').splitlines() if l.strip()]
                if lines and lines[-1].startswith('RPRT'):
                    break
                if len(lines) >= expect_lines and not cmd.startswith(('P ', 'S')):
                    break
                if len(buf) >= _ROTCTLD_MAX_BUF:
                    break
                chunk = s.recv(128)
                if not chunk:
                    break
                buf = buf + chunk
            return [l.strip() for l in buf.decode('ascii', 'replace').splitlines() if l.strip()]
    with _lock:
        # create_connection() ne borne pas la résolution DNS (getaddrinfo) —
        # un hôte LAN mal résolu bloquerait indéfiniment ce thread. Executor
        # borné pour garantir un retour même si le thread reste coincé.
        fut = _EXECUTOR.submit(_do)
        return fut.result(timeout=TIMEOUT_S + 3)


def _rotctld_get(host, port):
    lines = _rotctld_command(host, port, 'p', expect_lines=2)
    if not lines or lines[0].startswith('RPRT'):
        return {'ok': False, 'error': f'Réponse rotctld inattendue : {lines}'}
    az = float(lines[0])
    el = float(lines[1]) if len(lines) > 1 and not lines[1].startswith('RPRT') else 0.0
    return {'ok': True, 'azimuth': round(az, 1), 'elevation': round(el, 1)}


def _rotctld_set(host, port, az, el):
    lines = _rotctld_command(host, port, f'P {az:.1f} {el:.1f}')
    if not _rprt_ok(lines):
        return {'ok': False, 'error': f'Refus rotctld : {lines}'}
    return {'ok': True, 'azimuth': round(az, 1), 'elevation': round(el, 1)}


def _rotctld_stop(host, port):
    lines = _rotctld_command(host, port, 'S')
    if not _rprt_ok(lines):
        return {'ok': False, 'error': f'Refus rotctld : {lines}'}
    return {'ok': True}


# ─── GS-232 (natif, TCP) ─────────────────────────────────────────────────────
# Compatible GS-232A (« +0aaa ») ET GS-232B (« AZ=aaa EL=eee »), c'est pourquoi
# le parseur reconnaît les DEUX formes. Les commandes de mouvement (M/W/S) ne
# renvoient rien sur la plupart des boîtiers : on ne lit pas leur réponse.
_GS_AZ = re.compile(r'AZ\s*=?\s*(\d{1,3})', re.I)
_GS_EL = re.compile(r'EL\s*=?\s*(\d{1,3})', re.I)
_GS_PLUS = re.compile(r'\+0*(\d{1,3})')


def _gs232_parse(resp):
    """('AZ=180 EL=045' | '+0180+0045') -> (az, el). None si illisible."""
    az = el = None
    m = _GS_AZ.search(resp)
    if m:
        az = int(m.group(1))
    m = _GS_EL.search(resp)
    if m:
        el = int(m.group(1))
    if az is None:
        nums = _GS_PLUS.findall(resp)
        if nums:
            az = int(nums[0])
            if len(nums) > 1 and el is None:
                el = int(nums[1])
    return az, el


def _gs232_txrx(host, port, cmd, want_reply):
    def _do():
        with socket.create_connection((host, port), timeout=TIMEOUT_S) as s:
            s.settimeout(TIMEOUT_S)
            s.sendall((cmd + '\r').encode('ascii', errors='replace'))
            if not want_reply:
                return ''
            buf = b''
            while b'\r' not in buf and b'\n' not in buf and len(buf) < 256:
                chunk = s.recv(64)
                if not chunk:
                    break
                buf = buf + chunk
            return buf.decode('ascii', 'replace')
    with _lock:
        # create_connection() ne borne pas la résolution DNS (getaddrinfo) —
        # un hôte LAN mal résolu bloquerait indéfiniment ce thread. Executor
        # borné pour garantir un retour même si le thread reste coincé.
        fut = _EXECUTOR.submit(_do)
        return fut.result(timeout=TIMEOUT_S + 3)


def _gs232_get(host, port):
    resp = _gs232_txrx(host, port, 'C2', want_reply=True)
    az, el = _gs232_parse(resp)
    if az is None:
        # Boîtier azimut seul qui ne connaît pas C2 : réessayer avec C.
        resp = _gs232_txrx(host, port, 'C', want_reply=True)
        az, el = _gs232_parse(resp)
    if az is None:
        return {'ok': False, 'error': f'Réponse GS-232 illisible : {resp!r}'}
    return {'ok': True, 'azimuth': round(float(az), 1),
            'elevation': round(float(el or 0), 1)}


def _gs232_set(host, port, az, el):
    # W (azimut + élévation) UNIQUEMENT quand une élévation est demandée : M est
    # universellement compris, y compris par les boîtiers Az/El, alors que W
    # ferait bafouiller un boîtier azimut seul.
    if el and el > 0:
        cmd = 'W%03d %03d' % (int(round(az)) % 360, int(round(el)))
    else:
        cmd = 'M%03d' % (int(round(az)) % 360)
    _gs232_txrx(host, port, cmd, want_reply=False)
    return {'ok': True, 'azimuth': round(float(az), 1),
            'elevation': round(float(el or 0), 1)}


def _gs232_stop(host, port):
    _gs232_txrx(host, port, 'S', want_reply=False)
    return {'ok': True}


# ─── DISPATCH PUBLIC ─────────────────────────────────────────────────────────

def get_position(host, port, proto='rotctld'):
    """Position courante. {'ok', 'azimuth', 'elevation'} ou {'ok': False}."""
    proto = _norm_proto(proto)
    try:
        return _gs232_get(host, port) if proto == 'gs232' else _rotctld_get(host, port)
    except Exception as e:
        nom = 'GS-232' if proto == 'gs232' else 'rotctld'
        return {'ok': False, 'error': f'{nom} injoignable ({e})'}


def set_position(host, port, azimuth, elevation=0, proto='rotctld'):
    """Pointe l'antenne : azimut 0-360°, élévation 0-90°."""
    proto = _norm_proto(proto)
    try:
        az = max(0.0, min(360.0, float(azimuth)))
        el = max(0.0, min(90.0, float(elevation or 0)))
    except (TypeError, ValueError):
        return {'ok': False, 'error': 'Azimut/élévation invalide'}
    try:
        return (_gs232_set(host, port, az, el) if proto == 'gs232'
                else _rotctld_set(host, port, az, el))
    except Exception as e:
        nom = 'GS-232' if proto == 'gs232' else 'rotctld'
        return {'ok': False, 'error': f'{nom} injoignable ({e})'}


def stop(host, port, proto='rotctld'):
    proto = _norm_proto(proto)
    try:
        return _gs232_stop(host, port) if proto == 'gs232' else _rotctld_stop(host, port)
    except Exception as e:
        nom = 'GS-232' if proto == 'gs232' else 'rotctld'
        return {'ok': False, 'error': f'{nom} injoignable ({e})'}
