# -*- coding: utf-8 -*-
"""Pilotage de l'amplificateur PowerGenius XL (4O3A / FlexRadio) — port de
COMMANDE Ethernet natif TCP 9008 (découverte UDP 9008 en broadcast existe
aussi mais n'est PAS implémentée ici, pas indispensable pour LogX).

Source unique et officielle vérifiée par WebFetch (2 requêtes distinctes,
03/08/2026) : le wiki GitHub FlexRadio (PAS 4o3a/genius-api-docs, quasi vide)
  https://github.com/flexradio/smartsdr-api-docs/wiki/PowerGenius-Ethernet-API

CONFIRMÉ littéralement par cette page (haute confiance) :
  - Prologue de connexion : le PGXL envoie "V<a.b.c> [ AUTH]" dès l'accept()
    (version firmware ; AUTH ne concerne que l'accès WAN, ignoré ici — LogX
    vise un usage LAN, comme demandé).
  - Trame requête  : "C<seq>|<commande>\r"  (seq = 1-255, terminateur 0x0D).
  - Trame réponse  : "R<seq>|<hex>|<message>"  — hex "0" = succès, toute
    autre valeur = échec (AUCUNE liste de codes d'erreur énumérée par la
    doc — vérifié explicitement, pas une lacune de lecture).
  - Trame async    : "S<0>|<message>"  (ex. après "save" : "S|state=REBOOT").
  - Commandes confirmées : "status", "meter create name=FWD/RL/DRV/ID/TEMP
    type=AMP min=... max=... units=..." (5 mesureurs), "amplifier create
    ip=... port=... model=... serial_num=... ant=...", "interlock create
    type=AMP valid_antennas=... name=... serial=...", "interlock disable
    <id>", "setup read", "ifconf read/address=...", "flexradio ampslice=
    {A|B} serial=... txant=... ptt=LAN active=1", "save", "keepalive
    enable", "ping", "message severity=... code=... "texte"".
  - Le style "clé=valeur séparées par des espaces" est confirmé pour TOUTES
    les commandes ci-dessus (meter create, flexradio, ifconf, message) — on
    suppose donc (PAS vérifié littéralement, la doc ne montre jamais une
    trame "status" complète) que la RÉPONSE à "status" suit le même style.
    "state=" est en tout cas un nom de clé confirmé ailleurs (async "save"
    -> "state=REBOOT"), ce qui rend plausible qu'un "state=STANDBY" ou
    "state=OPERATE" apparaisse dans la réponse status — voir pgxl_parse_
    status() ci-dessous, qui reste GÉNÉRIQUE (parse tout couple clé=valeur
    rencontré) plutôt que de figer une liste de champs non confirmée.

PAS CONFIRMÉ par la doc (vérifié explicitement par une 2e requête WebFetch
ciblée avant d'écrire le code, comme demandé) — donc PAS deviné dans ce
module :
  - Le format complet et littéral de la réponse "status" (champs exacts,
    unités, présence d'un champ "fault"/"alarm").
  - Une commande dédiée pour basculer OPERATE <-> STANDBY (mise en/hors
    service manuelle, PAR OPPOSITION au PTT auto piloté par la radio via
    LAN/CAT/CI-V/BCD/Pin2Band, qui LUI est documenté comme la source
    normale du PTT). "interlock disable <id>" est un candidat évoqué par
    la consigne de ce chantier, mais (a) sa syntaxe de réponse n'est pas
    documentée, (b) sémantiquement un "interlock" est un dispositif de
    SÉCURITÉ — le "disable" pourrait tout aussi bien LEVER une protection
    que mettre l'ampli en veille, aucun moyen de trancher sans essai sur du
    vrai matériel. set_operate() REFUSE donc explicitement plutôt que
    d'envoyer une commande devinée à un ampli réel (règle de la maison :
    un module qui refuse proprement vaut mieux qu'un module qui invente).
  - Une commande de sélection de bande manuelle indépendante du CAT/BCD/
    Pin2Band (absente de la doc).
  - La conversion du mesureur RL (units=DB, probablement "Return Loss") en
    ROS/SWR : calculée ICI avec la formule RF standard SWR=(1+|G|)/(1-|G|),
    |G|=10^(-RL_dB/20) — formule physique universelle, PAS une donnée
    PowerGenius, mais son applicabilité à ce mesureur précis n'est pas
    confirmée par la doc (RL pourrait mesurer autre chose). Le mesureur FWD
    (units=DBM, pas Watts) n'est PAS converti en Watts : aucune formule de
    conversion dBm -> W absolue documentée pour ce mesureur (dBm est déjà
    une unité de puissance mais relative à une référence non précisée par
    la doc pour ce contexte) — power_w reste explicitement None plutôt que
    d'inventer un facteur.

Comme logx_rotor.py : toute E/S réseau (y compris la résolution DNS/la
connexion initiale, PAS bornée par socket.create_connection(timeout=...)
seul, voir commentaire de _connect_bounded ci-dessous) passe par un
ThreadPoolExecutor borné dans le temps. Deux points d'injection pour les
tests : la variable de module `_open_transport` (remplacée globalement,
comme dans logx_rotor.py/logx_amp.py) et le paramètre `transport=` de
_ensure_connected()/test_connection() (factory ponctuelle, même motif que
`open_serial=`/`urlopen=` dans logx_relay.py.test_connection()) — la
majorité de tests/test_powergenius.py utilise plutôt un VRAI serveur TCP
loopback (classe FakePgxl), motif légitime déjà établi dans ce dépôt
(test_rotor.py/test_amp.py) ; un test dédié exerce en plus `transport=`
pour prouver que ce point d'injection fonctionne réellement.
"""
import concurrent.futures as _cf
import socket
import threading
import time

