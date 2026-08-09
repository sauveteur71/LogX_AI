# -*- coding: utf-8 -*-
"""Pilotage de l'amplificateur ACOM (500S/600S/700S/1200S/2020S) par son
interface RS-232 de télécommande — port série natif, 9600 bauds/8N1.

Source unique mais RÉELLE ET VÉRIFIÉE LIGNE PAR LIGNE (pas un résumé
WebFetch, contrairement au bloqueur qui a forcé logx_icomremote.py à rester
désactivé) : le dépôt GitHub open source (licence MIT)
  https://github.com/bjornekelund/ACOM-Controller
de Björn Ekelund (SM7IUN, membre CWops, opérateur radioamateur possédant
réellement un amplificateur ACOM — voir https://sm7iun.se/station/acom/) —
une application Windows fonctionnelle, utilisée en pratique par des OM pour
piloter leur PROPRE amplificateur réel, pas une rétro-ingénierie théorique.
Fichier `MainWindow.xaml.cs` (641 lignes) téléchargé intégralement via
`gh api`/`curl` et lu en entier par l'outil Read (03-04/08/2026 selon la
numérotation interne de session) — PAS un résumé produit par un petit modèle
comme pour l'analyse initiale de kappanhang dans logx_icomremote.py.

CORROBORATION INDÉPENDANTE (WebSearch/WebFetch, même session) : un fil du
forum communautaire FlexRadio ("SmartSDR 3.9.18 Serial pass-through remote
control of Acom 500S amplifier") confirme indépendamment que "the PA can be
switched on or off using the CTS or DSR pins on the RS232 connection" — un
mécanisme SÉPARÉ du protocole de commande par octets décrit ci-dessous, et
qui corrobore exactement le commentaire du code source
(`DtrEnable = false; RtsEnable = false; // ... to avoid blocking front panel
power button`). Ce même fil recommande explicitement "the great ACOM
Controller tool from Björn Ekelund" plutôt que le pass-through FlexRadio —
confirmation d'usage réel par la communauté, pas un projet isolé/mort.

RÉFUTATION EXPLICITE d'une piste non vérifiée : une recherche web antérieure
avait fait remonter une affirmation ("SunSDR utiliserait le protocole
Kenwood pour piloter ces amplis") — CONTREDITE par la lecture du code source
réel : le protocole est un cadrage BINAIRE PROPRIÉTAIRE (trames à en-tête
0x55, PAS des commandes ASCII "xx;" façon Kenwood/Yaesu/Elecraft comme dans
logx_cat.py). Cette piste est donc écartée, pas silencieusement ignorée.

CONFIRMÉ par la lecture du code source (haute confiance — bytes littéraux
utilisés tels quels par une application qui pilote du vrai matériel) :
  - Port série : 9600 bauds, 8 bits, parité aucune, 1 bit stop, sans
    contrôle de flux logiciel/matériel (`Handshake.None`).
  - RTS et DTR doivent rester BAS en permanence : sur l'ACOM, ces deux
    lignes câblent l'ALIMENTATION physique de l'ampli (bouton façade),
    PAS une fonction PTT/CAT générique comme sur les interfaces radio
    habituelles (voir `piege-pyserial-rts-dtr-constructeur` déjà connu de
    ce dépôt pour logx_cat.SerialPort, ici la même construction "port fermé
    -> propriétés -> open()" est reprise mais l'enjeu est plus grave : sur
    un ampli 500 W à 2 kW, un mauvais état de ces lignes ne casserait pas
    qu'une commande CAT, il pourrait couper/rallumer l'ampli en pleine
    séance).
  - 3 commandes fixes (trames complètes, checksum déjà inclus dans la
    constante car ce sont des commandes SANS PARAMÈTRE) :
    Operate  = 55 81 08 02 00 06 00 1A  (gestionnaire réel : OperateClick)
    Standby  = 55 81 08 02 00 05 00 1B  (gestionnaire réel : StandbyClick)
    Off      = 55 81 08 02 00 0A 00 16  (gestionnaire réel : OffClick)
    Sémantique NON ambiguë (noms de gestionnaires de bouton explicites dans
    le code source), contrairement au candidat "interlock disable" écarté
    dans logx_powergenius.py (sémantique de sécurité incertaine) — c'est
    pourquoi, DIFFÉREMMENT de set_operate() dans logx_powergenius.py,
    set_operate() ci-dessous n'est PAS un refus : il envoie réellement l'une
    de ces 3 trames.
  - Activer/désactiver la télémétrie périodique : Enable = 55 92 04 15,
    Disable = 55 91 04 16 (envoyée par l'appli à l'ouverture puis toutes les
    200 ms tant qu'aucune trame n'est reçue, et à la fermeture propre).
  - Trame de télémétrie reçue en retour : exactement 72 octets, débute par
    55 2F, somme de TOUS les octets de la trame == 0 (mod 256) = checksum
    valide. Champs confirmés (indices d'octet dans la trame) :
      - octet 3 (nibble haut) = état : 1 RESET, 2 INIT, 3 DEBUG, 4 SERVICE,
        5 STANDBY, 6 RECEIVE, 7 TRANSMIT, 9 SYSTEM, 10 OFF (autre -> inconnu
        dans le code source lui-même, "default" du switch C#).
      - octets 16-17 (LE) - offset_température(modèle) = température °C.
      - octets 20-21 (LE) / 10.0 = puissance d'excitation (W).
      - octets 22-23 (LE) = puissance de sortie (W).
      - octets 24-25 (LE) = puissance réfléchie, unité RESTÉE AMBIGUË dans
        la source elle-même (affichée juste suffixée "R", aucune formule de
        conversion Watts documentée dans le code) — donc exposée BRUTE
        (`reflected_raw`) plutôt que déguisée en Watts.
      - octets 26-27 (LE) / 100.0 = ROS/SWR.
      - octets 8-9 : octet8*0.1 + octet9*25.6 = puissance DC consommée (W).
      - octet 66 = code d'erreur (0xFF = pas d'erreur ; sinon table
        ACOM_ERROR_CODES ci-dessous, reprise du switch C# — libellés
        traduits en français par ce module, PAS le texte officiel de
        l'écran de l'ampli qui n'a jamais été vu).
      - octet 69 nibble haut = état ventilateur (0=arrêt, 1-4=vitesses).
      - octet 69 nibble bas = index de bande (table BAND_NAMES, confirmée
        dans le code source, gamme 160 m à 4 m).
  - Table de calibration par modèle (offset température, puissances
    nominale/max) CONFIRMÉE pour exactement 5 modèles : 500S/600S/700S
    (défaut)/1200S/2020S — voir ACOM_MODELS. Un modèle absent de cette
    liste ne calibre PAS la température (`temp_c` reste None) plutôt que
    d'appliquer un offset au hasard : les 5 offsets connus vont de 273 à
    282, une erreur de quelques degrés serait silencieuse et trompeuse.

PAS CONFIRMÉ — donc PAS implémenté/deviné dans ce module (règle de la
maison : « un module qui refuse proprement vaut mieux qu'un module qui
invente ») :
  - AUCUNE commande de changement de bande/fréquence n'existe dans ce
    protocole : le champ bande de la télémétrie est une lecture SEULE, la
    bande est déterminée par l'ampli lui-même (poursuite du filtre passe-bas
    en fonction du signal d'excitation reçu, comme les amplis à accord
    automatique classiques) — PAS pilotable depuis LogX, et ce n'est pas un
    manque de cette implémentation mais une caractéristique confirmée du
    protocole lui-même (aucun octet de commande de bande dans TOUT le
    fichier source lu).
  - Aucune commande de réglage de puissance/gain n'existe non plus dans le
    fichier source lu — le panneau de configuration de l'appli C#
    (Config.xaml, non téléchargé) ne sert qu'au choix COM port/modèle
    LOCAUX à l'appli, jamais envoyés à l'ampli.
  - Le transport Ethernet "ACOM eBox" (pont RS-232<->Ethernet officiel
    ACOM) N'EST PAS implémenté ici : son manuel utilisateur (PDF, trouvé via
    WebSearch) n'a pas pu être lu de façon fiable (flux compressés
    FlateDecode illisibles par l'outil de lecture utilisé) — impossible de
    confirmer si le pont est un passe-plat TRANSPARENT du même protocole
    binaire (auquel cas AcomPort/acom_extract_frame resteraient valables
    tels quels sur un socket TCP) ou s'il ajoute son propre enrobage. Pas
    deviné : seul le transport série RS-232 direct est proposé.
  - Le mécanisme d'alimentation physique par CTS/DSR (mentionné par le fil
    FlexRadio ci-dessus) n'est PAS piloté par ce module — seul le triplet
    Operate/Standby/Off (état RF, pas alimentation secteur) l'est. Couper/
    rétablir l'alimentation d'un ampli à distance depuis un logiciel de log
    serait un risque disproportionné pour un bénéfice marginal, alors que
    la sémantique exacte de ces lignes sur le connecteur n'a été vue que
    dans un commentaire de code et un message de forum, jamais dans une doc
    ACOM officielle.
  - Aucune documentation ACOM officielle (site constructeur, manuel PDF des
    modèles 500S/700S/1200S/2020S) ne détaille ce protocole série au niveau
    octet — cherché mais jamais trouvé publiquement. Toute cette
    implémentation repose donc sur UNE SEULE source, quoique de haute
    qualité (logiciel réel, testé sur du vrai matériel, corroboré
    indépendamment sur le point RTS/DTR par un fil de forum tiers).

Comme logx_cat.SerialPort : toute E/S touchant pyserial passe par une seule
classe (`AcomPort`), le cadrage/décodage de trame est séparé en fonctions
PURES testables sans port réel (`acom_extract_frame`/`acom_parse_telemetry`,
même esprit que `civ_parse_frame`/`pgxl_parse_status`). Point d'injection
pour les tests : la variable de module `_open_serial` (remplacée
globalement, même motif que `_open_transport` dans logx_powergenius.py) et
le paramètre `opener=` de `test_connection()`.
"""
import threading
import time

