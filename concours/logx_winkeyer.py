# -*- coding: utf-8 -*-
"""Manipulateur WinKeyer K1EL — le standard de fait du concours CW.

Pourquoi ce module alors que la commande KY existe déjà (logx_cat) :

  - KY ne couvre que Kenwood et Elecraft. **Icom ne publie aucune commande
    CI-V d'envoi de texte CW**, et la commande Yaesu homonyme n'a pas la même
    signification selon les modèles. Ces deux marques n'ont donc AUCUNE
    manipulation en mode natif — le WinKeyer est leur seule voie.
  - Même sur les radios qui acceptent KY, la commande passe par le même canal
    série que le reste du pilotage (lecture de fréquence toutes les 3 s,
    changements de bande...). Le WinKeyer, lui, a son propre port et son propre
    processeur : la cadence ne dépend plus du trafic CAT. C'est la raison pour
    laquelle N1MM, Win-Test et DXLog le recommandent tous.

RÉSERVE IMPORTANTE : ce module a été écrit d'après la documentation du
protocole K1EL et ses trames sont vérifiées octet par octet par les tests,
mais **aucun WinKeyer n'a été branché**. Le premier essai sur un boîtier réel
reste à faire.

Particularités du lien série, qui expliquent pourquoi ce module n'utilise pas
la couche série de logx_cat :
  - 1200 bauds, 8 bits, sans parité, **DEUX bits de stop** (logx_cat.SerialPort
    est câblé à un seul) ;
  - le tampon d'entrée ne doit PAS être vidé avant chaque écriture : le
    WinKeyer renvoie des octets d'état non sollicités et l'octet de version à
    l'ouverture, que logx_cat jetterait (il fait reset_input_buffer()).
"""
import threading
import time

try:
    import serial as _pyserial
    HAS_PYSERIAL = True
except ImportError:
    _pyserial = None
    HAS_PYSERIAL = False

# ─── Protocole K1EL ─────────────────────────────────────────────────────────
ADMIN = 0x00           # préfixe des commandes d'administration
ADMIN_RESET = 0x01
ADMIN_HOST_OPEN = 0x02   # réponse : 1 octet = version du micrologiciel
ADMIN_HOST_CLOSE = 0x03
ADMIN_ENABLE_WK3 = 0x14  # 00 14 : active les capacités spécifiques WK3
CMD_SET_SIDETONE = 0x01  # 01 nn : sidetone WK3, nn = round(62500/Hz)
CMD_SET_WPM = 0x02       # suivi de la vitesse en mots/minute
CMD_SET_WEIGHTING = 0x03  # 03 nn : weighting %, 10–90 (50 = neutre)
CMD_PTT_LEAD_TAIL = 0x04  # suivi de <lead><tail>, par pas de 10 ms
CMD_SET_PIN_CONFIG = 0x09  # 09 nn : bits sorties KEY/PTT/sidetone
CMD_CLEAR_BUFFER = 0x0A   # vide le tampon = ARRÊT IMMÉDIAT
CMD_KEY_IMMEDIATE = 0x0B  # 0B 01 / 0B 00 : key down/up (tune manuel)
CMD_SET_FARNSWORTH = 0x0D  # 0D nn : Farnsworth WPM caractères, 10–99
CMD_SET_MODE = 0x0E       # registre de mode
CMD_GET_STATUS = 0x15
CMD_SET_DIT_DAH_RATIO = 0x17  # 17 nn : ratio dit/dah, 33–66 (50 = 1:3)
# ⚠️ le ratio est 0x17 ; 0x0C est HSCW (piège classique des tables WK).

BAUD = 1200
WPM_MIN, WPM_MAX = 5, 99

# ─── Réglages fins WK3 (Phase 2 keyer CW) — opcodes/plages SOURCÉS K1EL WK3.1 ──
# Fonctions PURES : construisent la trame octet(s) et lèvent ValueError hors
# plage. AUCUNE émission ici (pas de port ouvert) — le câblage à l'ouverture et
# l'UI de réglage sont séparés, l'essai on-air reste supervisé par l'opérateur.

