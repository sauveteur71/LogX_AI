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
    """Ports série disponibles : [{'device': 'COM3', 'description': '...'}].
    Liste vide si pyserial est absent ou si aucun port n'est détecté —
    jamais d'exception (appelé depuis l'UI de configuration)."""
    if not HAS_PYSERIAL:
        return []
    try:
        return [{'device': p.device, 'description': p.description or ''}
                for p in _list_ports.comports()]
    except Exception:
        return []


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
    # Les sous-commandes connues (14/15/1A/1C/19/25/26) ont un octet Sc ;
    # les autres (00/01/03/04/05/06/0F) n'en ont pas.
    has_sub = cmd in (0x14, 0x15, 0x19, 0x1A, 0x1C, 0x25, 0x26)
    if has_sub and len(rest) >= 2:
        return addr_dest, addr_src, cmd, rest[1], rest[2:]
    return addr_dest, addr_src, cmd, None, rest[1:]


def civ_is_ok(frame):
    """FB FD = accusé positif, FA FD = échec (utilisé pour les commandes SET
    sans sous-commande, ex. 0F split)."""
    return frame[-2:] == b'\xFB\xFD' if len(frame) >= 2 else False


class CivRadio:
    """Pilote Icom CI-V — encode les requêtes, décode les réponses. Ne fait
    AUCUNE E/S : `transport` est injecté (SerialPort réel ou double de test)."""

    def __init__(self, transport, addr_radio):
        self.t = transport
        self.addr = addr_radio

    def _query(self, cmd, sub=None, data=b'', read_reply=True):
        frame = civ_build_frame(self.addr, cmd, sub, data)
        self.t.write(frame)
        if not read_reply:
            return None
        raw = self.t.read_until(CIV_END, timeout=1.0)
        return civ_parse_frame(raw)

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

    def set_mode(self, mode):
        code = CIV_MODES.get(mode.upper())
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


# ═══════════════════════════════════════════════════════════════════════════
#  ASCII générique (Yaesu / Kenwood / Elecraft) — commandes 2 lettres + ';'
# ═══════════════════════════════════════════════════════════════════════════

