# -*- coding: utf-8 -*-
"""Pilotage d'amplificateurs HF (natif, pyserial direct) — 3 protocoles
constructeurs vérifiés contre leur documentation officielle :

  - Elecraft KPA500/KPA1500 : ASCII '^XX;' (KPA500 Programmer's Reference).
  - Icom IC-PW2/PW-1 : CI-V étendu (IC-PW2 CI-V Reference Guide) — réutilise
    l'encodage/décodage de trame CI-V de logx_cat.py (même FE FE.../FD).
  - SPE/Expert 1.3K-FA/1.5K-FA/2K-FA : paquets binaires SYN+CNT+DATA+CHK,
    commandes = codes touche clavier (SPE Application Programmer's Guide).

Comme logx_cat.py : l'encodage/décodage de trame est séparé du
transport série pour être testable sans matériel (transport injecté).

Recherche préalable (protocoles disponibles/écartés — ACOM non documenté
officiellement, Ameritron/Yaesu VL-1000/Tokyo Hy-Power n'ont pas de protocole
propre, juste du band-data BCD ou un suivi passif du CAT radio) : voir mémoire
de session, pas dupliqué ici.
"""
import threading
import time

from logx_cat import (HAS_PYSERIAL, SerialPort, list_ports,
                              civ_build_frame, civ_parse_frame, civ_is_ok, CIV_END,
                              CIV_CTRL_ADDR)

_open_serial = SerialPort if HAS_PYSERIAL else None


# ═══════════════════════════════════════════════════════════════════════════
#  Elecraft KPA500 / KPA1500 — ASCII '^XX;'
# ═══════════════════════════════════════════════════════════════════════════

def _implied_decimal(s, pos):
    """'014' avec virgule implicite après la position `pos` (1-indexée) -> 1.4.
    None si `s` n'est pas purement numérique."""
    s = (s or '').strip()
    if not s.isdigit():
        return None
    return float(f'{s[:pos]}.{s[pos:]}')


def kpa_parse_ws(data):
    """'^WSppp sss;' -> ppp = puissance en W (entier), sss = SWR (virgule
    implicite après le 2e chiffre, ex. '014' -> 1.4). None si trame illisible."""
    parts = (data or '').strip().split()
    if len(parts) != 2 or not parts[0].isdigit():
        return None
    swr = _implied_decimal(parts[1], 2)
    return {'power_w': int(parts[0]), 'swr': swr}


def kpa_parse_vi(data):
    """'^VIvvv iii;' -> volts/ampères, virgule implicite après le 2e chiffre
    pour les deux valeurs."""
    parts = (data or '').strip().split()
    if len(parts) != 2:
        return None
    return {'volts': _implied_decimal(parts[0], 2), 'amps': _implied_decimal(parts[1], 2)}


