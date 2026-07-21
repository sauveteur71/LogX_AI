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
"""
import socket
import threading

DEFAULT_HOST = '127.0.0.1'
DEFAULT_PORT = 4532
TIMEOUT_S = 2.0

_lock = threading.Lock()  # une commande CAT à la fois (rigctld est séquentiel)


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


def _command(host, port, cmd):
    """Envoie UNE commande rigctld et retourne ses lignes de réponse.
    Le protocole répond soit des valeurs (une par ligne), soit 'RPRT n'
    (n=0 succès) pour les commandes de réglage."""
    with _lock:
        with socket.create_connection((host, port), timeout=TIMEOUT_S) as s:
            s.settimeout(TIMEOUT_S)
            s.sendall((cmd + '\n').encode('ascii', errors='replace'))
            buf = b''
            while b'\n' not in buf or (cmd[0] in 'Ff mM' and not _complete(cmd, buf)):
                chunk = s.recv(256)
                if not chunk:
                    break
                buf = buf + chunk
                if buf.endswith(b'\n') and _complete(cmd, buf):
                    break
            return [l.strip() for l in buf.decode('ascii', errors='replace').splitlines() if l.strip()]


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


def _rprt_ok(lines):
    return bool(lines) and lines[-1].replace(' ', '') in ('RPRT0',)


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
        _command(host, port, '\\stop_morse')
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
