# -*- coding: utf-8 -*-
"""Pilotage CAT NATIF (pyserial direct) — sans dépendance à Hamlib/rigctld.

Deux familles de protocole, chacune vérifiée sur les manuels constructeurs
officiels (voir "commande radio pc/Commandes_Pilotage_Radio_PC.md" pour le
détail complet et les sources) :
  - CI-V (Icom, + Xiegu qui l'émule) : trames binaires FE FE ... FD.
  - ASCII générique (Yaesu / Kenwood / Elecraft) : commandes 2 lettres + `;`,
    quasi identiques entre les trois marques (FA/FB/MD/IF/ID/TX/SM/PC/FT/FR),
    avec des tables de correspondance par marque pour les codes de mode et
    les particularités de split.

La logique de trame (encodage/décodage) est séparée du transport série pour
être testable sans matériel : les fonctions `civ_*` et `ascii_*` ne prennent
que des bytes/str en entrée et en sortie. `SerialPort` est la seule classe
qui touche pyserial ; les tests lui substituent un double en mémoire.

Complète logx_rig.py (rigctld/Hamlib) plutôt que le remplacer : ce
module est le choix par défaut pour les marques couvertes nativement
(Icom/Xiegu/Yaesu/Kenwood/Elecraft), rigctld reste l'option "avancé" pour
tout le reste (Ten-Tec, RGO, modèles anciens...).
"""
import threading
import time

try:
    import serial as _pyserial
    import serial.tools.list_ports as _list_ports
    HAS_PYSERIAL = True
except ImportError:
    HAS_PYSERIAL = False


def list_ports():
    """Ports série disponibles : [{'device': 'COM3', 'description': '...',
    'vid': 0x10C4, 'pid': 0xEA60, 'serial_number': '...', 'product': '...'}].
    vid/pid/serial_number/product peuvent être None (port non-USB, ou champ
    non exposé par la plateforme) — jamais d'exception (appelé depuis l'UI
    de configuration, et depuis le pré-filtre passif marque/modèle : voir
    guess_from_usb_signature())."""
    if not HAS_PYSERIAL:
        return []
    try:
        return [{'device': p.device, 'description': p.description or '',
                  'vid': p.vid, 'pid': p.pid,
                  'serial_number': p.serial_number,
                  'product': p.product}
                for p in _list_ports.comports()]
    except Exception:
        return []


# VID:PID de boîtiers d'interface radioamateur dédiés — PID réservé auprès
# du fondeur de la puce par le fabricant, donc DISTINCTIF (contrairement aux
# puces génériques FTDI/CP210x/CH340/PL2303 partagées par des centaines de
# produits sans rapport). Sourcé des tables d'ID des pilotes Linux upstream
# (ftdi_sio_ids.h, cp210x.c) — voir mémoire du chantier CAT plug-and-play
# (03/08/2026). Liste non exhaustive, à compléter au fil des retours béta.
KNOWN_INTERFACE_VIDPID = {
    (0x0403, 0xEEE8): 'microHAM USB Interface (USB-KW)',
    (0x0403, 0xEEE9): 'microHAM USB Interface (USB-YS)',
    (0x0403, 0xEEEA): 'microHAM USB Interface (USB-Y6)',
    (0x0403, 0xEEEB): 'microHAM USB Interface (USB-Y8)',
    (0x0403, 0xEEEC): 'microHAM USB Interface (USB-IC)',
    (0x0403, 0xEEED): 'microHAM USB Interface (USB-DB9)',
    (0x0403, 0xEEEE): 'microHAM USB Interface (USB-RS232)',
    (0x0403, 0xEEEF): 'microHAM USB Interface (USB-Y9)',
    (0x10C4, 0x814A): 'West Mountain Radio RIGblaster Plug&Play',
    (0x10C4, 0x814B): 'West Mountain Radio RIGtalk',
    (0x2405, 0x0003): 'West Mountain Radio RIGblaster Advantage',
}


def guess_from_usb_signature(port):
    """Devine marque/modèle/interface à partir du seul VID:PID/numéro de
    série d'un port (`port` = un des dicts renvoyés par list_ports()) —
    AUCUN octet CAT envoyé, donc AUCUN risque. Retourne un indice
    ({'kind': 'interface'|'radio', ..., 'certain': False}) à proposer en
    confirmation (ou à affiner par une sonde active), jamais à appliquer
    tel quel — voir la mise en garde de l'audit 03/08/2026 : le VID:PID seul
    ne suffit jamais à une identification certaine. Retourne None si rien
    de reconnu.

    Deux pistes distinctes :
    1. Boîtier d'interface à PID dédié (microHAM, RIGblaster, RIGtalk) —
       ne dit rien de la radio branchée derrière, juste « ce port est très
       probablement un vrai lien CAT/PTT », utile pour savoir SUR QUEL port
       lancer la sonde active plutôt que sur un port audio/PTT du même
       boîtier (voir le piège documenté dans _friendly_open_error()).
    2. Radio Icom à port USB natif — la puce (Silicon Labs CP210x, VID:PID
       10C4:EA60) est générique et partagée par des centaines d'adaptateurs
       sans rapport, MAIS Icom inscrit le nom exact du modèle dans le
       numéro de série USB (confirmé : « IC-7300 03000000 »,
       « IC-9700 13000000 A »/« ...B », le suffixe A/B distinguant le port
       CAT du port audio). Rien de confirmé d'équivalent chez Yaesu/Kenwood/
       Elecraft — pour ces marques, seule la sonde active (autodetect_scan)
       reste fiable."""
    vid, pid = port.get('vid'), port.get('pid')
    serial_number = (port.get('serial_number') or '').strip()

    if vid is not None and pid is not None:
        label = KNOWN_INTERFACE_VIDPID.get((vid, pid))
        if label:
            return {'kind': 'interface', 'label': label, 'certain': False}

    for model in CIV_ADDRESSES:
        if model.startswith('IC-') and serial_number.startswith(model + ' '):
            return {'kind': 'radio', 'brand': 'icom', 'model': model, 'certain': False}

    return None


# ─── Watcher de branchement (tâche de fond) ─────────────────────────────────
#
# Surveille les branchements/débranchements de port série SANS jamais
# interroger le port lui-même (aucun octet CAT envoyé, aucun risque) — un
# simple diff de list_ports() toutes les ~1.5s. Coût CPU négligeable, aucun
# droit administrateur requis, aucune fenêtre Windows ni dépendance WMI
# (comparé à WM_DEVICECHANGE/Win32_DeviceChangeEvent : gain de latence
# imperceptible pour un humain qui vient de brancher un câble, au prix d'un
# thread de message à superviser — voir mémoire du chantier CAT
# plug-and-play, 03/08/2026). Chaque nouveau port reçoit un indice PASSIF
# (guess_from_usb_signature) : jamais appliqué tout seul, juste proposé à
# l'UI pour une confirmation en un clic — voir CLAUDE.md/mémoire pour le
# choix assumé de ne jamais activer le pilotage sans ce clic.

_watcher_lock = threading.Lock()
_pending_detections = {}   # device -> {'device','description', + indice}
_watcher_thread_started = False


def get_pending_detections():
    """Détections en attente de confirmation, les plus récentes en dernier.
    Jamais vidé automatiquement par le watcher lui-même (sauf débranchement
    du port) — c'est l'UI qui doit appeler dismiss_detection() une fois que
    l'opérateur a confirmé ou décliné. Renvoie des COPIES (trouvé en revue
    adversariale) : sinon le verrou protège la structure de
    _pending_detections mais pas les dicts qu'on vient de sortir de son
    verrou — un futur appelant qui les muterait en place créerait une
    course avec _port_watcher_tick, sans qu'aucun verrou ne le protège."""
    with _watcher_lock:
        return [dict(v) for v in _pending_detections.values()]


def dismiss_detection(device):
    """Retire une détection en attente — sinon elle réapparaîtrait à
    l'identique tant que le port reste branché et non configuré."""
    with _watcher_lock:
        _pending_detections.pop(device, None)


def _port_watcher_tick(known_devices):
    """Un tour de scan : renvoie le nouvel ensemble de devices connus. Séparé
    de la boucle infinie pour rester testable directement (pas de thread ni
    de sleep dans les tests). Le try/except couvre TOUT le corps (pas
    seulement list_ports(), trouvé trop étroit en revue adversariale) : une
    exception inattendue dans guess_from_usb_signature() ou la construction
    du dict aurait sinon remonté jusqu'à port_watcher_loop() et tué
    silencieusement le thread daemon pour le reste de la durée de vie du
    serveur (potentiellement plusieurs jours lors d'une expédition)."""
    try:
        current_ports = list_ports()
        current = {p['device']: p for p in current_ports}
        current_devices = set(current)
        for device in current_devices - known_devices:
            guess = guess_from_usb_signature(current[device])
            if guess:
                with _watcher_lock:
                    _pending_detections[device] = dict(
                        guess, device=device, description=current[device].get('description') or '')
        for device in known_devices - current_devices:
            with _watcher_lock:
                _pending_detections.pop(device, None)
        return current_devices
    except Exception:
        return known_devices


def port_watcher_loop(poll_interval=1.5):
    """Boucle de fond (thread daemon, jamais appelée directement en test —
    voir _port_watcher_tick). Ne s'arrête jamais ; toute exception de scan
    est absorbée par _port_watcher_tick (liste inchangée, on réessaie au
    tour suivant)."""
    known = set()
    while True:
        known = _port_watcher_tick(known)
        time.sleep(poll_interval)


def start_port_watcher():
    """Démarre le watcher une seule fois, quel que soit le nombre d'appels —
    un endpoint qui l'invoquerait par erreur à chaque requête ne doit jamais
    empiler des threads."""
    global _watcher_thread_started
    with _watcher_lock:
        if _watcher_thread_started:
            return
        _watcher_thread_started = True
    threading.Thread(target=port_watcher_loop, daemon=True).start()


def _transceive(transport, data, terminator, timeout=1.0, accept=None):
    """Écrit `data` puis lit jusqu'à `terminator` en une transaction unique
    quand le transport l'expose (SerialPort réel — voir sa méthode
    transceive(), verrou tenu de bout en bout pour rester atomique face au
    polling logbook concurrent). Repli sur write()+read_until() séparés pour
    les transports qui n'implémentent que l'interface minimale (doubles de
    test synchrones, sans thread concurrent donc sans risque).

    `accept` (callable bytes -> bool), si fourni, fait relire une NOUVELLE
    trame dans le MÊME budget `timeout` tant que celle lue est rejetée, au
    lieu d'abandonner après une seule lecture — le budget restant est
    décrémenté à chaque trame rejetée. Décisif sur un bus CI-V partagé avec
    un autre logiciel (WSJT-X/N1MM via séparateur) ou si la radio a la
    notification "CI-V Transceive" activée : une trame parasite (mal
    adressée, ou d'une autre commande) qui tombe dans l'unique lecture d'un
    essai ne doit pas faire conclure "radio muette" alors qu'elle répond
    (trouvé en revue adversariale du chantier CAT plug-and-play, 03/08/2026).
    On ne relit QUE si une trame COMPLÈTE (terminée par `terminator`) a été
    reçue et rejetée — une lecture vide/tronquée signifie que rien n'est
    arrivé dans le budget imparti à CET essai, retenter immédiatement
    n'apporterait rien (et boucherait à chaud sur les doubles de test, dont
    le read_until() ne bloque pas comme le vrai pyserial)."""
    fn = getattr(transport, 'transceive', None)
    if fn is not None:
        return fn(data, terminator, timeout=timeout, accept=accept)
    transport.write(data)
    if accept is None:
        return transport.read_until(terminator, timeout=timeout)
    deadline = time.monotonic() + timeout
    remaining = timeout
    while True:
        frame = transport.read_until(terminator, timeout=max(remaining, 0))
        if accept(frame):
            return frame
        if not frame.endswith(terminator):
            return frame
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return frame


