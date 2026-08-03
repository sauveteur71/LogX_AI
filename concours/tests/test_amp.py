# -*- coding: utf-8 -*-
"""Tests du pilotage d'amplificateurs HF (logx_amp) : logique de
trame pure (KPA ASCII, CI-V étendu, paquets SPE) + boucle complète contre des
amplis FICTIFS en mémoire (aucun port série réel requis)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_amp as amp
import logx_cat as cat


# ─── DOUBLES DE TEST : amplis fictifs en mémoire ─────────────────────────────

class FakeKpaAmp:
    """Simule un KPA500/KPA1500 : répond aux commandes ASCII '^XX;'."""

    def __init__(self, power_w=100, swr3='010', operate=True, fault=0, temp=25, band='05'):
        self.power_w = power_w
        self.swr3 = swr3   # 3 chiffres, virgule implicite après le 2e (ex. '014' -> 1.4)
        self.operate = operate
        self.fault = fault
        self.temp = temp
        self.band = band
        self._pending = b''

    def write(self, data):
        cmd = data.decode('ascii')
        if cmd == '^WS;':
            self._pending = f'^WS{self.power_w:03d} {self.swr3};'.encode()
        elif cmd == '^OS;':
            self._pending = f'^OS{1 if self.operate else 0};'.encode()
        elif cmd.startswith('^OS'):
            self.operate = cmd[3] == '1'
            self._pending = f'^OS{1 if self.operate else 0};'.encode()
        elif cmd == '^FL;':
            self._pending = f'^FL{self.fault:02d};'.encode()
        elif cmd == '^FLC;':
            self.fault = 0
            self._pending = b''
        elif cmd == '^TM;':
            self._pending = f'^TM{self.temp:03d};'.encode()
        elif cmd.startswith('^BN'):
            self.band = cmd[3:5]
            self._pending = f'^BN{self.band};'.encode()
        elif cmd == '^ON0;':
            self._pending = b''
        else:
            self._pending = b''

    def read_until(self, terminator, timeout=1.0):
        r, self._pending = self._pending, b''
        return r

    def close(self):
        pass


def _encode_raw2(v):
    """Inverse de IcomAmp._raw2 : encode un entier 0-0255 sur 2 octets selon
    la convention Icom (chaque octet = 2 chiffres décimaux lus en hexa)."""
    s = f'{v:04d}'
    return bytes([int(s[0:2], 16), int(s[2:4], 16)])


class FakeIcomAmp:
    """Simule un IC-PW2/PW-1 : répond aux trames CI-V étendues (15/1A/1C/18)."""

    def __init__(self, addr=0xAA, power_raw=161, swr_raw=40, fault=0, operate=True, tx=False):
        self.addr = addr
        self.power_raw = power_raw
        self.swr_raw = swr_raw
        self.fault = fault
        self.operate = operate
        self.tx = tx
        self._pending = b''

    def _ok_reply(self):
        return bytes([0xFE, 0xFE, 0xE0, self.addr, 0xFB, 0xFD])

    def _data_reply(self, cmd, sub, data):
        body = bytes([cmd]) + (bytes([sub]) if sub is not None else b'') + bytes(data)
        return bytes([0xFE, 0xFE, 0xE0, self.addr]) + body + b'\xFD'

    def write(self, data):
        parsed = cat.civ_parse_frame(data)
        if not parsed or parsed[0] != self.addr:
            self._pending = b''
            return
        _, _, cmd, sub, payload = parsed
        if cmd == 0x15 and sub == 0x11:
            self._pending = self._data_reply(0x15, 0x11, _encode_raw2(self.power_raw))
        elif cmd == 0x15 and sub == 0x12:
            self._pending = self._data_reply(0x15, 0x12, _encode_raw2(self.swr_raw))
        elif cmd == 0x1A and sub == 0x0C:
            self._pending = self._data_reply(0x1A, 0x0C, bytes([self.fault]))
        elif cmd == 0x1A and sub == 0x0D:
            self.fault = 0
            self._pending = self._ok_reply()
        elif cmd == 0x1A and sub == 0x09:
            if payload:
                self.operate = bool(payload[0])
                self._pending = self._ok_reply()
            else:
                self._pending = self._data_reply(0x1A, 0x09, bytes([1 if self.operate else 0]))
        elif cmd == 0x1A and sub == 0x03:
            self._pending = self._ok_reply()
        elif cmd == 0x1C and sub == 0x00:
            self._pending = self._data_reply(0x1C, 0x00, bytes([1 if self.tx else 0]))
        elif cmd == 0x18:
            self._pending = self._ok_reply()
        else:
            self._pending = b''

    def read_until(self, terminator, timeout=1.0):
        r, self._pending = self._pending, b''
        return r

    def close(self):
        pass


class FakeSpeAmp:
    """Simule un SPE/Expert 1.3K/1.5K/2K-FA : répond aux paquets binaires
    SYN+CNT+DATA+CHK. OPERATE bascule l'état (comportement documenté : codes
    touche = appui clavier, pas un SET direct)."""

    def __init__(self, band_idx=5, operate=False, power_w=0):
        self.band_idx = band_idx
        self.operate = operate
        self.power_w = power_w
        self._pending = b''

    def write(self, data):
        if len(data) < 5 or data[0:3] != b'\x55\x55\x55':
            self._pending = b''
            return
        cnt = data[3]
        cmd_bytes = data[4:4 + cnt]
        if not cmd_bytes:
            self._pending = b''
            return
        code = cmd_bytes[0]
        if code == amp.SPE_CMD['status']:
            self._pending = self._build_status()
        elif code == amp.SPE_CMD['operate']:
            self.operate = not self.operate
            self._pending = b''
        elif code == amp.SPE_CMD['band_up']:
            self.band_idx += 1
            self._pending = b''
        elif code == amp.SPE_CMD['band_down']:
            self.band_idx -= 1
            self._pending = b''
        else:
            self._pending = b''

    def _build_status(self):
        fields = ['20K', 'O' if self.operate else 'S', 'R', 'x', '1',
                  f'{self.band_idx:02d}', '1a', '0r', 'L',
                  f'{int(self.power_w):04d}', ' 1.20', ' 1.10', '48.0', '20.0',
                  '033', '000', '000', 'N', 'N']
        s = ','.join(fields)
        data = s.encode('ascii')
        cnt = len(data)
        chk = sum(data)
        return (bytes([0xAA, 0xAA, 0xAA, cnt]) + data
                + bytes([chk & 0xFF, (chk >> 8) & 0xFF]) + b'\r\n')

    def read_until(self, terminator, timeout=1.0):
        r, self._pending = self._pending, b''
        return r

    def close(self):
        pass


class _FakeFactory:
    """Remplace amp._open_serial : retourne toujours le même faux transport,
    ignore port/baudrate (même esprit que test_cat.py)."""

    def __init__(self, transport):
        self.transport = transport
        self.calls = 0

    def __call__(self, port, baudrate=19200):
        self.calls += 1
        return self.transport


def _with_fake_serial(transport, fn):
    original = amp._open_serial
    factory = _FakeFactory(transport)
    amp._open_serial = factory
    try:
        return fn(factory)
    finally:
        amp._open_serial = original
        amp.disconnect_persistent()


# ─── Logique de trame pure ───────────────────────────────────────────────────

def test_kpa_parse_ws():
    assert amp.kpa_parse_ws('204 014') == {'power_w': 204, 'swr': 1.4}


def test_kpa_parse_ws_illisible():
    assert amp.kpa_parse_ws('abc') is None
    assert amp.kpa_parse_ws('') is None


def test_kpa_parse_vi():
    assert amp.kpa_parse_vi('480 200') == {'volts': 48.0, 'amps': 20.0}


def test_spe_build_packet_exemple_doc():
    # Exemple du guide : passage en OPERATE (0x0D), checksum = l'octet lui-même
    assert amp.spe_build_packet([0x0D]) == b'\x55\x55\x55\x01\x0d\x0d'


def test_spe_parse_status_roundtrip():
    fake = FakeSpeAmp(band_idx=5, operate=True, power_w=500)
    raw = fake._build_status()
    parsed = amp.spe_parse_status(raw)
    assert parsed['ok'] and parsed['operate'] is True and parsed['band'] == '05'
    assert parsed['power_w'] == 500.0
    assert parsed['warning_label'] == '' and parsed['alarm_label'] == ''


def test_spe_parse_status_trame_courte():
    assert amp.spe_parse_status(b'\xAA\xAA') is None


# ─── KpaAmp (boucle complète, ampli fictif) ──────────────────────────────────

def test_kpa_get_status():
    driver = amp.KpaAmp(FakeKpaAmp(power_w=204, swr3='014', operate=True, fault=0, temp=32))
    st = driver.get_status()
    assert st == {'ok': True, 'power_w': 204, 'swr': 1.4, 'operate': True,
                  'fault_code': 0, 'temp_c': 32}


def test_kpa_set_operate():
    driver = amp.KpaAmp(FakeKpaAmp(operate=False))
    r = driver.set_operate(True)
    assert r == {'ok': True, 'operate': True}
    assert driver.get_status()['operate'] is True


def test_kpa_set_band_code_inconnu():
    driver = amp.KpaAmp(FakeKpaAmp())
    r = driver.set_band('999')
    assert not r['ok']


def test_kpa_set_band():
    driver = amp.KpaAmp(FakeKpaAmp())
    r = driver.set_band('40')
    assert r['ok']


# ─── IcomAmp (boucle complète, ampli fictif) ─────────────────────────────────

def test_icom_get_status():
    driver = amp.IcomAmp(FakeIcomAmp(addr=0xAA, power_raw=161, swr_raw=40, fault=0, operate=True))
    st = driver.get_status()
    assert st['ok'] and st['power_raw'] == 161 and st['swr_raw'] == 40
    assert st['operate'] is True and st['fault_code'] == 0
    assert st['fault_label'] == 'Aucune protection'


def test_icom_fault_label():
    driver = amp.IcomAmp(FakeIcomAmp(fault=3))
    st = driver.get_status()
    assert st['fault_label'] == 'Puissance'


def test_icom_set_operate():
    driver = amp.IcomAmp(FakeIcomAmp(operate=False))
    r = driver.set_operate(True)
    assert r == {'ok': True, 'operate': True}


def test_icom_set_band_code_inconnu():
    driver = amp.IcomAmp(FakeIcomAmp())
    r = driver.set_band('999')
    assert not r['ok']


def test_icom_power_on_off():
    driver = amp.IcomAmp(FakeIcomAmp())
    assert driver.power_on() == {'ok': True}
    assert driver.power_off() == {'ok': True}


# ─── Garde-fou de sens de trame CI-V (même bug/correctif que logx_cat.py,
#     audit 03/08/2026) : un écho de notre propre requête ne doit jamais
#     être pris pour une réponse de l'ampli ────────────────────────────────

class EchoTransport:
    def __init__(self):
        self._pending = b''

    def write(self, data):
        self._pending = bytes(data)

    def read_until(self, terminator, timeout=1.0):
        r, self._pending = self._pending, b''
        return r

    def close(self):
        pass


def test_icom_amp_echo_boucle_ne_donne_jamais_ok():
    driver = amp.IcomAmp(EchoTransport(), addr=0xAA)
    st = driver.get_status()
    assert st['ok'] is False
    assert driver.set_operate(True)['ok'] is False


class _FixedReply:
    """Renvoie toujours la même trame brute, quelle que soit la requête —
    pour construire des cas adversariaux précis (contrairement à
    EchoTransport qui renvoie la requête elle-même)."""

    def __init__(self, raw):
        self._raw = raw

    def write(self, data):
        pass

    def read_until(self, terminator, timeout=1.0):
        return self._raw

    def close(self):
        pass


def test_icom_amp_set_rejette_accuse_bien_forme_mais_mauvais_sens():
    """🚨 Trouvé en revue adversariale : le test d'écho ci-dessus ne prouve
    RIEN sur le garde-fou de _set() (une requête échoée ne se termine
    jamais par hasard en FB/FD). Ici la trame est BIEN FORMÉE et se termine
    par un accusé positif valide (FB FD), mais TO/FROM sont inversés
    (comme si l'ampli se répondait dans le mauvais sens) — le garde-fou
    doit la rejeter malgré l'accusé valide."""
    raw = bytes([0xFE, 0xFE, 0xAA, 0xE0, 0xFB, 0xFD])   # TO=0xAA(nous), FROM=0xE0 : inversé
    driver = amp.IcomAmp(_FixedReply(raw), addr=0xAA)
    assert driver.set_operate(True)['ok'] is False


def test_icom_amp_set_rejette_accuse_sans_vrai_preambule():
    """🚨 Trouvé en revue adversariale : _set() validait avant par indexation
    brute (raw[2]/raw[3]) sans jamais vérifier le préambule FE FE ni le
    terminateur FD — une suite d'octets qui aurait par coïncidence les bons
    octets d'adresse aux bonnes positions ET se terminant en FB FD passait
    donc comme un accusé valide, sans qu'aucune vraie trame CI-V n'existe."""
    raw = bytes([0x00, 0x00, 0xE0, 0xAA, 0xFB, 0xFD])   # pas de préambule FE FE
    driver = amp.IcomAmp(_FixedReply(raw), addr=0xAA)
    assert driver.set_operate(True)['ok'] is False


# ─── SpeAmp (boucle complète, ampli fictif) ──────────────────────────────────

def test_spe_get_status():
    driver = amp.SpeAmp(FakeSpeAmp(band_idx=5, operate=False, power_w=0))
    st = driver.get_status()
    assert st['ok'] and st['operate'] is False and st['band'] == '05'


def test_spe_set_operate_bascule_uniquement_si_necessaire():
    fake = FakeSpeAmp(operate=False)
    driver = amp.SpeAmp(fake)
    r = driver.set_operate(True)
    assert r['operate'] is True
    # Déjà dans l'état demandé -> pas de nouveau toggle
    r2 = driver.set_operate(True)
    assert r2['operate'] is True


def test_spe_set_band_pas_a_pas():
    fake = FakeSpeAmp(band_idx=5)   # '20' (index 5 dans SPE_BAND_ORDER)
    driver = amp.SpeAmp(fake)
    r = driver.set_band('40')       # index 3 -> 2 pas vers le bas
    assert r['ok'] and r['band'] == '03'


def test_spe_set_band_inconnu():
    driver = amp.SpeAmp(FakeSpeAmp())
    r = driver.set_band('999')
    assert not r['ok']


# ─── Réglages ─────────────────────────────────────────────────────────────────

def test_amp_settings_defaut():
    s = amp.amp_settings({})
    assert s == {'enabled': False, 'brand': '', 'port': '', 'baudrate': 9600, 'civ_addr': 0xAA}


def test_amp_settings_personnalises():
    s = amp.amp_settings({'amp_enabled': True, 'amp_brand': 'ICOM', 'amp_port': 'COM9',
                          'amp_baudrate': '19200', 'amp_civ_addr': 'AA'})
    assert s == {'enabled': True, 'brand': 'icom', 'port': 'COM9',
                'baudrate': 19200, 'civ_addr': 0xAA}


def test_amp_settings_baudrate_par_defaut_selon_marque():
    assert amp.amp_settings({'amp_brand': 'elecraft'})['baudrate'] == amp.AMP_DEFAULT_BAUD['elecraft']
    assert amp.amp_settings({'amp_brand': 'spe'})['baudrate'] == amp.AMP_DEFAULT_BAUD['spe']


def test_amp_settings_civ_addr_invalide_retombe_sur_defaut():
    assert amp.amp_settings({'amp_civ_addr': 'zz'})['civ_addr'] == 0xAA


# ─── Orchestration (get_state/set_operate/set_band/clear_fault/power_toggle) ─

def test_get_state_desactive():
    assert amp.get_state({}) == {'enabled': False}


def test_get_state_kpa():
    fake = FakeKpaAmp(power_w=100, swr3='010', operate=True, fault=0, temp=25)
    cfg = {'amp_enabled': True, 'amp_brand': 'elecraft', 'amp_port': 'COM5'}

    def run(factory):
        st = amp.get_state(cfg)
        assert st['ok'] and st['enabled'] and st['power_w'] == 100
        amp.get_state(cfg)
        assert factory.calls == 1   # connexion réutilisée

    _with_fake_serial(fake, run)


def test_set_operate_icom():
    fake = FakeIcomAmp(operate=False)
    cfg = {'amp_enabled': True, 'amp_brand': 'icom', 'amp_port': 'COM6', 'amp_civ_addr': 'AA'}

    def run(factory):
        r = amp.set_operate(cfg, True)
        assert r == {'ok': True, 'operate': True}

    _with_fake_serial(fake, run)


def test_set_band_spe():
    fake = FakeSpeAmp(band_idx=5)
    cfg = {'amp_enabled': True, 'amp_brand': 'spe', 'amp_port': 'COM7'}

    def run(factory):
        r = amp.set_band(cfg, '40')
        assert r['ok'] and r['band'] == '03'

    _with_fake_serial(fake, run)


def test_clear_fault_kpa():
    fake = FakeKpaAmp(fault=5)
    cfg = {'amp_enabled': True, 'amp_brand': 'elecraft', 'amp_port': 'COM5'}

    def run(factory):
        r = amp.clear_fault(cfg)
        assert r['ok']

    _with_fake_serial(fake, run)


def test_clear_fault_spe_non_disponible():
    fake = FakeSpeAmp()
    cfg = {'amp_enabled': True, 'amp_brand': 'spe', 'amp_port': 'COM7'}

    def run(factory):
        r = amp.clear_fault(cfg)
        assert not r['ok'] and 'défaut' in r['error'].lower()

    _with_fake_serial(fake, run)


def test_power_toggle_icom():
    fake = FakeIcomAmp()
    cfg = {'amp_enabled': True, 'amp_brand': 'icom', 'amp_port': 'COM6', 'amp_civ_addr': 'AA'}

    def run(factory):
        assert amp.power_toggle(cfg, False) == {'ok': True}
        assert amp.power_toggle(cfg, True) == {'ok': True}

    _with_fake_serial(fake, run)


def test_power_toggle_desactive():
    assert not amp.power_toggle({}, True)['ok']


def test_disable_ferme_la_connexion_persistante():
    fake = FakeKpaAmp()
    cfg = {'amp_enabled': True, 'amp_brand': 'elecraft', 'amp_port': 'COM5'}

    def run(factory):
        amp.get_state(cfg)
        assert factory.calls == 1
        amp.disconnect_persistent()
        amp.get_state(cfg)
        assert factory.calls == 2

    _with_fake_serial(fake, run)


def test_test_connection_port_manquant():
    r = amp.test_connection('elecraft', '', 38400)
    assert not r['ok']


def test_test_connection_marque_manquante():
    r = amp.test_connection('', 'COM5', 9600)
    assert not r['ok']


def test_test_connection_kpa_reussi():
    fake = FakeKpaAmp(power_w=50, swr3='010')

    def run(factory):
        r = amp.test_connection('elecraft', 'COM5', 38400)
        assert r['ok'] and r['status']['power_w'] == 50

    _with_fake_serial(fake, run)