DEFAULT_PORT = 9008
CONNECT_TIMEOUT_S = 3.0
CMD_TIMEOUT_S = 3.0
TERM = b'\r'

_EXECUTOR = _cf.ThreadPoolExecutor(max_workers=4, thread_name_prefix='pgxl_net')


# ═══════════════════════════════════════════════════════════════════════════
#  Fonctions PURES (parsing) — testables sans réseau, comme civ_parse_frame()
#  dans logx_cat.py ou pgxl_parse_status() plus bas.
# ═══════════════════════════════════════════════════════════════════════════

def pgxl_build_command(seq, cmd_text):
    """"C<seq>|<cmd_text>\\r" encodé ASCII — trame de requête (confirmé)."""
    return f'C{seq}|{cmd_text}\r'.encode('ascii', errors='replace')


def pgxl_parse_response(line):
    """Décode une ligne "R<seq>|<hex>|<message>" ou "S<0>|<message>" (sans le
    terminateur \\r final, déjà retiré par l'appelant). Retourne
    {'kind':'R'|'S', 'seq':int, 'ok':bool, 'code':int|None, 'message':str}
    ou None si la ligne est illisible/vide — jamais d'exception."""
    if not line:
        return None
    if isinstance(line, bytes):
        line = line.decode('ascii', errors='replace')
    line = line.strip()
    if not line:
        return None
    kind = line[0]
    if kind not in ('R', 'S'):
        return None
    rest = line[1:]
    if not rest.startswith(('0', '1', '2', '3', '4', '5', '6', '7', '8', '9')):
        return None
    # Le numéro de séquence est la suite de chiffres avant le premier '|'.
    seq_str, sep, tail = rest.partition('|')
    if not sep or not seq_str.isdigit():
        return None
    seq = int(seq_str)
    if kind == 'S':
        return {'kind': 'S', 'seq': seq, 'ok': True, 'code': None, 'message': tail}
    # 'R' : tail = "<hex>|<message>" — le message peut lui-même contenir '|'
    # (ex. flottant écrit avec des unités concaténées), on ne coupe qu'une fois.
    code_str, sep2, message = tail.partition('|')
    if not sep2:
        return None
    try:
        code = int(code_str.strip(), 16)
    except ValueError:
        return None
    return {'kind': 'R', 'seq': seq, 'ok': code == 0, 'code': code, 'message': message}


def pgxl_parse_status(message):
    """Parse une réponse de type "clé=valeur clé=valeur ..." séparée par des
    espaces (style confirmé pour les AUTRES commandes de cette API — voir
    docstring du module — appliqué ici par analogie, PAS vérifié
    littéralement pour "status" faute d'exemple complet dans la doc).
    Retourne un dict {clé_minuscule: valeur_str} — jamais d'exception, une
    entrée sans '=' est simplement ignorée plutôt que de deviner sa forme."""
    out = {}
    for token in (message or '').split():
        key, sep, val = token.partition('=')
        if sep and key:
            out[key.strip().lower()] = val.strip()
    return out


def _to_float(raw):
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def pgxl_rl_db_to_swr(rl_db):
    """Formule RF standard (universelle, pas propre au PGXL) : à partir d'un
    "retour de perte" en dB, calcule le ROS équivalent. Retourne None si
    `rl_db` est invalide ou <= 0 (un "return loss" est par convention une
    valeur positive ; une valeur nulle ou négative n'a pas de ROS fini/défini
    par cette formule et on refuse de deviner plutôt que de renvoyer inf/NaN)."""
    if rl_db is None or rl_db <= 0:
        return None
    gamma = 10 ** (-rl_db / 20.0)
    if gamma >= 1:
        return None
    return round((1 + gamma) / (1 - gamma), 2)