# ═══════════════════════════════════════════════════════════════════════════
#  CI-V (Icom / Xiegu) — trames binaires
# ═══════════════════════════════════════════════════════════════════════════

CIV_PREAMBLE = b'\xFE\xFE'
CIV_END = b'\xFD'
CIV_CTRL_ADDR = 0xE0  # adresse PC par défaut

CIV_MODES = {'LSB': 0x00, 'USB': 0x01, 'AM': 0x02, 'CW': 0x03,
             'RTTY': 0x04, 'FM': 0x05, 'CW-R': 0x07, 'RTTY-R': 0x08}
CIV_MODES_REV = {v: k for k, v in CIV_MODES.items()}

# Adresses CI-V par défaut usine (modifiables sur la radio en Set mode) —
# valeurs standard largement documentées (manuels Icom, Hamlib, guides CAT).
# Un mauvais réglage ici n'empêche rien : le champ MODÈLE ne sert qu'à
# préremplir l'adresse, elle reste éditable si la radio a été reconfigurée.
CIV_ADDRESSES = {
    # Icom HF/VHF/UHF modernes (USB direct)
    'IC-705': 0xA4, 'IC-7300': 0x94, 'IC-7100': 0x88, 'IC-7200': 0x76,
    'IC-7410': 0x80, 'IC-7600': 0x7A, 'IC-7610': 0x98, 'IC-7700': 0x74,
    'IC-7800': 0x6A, 'IC-7851': 0x8E, 'IC-9100': 0x7C, 'IC-9700': 0xA2,
    'IC-905': 0xAC,
    # Icom génération précédente (interface CT-17 ou jack CI-V 3.5mm)
    'IC-706MKIIG': 0x58, 'IC-7000': 0x70, 'IC-718': 0x5E,
    'IC-746': 0x56, 'IC-746PRO': 0x66,
    'IC-756': 0x50, 'IC-756PRO': 0x5C, 'IC-756PROII': 0x64, 'IC-756PROIII': 0x6E,
    'IC-910H': 0x60,  # populaire en satellite (VHF/UHF/1.2GHz tout-mode)
    # Récepteurs Icom
    'IC-R75': 0x5A, 'IC-R8600': 0x96,
    # Xiegu (émulation CI-V Icom)
    'XIEGU-G90': 0x70, 'XIEGU-G106': 0x70, 'XIEGU-X6100': 0xA4, 'XIEGU-X5105': 0x70,
}


def civ_encode_freq(freq_hz):
    """5 octets BCD poids faible en premier. Vérifié contre l'exemple de
    référence 145 000 000 Hz -> 00 00 00 45 01 (round-trip testé)."""
    s = str(int(freq_hz)).rjust(10, '0')
    pairs = [s[0:2], s[2:4], s[4:6], s[6:8], s[8:10]]
    return bytes(int(p, 16) for p in reversed(pairs))


def civ_decode_freq(data5):
    """Inverse de civ_encode_freq."""
    hexstr = ''.join(f'{b:02x}' for b in data5)
    pairs = [hexstr[i:i + 2] for i in range(0, 10, 2)]
    return int(''.join(reversed(pairs)))


def civ_build_frame(addr_radio, cmd, sub=None, data=b''):
    """Construit une trame CI-V complète prête à envoyer."""
    body = bytes([cmd]) + (bytes([sub]) if sub is not None else b'') + bytes(data)
    return CIV_PREAMBLE + bytes([addr_radio, CIV_CTRL_ADDR]) + body + CIV_END


def civ_parse_frame(frame):
    """Extrait (addr_dest, addr_src, cmd, sub_or_None, data) d'une trame.
    Les deux octets d'adresse ont un sens qui dépend du SENS de la trame
    (protocole symétrique) : dans une requête PC->radio, addr_dest=radio et
    addr_src=E0(PC) ; dans une réponse radio->PC, addr_dest=E0(PC) et
    addr_src=radio. On renvoie les deux octets positionnellement, à
    l'appelant d'interpréter selon le contexte (voir §2.1 de la doc).
    Retourne None si la trame est mal formée (pas de préambule/fin, trop
    courte) — jamais d'exception."""
    if len(frame) < 5 or frame[:2] != CIV_PREAMBLE or frame[-1:] != CIV_END:
        return None
    addr_dest, addr_src = frame[2], frame[3]
    rest = frame[4:-1]
    if not rest:
        return None
    cmd = rest[0]
    # Les sous-commandes connues (14/15/1A/1C/19/25/26/27) ont un octet Sc ;
    # les autres (00/01/03/04/05/06/0F) n'en ont pas. 0x27 (scope) AJOUTÉ pour
    # le chantier scope CI-V : sans lui, tout le sous-système 27 00 (waveform)
    # comme 27 14/27 15 (config) serait mal parsé — l'octet de sous-commande
    # resterait collé en tête de `data` au lieu d'être extrait à part (piège
    # documenté par la spec du chantier, prérequis absolu).
    has_sub = cmd in (0x14, 0x15, 0x19, 0x1A, 0x1C, 0x25, 0x26, 0x27)
    if has_sub and len(rest) >= 2:
        return addr_dest, addr_src, cmd, rest[1], rest[2:]
    return addr_dest, addr_src, cmd, None, rest[1:]


def civ_is_ok(frame):
    """FB FD = accusé positif, FA FD = échec (utilisé pour les commandes SET
    sans sous-commande, ex. 0F split)."""
    return frame[-2:] == b'\xFB\xFD' if len(frame) >= 2 else False


# ═══════════════════════════════════════════════════════════════════════════
#  Scope CI-V 0x27 (panadapter natif Icom) — réutilise civ_encode_freq/
#  civ_decode_freq (même BCD 5 octets) et civ_build_frame/civ_parse_frame
#  ci-dessus, aucune duplication d'encodage.
#
#  Source : IC-7300MK2 CI-V Reference Guide + IC-705 CI-V Reference Guide
#  (documentation constructeur officielle) — réimplémentation indépendante,
#  PAS de code repris de wfview (GPL) ni d'aucun autre projet tiers.
#
#  Découpage en paquets DIVISION=11, cas PORT SÉRIE uniquement (le cas LAN/
#  WLAN, division différente, n'est pas couvert — ce projet ne parle au poste
#  qu'en série, comme le reste de logx_cat.py).
# ═══════════════════════════════════════════════════════════════════════════

# Modèles Icom dont le CI-V publie effectivement un scope waveform (27 00) —
# vérifié contre les deux guides CI-V listés ci-dessus. Sert de filtre côté
# HTTP (/rig/scope_available) : n'proposer l'option "CI-V natif" du
# panadapter que sur un modèle qui a une chance réelle de répondre, plutôt
# que de laisser l'opérateur découvrir le silence radio après coup.
MODELES_SCOPE_CIV = {'IC-7300', 'IC-7610', 'IC-9700', 'IC-705', 'IC-7851'}

# Spans valides en mode Center/SCROLL-C (27 15), en Hz — la doc les exprime
# en kHz (2.5/5/10/25/50/100/250/500) mais l'encodage BCD sur le fil est le
# même que civ_encode_freq(), donc on travaille en Hz partout comme pour la
# fréquence normale (pas de conversion kHz<->Hz à part).
CIV_SCOPE_SPANS_HZ = (2500, 5000, 10000, 25000, 50000, 100000, 250000, 500000)

CIV_SCOPE_MODE_CODES = {'center': 0x00, 'fixed': 0x01}
# 0x02 SCROLL-C et 0x03 SCROLL-F existent aussi côté RADIO->PC (le paquet 1
# d'une ligne peut arriver avec un de ces deux codes si l'opérateur a changé
# le mode scope sur la radio directement) — mais ce module ne les propose
# PAS en écriture via configure_scope() : la doc IC-705 ne connaît que
# Center/Fixed (00/01), et un mode Scroll mal choisi pour un poste qui ne le
# supporte pas donnerait un refus silencieux plutôt qu'une erreur claire.
CIV_SCOPE_MODE_NAMES_RX = {0x00: 'center', 0x01: 'fixed', 0x02: 'fixed', 0x03: 'fixed'}


def civ_scope_configure_frames(addr_radio, mode, span_hz=None):
    """Construit la/les trame(s) SET de configuration du scope : 27 14 (mode)
    puis, si mode='center' ET un span est fourni, 27 15 (span). Fonction PURE
    (aucune E/S) — l'appelant (CivRadio.configure_scope) écrit chaque trame
    et attend son propre accusé, ce sont deux commandes CI-V distinctes."""
    mode_code = CIV_SCOPE_MODE_CODES.get(mode)
    if mode_code is None:
        raise ValueError(f"mode scope inconnu pour la configuration : {mode!r}")
    frames = [civ_build_frame(addr_radio, 0x27, sub=0x14, data=bytes([mode_code]))]
    if mode == 'center' and span_hz:
        # Un appel direct à /rig/scope_configure (hors du <select> de
        # logx_panadapter.html, qui restreint déjà aux 8 bonnes valeurs)
        # pourrait sinon envoyer une trame 27 15 avec un span hors spec —
        # comportement radio non documenté, mieux vaut un refus explicite
        # ici (revue adversariale avant fusion, CONFIRMED mineur).
        if int(span_hz) not in CIV_SCOPE_SPANS_HZ:
            raise ValueError(f"span scope invalide : {span_hz} Hz "
                              f"(valeurs valides : {CIV_SCOPE_SPANS_HZ})")
        frames.append(civ_build_frame(addr_radio, 0x27, sub=0x15, data=civ_encode_freq(int(span_hz))))
    return frames


def _civ_scope_bcd_order(byte):
    """Décode l'octet ② 'order' (numéro de CE paquet) d'un paquet scope —
    codé en BCD sur 1 SEUL octet (chaque nibble est un chiffre décimal),
    PAS de l'hexadécimal brut : 0x11 vaut 11 décimal (le paquet n°11), pas
    17. Retourne None si un des deux nibbles n'est pas un chiffre 0-9 —
    trame corrompue, jamais d'exception ni de valeur devinée."""
    hi, lo = byte >> 4, byte & 0x0F
    if hi > 9 or lo > 9:
        return None
    return hi * 10 + lo


def civ_parse_scope_packet(sub, data):
    """Décode UN paquet de la famille scope waveform (27 00), déjà séparé en
    (sub, data) par civ_parse_frame() — sub doit valoir 0x00 (waveform data ;
    27 14/27 15 sont de la configuration, pas du waveform, et ne passent pas
    par cette fonction). `data` commence par ①VFO/②order/③division communs
    à TOUS les paquets ; le paquet n°1 (et lui seul) porte en plus ④mode/
    ⑤fréquences/⑥hors-plage, les paquets 2-11 portent un chunk de waveform.

    Retourne un dict {'order', 'division', ...} ou None si la trame est trop
    courte / l'order illisible — jamais d'exception (même garantie que
    civ_parse_frame)."""
    if sub != 0x00 or len(data) < 3:
        return None
    # data[0] = ①VFO select/unselect, toujours 0x00 dans cette trame — pas de
    # notion de second VFO côté scope (un seul flux par radio), ignoré ici.
    order = _civ_scope_bcd_order(data[1])
    division = _civ_scope_bcd_order(data[2])
    if order is None or division is None:
        return None
    result = {'order': order, 'division': division}
    if order == 1:
        # Le SEUL paquet à porter ④⑤⑥ — 15 octets de corps au total.
        if len(data) < 15:
            return None
        result['scope_mode'] = data[3]
        # ⑤ : en Center, field1=fréquence CENTRALE et field2=span courant ;
        # en Fixed/Scroll, field1=bord BAS et field2=bord HAUT — même
        # encodage BCD 5 octets dans les deux cas (civ_decode_freq), seule
        # l'INTERPRÉTATION change selon ④ (voir civ_reassemble_scope_line).
        result['field1_hz'] = civ_decode_freq(data[4:9])
        result['field2_hz'] = civ_decode_freq(data[9:14])
        result['out_of_range'] = bool(data[14])
    else:
        # Paquets 2-10 : 53 octets de corps (50 de waveform après ①②③).
        # Paquet 11 : 28 octets de corps (25 de waveform après ①②③), plus
        # court — pas de longueur fixe à vérifier ici, la reconstruction
        # (civ_reassemble_scope_line) contrôle la longueur totale (475).
        result['waveform'] = bytes(data[3:])
    return result


