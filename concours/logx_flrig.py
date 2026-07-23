# -*- coding: utf-8 -*-
"""Pilotage CAT via flrig (protocole XML-RPC réseau) — 4e backend CAT aux
côtés de logx_cat (série natif), logx_tci (WebSocket) et logx_rig
(rigctld/Hamlib).

flrig est un pilote CAT autonome très répandu chez les utilisateurs Linux/
fldigi (souvent jugé plus réactif que Hamlib sur certains transceivers) : il
dialogue lui-même en série avec la radio et expose un serveur XML-RPC réseau
(port 12345 par défaut) que d'autres logiciels pilotent — même principe que
rigctld, mais en XML-RPC plutôt qu'en protocole texte Hamlib. xmlrpc.client
est dans la bibliothèque standard : zéro dépendance supplémentaire, comme
pour logx_rig.py (socket brut) et logx_tci.py (WebSocket écrit à la main).

Méthodes XML-RPC utilisées, vérifiées contre les chaînes enregistrées dans le
serveur XML-RPC officiel de flrig (dépôt w1hkj/flrig,
src/server/xml_server.cxx — la page de doc publique w1hkj.com/flrig-help/
xmlrpc_commands.html était inaccessible en DNS depuis ce poste au moment de
l'implémentation, la liste vient donc directement du code source) :
    rig.get_vfo          s:n   fréquence du VFO actif, en Hz (chaîne)
    rig.set_frequency    d:d   règle la fréquence du VFO actif, en Hz
    rig.get_mode         s:n   mode courant (chaîne, ex. "USB", "CW")
    rig.set_mode         i:s   règle le mode
    rig.get_ptt          i:n   état PTT (0/1)
    rig.set_ptt          n:i   règle le PTT on(1)/off(0)

Pas d'envoi CW ici : flrig n'expose pas de méthode générique "envoie ce texte
via le keyer CW de la radio" (seul rig.cwio_text existe, mais il pilote un
montage DTR/RTS optionnel non représenté dans la config CONFIG de LogX AI,
donc pas fiable à activer sans plus de réglages) — même choix que le mode
natif : le keyer CW du logbook reste réservé à TCI/rigctld.
"""
import threading
import xmlrpc.client

DEFAULT_HOST = '127.0.0.1'
DEFAULT_PORT = 12345
TIMEOUT_S = 2.0

_lock = threading.Lock()  # une commande à la fois (même précaution que logx_rig)


class _TimeoutTransport(xmlrpc.client.Transport):
    """xmlrpc.client ne propose pas de timeout natif sur les appels — sans
    lui, un flrig qui ne répond plus bloquerait indéfiniment l'appelant
    (inacceptable dans le thread HTTP, voir contrainte réseau non bloquant
    du projet)."""

    def __init__(self, timeout):
        super().__init__()
        self._timeout = timeout

    def make_connection(self, host):
        conn = super().make_connection(host)
        conn.timeout = self._timeout
        return conn


def _proxy(host, port):
    return xmlrpc.client.ServerProxy(f'http://{host}:{port}/',
                                     transport=_TimeoutTransport(TIMEOUT_S),
                                     allow_none=True)


def flrig_settings(cfg):
    """Réglages flrig depuis la config CLIENT. Le choix du mode ('native' /
    'tci' / 'rigctld' / 'flrig') reste porté par cat_settings() de
    logx_cat — ce module ne gère que host/port, le dispatch se fait
    côté HTTP (même principe que logx_tci.tci_settings)."""
    cfg = cfg or {}
    try:
        port = int(cfg.get('flrig_port') or DEFAULT_PORT)
    except (TypeError, ValueError):
        port = DEFAULT_PORT
    return {'host': (cfg.get('flrig_host') or '').strip() or DEFAULT_HOST, 'port': port}


def get_state(host, port):
    """État courant : fréquence (Hz) + mode. Même forme que
    logx_rig.get_state/logx_tci.get_state."""
    try:
        with _lock:
            proxy = _proxy(host, port)
            freq = int(float(proxy.rig.get_vfo()))
            mode = str(proxy.rig.get_mode())
        return {'ok': True, 'freq_hz': freq,
                'freq_khz': round(freq / 1000.0, 2), 'mode': mode}
    except Exception as e:
        return {'ok': False, 'error': f'flrig injoignable ({e})'}


def set_freq(host, port, freq_hz, mode=None):
    """QSY : règle la fréquence (et le mode si fourni)."""
    try:
        with _lock:
            proxy = _proxy(host, port)
            proxy.rig.set_frequency(float(freq_hz))
            if mode:
                proxy.rig.set_mode(str(mode))
        return {'ok': True}
    except Exception as e:
        return {'ok': False, 'error': f'flrig injoignable ({e})'}


def set_ptt(host, port, on):
    """Bascule PTT — même signature que logx_cat.set_ptt/logx_tci.set_ptt/
    logx_rig.set_ptt, pour le keyer vocal (logx_voicekeyer.py)."""
    try:
        with _lock:
            proxy = _proxy(host, port)
            proxy.rig.set_ptt(1 if on else 0)
        return {'ok': True}
    except Exception as e:
        return {'ok': False, 'error': f'flrig injoignable ({e})'}


def test_connection(host, port):
    """Test ÉPHÉMÈRE (bouton CONFIG) : une seule requête XML-RPC, sans
    connexion persistante à fermer (contrairement à TCI/natif, flrig ne
    maintient aucun état côté client entre deux appels)."""
    host = (host or '').strip() or DEFAULT_HOST
    try:
        port = int(port or DEFAULT_PORT)
    except (TypeError, ValueError):
        port = DEFAULT_PORT
    st = get_state(host, port)
    if not st.get('ok'):
        return st
    return {'ok': True, 'freq_hz': st['freq_hz'], 'mode': st.get('mode', '')}
