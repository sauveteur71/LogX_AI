# -*- coding: utf-8 -*-
"""Pilotage de relais — panneau "Station Control" (commutation d'antennes ou
d'accessoires par carte relais), DEUX familles de matériel.

1. Série (KMTronic USB Relay, Denkovi USB Relay, et tout boîtier "générique"
   qui suit le même protocole d'octets — c'est le même circuit de commande
   sur la quasi-totalité des cartes relais USB/série bon marché) : protocole
   documenté par KMTronic — 3 octets par commande [0xFF, numéro_relais,
   état] (état: 0x01=ON, 0x00=OFF).

2. WebSwitch (Digital Loggers Web Power Switch) : HTTP, authentification
   Basic, API CGI historique documentée par Digital Loggers —
   GET http://host/outlet?<N>=ON|OFF.

Auto-pilotage depuis la fréquence radio (comme PstRotator, voir logx_rotor.py
et logx_http._rig_state_dict) : maybe_apply_band() ne bascule le relais QUE
quand la bande a réellement changé (pas à chaque poll ~3s) — une carte relais
mécanique s'use à chaque commutation, marteler le même ordre en boucle est un
risque matériel réel, pas juste du bruit réseau.

Fonctionnalité DÉSACTIVÉE par défaut. Toute erreur retourne
{'ok': False, 'error': ...} — jamais d'exception vers le serveur HTTP."""
import base64
import concurrent.futures as _cf
import threading
import urllib.request

from logx_cat import HAS_PYSERIAL, SerialPort

_open_serial = SerialPort if HAS_PYSERIAL else None
_EXECUTOR = _cf.ThreadPoolExecutor(max_workers=2, thread_name_prefix='relay_http')
TIMEOUT_S = 3.0
RELAY_DEFAULT_BAUD = 9600

# Sérialise les écritures (port série ou HTTP) : un clic manuel et l'auto-
# pilotage par fréquence ne doivent jamais s'entrelacer sur le même relais.
_lock = threading.Lock()

# État de l'auto-pilotage (dernière bande traitée) — PAS dans relay_settings()
# (qui est pure, dérivée de la config à chaque appel) : c'est un état
# d'exécution, comme _circuit dans logx_callbook.py.
_auto_state = {'last_band': None}


def relay_settings(cfg):
    cfg = cfg or {}
    band_map_raw = cfg.get('relay_band_map') or {}
    band_map = {}
    if isinstance(band_map_raw, dict):
        for k, v in band_map_raw.items():
            try:
                band_map[str(k)] = int(v)
            except (TypeError, ValueError):
                continue
    return {
        'enabled': str(cfg.get('relay_enabled', '')) in ('1', 'true', 'True', 'on'),
        'kind': cfg.get('relay_kind', 'kmtronic_serial'),   # kmtronic_serial|generic_serial|webswitch
        'port': cfg.get('relay_port', ''),
        'baud': int(cfg.get('relay_baud', RELAY_DEFAULT_BAUD) or RELAY_DEFAULT_BAUD),
        'host': cfg.get('relay_host', ''),
        'user': cfg.get('relay_user', 'admin'),
        'password': cfg.get('relay_password', ''),
        'relay_count': int(cfg.get('relay_count', 4) or 4),
        'auto_band_enabled': str(cfg.get('relay_auto_band', '')) in ('1', 'true', 'True', 'on'),
        'band_map': band_map,
    }


def _set_serial(port, baud, relay_num, on, open_serial=None):
    opener = open_serial or _open_serial
    if opener is None:
        return {'ok': False, 'error': "pyserial n'est pas installé"}
    try:
        ser = opener(port, baudrate=baud)
    except Exception as e:
        return {'ok': False, 'error': str(e)}
    try:
        ser.write(bytes([0xFF, relay_num, 0x01 if on else 0x00]))
        return {'ok': True}
    except Exception as e:
        return {'ok': False, 'error': str(e)}
    finally:
        try:
            ser.close()
        except Exception:
            pass