class KpaAmp:
    """Elecraft KPA500/KPA1500 — voir KPA500 Programmer's Reference (Rev. A2).
    Le KPA1500 partage le même jeu de commandes ASCII (en plus d'un accès
    réseau TCP/UDP non couvert ici — port série uniquement pour l'instant)."""

    # '^BN00;'..'^BN10;' — 160m à 6m (valeurs hors de cette table ignorées par l'ampli)
    BAND_CODES = {'160': '00', '80': '01', '60': '02', '40': '03', '30': '04',
                  '20': '05', '17': '06', '15': '07', '12': '08', '10': '09', '6': '10'}

    def __init__(self, transport):
        self.t = transport

    def _cmd(self, name, data=''):
        self.t.write(f'^{name}{data};'.encode('ascii'))
        return self.t.read_until(b';', timeout=1.0).decode('ascii', errors='replace')

    def _get(self, name):
        """Envoie le GET (nom seul) et retourne les données de la réponse, ou
        None si l'ampli ne répond pas avec le préfixe attendu (toujours en
        MAJUSCULES côté KPA500, quelle que soit la casse envoyée)."""
        reply = self._cmd(name)
        prefix = f'^{name.upper()}'
        if not reply.upper().startswith(prefix):
            return None
        return reply[len(prefix):].rstrip(';')

    def get_status(self):
        """Puissance/SWR (^WS) + état standby/operate (^OS) + code défaut (^FL)
        + température (^TM) en un seul appel groupé — comme AsciiRadio.get_state()
        dans logx_cat.py."""
        ws_raw = self._get('WS')
        if ws_raw is None:
            return {'ok': False, 'error': 'Pas de réponse ^WS (KPA) — '
                                          'vérifie port/vitesse/câble'}
        ws = kpa_parse_ws(ws_raw) or {}
        out = {'ok': True, 'power_w': ws.get('power_w'), 'swr': ws.get('swr')}
        os_raw = self._get('OS')
        if os_raw is not None and os_raw.strip() in ('0', '1'):
            out['operate'] = os_raw.strip() == '1'
        fl_raw = self._get('FL')
        if fl_raw is not None and fl_raw.strip().isdigit():
            out['fault_code'] = int(fl_raw.strip())
        tm_raw = self._get('TM')
        if tm_raw is not None and tm_raw.strip().isdigit():
            out['temp_c'] = int(tm_raw.strip())
        return out

    def set_operate(self, on):
        reply = self._cmd('OS', '1' if on else '0')
        if not reply.upper().startswith('^OS'):
            return {'ok': False, 'error': 'Pas de réponse ^OS (KPA)'}
        return {'ok': True, 'operate': bool(on)}

    def clear_fault(self):
        self._cmd('FL', 'C')
        return {'ok': True}   # ^FLC; ne documente pas d'accusé dédié

    def set_band(self, band_mhz):
        code = self.BAND_CODES.get(str(band_mhz))
        if code is None:
            return {'ok': False, 'error': f"Bande inconnue pour l'ampli Elecraft : {band_mhz}"}
        reply = self._cmd('BN', code)
        return {'ok': reply.upper().startswith('^BN')}

    def power_off(self):
        self._cmd('ON', '0')
        return {'ok': True}   # pas de réponse garantie une fois éteint

    def power_on(self):
        """Commande BootLoader 'P' (caractère seul, sans ';', sans réponse) —
        distincte des commandes normales '^XX;', voir doc §BootLoader."""
        self.t.write(b'P')
        return {'ok': True}


# ═══════════════════════════════════════════════════════════════════════════
#  Icom IC-PW2 / PW-1 — CI-V étendu (réutilise le codec de logx_cat)
# ═══════════════════════════════════════════════════════════════════════════

ICOM_AMP_FAULT_LABELS = {0: 'Aucune protection', 1: 'Température', 2: 'ALC',
                         3: 'Puissance', 4: 'Bande', 5: 'Alimentation'}

# Commande 1A/03 : 1.8 à 50 MHz (voir doc "Frequency band data")
ICOM_AMP_BAND_CODES = {'1.8': 0x00, '3.5': 0x01, '7': 0x02, '10': 0x03, '14': 0x04,
                       '18': 0x05, '21': 0x06, '24': 0x07, '28': 0x08, '50': 0x09}