try:
    import serial as _pyserial
    HAS_PYSERIAL = True
except ImportError:
    HAS_PYSERIAL = False

DEFAULT_BAUD = 9600
TELEMETRY_LEN = 72
TELEMETRY_HEADER = b'\x55\x2F'

CMD_ENABLE_TELEMETRY = bytes([0x55, 0x92, 0x04, 0x15])
CMD_DISABLE_TELEMETRY = bytes([0x55, 0x91, 0x04, 0x16])
CMD_OPERATE = bytes([0x55, 0x81, 0x08, 0x02, 0x00, 0x06, 0x00, 0x1A])
CMD_STANDBY = bytes([0x55, 0x81, 0x08, 0x02, 0x00, 0x05, 0x00, 0x1B])
CMD_OFF = bytes([0x55, 0x81, 0x08, 0x02, 0x00, 0x0A, 0x00, 0x16])
_MODE_COMMANDS = {'operate': CMD_OPERATE, 'standby': CMD_STANDBY, 'off': CMD_OFF}

CONNECT_TIMEOUT_S = 3.0
CMD_TIMEOUT_S = 3.0
MIN_TIMEOUT_S = 1.0
MAX_TIMEOUT_S = 10.0

# BandName[] de MainWindow.xaml.cs — index = octet69 & 0x0F.
BAND_NAMES = ('?m', '160m', '80m', '40/60m', '30m', '20m', '17m', '15m',
              '12m', '10m', '6m', '4m', '?m', '?m', '?m', '?m')