def _set_webswitch(host, user, password, relay_num, on, urlopen=None):
    opener = urlopen or urllib.request.urlopen

    def _do():
        auth = base64.b64encode(f'{user}:{password}'.encode()).decode()
        url = f"http://{host}/outlet?{relay_num}={'ON' if on else 'OFF'}"
        req = urllib.request.Request(url, headers={'Authorization': f'Basic {auth}'})
        with opener(req, timeout=TIMEOUT_S) as resp:
            return getattr(resp, 'status', 200)

    try:
        fut = _EXECUTOR.submit(_do)
        status = fut.result(timeout=TIMEOUT_S + 2)
        return {'ok': True, 'status': status}
    except Exception as e:
        return {'ok': False, 'error': str(e)}


def set_relay(cfg, relay_num, on, open_serial=None, urlopen=None):
    """Bascule UN relais. `cfg` : config brute (passe par relay_settings())."""
    s = relay_settings(cfg)
    with _lock:
        if s['kind'] == 'webswitch':
            if not s['host']:
                return {'ok': False, 'error': 'Adresse WebSwitch non configurée'}
            return _set_webswitch(s['host'], s['user'], s['password'], relay_num, on, urlopen=urlopen)
        if not s['port']:
            return {'ok': False, 'error': 'Port série non configuré'}
        return _set_serial(s['port'], s['baud'], relay_num, on, open_serial=open_serial)


def test_connection(cfg, open_serial=None, urlopen=None):
    """N'envoie AUCUNE commande de commutation (contrairement à set_relay) —
    juste ouvre le port/la connexion pour vérifier la joignabilité, comme
    test_connection() dans logx_amp.py pour le transport réseau. Actionner
    un relais réel pour un simple test serait un effet de bord inattendu."""
    s = relay_settings(cfg)
    if s['kind'] == 'webswitch':
        if not s['host']:
            return {'ok': False, 'error': 'Adresse WebSwitch non configurée'}
        opener = urlopen or urllib.request.urlopen

        def _do():
            auth = base64.b64encode(f"{s['user']}:{s['password']}".encode()).decode()
            req = urllib.request.Request(f"http://{s['host']}/", headers={'Authorization': f'Basic {auth}'})
            with opener(req, timeout=TIMEOUT_S) as resp:
                return getattr(resp, 'status', 200)
        try:
            fut = _EXECUTOR.submit(_do)
            fut.result(timeout=TIMEOUT_S + 2)
            return {'ok': True}
        except Exception as e:
            return {'ok': False, 'error': str(e)}
    if not s['port']:
        return {'ok': False, 'error': 'Port série non configuré'}
    opener = open_serial or _open_serial
    if opener is None:
        return {'ok': False, 'error': "pyserial n'est pas installé"}
    try:
        ser = opener(s['port'], baudrate=s['baud'])
        ser.close()
        return {'ok': True}
    except Exception as e:
        return {'ok': False, 'error': str(e)}


def apply_band_relay(cfg, band, open_serial=None, urlopen=None):
    """Bascule le relais mappé à `band` sur ON, coupe tous les AUTRES relais
    du mapping — comportement "commutateur d'antenne exclusif", une seule
    antenne active à la fois. Appelée sans condition de changement (voir
    maybe_apply_band pour la version dédupliquée utilisée par le polling)."""
    s = relay_settings(cfg)
    if not s['enabled'] or not s['auto_band_enabled'] or not s['band_map']:
        return {'ok': False, 'error': 'Auto-pilotage désactivé ou table vide'}
    target = s['band_map'].get(str(band))
    if target is None:
        return {'ok': False, 'error': f'Bande {band} non mappée'}
    results = {}
    for relay_num in sorted(set(s['band_map'].values())):
        results[relay_num] = set_relay(cfg, relay_num, relay_num == target,
                                        open_serial=open_serial, urlopen=urlopen)
    ok = all(r.get('ok') for r in results.values())
    return {'ok': ok, 'activated': target, 'results': results}


def maybe_apply_band(cfg, band, open_serial=None, urlopen=None):
    """Version DÉDUPLIQUÉE d'apply_band_relay() : ne fait rien si `band` est
    la même que la dernière traitée — c'est celle-ci que le polling
    (_rig_state_dict) doit appeler, jamais apply_band_relay() directement,
    sous peine de rejouer la commutation à chaque poll (~3s) tant que
    l'opérateur reste sur la même bande."""
    if band == _auto_state['last_band']:
        return {'ok': True, 'skipped': True}
    _auto_state['last_band'] = band
    return apply_band_relay(cfg, band, open_serial=open_serial, urlopen=urlopen)
