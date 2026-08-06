# -*- coding: utf-8 -*-
"""Pilotage FlexRadio SmartSDR — protocole réseau TCP « SmartSDR TCPIP API »,
5e backend CAT aux côtés de logx_cat (série natif), logx_tci (WebSocket),
logx_rig (rigctld/Hamlib) et logx_flrig (XML-RPC).

Protocole ASCII texte sur TCP, port de commande 4992 par défaut. Doc
officielle vérifiée par WebFetch réussi sur le wiki GitHub officiel
(pages "SmartSDR TCPIP API", "TCPIP slice", "TCPIP xmit", "TCPIP sub",
"SmartSDR Status Responses") :
    https://github.com/flexradio/smartsdr-api-docs/wiki

Handshake : dès la connexion TCP établie, la radio envoie DEUX lignes de
bienvenue AVANT toute commande — "V<version>" (version de protocole) puis
"H<handle>" (identifiant hexadécimal 32 bits de CETTE connexion, préfixe des
messages asynchrones qui suivent). Il FAUT lire ces deux lignes avant
d'émettre quoi que ce soit, sous peine de désynchroniser les échanges
suivants (même précaution que le handshake WebSocket de logx_tci.py).

Requête  : "C[D]<seq>|<commande><terminateur>" ('D' optionnel = debug,
           NON utilisé ici ; terminateur 0x0D, 0x0A ou 0x0D0A — ce module
           envoie '\\n').
Réponse  : "R<seq>|<code_hexa>|<message>[|debug]" — code_hexa "0" = succès.
Message asynchrone poussé par la radio (PAS une réponse à une commande,
           à LIRE et router sans jamais bloquer une commande en attente) :
           "S<handle>|<message>"

Le protocole est PUSH, comme TCI (voir logx_tci.py) : la fréquence/le mode/
l'état PTT ne se lisent pas par une requête synchrone dédiée mais sont reçus
en continu via des messages "S" — et UNIQUEMENT après abonnement explicite,
sans quoi la radio ne notifie jamais rien. Deux abonnements suffisent pour ce
module (verbes confirmés par la doc officielle "TCPIP sub", WebFetch réussi) :
    C<seq>|sub slice all   -> S<handle>|slice <n> RF_frequency=<MHz> mode=<mode> ...
    C<seq>|sub radio all   -> inclut S<handle>|interlock state=<état> ...
                               (READY/RECEIVE = pas en émission ;
                               PTT_REQUESTED/TRANSMITTING = en émission)
Un fil d'arrière-plan lit ces messages en continu et alimente un cache
d'état — même architecture que TciClient (logx_tci.py) : get_state() renvoie
le cache sans aller-retour réseau à chaque appel.

Commande de réglage utilisée par ce module (verbe confirmé par la doc
officielle "TCPIP xmit", WebFetch réussi — PAS une déduction par analogie) :
    C<seq>|xmit <0|1>   -> PTT/MOX on(1)/off(0)

PÉRIMÈTRE (règle 9 du chantier LogX) : uniquement get_state (fréquence/mode
du premier « slice » — récepteur virtuel Flex — vu, comme le récepteur '0'
par défaut de TciClient) et set_ptt, pour le besoin strict d'un contest
logger. Les commandes de réglage fréquence/mode ("slice t"/"slice s",
également confirmées par la doc officielle "TCPIP slice") ne sont PAS
exposées publiquement ici — hors contrat demandé pour ce module — et le CW
n'est pas géré (pas de méthode "cw"/"cwx" documentée pour un texte libre
côté keyer, contrairement à TCI cw_macros).
"""
import concurrent.futures as _cf
import select
import socket
import threading
import time

DEFAULT_HOST = '127.0.0.1'
DEFAULT_PORT = 4992
CONNECT_TIMEOUT_S = 3.0
WRITE_TIMEOUT_S = 5.0
READ_IDLE_TIMEOUT_S = 30.0   # au-delà de ce silence, la connexion est jugée morte
MAX_LINE_LEN = 8192          # borne défensive : une ligne sans '\n' ne doit jamais
                              # faire grossir le buffer indéfiniment (trame malformée)

# getaddrinfo (résolution DNS) n'est PAS couvert par un socket.settimeout()
# posé après coup — un hôte mal résolu bloquerait indéfiniment ce thread sans
# cet executor borné. Même motif que logx_rotor._rotctld_command/_gs232_txrx.
_EXECUTOR = _cf.ThreadPoolExecutor(max_workers=2, thread_name_prefix='flexradio_cat')