def civ_reassemble_scope_line(packets):
    """Reconstitue UNE ligne complète de spectre à partir d'une liste de
    paquets déjà décodés par civ_parse_scope_packet() — dans un ordre
    QUELCONQUE (reconstruction par le champ ②/order de chaque paquet, pas
    par l'ordre d'arrivée/de la liste, même si en pratique le port série les
    délivre dans l'ordre).

    Retourne {'ok': True, 'mode': 'center'|'fixed', 'out_of_range': bool,
    'data': [0-160 par pixel]} + ('center_freq_hz','span_hz') OU
    ('edge_lo_hz','edge_hi_hz') selon le mode ; ou {'ok': False, 'error': str}
    si le paquet 1 manque, si un paquet 2-11 manque (hors cas hors-plage), ou
    si le total reconstruit ne fait pas 475 octets — JAMAIS d'exception sur
    un jeu de paquets incomplet (bus CI-V, ligne interrompue par un QSY)."""
    by_order = {}
    for p in packets:
        if p is not None:
            by_order[p['order']] = p
    pkt1 = by_order.get(1)
    if pkt1 is None:
        return {'ok': False, 'error': 'Paquet scope n°1 (fréquences/mode) manquant'}
    scope_mode = pkt1.get('scope_mode')
    mode_name = CIV_SCOPE_MODE_NAMES_RX.get(scope_mode)
    if mode_name is None:
        return {'ok': False, 'error': f'Mode scope reçu inconnu (0x{scope_mode:02X})'}
    result = {'ok': True, 'mode': mode_name, 'out_of_range': bool(pkt1.get('out_of_range'))}
    if scope_mode == 0x00:
        result['center_freq_hz'] = pkt1['field1_hz']
        result['span_hz'] = pkt1['field2_hz']
    else:
        result['edge_lo_hz'] = pkt1['field1_hz']
        result['edge_hi_hz'] = pkt1['field2_hz']
    if result['out_of_range']:
        # Hors plage : la radio n'envoie AUCUN paquet de waveform (2 à 11) —
        # le paquet 1 est alors le SEUL de toute la ligne. Ce n'est PAS une
        # erreur de reconstruction, juste une ligne sans données à afficher.
        result['data'] = []
        return result
    chunks = []
    for order in range(2, 12):
        pkt = by_order.get(order)
        if pkt is None or 'waveform' not in pkt:
            return {'ok': False, 'error': f'Paquet scope n°{order} manquant — ligne incomplète'}
        chunks.append(pkt['waveform'])
    waveform = b''.join(chunks)
    # 9 paquets à 50 octets (2..10) + 1 paquet à 25 octets (11) = 475 pixels.
    if len(waveform) != 475:
        return {'ok': False, 'error': f'Waveform reconstruite de longueur inattendue '
                f'({len(waveform)} octets, 475 attendus)'}
    result['data'] = list(waveform)
    return result


class CivRadio:
    """Pilote Icom CI-V — encode les requêtes, décode les réponses. Ne fait
    AUCUNE E/S : `transport` est injecté (SerialPort réel ou double de test)."""

    def __init__(self, transport, addr_radio):
        self.t = transport
        self.addr = addr_radio

    def _query(self, cmd, sub=None, data=b'', read_reply=True):
        frame = civ_build_frame(self.addr, cmd, sub, data)
        if not read_reply:
            self.t.write(frame)
            return None

        def _matches(raw):
            parsed = civ_parse_frame(raw)
            # Garde-fou de sens : une VRAIE réponse radio->PC porte TO=E0(PC)
            # et FROM=self.addr (la radio interrogée) — sans ce contrôle, un
            # simple écho de notre propre requête (câble bouclé, port sans
            # UART réelle derrière, appareil en écho local) est
            # syntaxiquement bien formé et serait accepté à tort comme une
            # vraie réponse (faux positif silencieux trouvé en audit
            # 03/08/2026).
            # Garde-fou de COMMANDE (trouvé en revue adversariale avant
            # fusion, même jour) : les seules adresses TO/FROM ne suffisent
            # PAS sur un bus CI-V partagé par plusieurs logiciels (LogX +
            # WSJT-X + N1MM... via un séparateur CI-V) — TOUS utilisent par
            # convention l'adresse contrôleur 0xE0, donc la réponse d'UN
            # AUTRE logiciel à SA propre requête (ex. get_freq) a exactement
            # les mêmes TO/FROM que la nôtre. Sans vérifier que cmd/sub
            # correspondent à CE qu'on vient d'envoyer, get_ptt()/
            # get_mode()/identify() pourraient lire les octets d'une réponse
            # à une AUTRE commande (ex. de la fréquence BCD prise pour un
            # booléen PTT).
            if (not parsed or parsed[0] != CIV_CTRL_ADDR or parsed[1] != self.addr
                    or parsed[2] != cmd or (sub is not None and parsed[3] != sub)):
                return None
            return parsed

        # accept= : une trame parasite qui échoue à _matches() (mauvaise
        # adresse/commande — bus CI-V partagé, notification "CI-V
        # Transceive" restée activée sur la radio) ne doit pas faire
        # abandonner après une seule lecture : on relit dans le budget de
        # timeout restant (voir _transceive() — trouvé en revue adversariale
        # du chantier CAT plug-and-play, 03/08/2026).
        raw = _transceive(self.t, frame, CIV_END, timeout=1.0,
                           accept=lambda r: _matches(r) is not None)
        return _matches(raw)

    def get_freq(self):
        parsed = self._query(0x03)
        if not parsed or len(parsed[4]) < 5:
            return {'ok': False, 'error': 'Pas de réponse fréquence (CI-V)'}
        return {'ok': True, 'freq_hz': civ_decode_freq(parsed[4][:5])}

    def set_freq(self, freq_hz):
        parsed = self._query(0x05, data=civ_encode_freq(freq_hz))
        ok = parsed is not None
        return {'ok': ok} if ok else {'ok': False, 'error': 'Radio CI-V ne répond pas'}

    def get_mode(self):
        parsed = self._query(0x04)
        if not parsed or not parsed[4]:
            return {'ok': False, 'error': 'Pas de réponse mode (CI-V)'}
        return {'ok': True, 'mode': CIV_MODES_REV.get(parsed[4][0], '?')}

    def set_mode(self, mode, freq_hz=None):
        # normaliser_mode traduit le vocabulaire du carnet (SSB, FT8…) vers
        # celui de la radio (LSB/USB…) — voir son commentaire.
        code = CIV_MODES.get(normaliser_mode(mode, freq_hz, 'icom'))
        if code is None:
            return {'ok': False, 'error': f"Mode CI-V inconnu : {mode}"}
        parsed = self._query(0x06, data=bytes([code]))
        return {'ok': parsed is not None}

    def get_ptt(self):
        parsed = self._query(0x1C, sub=0x00)
        if not parsed or not parsed[4]:
            return {'ok': False, 'error': 'Pas de réponse PTT (CI-V)'}
        return {'ok': True, 'ptt': bool(parsed[4][0])}

    def set_ptt(self, on):
        parsed = self._query(0x1C, sub=0x00, data=bytes([1 if on else 0]))
        return {'ok': parsed is not None}

    def get_smeter(self):
        """Échelle brute Icom 0000-0255 (non linéaire, propre au constructeur —
        pas de conversion S-unit ici, laissée à l'appelant si besoin)."""
        parsed = self._query(0x15, sub=0x02)
        if not parsed or len(parsed[4]) < 2:
            return {'ok': False, 'error': 'Pas de réponse S-mètre (CI-V)'}
        raw = int(f'{parsed[4][0]:02x}{parsed[4][1]:02x}')
        return {'ok': True, 'raw': raw}

    def identify(self):
        """Lit l'adresse CI-V configurée — PAS un code modèle (voir doc).
        Sert uniquement à confirmer qu'une radio répond à cette adresse."""
        parsed = self._query(0x19, sub=0x00)
        if not parsed:
            return {'ok': False}
        return {'ok': True, 'addr': parsed[4][0] if parsed[4] else self.addr}

    def _civ_set_frame(self, frame):
        """Écrit une trame SET déjà construite et vérifie l'accusé FB/FD —
        même principe que AmpRadio._set() dans logx_amp.py (un accusé Icom
        n'échote PAS cmd/sub, inutile de le revérifier comme le fait
        _query() pour les réponses GET). `accept=` relit dans le budget de
        timeout si une trame parasite bien adressée mais d'un AUTRE échange
        traîne encore sur le bus (même raisonnement que _query(), voir
        _transceive())."""
        def _matches(raw):
            parsed = civ_parse_frame(raw)
            return parsed is not None and parsed[0] == CIV_CTRL_ADDR and parsed[1] == self.addr

        raw = _transceive(self.t, frame, CIV_END, timeout=1.0, accept=_matches)
        if not _matches(raw):
            return False
        return civ_is_ok(raw)

    def configure_scope(self, mode, span_hz=None):
        """Configure le scope CI-V : 27 14 (mode), puis 27 15 (span) si
        mode='center' et qu'un span est fourni — DEUX commandes CI-V
        distinctes, chacune avec son propre accusé, pas une trame combinée.
        `mode` : 'center' ou 'fixed' (voir CIV_SCOPE_MODE_CODES ; l'IC-705 ne
        connaît que ces deux-là, un poste qui ne supporte pas 'fixed'
        répondra par un accusé négatif géré comme n'importe quel échec).
        Les trames elles-mêmes viennent de civ_scope_configure_frames()
        (fonction pure, testée isolément) — cette méthode ne fait que les
        écrire et vérifier leur accusé, un seul endroit construit le binaire."""
        try:
            frames = civ_scope_configure_frames(self.addr, mode, span_hz)
        except ValueError as e:
            return {'ok': False, 'error': str(e)}
        if not self._civ_set_frame(frames[0]):
            return {'ok': False, 'error': 'Radio CI-V ne répond pas (27 14 mode scope)'}
        if len(frames) > 1 and not self._civ_set_frame(frames[1]):
            return {'ok': False, 'error': 'Radio CI-V ne répond pas (27 15 span scope)'}
        return {'ok': True}

    def read_scope_line(self, timeout=2.0):
        """Écoute les trames 27 00 (scope waveform) qui arrivent sur le bus
        CI-V pendant `timeout` secondes et reconstitue UNE ligne complète.

        LIMITE CONNUE, documentée plutôt que devinée : aucune sous-commande
        CI-V « start/stop streaming » du scope n'a été trouvée dans les
        guides CI-V IC-7300MK2/IC-705 consultés — le flux 27 00 semble
        poussé par la radio quand son écran SCOPE est actif (et/ou la
        notification « CI-V Transceive » activée), pas déclenché par une
        commande dédiée émise d'ici. Cette méthode se contente donc
        d'ÉCOUTER ce qui arrive dans le budget de temps imparti, sans
        jamais supposer qu'un "start" a été émis au préalable — si rien
        n'arrive, l'erreur retournée nomme explicitement cette limite
        plutôt que de laisser croire à une panne CAT générique.

        Passe par `transport.transceive_listen()` quand le transport
        l'expose (SerialPort réel — voir sa méthode dédiée : verrou
        d'instance tenu sur TOUTE la fenêtre d'écoute, pas juste par
        lecture individuelle). Une ligne de spectre enchaîne jusqu'à 11
        lectures sur plusieurs secondes ; si chaque lecture prenait/
        relâchait le verrou séparément (comme write()), un thread
        concurrent (ex. /rig/state, pollé toutes les 4s par chaque page
        ouverte) pourrait s'intercaler entre deux paquets et faire son
        propre reset_input_buffer()+write() sur le même port, corrompant
        la ligne en cours de réception — trouvé en revue avant fusion.
        Repli sur write()-less read_until() en boucle pour les doubles de
        test minimalistes (synchrones, sans thread concurrent donc sans
        ce risque)."""
        packets = []
        seen_orders = set()
        state = {'pkt1': None}

        def _on_frame(raw):
            parsed = civ_parse_frame(raw)
            if not parsed:
                return False
            addr_dest, addr_src, cmd, sub, data = parsed
            # Même garde-fou de sens ET de commande que _query()/_civ_set() :
            # une ligne de spectre authentique part de LA radio interrogée
            # (FROM=self.addr) vers le contrôleur (TO=E0) sur la commande
            # scope — sinon un écho de notre propre trame, ou une trame d'un
            # tout autre échange sur un bus CI-V partagé, serait pris à tort
            # pour un morceau de spectre.
            if addr_dest != CIV_CTRL_ADDR or addr_src != self.addr or cmd != 0x27:
                return False
            pkt = civ_parse_scope_packet(sub, data)
            if pkt is None:
                return False
            order = pkt['order']
            if order in seen_orders:
                return False  # doublon (retransmission bus) : garder le premier
            seen_orders.add(order)
            packets.append(pkt)
            if order == 1:
                state['pkt1'] = pkt
            pkt1 = state['pkt1']
            if pkt1 is not None:
                if pkt1.get('out_of_range'):
                    return True  # paquet 1 seul suffit, hors plage — voir spec
                if len(seen_orders) >= 11:
                    return True  # les 11 paquets (1 + 2..11) sont tous arrivés
            return False

        listen = getattr(self.t, 'transceive_listen', None)
        if listen is not None:
            listen(CIV_END, timeout, _on_frame)
        else:
            deadline = time.monotonic() + timeout
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                raw = self.t.read_until(CIV_END, timeout=remaining)
                if not raw:
                    # Rien reçu dans le budget restant de CET essai : sur un
                    # double de test (read_until non bloquant) comme sur un
                    # vrai port série arrivé à échéance, insister ne
                    # changerait rien.
                    break
                if _on_frame(raw):
                    break
        if not packets:
            return {'ok': False, 'error': "Aucune trame scope (27 00) reçue — vérifie que "
                    "l'écran SCOPE de la radio est actif (le CI-V ne publie pas de commande "
                    "« start » dédiée pour ce flux, voir limite documentée dans le code)"}
        return civ_reassemble_scope_line(packets)