ACOM_STATUS = {1: 'RESET', 2: 'INIT', 3: 'DEBUG', 4: 'SERVICE', 5: 'STANDBY',
               6: 'RECEIVE', 7: 'TRANSMIT', 9: 'SYSTEM', 10: 'OFF'}

# Switch(errorCode) de MainWindow.xaml.cs — libellés traduits en français par
# CE module (voir docstring : jamais vu le texte affiché sur l'écran réel).
ACOM_ERROR_CODES = {
    0x00: 'Commutation à chaud (hot switching)',
    0x08: 'Commutation à chaud (hot switching)',
    0x03: "Puissance d'excitation au mauvais moment",
    0x04: 'Avertissement puissance réfléchie',
    0x05: 'Avertissement puissance réfléchie',
    0x06: "Puissance d'excitation trop élevée",
    0x07: "Puissance d'excitation trop élevée",
    0x0C: 'Puissance RF au mauvais moment',
    0x0E: "Arrêter l'émission d'abord",
    0x0F: "Retirer la puissance d'excitation",
    0x24: 'Courant PAM excessif', 0x25: 'Courant PAM excessif',
    0x39: 'Courant PAM excessif', 0x44: 'Courant PAM excessif',
    0x45: 'Courant PAM excessif', 0x59: 'Courant PAM excessif',
    0x70: 'Erreur CAT',
}