def _close_late_socket(fut):
    """Callback pour un socket.create_connection() qui finit par réussir
    APRÈS que l'appelant de FlexSocket.connect() a déjà abandonné (timeout
    écoulé côté appelant) — ferme ce socket devenu orphelin plutôt que de le
    laisser fuir (personne d'autre n'y a de référence)."""
    try:
        sock = fut.result()
    except Exception:
        return
    try:
        sock.close()
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════════════════
#  Transport TCP texte minimal — lignes ASCII, pas de framing binaire
#  (contrairement à TCI qui est du WebSocket, voir logx_tci.WebSocketClient)
# ═══════════════════════════════════════════════════════════════════════════

class FlexSocket:
    """Connexion TCP texte vers le port de commande SmartSDR (4992).
    Injectable en paramètre (voir _open_sock plus bas) — les tests ne
    touchent jamais un vrai socket réseau pour la couche FlexClient."""

    def __init__(self, host, port, timeout=CONNECT_TIMEOUT_S):
        self.host = host
        self.port = port
        self.timeout = timeout
        self._sock = None
        self._buf = b''
        self._write_lock = threading.Lock()

    def connect(self):
        def _do():
            return socket.create_connection((self.host, self.port), timeout=self.timeout)
        fut = _EXECUTOR.submit(_do)
        try:
            self._sock = fut.result(timeout=self.timeout + 3)
        except _cf.TimeoutError:
            # fut.result() a expiré côté appelant, mais _do() continue de
            # tourner en arrière-plan dans l'executor et peut encore réussir
            # (créer un socket) APRÈS coup — sans ce callback, ce socket-là
            # ne serait jamais fermé (fuite de descripteur). fut.cancel() ne
            # sert à rien ici (le thread tourne déjà) : on ferme le socket
            # depuis le callback s'il finit par arriver, sans bloquer ce
            # connect() qui a déjà échoué pour l'appelant.
            fut.add_done_callback(_close_late_socket)
            raise
        # Handshake PAS encore terminé au retour de connect() (le commentaire
        # précédent ici affirmait le contraire, à tort) : les deux lignes de
        # bienvenue "V…"/"H…" restent à lire par
        # FlexClient.connect_and_start(), qui appelle mark_handshake_done()
        # une fois qu'elles sont effectivement reçues. On garde donc le
        # timeout COURT de connexion (self.timeout) pendant cette lecture —
        # un pair qui accepte le TCP mais reste ensuite muet est ainsi
        # détecté en ~self.timeout, pas en ~READ_IDLE_TIMEOUT_S (30 s).
        # Même distinction que logx_tci.WebSocketClient.connect(), qui
        # applique self.timeout à la lecture de la réponse HTTP Upgrade puis
        # READ_IDLE_TIMEOUT_S seulement après un "101 Switching Protocols"
        # confirmé.
        self._sock.settimeout(self.timeout)

    def mark_handshake_done(self):
        """À appeler UNE FOIS que les deux lignes V/H ont été effectivement
        reçues (voir FlexClient.connect_and_start()) : bascule du timeout
        court de connexion vers le timeout de silence prolongé — protocole
        PUSH, la radio peut légitimement rester muette longtemps entre deux
        messages 'S' une fois les abonnements posés (voir _subscribe())."""
        self._sock.settimeout(READ_IDLE_TIMEOUT_S)

    def send_line(self, text):
        payload = (text + '\n').encode('ascii', errors='replace')
        # Sans select(), un pair mort sans FIN/RST ferait attendre sendall()
        # jusqu'à READ_IDLE_TIMEOUT_S (ou indéfiniment si le timeout socket ne
        # couvre pas l'écriture) — geler l'appelant (thread HTTP). Même garde
        # que WebSocketClient.send_text dans logx_tci.py.
        with self._write_lock:
            _, writable, _ = select.select([], [self._sock], [], WRITE_TIMEOUT_S)
            if not writable:
                raise TimeoutError('FlexRadio : le pair ne répond plus (écriture bloquée)')
            self._sock.sendall(payload)

    def recv_line(self):
        """Une ligne complète (CR final retiré, s'il y en a un), bloquant
        jusqu'à READ_IDLE_TIMEOUT_S de silence. Lève ConnectionError si le
        pair ferme, si le silence dépasse le délai, ou si aucun '\\n'
        n'apparaît avant MAX_LINE_LEN octets (trame malformée) — jamais un
        buffer qui grossit indéfiniment sur une ligne qui ne vient jamais."""
        while b'\n' not in self._buf:
            if len(self._buf) > MAX_LINE_LEN:
                raise ConnectionError(
                    'FlexRadio : ligne sans terminateur au-delà de %d octets' % MAX_LINE_LEN)
            try:
                chunk = self._sock.recv(4096)
            except socket.timeout:
                raise ConnectionError(
                    'FlexRadio : aucune donnée reçue depuis %ds - connexion jugée morte'
                    % READ_IDLE_TIMEOUT_S)
            if not chunk:
                raise ConnectionError('Connexion FlexRadio fermée par le serveur')
            self._buf += chunk
        line, self._buf = self._buf.split(b'\n', 1)
        return line.rstrip(b'\r').decode('utf-8', errors='replace')

    def close(self):
        try:
            self._sock.close()
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════════════════════
#  Client FlexRadio — lit en continu, maintient un cache d'état, envoie xmit
# ═══════════════════════════════════════════════════════════════════════════

