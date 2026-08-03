# -*- coding: utf-8 -*-
"""Tests du pilotage CAT natif (logx_cat) : logique de trame pure
(BCD, CI-V, IF ASCII) + boucle complète contre des radios FICTIVES en
mémoire (aucun port série réel requis, aucune dépendance matérielle)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_cat as cat


# ─── DOUBLES DE TEST : radios fictives en mémoire ──────────────────────────

def _swap_addr_for_test(frame, addr_dest, addr_src):
    """Aide de test : réémet une trame comme si elle venait de la radio —
    TO=addr_dest (0xE0/PC) et FROM=addr_src (l'adresse de la radio), l'ordre
    inverse de civ_build_frame() qui construit toujours TO=radio/FROM=E0.
    Piège trouvé en audit 03/08/2026 : cet appel était fait avec les deux
    arguments intervertis (TO=radio, FROM=E0, soit l'INVERSE du vrai format
    CI-V) — resté invisible tant que rien ne validait le sens de la trame
    côté production. Corrigé en même temps que le garde-fou dans
    logx_cat.py/logx_amp.py, sinon ce double de test aurait fait échouer
    tous les appels ci-dessous une fois le contrôle de sens ajouté."""
    if len(frame) < 4:
        return frame
    return frame[:2] + bytes([addr_dest, addr_src]) + frame[4:]


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
                cat.civ_build_frame(0xE0, 0x03, data=cat.civ_encode_freq(self.freq)), 0xE0, self.addr)
        elif cmd == 0x05:  # set freq
            self.freq = cat.civ_decode_freq(payload[:5])
            self._pending = _swap_addr_for_test(
                cat.civ_build_frame(0xE0, 0x05), 0xE0, self.addr)
        elif cmd == 0x04:  # get mode
            self._pending = _swap_addr_for_test(
                cat.civ_build_frame(0xE0, 0x04, data=bytes([self.mode_code])), 0xE0, self.addr)
        elif cmd == 0x06:  # set mode
            self.mode_code = payload[0]
            self._pending = _swap_addr_for_test(cat.civ_build_frame(0xE0, 0x06), 0xE0, self.addr)
        elif cmd == 0x1C and sub == 0x00:
            if payload:
                self.ptt = bool(payload[0])
                self._pending = _swap_addr_for_test(
                    cat.civ_build_frame(0xE0, 0x1C, sub=0x00), 0xE0, self.addr)
            else:
                self._pending = _swap_addr_for_test(
                    cat.civ_build_frame(0xE0, 0x1C, sub=0x00, data=bytes([1 if self.ptt else 0])),
                    0xE0, self.addr)
        elif cmd == 0x15 and sub == 0x02:
            self._pending = _swap_addr_for_test(
                cat.civ_build_frame(0xE0, 0x15, sub=0x02, data=bytes([0x01, 0x20])), 0xE0, self.addr)
        elif cmd == 0x19 and sub == 0x00:
            self._pending = _swap_addr_for_test(
                cat.civ_build_frame(0xE0, 0x19, sub=0x00, data=bytes([self.addr])), 0xE0, self.addr)
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


# ─── Garde-fou de sens de trame CI-V (bug trouvé en audit 03/08/2026) ──────
# Un câble en boucle, un port sans vraie UART derrière, ou un appareil en
# écho local renvoie tel quel ce qu'on vient de lui envoyer : la trame est
# syntaxiquement bien formée (préambule/fin corrects) mais ce n'est PAS une
# réponse d'une radio. Avant le correctif, civ_parse_frame() ne validait pas
# le sens (TO=E0/PC, FROM=adresse radio attendue) et un tel écho était
# accepté comme un vrai succès — silencieusement.

class EchoTransport:
    """Renvoie exactement ce qu'on lui écrit — simule un câble en boucle ou
    un port sans UART réelle derrière (audit 03/08/2026, cf. CLAUDE.md/mémoire
    du chantier CAT plug-and-play)."""

    def __init__(self):
        self._pending = b''

    def write(self, data):
        self._pending = bytes(data)

    def read_until(self, terminator, timeout=1.0):
        r, self._pending = self._pending, b''
        return r

    def close(self):
        pass


def test_civ_radio_echo_boucle_ne_donne_jamais_ok():
    """Écho de la requête elle-même sur get_freq/set_freq/set_mode/identify —
    aucun ne doit rapporter ok:True, même si la trame est bien formée."""
    echo = EchoTransport()
    radio = cat.CivRadio(echo, cat.CIV_ADDRESSES['IC-7300'])
    assert radio.get_freq()['ok'] is False
    assert radio.set_freq(14250000)['ok'] is False
    assert radio.set_mode('USB')['ok'] is False
    assert radio.identify()['ok'] is False


def test_autodetect_echo_boucle_ne_detecte_aucune_radio():
    """Le repli CI-V de autodetect() ne doit jamais confondre un écho de sa
    propre requête d'identification (adresse 0x19/00) avec une vraie radio."""
    echo = EchoTransport()
    r = cat.autodetect(echo)
    assert r['ok'] is False


# ─── Relecture dans le budget de timeout face à une trame parasite ─────────
# Bus CI-V partagé avec un autre logiciel (WSJT-X/N1MM+ via un séparateur) ou
# notification "CI-V Transceive" restée activée sur la radio : une trame
# bien formée et bien adressée, mais qui répond à une AUTRE commande, peut
# arriver AVANT la vraie réponse à notre propre requête. Avant le correctif,
# _query()/autodetect() ne lisaient qu'UNE trame par essai et concluaient
# "radio muette" dès que cette trame ne correspondait pas — trouvé en revue
# adversariale du chantier CAT plug-and-play (03/08/2026).

class QueuedCivTransport:
    """Sert une liste de trames PRÉ-CONSTRUITES, une par read_until() — peu
    importe le contenu écrit (pas une vraie radio, juste le flux tel qu'il
    arriverait sur un bus CI-V partagé). Chaque read_until() ne retourne
    JAMAIS plus d'une trame à la fois même si plusieurs sont mises en
    attente d'un coup, comme le ferait réellement pyserial en s'arrêtant au
    premier terminateur rencontré."""

    def __init__(self, frames):
        self._queue = list(frames)

    def write(self, data):
        pass

    def read_until(self, terminator, timeout=1.0):
        if not self._queue:
            return b''
        return self._queue.pop(0)

    def close(self):
        pass


def _reponse_civ(addr, cmd, sub=None, data=b''):
    """Construit une trame de RÉPONSE radio->PC (TO=E0/PC, FROM=addr) —
    l'inverse de civ_build_frame(), qui construit toujours des REQUÊTES
    PC->radio (voir _swap_addr_for_test)."""
    return _swap_addr_for_test(cat.civ_build_frame(0xE0, cmd, sub, data), 0xE0, addr)


def test_query_civ_relit_apres_une_trame_parasite_meme_fenetre():
    """Une trame parasite bien adressée mais d'une AUTRE commande (ici une
    réponse PTT, comme si un autre logiciel venait d'interroger sa propre
    commande sur le bus partagé) précède la vraie réponse de fréquence —
    get_freq() doit relire au lieu d'abandonner après la première lecture."""
    addr = cat.CIV_ADDRESSES['IC-7300']
    parasite = _reponse_civ(addr, 0x1C, sub=0x00, data=bytes([0]))   # réponse PTT, pas freq
    vraie_reponse = _reponse_civ(addr, 0x03, data=cat.civ_encode_freq(14074000))
    transport = QueuedCivTransport([parasite, vraie_reponse])
    radio = cat.CivRadio(transport, addr)
    assert radio.get_freq() == {'ok': True, 'freq_hz': 14074000}


def test_query_civ_relit_apres_plusieurs_trames_parasites():
    """Deux trames parasites de suite (bus très bavard) avant la vraie
    réponse — toutes doivent être absorbées dans le même budget de
    timeout."""
    addr = cat.CIV_ADDRESSES['IC-9700']
    parasites = [_reponse_civ(addr, 0x1C, sub=0x00, data=bytes([1])),
                 _reponse_civ(addr, 0x04, data=bytes([cat.CIV_MODES['USB']]))]
    vraie_reponse = _reponse_civ(addr, 0x03, data=cat.civ_encode_freq(432175000))
    transport = QueuedCivTransport(parasites + [vraie_reponse])
    radio = cat.CivRadio(transport, addr)
    assert radio.get_freq() == {'ok': True, 'freq_hz': 432175000}


def test_query_civ_que_des_parasites_echoue_proprement():
    """Si AUCUNE vraie réponse n'arrive jamais (que des trames parasites,
    puis silence), la relecture doit tout de même finir par abandonner —
    jamais de blocage, jamais de faux positif sur une trame parasite."""
    addr = cat.CIV_ADDRESSES['IC-7300']
    parasites = [_reponse_civ(addr, 0x1C, sub=0x00, data=bytes([0])),
                 _reponse_civ(addr, 0x04, data=bytes([cat.CIV_MODES['CW']]))]
    transport = QueuedCivTransport(parasites)   # pas de vraie réponse ensuite
    radio = cat.CivRadio(transport, addr)
    assert radio.get_freq()['ok'] is False


def test_autodetect_civ_repli_relit_apres_trame_parasite():
    """Même scénario que pour _query(), mais via le repli CI-V de
    autodetect() : une trame parasite bien adressée à LA BONNE radio mais
    d'une autre commande précède la vraie réponse d'identification (0x19)."""
    addr = cat.CIV_ADDRESSES['IC-7300']
    parasite = _reponse_civ(addr, 0x1C, sub=0x00, data=bytes([0]))
    vraie_reponse = _reponse_civ(addr, 0x19, sub=0x00, data=bytes([addr]))

    class BusPartage:
        """Simule le bus CI-V partagé pour TOUTES les adresses essayées par
        autodetect() : silence sur les mauvaises adresses (comme une vraie
        radio qui ignore une requête qui ne lui est pas destinée), trame
        parasite puis vraie réponse sur LA bonne adresse."""

        def __init__(self):
            self._queue = []

        def write(self, data):
            parsed = cat.civ_parse_frame(data)
            if parsed and parsed[0] == addr:
                self._queue = [parasite, vraie_reponse]
            else:
                self._queue = []

        def read_until(self, terminator, timeout=1.0):
            if not self._queue:
                return b''
            return self._queue.pop(0)

        def close(self):
            pass

    r = cat.autodetect(BusPartage())
    assert r['ok'] and r['protocol'] == 'civ' and r['model'] == 'IC-7300'


def test_test_connection_civ_relit_apres_trame_parasite():
    """test_connection() (bouton CONFIG) délègue à CivRadio.get_freq(), donc
    hérite de la relecture — vérifié bout en bout via _open_serial substitué,
    comme les autres tests de test_connection()."""
    addr = cat.CIV_ADDRESSES['IC-9700']
    parasite = _reponse_civ(addr, 0x1C, sub=0x00, data=bytes([0]))
    vraie_reponse = _reponse_civ(addr, 0x03, data=cat.civ_encode_freq(432175000))
    transport = QueuedCivTransport([parasite, vraie_reponse])

    def run(factory):
        r = cat.test_connection('icom', 'IC-9700', 'COM3', 19200)
        assert r == {'ok': True, 'detected_model': 'IC-9700', 'freq_hz': 432175000}

    _with_fake_serial(transport, run)


# ─── RTS/DTR forcés bas à l'ouverture (bug trouvé en audit 03/08/2026) ─────
# Par défaut pyserial/Windows lèvent RTS et DTR à l'ouverture du port ; sur
# une interface qui câble le PTT dessus, un simple test de connexion pourrait
# déclencher l'émission. SerialPort doit toujours les forcer bas à l'ouverture.

def test_serial_port_force_rts_dtr_bas_a_ouverture(monkeypatch):
    """🚨 Piège trouvé en revue adversariale avant fusion : le VRAI
    pyserial.Serial() n'accepte PAS rts=/dtr= comme arguments du
    CONSTRUCTEUR (ValueError « unexpected keyword arguments ») — seulement
    comme propriétés d'instance à poser AVANT open(). Un premier double de
    test acceptait n'importe quel kwarg (`__init__(self, device, **kwargs)`)
    et masquait donc totalement cette contrainte réelle : le test passait
    au vert alors que le vrai code cassait l'ouverture de TOUT port CAT
    natif en production. Ce double-ci n'accepte AUCUN argument positionnel
    au constructeur (comme le vrai `serial.Serial()`), pour retrouver cette
    même erreur si jamais la production régresse vers l'ancien style."""
    if not cat.HAS_PYSERIAL:
        import pytest
        pytest.skip("pyserial non installé dans cet environnement")

    class _FakeUnderlyingSerial:
        def __init__(self):   # aucun argument — comme le vrai serial.Serial()
            self.port = None
            self.baudrate = None
            self.timeout = None
            self.bytesize = None
            self.parity = None
            self.stopbits = None
            self.rts = None
            self.dtr = None
            self.opened = False

        def open(self):
            self.opened = True

        def close(self):
            pass

    fake = _FakeUnderlyingSerial()
    monkeypatch.setattr(cat._pyserial, 'Serial', lambda: fake)
    cat.SerialPort('COM99', baudrate=19200)
    assert fake.port == 'COM99'
    assert fake.baudrate == 19200
    assert fake.rts is False
    assert fake.dtr is False
    assert fake.opened is True


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


# ─── Pré-filtre passif VID:PID/numéro de série (aucun octet CAT envoyé) ────

def test_guess_usb_signature_microham():
    port = {'vid': 0x0403, 'pid': 0xEEEC, 'serial_number': None, 'product': None}
    r = cat.guess_from_usb_signature(port)
    assert r == {'kind': 'interface', 'label': 'microHAM USB Interface (USB-IC)',
                 'certain': False}


def test_guess_usb_signature_icom_via_numero_de_serie():
    port = {'vid': 0x10C4, 'pid': 0xEA60, 'serial_number': 'IC-7300 03000000', 'product': None}
    r = cat.guess_from_usb_signature(port)
    assert r == {'kind': 'radio', 'brand': 'icom', 'model': 'IC-7300', 'certain': False}


def test_guess_usb_signature_icom_port_audio_suffixe():
    port = {'vid': 0x10C4, 'pid': 0xEA60, 'serial_number': 'IC-9700 13000000 A', 'product': None}
    r = cat.guess_from_usb_signature(port)
    assert r == {'kind': 'radio', 'brand': 'icom', 'model': 'IC-9700', 'certain': False}


def test_guess_usb_signature_puce_generique_seule_ne_devine_rien():
    """VID:PID 10C4:EA60 seul (sans numéro de série exploitable) est partagé
    par des centaines d'adaptateurs — ne doit jamais deviner à tort."""
    port = {'vid': 0x10C4, 'pid': 0xEA60, 'serial_number': None, 'product': None}
    assert cat.guess_from_usb_signature(port) is None


def test_guess_usb_signature_port_non_usb():
    port = {'vid': None, 'pid': None, 'serial_number': None, 'product': None}
    assert cat.guess_from_usb_signature(port) is None


# ─── Watcher de branchement (tick isolé, sans thread ni sleep) ─────────────

def test_port_watcher_tick_detecte_nouveau_port_reconnu(monkeypatch):
    cat._pending_detections.clear()
    ports = [{'device': 'COM5', 'description': 'microHAM', 'vid': 0x0403,
              'pid': 0xEEEC, 'serial_number': None, 'product': None}]
    monkeypatch.setattr(cat, 'list_ports', lambda: ports)
    known = cat._port_watcher_tick(set())
    assert known == {'COM5'}
    pending = cat.get_pending_detections()
    assert len(pending) == 1
    assert pending[0]['device'] == 'COM5'
    assert pending[0]['kind'] == 'interface'
    cat._pending_detections.clear()


def test_port_watcher_tick_ignore_port_deja_connu(monkeypatch):
    cat._pending_detections.clear()
    ports = [{'device': 'COM5', 'description': '', 'vid': 0x0403,
              'pid': 0xEEEC, 'serial_number': None, 'product': None}]
    monkeypatch.setattr(cat, 'list_ports', lambda: ports)
    known = cat._port_watcher_tick({'COM5'})   # déjà dans les connus
    assert known == {'COM5'}
    assert cat.get_pending_detections() == []


def test_port_watcher_tick_debranchement_retire_la_detection(monkeypatch):
    cat._pending_detections.clear()
    monkeypatch.setattr(cat, 'list_ports', lambda: [
        {'device': 'COM5', 'description': '', 'vid': 0x0403,
         'pid': 0xEEEC, 'serial_number': None, 'product': None}])
    known = cat._port_watcher_tick(set())
    assert cat.get_pending_detections() != []

    monkeypatch.setattr(cat, 'list_ports', lambda: [])   # débranché
    known = cat._port_watcher_tick(known)
    assert known == set()
    assert cat.get_pending_detections() == []


def test_port_watcher_tick_port_sans_indice_reconnu_pas_de_detection(monkeypatch):
    cat._pending_detections.clear()
    monkeypatch.setattr(cat, 'list_ports', lambda: [
        {'device': 'COM6', 'description': 'Adaptateur générique', 'vid': 0x1A86,
         'pid': 0x7523, 'serial_number': None, 'product': None}])   # CH340 générique
    known = cat._port_watcher_tick(set())
    assert known == {'COM6'}
    assert cat.get_pending_detections() == []


def test_dismiss_detection_retire_bien_la_bonne_entree(monkeypatch):
    cat._pending_detections.clear()
    monkeypatch.setattr(cat, 'list_ports', lambda: [
        {'device': 'COM7', 'description': '', 'vid': 0x0403,
         'pid': 0xEEEC, 'serial_number': None, 'product': None}])
    cat._port_watcher_tick(set())
    assert len(cat.get_pending_detections()) == 1
    cat.dismiss_detection('COM7')
    assert cat.get_pending_detections() == []


def test_dismiss_detection_ne_reapparait_pas_tant_que_branche(monkeypatch):
    """Cycle réel décrit par le docstring de dismiss_detection() : l'opérateur
    clique « Ignorer », laisse l'interface branchée — un nouveau tour de
    scan ne doit PAS la refaire réapparaître (elle reste dans known_devices,
    ce n'est pas un nouveau branchement)."""
    cat._pending_detections.clear()
    ports = [{'device': 'COM7', 'description': '', 'vid': 0x0403,
              'pid': 0xEEEC, 'serial_number': None, 'product': None}]
    monkeypatch.setattr(cat, 'list_ports', lambda: ports)
    known = cat._port_watcher_tick(set())
    assert len(cat.get_pending_detections()) == 1
    cat.dismiss_detection('COM7')

    known = cat._port_watcher_tick(known)   # 2e tour, port TOUJOURS branché
    assert known == {'COM7'}
    assert cat.get_pending_detections() == []

    known = cat._port_watcher_tick(known)   # 3e tour, rien ne change
    assert cat.get_pending_detections() == []


def test_guess_usb_signature_vid_sans_pid_ne_devine_rien():
    port = {'vid': 0x0403, 'pid': None, 'serial_number': None, 'product': None}
    assert cat.guess_from_usb_signature(port) is None


def test_guess_usb_signature_pid_sans_vid_ne_devine_rien():
    port = {'vid': None, 'pid': 0xEEEC, 'serial_number': None, 'product': None}
    assert cat.guess_from_usb_signature(port) is None


def test_guess_usb_signature_icom_suffixe_b_meme_resultat_que_a():
    """Documente le comportement actuel (limitation connue, pas un bug) :
    guess_from_usb_signature() ne distingue PAS le port CAT (souvent
    suffixe A) du port audio (souvent suffixe B) d'une radio Icom double-port
    comme l'IC-9700 — les deux donnent le même indice « radio détectée ».
    La sonde active (autodetectCat, déjà sûre) reste seule responsable de
    confirmer LEQUEL des deux répond vraiment au CAT."""
    port_a = {'vid': 0x10C4, 'pid': 0xEA60, 'serial_number': 'IC-9700 13000000 A', 'product': None}
    port_b = {'vid': 0x10C4, 'pid': 0xEA60, 'serial_number': 'IC-9700 13000000 B', 'product': None}
    assert cat.guess_from_usb_signature(port_a) == cat.guess_from_usb_signature(port_b)


def test_port_watcher_tick_exception_hors_list_ports_absorbee(monkeypatch):
    """🚨 Trouvé en revue adversariale : le try/except ne couvrait QUE
    list_ports(), pas guess_from_usb_signature() ni la construction du dict
    qui suit — une exception inattendue là tuait le thread daemon pour de
    bon, silencieusement, jusqu'au redémarrage du serveur."""
    cat._pending_detections.clear()
    monkeypatch.setattr(cat, 'list_ports', lambda: [
        {'device': 'COM8', 'description': '', 'vid': 0x0403,
         'pid': 0xEEEC, 'serial_number': None, 'product': None}])

    def _boom(port):
        raise RuntimeError('panne inattendue')

    monkeypatch.setattr(cat, 'guess_from_usb_signature', _boom)
    known = cat._port_watcher_tick(set())
    assert known == set()   # exception absorbée -> liste connue inchangée
    assert cat.get_pending_detections() == []


def test_start_port_watcher_idempotent(monkeypatch):
    """Plusieurs appels ne doivent jamais démarrer plusieurs threads."""
    calls = []

    class _FakeThread:
        def __init__(self, target=None, daemon=None):
            calls.append(target)
        def start(self):
            pass

    original = cat._watcher_thread_started
    cat._watcher_thread_started = False
    monkeypatch.setattr(cat.threading, 'Thread', _FakeThread)
    try:
        cat.start_port_watcher()
        cat.start_port_watcher()
        cat.start_port_watcher()
        assert len(calls) == 1
    finally:
        cat._watcher_thread_started = original


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