# ═══════════════════════════════════════════════════════════════════════════
#  Transport TCP — connexion persistante, injectable pour les tests
# ═══════════════════════════════════════════════════════════════════════════

def _connect_bounded(host, port, timeout):
    """socket.create_connection(timeout=...) ne borne PAS la résolution DNS
    (getaddrinfo) — même piège documenté dans logx_rotor.py. On soumet donc
    la connexion complète (DNS + connect) à un ThreadPoolExecutor et on borne
    l'attente du résultat, pour ne jamais geler le thread HTTP appelant sur
    un hôte injoignable/mal résolu."""
    fut = _EXECUTOR.submit(socket.create_connection, (host, port), timeout)
    return fut.result(timeout=timeout + 2)


class PgxlPort:
    """Transport TCP brut vers le port de commande 9008 du PowerGenius XL.
    Une seule connexion persistante porte tout le dialogue commande/réponse
    (comme TcpAmpPort dans logx_amp.py) : on accumule dans un tampon jusqu'à
    un terminateur '\\r', une ligne à la fois (une trame R/S par ligne)."""

    def __init__(self, host, port=DEFAULT_PORT, timeout=CONNECT_TIMEOUT_S):
        self._lock = threading.Lock()
        self._sock = _connect_bounded(host, port, timeout)
        self._buf = b''
        self._seq = 0
        self.prologue = self._read_line(timeout) or ''

    def _read_line(self, timeout):
        deadline = time.monotonic() + timeout
        while TERM not in self._buf:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            self._sock.settimeout(max(remaining, 0.01))
            try:
                chunk = self._sock.recv(4096)
            except (socket.timeout, OSError):
                break
            if not chunk:
                break
            self._buf += chunk
        if TERM in self._buf:
            idx = self._buf.index(TERM)
            line, self._buf = self._buf[:idx], self._buf[idx + 1:]
            return line.decode('ascii', errors='replace')
        return None

    def command(self, cmd_text, timeout=CMD_TIMEOUT_S):
        """Envoie une commande, attend LA réponse "R<seq>|..." correspondant
        à NOTRE numéro de séquence — les trames "S<0>|..." (async, non
        sollicitées) et toute réponse à une autre séquence rencontrées entre-
        temps sont ignorées plutôt que mal interprétées (même prudence que
        le garde-fou de sens CI-V dans logx_amp.IcomAmp._get()). Lève
        ConnectionError/TimeoutError plutôt que de renvoyer une valeur
        ambiguë — c'est l'appelant (get_state/set_operate/test_connection)
        qui traduit en {'ok': False, 'error': ...}."""
        with self._lock:
            self._seq = (self._seq % 255) + 1
            seq = self._seq
            frame = pgxl_build_command(seq, cmd_text)
            self._sock.settimeout(timeout)
            try:
                self._sock.sendall(frame)
            except OSError as e:
                raise ConnectionError(f'Écriture PowerGenius impossible : {e}')
            deadline = time.monotonic() + timeout
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError('PowerGenius : pas de réponse dans le délai imparti')
                line = self._read_line(remaining)
                if line is None:
                    raise TimeoutError('PowerGenius : pas de réponse dans le délai imparti')
                parsed = pgxl_parse_response(line)
                if parsed is None:
                    continue
                if parsed['kind'] == 'R' and parsed['seq'] == seq:
                    return parsed
                # trame async ou réponse à une autre requête : on continue d'attendre

    def close(self):
        try:
            self._sock.close()
        except OSError:
            pass


# ═══════════════════════════════════════════════════════════════════════════
#  Réglages + connexion persistante (même schéma que logx_tci.py/logx_amp.py)
# ═══════════════════════════════════════════════════════════════════════════

MIN_TIMEOUT_S = 1.0
MAX_TIMEOUT_S = 10.0