# ═══════════════════════════════════════════════════════════════════════════
#  ASCII générique (Yaesu / Kenwood / Elecraft) — commandes 2 lettres + ';'
# ═══════════════════════════════════════════════════════════════════════════

# Tables de mode par marque (les codes diffèrent légèrement — vérifié doc).
ASCII_MODES = {
    # 'C' = DATA-USB : le créneau des modes numériques (FT8, FT4, PSK) sur les
    # Yaesu ASCII. Il manquait — la radio ne pouvait donc PAS être mise en
    # numérique par le logiciel (voir normaliser_mode ci-dessous).
    'yaesu':    {'1': 'LSB', '2': 'USB', '3': 'CW', '4': 'FM', '5': 'AM',
                 '6': 'RTTY-LSB', '7': 'CW-R', '9': 'RTTY-USB',
                 'C': 'DATA-USB'},
    'kenwood':  {'1': 'LSB', '2': 'USB', '3': 'CW', '4': 'FM', '5': 'AM',
                 '6': 'FSK', '7': 'CW-R', '9': 'FSK-R'},
    'elecraft': {'1': 'LSB', '2': 'USB', '3': 'CW', '4': 'FM', '5': 'AM',
                 '6': 'DATA', '7': 'CW-REV', '9': 'DATA-REV'},
}
for _brand in list(ASCII_MODES):
    ASCII_MODES[_brand + '_rev'] = {v: k for k, v in ASCII_MODES[_brand].items()}

# Split : quel jeu de commandes FT utiliser (voir doc §3.5/§5.6/§4.4).
# 'ft01'    : FT0;/FT1; (anciens Yaesu, Elecraft)
# 'ft23'    : FT2;/FT3; (FT-991/FTDX10/FTDX101 récents)
# 'fr_ft'   : Kenwood — split automatique dès que FR != FT, pas de commande dédiée
# DÉFAUT DE DONNÉE CORRIGÉ ICI : le FT-991 (sans « A ») est un modèle réel de
# BRAND_BY_MODEL, mais était ABSENT d'ici — il retombait donc sur le repli
# générique 'ft01' (FT0;/FT1;), alors que son propre CAT Operation Reference
# Book (vérifié, pas seulement celui du 991A) documente la commande FT
# (« FUNCTION TX ») avec exactement les mêmes valeurs P1=2/3 que le FT-991A ;
# FT0;/FT1; n'existe pas sur ce poste. Sans impact utilisateur AUJOURD'HUI —
# self.split_style est calculé plus bas mais aucune méthode de ce fichier ne
# l'utilise encore pour émettre une commande split — corrigé pour que la
# donnée soit juste le jour où cette fonctionnalité sera câblée.
SPLIT_STYLE = {
    'FT-991': 'ft23', 'FT-991A': 'ft23', 'FTDX10': 'ft23', 'FT-891': 'ft01',
    'FTDX101D': 'ft23', 'FTDX101MP': 'ft23',
    'TS-2000': 'fr_ft', 'TS-590S': 'fr_ft', 'TS-890S': 'fr_ft', 'TS-990S': 'fr_ft',
    'K3': 'ft01', 'K3S': 'ft01', 'KX3': 'ft01', 'KX2': 'ft01', 'K4': 'ft01',
}

# Codes ID -> modèle (Yaesu/Kenwood ; Elecraft répond toujours 017, non listé ici)
#
# DÉFAUT RÉEL QUE ÇA CORRIGE : les codes Yaesu sont ici à 3 chiffres
# ('570', '670'...) alors que la radio répond réellement sur 4 chiffres avec
# un zéro de tête — vérifié dans les CAT Operation Reference Books officiels
# du FT-991 (« ID  P1  0570: FT-991 ») et du FT-991A (« ID  P1  0670:
# FT-991A »). `identify()`/`autodetect()` extraient déjà les chiffres bruts de
# la trame (donc '0570', jamais '570') : la table ne matchait jamais aucun
# poste Yaesu réel. Les codes Kenwood (3 chiffres, sans zéro de tête
# supplémentaire — ex. TS-2000 = 019) restent inchangés.
ASCII_ID_TABLE = {
    '0135': 'FT-891', '0570': 'FT-991', '0670': 'FT-991A',
    '0761': 'FTDX10', '0681': 'FTDX101D', '0682': 'FTDX101MP',
    '019': 'TS-2000', '021': 'TS-590S', '023': 'TS-590SG',
    '022': 'TS-990S', '024': 'TS-890S',
}

# Postes dont le CAT est BINAIRE 5 octets (famille A Yaesu) : le dernier octet
# est l'opcode, la trame est de longueur fixe, il n'y a pas de terminateur.
# Ce pilote ne parle qu'ASCII : il leur envoyait « IF; », auquel ils ne
# repondent JAMAIS — pas d'erreur, pas de trame, juste le silence, et
# l'operateur qui cherche un probleme de cable ou de vitesse.
#
# Ils NE SONT PAS retires de la page CONFIG : leur proprietaire doit savoir
# quoi faire, pas voir son poste disparaitre. Le mode rigctld/Hamlib, deja
# present dans le logiciel, les pilote parfaitement.
MODELES_CAT_BINAIRE = {
    'FT-817': 'Yaesu CAT binaire 5 octets',
    'FT-817ND': 'Yaesu CAT binaire 5 octets',
    'FT-818': 'Yaesu CAT binaire 5 octets',
    'FT-857': 'Yaesu CAT binaire 5 octets',
    'FT-857D': 'Yaesu CAT binaire 5 octets',
    'FT-897': 'Yaesu CAT binaire 5 octets',
    'FT-897D': 'Yaesu CAT binaire 5 octets',
    'FT-847': 'Yaesu CAT binaire 5 octets',
    'FT-100': 'Yaesu CAT binaire 5 octets',
    'FT-100D': 'Yaesu CAT binaire 5 octets',
}


def modele_non_pilotable(model):
    """Message d'explication si ce modèle n'est pas pilotable en natif, sinon
    None. Retourner un message EXPLICITE vaut infiniment mieux qu'un timeout :
    le symptôme d'un protocole inadapté et celui d'un câble débranché sont
    exactement le même — rien ne répond."""
    proto = MODELES_CAT_BINAIRE.get(str(model or '').upper().strip())
    if not proto:
        return None
    return ('%s : %s, que le pilotage natif ne parle pas. '
            'Utilise le mode « rigctld / Hamlib », qui gère ce poste.'
            % (model, proto))


BRAND_BY_MODEL = {
    'FT-891': 'yaesu', 'FT-991': 'yaesu', 'FT-991A': 'yaesu', 'FTDX10': 'yaesu',
    'FTDX101D': 'yaesu', 'FTDX101MP': 'yaesu',
    'TS-2000': 'kenwood', 'TS-590S': 'kenwood', 'TS-590SG': 'kenwood',
    'TS-990S': 'kenwood', 'TS-890S': 'kenwood',
    'K3': 'elecraft', 'K3S': 'elecraft', 'KX3': 'elecraft', 'KX2': 'elecraft',
    'K4': 'elecraft',
}


# Positions de champ ABSOLUES depuis le début du corps (après "IF", avant
# ";"), dérivées de la description des champs par marque (voir doc §3.3/
# §4.3/§5.3). Le champ fréquence est fiable à 100% (toujours en tête, 9 ou
# 11 chiffres selon marque). Le champ mode suit RIT/XIT/mémoire — sa position
# absolue est stable au sein d'une même famille récente, mais N'A PAS PU être
# vérifiée contre une capture d'un vrai poste (seulement contre la
# description textuelle des manuels) : à confirmer sur matériel réel avant
# un usage critique. La longueur totale de trame peut varier en QUEUE
# (scan/CTCSS/sous-mode) sans affecter ces positions de tête.
_IF_FIELDS = {
    # brand: (freq_start, freq_len, mode_pos, min_len)
    #
    # DÉFAUT RÉEL QUE ÇA CORRIGE (vérifié contre le « FT-991A/FT-991 CAT
    # Operation Reference Book » officiel, table IF p.10) : le canal mémoire
    # Yaesu (P1) fait 3 chiffres (« 001-117 »), pas 2 — freq_start valait 2,
    # décalant la lecture de la fréquence d'un chiffre vers la gauche (le
    # dernier chiffre du canal mémoire pris pour le premier de la fréquence,
    # et le vrai dernier chiffre de fréquence perdu). mode_pos=18 restait
    # juste par ailleurs (compensation accidentelle dans l'ancien commentaire,
    # qui comptait mem(2)+offset(5) au lieu de mem(3)+offset(4) — même total).
    'yaesu':    (3, 9, 18, 19),   # mem(3) freq(9) clarif(4) rit(1) xit(1) mode
    'kenwood':  (0, 11, 26, 27),  # freq(11) espaces(5) offset(5) rit(1) xit(1) mem(2) tx(1) mode
    'elecraft': (0, 11, 27, 28),  # freq(11) filler(5) offset(5) rit(1) xit(1) filler(1) mem(2) tx(1) mode
}