class IcomAmp:
    """Icom IC-PW2/PW-1 — CI-V étendu (commandes 15/18/1A/1C), voir IC-PW2
    CI-V Reference Guide. Adresse par défaut usine 0xAA."""

    def __init__(self, transport, addr=0xAA):
        self.t = transport
        self.addr = addr

    def _get(self, cmd, sub=None):
        frame = civ_build_frame(self.addr, cmd, sub)
        self.t.write(frame)
        raw = self.t.read_until(CIV_END, timeout=1.0)
        parsed = civ_parse_frame(raw)
        # Garde-fou de sens (même piège que CivRadio._query() dans
        # logx_cat.py, corrigé en même temps) : une vraie réponse ampli->PC
        # porte TO=E0(PC)/FROM=self.addr — sans ce contrôle, un écho de notre
        # propre requête serait pris à tort pour une réponse de l'ampli.
        # Garde-fou de COMMANDE (revue adversariale avant fusion) : sur un
        # bus CI-V partagé, vérifie aussi que cmd/sub correspondent à CE
        # qu'on vient d'envoyer — sinon la réponse à une AUTRE requête
        # (même TO/FROM par convention) serait mal interprétée.
        if (not parsed or parsed[0] != CIV_CTRL_ADDR or parsed[1] != self.addr
                or parsed[2] != cmd or (sub is not None and parsed[3] != sub)):
            return None
        return parsed

    def _set(self, cmd, sub=None, data=b''):
        frame = civ_build_frame(self.addr, cmd, sub, data)
        self.t.write(frame)
        raw = self.t.read_until(CIV_END, timeout=1.0)
        # civ_parse_frame() valide la structure complète (préambule/fin,
        # longueur) avant qu'on ne regarde le sens — l'indexation brute
        # raw[2]/raw[3] d'avant ne le faisait pas (trouvé en revue
        # adversariale : une suite d'octets bruyante de la bonne longueur
        # aurait pu passer). Un accusé Icom (FB/FA) n'échote PAS cmd/sub —
        # inutile de les revérifier ici, contrairement à _get().
        parsed = civ_parse_frame(raw)
        if not parsed or parsed[0] != CIV_CTRL_ADDR or parsed[1] != self.addr:
            return False
        return civ_is_ok(raw)

    @staticmethod
    def _raw2(data):
        """Décodage Icom classique des mesureurs (2 octets -> 0000-0255) :
        même principe que get_smeter() de logx_cat.py — valeur BRUTE,
        non linéaire, propre au constructeur (voir doc : Po/SWR ne sont PAS
        exprimés en unités directes, pas de conversion inventée ici)."""
        if not data or len(data) < 2:
            return None
        return int(f'{data[0]:02x}{data[1]:02x}')

    def get_status(self):
        """Puissance/SWR (brutes 0-255, cmd 15) + protection (1A/0C) + état
        AMP ON/OFF = équivalent standby/operate (1A/09) + statut TX (1C/00)."""
        po = self._get(0x15, 0x11)
        if not po:
            return {'ok': False, 'error': 'Pas de réponse CI-V — '
                                          'vérifie adresse/port/vitesse/câble'}
        out = {'ok': True, 'power_raw': self._raw2(po[4])}
        swr = self._get(0x15, 0x12)
        if swr:
            out['swr_raw'] = self._raw2(swr[4])
        fault = self._get(0x1A, 0x0C)
        if fault and fault[4]:
            code = fault[4][0]
            out['fault_code'] = code
            out['fault_label'] = ICOM_AMP_FAULT_LABELS.get(code, '?')
        amp_on = self._get(0x1A, 0x09)
        if amp_on and amp_on[4]:
            out['operate'] = bool(amp_on[4][0])
        ptt = self._get(0x1C, 0x00)
        if ptt and ptt[4]:
            out['tx'] = bool(ptt[4][0])
        return out

    def set_operate(self, on):
        """Commande 1A/09 (« AMP setting ») : 00=OFF/standby, 01=ON/operate —
        équivalent fonctionnel du STBY/OPER des autres marques."""
        ok = self._set(0x1A, 0x09, bytes([1 if on else 0]))
        if not ok:
            return {'ok': False, 'error': "Pas d'accusé CI-V (1A/09)"}
        return {'ok': True, 'operate': bool(on)}

    def clear_fault(self):
        return {'ok': self._set(0x1A, 0x0D)}

    def set_band(self, band_mhz, input_conn=0):
        code = ICOM_AMP_BAND_CODES.get(str(band_mhz))
        if code is None:
            return {'ok': False, 'error': f"Bande inconnue pour l'ampli Icom : {band_mhz}"}
        return {'ok': self._set(0x1A, 0x03, bytes([input_conn, code]))}

    def power_on(self):
        return {'ok': self._set(0x18, 0x01)}

    def power_off(self):
        return {'ok': self._set(0x18, 0x00)}


# ═══════════════════════════════════════════════════════════════════════════
#  SPE / Expert 1.3K-FA / 1.5K-FA / 2K-FA — paquets binaires SYN+CNT+DATA+CHK
# ═══════════════════════════════════════════════════════════════════════════

# Codes touche (§4 du Application Programmer's Guide) — équivalent des appuis
# clavier du panneau avant, PAS des SET directs (voir set_operate ci-dessous).
SPE_CMD = {
    'input': 0x01, 'band_down': 0x02, 'band_up': 0x03, 'antenna': 0x04,
    'l_down': 0x05, 'l_up': 0x06, 'c_down': 0x07, 'c_up': 0x08, 'tune': 0x09,
    'power_off': 0x0A, 'power': 0x0B, 'display': 0x0C, 'operate': 0x0D,
    'cat': 0x0E, 'left': 0x0F, 'right': 0x10, 'set': 0x11,
    'backlight_on': 0x82, 'backlight_off': 0x83, 'status': 0x90,
}

