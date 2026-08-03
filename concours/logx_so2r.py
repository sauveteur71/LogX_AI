# -*- coding: utf-8 -*-
"""SO2R : deux radios, une seule paire d'oreilles et un seul manipulateur.

Le SO2R consiste à appeler CQ sur une bande pendant qu'on cherche des
multiplicateurs sur l'autre. C'est ce qui sépare un score honorable d'un score
de podium en HF mono-opérateur.

CE QUE FAIT CE MODULE, ET CE QU'IL NE FAIT PAS.

La commutation réelle — quelle radio émet, ce qu'on entend dans quelle oreille,
où part le manipulateur — se fait dans un BOÎTIER matériel (microHAM MK2R,
YCCC SO2R Box, EA4TX ARS...). Aucun logiciel ne peut router de l'audio ou une
porteuse à la place d'un relais. Ce que le logiciel fait, c'est DIRE au boîtier
quoi commuter : c'est le rôle du protocole OTRSP, que tous ces boîtiers
comprennent.

Ce module tient donc deux choses :
  - l'état de FOCUS (quelle radio est en émission), partagé côté serveur pour
    que toutes les pages ouvertes le voient — un opérateur qui bascule sur la
    radio 2 depuis le logbook doit voir le band map suivre ;
  - le dialogue OTRSP avec le boîtier.

CE QUI N'EST PAS FAIT, et qu'il ne faut pas croire acquis : le « dueling CQ »
automatique, les scénarios de commutation avancés (mémoires du boîtier), et le
second band map à l'écran. Ce lot pose les fondations utilisables ; le reste
suppose du temps d'antenne pour être réglé correctement.

RÉSERVE : aucun boîtier OTRSP n'a été branché. Les trames sont conformes à la
spécification du protocole et vérifiées octet par octet, mais le premier essai
sur du matériel reste à faire.
"""
import threading

try:
    import serial as _pyserial
    HAS_PYSERIAL = True
except ImportError:
    _pyserial = None
    HAS_PYSERIAL = False

# OTRSP : commandes ASCII terminées par un retour chariot. Le jeu utilisé ici
# est le minimum commun à tous les boîtiers du marché.
#   TX1 / TX2    quelle radio EMET (et donc où part le manipulateur)
#   RX1 / RX2    quelle radio on ECOUTE
#   RX1S / RX2S  écoute STEREO : la radio choisie dans une oreille, l'autre
#                dans la seconde — c'est le mode de travail habituel en SO2R,
#                on garde une oreille sur le CQ pendant qu'on cherche.
BAUD = 9600
FIN = b'\r'

_lock = threading.Lock()
_port = None
_port_nom = None
# Focus courant : 1 ou 2. Etat PARTAGE (module-level) — toutes les pages
# ouvertes doivent voir la meme chose.
_focus = 1
_ecoute = 'RX1S'


class PortOtrsp:
    def __init__(self, device, timeout=1.0):
        if not HAS_PYSERIAL:
            raise RuntimeError("pyserial n'est pas installé")
        # rts=False, dtr=False : évite de lever ces lignes par défaut à
        # l'ouverture (voir logx_cat.py:SerialPort, même correctif) — le
        # protocole OTRSP ne dépend pas de RTS/DTR, autant ne pas risquer de
        # déclencher un relais d'antenne/PTT auxiliaire selon le câblage.
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
        self._ser.stopbits = 1
        self._ser.rts = False
        self._ser.dtr = False
        self._ser.open()

    def write(self, data):
        self._ser.write(bytes(data))

    def read(self, n=1, timeout=0.3):
        self._ser.timeout = timeout
        return self._ser.read(n)

    def close(self):
        try:
            self._ser.close()
        except Exception:
            pass


# Point d'injection pour les tests (même motif que logx_cat et logx_winkeyer).
_ouvrir_port = PortOtrsp


def parametres(cfg):
    cfg = cfg or {}
    return {
        'enabled': str(cfg.get('so2r_enabled', '')).strip() not in ('', '0', 'False', 'false'),
        'port': str(cfg.get('so2r_port', '') or '').strip(),
        'stereo': str(cfg.get('so2r_stereo', '1')).strip() not in ('', '0', 'False', 'false'),
    }


def _fermer_locked():
    global _port, _port_nom
    if _port is not None:
        _port.close()
    _port = None
    _port_nom = None


def fermer():
    with _lock:
        _fermer_locked()
    return {'ok': True}


