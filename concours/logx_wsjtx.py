# -*- coding: utf-8 -*-
"""Pont WSJT-X → LogX : auto-log FT8/FT4 en temps réel.

WSJT-X diffuse toute son activité en UDP (protocole Qt QDataStream, gros-boutien,
port 2237 par défaut). Deux messages nous intéressent :
  - type 1 « Status »   : bande/fréquence/mode courants → indicateur de liaison.
  - type 5 « QSO Logged » : émis quand l'opérateur valide un QSO dans WSJT-X
    → le contact atterrit AUTOMATIQUEMENT dans le logbook partagé (call, grid,
    bande, mode, rapports, heure), sans ressaisie.

Côté WSJT-X : Réglages → Rapports → « UDP Server » = adresse du PC LogX,
port 2237. Fonctionnalité désactivée par défaut ; activée dans CONFIG.

L'insertion dans le log réutilise la même logique (dédup + scoring) que la
saisie manuelle, via un callback fourni par le serveur.
"""
import collections
import math
import re
import socket
import struct
import threading
import datetime
from logx_utils import utcnow

MAGIC = 0xADBCCBDA
DEFAULT_PORT = 2237

# État partagé pour l'indicateur de liaison (widget logbook)
status = {'connected': False, 'last_seen': 0, 'dial_mhz': 0, 'mode': '',
          'tx_mode': '', 'de_call': '', 'logged_total': 0}
_status_lock = threading.Lock()
_listener_started = False
_listener_lock = threading.Lock()


# ─── LECTEUR QDataStream (gros-boutien) ──────────────────────────────────────
class _Reader:
    def __init__(self, data):
        self.d = data
        self.i = 0

    def u32(self):
        v = struct.unpack_from('>I', self.d, self.i)[0]
        self.i += 4
        return v

    def u64(self):
        v = struct.unpack_from('>Q', self.d, self.i)[0]
        self.i += 8
        return v

    def i64(self):
        v = struct.unpack_from('>q', self.d, self.i)[0]
        self.i += 8
        return v

    def i32(self):
        v = struct.unpack_from('>i', self.d, self.i)[0]
        self.i += 4
        return v

    def f64(self):
        v = struct.unpack_from('>d', self.d, self.i)[0]
        self.i += 8
        return v

    def u8(self):
        v = self.d[self.i]
        self.i += 1
        return v

    def utf8(self):
        """Chaîne Qt : longueur u32 (0xffffffff = null) puis octets UTF-8."""
        n = self.u32()
        if n == 0xFFFFFFFF:
            return ''
        s = self.d[self.i:self.i + n].decode('utf-8', 'replace')
        self.i += n
        return s

    def datetime(self):
        """QDateTime Qt : QDate (jour julien i64) + QTime (ms u32) + timespec u8."""
        jdn = self.i64()
        ms = self.u32()
        spec = self.u8()
        if spec == 2:      # OffsetFromUTC : + offset i32
            self.i += 4
        return _jdn_to_datetime(jdn, ms)