# Bits PINCFG (0x09) : le PTT n'agit QUE si son bit est activé ici (régler le
# lead/tail via 0x04 ne suffit pas).
PINCFG_PTT = 0x01
PINCFG_SIDETONE = 0x02
PINCFG_KEY_2 = 0x04
PINCFG_KEY_1 = 0x08

# Bits MODE (0x0E). Le watchdog paddle doit rester ACTIF par défaut (bit à 0 :
# ne PAS poser MODE_DISABLE_PADDLE_WATCHDOG) — il coupe après 128 éléments
# consécutifs, protection contre un paddle bloqué.
MODE_DISABLE_PADDLE_WATCHDOG = 0x80
MODE_PADDLE_ECHOBACK = 0x40
MODE_IAMBIC_B = 0x00
MODE_IAMBIC_A = 0x10
MODE_ULTIMATIC = 0x20
MODE_BUG = 0x30
MODE_SWAP_PADDLES = 0x08
MODE_SERIAL_ECHOBACK = 0x04
MODE_AUTOSPACE = 0x02
MODE_CONTEST_SPACING = 0x01
MODE_LOGX_DEFAUT = MODE_IAMBIC_A | MODE_SERIAL_ECHOBACK | MODE_AUTOSPACE   # 0x16


def wk_set_weighting(percent):
    """03 nn — weighting %. 10–90 (50 = neutre ; <50 éléments plus courts)."""
    if not 10 <= percent <= 90:
        raise ValueError("weighting WinKeyer hors plage 10–90")
    return bytes([CMD_SET_WEIGHTING, percent])


def wk_set_dit_dah_ratio(value):
    """17 nn — ratio dit/dah. 33–66 (50 = 1:3 standard ; dah/dit = 3*nn/50)."""
    if not 33 <= value <= 66:
        raise ValueError("ratio dit/dah WinKeyer hors plage 33–66")
    return bytes([CMD_SET_DIT_DAH_RATIO, value])


def wk_set_farnsworth(character_wpm):
    """0D nn — Farnsworth : WPM des CARACTÈRES (≥ WPM global). 10–99.
    NE PAS envoyer 0 en hôte WK3 (désactivation) sans essai matériel."""
    if not 10 <= character_wpm <= 99:
        raise ValueError("Farnsworth WinKeyer hors plage 10–99 WPM")
    return bytes([CMD_SET_FARNSWORTH, character_wpm])


def wk_set_sidetone(frequency_hz):
    """01 nn — sidetone WK3. 500–4000 Hz, nn = round(62500/Hz)."""
    if not 500 <= frequency_hz <= 4000:
        raise ValueError("sidetone WK3 hors plage 500–4000 Hz")
    return bytes([CMD_SET_SIDETONE, round(62500 / frequency_hz)])


def wk_set_ptt_lead_tail(lead_ms, tail_ms):
    """04 lead tail — délais PTT, pas de 10 ms, 0–2500 ms. Le tail RÉEL garde en
    plus 3 temps de dit (04 00 00 ne coupe donc pas instantanément)."""
    if lead_ms % 10 or tail_ms % 10:
        raise ValueError("lead/tail PTT doivent être des multiples de 10 ms")
    lead, tail = lead_ms // 10, tail_ms // 10
    if not 0 <= lead <= 250:
        raise ValueError("lead PTT hors plage 0–2500 ms")
    if not 0 <= tail <= 250:
        raise ValueError("tail PTT hors plage 0–2500 ms")
    return bytes([CMD_PTT_LEAD_TAIL, lead, tail])


def wk_set_pin_config(pin_config):
    """09 nn — bits PINCFG (KEY1/KEY2/PTT/sidetone). Sans le bit PTT, 0x04 ne
    produit aucun PTT."""
    if not 0 <= pin_config <= 255:
        raise ValueError("PINCFG WinKeyer hors plage 0–255")
    return bytes([CMD_SET_PIN_CONFIG, pin_config])


def wk_set_mode(mode_bits):
    """0E nn — registre de mode (Iambic A/B, Ultimatic, Bug, autospace…)."""
    if not 0 <= mode_bits <= 255:
        raise ValueError("mode WinKeyer hors plage 0–255")
    return bytes([CMD_SET_MODE, mode_bits])