def ascii_parse_if(frame, brand):
    """Décode une trame IF; (voir doc §3.3/§4.3/§5.3 pour le détail par
    marque). Retourne au minimum {'freq_hz'} ; 'mode' seulement si la trame
    est assez longue et le code reconnu — jamais de valeur devinée."""
    s = frame.strip().rstrip(';')
    if not s.startswith('IF'):
        return None
    body = s[2:]
    spec = _IF_FIELDS.get(brand)
    if not spec:
        return None
    freq_start, freq_len, mode_pos, min_len = spec
    if len(body) < freq_start + freq_len:
        return None
    try:
        freq_hz = int(body[freq_start:freq_start + freq_len])
    except ValueError:
        return None
    result = {'freq_hz': freq_hz}
    if len(body) > mode_pos:
        code = body[mode_pos]
        mode = ASCII_MODES.get(brand, {}).get(code)
        if mode:
            result['mode'] = mode
    return result


# Largeur du champ fréquence, EN CHIFFRES, par marque.
#
# DÉFAUT RÉEL QUE ÇA CORRIGE. Cette fonction envoyait 11 chiffres à tout le
# monde, avec pour justification écrite dans son docstring : « les modèles
# Yaesu acceptent aussi ce format, au pire des zéros de tête surnuméraires sans
# effet ». C'était une supposition, pas une lecture de manuel — et elle est
# fausse : le CAT ASCII Yaesu est à CHAMPS DE LARGEUR FIXE. `FA` y prend
# 9 chiffres (`FA014074000;`), pas 11.
#
# Le code se contredisait lui-même : _IF_FIELDS déclare `('yaesu', 2, 9, ...)`
# pour LIRE la fréquence. On lisait donc 9 chiffres et on en écrivait 11.
# Conséquence : sur toute la famille Yaesu ASCII — FT-891, FT-991/991A,
# FTDX10, FTDX101 — cliquer un spot ne faisait PAS changer la radio de
# fréquence. C'est la fonction principale du logiciel.
#
# NON VÉRIFIÉ SUR MATÉRIEL RÉEL, faute de poste : la source est la fiche CAT
# Yaesu (« FA;  → FA014074000; ») et la cohérence avec le chemin de lecture
# déjà en place. À confirmer sur un vrai FT-991A avant de s'y fier.
ASCII_FREQ_DIGITS = {'yaesu': 9, 'kenwood': 11, 'elecraft': 11}
ASCII_FREQ_DIGITS_DEFAUT = 11


def ascii_encode_freq_cmd(vfo_cmd, freq_hz, brand=None):
    """FA/FB + fréquence en Hz, zéros de tête, puis ';'.

    La largeur dépend de la MARQUE (voir ASCII_FREQ_DIGITS). `brand=None`
    garde 11 chiffres — le comportement Kenwood/Elecraft, majoritaire.
    """
    n = ASCII_FREQ_DIGITS.get(brand, ASCII_FREQ_DIGITS_DEFAUT)
    return f'{vfo_cmd}{int(freq_hz):0{n}d};'


# ─── Le carnet et la radio ne parlent pas la même langue ─────────────────────
#
# DÉFAUT RÉEL, mesuré : le carnet manipule SSB · CW · FM · AM · RTTY · FT8 ·
# FT4 · PSK, la radio veut LSB · USB · CW · AM · FM · RTTY. « SSB » — le mode
# par défaut au démarrage, et de loin le plus utilisé — ne correspondait à
# AUCUNE entrée, sur aucune marque. Cliquer un spot changeait donc la
# fréquence en laissant la radio dans le mode précédent, et l'échec était
# avalé (set_freq ignore le retour de set_mode). Même chose pour FT8, FT4 et
# PSK : la radio ne passait jamais en numérique.
#
# DEUX CONVENTIONS À CONNAÎTRE, et elles ne se déduisent pas l'une de l'autre :
#   - PHONIE : LSB sur 160/80/40 m, USB sur 20 m et au-dessus, et toute la
#     VHF/UHF. La bascule tient à l'usage, pas à un règlement.
#   - NUMÉRIQUE : USB sur TOUTES les bandes, y compris 80 et 40 m où la phonie
#     est en LSB. Appliquer la règle de la phonie au FT8 mettrait la radio en
#     LSB sur 7,074 MHz — la station serait inaudible.
SEUIL_LSB_USB_HZ = 10_000_000

MODES_NUMERIQUES = frozenset((
    'FT8', 'FT4', 'JS8', 'JS8CALL', 'PSK', 'PSK31', 'PSK63', 'MFSK',
    'JT65', 'JT9', 'OLIVIA', 'DATA', 'DIGI', 'DIGITAL', 'MSK144', 'Q65',
))
MODES_PHONIE = frozenset(('SSB', 'PHONE', 'PHONIE', 'VOICE'))
# Nom du créneau numérique par marque. Yaesu a un mode DATA-USB dédié ; sur les
# autres, l'usage est de rester en USB et de router l'audio par la prise DATA —
# c'est ce que fait tout le monde, et ça ne peut pas mal tourner.
MODE_NUMERIQUE_PAR_MARQUE = {'yaesu': 'DATA-USB'}
# RTTY : trois noms pour la même chose selon la marque.
MODE_RTTY_PAR_MARQUE = {'yaesu': 'RTTY-LSB', 'kenwood': 'FSK', 'elecraft': 'DATA'}


def normaliser_mode(mode, freq_hz=None, brand=None):
    """Traduit un mode du carnet vers le vocabulaire de la radio.

    `freq_hz` n'est utile que pour la phonie (LSB ou USB). Sans lui, on
    retourne USB : c'est le choix le moins dommageable — il couvre 20 m et
    au-dessus, plus toute la VHF/UHF, soit la majorité du trafic, et une erreur
    de bande latérale s'entend immédiatement.
    """
    m = str(mode or '').upper().strip().replace('_', '-')
    if not m:
        return ''
    if m in MODES_PHONIE:
        try:
            f = float(freq_hz) if freq_hz else 0
        except (TypeError, ValueError):
            f = 0
        return 'LSB' if 0 < f < SEUIL_LSB_USB_HZ else 'USB'
    if m in MODES_NUMERIQUES:
        return MODE_NUMERIQUE_PAR_MARQUE.get(brand, 'USB')
    if m in ('RTTY', 'FSK'):
        return MODE_RTTY_PAR_MARQUE.get(brand, 'RTTY')
    return m


def ascii_encode_mode_cmd(mode, brand, vfo_suffix='', freq_hz=None):
    nom = normaliser_mode(mode, freq_hz, brand)
    code = ASCII_MODES.get(brand + '_rev', {}).get(nom)
    if code is None:
        return None
    # DÉFAUT RÉEL : chez Yaesu, MD prend un P1 obligatoire (« 0 » = MAIN RX,
    # voir table MD du CAT Operation Reference Book, « MD0C; » = DATA-USB) —
    # sans lui la radio reçoit « MDC; », une trame qu'elle rejette en silence
    # (le mode ne change jamais, sans erreur ni exception côté logiciel).
    # Kenwood/Elecraft n'ont PAS ce paramètre (« MD2; » suffit) : le suffixe
    # ne doit être ajouté que pour Yaesu.
    if brand == 'yaesu' and not vfo_suffix:
        vfo_suffix = '0'
    return f'MD{vfo_suffix}{code};'


class AsciiRadio:
    """Pilote ASCII générique — Yaesu/Kenwood/Elecraft. `brand` sélectionne
    la table de modes et le style de split ; `model` (optionnel) affine le
    split (ft01 vs ft23) et permet la lecture PTT/S-mètre/puissance quand
    la commande existe pour ce modèle précis."""

    def __init__(self, transport, brand, model=None):
        self.t = transport
        self.brand = brand
        self.model = model
        self.split_style = SPLIT_STYLE.get(model, 'ft01' if brand != 'kenwood' else 'fr_ft')

    def _cmd(self, cmd, read_reply=True):
        data = cmd.encode('ascii')
        if not read_reply:
            self.t.write(data)
            return None
        return _transceive(self.t, data, b';', timeout=1.0).decode('ascii', errors='replace')

    def get_state(self):
        reply = self._cmd('IF;')
        if not reply:
            return {'ok': False, 'error': 'Pas de réponse IF (ASCII)'}
        parsed = ascii_parse_if(reply, self.brand)
        if not parsed:
            return {'ok': False, 'error': f'Trame IF illisible : {reply!r}'}
        parsed['ok'] = True
        return parsed

    def set_freq(self, freq_hz):
        self._cmd(ascii_encode_freq_cmd('FA', freq_hz, self.brand), read_reply=False)
        return {'ok': True}

    def set_mode(self, mode, freq_hz=None):
        cmd = ascii_encode_mode_cmd(mode, self.brand, freq_hz=freq_hz)
        if cmd is None:
            return {'ok': False, 'error': f"Mode inconnu pour {self.brand} : {mode}"}
        self._cmd(cmd, read_reply=False)
        return {'ok': True}

    def get_ptt(self):
        if self.brand == 'elecraft':
            reply = self._cmd('TQ;')
            if reply and reply.startswith('TQ'):
                return {'ok': True, 'ptt': reply[2:3] == '1'}
        elif self.brand == 'yaesu':
            reply = self._cmd('TX;')
            if reply and reply.startswith('TX'):
                return {'ok': True, 'ptt': reply[2:3] != '0'}
        # Kenwood : pas de lecture dédiée fiable sur tous les modèles
        # (absente sur TS-890S) — signalé plutôt que deviné.
        return {'ok': False, 'error': f'Lecture PTT non disponible pour {self.brand}'}

    def set_ptt(self, on):
        if self.brand == 'yaesu':
            # Chez Yaesu, 'TX;' SANS chiffre est la forme de LECTURE (voir
            # get_ptt() ci-dessus, qui attend TX0;/TX1;/TX2; en réponse) —
            # pas un ordre d'émission. L'écriture exige le suffixe :
            # TX1; = PTT engagé, TX0; = PTT relâché.
            self._cmd('TX1;' if on else 'TX0;', read_reply=False)
        else:
            self._cmd('TX;' if on else 'RX;', read_reply=False)
        return {'ok': True}

    # ─── MANIPULATION CW ────────────────────────────────────────────────────
    # Kenwood et Elecraft acceptent la commande KY : le texte est envoyé au
    # keyer interne de la radio, qui le manipule à la vitesse réglée sur le
    # poste. Jusqu'ici le mode natif refusait tout envoi CW — or c'est le mode
    # que la CONFIG recommande par DÉFAUT pour Icom, Yaesu, Kenwood, Elecraft
    # et Xiegu. Concrètement, un opérateur CW en mode natif n'avait pas de
    # manipulation du tout : ESM se contentait de copier le texte dans le
    # presse-papier.
    #
    # Yaesu est volontairement ABSENT : la commande existe sur certains
    # modèles avec une sémantique différente (mémoires du keyer plutôt
    # qu'envoi de texte libre), et se tromper enverrait n'importe quoi sur
    # l'air. Mieux vaut un refus explicite qu'une manipulation fantaisiste.
    CW_BRANDS = ('kenwood', 'elecraft')
    # Le tampon KY accepte 24 caractères. On découpe plus court pour laisser
    # la radio respirer entre deux envois.
    CW_CHUNK = 20
    # Délai entre deux segments KY : laisse le temps à la radio de vider une
    # partie du tampon avant l'arrivée du bloc suivant. Majoré par prudence
    # pour couvrir aussi les vitesses lentes (~10-15 mpm, usage DX/pile-up),
    # pas seulement le confort moyen.
    CW_CHUNK_DELAY_S = 0.5
    # Jeu de caractères réellement manipulable. Tout le reste est écarté
    # plutôt qu'envoyé tel quel : un caractère refusé peut faire ignorer la
    # commande ENTIÈRE par la radio, donc perdre tout le message.
    CW_ALLOWED = set('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 /?.,=+-')

    def send_cw(self, text):
        if self.brand not in self.CW_BRANDS:
            return {'ok': False,
                    'error': "Envoi CW non disponible en mode Natif pour %s — "
                             "utilise un WinKeyer, rigctld ou TCI" % self.brand}
        propre = ''.join(c for c in str(text or '').upper() if c in self.CW_ALLOWED)
        propre = ' '.join(propre.split())        # espaces multiples = un seul
        if not propre:
            return {'ok': False, 'error': 'Rien à manipuler (texte vide après filtrage)'}
        for i in range(0, len(propre), self.CW_CHUNK):
            self._cmd('KY %s;' % propre[i:i + self.CW_CHUNK], read_reply=False)
            if i + self.CW_CHUNK < len(propre):
                time.sleep(self.CW_CHUNK_DELAY_S)
        return {'ok': True, 'text': propre}

    def stop_cw(self):
        """Vide le tampon du keyer. `KY0;` est la forme reconnue par Kenwood
        comme par Elecraft ; on repasse en réception ensuite pour ne pas
        laisser la radio en émission si le tampon était déjà vide."""
        if self.brand not in self.CW_BRANDS:
            return {'ok': False, 'error': 'Arrêt CW non disponible pour %s' % self.brand}
        self._cmd('KY0;', read_reply=False)
        self._cmd('RX;', read_reply=False)
        return {'ok': True}

    def get_smeter(self):
        reply = self._cmd('SM0;' if self.brand == 'yaesu' else 'SM;')
        if reply and reply.startswith('SM'):
            digits = ''.join(c for c in reply if c.isdigit())
            if digits:
                return {'ok': True, 'raw': int(digits)}
        return {'ok': False, 'error': f'Pas de réponse S-mètre ({self.brand})'}

    def identify(self):
        reply = self._cmd('ID;')
        if not reply or not reply.startswith('ID'):
            return {'ok': False}
        code = ''.join(c for c in reply if c.isdigit())
        model = ASCII_ID_TABLE.get(code)
        return {'ok': True, 'code': code, 'model': model}