def pgxl_settings(cfg):
    """Réglages PowerGenius XL depuis la config CLIENT — absence des champs
    pgxl_* -> enabled=False, jamais d'exception même sur cfg vide/None
    (même garantie que amp_settings()/tci_settings()).

    `pgxl_timeout` est BORNÉ à [MIN_TIMEOUT_S, MAX_TIMEOUT_S] : contrairement
    à amp_settings()/tci_settings()/rotor_settings() (timeout toujours une
    constante fixe, jamais dérivée de la config client), ce module est le
    seul à accepter un timeout venant de CONFIG — sans clamp, une valeur
    erronée ou énorme (ex. 999999) bloquerait le thread HTTP appelant pendant
    toute cette durée en tenant _persistent_lock, gelant au passage tout
    autre appel concurrent."""
    cfg = cfg or {}
    try:
        port = int(cfg.get('pgxl_port') or DEFAULT_PORT)
    except (TypeError, ValueError):
        port = DEFAULT_PORT
    try:
        timeout = float(cfg.get('pgxl_timeout') or CMD_TIMEOUT_S)
    except (TypeError, ValueError):
        timeout = CMD_TIMEOUT_S
    timeout = max(MIN_TIMEOUT_S, min(timeout, MAX_TIMEOUT_S))
    return {
        'enabled': bool(cfg.get('pgxl_enabled')),
        'host': (cfg.get('pgxl_host') or '').strip(),
        'port': port,
        'timeout': timeout,
    }


_persistent = {}
_persistent_lock = threading.Lock()
_io_lock = threading.Lock()   # sérialise les échanges commande/réponse (voir logx_amp.py _io_lock)

_open_transport = PgxlPort   # point d'injection pour les tests (double sans vrai socket)


def _ensure_connected(st, transport=None):
    """`transport=` : factory ponctuelle injectable pour les tests, même
    signature que `_open_transport` (callable(host, port, timeout) -> objet
    transport) — court-circuite `_open_transport` quand fourni, sur le même
    motif que `open_serial=`/`urlopen=` dans logx_relay.py.test_connection().
    Par défaut (None), utilise la variable de module `_open_transport`."""
    key = (st['host'], st['port'])
    with _persistent_lock:
        entry = _persistent.get('default')
        if entry and entry['key'] == key:
            return entry['transport'], None
        if entry:
            entry['transport'].close()
            _persistent.pop('default', None)
        if not st['host']:
            return None, 'Adresse IP/hôte du PowerGenius XL non configurée'
        opener = transport or _open_transport
        try:
            conn = opener(st['host'], st['port'], st['timeout'])
        except Exception as e:
            return None, f"Impossible de joindre {st['host']}:{st['port']} : {e}"
        _persistent['default'] = {'key': key, 'transport': conn}
        return conn, None


def disconnect_persistent():
    with _persistent_lock:
        entry = _persistent.pop('default', None)
    if entry:
        entry['transport'].close()


def _status_to_state(parsed_status):
    """Traduit le dict générique {clé: valeur_str} de pgxl_parse_status() en
    la forme unifiée demandée (même esprit que get_state() dans
    logx_amp.py) : 'ok','operate','fwd_dbm'/'power_w','swr','fault', plus
    les valeurs brutes confirmées disponibles. Aucune clé n'est fabriquée
    si absente de la réponse — voir docstring du module pour ce qui n'est
    pas confirmé (power_w reste toujours None, jamais deviné)."""
    state_raw = (parsed_status.get('state') or '').strip().upper()
    operate = None
    # Seules les valeurs LITTÉRALEMENT confirmées par la doc sont reconnues
    # ('OPERATE'/'STANDBY', par analogie avec l'unique exemple vérifié —
    # l'async "state=REBOOT") : il s'agit potentiellement d'un état lié à
    # l'émission (TX enable), la prudence prime sur la couverture — tout
    # alias deviné (OPER/ON/STBY/OFF) retombe volontairement dans l'état
    # "inconnu" (operate=None) plutôt que d'être supposé équivalent.
    if state_raw == 'OPERATE':
        operate = True
    elif state_raw == 'STANDBY':
        operate = False
    fwd_dbm = _to_float(parsed_status.get('fwd'))
    rl_db = _to_float(parsed_status.get('rl'))
    out = {
        'ok': True,
        'operate': operate,
        'state_raw': state_raw or None,
        'fwd_dbm': fwd_dbm,
        'power_w': None,   # jamais déduit de fwd_dbm — voir docstring du module
        'rl_db': rl_db,
        'swr': pgxl_rl_db_to_swr(rl_db),
        'drv_dbm': _to_float(parsed_status.get('drv')),
        'id_amps': _to_float(parsed_status.get('id')),
        'temp_c': _to_float(parsed_status.get('temp')),
        'fault': None,   # pas de champ "fault"/"alarm" confirmé dans la doc pour "status"
        'raw': parsed_status,
    }
    return out