# Un octet d'état du WinKeyer a ses deux bits de poids fort à 1. Sert à
# distinguer un état d'un écho de caractère quand on lit le port.
MASQUE_ETAT = 0xC0

# Jeu de caractères manipulable. Identique à celui de la voie KY (logx_cat)
# pour qu'une macro se comporte pareil quel que soit le manipulateur utilisé.
CARACTERES = set('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 /?.,=+-')

_lock = threading.Lock()
_port = None          # connexion persistante : ouvrir/fermer à chaque macro
_port_nom = None      # coûterait ~1 s et couperait le début du message
_version = None


class PortWinKeyer:
    """Couche série minimale, aux réglages exigés par le WinKeyer."""

    def __init__(self, device, timeout=1.0):
        if not HAS_PYSERIAL:
            raise RuntimeError("pyserial n'est pas installé")
        # rts=False, dtr=False : évite de lever ces lignes par défaut à
        # l'ouverture (voir logx_cat.py:SerialPort, même correctif) — sur
        # certains câblages simplifiés, RTS/DTR sert de ligne de clé/PTT
        # auxiliaire ; on ne veut jamais keyer au simple fait d'ouvrir le
        # port (ouverture/fermeture répétée possible lors d'un test).
        # pyserial n'accepte PAS rts=/dtr= comme arguments du constructeur
        # (ValueError) — seulement comme propriétés d'instance à poser AVANT
        # open() (voir logx_cat.py:SerialPort pour le détail, corrigé en
        # même temps ici après une revue adversariale avant fusion).
        self._ser = _pyserial.Serial()
        self._ser.port = device
        self._ser.baudrate = BAUD
        self._ser.timeout = timeout
        self._ser.bytesize = 8
        self._ser.parity = 'N'
        self._ser.stopbits = 2
        self._ser.rts = False
        self._ser.dtr = False
        self._ser.open()

    def write(self, data):
        self._ser.write(bytes(data))

    def read(self, n=1, timeout=1.0):
        self._ser.timeout = timeout
        return self._ser.read(n)

    def close(self):
        try:
            self._ser.close()
        except Exception:
            pass


# Point d'injection pour les tests : remplacé par un double qui ne touche
# aucun port réel (même motif que logx_cat._open_serial).
_ouvrir_port = PortWinKeyer


def parametres(cfg):
    cfg = cfg or {}
    wpm = cfg.get('winkeyer_wpm', 25)
    try:
        wpm = int(wpm)
    except (TypeError, ValueError):
        wpm = 25
    return {
        'enabled': str(cfg.get('winkeyer_enabled', '')).strip() not in ('', '0', 'False', 'false'),
        'port': str(cfg.get('winkeyer_port', '') or '').strip(),
        'wpm': max(WPM_MIN, min(WPM_MAX, wpm)),
    }


def _fermer_locked():
    global _port, _port_nom, _version
    if _port is not None:
        try:
            _port.write(bytes([ADMIN, ADMIN_HOST_CLOSE]))
        except Exception:
            pass
        _port.close()
    _port = None
    _port_nom = None
    _version = None


def fermer():
    with _lock:
        _fermer_locked()
    return {'ok': True}