# ═══════════════════════════════════════════════════════════════════════════
#  Transport série (pyserial réel)
# ═══════════════════════════════════════════════════════════════════════════

class SerialPort:
    """Fine couche au-dessus de pyserial — verrouillée par instance (un port
    = un verrou), pas de verrou global : plusieurs radios sur des ports
    différents fonctionnent en parallèle (SO2R)."""

    def __init__(self, device, baudrate=19200, timeout=1.0):
        if not HAS_PYSERIAL:
            raise RuntimeError("pyserial n'est pas installé")
        self._lock = threading.Lock()
        # rts=False, dtr=False : par défaut pyserial/Windows lèvent RTS et
        # DTR dès l'ouverture du port. Sur les interfaces qui câblent le PTT
        # sur RTS/DTR plutôt que sur une commande logicielle (certains
        # RigBlaster/microHAM), une simple ouverture de port (test de
        # connexion, autodetect_scan) pourrait sinon déclencher l'émission
        # (porteuse nue) sans qu'aucune trame CAT n'ait été envoyée — trouvé
        # en audit 03/08/2026, jamais un problème observé faute d'y avoir
        # pensé plus tôt.
        # 🚨 pyserial (3.5, voir requirements.txt) n'accepte PAS rts=/dtr=
        # comme arguments du CONSTRUCTEUR — seulement comme propriétés
        # d'instance (SerialBase.__init__ lève ValueError sur tout kwarg
        # inconnu). Un premier essai avec rts=/dtr= en kwargs cassait donc
        # l'ouverture de TOUT port CAT natif (trouvé par revue adversariale
        # avant fusion, jamais poussé). Construire fermé (port=None),
        # poser les propriétés, PUIS ouvrir : _reconfigure_port() applique
        # rts_state/dtr_state dès la configuration matérielle du port, sans
        # aucune fenêtre où les lignes seraient hautes par défaut.
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

    def write(self, data):
        """Écriture seule, sans attente de réponse (SET fire-and-forget,
        ex. set_freq()/set_ptt() ASCII appelés avec read_reply=False)."""
        with self._lock:
            self._ser.reset_input_buffer()
            self._ser.write(data)

    def transceive(self, data, terminator, timeout=1.0, accept=None):
        """Écrit `data` PUIS lit jusqu'à `terminator` sous UNE SEULE
        acquisition du verrou d'instance : toute la transaction
        requête/réponse est atomique (même correctif que `_io_lock` dans
        logx_amp.py). Le serveur HTTP est multi-thread — polling logbook et
        clics opérateur écrivent chacun sur le même port — donc sans cela un
        thread pouvait voir sa réponse effacée par le reset_input_buffer()
        d'un autre thread, ou lire la réponse destinée à une autre commande.

        `accept` (callable bytes -> bool), si fourni, relit une nouvelle
        trame dans le MÊME budget `timeout` — donc SANS relâcher le verrou,
        sans quoi le budget de temps « restant » face à une trame parasite
        n'aurait plus rien d'atomique — tant qu'une trame COMPLÈTE reçue est
        rejetée (voir _transceive() pour le détail, notamment pourquoi une
        lecture vide/tronquée arrête la boucle immédiatement plutôt que de
        retenter)."""
        accept = accept or (lambda frame: True)
        with self._lock:
            self._ser.reset_input_buffer()
            self._ser.write(data)
            deadline = time.monotonic() + timeout
            remaining = timeout
            while True:
                self._ser.timeout = max(remaining, 0)
                frame = self._ser.read_until(terminator)
                if accept(frame):
                    return frame
                if not frame.endswith(terminator):
                    return frame
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return frame

    def transceive_listen(self, terminator, timeout, on_frame):
        """Écoute PASSIVE (aucune écriture) de plusieurs trames consécutives
        pendant `timeout` secondes, verrou d'instance tenu sur TOUTE la
        fenêtre — pas relâché entre deux lectures — nécessaire pour le
        scope CI-V (CivRadio.read_scope_line) qui enchaîne jusqu'à 11
        lectures sur plusieurs secondes en partageant le même port série
        que le reste du CAT (get_freq/set_freq, polling /rig/state toutes
        les 4s par page ouverte). Sans verrou unique tenu de bout en bout,
        un thread concurrent pourrait s'intercaler entre deux paquets et
        faire son propre reset_input_buffer()+write() sur le port,
        effaçant/corrompant la ligne de spectre en cours de réception —
        même risque que celui déjà documenté sur transceive() ci-dessus,
        juste étalé sur une fenêtre plus longue et sans écriture de notre
        part entre les lectures.

        `on_frame(frame)` est appelé pour CHAQUE trame complète reçue
        (se terminant par `terminator`) ; doit retourner True pour arrêter
        l'écoute plus tôt (ex. les 11 paquets scope attendus sont tous
        arrivés ou la ligne est hors-plage), False pour continuer jusqu'à
        épuisement du budget. Une lecture vide/tronquée (rien arrivé dans
        le budget restant) arrête l'écoute immédiatement, comme pour
        transceive()."""
        with self._lock:
            deadline = time.monotonic() + timeout
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return
                self._ser.timeout = max(remaining, 0)
                frame = self._ser.read_until(terminator)
                if not frame or not frame.endswith(terminator):
                    return
                if on_frame(frame):
                    return

    def read_until(self, terminator, timeout=1.0):
        with self._lock:
            self._ser.timeout = timeout
            return self._ser.read_until(terminator)

    def close(self):
        try:
            self._ser.close()
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════════════════════
#  Gestionnaire multi-radio (SO2R) + détection automatique
# ═══════════════════════════════════════════════════════════════════════════

CAT_DEFAULT_BAUD = {'icom': 19200, 'xiegu': 19200, 'yaesu': 4800,
                    'kenwood': 9600, 'elecraft': 38400}


def _friendly_open_error(port, exc):
    """Traduit l'exception pyserial brute (message technique, souvent un
    texte d'exception OS wrappé par pyserial — ex. « could not open port
    'COM5': PermissionError(13, 'Access is denied.', ...) » sous Windows) en
    cause probable côté opérateur, SANS jamais cacher le détail technique
    d'origine (gardé entre parenthèses) : un beta-testeur peut avoir besoin
    de le recopier tel quel pour un diagnostic plus poussé. Retour signalé
    par un beta-testeur microHAM (02/08/2026) : le message brut ne dit ni
    « le port est déjà pris » ni « le port n'existe pas », deux causes très
    fréquentes avec une interface qui expose plusieurs ports COM virtuels
    (microHAM Router, USB Device Router...).

    Ce message n'apparaît qu'APRÈS l'échec des nouvelles tentatives de
    _open_serial_retry() (voir sa docstring) : un simple redémarrage de
    LogX AI, même la seconde d'avant, a déjà été absorbé silencieusement à
    ce stade — donc le préciser ici n'aurait été qu'un faux espoir dans la
    majorité des cas réels. Mentionné quand même en dernier recours (retour
    F4GLD, 15/08/2026 : « COM4 déjà utilisé alors que j'ai redémarré le
    serveur ! ») pour le cas plus rare où le pilote USB met plus d'1,4 s à
    relâcher le port."""
    msg = str(exc)
    low = msg.lower()
    if 'permissionerror' in low or 'access is denied' in low or 'permission denied' in low or 'errno 13' in low:
        cause = (f"{port} est déjà utilisé — par un autre logiciel (WSJT-X, "
                 "un autre logbook, le microHAM Router/USB Device Router...), "
                 "ou par une instance de LogX AI qui vient tout juste de se "
                 "fermer et dont le pilote USB n'a pas encore fini de "
                 "relâcher le port (rare, réessaie dans quelques secondes). "
                 "Si le problème persiste : ferme le logiciel en question, "
                 "ou si ton interface expose plusieurs ports COM (cas "
                 "fréquent avec microHAM), choisis-en un autre.")
    elif ('filenotfounderror' in low or 'cannot find the file' in low
          or 'no such file' in low or 'errno 2' in low):
        cause = (f"{port} n'existe pas ou n'est plus branché — vérifie le "
                 "câble USB et que le pilote/routeur de l'interface (ex. "
                 "microHAM Router) tourne bien, puis re-choisis le port dans "
                 "la liste (elle a pu changer).")
    else:
        cause = f"Impossible d'ouvrir {port}."
    return f"{cause} (détail technique : {msg})"

# Point d'injection pour les tests : remplacer par un double qui ne touche
# pas un vrai port série (voir tests/test_cat.py). Par défaut, le vrai
# constructeur pyserial.
_open_serial = SerialPort if HAS_PYSERIAL else None

# Point d'injection pour les tests (même esprit que _open_serial ci-dessus) :
# remplacer par un no-op pour ne pas ralentir la suite pytest des délais
# réels ci-dessous. Par défaut, le vrai time.sleep.
_retry_sleep = time.sleep