class FlexClient:
    """Pilote FlexRadio haut niveau. `sock` est injecté (FlexSocket réel ou
    double de test, voir tests/test_flexradio.py) — aucune E/S directe dans
    cette classe. État alimenté en continu par le fil de lecture (messages
    'S' poussés par la radio APRÈS abonnement) plutôt qu'interrogé à la
    demande — même principe que TciClient (logx_tci.py)."""

    def __init__(self, sock):
        self.sock = sock
        self.state = {'ready': False, 'handle': None, 'freq_hz': {}, 'mode': {}, 'ptt': False}
        self._lock = threading.Lock()
        self._reader = None
        self._stop = False
        self._seq = 0

    def connect_and_start(self):
        self.sock.connect()
        # Les DEUX lignes de bienvenue (V puis H) DOIVENT être lues ici,
        # AVANT de démarrer le fil de lecture — sinon le fil et cette
        # méthode se disputeraient les deux premières lignes du flux. Le
        # socket est encore au timeout COURT de connexion à ce stade (voir
        # FlexSocket.connect()) : un pair qui accepte le TCP mais reste
        # ensuite muet fait échouer recv_line() vite, pas au bout de
        # READ_IDLE_TIMEOUT_S.
        self.sock.recv_line()          # "V<version>" — non exploité ici
        handle_line = self.sock.recv_line()   # "H<handle>"
        # Handshake réellement confirmé ICI (pas au retour de sock.connect())
        # : on peut désormais basculer sur le timeout de silence prolongé.
        self.sock.mark_handshake_done()
        with self._lock:
            if handle_line[:1] == 'H':
                self.state['handle'] = handle_line[1:].strip()
        self._reader = threading.Thread(target=self._read_loop, daemon=True)
        self._reader.start()
        self._subscribe()
        # Attend une première fréquence de slice avant de rendre la main,
        # sans bloquer indéfiniment si la radio n'a aucun slice actif.
        deadline = time.time() + 3.0
        while not self.state['freq_hz'] and time.time() < deadline:
            time.sleep(0.05)
        with self._lock:
            self.state['ready'] = True

    def _next_seq(self):
        with self._lock:
            self._seq += 1
            return self._seq

    def _send(self, command):
        self.sock.send_line('C%d|%s' % (self._next_seq(), command))

    def _subscribe(self):
        # Verbes confirmés par la doc officielle "TCPIP sub" — sans cet
        # abonnement, la radio n'émet JAMAIS de message 'S' spontané pour
        # ces catégories (comportement documenté, pas une supposition).
        self._send('sub slice all')
        self._send('sub radio all')

    def _read_loop(self):
        while not self._stop:
            try:
                line = self.sock.recv_line()
            except Exception:
                break
            try:
                self._handle_line(line)
            except Exception:
                # Une SEULE ligne de statut malformée ou inattendue ne doit
                # jamais tuer tout le fil de lecture : sans ce try/except,
                # reader.is_alive() passerait à False et _ensure_connected()
                # forcerait une reconnexion complète et SYNCHRONE dans le
                # thread HTTP appelant au prochain appel — potentiellement
                # lente. On ignore la ligne fautive et on continue à lire
                # les suivantes (même discipline que les `except Exception:
                # pass` déjà utilisés ailleurs dans ce module, ex.
                # FlexSocket.close()).
                pass

    def _handle_line(self, line):
        if line[:1] == 'S':
            self._handle_status(line)
        # 'R' (réponse à une commande) et un 'V' tardif éventuel : ignorés —
        # aucune commande de ce module n'attend de réponse synchrone avant
        # de rendre la main (même choix que set_freq/set_ptt de TciClient).

    def _handle_status(self, line):
        # "S<handle>|<message>" — le handle sert à router côté client
        # multi-connexion avancé (hors périmètre ici), seul <message> est
        # exploité.
        _, sep, message = line.partition('|')
        if not sep:
            return
        parts = message.split()
        if not parts:
            return
        if parts[0] == 'slice' and len(parts) >= 2:
            self._handle_slice_status(parts[1], parts[2:])
        elif parts[0] == 'interlock':
            self._handle_interlock_status(parts[1:])

    def _handle_slice_status(self, slice_no, fields):
        with self._lock:
            for field in fields:
                key, sep, value = field.partition('=')
                if not sep:
                    continue
                if key == 'RF_frequency':
                    try:
                        # RF_frequency est en MHz (doc officielle) -> Hz entier.
                        # OverflowError couvre round()/int() sur float('inf')
                        # (une valeur non finie envoyée par une radio qui
                        # déraille) — ValueError seul ne l'attrape PAS (il ne
                        # couvre que le NaN et l'échec de float(value)) ; sans
                        # OverflowError ici, une seule ligne de statut
                        # malformée fait remonter une exception non catchée
                        # jusqu'à _read_loop().
                        self.state['freq_hz'][slice_no] = int(round(float(value) * 1000000))
                    except (ValueError, OverflowError, TypeError):
                        pass
                elif key == 'mode':
                    self.state['mode'][slice_no] = value.upper()

    def _handle_interlock_status(self, fields):
        for field in fields:
            key, sep, value = field.partition('=')
            if key == 'state':
                with self._lock:
                    self.state['ptt'] = value.strip().upper() in ('PTT_REQUESTED', 'TRANSMITTING')

    def get_state(self, slice_no='0'):
        with self._lock:
            freq = self.state['freq_hz'].get(slice_no)
            if freq is None and self.state['freq_hz']:
                # Repli : premier slice connu si le slice '0' n'a jamais émis
                # de statut (ex. seul le slice 1 est actif côté radio).
                slice_no = sorted(self.state['freq_hz'].keys())[0]
                freq = self.state['freq_hz'][slice_no]
            return {'ready': self.state['ready'], 'freq_hz': freq,
                    'mode': self.state['mode'].get(slice_no), 'ptt': self.state['ptt']}

    def set_ptt(self, on):
        self._send('xmit %d' % (1 if on else 0))

    def close(self):
        self._stop = True
        self.sock.close()


