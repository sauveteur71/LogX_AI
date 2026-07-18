# -*- coding: utf-8 -*-
"""Tests du pilotage CAT natif (radiocontest_cat) : logique de trame pure
(BCD, CI-V, IF ASCII) + boucle complète contre des radios FICTIVES en
mémoire (aucun port série réel requis, aucune dépendance matérielle)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import radiocontest_cat as cat


# ─── DOUBLES DE TEST : radios fictives en mémoire ──────────────────────────

def _swap_addr_for_test(frame, addr_from, addr_to):
    """Aide de test : réémet une trame comme si elle venait de la radio
    (adresses source/dest inversées par rapport à civ_build_frame)."""
    if len(frame) < 4:
        return frame
    return frame[:2] + bytes([addr_from, addr_to]) + frame[4:]


class FakeCivRadio:
    """Simule une radio Icom : répond aux requêtes CI-V envoyées via write(),
    la réponse est récupérée par read_until()."""

    def __init__(self, addr, freq=14074000, mode_code=0x03):
        self.addr = addr
        self.freq = freq
        self.mode_code = mode_code
        self.ptt = False
        self._pending = b''

    def write(self, data):
        parsed = cat.civ_parse_frame(data)
        # Trame reçue = une REQUÊTE PC->radio : addr_dest (1er octet) doit
        # être NOTRE adresse pour qu'on y réponde.
        if not parsed or parsed[0] != self.addr:
            self._pending = b''
            return
        _, _, cmd, sub, payload = parsed
        if cmd == 0x03:  # get freq
            self._pending = _swap_addr_for_test(
                cat.civ_build_frame(0xE0, 0x03, data=cat.civ_encode_freq(self.freq)), self.addr, 0xE0)
        elif cmd == 0x05:  # set freq
            self.freq = cat.civ_decode_freq(payload[:5])
            self._pending = _swap_addr_for_test(
                cat.civ_build_frame(0xE0, 0x05), self.addr, 0xE0)
        elif cmd == 0x04:  # get mode
            self._pending = _swap_addr_for_test(
                cat.civ_build_frame(0xE0, 0x04, data=bytes([self.mode_code])), self.addr, 0xE0)
        elif cmd == 0x06:  # set mode
            self.mode_code = payload[0]
            self._pending = _swap_addr_for_test(cat.civ_build_frame(0xE0, 0x06), self.addr, 0xE0)
        elif cmd == 0x1C and sub == 0x00:
            if payload:
                self.ptt = bool(payload[0])
                self._pending = _swap_addr_for_test(
                    cat.civ_build_frame(0xE0, 0x1C, sub=0x00), self.addr, 0xE0)
            else:
                self._pending = _swap_addr_for_test(
                    cat.civ_build_frame(0xE0, 0x1C, sub=0x00, data=bytes([1 if self.ptt else 0])),
                    self.addr, 0xE0)
        elif cmd == 0x15 and sub == 0x02:
            self._pending = _swap_addr_for_test(
                cat.civ_build_frame(0xE0, 0x15, sub=0x02, data=bytes([0x01, 0x20])), self.addr, 0xE0)
        elif cmd == 0x19 and sub == 0x00:
            self._pending = _swap_addr_for_test(
                cat.civ_build_frame(0xE0, 0x19, sub=0x00, data=bytes([self.addr])), self.addr, 0xE0)
        else:
            self._pending = b''

    def read_until(self, terminator, timeout=1.0):
        r, self._pending = self._pending, b''
        return r

    def close(self):
        pass


class FakeAsciiRadio:
    """Simule une radio Yaesu/Kenwood/Elecraft ASCII."""

    def __init__(self, brand, freq=14074000, mode='CW', id_code='670'):
        self.brand = brand
        self.freq = freq
        self.mode = mode
        self.id_code = id_code
        self.ptt = False
        self._pending = b''

    def write(self, data):
        cmd = data.decode('ascii')
        if cmd == 'IF;':
            spec = cat._IF_FIELDS[self.brand]
            body = ['0'] * (spec[2] + 1)
            freq_s = str(self.freq).rjust(spec[1], '0')
            for i, c in enumerate(freq_s):
                body[spec[0] + i] = c
            code = cat.ASCII_MODES.get(self.brand + '_rev', {}).get(self.mode, '3')
            body[spec[2]] = code
            self._pending = ('IF' + ''.join(body) + ';').encode('ascii')
        elif cmd.startswith('FA'):
            self.freq = int(cmd[2:-1])
            self._pending = b''
        elif cmd.startswith('MD'):
            code = cmd[2:-1]
            self.mode = cat.ASCII_MODES.get(self.brand, {}).get(code, self.mode)
            self._pending = b''
        elif cmd == 'TQ;':
            self._pending = f'TQ{1 if self.ptt else 0};'.encode()
        elif cmd == 'TX;':
            self.ptt = True
            self._pending = b'TX0;' if self.brand != 'yaesu' else b''
        elif cmd == 'RX;':
            self.ptt = False
            self._pending = b''
        elif cmd in ('SM0;', 'SM;'):
            self._pending = b'SM0015;'
        elif cmd == 'ID;':
            self._pending = f'ID{self.id_code};'.encode()
        else:
            self._pending = b''

    def read_until(self, terminator, timeout=1.0):
        r, self._pending = self._pending, b''
        return r

    def close(self):
        pass


# ─── BCD fréquence (CI-V) ───────────────────────────────────────────────────

def test_bcd_freq_reference_connue():
    """145.000.000 Hz -> 00 00 00 45 01, exemple de référence largement
    documenté pour le protocole CI-V Icom."""
    assert cat.civ_encode_freq(145000000).hex() == '0000004501'


def test_bcd_freq_roundtrip():
    for f in (145500000, 14074000, 432175000, 1296000000, 1800000, 50313000):
        assert cat.civ_decode_freq(cat.civ_encode_freq(f)) == f


# ─── Trames CI-V ────────────────────────────────────────────────────────────

def test_civ_build_et_parse_frame():
    frame = cat.civ_build_frame(0x94, 0x03)
    assert frame == b'\xFE\xFE\x94\xE0\x03\xFD'
    parsed = cat.civ_parse_frame(frame)
    assert parsed == (0x94, 0xE0, 0x03, None, b'')


def test_civ_parse_frame_avec_sous_commande():
    frame = cat.civ_build_frame(0x94, 0x1C, sub=0x00, data=bytes([1]))
    parsed = cat.civ_parse_frame(frame)
    assert parsed == (0x94, 0xE0, 0x1C, 0x00, b'\x01')


def test_civ_parse_frame_malformee_retourne_none():
    assert cat.civ_parse_frame(b'\x00\x01') is None
    assert cat.civ_parse_frame(b'') is None


# ─── CivRadio (Icom) contre radio fictive ──────────────────────────────────

def test_civ_radio_get_set_freq():
    fake = FakeCivRadio(0x94, freq=14074000)
    radio = cat.CivRadio(fake, 0x94)
    assert radio.get_freq() == {'ok': True, 'freq_hz': 14074000}
    assert radio.set_freq(3512000)['ok']
    assert fake.freq == 3512000


def test_civ_radio_get_set_mode():
    fake = FakeCivRadio(0x94, mode_code=cat.CIV_MODES['CW'])
    radio = cat.CivRadio(fake, 0x94)
    assert radio.get_mode() == {'ok': True, 'mode': 'CW'}
    assert radio.set_mode('USB')['ok']
    assert fake.mode_code == cat.CIV_MODES['USB']


def test_civ_radio_ptt():
    fake = FakeCivRadio(0x94)
    radio = cat.CivRadio(fake, 0x94)
    assert radio.get_ptt() == {'ok': True, 'ptt': False}
    assert radio.set_ptt(True)['ok']
    assert fake.ptt is True
    assert radio.get_ptt() == {'ok': True, 'ptt': True}


def test_civ_radio_smeter_et_identify():
    fake = FakeCivRadio(0x94)
    radio = cat.CivRadio(fake, 0x94)
    sm = radio.get_smeter()
    assert sm['ok'] and sm['raw'] == 120   # 01 20 BCD -> "0120" -> S9
    ident = radio.identify()
    assert ident == {'ok': True, 'addr': 0x94}


def test_civ_radio_mauvaise_adresse_pas_de_reponse():
    fake = FakeCivRadio(0x94)
    radio = cat.CivRadio(fake, 0xA2)   # adresse différente : la fake radio ignore
    r = radio.get_freq()
    assert not r['ok']


# ─── Trames IF ASCII (Yaesu / Kenwood / Elecraft) ──────────────────────────

def test_ascii_parse_if_yaesu():
    f = 'IF' + '00' + '014074000' + '+0000' + '0' + '0' + '3' + '0' + ';'
    assert cat.ascii_parse_if(f, 'yaesu') == {'freq_hz': 14074000, 'mode': 'CW'}


def test_ascii_parse_if_kenwood():
    f = 'IF' + '00014195000' + '     ' + '+0000' + '0' + '0' + '00' + '0' + '3' + '0000000;'
    assert cat.ascii_parse_if(f, 'kenwood') == {'freq_hz': 14195000, 'mode': 'CW'}


def test_ascii_parse_if_elecraft():
    f = 'IF' + '00014060000' + '     ' + '+0000' + '0' + '0' + '0' + '00' + '0' + '3' + '0000001;'
    assert cat.ascii_parse_if(f, 'elecraft') == {'freq_hz': 14060000, 'mode': 'CW'}


def test_ascii_parse_if_trame_trop_courte():
    assert cat.ascii_parse_if('IF123;', 'kenwood') is None


def test_ascii_parse_if_marque_inconnue():
    assert cat.ascii_parse_if('IF00014074000;', 'ten-tec') is None


# ─── AsciiRadio contre radio fictive ────────────────────────────────────────

def test_ascii_radio_get_state_yaesu():
    fake = FakeAsciiRadio('yaesu', freq=14074000, mode='CW')
    radio = cat.AsciiRadio(fake, 'yaesu', model='FT-991A')
    st = radio.get_state()
    assert st['ok'] and st['freq_hz'] == 14074000 and st['mode'] == 'CW'


def test_ascii_radio_set_freq_et_mode():
    fake = FakeAsciiRadio('kenwood')
    radio = cat.AsciiRadio(fake, 'kenwood', model='TS-890S')
    assert radio.set_freq(21050000)['ok']
    assert fake.freq == 21050000
    assert radio.set_mode('USB')['ok']
    assert fake.mode == 'USB'


def test_ascii_radio_mode_inconnu_erreur_propre():
    fake = FakeAsciiRadio('elecraft')
    radio = cat.AsciiRadio(fake, 'elecraft')
    r = radio.set_mode('DSTAR')
    assert not r['ok'] and 'inconnu' in r['error'].lower()


def test_ascii_radio_ptt_elecraft_lecture_dediee():
    fake = FakeAsciiRadio('elecraft')
    radio = cat.AsciiRadio(fake, 'elecraft')
    assert radio.get_ptt() == {'ok': True, 'ptt': False}
    fake.ptt = True
    assert radio.get_ptt() == {'ok': True, 'ptt': True}


def test_ascii_radio_ptt_kenwood_non_disponible():
    """Pas de lecture PTT fiable documentée pour Kenwood (TS-890 notamment) —
    doit le signaler plutôt que deviner."""
    fake = FakeAsciiRadio('kenwood')
    radio = cat.AsciiRadio(fake, 'kenwood')
    r = radio.get_ptt()
    assert not r['ok']


def test_ascii_radio_smeter():
    fake = FakeAsciiRadio('yaesu')
    radio = cat.AsciiRadio(fake, 'yaesu')
    sm = radio.get_smeter()
    assert sm == {'ok': True, 'raw': 15}


def test_ascii_radio_identify():
    fake = FakeAsciiRadio('yaesu', id_code='670')
    radio = cat.AsciiRadio(fake, 'yaesu')
    ident = radio.identify()
    assert ident == {'ok': True, 'code': '670', 'model': 'FT-991A'}


# ─── Détection automatique ──────────────────────────────────────────────────

def test_autodetect_ascii_certain():
    fake = FakeAsciiRadio('yaesu', id_code='670')
    r = cat.autodetect(fake)
    assert r == {'ok': True, 'protocol': 'ascii', 'brand': 'yaesu',
                 'model': 'FT-991A', 'certain': True}


def test_autodetect_elecraft_ambigu():
    fake = FakeAsciiRadio('elecraft', id_code='017')
    r = cat.autodetect(fake)
    assert r['ok'] and r['certain'] is False and r['brand'] == 'elecraft'


def test_autodetect_civ_repli():
    fake = FakeCivRadio(cat.CIV_ADDRESSES['IC-7300'])
    r = cat.autodetect(fake)
    assert r['ok'] and r['protocol'] == 'civ' and r['model'] == 'IC-7300'
    assert r['certain'] is False   # jamais certain pour Icom (adresse réassignable)


def test_autodetect_aucune_radio():
    class Silence:
        def write(self, data): pass
        def read_until(self, terminator, timeout=1.0): return b''
        def close(self): pass
    r = cat.autodetect(Silence())
    assert not r['ok']


# ─── RigManager (multi-radio) ───────────────────────────────────────────────

def test_rig_manager_multi_radio():
    mgr = cat.RigManager()
    fake1 = FakeCivRadio(0x94)
    fake2 = FakeAsciiRadio('kenwood')
    mgr.add('radio1', fake1, 'civ', addr=0x94)
    mgr.add('radio2', fake2, 'ascii', brand='kenwood', model='TS-890S')

    assert mgr.get('radio1').get_freq()['ok']
    assert mgr.get('radio2').set_freq(7100000)['ok']
    assert set(mgr.list_active()) == {'radio1', 'radio2'}

    mgr.remove('radio1')
    assert mgr.get('radio1') is None
    assert set(mgr.list_active()) == {'radio2'}


# ─── list_ports ne doit jamais lever d'exception ────────────────────────────

def test_list_ports_ne_crashe_jamais():
    ports = cat.list_ports()
    assert isinstance(ports, list)


# ─── Couche haut niveau pilotée par la config (cat_settings/get_state/
#     set_freq/test_connection) — injection d'un faux port série ───────────

def test_cat_settings_defaut_desactive():
    s = cat.cat_settings({})
    assert s['enabled'] is False
    assert s['mode'] == 'native'   # défaut si jamais configuré


def test_cat_settings_lit_la_config():
    s = cat.cat_settings({'cat_enabled': True, 'cat_mode': 'native',
                          'cat_brand': 'Yaesu', 'cat_model': 'FT-991A',
                          'cat_port': 'COM5', 'cat_baudrate': '38400'})
    assert s == {'enabled': True, 'mode': 'native', 'brand': 'yaesu',
                'model': 'FT-991A', 'port': 'COM5', 'baudrate': 38400}


def test_cat_settings_baudrate_par_defaut_selon_marque():
    s = cat.cat_settings({'cat_brand': 'kenwood'})
    assert s['baudrate'] == cat.CAT_DEFAULT_BAUD['kenwood']


class _FakeFactory:
    """Remplace _open_serial : retourne toujours la même fausse radio,
    ignore port/baudrate (comme un vrai constructeur les consommerait)."""

    def __init__(self, transport):
        self.transport = transport
        self.calls = 0

    def __call__(self, port, baudrate=19200):
        self.calls += 1
        return self.transport


def _with_fake_serial(transport, fn):
    """Exécute fn() avec cat._open_serial substitué, restauré ensuite —
    même esprit que FakeRigctld.close() dans test_rig.py (jamais de fuite
    entre tests)."""
    original = cat._open_serial
    factory = _FakeFactory(transport)
    cat._open_serial = factory
    try:
        return fn(factory)
    finally:
        cat._open_serial = original
        cat.disconnect_persistent()


def test_get_state_natif_desactive():
    assert cat.get_state({}) == {'enabled': False}
    assert cat.get_state({'cat_enabled': True, 'cat_mode': 'rigctld'}) == {'enabled': False}


def test_get_state_natif_civ():
    fake = FakeCivRadio(cat.CIV_ADDRESSES['IC-7300'], freq=14195000, mode_code=cat.CIV_MODES['USB'])
    cfg = {'cat_enabled': True, 'cat_mode': 'native', 'cat_brand': 'icom',
           'cat_model': 'IC-7300', 'cat_port': 'COM3'}

    def run(factory):
        st = cat.get_state(cfg)
        assert st == {'ok': True, 'enabled': True, 'freq_hz': 14195000,
                      'freq_khz': 14195.0, 'mode': 'USB'}
        # 2e appel : connexion réutilisée (pas de nouvelle ouverture de port)
        cat.get_state(cfg)
        assert factory.calls == 1

    _with_fake_serial(fake, run)


def test_get_state_natif_ascii():
    fake = FakeAsciiRadio('kenwood', freq=7100000, mode='LSB')
    cfg = {'cat_enabled': True, 'cat_mode': 'native', 'cat_brand': 'kenwood',
           'cat_model': 'TS-890S', 'cat_port': 'COM7'}

    def run(factory):
        st = cat.get_state(cfg)
        assert st == {'ok': True, 'freq_hz': 7100000, 'mode': 'LSB',
                      'enabled': True, 'freq_khz': 7100.0}

    _with_fake_serial(fake, run)


def test_set_freq_natif_reconnecte_si_config_change():
    fake94 = FakeCivRadio(cat.CIV_ADDRESSES['IC-7300'])
    cfg_a = {'cat_enabled': True, 'cat_mode': 'native', 'cat_brand': 'icom',
             'cat_model': 'IC-7300', 'cat_port': 'COM3'}
    cfg_b = dict(cfg_a, cat_port='COM4')   # port différent -> reconnexion attendue

    def run(factory):
        assert cat.set_freq(cfg_a, 14250000)['ok']
        assert fake94.freq == 14250000
        assert factory.calls == 1
        cat.set_freq(cfg_b, 3512000)
        assert factory.calls == 2   # reconnecté car la config a changé

    _with_fake_serial(fake94, run)


def test_set_freq_pilotage_desactive():
    r = cat.set_freq({}, 14250000)
    assert not r['ok']


def test_ensure_connected_port_manquant():
    driver, err = cat._ensure_connected({'port': '', 'brand': 'icom', 'model': 'IC-7300', 'baudrate': 19200})
    assert driver is None and 'non configuré' in err


def test_test_connection_civ():
    fake = FakeCivRadio(cat.CIV_ADDRESSES['IC-9700'], freq=432175000)

    def run(factory):
        r = cat.test_connection('icom', 'IC-9700', 'COM3', 19200)
        assert r == {'ok': True, 'detected_model': 'IC-9700', 'freq_hz': 432175000}

    _with_fake_serial(fake, run)


def test_test_connection_ascii():
    fake = FakeAsciiRadio('yaesu', freq=14074000, id_code='670')

    def run(factory):
        r = cat.test_connection('yaesu', 'FT-991A', 'COM5', 4800)
        assert r == {'ok': True, 'detected_model': 'FT-991A', 'freq_hz': 14074000}

    _with_fake_serial(fake, run)


def test_test_connection_port_manquant():
    r = cat.test_connection('icom', 'IC-7300', '', 19200)
    assert not r['ok'] and 'manquant' in r['error']


def test_test_connection_ne_touche_pas_la_connexion_persistante():
    """Le test éphémère doit ouvrir/fermer sa PROPRE connexion, sans
    perturber celle utilisée par le polling logbook (_ensure_connected)."""
    fake_persist = FakeCivRadio(cat.CIV_ADDRESSES['IC-7300'], freq=14195000)
    fake_test = FakeCivRadio(cat.CIV_ADDRESSES['IC-9700'], freq=432175000)
    cfg = {'cat_enabled': True, 'cat_mode': 'native', 'cat_brand': 'icom',
           'cat_model': 'IC-7300', 'cat_port': 'COM3'}

    class _TwoRadios:
        def __init__(self):
            self.n = 0
        def __call__(self, port, baudrate=19200):
            self.n += 1
            return fake_persist if self.n == 1 else fake_test

    original = cat._open_serial
    factory = _TwoRadios()
    cat._open_serial = factory
    try:
        st = cat.get_state(cfg)          # ouvre et garde fake_persist
        assert st['freq_hz'] == 14195000
        r = cat.test_connection('icom', 'IC-9700', 'COM9', 19200)  # ouvre fake_test, le referme
        assert r['ok'] and r['freq_hz'] == 432175000
        st2 = cat.get_state(cfg)          # doit toujours utiliser fake_persist (réutilisée)
        assert st2['freq_hz'] == 14195000 and factory.n == 2
    finally:
        cat._open_serial = original
        cat.disconnect_persistent()