# §4 : bandes 160m -> 4m dans l'ordre croissant des codes 00-11 (2K-FA
# s'arrête à 10=6m, 1.3K-FA va jusqu'à 11=4m).
SPE_BAND_ORDER = ['160', '80', '60', '40', '30', '20', '17', '15', '12', '10', '6', '4']

SPE_WARNING_LABELS = {
    'M': 'Alarme ampli', 'A': 'Aucune antenne sélectionnée', 'S': 'SWR antenne',
    'B': 'Bande invalide', 'P': 'Puissance dépassée', 'O': 'Surchauffe',
    'Y': 'ATU indisponible', 'W': 'Accord sans puissance', 'K': 'ATU by-passé',
    'R': 'Interrupteur maintenu à distance', 'T': 'Combineur en surchauffe',
    'C': 'Défaut combineur', 'N': '',
}
SPE_ALARM_LABELS = {
    'S': 'SWR hors limites', 'A': 'Protection ampli', 'D': 'Surpilotage entrée',
    'H': 'Surchauffe excessive', 'C': 'Défaut combineur', 'N': '',
}


def spe_build_packet(data_bytes):
    """SYN(0x55)×3 + CNT + DATA + CHK (somme modulo-256 des octets DATA) —
    voir Application Programmer's Guide §3."""
    chk = sum(data_bytes) % 256
    return bytes([0x55, 0x55, 0x55, len(data_bytes)]) + bytes(data_bytes) + bytes([chk])


def spe_parse_status(raw):
    """Réponse à la commande STATUS (0x90) : SYN(0xAA)×3 + CNT + 67 caractères
    ASCII (19 champs séparés par des virgules, §5) + CHK(2 octets) + CR LF.
    None si trame trop courte ou champs manquants — jamais de valeur devinée."""
    if len(raw) < 5 or raw[0:3] != b'\xAA\xAA\xAA':
        return None
    cnt = raw[3]
    data = raw[4:4 + cnt]
    if len(data) < cnt:
        return None
    fields = [x.strip() for x in data.decode('ascii', errors='replace').split(',')]
    if len(fields) < 19:
        return None

    def _f(x):
        try:
            return float(x)
        except ValueError:
            return None

    warning, alarm = fields[17], fields[18]
    return {
        'ok': True, 'id': fields[0], 'operate': fields[1] == 'O', 'tx': fields[2] == 'T',
        'input': fields[4], 'band': fields[5], 'power_level': fields[8],
        'power_w': _f(fields[9]), 'swr_atu': _f(fields[10]), 'swr_ant': _f(fields[11]),
        'v_pa': _f(fields[12]), 'i_pa': _f(fields[13]),
        'temp_upr': _f(fields[14]), 'temp_lwr': _f(fields[15]), 'temp_cmb': _f(fields[16]),
        'warning': warning, 'warning_label': SPE_WARNING_LABELS.get(warning, ''),
        'alarm': alarm, 'alarm_label': SPE_ALARM_LABELS.get(alarm, ''),
    }


class SpeAmp:
    """SPE/Expert 1.3K-FA/1.5K-FA/2K-FA — voir Application Programmer's Guide
    (spetlc.com). Les commandes sont des codes touche clavier (comme un appui
    physique) : OPERATE BASCULE standby<->operate plutôt que de FIXER un état,
    d'où la relecture du statut avant/après dans set_operate()."""

    def __init__(self, transport):
        self.t = transport

    def _send_keys(self, *names):
        self.t.write(spe_build_packet([SPE_CMD[n] for n in names]))

    def get_status(self):
        self._send_keys('status')
        raw = self.t.read_until(b'\n', timeout=1.0)
        parsed = spe_parse_status(raw)
        if not parsed:
            return {'ok': False, 'error': 'Pas de réponse STATUS (SPE) — '
                                          'vérifie port/vitesse/câble'}
        return parsed

    def set_operate(self, on):
        st = self.get_status()
        if not st.get('ok'):
            return st
        if st['operate'] == bool(on):
            return st
        self._send_keys('operate')
        self.t.read_until(b'\n', timeout=0.3)   # vide l'ACK du keystroke (pas de CR LF)
        time.sleep(0.2)
        return self.get_status()

    def power_off(self):
        self._send_keys('power_off')
        return {'ok': True}

    def set_band(self, band_mhz):
        """Pas de commande d'accès direct à une bande (§4) — seulement
        BAND+/BAND- (pas à pas, comme au panneau avant). On lit la bande
        actuelle puis on envoie le nombre de pas nécessaires dans le bon sens,
        d'après l'ordre croissant documenté des codes de bande (§5)."""
        band_mhz = str(band_mhz)
        if band_mhz not in SPE_BAND_ORDER:
            return {'ok': False, 'error': f"Bande inconnue pour l'ampli SPE : {band_mhz}"}
        st = self.get_status()
        if not st.get('ok'):
            return st
        try:
            current_idx = int(st['band'])
        except (TypeError, ValueError):
            return {'ok': False, 'error': 'Bande actuelle illisible (SPE)'}
        target_idx = SPE_BAND_ORDER.index(band_mhz)
        delta = target_idx - current_idx
        key = 'band_up' if delta > 0 else 'band_down'
        for _ in range(abs(delta)):
            self._send_keys(key)
            self.t.read_until(b'\n', timeout=0.3)
            time.sleep(0.15)
        return self.get_status()


