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
CMD_SET_WPM = 0x02       # suivi de la vitesse en mots/minute
CMD_PTT_LEAD_TAIL = 0x04  # suivi de <lead><tail>, par pas de 10 ms
CMD_CLEAR_BUFFER = 0x0A   # vide le tampon = ARRÊT IMMÉDIAT
CMD_SET_MODE = 0x0E       # registre de mode

BAUD = 1200
WPM_MIN, WPM_MAX = 5, 99

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