# Configuration(ampModel) de MainWindow.xaml.cs — 5 modèles confirmés.
ACOM_MODELS = {
    '500S': {'nominal_fwd_w': 500.0, 'max_fwd_w': 600.0,
              'nominal_rev_w': 99.0, 'max_rev_w': 130.0,
              'temp_offset': 282, 'warning_temp_c': 65},
    '600S': {'nominal_fwd_w': 600.0, 'max_fwd_w': 700.0,
              'nominal_rev_w': 114.0, 'max_rev_w': 150.0,
              'temp_offset': 273, 'warning_temp_c': 65},
    '700S': {'nominal_fwd_w': 700.0, 'max_fwd_w': 800.0,
              'nominal_rev_w': 129.0, 'max_rev_w': 170.0,
              'temp_offset': 282, 'warning_temp_c': 65},
    '1200S': {'nominal_fwd_w': 1200.0, 'max_fwd_w': 1400.0,
               'nominal_rev_w': 228.0, 'max_rev_w': 300.0,
               'temp_offset': 281, 'warning_temp_c': 65},
    '2020S': {'nominal_fwd_w': 1800.0, 'max_fwd_w': 2000.0,
               'nominal_rev_w': 228.0, 'max_rev_w': 300.0,
               'temp_offset': 282, 'warning_temp_c': 65},
}


# ═══════════════════════════════════════════════════════════════════════════
#  Fonctions PURES (cadrage/décodage) — testables sans port série, comme
#  civ_parse_frame()/pgxl_parse_status() dans les modules CAT/amplis voisins.
# ═══════════════════════════════════════════════════════════════════════════

def acom_extract_frame(buf):
    """Cherche une trame de télémétrie ACOM complète et valide (somme de
    tous ses octets == 0 mod 256) dans `buf`. Retourne (frame_72_octets ou
    None, reste) — `reste` : les octets non consommés, à reconcaténer au
    prochain lot lu sur le port série. Ne lève jamais d'exception, avance
    TOUJOURS d'au moins un octet en cas d'échec (resynchronisation), pour ne
    jamais boucler indéfiniment sur un flux corrompu ou mal aligné — même
    esprit que le parseur état-par-état de Port_OnReceiveData() dans
    MainWindow.xaml.cs, réécrit ici comme une fonction PURE sur un tampon
    complet plutôt que comme une machine à état incrémentale (plus simple à
    tester)."""
    if not buf:
        return None, b''
    idx = buf.find(bytes([0x55]))
    if idx < 0:
        return None, b''
    buf = buf[idx:]
    if len(buf) < 2:
        return None, buf
    if buf[1] != 0x2F:
        return None, buf[1:]
    if len(buf) < TELEMETRY_LEN:
        return None, buf
    frame, rest = buf[:TELEMETRY_LEN], buf[TELEMETRY_LEN:]
    if sum(frame) % 256 != 0:
        return None, rest
    return frame, rest


