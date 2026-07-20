# -*- coding: utf-8 -*-
"""Pilotage du rotor d'antenne via Hamlib rotctld (protocole réseau texte).

rotctld est au rotor ce que rigctld est à la radio : il tourne sur le PC
relié au boîtier de commande (port 4533 par défaut) et parle un protocole
texte trivial :
    p            → lit la position → "azimut\\nélévation"
    P 120 0      → pointe l'antenne sur azimut 120°, élévation 0°
    S            → stoppe le mouvement

L'azimut est DÉJÀ calculé partout dans l'app (boussole du logbook, cap sur
chaque spot via bearing/cardinal) : le rotor ne fait que l'appliquer.

Fonctionnalité DÉSACTIVÉE par défaut : activer dans CONFIG (mode expert),
ou section "rotor" de config.json. Toute erreur réseau retourne un dict
{'ok': False, 'error': ...} — jamais d'exception vers le serveur HTTP.
"""
import socket
import threading

DEFAULT_HOST = '127.0.0.1'
DEFAULT_PORT = 4533
TIMEOUT_S = 3.0        # un rotor peut être lent à répondre

_lock = threading.Lock()  # rotctld est séquentiel


def rotor_settings(cfg):
    """Réglages rotor depuis la config CLIENT (prioritaire) puis config.json."""
    cfg = cfg or {}
    enabled = bool(cfg.get('rotor_enabled'))
    host = (cfg.get('rotor_host') or '').strip()
    port = cfg.get('rotor_port')
    if not host or not port:
        try:
            import json
            with open('config.json', encoding='utf-8') as f:
                rot = (json.load(f).get('rotor', {}) or {})
            enabled = enabled or bool(rot.get('enabled'))
            host = host or rot.get('host', '')
            port = port or rot.get('port')
        except Exception:
            pass
    try:
        port = int(port)
    except (TypeError, ValueError):
        port = DEFAULT_PORT
    return {'enabled': enabled, 'host': host or DEFAULT_HOST, 'port': port}


def _command(host, port, cmd, expect_lines=1):
    """Envoie UNE commande rotctld et retourne ses lignes de réponse."""
    with _lock:
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
                chunk = s.recv(128)
                if not chunk:
                    break
                buf = buf + chunk
            return [l.strip() for l in buf.decode('ascii', 'replace').splitlines() if l.strip()]


def _rprt_ok(lines):
    return bool(lines) and lines[-1].replace(' ', '') == 'RPRT0'


def get_position(host, port):
    """Position courante. {'ok', 'azimuth', 'elevation'}"""
    try:
        lines = _command(host, port, 'p', expect_lines=2)
        if not lines or lines[0].startswith('RPRT'):
            return {'ok': False, 'error': f'Réponse rotctld inattendue : {lines}'}
        az = float(lines[0])
        el = float(lines[1]) if len(lines) > 1 and not lines[1].startswith('RPRT') else 0.0
        return {'ok': True, 'azimuth': round(az, 1), 'elevation': round(el, 1)}
    except Exception as e:
        return {'ok': False, 'error': f'rotctld injoignable ({e})'}


def set_position(host, port, azimuth, elevation=0):
    """Pointe l'antenne : azimut 0-360°, élévation 0-90°."""
    try:
        az = max(0.0, min(360.0, float(azimuth)))
        el = max(0.0, min(90.0, float(elevation)))
        lines = _command(host, port, f'P {az:.1f} {el:.1f}')
        if not _rprt_ok(lines):
            return {'ok': False, 'error': f'Refus rotctld : {lines}'}
        return {'ok': True, 'azimuth': round(az, 1), 'elevation': round(el, 1)}
    except Exception as e:
        return {'ok': False, 'error': f'rotctld injoignable ({e})'}


def stop(host, port):
    try:
        _command(host, port, 'S')
        return {'ok': True}
    except Exception as e:
        return {'ok': False, 'error': f'rotctld injoignable ({e})'}