# ═══════════════════════════════════════════════════════════════════════════
#  Couche pilotée par la config CLIENT — connexion persistante réutilisée
# ═══════════════════════════════════════════════════════════════════════════

# Point d'injection pour les tests : remplacer par un double qui ne touche
# pas un vrai socket (voir tests/test_flexradio.py). Par défaut, le vrai
# transport TCP.
_open_sock = FlexSocket

_persistent = {}
_persistent_lock = threading.Lock()


def flexradio_settings(cfg):
    """Réglages FlexRadio depuis la config CLIENT — fonction PURE, jamais
    d'exception même sur un cfg vide ou None. Le choix du mode CAT ('native'
    / 'tci' / 'rigctld' / 'flrig' / 'flex') reste porté par cat_settings() de
    logx_cat — même principe que logx_tci.tci_settings/logx_flrig.flrig_settings
    pour host/port. EXCEPTION à ce principe pour 'enabled' : contrairement à
    tci_settings/flrig_settings (qui n'ont PAS ce champ — l'activation y est
    entièrement déléguée à cat_settings() via le choix du mode CAT),
    flexradio_settings() introduit son PROPRE champ 'enabled'
    (flexradio_enabled) pour que get_state()/set_ptt() puissent couper toute
    E/S réseau tant qu'il n'est pas explicitement activé en CONFIG, avant
    même de regarder quel mode CAT est sélectionné."""
    cfg = cfg or {}
    try:
        port = int(cfg.get('flexradio_port') or DEFAULT_PORT)
    except (TypeError, ValueError):
        port = DEFAULT_PORT
    return {'enabled': bool(cfg.get('flexradio_enabled')),
            'host': (cfg.get('flexradio_host') or '').strip() or DEFAULT_HOST,
            'port': port}