def acom_parse_telemetry(frame, model=None):
    """Décode les champs d'une trame de télémétrie DÉJÀ validée par
    acom_extract_frame() (somme de contrôle correcte) — cette fonction ne
    revérifie pas la somme de contrôle, elle extrait seulement les champs
    (séparation stricte cadrage/décodage). Retourne None si `frame` ne fait
    pas exactement 72 octets.

    `model` (une clé de ACOM_MODELS, ex. '700S') calibre la température —
    sans lui (None ou modèle absent de ACOM_MODELS), 'temp_c' reste None
    plutôt que d'appliquer un offset au hasard (voir docstring du module)."""
    if frame is None or len(frame) != TELEMETRY_LEN:
        return None
    status_code = (frame[3] & 0xF0) >> 4
    fan = (frame[69] & 0xF0) >> 4
    band_index = frame[69] & 0x0F
    drive_raw = frame[20] + frame[21] * 256
    reflected_raw = frame[24] + frame[25] * 256
    power_w = frame[22] + frame[23] * 256
    dc_power_w = round(frame[8] * 0.1 + frame[9] * 25.6, 1)
    error_code = frame[66]
    calib = ACOM_MODELS.get(model)
    temp_raw = frame[16] + frame[17] * 256
    return {
        'status_code': status_code,
        'status': ACOM_STATUS.get(status_code, 'UNKNOWN'),
        'fan': fan,
        'band': BAND_NAMES[band_index],
        'drive_w': round(drive_raw / 10.0, 1),
        'power_w': power_w,
        'reflected_raw': reflected_raw,
        'swr': round((frame[26] + frame[27] * 256) / 100.0, 2),
        'dc_power_w': dc_power_w,
        'temp_c': (temp_raw - calib['temp_offset']) if calib else None,
        'error_code': None if error_code == 0xFF else error_code,
        'error_message': None if error_code == 0xFF else ACOM_ERROR_CODES.get(
            error_code, f"Erreur (code {error_code:#04x}) — voir l'écran de l'ampli"),
        'model': model,
    }


# ═══════════════════════════════════════════════════════════════════════════
#  Transport série (pyserial réel)
# ═══════════════════════════════════════════════════════════════════════════

class AcomPort:
    """Fine couche au-dessus de pyserial pour l'ACOM — un port = un verrou
    d'instance (comme SerialPort dans logx_cat.py)."""

    def __init__(self, device, baudrate=DEFAULT_BAUD, timeout=CONNECT_TIMEOUT_S):
        if not HAS_PYSERIAL:
            raise RuntimeError("pyserial n'est pas installé")
        self._lock = threading.Lock()
        self._buf = b''
        # rts=False, dtr=False : sur l'ACOM ces deux lignes câblent
        # l'ALIMENTATION physique de l'ampli (pas un simple PTT comme sur
        # les interfaces radio habituelles, voir docstring du module) — un
        # état haut, même transitoire à l'ouverture, pourrait couper/
        # rallumer un ampli de plusieurs centaines de watts en pleine
        # séance. Construire fermé (port non assigné), poser les propriétés,
        # PUIS ouvrir : même patron que logx_cat.SerialPort, imposé par
        # pyserial 3.5 qui rejette rts=/dtr= comme kwargs du constructeur
        # (voir mémoire piege-pyserial-rts-dtr-constructeur) — ici l'enjeu
        # matériel est plus grave qu'un simple bug logiciel.
        self._ser = _pyserial.Serial()
        self._ser.port = device
        self._ser.baudrate = baudrate
        self._ser.timeout = timeout
        self._ser.bytesize = 8
        self._ser.parity = 'N'
        self._ser.stopbits = 1
        self._ser.rts = False
        self._ser.dtr = False
        self._ser.open()

    def send_command(self, data):
        with self._lock:
            self._ser.write(data)

    def read_one_frame(self, timeout):
        """Accumule les octets reçus jusqu'à extraire UNE trame de
        télémétrie valide ou expiration du délai. Retourne les 72 octets
        bruts, ou None. Resynchronise automatiquement sur tout octet
        parasite (voir acom_extract_frame). Verrou tenu sur toute la
        fenêtre d'attente : sérialise avec send_command() comme _io_lock
        dans logx_powergenius.py/logx_amp.py."""
        with self._lock:
            deadline = time.monotonic() + timeout
            while True:
                frame, self._buf = acom_extract_frame(self._buf)
                if frame is not None:
                    return frame
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return None
                self._ser.timeout = max(remaining, 0.05)
                chunk = self._ser.read(max(1, self._ser.in_waiting or 1))
                if chunk:
                    self._buf += chunk
                elif remaining <= 0.05:
                    return None

    def close(self):
        # MainWindow_Closed (MainWindow.xaml.cs:125-137) envoie CommandDisable
        # Telemetry avant de fermer le port -- reproduit ici (constat de revue
        # adversariale : CMD_DISABLE_TELEMETRY était défini mais jamais
        # envoyé). Sans risque matériel (contrairement à RTS/DTR) : c'est
        # juste "arrête de m'envoyer la télémétrie", pas une commande
        # Operate/Standby/Off -- une erreur ici (port déjà en défaut) est
        # donc ignorée, la fermeture du port reste la priorité.
        #
        # self._lock tenu ici comme dans send_command()/read_one_frame() --
        # deuxième constat de la même revue adversariale : sans lui, un
        # thread qui bascule Operate/Standby/Off (send_command(), sous
        # verrou) pouvait voir son écriture s'entrelacer sur le fil RS-232
        # avec celle-ci, envoyée depuis un autre thread qui ferme la
        # connexion (ex. changement de port en CONFIG) -- un risque réel,
        # pas seulement théorique, sur un ampli de plusieurs centaines à
        # plusieurs milliers de watts.
        with self._lock:
            try:
                self._ser.write(CMD_DISABLE_TELEMETRY)
            except Exception:
                pass
            try:
                self._ser.close()
            except Exception:
                pass


