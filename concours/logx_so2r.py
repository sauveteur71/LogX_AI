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
import time

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


def config_radio_active(cfg, radio=None):
    """Vue de la config vue par la radio qui a le focus : les clés cat2_* sont
    présentées sous leur nom cat_*, pour que tout le pilotage existant
    fonctionne sans savoir qu'il y a deux radios.

    `radio` (1 ou 2, optionnel) : force la radio plutôt que de relire le focus
    courant. À utiliser quand l'appelant a DÉJÀ lu `so2r.focus()` une fois
    pour une même requête HTTP (ex. pour armer le verrou TX) — repasser cette
    même valeur ici évite une SECONDE lecture indépendante de l'état de focus
    partagé, qui pourrait diverger de la première si un `/so2r/focus`
    concurrent bascule entre les deux (trouvé en revue adversariale
    07/08/2026 : le verrou TX pouvait alors protéger une radio différente de
    celle réellement pilotée par cette config)."""
    cfg = dict(cfg or {})
    suffixe = ('' if radio == 1 else '2') if radio in (1, 2) else cle_radio_active()
    if not suffixe:
        return cfg
    for cle in ('cat_enabled', 'cat_mode', 'cat_brand', 'cat_model',
                'cat_port', 'cat_baudrate', 'cat_civ_addr'):
        source = cle.replace('cat_', 'cat%s_' % suffixe, 1)
        if source in cfg:
            cfg[cle] = cfg[source]
    # ─── PTT MATÉRIEL : jamais d'héritage entre les deux radios ─────────────
    #
    # 🚨 DÉFAUT CRITIQUE TROUVÉ EN REVUE ADVERSARIALE (20/08/2026) et vérifié
    # sur ce code. La boucle ci-dessus ne recopie que si la clé cat2_* EXISTE ;
    # sinon la valeur de la radio 1 RESTE en place. Pour un débit ou une
    # adresse CI-V, hériter est au pire inutile. Pour le PTT, c'est un
    # sinistre : avec le focus sur la radio 2 et un `cat_ptt_port` réglé pour
    # la radio 1, port_ptt_effectif() renvoyait le port de la RADIO 1 — donc
    # LogX AI levait la ligne d'émission sur un poste pendant que l'écran en
    # montrait un autre. Exactement les deux porteuses simultanées que le
    # verrou TX de ce module existe pour empêcher.
    #
    # Le câblage d'un PTT est du MATÉRIEL propre à chaque poste : l'hériter
    # n'est jamais correct. En l'absence de réglage explicite pour la radio
    # visée, on retombe donc sur la commande CAT — le comportement historique,
    # qui n'actionne aucune broche.
    for cle in ('cat_ptt_method', 'cat_ptt_port'):
        source = cle.replace('cat_', 'cat%s_' % suffixe, 1)
        cfg[cle] = cfg.get(source, '')
    # OmniRig (Phase 1, MVP logiciel-seul) : quel numero de radio COTE
    # OMNIRIG (Rig1/Rig2) -- la radio 1 s'appelle omnirig_rig_num, pas
    # cat_omnirig_rig_num, donc hors de la boucle generique ci-dessus. Sans
    # ce remap, la radio 2 en mode OmniRig piloterait le MEME Rig1/Rig2 que
    # la radio 1 (voir docs/ETUDE_SO2R.md, question ouverte #1 -- corrige ici).
    if 'cat2_omnirig_rig_num' in cfg:
        cfg['omnirig_rig_num'] = cfg['cat2_omnirig_rig_num']
    # 'omnirig_enabled' est un second interrupteur "ceinture-et-bretelles"
    # verifie par logx_omnirig.omnirig_settings() INDEPENDAMMENT de cat_mode
    # -- mais logx_configuration.html ne le calcule QUE depuis cat_enabled/
    # cat_mode de la RADIO 1 (jamais cat2_*). Sans cette ligne, la radio 2 en
    # OmniRig (le mode recommande par l'UI pour la radio 2, cat_mode est lui
    # bien remappe ci-dessus) se voit refuser tout pilotage avec "Pilotage
    # OmniRig desactive (CONFIG)" des que la radio 1 n'est pas elle-meme en
    # OmniRig -- bug critique trouve en revue adversariale (07/08/2026).
    cfg['omnirig_enabled'] = (cfg.get('cat_mode') == 'omnirig'
                               and str(cfg.get('cat_enabled', '')).strip()
                               not in ('', '0', 'False', 'false'))
    # Keyer vocal (Phase 2 SO2R) : périphérique de sortie propre à la radio 2
    # -- pas préfixé cat_ non plus (voicekeyer_device, pas cat_voicekeyer_device),
    # donc hors de la boucle générique. play_wav(path, device_index) accepte
    # déjà un device par appel ; sans ce remap, un message vocal émis alors
    # que la radio 2 a le focus sortirait quand même par le périphérique de
    # la radio 1.
    if 'voicekeyer_device2' in cfg:
        cfg['voicekeyer_device'] = cfg['voicekeyer_device2']
    return cfg