# ═══════════════════════════════════════════════════════════════════════════
#  Réglages + connexion persistante (même schéma que logx_cat.py)
# ═══════════════════════════════════════════════════════════════════════════

AMP_DEFAULT_BAUD = {'elecraft': 38400, 'icom': 19200, 'spe': 9600}


def amp_settings(cfg):
    """Réglages du pilotage d'ampli depuis la config CLIENT — absence des
    champs amp_* -> enabled=False, aucun effet si le chantier n'est pas
    configuré (comme cat_settings())."""
    cfg = cfg or {}
    brand = (cfg.get('amp_brand') or '').strip().lower()
    try:
        baudrate = int(cfg.get('amp_baudrate') or 0)
    except (TypeError, ValueError):
        baudrate = 0
    civ_addr = 0xAA
    try:
        if cfg.get('amp_civ_addr'):
            civ_addr = int(str(cfg['amp_civ_addr']), 16)
    except (TypeError, ValueError):
        civ_addr = 0xAA
    return {
        'enabled': bool(cfg.get('amp_enabled')),
        'brand': brand,
        'port': (cfg.get('amp_port') or '').strip(),
        'baudrate': baudrate or AMP_DEFAULT_BAUD.get(brand, 9600),
        'civ_addr': civ_addr,
    }


_persistent = {}
_persistent_lock = threading.Lock()
# Sérialise les ÉCHANGES série complets (write+read) avec l'ampli : _persistent_lock
# ne protège que l'obtention du driver, pas les commandes elles-mêmes. Le serveur
# HTTP étant multi-thread, un polling get_status pouvait s'entrelacer avec un
# set_band/set_operate — deux write() concurrents sur le même port, chaque read
# lisant la réponse de l'autre. (Même principe que _lock dans logx_rotor.py.)
_io_lock = threading.Lock()


def _make_driver(brand, transport, civ_addr):
    if brand == 'elecraft':
        return KpaAmp(transport)
    if brand == 'icom':
        return IcomAmp(transport, civ_addr)
    if brand == 'spe':
        return SpeAmp(transport)
    return None


def _ensure_connected(settings):
    """Retourne (driver, erreur_ou_None). Ouvre le port au premier appel,
    réutilise la connexion tant que la config ne change pas — même mécanisme
    que logx_cat._ensure_connected()."""
    key = (settings['port'], settings['brand'], settings['baudrate'], settings['civ_addr'])
    with _persistent_lock:
        entry = _persistent.get('default')
        if entry and entry['key'] == key:
            return entry['driver'], None
        if entry:
            entry['transport'].close()
            _persistent.pop('default', None)
        if not settings['port']:
            return None, 'Port série non configuré'
        if not settings['brand']:
            return None, "Marque d'ampli non configurée"
        try:
            transport = _open_serial(settings['port'], baudrate=settings['baudrate'])
        except Exception as e:
            return None, f"Impossible d'ouvrir {settings['port']} : {e}"
        driver = _make_driver(settings['brand'], transport, settings['civ_addr'])
        if driver is None:
            transport.close()
            return None, f"Marque d'ampli inconnue : {settings['brand']}"
        _persistent['default'] = {'key': key, 'driver': driver, 'transport': transport}
        return driver, None


def disconnect_persistent():
    with _persistent_lock:
        entry = _persistent.pop('default', None)
    if entry:
        entry['transport'].close()