def _ensure_connected(settings):
    """Retourne (client, erreur_ou_None). Connecte au premier appel, réutilise
    la connexion tant que host/port ne changent pas et que le fil de lecture
    est toujours vivant (même principe que logx_tci._ensure_connected — sans
    cette vérification, une connexion morte servirait indéfiniment le
    dernier cache d'état avec ok=True)."""
    key = (settings['host'], settings['port'])
    with _persistent_lock:
        entry = _persistent.get('default')
        reader = getattr(entry['client'], '_reader', None) if entry else None
        if entry and entry['key'] == key and reader is not None and reader.is_alive():
            return entry['client'], None
        if entry:
            entry['client'].close()
            _persistent.pop('default', None)
        try:
            sock = _open_sock(settings['host'], settings['port'])
            client = FlexClient(sock)
            client.connect_and_start()
        except Exception as e:
            return None, f"Impossible de joindre la radio FlexRadio {settings['host']}:{settings['port']} ({e})"
        _persistent['default'] = {'key': key, 'client': client}
        return client, None


def disconnect_persistent():
    """Ferme la connexion persistante (ex. avant de changer de config)."""
    with _persistent_lock:
        entry = _persistent.pop('default', None)
    if entry:
        entry['client'].close()


def get_state(cfg):
    """État courant (fréquence + mode du premier slice actif, + PTT) — même
    forme que logx_cat/logx_tci/logx_flrig pour que le client HTTP reste
    inchangé quel que soit le mode radio actif. enabled=False (réglage
    désactivé en CONFIG) ne déclenche aucune E/S réseau."""
    settings = flexradio_settings(cfg)
    if not settings['enabled']:
        return {'ok': False, 'error': 'Pilotage FlexRadio désactivé (CONFIG)', 'enabled': False}
    client, err = _ensure_connected(settings)
    if err:
        return {'ok': False, 'error': err, 'enabled': True}
    st = client.get_state()
    if st['freq_hz'] is None:
        return {'ok': False, 'error': 'Pas encore reçu de fréquence de la radio '
                '(aucun slice actif, ou abonnement pas encore confirmé)', 'enabled': True}
    return {'ok': True, 'enabled': True, 'freq_hz': st['freq_hz'],
            'freq_khz': round(st['freq_hz'] / 1000.0, 2), 'mode': st['mode'] or '',
            'ptt': bool(st['ptt'])}


def set_ptt(cfg, on):
    """Bascule PTT/MOX — même signature que logx_cat.set_ptt/logx_tci.set_ptt/
    logx_flrig.set_ptt, pour le keyer vocal (logx_voicekeyer.py)."""
    settings = flexradio_settings(cfg)
    if not settings['enabled']:
        return {'ok': False, 'error': 'Pilotage FlexRadio désactivé (CONFIG)'}
    client, err = _ensure_connected(settings)
    if err:
        return {'ok': False, 'error': err}
    try:
        client.set_ptt(bool(on))
        return {'ok': True}
    except Exception as e:
        disconnect_persistent()
        return {'ok': False, 'error': f'Radio FlexRadio injoignable ({e})'}


def test_connection(host, port):
    """Test ÉPHÉMÈRE (bouton CONFIG) : connecte, s'abonne, attend un premier
    état, ferme — ne touche jamais à la connexion persistante utilisée par
    le polling logbook (même principe que logx_tci.test_connection)."""
    host = (host or '').strip() or DEFAULT_HOST
    try:
        port = int(port or DEFAULT_PORT)
    except (TypeError, ValueError):
        port = DEFAULT_PORT
    try:
        sock = _open_sock(host, port)
        client = FlexClient(sock)
        client.connect_and_start()
    except Exception as e:
        return {'ok': False, 'error': f"Impossible de joindre {host}:{port} ({e})"}
    try:
        st = client.get_state()
        if st['freq_hz'] is None:
            return {'ok': False, 'error': "Connecté, mais aucune fréquence reçue — "
                    "vérifie qu'un slice (récepteur) est actif dans SmartSDR"}
        return {'ok': True, 'freq_hz': st['freq_hz'], 'mode': st['mode'] or ''}
    finally:
        client.close()