# Tables de mode par marque (les codes diffèrent légèrement — vérifié doc).
ASCII_MODES = {
    'yaesu':    {'1': 'LSB', '2': 'USB', '3': 'CW', '4': 'FM', '5': 'AM',
                 '6': 'RTTY-LSB', '7': 'CW-R', '9': 'RTTY-USB'},
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
SPLIT_STYLE = {
    'FT-991A': 'ft23', 'FTDX10': 'ft23', 'FT-891': 'ft01',
    'FTDX101D': 'ft23', 'FTDX101MP': 'ft23',
    'TS-2000': 'fr_ft', 'TS-590S': 'fr_ft', 'TS-890S': 'fr_ft', 'TS-990S': 'fr_ft',
    'K3': 'ft01', 'K3S': 'ft01', 'KX3': 'ft01', 'KX2': 'ft01', 'K4': 'ft01',
}

# Codes ID -> modèle (Yaesu/Kenwood ; Elecraft répond toujours 017, non listé ici)
ASCII_ID_TABLE = {
    '135': 'FT-891', '570': 'FT-991', '670': 'FT-991A',
    '761': 'FTDX10', '681': 'FTDX101D', '682': 'FTDX101MP',
    '019': 'TS-2000', '021': 'TS-590S', '023': 'TS-590SG',
    '022': 'TS-990S', '024': 'TS-890S',
}

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
    'yaesu':    (2, 9, 18, 19),   # mem(2) freq(9) offset(5) rit(1) xit(1) mode
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


def ascii_encode_freq_cmd(vfo_cmd, freq_hz):
    """FAxxxxxxxxxxx; — 11 chiffres, zéros de tête (Kenwood/Elecraft/Yaesu
    récents). Les modèles Yaesu plus anciens acceptent aussi ce format à
    11 chiffres (au pire des zéros de tête surnuméraires sans effet)."""
    return f'{vfo_cmd}{int(freq_hz):011d};'


def ascii_encode_mode_cmd(mode, brand, vfo_suffix=''):
    code = ASCII_MODES.get(brand + '_rev', {}).get(mode.upper())
    if code is None:
        return None
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
        self.t.write(cmd.encode('ascii'))
        if not read_reply:
            return None
        return self.t.read_until(b';', timeout=1.0).decode('ascii', errors='replace')

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
        reply = self._cmd(ascii_encode_freq_cmd('FA', freq_hz), read_reply=False)
        return {'ok': True}

    def set_mode(self, mode):
        cmd = ascii_encode_mode_cmd(mode, self.brand)
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
    CW_CHUNK = 24
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
        self._ser = _pyserial.Serial(device, baudrate=baudrate, timeout=timeout,
                                     bytesize=8, parity='N', stopbits=1)

    def write(self, data):
        with self._lock:
            self._ser.reset_input_buffer()
            self._ser.write(data)

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

# Point d'injection pour les tests : remplacer par un double qui ne touche
# pas un vrai port série (voir tests/test_cat.py). Par défaut, le vrai
# constructeur pyserial.
_open_serial = SerialPort if HAS_PYSERIAL else None


def cat_settings(cfg):
    """Réglages du pilotage natif depuis la config CLIENT. `mode` distingue
    'native' (ce module) de 'rigctld' (logx_rig, inchangé) — une
    config existante sans les champs cat_* se comporte comme avant
    (cat_enabled absent -> enabled=False, aucun effet sur le mode rigctld)."""
    cfg = cfg or {}
    brand = (cfg.get('cat_brand') or '').strip().lower()
    try:
        baudrate = int(cfg.get('cat_baudrate') or 0)
    except (TypeError, ValueError):
        baudrate = 0
    return {
        'enabled': bool(cfg.get('cat_enabled')),
        'mode': cfg.get('cat_mode') or 'native',
        'brand': brand,
        'model': (cfg.get('cat_model') or '').strip() or None,
        'port': (cfg.get('cat_port') or '').strip(),
        'baudrate': baudrate or CAT_DEFAULT_BAUD.get(brand, 19200),
    }


# Connexion persistante unique (poste principal) — rouverte automatiquement
# si la configuration (port/marque/modèle/vitesse) change entre deux appels.
_persistent = {}
_persistent_lock = threading.Lock()


def _ensure_connected(settings):
    """Retourne (driver, erreur_ou_None). Ouvre le port au premier appel,
    réutilise la connexion tant que la config ne change pas."""
    key = (settings['port'], settings['brand'], settings['model'], settings['baudrate'])
    with _persistent_lock:
        entry = _persistent.get('default')
        if entry and entry['key'] == key:
            return entry['driver'], None
        if entry:
            entry['transport'].close()
            _persistent.pop('default', None)
        if not settings['port']:
            return None, 'Port série non configuré'
        try:
            transport = _open_serial(settings['port'], baudrate=settings['baudrate'])
        except Exception as e:
            return None, f"Impossible d'ouvrir {settings['port']} : {e}"
        if settings['brand'] in ('icom', 'xiegu'):
            addr = CIV_ADDRESSES.get(settings['model'], 0x94)
            driver = CivRadio(transport, addr)
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
            driver.set_mode(mode)
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


def test_connection(brand, model, port, baudrate):
    """Test ÉPHÉMÈRE (bouton CONFIG) : ouvre, interroge, ferme — ne touche
    jamais à la connexion persistante utilisée par le polling logbook."""
    if not port:
        return {'ok': False, 'error': 'Port série manquant'}
    brand = (brand or '').strip().lower()
    try:
        transport = _open_serial(port, baudrate=baudrate or CAT_DEFAULT_BAUD.get(brand, 19200))
    except Exception as e:
        return {'ok': False, 'error': f"Impossible d'ouvrir {port} : {e}"}
    try:
        if brand in ('icom', 'xiegu'):
            addr = CIV_ADDRESSES.get(model, 0x94)
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
        transport.write(b'ID;')
        reply = transport.read_until(b';', timeout=0.8).decode('ascii', errors='replace')
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
        try:
            transport.write(civ_build_frame(addr, 0x19, sub=0x00))
            raw = transport.read_until(CIV_END, timeout=0.5)
        except Exception:
            continue
        parsed = civ_parse_frame(raw)
        if parsed:
            return {'ok': True, 'protocol': 'civ', 'brand': 'icom', 'model': name,
                    'addr': addr, 'certain': False,
                    'note': "Adresse CI-V par défaut détectée — peut avoir été "
                            "changée manuellement sur la radio"}

    return {'ok': False, 'error': 'Aucune radio détectée automatiquement — '
                                  'choisis ta marque/modèle manuellement'}