def get_state(cfg):
    """État courant de l'ampli — forme unifiée {'enabled','ok','error'?, ...}
    quelle que soit la marque (les champs au-delà de ok/enabled varient selon
    ce que le protocole du constructeur expose réellement)."""
    settings = amp_settings(cfg)
    if not settings['enabled']:
        return {'enabled': False}
    driver, err = _ensure_connected(settings)
    if err:
        return {'ok': False, 'error': err, 'enabled': True}
    try:
        with _io_lock:
            st = driver.get_status()
        st['enabled'] = True
        return st
    except Exception as e:
        return {'ok': False, 'error': f'Ampli injoignable ({e})', 'enabled': True}


def set_operate(cfg, on):
    """Bascule standby/operate — même signature que logx_cat.set_ptt,
    pour un futur bouton CONFIG/LOGBOOK 'ampli en émission'."""
    settings = amp_settings(cfg)
    if not settings['enabled']:
        return {'ok': False, 'error': 'Pilotage ampli désactivé (CONFIG)'}
    driver, err = _ensure_connected(settings)
    if err:
        return {'ok': False, 'error': err}
    try:
        with _io_lock:
            return driver.set_operate(bool(on))
    except Exception as e:
        return {'ok': False, 'error': f'Ampli injoignable ({e})'}


def set_band(cfg, band_mhz):
    """QSY de bande de l'ampli — même esprit que logx_cat.set_freq."""
    settings = amp_settings(cfg)
    if not settings['enabled']:
        return {'ok': False, 'error': 'Pilotage ampli désactivé (CONFIG)'}
    driver, err = _ensure_connected(settings)
    if err:
        return {'ok': False, 'error': err}
    try:
        with _io_lock:
            return driver.set_band(band_mhz)
    except Exception as e:
        return {'ok': False, 'error': f'Ampli injoignable ({e})'}


def clear_fault(cfg):
    settings = amp_settings(cfg)
    if not settings['enabled']:
        return {'ok': False, 'error': 'Pilotage ampli désactivé (CONFIG)'}
    driver, err = _ensure_connected(settings)
    if err:
        return {'ok': False, 'error': err}
    if not hasattr(driver, 'clear_fault'):
        return {'ok': False, 'error': "Pas d'acquittement de défaut documenté pour cet ampli"}
    try:
        with _io_lock:
            return driver.clear_fault()
    except Exception as e:
        return {'ok': False, 'error': f'Ampli injoignable ({e})'}


def power_toggle(cfg, on):
    settings = amp_settings(cfg)
    if not settings['enabled']:
        return {'ok': False, 'error': 'Pilotage ampli désactivé (CONFIG)'}
    driver, err = _ensure_connected(settings)
    if err:
        return {'ok': False, 'error': err}
    try:
        if on:
            if not hasattr(driver, 'power_on'):
                return {'ok': False, 'error': "Mise sous tension à distance non "
                                              "disponible pour cet ampli"}
            with _io_lock:
                return driver.power_on()
        with _io_lock:
            return driver.power_off()
    except Exception as e:
        return {'ok': False, 'error': f'Ampli injoignable ({e})'}


def test_connection(brand, port, baudrate, civ_addr=None):
    """Test ÉPHÉMÈRE (bouton CONFIG) : ouvre, interroge le statut, ferme — ne
    touche jamais à la connexion persistante utilisée par le polling logbook."""
    if not port:
        return {'ok': False, 'error': 'Port série manquant'}
    brand = (brand or '').strip().lower()
    if not brand:
        return {'ok': False, 'error': "Marque d'ampli manquante"}
    try:
        transport = _open_serial(port, baudrate=baudrate or AMP_DEFAULT_BAUD.get(brand, 9600))
    except Exception as e:
        return {'ok': False, 'error': f"Impossible d'ouvrir {port} : {e}"}
    try:
        driver = _make_driver(brand, transport, civ_addr or 0xAA)
        if driver is None:
            return {'ok': False, 'error': f"Marque d'ampli inconnue : {brand}"}
        st = driver.get_status()
        if not st.get('ok'):
            return {'ok': False, 'error': st.get('error', 'Pas de réponse — '
                                                          'vérifie port/vitesse/câble')}
        return {'ok': True, 'status': st}
    except Exception as e:
        return {'ok': False, 'error': f'Ampli injoignable ({e})'}
    finally:
        transport.close()