# ─── Verrou d'exclusivité TX ─────────────────────────────────────────────────
# Le focus (ci-dessus) route le PILOTAGE vers la bonne radio, mais ne garantit
# rien : rien n'empêchait jusqu'ici d'armer un ordre d'émission (PTT/CW/voix)
# sur la radio 2 pendant que la radio 1 est encore en train d'émettre. Un log
# avec deux porteuses actives en même temps est disqualifiable dans la plupart
# des règlements de concours (ex. CQ WW : « Only one transmitted signal is
# permitted at any time ») — ce verrou logiciel réduit CE risque précis,
# équivalent du « First One Wins » de N1MM+. Il ne protège PAS le matériel
# (désensibilisation/dégât récepteur voisin) : ça reste hors de portée
# logicielle, voir docs/ETUDE_SO2R.md §2.
#
# TX_LOCK_TIMEOUT_S : un verrou "collé" (radio déconnectée en cours
# d'émission, plantage du keyer, opérateur qui ne relâche jamais explicitement
# via /rig/stop) doit se libérer tout seul plutôt que bloquer l'opérateur
# indéfiniment sur l'autre radio. 2 minutes dépasse largement un message DVK
# (plafonné à 10 Mo PCM16, ~2 min à 44,1 kHz) ou une manip CW normale ; valeur
# de départ ajustable si l'usage réel montre qu'elle est mal calibrée.
TX_LOCK_TIMEOUT_S = 120

_tx_lock = threading.Lock()
_tx_radio = None    # 1 ou 2 : quelle radio est censée émettre, None si aucune
_tx_armee_a = 0.0    # time.monotonic() au moment de l'armement
_tx_source = ''      # 'cw' / 'ptt' / 'voix' : QUI l'a pris (voir deverrouiller_tx)


def verrouiller_tx(radio, source=''):
    """Arme le verrou d'exclusivité TX pour `radio` (1 ou 2), à appeler AVANT
    tout ordre d'émission (PTT ON, envoi CW, message vocal). Refuse si l'AUTRE
    radio est déjà armée et le verrou n'a pas expiré.

    Auto-nettoyant : un verrou périmé (TX_LOCK_TIMEOUT_S dépassé) est traité
    comme libre, pas besoin d'un déblocage manuel après un incident.

    `source` : QUI prend le verrou ('cw', 'ptt', 'voix'). Sert uniquement à
    empêcher qu'un chemin d'arrêt libère le verrou d'un AUTRE chemin — voir
    deverrouiller_tx(). Vide = anonyme, comportement d'avant."""
    global _tx_radio, _tx_armee_a, _tx_source
    with _tx_lock:
        maintenant = time.monotonic()
        if (_tx_radio is not None and _tx_radio != radio
                and (maintenant - _tx_armee_a) < TX_LOCK_TIMEOUT_S):
            return {'ok': False, 'error':
                    'Radio %d deja en emission (verrou TX exclusif) -- '
                    'attends la fin ou %.0fs' %
                    (_tx_radio, TX_LOCK_TIMEOUT_S - (maintenant - _tx_armee_a))}
        _tx_radio = radio
        _tx_armee_a = maintenant
        _tx_source = source or ''
        return {'ok': True}


def deverrouiller_tx(radio, source=None):
    """Lève le verrou si `radio` le détient encore — jamais celui d'une AUTRE
    radio (un relâchement tardif/en échec de la radio 1 ne doit pas effacer un
    verrou fraîchement pris par la radio 2).

    `source` : si fournie, ne lève le verrou QUE s'il a été pris par cette
    même source. DÉFAUT RÉEL du 20/08/2026 : Échap envoie /rig/stop dès qu'un
    pilote CW existe (coupe-circuit voulu, logx_theme_shortcuts.js), et
    /rig/stop levait le verrou SANS REGARDER qui le détenait. Or /rig/ptt le
    prend aussi — c'est par là que passe le séquenceur FT8. Un Échap réflexe
    pour fermer une popup libérait donc le verrou pendant que le FT8 émettait,
    et la radio 2 pouvait alors prendre la parole en même temps : exactement
    les deux porteuses simultanées que ce verrou existe pour empêcher.

    None = comportement historique (lève quoi qu'il arrive), conservé pour les
    chemins qui relâchent LEUR PROPRE verrou dans la même requête."""
    global _tx_radio, _tx_source
    with _tx_lock:
        if _tx_radio == radio and (source is None or _tx_source == source):
            _tx_radio = None
            _tx_source = ''


def tx_actif():
    """État courant du verrou — pour diagnostic (/so2r/state) ET pour cibler la
    radio du STOP matériel (logx_http /rig/stop lit ['radio']). Lecture seule.

    Applique la MÊME expiration que verrouiller_tx() : un verrou périmé
    (TX_LOCK_TIMEOUT_S dépassé) est traité comme LIBRE (radio=None). Sans ça,
    /so2r/state affichait une radio « en émission » alors que le verrou était en
    réalité déjà relâché, et /rig/stop ciblait cette radio périmée au lieu du
    focus courant."""
    with _tx_lock:
        actif = (_tx_radio is not None
                 and (time.monotonic() - _tx_armee_a) < TX_LOCK_TIMEOUT_S)
        return {'radio': _tx_radio if actif else None,
                'depuis_s': round(time.monotonic() - _tx_armee_a, 1) if actif else 0}


def reinitialiser():
    """Remet l'état à neuf — utilisé par les tests."""
    global _focus, _ecoute, _tx_radio, _tx_armee_a, _tx_source
    with _lock:
        _focus = 1
        _ecoute = 'RX1S'
        _fermer_locked()
    with _tx_lock:
        _tx_radio = None
        _tx_armee_a = 0.0
        _tx_source = ''   # invariant : pas de source sans verrou