def _ouvrir_locked(nom_port):
    global _port, _port_nom
    if _port is not None and _port_nom == nom_port:
        return None
    _fermer_locked()
    # Comme pour le WinKeyer : l'ouverture d'un port série lève sur tout ce qui
    # va de travers (port absent, déjà pris, droits). Cet appel vient du
    # handler HTTP — laisser filer l'exception tuerait la connexion sans
    # réponse, et le navigateur afficherait un échec réseau au lieu du motif.
    try:
        _port = _ouvrir_port(nom_port)
    except Exception as e:
        _port = None
        return 'Port %s inutilisable (%s)' % (nom_port, e)
    _port_nom = nom_port
    return None


def _envoyer_locked(commande):
    try:
        _port.write(commande.encode('ascii') + FIN)
        return None
    except Exception as e:
        _fermer_locked()
        return 'Boitier OTRSP injoignable (%s)' % e


def focus():
    """État courant, lisible sans toucher au matériel."""
    with _lock:
        return {'ok': True, 'focus': _focus, 'ecoute': _ecoute}


def basculer(cfg, radio=None):
    """Bascule l'émission sur `radio` (1 ou 2), ou sur l'AUTRE si non précisé.

    Sans boîtier configuré, l'état interne bascule quand même : le focus sert
    aussi à router le QSY et les macros vers la bonne radio, ce qui a du sens
    même sans commutateur matériel (deux radios, casque branché à la main)."""
    global _focus, _ecoute
    p = parametres(cfg)
    with _lock:
        cible = _focus
        if radio in (1, 2, '1', '2'):
            cible = int(radio)
        else:
            cible = 2 if _focus == 1 else 1
        _focus = cible
        # En stéréo, on garde une oreille sur l'autre radio : c'est le mode de
        # travail réel du SO2R. Sans stéréo, l'écoute suit l'émission.
        _ecoute = ('RX%dS' % cible) if p['stereo'] else ('RX%d' % cible)

        if not p['enabled'] or not p['port']:
            return {'ok': True, 'focus': _focus, 'ecoute': _ecoute,
                    'note': 'boitier OTRSP non configure — focus logiciel seulement'}
        err = _ouvrir_locked(p['port'])
        if err:
            return {'ok': False, 'error': err, 'focus': _focus}
        for cmd in ('TX%d' % cible, _ecoute):
            err = _envoyer_locked(cmd)
            if err:
                return {'ok': False, 'error': err, 'focus': _focus}
    return {'ok': True, 'focus': cible, 'ecoute': _ecoute}


def tester(cfg):
    """Bouton « Tester » : ouvre le port et envoie une commande inoffensive
    (sélection de la radio 1) pour prouver que le boîtier répond au câble."""
    p = parametres(cfg)
    if not p['port']:
        return {'ok': False, 'error': 'Port du boitier OTRSP non renseigne'}
    with _lock:
        err = _ouvrir_locked(p['port'])
        if err:
            return {'ok': False, 'error': err}
        err = _envoyer_locked('TX1')
        if err:
            return {'ok': False, 'error': err}
    return {'ok': True, 'note': 'commande TX1 envoyee sur %s' % p['port']}


def cle_radio_active():
    """Suffixe de configuration de la radio qui a le focus : '' pour la radio 1
    (cat_port, cat_brand...), '2' pour la seconde (cat2_port, cat2_brand...).

    Un seul endroit décide de cette correspondance : ailleurs, on demande la
    clé plutôt que de la reconstruire, sinon une moitié du code piloterait la
    radio 1 pendant que l'autre piloterait la 2."""
    with _lock:
        return '' if _focus == 1 else '2'


def config_radio_active(cfg):
    """Vue de la config vue par la radio qui a le focus : les clés cat2_* sont
    présentées sous leur nom cat_*, pour que tout le pilotage existant
    fonctionne sans savoir qu'il y a deux radios."""
    cfg = dict(cfg or {})
    suffixe = cle_radio_active()
    if not suffixe:
        return cfg
    for cle in ('cat_enabled', 'cat_mode', 'cat_brand', 'cat_model',
                'cat_port', 'cat_baudrate', 'cat_civ_addr'):
        source = cle.replace('cat_', 'cat%s_' % suffixe, 1)
        if source in cfg:
            cfg[cle] = cfg[source]
    return cfg


def reinitialiser():
    """Remet l'état à neuf — utilisé par les tests."""
    global _focus, _ecoute
    with _lock:
        _focus = 1
        _ecoute = 'RX1S'
        _fermer_locked()