# ═══════════════════════════════════════════════════════════════════════════
#  Réglages + connexion persistante (même schéma que logx_powergenius.py)
# ═══════════════════════════════════════════════════════════════════════════

def acom_settings(cfg):
    """Réglages ACOM depuis la config CLIENT — fonction PURE, jamais
    d'exception même sur cfg vide/None (même garantie que pgxl_settings()/
    icomremote_settings()). Un modèle non reconnu retombe à None (champs de
    température calibrés désactivés, jamais devinés — voir
    acom_parse_telemetry)."""
    cfg = cfg or {}
    model = (cfg.get('acom_model') or '').strip().upper()
    if model not in ACOM_MODELS:
        model = None
    try:
        timeout = float(cfg.get('acom_timeout') or CMD_TIMEOUT_S)
    except (TypeError, ValueError):
        timeout = CMD_TIMEOUT_S
    timeout = max(MIN_TIMEOUT_S, min(timeout, MAX_TIMEOUT_S))
    return {
        'enabled': bool(cfg.get('acom_enabled')),
        'port': (cfg.get('acom_port') or '').strip(),
        'model': model,
        'baudrate': DEFAULT_BAUD,
        'timeout': timeout,
    }


_persistent = {}
_persistent_lock = threading.Lock()
_io_lock = threading.Lock()   # sérialise commande+lecture (voir logx_amp.py _io_lock)

_open_serial = AcomPort   # point d'injection pour les tests


def _ensure_connected(st, opener=None):
    key = (st['port'], st['baudrate'])
    with _persistent_lock:
        entry = _persistent.get('default')
        if entry and entry['key'] == key:
            return entry['transport'], None
        if entry:
            entry['transport'].close()
            _persistent.pop('default', None)
        if not st['port']:
            return None, "Port série de l'ACOM non configuré"
        fn = opener or _open_serial
        try:
            conn = fn(st['port'], st['baudrate'], st['timeout'])
        except Exception as e:
            return None, f"Impossible d'ouvrir {st['port']} : {e}"
        _persistent['default'] = {'key': key, 'transport': conn}
        return conn, None


def disconnect_persistent():
    with _persistent_lock:
        entry = _persistent.pop('default', None)
    if entry:
        entry['transport'].close()