def _ouvrir_locked(nom_port, wpm):
    """Ouvre et fait entrer le WinKeyer en mode piloté.

    L'ouverture RENVOIE la version du micrologiciel : c'est la seule preuve
    qu'un WinKeyer est bien au bout du câble. Sans cette lecture, un port série
    quelconque (adaptateur USB sans rien derrière) passerait pour un
    manipulateur, et les macros partiraient dans le vide sans le moindre
    message."""
    global _port, _port_nom, _version
    if _port is not None and _port_nom == nom_port:
        return None
    _fermer_locked()
    # L'ouverture d'un port série lève sur tout ce qui va de travers : port
    # inexistant, déjà pris par un autre logiciel, droits insuffisants,
    # pyserial absent. Cet appel vient du handler HTTP : laisser filer
    # l'exception tuait la connexion SANS RÉPONSE — le navigateur affichait un
    # échec réseau au lieu de « port introuvable ». Trouvé sur serveur réel ;
    # le faux boîtier des tests, lui, ne lève jamais à la construction.
    try:
        _port = _ouvrir_port(nom_port)
    except Exception as e:
        _port = None
        return "Port %s inutilisable (%s)" % (nom_port, e)
    _port_nom = nom_port
    # Le boîtier a besoin d'un instant après ouverture du port avant d'accepter
    # la commande d'ouverture de session.
    time.sleep(0.05)
    try:
        _port.write(bytes([ADMIN, ADMIN_HOST_OPEN]))
        reponse = _port.read(1, timeout=2.0)
        # Un octet d'état résiduel (MASQUE_ETAT) peut précéder la vraie
        # réponse si le boîtier avait déjà quelque chose en attente.
        essais = 0
        while reponse and (reponse[0] & MASQUE_ETAT) == MASQUE_ETAT and essais < 4:
            reponse = _port.read(1, timeout=0.5)
            essais += 1
    except Exception as e:
        _fermer_locked()
        return 'WinKeyer injoignable sur %s (%s)' % (nom_port, e)
    if not reponse:
        _fermer_locked()
        return ("Aucune réponse du WinKeyer sur %s — vérifie le port, "
                "l'alimentation du boîtier et le câble" % nom_port)
    _version = reponse[0]
    _port.write(bytes([CMD_SET_WPM, wpm]))
    return None


def _nettoyer(texte):
    propre = ''.join(c for c in str(texte or '').upper() if c in CARACTERES)
    return ' '.join(propre.split())


def envoyer(cfg, texte):
    """Manipule `texte`. Ne lève jamais : {'ok': bool, 'error'?: str}."""
    p = parametres(cfg)
    if not p['enabled']:
        return {'ok': False, 'error': 'WinKeyer désactivé (CONFIG)'}
    if not p['port']:
        return {'ok': False, 'error': 'Port du WinKeyer non renseigné (CONFIG)'}
    propre = _nettoyer(texte)
    if not propre:
        return {'ok': False, 'error': 'Rien à manipuler (texte vide après filtrage)'}
    with _lock:
        err = _ouvrir_locked(p['port'], p['wpm'])
        if err:
            return {'ok': False, 'error': err}
        try:
            _port.write(bytes([CMD_SET_WPM, p['wpm']]))
            _port.write(propre.encode('ascii'))
        except Exception as e:
            _fermer_locked()
            return {'ok': False, 'error': 'WinKeyer injoignable (%s)' % e}
    return {'ok': True, 'text': propre, 'wpm': p['wpm']}


def arreter(cfg):
    """Vide le tampon du manipulateur — arrêt immédiat du message en cours.

    N'ouvre PAS la connexion si elle ne l'est pas déjà : demander l'arrêt d'un
    manipulateur qui ne manipule pas n'a pas à faire clignoter un boîtier ni à
    remonter une erreur de port."""
    p = parametres(cfg)
    if not p['enabled']:
        return {'ok': False, 'error': 'WinKeyer désactivé (CONFIG)'}
    with _lock:
        if _port is None:
            return {'ok': True, 'note': 'rien en cours'}
        try:
            _port.write(bytes([CMD_CLEAR_BUFFER]))
        except Exception as e:
            _fermer_locked()
            return {'ok': False, 'error': 'WinKeyer injoignable (%s)' % e}
    return {'ok': True}


def tester(cfg):
    """Bouton « Tester » de la page CONFIG : ouvre, lit la version, garde la
    connexion. La version est l'information utile — elle prouve que c'est bien
    un WinKeyer et dit lequel."""
    p = parametres(cfg)
    if not p['port']:
        return {'ok': False, 'error': 'Port du WinKeyer non renseigné'}
    with _lock:
        err = _ouvrir_locked(p['port'], p['wpm'])
        if err:
            return {'ok': False, 'error': err}
        v = _version
    return {'ok': True, 'version': v,
            'version_texte': 'WinKeyer v%d.%d' % (v // 10, v % 10) if v else '?'}