# Délais (secondes) entre tentatives d'ouverture quand pyserial signale un
# port "déjà utilisé" — voir _open_serial_retry(). ~1,4 s de budget total
# dans le pire cas, du même ordre que d'autres budgets déjà acceptés ailleurs
# dans l'appli (ex. _HTTP_BUDGET dans logx_singleton.py).
_OPEN_RETRY_DELAYS = (0.2, 0.4, 0.8)


def _looks_like_transient_busy(exc):
    """Le port est-il signalé PRIS (par opposition à absent/débranché, ou à
    une autre cause) ? Seul ce cas mérite une nouvelle tentative — voir
    _open_serial_retry(). Même classification que _friendly_open_error(),
    dupliquée à dessein : les deux fonctions répondent à des questions
    différentes (« dois-je réessayer ? » vs « quel message afficher ? ») et
    coupler l'une à l'autre les rendrait plus difficiles à faire évoluer
    séparément."""
    low = str(exc).lower()
    return ('permissionerror' in low or 'access is denied' in low
            or 'permission denied' in low or 'errno 13' in low)


def _open_serial_retry(port, baudrate):
    """Ouvre `port` via _open_serial(), en retentant BRIÈVEMENT si l'échec
    ressemble à un port "déjà utilisé" (voir _looks_like_transient_busy) —
    jamais sur un port absent/introuvable, où retenter ne changerait rien et
    ne ferait que retarder un message d'erreur déjà exploitable.

    BUG RÉEL CORRIGÉ ICI (rapporté par F4GLD : « COM4 déjà utilisé alors que
    j'ai redémarré le serveur ! »). Il n'existe AUCUN verrou applicatif côté
    LogX AI qui pourrait expliquer ça : `_persistent` (ci-dessus) est un
    simple dict en mémoire de PROCESS, vide par construction à chaque
    nouveau lancement — un vrai redémarrage (process tué puis relancé, ou le
    bouton "installer et redémarrer" de la MAJ résiliente) ne peut pas
    laisser un verrou LogX AI fantôme derrière lui. La cause est plus bas
    niveau : sur certains adaptateurs USB-série (FTDI/CP210x/CH340...), le
    PILOTE Windows peut mettre jusqu'à quelques centaines de ms — voire un
    peu plus — à relâcher le port au niveau matériel après la fin du process
    qui le tenait, même si ce process a déjà complètement disparu au sens de
    l'OS. Le tout premier essai d'ouverture du nouveau process (à l'ouverture
    de CONFIG, ou au premier /rig/state polling) tombait alors sur
    PermissionError sans jamais réessayer, alors qu'un essai quelques
    centaines de ms plus tard aurait réussi. Sans retry, `_ensure_connected`
    ne mémorise d'ailleurs même pas l'échec (pas d'entrée `_persistent`) —
    l'appel SUIVANT (polling à 4s) aurait fini par réussir tout seul, mais
    seulement après avoir déjà affiché une erreur trompeuse à l'opérateur."""
    delays = (0,) + _OPEN_RETRY_DELAYS
    last_exc = None
    for delay in delays:
        if delay:
            _retry_sleep(delay)
        try:
            return _open_serial(port, baudrate=baudrate)
        except Exception as e:
            last_exc = e
            if not _looks_like_transient_busy(e):
                raise
    raise last_exc


def _parse_civ_addr(value):
    """Adresse CI-V saisie (texte hexa, ex. "AA") -> int, ou None si absente/
    invalide — jamais d'exception, sert de repli vers l'adresse usine."""
    try:
        if value:
            return int(str(value), 16)
    except (TypeError, ValueError):
        pass
    return None


def cat_settings(cfg):
    """Réglages du pilotage natif depuis la config CLIENT. `mode` distingue
    'native' (ce module) de 'rigctld' (logx_rig, inchangé) — une
    config existante sans les champs cat_* se comporte comme avant
    (cat_enabled absent -> enabled=False, aucun effet sur le mode rigctld).

    `civ_addr` : adresse CI-V usine du MODÈLE choisi (CIV_ADDRESSES), sauf si
    l'opérateur a rentré une adresse manuelle (`cat_civ_addr`, champ avancé) —
    pratique courante en multi-poste/SO2R pour éviter les collisions sur le
    bus CI-V. Sans repli manuel, une radio reconfigurée en Set mode restait
    injoignable : LogX AI interrogeait toujours l'adresse usine du modèle."""
    cfg = cfg or {}
    brand = (cfg.get('cat_brand') or '').strip().lower()
    try:
        baudrate = int(cfg.get('cat_baudrate') or 0)
    except (TypeError, ValueError):
        baudrate = 0
    model = (cfg.get('cat_model') or '').strip() or None
    civ_addr = _parse_civ_addr(cfg.get('cat_civ_addr')) or CIV_ADDRESSES.get(model, 0x94)
    return {
        'enabled': bool(cfg.get('cat_enabled')),
        'mode': cfg.get('cat_mode') or 'native',
        'brand': brand,
        'model': model,
        'port': (cfg.get('cat_port') or '').strip(),
        'baudrate': baudrate or CAT_DEFAULT_BAUD.get(brand, 19200),
        'civ_addr': civ_addr,
    }


# Connexion persistante unique (poste principal) — rouverte automatiquement
# si la configuration (port/marque/modèle/vitesse) change entre deux appels.
_persistent = {}
_persistent_lock = threading.Lock()


def _ensure_connected(settings):
    """Retourne (driver, erreur_ou_None). Ouvre le port au premier appel,
    réutilise la connexion tant que la config ne change pas."""
    key = (settings['port'], settings['brand'], settings['model'], settings['baudrate'],
           settings['civ_addr'])
    with _persistent_lock:
        entry = _persistent.get('default')
        if entry and entry['key'] == key:
            return entry['driver'], None
        if entry:
            entry['transport'].close()
            _persistent.pop('default', None)
        if not settings['port']:
            return None, 'Port série non configuré'
        # AVANT d'ouvrir le port : un poste au CAT binaire ne repondra a aucune
        # de nos trames. Ouvrir puis attendre le timeout donnerait « pas de
        # reponse », strictement indiscernable d'un cable debranche.
        refus = modele_non_pilotable(settings['model'])
        if refus:
            return None, refus
        try:
            transport = _open_serial_retry(settings['port'], settings['baudrate'])
        except Exception as e:
            return None, _friendly_open_error(settings['port'], e)
        if settings['brand'] in ('icom', 'xiegu'):
            driver = CivRadio(transport, settings['civ_addr'])
        else:
            driver = AsciiRadio(transport, settings['brand'], settings['model'])
        _persistent['default'] = {'key': key, 'driver': driver, 'transport': transport}
        return driver, None


def disconnect_persistent():
    """Ferme la connexion persistante (ex. avant de changer de config)."""
    with _persistent_lock:
        entry = _persistent.pop('default', None)
    if entry:
        entry['transport'].close()


def get_state(cfg):
    """État courant (fréquence + mode) — même forme que logx_rig
    pour que le client puisse rester inchangé quel que soit le mode actif."""
    settings = cat_settings(cfg)
    if not settings['enabled'] or settings['mode'] != 'native':
        return {'enabled': False}
    driver, err = _ensure_connected(settings)
    if err:
        return {'ok': False, 'error': err, 'enabled': True}
    try:
        if isinstance(driver, CivRadio):
            f = driver.get_freq()
            if not f.get('ok'):
                return {'ok': False, 'error': f.get('error', 'Pas de réponse'), 'enabled': True}
            m = driver.get_mode()
            return {'ok': True, 'enabled': True, 'freq_hz': f['freq_hz'],
                    'freq_khz': round(f['freq_hz'] / 1000.0, 2),
                    'mode': m.get('mode', '') if m.get('ok') else ''}
        st = driver.get_state()
        if not st.get('ok'):
            return {'ok': False, 'error': st.get('error', 'Pas de réponse'), 'enabled': True}
        st['freq_khz'] = round(st['freq_hz'] / 1000.0, 2)
        st['enabled'] = True
        return st
    except Exception as e:
        # Port tombé (USB débranché, SerialException) : on invalide la connexion
        # persistante pour qu'elle soit RÉOUVERTE au prochain appel — sans ça,
        # l'entrée morte restait et le pilotage échouait indéfiniment, même après
        # rebranchement sur le même COM.
        disconnect_persistent()
        return {'ok': False, 'error': f'Radio injoignable ({e})', 'enabled': True}


def set_freq(cfg, freq_hz, mode=None):
    """QSY natif — même signature que logx_rig.set_freq."""
    settings = cat_settings(cfg)
    if not settings['enabled'] or settings['mode'] != 'native':
        return {'ok': False, 'error': 'Pilotage natif non actif'}
    driver, err = _ensure_connected(settings)
    if err:
        return {'ok': False, 'error': err}
    try:
        r = driver.set_freq(freq_hz)
        if r.get('ok') and mode:
            # La FRÉQUENCE est passée à set_mode : elle décide de LSB ou USB en
            # phonie. Et l'échec n'est plus avalé — c'est ce silence qui a
            # laissé « SSB inconnu » passer inaperçu.
            m = driver.set_mode(mode, freq_hz)
            if not m.get('ok'):
                r = dict(r)
                r['mode_error'] = m.get('error', 'mode non appliqué')
        return r
    except Exception as e:
        disconnect_persistent()
        return {'ok': False, 'error': f'Radio injoignable ({e})'}


def set_ptt(cfg, on):
    """Bascule PTT natif (CivRadio/AsciiRadio ont chacun leur set_ptt) — même
    signature que logx_rig.set_ptt/logx_tci.set_ptt, pour le
    keyer vocal (logx_voicekeyer.py)."""
    settings = cat_settings(cfg)
    if not settings['enabled'] or settings['mode'] != 'native':
        return {'ok': False, 'error': 'Pilotage natif non actif'}
    driver, err = _ensure_connected(settings)
    if err:
        return {'ok': False, 'error': err}
    try:
        return driver.set_ptt(bool(on))
    except Exception as e:
        disconnect_persistent()
        return {'ok': False, 'error': f'Radio injoignable ({e})'}


def send_cw(cfg, text):
    """Manipulation CW en mode natif — même signature que logx_rig.send_cw /
    logx_tci.send_cw, pour que /rig/cw dispatche sans cas particulier.

    Icom n'est PAS couvert : le protocole CI-V ne publie pas de commande
    d'envoi de texte CW (vérifié sur la documentation constructeur). Le refus
    est explicite et nomme la solution, plutôt que de laisser croire à une
    panne."""
    settings = cat_settings(cfg)
    if not settings['enabled'] or settings['mode'] != 'native':
        return {'ok': False, 'error': 'Pilotage natif non actif'}
    driver, err = _ensure_connected(settings)
    if err:
        return {'ok': False, 'error': err}
    if not hasattr(driver, 'send_cw'):
        return {'ok': False,
                'error': "Envoi CW indisponible en CI-V : Icom ne publie pas de "
                         "commande d'envoi de texte CW. Utilise un WinKeyer, "
                         "rigctld ou TCI."}
    try:
        return driver.send_cw(text)
    except Exception as e:
        disconnect_persistent()
        return {'ok': False, 'error': f'Radio injoignable ({e})'}


def stop_cw(cfg):
    """Vide le tampon du keyer (bouton ■ STOP CW)."""
    settings = cat_settings(cfg)
    if not settings['enabled'] or settings['mode'] != 'native':
        return {'ok': False, 'error': 'Pilotage natif non actif'}
    driver, err = _ensure_connected(settings)
    if err:
        return {'ok': False, 'error': err}
    if not hasattr(driver, 'stop_cw'):
        return {'ok': False, 'error': 'Arrêt CW indisponible en CI-V'}
    try:
        return driver.stop_cw()
    except Exception as e:
        disconnect_persistent()
        return {'ok': False, 'error': f'Radio injoignable ({e})'}