def _jdn_to_datetime(jdn, ms):
    """Jour julien + millisecondes → datetime UTC (None si invalide)."""
    try:
        # Algorithme standard (Fliegel & Van Flandern)
        a = jdn + 32044
        b = (4 * a + 3) // 146097
        c = a - (146097 * b) // 4
        d = (4 * c + 3) // 1461
        e = c - (1461 * d) // 4
        m = (5 * e + 2) // 153
        day = e - (153 * m + 2) // 5 + 1
        month = m + 3 - 12 * (m // 10)
        year = 100 * b + d - 4800 + m // 10
        sec = ms // 1000
        return datetime.datetime(year, month, day, sec // 3600,
                                 (sec % 3600) // 60, sec % 60)
    except Exception:
        return None


# ─── PARSING DES MESSAGES ────────────────────────────────────────────────────
# ─── ÉCRITEUR QDataStream : le sens SORTANT, vers WSJT-X ─────────────────────
# Jusqu'ici la liaison était en écoute seule. WSJT-X accepte pourtant des
# messages sur le même socket UDP, et c'est la seule voie pour lui faire
# répondre à un décodage sans que personne ne touche la souris.
#
# LE PIÈGE DE FORMAT, et il est silencieux : Qt sérialise un `float` déclaré
# dans WSJT-X sur HUIT octets, pas quatre — QDataStream est en double précision
# par défaut. Le décodeur du projet le confirme, il lit ce champ avec f64
# (voir le type 2 « Decode » plus bas). Écrire 4 octets décalerait tout ce qui
# suit et WSJT-X jetterait le message sans un mot. On mirroir donc exactement
# le lecteur : c'est LUI la référence, pas la documentation.

TYPE_REPLY = 4
TYPE_HALT_TX = 8


class _Writer:
    """Miroir strict de _Reader. Toute méthode ajoutée ici doit avoir sa
    jumelle en lecture, sinon les deux formats divergent en silence."""

    def __init__(self):
        self.parts = []

    def u32(self, v):
        self.parts.append(struct.pack('>I', int(v) & 0xFFFFFFFF))
        return self

    def i32(self, v):
        self.parts.append(struct.pack('>i', int(v)))
        return self

    def f64(self, v):
        self.parts.append(struct.pack('>d', float(v)))
        return self

    def u8(self, v):
        self.parts.append(struct.pack('>B', int(v) & 0xFF))
        return self

    def utf8(self, s):
        """Chaîne Qt : longueur u32 puis octets UTF-8. Une chaîne VIDE et une
        chaîne NULLE ne s'encodent pas pareil (0 contre 0xffffffff) ; WSJT-X
        tolère les deux ici, on écrit la forme vide, plus simple à relire."""
        b = ('' if s is None else str(s)).encode('utf-8')
        self.u32(len(b))
        if b:
            self.parts.append(b)
        return self

    def octets(self):
        return b''.join(self.parts)


def _entete(mtype, wsjtx_id, schema=2):
    w = _Writer()
    w.u32(MAGIC).u32(schema).u32(mtype).utf8(wsjtx_id or '')
    return w


def construire_reply(decodage, wsjtx_id, schema=2):
    """Message « Reply » (type 4) : demande à WSJT-X de répondre À CE décodage.

    C'est l'équivalent exact d'un double-clic sur la ligne dans le waterfall :
    WSJT-X remplit l'indicatif, cale le décalage audio et arme l'émission selon
    ses propres réglages. On ne fabrique donc AUCUN message radio nous-mêmes —
    c'est WSJT-X qui reste maître de ce qui part sur l'air.

    Les champs du décodage sont RENVOYÉS TELS QUELS. WSJT-X s'en sert pour
    retrouver la ligne concernée : une heure ou un delta approximatif et il ne
    reconnaît rien. D'où la nécessité d'avoir conservé time_ms, snr et dt à la
    lecture — ce que l'ancien parseur jetait.
    """
    w = _entete(TYPE_REPLY, wsjtx_id, schema)
    w.u32(decodage.get('time_ms', 0))
    w.i32(decodage.get('snr', 0))
    w.f64(decodage.get('dt', 0.0))
    w.u32(decodage.get('delta_hz', 0))
    w.utf8(decodage.get('mode', ''))
    w.utf8(decodage.get('message', ''))
    w.u8(1 if decodage.get('low_confidence') else 0)
    w.u8(int(decodage.get('modifiers', 0)))
    return w.octets()


def construire_halt_tx(wsjtx_id, auto_seulement=False, schema=2):
    """Message « Halt Tx » (type 8) : coupe l'émission de WSJT-X.

    C'est le coupe-circuit. auto_seulement=True désarme l'émission automatique
    en laissant finir la séquence en cours ; False coupe immédiatement. Les
    deux doivent exister : l'arrêt propre pour la fin d'une session sans
    surveillance, l'arrêt net pour un opérateur qui reprend la main.
    """
    w = _entete(TYPE_HALT_TX, wsjtx_id, schema)
    w.u8(1 if auto_seulement else 0)
    return w.octets()


def parse_message(data):
    """Retourne un dict décrivant le message, ou None si non pertinent/illisible.
    Types gérés : 1 (Status), 2 (Decode) et 5 (QSO Logged)."""
    if len(data) < 12:
        return None
    r = _Reader(data)
    # TOUTE la lecture — en-tête compris — est protégée : un datagramme avec le
    # bon MAGIC mais tronqué (12 octets pile, ou coupé au milieu de l'id) faisait
    # lever struct.error/IndexError DÈS l'en-tête, hors du try, ce qui remontait
    # jusqu'à la boucle _run et TUAIT le thread d'écoute (plus aucun auto-log
    # jusqu'au redémarrage). N'importe quel logiciel parlant sur le port suffisait.
    try:
        if r.u32() != MAGIC:
            return None
        schema = r.u32()
        mtype = r.u32()
        # L'identifiant d'instance et la version de schéma étaient LUS PUIS
        # JETÉS. Ils sont indispensables pour répondre : tout message qu'on
        # renvoie doit porter le même id (WSJT-X ignore les autres) et le même
        # schéma. On les remonte donc systématiquement.
        wsjtx_id = r.utf8()
        if mtype == 1:      # Status
            dial_hz = r.u64()
            mode = r.utf8()
            r.utf8()        # dx_call
            r.utf8()        # report
            tx_mode = r.utf8()
            return {'type': 'status', 'dial_mhz': round(dial_hz / 1e6, 4),
                    'mode': mode, 'tx_mode': tx_mode,
                    'wsjtx_id': wsjtx_id, 'schema': schema}
        if mtype == 2:      # Decode : un décodage affiché dans le waterfall (PAS un QSO)
            r.u8()          # 'new' (bool) — pas utilisé
            # Heure, SNR et delta temps étaient LUS PUIS JETÉS : le cache de
            # décodages se contente de l'horloge du serveur pour sa fraîcheur.
            # Mais un message « Reply » doit RENVOYER ces trois champs à
            # l'identique — c'est ainsi que WSJT-X retrouve la ligne visée. Les
            # jeter, c'était s'interdire à jamais de répondre à un décodage.
            time_ms = r.u32()   # QTime : ms depuis minuit UTC
            snr = r.i32()
            dt = r.f64()        # delta temps (s), 8 octets — voir _Writer.f64
            delta_hz = r.u32()
            mode = r.utf8()
            message = r.utf8()
            return {'type': 'decode', 'mode': mode, 'message': message,
                    'delta_hz': delta_hz, 'time_ms': time_ms, 'snr': snr,
                    'dt': dt, 'wsjtx_id': wsjtx_id, 'schema': schema}
        if mtype == 5:      # QSO Logged
            time_off = r.datetime()
            call = r.utf8()
            grid = r.utf8()
            dial_hz = r.u64()
            mode = r.utf8()
            rpt_sent = r.utf8()
            rpt_recv = r.utf8()
            r.utf8()        # tx_power
            r.utf8()        # comments
            r.utf8()        # name
            time_on = r.datetime()
            return {'type': 'qso_logged', 'call': call, 'grid': grid,
                    'dial_mhz': round(dial_hz / 1e6, 4), 'mode': mode,
                    'rpt_sent': rpt_sent, 'rpt_recv': rpt_recv,
                    'time_on': time_on or time_off}
    except (struct.error, IndexError):
        return None
    return None


def _mhz_to_band(mhz):
    """Fréquence dial (MHz) → bande interne."""
    # Bandes WARC (30/17/12 m) mappées sur LEUR propre code interne — pas sur
    # la bande contest voisine : un QSO 30 m rabattu sur '7' (40 m) faussait la
    # déduplication, la Worked Matrix, les diplômes DXCC par bande et l'export.
    for lo, hi, b in ((1.8, 2.0, '1.8'), (3.5, 4.0, '3.5'), (7.0, 7.3, '7'),
                      (10.1, 10.15, '10.1'), (14.0, 14.35, '14'), (18.0, 18.2, '18'),
                      (21.0, 21.45, '21'), (24.8, 25.0, '24'), (28.0, 29.7, '28'),
                      (50, 54, '50'), (70, 71, '70'), (144, 148, '144'),
                      (430, 440, '432')):
        if lo <= mhz <= hi:
            return b
    return str(int(mhz)) if mhz else ''


# ─── ALERTE « DXCC/DÉPARTEMENT MANQUANT » (façon GridTracker) ────────────────
# GridTracker (référence de l'écosystème FT8) colore/alerte un décodage qui
# correspond à un pays/département JAMAIS travaillé — sa fonction la plus
# plébiscitée. Ici : on extrait le(s) indicatif(s) de chaque message Decode
# (type 2, un par station ENTENDUE dans le waterfall — pas un QSO) et on les
# garde en cache le temps qu'ils restent "actifs". Le croisement avec le log
# (DXCC déjà travaillé/confirmé à VIE) est fait côté logx_http.py via
# logx_awards.spotted_new_ones() — déjà écrite pour exactement la même
# question posée aux spots du cluster DX, pas de logique dupliquée ici.
_GRID_RE = re.compile(r'^[A-X]{2}\d{2}([A-X]{2})?$')
_CALL_RE = re.compile(r'^[0-9A-Z]{1,4}\d[A-Z]{1,4}(?:/[0-9A-Z]{1,4})?$')
# Forme "cœur" d'un indicatif (sans préfixe/suffixe composé) — sert à
# reconnaître le format PRÉFIXE/INDICATIF (voir _is_compound_prefix_call).
_BASE_CALL_RE = re.compile(r'^[0-9A-Z]{1,4}\d[A-Z]{1,4}$')
_PORTABLE_SUFFIXES = {'P', 'M', 'MM', 'AM', 'QRP', 'A', 'J', 'LH'}
_REPORT_RE = re.compile(r'^R?[+-]\d{2}$')
_DECODE_SKIP_TOKENS = {'CQ', 'QRZ', 'DE', 'RRR', 'RR73', '73', 'TNX', 'TU',
                       'DX', 'TEST', 'POTA', 'SOTA', 'WWFF', 'IOTA', 'AGN'}
_DECODE_TTL = 300     # 5 min : au-delà, une station décodée n'est plus "active"

_decodes = {}         # call -> {'band','freq_mhz','mode','last_seen'}
_decodes_lock = threading.Lock()


def _is_compound_prefix_call(tok):
    """PRÉFIXE/INDICATIF façon DXpedition (ex. PJ4/K1ABC, 9A/OK1ABC) — le
    format le plus courant en pratique, que _CALL_RE ne reconnaît PAS (il est
    pensé pour la forme inverse INDICATIF/SUFFIXE : F4ABC/P, F4ABC/QRP...).
    On distingue les deux formes en regardant quelle moitié a la forme d'un
    indicatif complet : dans INDICATIF/SUFFIXE c'est la partie AVANT le '/'
    (le suffixe, court, n'a pas cette forme) ; dans PRÉFIXE/INDICATIF c'est la
    partie APRÈS. Un préfixe purement numérique (ex. K1ABC/4, changement de
    zone) n'est pas un préfixe DXCC — exclu pour ne pas empiéter sur ce que
    _CALL_RE gère déjà."""
    if tok.count('/') != 1:
        return False
    prefix, base = tok.split('/')
    return bool(_BASE_CALL_RE.match(base)) and prefix not in _PORTABLE_SUFFIXES and not prefix.isdigit()


def extract_calls(message, my_call=''):
    """Indicatifs plausibles dans un message décodé FT8/FT4 (ex. « CQ F4ABC
    JN18 », « F4ABC F5XYZ +05 », « F4ABC F5XYZ RR73 », « PJ4/K1ABC F5XYZ
    +05 ») — exclut les grilles Maidenhead, les rapports, les jokers usuels
    (CQ/DX/POTA...) et mon propre indicatif (sous sa forme simple OU
    composée : PJ4/K1ABC exclu si my_call vaut 'K1ABC' OU 'PJ4/K1ABC').
    Reconnaît aussi bien INDICATIF/SUFFIXE (/P, /QRP, /M...) que PRÉFIXE/
    INDICATIF façon DXpedition (PJ4/K1ABC, 9A/OK1ABC) — voir
    _is_compound_prefix_call(). Parsing volontairement simple (PAS un
    décodeur FT8 complet comme WSJT-X lui-même) : suffisant pour savoir QUI
    est entendu, pas pour rejouer tout l'échange.

    Grammaire FT8 standard : « <destinataire> <émetteur> <rapport/RRR/
    RR73/73> ». Si aucun des deux indicatifs trouvés n'est le mien (échange
    entre deux tiers observé passivement dans le waterfall), seul le SECOND
    a réellement ÉMIS ce décodage précis — le premier n'est que le
    destinataire visé, pas prouvé "entendu" par ce message-là. On ne garde
    donc que l'émetteur dans ce cas, pour ne pas faire remonter un faux
    "entendu" sur toute conversation tierce."""
    my = (my_call or '').upper().strip()
    out = []
    for tok in (message or '').upper().replace('<', '').replace('>', '').split():
        if tok in _DECODE_SKIP_TOKENS or _REPORT_RE.match(tok) or _GRID_RE.match(tok):
            continue
        if my and (tok == my or my in tok.split('/')):
            continue
        if _CALL_RE.match(tok) or _is_compound_prefix_call(tok):
            out.append(tok)
    if len(out) == 2:
        out = out[1:]      # échange tiers : ne garder que l'émetteur (2e position)
    return out


def extract_grid(message):
    """Carré Maidenhead porté par un décodage FT8/FT4, ou '' s'il n'y en a pas.

    LE PIÈGE, et il casse la moitié des implémentations maison : « RR73 »
    CORRESPOND au motif d'un carré — RR est un champ valide (A-X), 73 des
    chiffres valides. Un parseur naïf invente donc un carré en Sibérie
    orientale à chaque fin de QSO, c'est-à-dire tout le temps. Idem pour
    « RRR » et « 73 ». D'où le filtrage par _DECODE_SKIP_TOKENS AVANT le
    motif, et jamais l'inverse.

    Seuls « CQ CALL GRID » et « CALL CALL GRID » portent un carré : un
    décodage avec rapport (« F4GLD K1ABC -15 »), un RR73 ou un 73 n'en a pas.
    C'est pourquoi le carré doit être MÉMORISÉ par indicatif (voir
    record_decode) et pas relu à chaque message.
    """
    for tok in (message or '').upper().replace('<', '').replace('>', '').split():
        if tok in _DECODE_SKIP_TOKENS:
            continue
        if _GRID_RE.match(tok):
            return tok
    return ''


def _decode_freq_mhz(msg):
    """Fréquence réelle du décodage (MHz) = dial courant (dernier message
    Status reçu) + décalage audio (delta_hz) du décodage. 0 si le dial n'est
    pas encore connu (aucun Status reçu depuis le démarrage de l'écoute)."""
    with _status_lock:
        dial = status.get('dial_mhz') or 0
    if not dial:
        return 0
    return round(dial + (msg.get('delta_hz', 0) or 0) / 1e6, 4)


# ─── L'HORLOGE SANS INTERNET ────────────────────────────────────────────────
# En expédition, sans NTP, l'horloge du PC dérive de quelques secondes par
# jour. Au-delà d'environ une seconde, les stations d'en face cessent de
# décoder les appels FT8 — et RIEN ne le signale : on croit simplement que la
# bande est fermée. C'est une panne silencieuse qui peut coûter des jours.
#
# LA MESURE EXISTE DÉJÀ, gratuitement : chaque décodage WSJT-X porte son DT,
# l'écart entre le début du signal reçu et le début de MA fenêtre de
# réception. Le consensus de dizaines de stations distinctes est la seule
# référence de temps disponible quand il n'y a plus de réseau.
#
# SENS DU DT, démontré et non recopié de mémoire (le projet a déjà payé cher
# une table écrite au jugé) : soit e l'avance de mon horloge sur l'UTC vrai
# (e > 0 = j'avance). Une station correcte émet à l'instant UTC vrai T. Ma
# fenêtre de réception s'ouvre quand MON horloge affiche T, c'est-à-dire à
# l'instant vrai T − e. Le signal commence donc e seconde APRÈS l'ouverture de
# ma fenêtre : DT = +e. Autrement dit, un DT médian positif signifie que MON
# horloge AVANCE, et qu'il faut la reculer d'autant. Le temps de propagation
# (au plus ~40 ms en HF) est négligeable devant le seuil d'une seconde.
#
# CE QUE CETTE FONCTION NE FAIT PAS : corriger rétroactivement l'heure des
# QSO. La dérive qui tue le FT8 se joue à ±1 s, or ni les robots de concours
# ni LoTW ne contestent à la seconde près — leurs tolérances sont en minutes.
# Réécrire un log pour ça serait prendre un risque sans contrepartie.
_dt_echantillons = collections.deque(maxlen=4000)   # (ts, indicatif, dt)

# Trois états, jamais deux. « Pas de mesure » (expédition CW/SSB, aucun
# décodage) n'est PAS « horloge bonne » ; et un effondrement du nombre de
# décodages est justement le symptôme d'une horloge partie trop loin — le dire
# vaut mieux que d'afficher une dérive calculée sur trois échantillons.
DERIVE_VERTE_S = 0.5
DERIVE_ROUGE_S = 1.2
DERIVE_MIN_STATIONS = 5


def _note_dt(call, msg, maintenant):
    dt = msg.get('dt')
    if not isinstance(dt, (int, float)):
        return
    if not math.isfinite(dt) or abs(dt) > 15:
        return          # hors de tout sens physique : décodage aberrant
    _dt_echantillons.append((maintenant, call, float(dt)))


def derive_horloge(fenetre_s=3 * 3600, maintenant=None):
    """L'écart mesuré entre mon horloge et le consensus des stations reçues.

    Rend toujours un dict avec `etat` :
      - 'mesuree'  : assez de stations DISTINCTES pour conclure ;
      - 'peu_de_donnees' : des décodages, mais pas assez de stations ;
      - 'aucune_mesure'  : aucun décodage dans la fenêtre.
    La médiane est prise sur les stations distinctes (un dernier DT par
    indicatif) : une station bavarde ne doit pas peser plus qu'une autre.
    """
    import time as _t
    now = maintenant if maintenant is not None else _t.time()
    debut = now - fenetre_s
    par_station = {}
    total = 0
    for ts, call, dt in _dt_echantillons:
        if ts < debut:
            continue
        total += 1
        par_station[call] = dt          # le plus récent de cette station
    n_stations = len(par_station)
    if not n_stations:
        return {'etat': 'aucune_mesure', 'echantillons': 0, 'stations': 0,
                'secondes': None, 'dispersion': None, 'couleur': 'inconnu'}
    valeurs = sorted(par_station.values())
    m = len(valeurs)
    mediane = (valeurs[m // 2] if m % 2 else
               (valeurs[m // 2 - 1] + valeurs[m // 2]) / 2.0)
    ecarts = sorted(abs(v - mediane) for v in valeurs)
    dispersion = (ecarts[m // 2] if m % 2 else
                  (ecarts[m // 2 - 1] + ecarts[m // 2]) / 2.0)
    if n_stations < DERIVE_MIN_STATIONS:
        etat, couleur = 'peu_de_donnees', 'inconnu'
    else:
        etat = 'mesuree'
        a = abs(mediane)
        couleur = ('verte' if a < DERIVE_VERTE_S
                   else 'rouge' if a > DERIVE_ROUGE_S else 'orange')
    return {'etat': etat, 'echantillons': total, 'stations': n_stations,
            'secondes': round(mediane, 2), 'dispersion': round(dispersion, 2),
            'couleur': couleur}


def record_decode(msg, my_call=''):
    """Message Decode (type 2) -> enregistre le(s) indicatif(s) entendus dans
    le cache des décodages récents (voir recent_decodes()). Isolé de _run()
    pour rester testable sans socket UDP. Purge au passage les entrées
    expirées (cache borné : pas de fuite mémoire sur une session de plusieurs
    jours d'activité FT8/FT4 continue)."""
    calls = extract_calls(msg.get('message', ''), my_call)
    if not calls:
        return []
    import time
    freq_mhz = _decode_freq_mhz(msg)
    band = _mhz_to_band(freq_mhz) if freq_mhz else ''
    mode = msg.get('mode') or ''
    now = time.time()
    # Le carré appartient à l'ÉMETTEUR, dernier indicatif de la grammaire FT8
    # « <destinataire> <émetteur> <carré> » — et c'est justement celui que
    # extract_calls conserve quand il en trouve deux.
    grid = extract_grid(msg.get('message', ''))
    with _decodes_lock:
        for i, c in enumerate(calls):
            connu = _decodes.get(c) or {}
            e = {'band': band, 'freq_mhz': freq_mhz, 'mode': mode, 'last_seen': now}
            # Les champs BRUTS du décodage, conservés pour pouvoir y RÉPONDRE
            # plus tard : un message « Reply » doit les renvoyer à l'identique,
            # c'est ainsi que WSJT-X retrouve la ligne visée (voir
            # construire_reply). Sans eux, on sait qui on a entendu mais on est
            # incapable de le rappeler.
            for cle in ('time_ms', 'snr', 'dt', 'delta_hz', 'message',
                        'wsjtx_id', 'schema'):
                if cle in msg:
                    e[cle] = msg[cle]
            # Le carré une fois connu N'EST JAMAIS EFFACÉ par un décodage
            # ultérieur qui n'en porte pas. Sur un QSO FT8, « CQ F4ABC JN18 »
            # est suivi de « ... -15 », « ... RR73 », « ... 73 » : sans cette
            # persistance, le carré disparaîtrait une seconde après son
            # apparition et l'alerte n'aurait jamais le temps de se déclencher.
            e['grid'] = (grid if (grid and i == len(calls) - 1)
                         else connu.get('grid', ''))
            _decodes[c] = e
            # Le DT part AUSSI dans un flux à part : _decodes est indexé par
            # indicatif, donc le dernier décodage y écrase le précédent — on ne
            # peut pas y lire une série temporelle. Sans ce flux, la dérive
            # d'horloge se calculerait sur un instantané, pas sur trois heures.
            _note_dt(c, msg, now)
        cutoff = now - _DECODE_TTL
        for k in [k for k, v in _decodes.items() if v['last_seen'] < cutoff]:
            del _decodes[k]
    return calls


# ─── NIVEAU 2 : RÉPONDRE À UN DÉCODAGE ───────────────────────────────────────
# « Armer le coup » : LogX remplit l'indicatif dans WSJT-X et cale le décalage
# audio, exactement comme un double-clic sur la ligne. C'est ENSUITE l'opérateur
# qui appuie sur Enable TX — rien ne part sur l'air du seul fait de ce clic.
#
# Trois choses manquaient, toutes jetées par l'écouteur : l'adresse d'où parle
# WSJT-X, la socket par laquelle lui répondre, et l'identifiant de son
# instance. On répond DEPUIS LA SOCKET D'ÉCOUTE et non depuis une socket
# neuve : WSJT-X répond au port d'où vient le message, et une socket éphémère
# ferait aussi trébucher le premier pare-feu venu.
_liaison = {'sock': None, 'peer': None, 'wsjtx_id': '', 'schema': 2}
_liaison_lock = threading.Lock()

# Un décodage plus vieux que ça ne désigne plus rien pour WSJT-X : les cycles
# FT8 durent 15 s et il ne garde que l'activité récente. Répondre à une ligne
# périmée ne provoque aucune erreur — simplement rien ne se passe, ce qui est
# le pire des retours. Mieux vaut refuser en le disant.
AGE_MAX_REPONSE_S = 120


def liaison_prete():
    """La liaison permet-elle d'ÉMETTRE vers WSJT-X ?

    Écouter et pouvoir répondre sont deux choses différentes : tant qu'aucun
    datagramme n'est arrivé, on ignore à quelle adresse parler.
    """
    with _liaison_lock:
        return bool(_liaison['sock'] and _liaison['peer'])


def _noter_liaison(sock, peer, msg):
    with _liaison_lock:
        _liaison['sock'] = sock
        _liaison['peer'] = peer
        if msg.get('wsjtx_id'):
            _liaison['wsjtx_id'] = msg['wsjtx_id']
        if msg.get('schema'):
            _liaison['schema'] = msg['schema']


def repondre_a(call):
    """Demande à WSJT-X de répondre au dernier décodage de `call`.

    Retourne un dict explicite : {'ok': True, ...} ou {'ok': False, 'error'}.
    Chaque refus dit POURQUOI — « rien ne s'est passé » est le retour le plus
    frustrant qui soit quand on vient de cliquer sur un indicatif.
    """
    import time
    c = str(call or '').upper().strip()
    if not c:
        return {'ok': False, 'error': 'Indicatif manquant'}
    with _decodes_lock:
        d = dict(_decodes.get(c) or {})
    if not d:
        return {'ok': False, 'error': 'Indicatif %s pas entendu recemment' % c}
    if 'time_ms' not in d:
        # Décodage mémorisé avant que les champs bruts soient conservés : on ne
        # peut pas fabriquer un Reply qui désigne quoi que ce soit.
        return {'ok': False, 'error': 'Decodage trop ancien pour etre rappele'}
    age = time.time() - d.get('last_seen', 0)
    if age > AGE_MAX_REPONSE_S:
        return {'ok': False,
                'error': 'Decodage vieux de %ds : WSJT-X ne le connait plus' % int(age)}
    with _liaison_lock:
        sock, peer = _liaison['sock'], _liaison['peer']
        wid = d.get('wsjtx_id') or _liaison['wsjtx_id']
        schema = d.get('schema') or _liaison['schema']
    if not sock or not peer:
        return {'ok': False,
                'error': "Aucun message recu de WSJT-X : verifie le serveur UDP "
                         "dans Reglages -> Rapports"}
    try:
        sock.sendto(construire_reply(d, wid, schema), peer)
    except Exception as e:
        return {'ok': False, 'error': 'Envoi impossible : %s' % e}
    print("[WSJTX] Reply -> %s (%s)" % (c, d.get('message', '')))
    return {'ok': True, 'call': c, 'message': d.get('message', ''),
            'mode': d.get('mode', ''), 'delta_hz': d.get('delta_hz', 0)}


def couper_emission(auto_seulement=False):
    """Coupe-circuit : demande à WSJT-X d'arrêter d'émettre."""
    with _liaison_lock:
        sock, peer = _liaison['sock'], _liaison['peer']
        wid, schema = _liaison['wsjtx_id'], _liaison['schema']
    if not sock or not peer:
        return {'ok': False, 'error': 'Aucune liaison WSJT-X'}
    try:
        sock.sendto(construire_halt_tx(wid, auto_seulement, schema), peer)
    except Exception as e:
        return {'ok': False, 'error': 'Envoi impossible : %s' % e}
    print("[WSJTX] Halt Tx (auto_seulement=%s)" % auto_seulement)
    return {'ok': True, 'auto_seulement': bool(auto_seulement)}


def recent_decodes(max_age=_DECODE_TTL):
    """Décodages FT8/FT4 encore « actifs » (call, band, freq_mhz, mode,
    last_seen) — consommé par _wsjtx_state_dict() (logx_http.py) pour
    l'alerte DXCC/département manquant façon GridTracker.

    Purge aussi le cache (pas seulement record_decode()) : sinon, un flux de
    décodages qui s'arrête (WSJT-X fermé) laisse les entrées expirées
    s'accumuler indéfiniment tant que rien ne rappelle record_decode() pour
    déclencher la purge — même si elles restent invisibles côté appelant
    (déjà filtrées ci-dessous). Lecture ET purge dans le MÊME bloc
    "with lock" : jamais de relâchement du verrou entre les deux. La purge
    utilise le TTL réel du cache (_DECODE_TTL), pas le max_age demandé par
    l'appelant : ce dernier ne sert qu'à filtrer la VUE retournée, pas à
    raccourcir la rétention réelle si jamais un appelant passe une fenêtre
    plus courte."""
    import time
    now = time.time()
    with _decodes_lock:
        purge_cutoff = now - _DECODE_TTL
        for k in [k for k, v in _decodes.items() if v['last_seen'] < purge_cutoff]:
            del _decodes[k]
        cutoff = now - max_age
        return [dict(call=c, **v) for c, v in _decodes.items() if v['last_seen'] >= cutoff]


def _my_call(cfg):
    """Indicatif réellement émis par la station (celui que WSJT-X transmet),
    PAS op_call (opérateur responsable du log, souvent différent en
    multi-opérateurs) — repli sur l'indicatif personnel si aucun indicatif de
    concours n'est renseigné."""
    cfg = cfg or {}
    return (cfg.get('callsign_contest') or cfg.get('callsign') or '').upper().strip()


def qso_from_logged(msg, cfg):
    """Message QSO Logged → dict QSO prêt pour le log partagé."""
    from logx_utils import locator_to_latlon, haversine
    dt = msg.get('time_on') or utcnow()
    my_loc = (cfg or {}).get('locator', '')
    grid = (msg.get('grid') or '').upper()
    dist = 0
    if grid:
        # WSJT-X envoie une grille 4 caractères (FT8) : la compléter au CENTRE
        # du carré ('FN31' → 'FN31MM') pour la distance ; la grille d'origine
        # reste stockée telle quelle dans le log.
        g6 = grid if len(grid) >= 6 else (grid + 'MM')[:6]
        a, b = locator_to_latlon(my_loc), locator_to_latlon(g6)
        if a[0] is not None and b[0] is not None:
            dist = haversine(a[0], a[1], b[0], b[1])
    return {
        'call': (msg.get('call') or '').upper(),
        'band': _mhz_to_band(msg.get('dial_mhz', 0)),
        'mode': (msg.get('mode') or 'FT8').upper(),
        'date': dt.strftime('%Y%m%d'), 'time': dt.strftime('%H:%M'),
        'rst_sent': msg.get('rpt_sent', ''), 'rst_rcvd': msg.get('rpt_recv', ''),
        'locator': (msg.get('grid') or '').upper(), 'dist': dist,
        'my_locator': my_loc, 'contest': (cfg or {}).get('contest', ''),
        'source': 'wsjtx', 'operator': (cfg or {}).get('op_call', ''),
    }


# ─── ÉCOUTEUR UDP ─────────────────────────────────────────────────────────────
def wsjtx_settings(cfg):
    cfg = cfg or {}
    enabled = bool(cfg.get('wsjtx_enabled'))
    port = cfg.get('wsjtx_port')
    if not enabled or not port:
        try:
            import json
            with open('config.json', encoding='utf-8') as f:
                w = (json.load(f).get('wsjtx', {}) or {})
            enabled = enabled or bool(w.get('enabled'))
            port = port or w.get('port')
        except Exception:
            pass
    try:
        port = int(port)
    except (TypeError, ValueError):
        port = DEFAULT_PORT
    return {'enabled': enabled, 'port': port}


def start_listener(get_cfg, add_qso, port=DEFAULT_PORT, on_decode=None,
                   on_qso=None):
    """Démarre l'écouteur UDP en thread de fond (idempotent).

    get_cfg() -> config courante ; add_qso(qso_dict) -> insère dans le log.

    on_decode(calls, msg) et on_qso(msg) sont des rappels FACULTATIFS, fournis
    par logx_http pour Wait-and-Pounce. Ils vivent là-bas et pas ici parce que
    décider s'il faut appeler demande le carnet, les confirmations LoTW et le
    barème du concours — que ce module n'a aucune raison de connaître. Ils
    tournent dans CE thread : au niveau 4, personne n'a de navigateur ouvert,
    la décision ne peut donc pas dépendre d'un client qui interroge.
    """
    global _listener_started
    # Check-then-set sous verrou : deux /wsjtx/state simultanés ne peuvent plus
    # lancer deux threads sur le même port.
    with _listener_lock:
        if _listener_started:
            return
        _listener_started = True

    def _run():
        global _listener_started
        import time
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(('0.0.0.0', port))
            sock.settimeout(1.0)
            print(f"[WSJTX] Ecoute UDP sur le port {port}")
        except Exception as e:
            print(f"[WSJTX] Impossible d'ecouter le port {port}: {e}")
            # Bind raté : on relâche le drapeau pour qu'une tentative ultérieure
            # (port libéré entre-temps) puisse redémarrer l'écouteur.
            with _listener_lock:
                _listener_started = False
            return
        while True:
            try:
                data, peer = sock.recvfrom(8192)
            except socket.timeout:
                continue
            except Exception:
                continue
            msg = parse_message(data)
            if not msg:
                continue
            # L'adresse de l'émetteur était JETÉE. C'est pourtant la seule
            # façon de savoir à qui répondre : WSJT-X n'annonce nulle part son
            # port d'écoute, il faut le déduire de ce qu'il nous envoie. On
            # garde aussi la socket : répondre depuis une autre changerait le
            # port source, ce que WSJT-X et les pare-feu n'aiment ni l'un ni
            # l'autre.
            _noter_liaison(sock, peer, msg)
            with _status_lock:
                status['connected'] = True
                status['last_seen'] = time.time()
                if msg.get('dial_mhz'):
                    status['dial_mhz'] = msg['dial_mhz']
                if msg.get('mode'):
                    status['mode'] = msg['mode']
            if msg['type'] == 'qso_logged':
                try:
                    qso = qso_from_logged(msg, get_cfg() or {})
                    if qso['call']:
                        res = add_qso(qso)
                        if res:
                            with _status_lock:
                                status['logged_total'] += 1
                            print(f"[WSJTX] +QSO auto {qso['call']} {qso['band']}MHz {qso['mode']}")
                except Exception as e:
                    print(f"[WSJTX] Erreur auto-log: {e}")
                # Le QSO a abouti : la session d'appel automatique doit le
                # savoir, sinon elle rappellerait indéfiniment une station
                # déjà travaillée. Enveloppé à part, même raison que ci-dessous.
                if on_qso:
                    try:
                        on_qso(msg)
                    except Exception as e:
                        print(f"[WSJTX] Erreur pounce (QSO): {e}")
            elif msg['type'] == 'decode':
                # Alerte DXCC/département manquant (voir recent_decodes()) —
                # le croisement avec le log se fait côté logx_http.py, ici on
                # ne fait qu'alimenter le cache des décodages entendus.
                calls = []
                try:
                    calls = record_decode(msg, _my_call(get_cfg() or {}))
                except Exception as e:
                    print(f"[WSJTX] Erreur decode: {e}")
                # Wait-and-Pounce (niveaux 3 et 4). Le rappel est enveloppé
                # SÉPARÉMENT : une erreur dans la logique d'appel automatique ne
                # doit pas emporter l'auto-log avec elle. Le thread d'écoute mort,
                # c'est TOUT le pont WSJT-X qui s'arrête jusqu'au redémarrage —
                # défaut déjà rencontré ici, on ne le refait pas.
                if on_decode and calls:
                    try:
                        on_decode(calls, msg)
                    except Exception as e:
                        print(f"[WSJTX] Erreur pounce: {e}")

    threading.Thread(target=_run, daemon=True).start()


def current_status():
    import time
    with _status_lock:
        s = dict(status)
    # « connecté » = un datagramme reçu il y a moins de 30 s
    s['connected'] = s['connected'] and (time.time() - s['last_seen'] < 30)
    return s