def get_state(cfg):
    """État courant (mesureurs FWD/RL/DRV/ID/TEMP + état si présent) — forme
    unifiée {'enabled','ok','error'?, ...} comme get_state() de logx_amp.py.
    Envoie la commande "status" (lecture seule, confirmée par la doc)."""
    st = pgxl_settings(cfg)
    if not st['enabled']:
        return {'enabled': False}
    transport, err = _ensure_connected(st)
    if err:
        return {'ok': False, 'error': err, 'enabled': True}
    try:
        with _io_lock:
            resp = transport.command('status', timeout=st['timeout'])
    except Exception as e:
        disconnect_persistent()
        return {'ok': False, 'error': f'PowerGenius XL injoignable ({e})', 'enabled': True}
    if not resp['ok']:
        return {'ok': False, 'error': f"Commande status refusée par le PowerGenius XL "
                                      f"(code {resp['code']:#x})", 'enabled': True}
    out = _status_to_state(pgxl_parse_status(resp['message']))
    out['enabled'] = True
    return out


def set_operate(cfg, on):
    """AUCUNE commande OPERATE/STANDBY manuelle n'est confirmée par la doc
    officielle PowerGenius Ethernet API (voir docstring du module — le
    candidat évoqué, "interlock disable <id>", n'a ni réponse documentée ni
    sémantique certaine, et un "interlock" est un dispositif de SÉCURITÉ :
    se tromper de sens serait dangereux, pas juste incorrect). Ce module
    refuse donc explicitement plutôt que d'envoyer un octet inventé à un
    ampli réel — règle de la maison. Le PTT/l'état operate du PGXL sont
    normalement pilotés automatiquement par la radio (LAN/CAT/CI-V/BCD/
    Pin2Band, voir doc) ; en attendant une confirmation du protocole exact
    (retour terrain ou nouvelle doc 4O3A/FlexRadio), utilise le panneau
    avant du PGXL ou SmartSDR pour basculer standby/operate à la main."""
    st = pgxl_settings(cfg)
    if not st['enabled']:
        return {'ok': False, 'error': 'Pilotage PowerGenius XL désactivé (CONFIG)'}
    return {'ok': False, 'error': (
        "Bascule OPERATE/STANDBY non confirmée par la documentation officielle "
        "PowerGenius Ethernet API (FlexRadio) — aucune commande fiable identifiée "
        "sans risque de mésinterprétation d'un mécanisme de sécurité (« interlock »). "
        "Utilise le panneau avant du PGXL ou SmartSDR en attendant."
    )}


def test_connection(host, port=None, timeout=None, transport=None):
    """Test ÉPHÉMÈRE (bouton CONFIG) : ouvre une connexion séparée (lit le
    prologue "V<a.b.c> ..."), envoie "status" (lecture seule, aucun effet de
    bord matériel), ferme — ne touche jamais à la connexion persistante
    utilisée par le polling logbook.

    `transport=` : factory ponctuelle injectable pour les tests, même motif
    que dans _ensure_connected() ci-dessus — court-circuite `_open_transport`
    quand fourni."""
    host = (host or '').strip()
    if not host:
        return {'ok': False, 'error': 'Adresse IP/hôte manquante'}
    try:
        port = int(port or DEFAULT_PORT)
    except (TypeError, ValueError):
        port = DEFAULT_PORT
    try:
        timeout = float(timeout or CMD_TIMEOUT_S)
    except (TypeError, ValueError):
        timeout = CMD_TIMEOUT_S
    # Plafond (revue sécurité) : `timeout` vient du client HTTP (bouton
    # CONFIG) sans aucune borne haute jusqu'ici — un client pouvait faire
    # tenir ouvert un thread serveur bien au-delà de toute latence réseau
    # légitime. 30s couvre largement un pire cas de câble/réseau lent.
    timeout = max(0.1, min(timeout, 30.0))
    opener = transport or _open_transport
    try:
        conn = opener(host, port, timeout)
    except Exception as e:
        return {'ok': False, 'error': f'Impossible de joindre {host}:{port} : {e}'}
    try:
        if not conn.prologue.startswith('V'):
            return {'ok': False, 'error': f"Prologue inattendu à la connexion "
                                          f"(pas un PowerGenius XL ?) : {conn.prologue!r}"}
        resp = conn.command('status', timeout=timeout)
        if not resp['ok']:
            return {'ok': False, 'error': f"Commande status refusée (code {resp['code']:#x})"}
        return {'ok': True, 'firmware': conn.prologue,
                'status': _status_to_state(pgxl_parse_status(resp['message']))}
    except Exception as e:
        return {'ok': False, 'error': f'PowerGenius XL injoignable ({e})'}
    finally:
        conn.close()