def scope_civ_available(cfg):
    """Le scope CI-V 0x27 n'existe que sur certains modèles Icom
    (MODELES_SCOPE_CIV) ET seulement en pilotage NATIF (TCI/rigctld/flrig ne
    donnent pas accès aux trames CI-V brutes, seulement à une fréquence/mode
    déjà décodés) — sert /rig/scope_available, pour n'afficher l'option
    "CI-V natif" du panadapter que quand elle a une chance réelle de
    fonctionner plutôt que de laisser l'opérateur la découvrir muette."""
    settings = cat_settings(cfg)
    if not settings['enabled']:
        return {'available': False, 'reason': 'Pilotage CAT natif désactivé (CONFIG)'}
    if settings['mode'] != 'native':
        return {'available': False,
                'reason': 'Le scope CI-V nécessite le mode « natif » (pas TCI/rigctld/flrig)'}
    model = settings['model']
    if model not in MODELES_SCOPE_CIV:
        return {'available': False,
                'reason': f"Modèle « {model or '?'} » non supporté pour le scope CI-V "
                          f"(supportés : {', '.join(sorted(MODELES_SCOPE_CIV))})"}
    return {'available': True, 'reason': ''}


def scope_configure(cfg, mode, span_hz=None):
    """Configure le scope CI-V (mode Center/Fixed + span) sur la connexion
    persistante déjà ouverte pour le CAT — pas de connexion série séparée."""
    settings = cat_settings(cfg)
    if not settings['enabled'] or settings['mode'] != 'native':
        return {'ok': False, 'error': 'Pilotage natif non actif'}
    if settings['model'] not in MODELES_SCOPE_CIV:
        # Même filtre modèle que scope_civ_available() (utilisé pour
        # masquer l'option côté UI) — répété ici pour un appel direct de
        # l'endpoint : sinon un modèle Icom/Xiegu non listé (ex. IC-7100)
        # passerait la garde `isinstance(driver, CivRadio)` ci-dessous et
        # enverrait une trame 27 14 que la radio n'a aucune chance de
        # comprendre, pour un message d'erreur générique moins clair.
        return {'ok': False, 'error': f"Modèle « {settings['model'] or '?'} » non supporté "
                f"pour le scope CI-V (supportés : {', '.join(sorted(MODELES_SCOPE_CIV))})"}
    driver, err = _ensure_connected(settings)
    if err:
        return {'ok': False, 'error': err}
    if not isinstance(driver, CivRadio):
        return {'ok': False, 'error': 'Scope CI-V réservé aux radios Icom/Xiegu (protocole CI-V)'}
    try:
        return driver.configure_scope(mode, span_hz)
    except Exception as e:
        disconnect_persistent()
        return {'ok': False, 'error': f'Radio injoignable ({e})'}


def scope_line(cfg, timeout=2.0):
    """Lit/réassemble UNE ligne de spectre scope CI-V (budget de temps borné,
    cohérent avec les autres timeouts CAT de ce module)."""
    settings = cat_settings(cfg)
    if not settings['enabled'] or settings['mode'] != 'native':
        return {'ok': False, 'error': 'Pilotage natif non actif'}
    if settings['model'] not in MODELES_SCOPE_CIV:
        # Voir le commentaire équivalent dans scope_configure() ci-dessus.
        return {'ok': False, 'error': f"Modèle « {settings['model'] or '?'} » non supporté "
                f"pour le scope CI-V (supportés : {', '.join(sorted(MODELES_SCOPE_CIV))})"}
    driver, err = _ensure_connected(settings)
    if err:
        return {'ok': False, 'error': err}
    if not isinstance(driver, CivRadio):
        return {'ok': False, 'error': 'Scope CI-V réservé aux radios Icom/Xiegu (protocole CI-V)'}
    try:
        return driver.read_scope_line(timeout=timeout)
    except Exception as e:
        disconnect_persistent()
        return {'ok': False, 'error': f'Radio injoignable ({e})'}


def test_connection(brand, model, port, baudrate, civ_addr=None):
    """Test ÉPHÉMÈRE (bouton CONFIG) : ouvre, interroge, ferme — ne touche
    jamais à la connexion persistante utilisée par le polling logbook.
    `civ_addr` (texte hexa, ex. "AA") : adresse CI-V manuelle si l'opérateur
    l'a changée sur la radio — repli sur l'adresse usine du modèle sinon."""
    if not port:
        return {'ok': False, 'error': 'Port série manquant'}
    brand = (brand or '').strip().lower()
    try:
        transport = _open_serial_retry(port, baudrate or CAT_DEFAULT_BAUD.get(brand, 19200))
    except Exception as e:
        return {'ok': False, 'error': _friendly_open_error(port, e)}
    try:
        if brand in ('icom', 'xiegu'):
            addr = _parse_civ_addr(civ_addr) or CIV_ADDRESSES.get(model, 0x94)
            driver = CivRadio(transport, addr)
            f = driver.get_freq()
            if not f.get('ok'):
                return {'ok': False, 'error': 'Radio muette à cette adresse — '
                                              'vérifie modèle/adresse CI-V/port/vitesse'}
            return {'ok': True, 'detected_model': model, 'freq_hz': f['freq_hz']}
        driver = AsciiRadio(transport, brand, model)
        st = driver.get_state()
        if not st.get('ok'):
            return {'ok': False, 'error': 'Pas de réponse — vérifie port/vitesse/câble'}
        ident = driver.identify()
        return {'ok': True, 'detected_model': (ident.get('model') if ident.get('ok') else None) or model,
                'freq_hz': st.get('freq_hz')}
    except Exception as e:
        return {'ok': False, 'error': f'Radio injoignable ({e})'}
    finally:
        transport.close()


class RigManager:
    """Registre des radios actives : radio_id -> pilote (CivRadio/AsciiRadio)
    + son transport. Permet plusieurs radios simultanées, chacune sur son
    propre port — c'est la brique de base d'un futur mode SO2R."""

    def __init__(self):
        self._radios = {}   # id -> {'driver':..., 'transport':..., 'meta':...}
        self._lock = threading.Lock()

    def add(self, radio_id, transport, protocol, brand=None, model=None, addr=None):
        if protocol == 'civ':
            driver = CivRadio(transport, addr)
        else:
            driver = AsciiRadio(transport, brand, model)
        with self._lock:
            self._radios[radio_id] = {'driver': driver, 'transport': transport,
                                      'protocol': protocol, 'brand': brand, 'model': model}

    def remove(self, radio_id):
        with self._lock:
            entry = self._radios.pop(radio_id, None)
        if entry:
            entry['transport'].close()

    def get(self, radio_id):
        with self._lock:
            entry = self._radios.get(radio_id)
        return entry['driver'] if entry else None

    def list_active(self):
        with self._lock:
            return {rid: {'protocol': e['protocol'], 'brand': e['brand'], 'model': e['model']}
                    for rid, e in self._radios.items()}


def autodetect(transport):
    """Tente d'identifier la radio connectée sur `transport` : ASCII `ID;`
    en premier (couvre Yaesu/Kenwood/Elecraft/K4), repli CI-V `19 00` aux
    adresses Icom connues si l'ASCII reste muet (voir doc §9).
    Retourne {'ok', 'protocol', 'brand'?, 'model'?, 'addr'?} — jamais de
    certitude absolue pour Icom (l'adresse peut avoir été changée par
    l'utilisateur), signalé via 'certain': True/False."""
    try:
        reply = _transceive(transport, b'ID;', b';', timeout=0.8).decode('ascii', errors='replace')
    except Exception:
        reply = ''
    if reply.startswith('ID') and any(c.isdigit() for c in reply):
        code = ''.join(c for c in reply if c.isdigit())
        model = ASCII_ID_TABLE.get(code)
        if model:
            return {'ok': True, 'protocol': 'ascii', 'brand': BRAND_BY_MODEL.get(model),
                    'model': model, 'certain': True}
        if code == '017':
            return {'ok': True, 'protocol': 'ascii', 'brand': 'elecraft',
                    'model': None, 'certain': False,
                    'note': 'K3/K3S/KX3/KX2 confondus — tester K3;/OM; pour affiner'}

    for name, addr in CIV_ADDRESSES.items():
        def _matches(raw, addr=addr):
            # Même garde-fou de sens ET de commande que CivRadio._query() :
            # TO=E0(PC), FROM=addr (la radio interrogée à CET essai précis),
            # ET cmd=0x19/sub=0x00 (sinon la réponse d'un AUTRE logiciel à SA
            # propre commande, sur un bus CI-V partagé, serait prise pour une
            # identification réussie — trouvé en revue adversariale avant
            # fusion, même piège que l'écho/bouclage déjà corrigé).
            parsed = civ_parse_frame(raw)
            if (parsed and parsed[0] == CIV_CTRL_ADDR and parsed[1] == addr
                    and parsed[2] == 0x19 and parsed[3] == 0x00):
                return parsed
            return None
        try:
            # accept= : une trame parasite (bus CI-V partagé, notification
            # "CI-V Transceive") ne fait plus abandonner l'essai après une
            # seule lecture — on relit dans le budget de timeout restant.
            raw = _transceive(transport, civ_build_frame(addr, 0x19, sub=0x00), CIV_END,
                               timeout=0.5, accept=lambda r: _matches(r) is not None)
        except Exception:
            continue
        if _matches(raw):
            return {'ok': True, 'protocol': 'civ', 'brand': 'icom', 'model': name,
                    'addr': addr, 'certain': False,
                    'note': "Adresse CI-V par défaut détectée — peut avoir été "
                            "changée manuellement sur la radio"}

    return {'ok': False, 'error': 'Aucune radio détectée automatiquement — '
                                  'choisis ta marque/modèle manuellement'}


# Vitesses courantes essayées par autodetect_scan(), dans l'ordre — 19200 et
# 9600 couvrent la grande majorité des postes récents (Icom USB, Kenwood,
# Elecraft), les suivantes rattrapent les réglages d'usine plus anciens
# (Yaesu 4800) ou les vitesses hautes de certains Icom (38400).
_AUTODETECT_BAUDS = (19200, 9600, 4800, 38400)


def autodetect_scan(port, bauds=None):
    """Bouton CONFIG « auto-détecter » quand marque/modèle sont encore
    inconnus (contrairement à test_connection(), qui les exige déjà) :
    balaie plusieurs vitesses courantes sur `port` et tente autodetect() à
    chacune, jusqu'à la première qui répond.

    Usage ponctuel (clic bouton) seulement — jamais en tâche de fond : le
    pire cas (rien ne répond, ex. mauvais port ou radio éteinte) peut
    prendre jusqu'à ~50s (autodetect() balaie déjà 23 adresses CI-V par
    vitesse essayée, ce module étant appelé une fois par vitesse)."""
    if not port:
        return {'ok': False, 'error': 'Port série manquant'}
    tried = list(bauds or _AUTODETECT_BAUDS)
    for baud in tried:
        try:
            transport = _open_serial_retry(port, baud)
        except Exception as e:
            return {'ok': False, 'error': _friendly_open_error(port, e)}
        try:
            result = autodetect(transport)
        finally:
            transport.close()
        if result.get('ok'):
            result['baudrate'] = baud
            return result
    return {'ok': False,
            'error': f"Aucune radio détectée sur {port} (essayé "
                     f"{', '.join(str(b) for b in tried)} bauds) — vérifie "
                     "le câble/port, que la radio est allumée et le CAT "
                     "activé, ou choisis marque/modèle/vitesse manuellement"}