def get_state(cfg):
    """État courant (télémétrie) — forme unifiée {'enabled','ok','error'?,
    ...} comme get_state() de logx_amp.py/logx_powergenius.py. Active la
    télémétrie puis attend une trame valide."""
    st = acom_settings(cfg)
    if not st['enabled']:
        return {'enabled': False}
    transport, err = _ensure_connected(st)
    if err:
        return {'ok': False, 'error': err, 'enabled': True}
    try:
        with _io_lock:
            transport.send_command(CMD_ENABLE_TELEMETRY)
            frame = transport.read_one_frame(st['timeout'])
    except Exception as e:
        disconnect_persistent()
        return {'ok': False, 'error': f'ACOM injoignable ({e})', 'enabled': True}
    if frame is None:
        return {'ok': False, 'enabled': True, 'error': (
            "Pas de télémétrie reçue de l'ACOM dans le délai imparti "
            "(vérifie le câble RS-232, le port choisi, et que l'ampli est allumé)")}
    out = acom_parse_telemetry(frame, st['model'])
    out['ok'] = True
    out['enabled'] = True
    return out


def set_operate(cfg, mode):
    """Bascule Operate/Standby/Off — DIFFÉREMMENT de set_operate() dans
    logx_powergenius.py (qui refuse explicitement), ceci envoie réellement
    l'une des 3 trames confirmées (voir docstring du module : sémantique non
    ambiguë, gestionnaires de bouton nommés explicitement dans la source).
    `mode` : 'operate' | 'standby' | 'off'."""
    cmd = _MODE_COMMANDS.get(mode)
    if cmd is None:
        return {'ok': False, 'error': (
            f"Mode ACOM inconnu : {mode!r} (attendu 'operate', 'standby' ou 'off')")}
    st = acom_settings(cfg)
    if not st['enabled']:
        return {'ok': False, 'error': 'Pilotage ACOM désactivé (CONFIG)'}
    transport, err = _ensure_connected(st)
    if err:
        return {'ok': False, 'error': err}
    try:
        with _io_lock:
            transport.send_command(cmd)
    except Exception as e:
        disconnect_persistent()
        return {'ok': False, 'error': f'Écriture ACOM impossible : {e}'}
    return {'ok': True, 'mode': mode}


def test_connection(port, model=None, timeout=None, opener=None):
    """Test ÉPHÉMÈRE (bouton CONFIG) : ouvre une connexion séparée, active
    la télémétrie, attend UNE trame valide, ferme — ne touche jamais à la
    connexion persistante utilisée par le polling logbook, et n'envoie
    JAMAIS Operate/Standby/Off (aucun effet de bord sur l'état RF de
    l'ampli, comme test_connection() de logx_powergenius.py).

    `opener=` : factory ponctuelle injectable pour les tests, même motif que
    `transport=` dans logx_powergenius.py — court-circuite `_open_serial`
    quand fourni."""
    port = (port or '').strip()
    if not port:
        return {'ok': False, 'error': 'Port série manquant'}
    model = (model or '').strip().upper()
    if model not in ACOM_MODELS:
        model = None
    try:
        timeout = float(timeout or CMD_TIMEOUT_S)
    except (TypeError, ValueError):
        timeout = CMD_TIMEOUT_S
    fn = opener or _open_serial
    try:
        conn = fn(port, DEFAULT_BAUD, timeout)
    except Exception as e:
        return {'ok': False, 'error': f"Impossible d'ouvrir {port} : {e}"}
    try:
        conn.send_command(CMD_ENABLE_TELEMETRY)
        frame = conn.read_one_frame(timeout)
        if frame is None:
            return {'ok': False, 'error': (
                "Pas de télémétrie reçue dans le délai imparti "
                "(câble/port/ampli éteint ?)")}
        return {'ok': True, 'telemetry': acom_parse_telemetry(frame, model)}
    except Exception as e:
        return {'ok': False, 'error': f'ACOM injoignable ({e})'}
    finally:
        conn.close()
