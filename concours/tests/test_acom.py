# -*- coding: utf-8 -*-
"""Tests du pilotage ACOM (logx_acom) — parsing pur + faux transport série
(interface AcomPort) injecté via `_open_serial`/`opener=`, jamais de vrai
port matériel (voir logx_powergenius.py/test_powergenius.py pour le même
principe côté TCP : ici pas de socket loopback possible pour du RS-232, donc
un double MINIMAL de AcomPort plutôt qu'un vrai serveur)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_acom as acom


def _frame(status=6, fan=0, band_idx=5, drive_raw=1000, power=100, reflected=5,
           swr_raw=110, dc8=0, dc9=20, temp_raw=310, error=0xFF):
    """Construit une trame de télémétrie de 72 octets synthétique mais
    checksum-valide (somme totale == 0 mod 256), pour tester acom_extract_
    frame()/acom_parse_telemetry() sans matériel réel. L'octet 71 sert
    d'ajustement de somme de contrôle — un choix de CE banc de test, pas une
    position confirmée par la source réelle (voir docstring du module :
    seule la propriété « somme totale nulle » est confirmée, pas l'octet
    précis qui la porte sur un vrai ACOM)."""
    b = bytearray(72)
    b[0], b[1] = 0x55, 0x2F
    b[3] = (status & 0x0F) << 4
    b[8], b[9] = dc8 & 0xFF, dc9 & 0xFF
    b[16], b[17] = temp_raw & 0xFF, (temp_raw >> 8) & 0xFF
    b[20], b[21] = drive_raw & 0xFF, (drive_raw >> 8) & 0xFF
    b[22], b[23] = power & 0xFF, (power >> 8) & 0xFF
    b[24], b[25] = reflected & 0xFF, (reflected >> 8) & 0xFF
    b[26], b[27] = swr_raw & 0xFF, (swr_raw >> 8) & 0xFF
    b[66] = error & 0xFF
    b[69] = ((fan & 0x0F) << 4) | (band_idx & 0x0F)
    b[71] = (-sum(b[:71])) % 256
    assert sum(b) % 256 == 0
    return bytes(b)


# ═══════════════════════════════════════════════════════════════════════════
#  Fonctions pures — cadrage
# ═══════════════════════════════════════════════════════════════════════════

def test_extract_frame_buffer_vide():
    assert acom.acom_extract_frame(b'') == (None, b'')
    assert acom.acom_extract_frame(None) == (None, b'')


def test_extract_frame_aucun_octet_55():
    assert acom.acom_extract_frame(b'\x01\x02\x03') == (None, b'')


def test_extract_frame_resynchronise_sur_second_octet_invalide():
    # 0x55 present mais pas suivi de 0x2F -> pas une trame telemetrie,
    # on avance d'un octet pour retenter plus loin dans le flux
    frame, rest = acom.acom_extract_frame(b'\x55\x01\x02')
    assert frame is None
    assert rest == b'\x01\x02'


def test_extract_frame_incomplete_attend_la_suite():
    partiel = b'\x55\x2F' + b'\x00' * 10
    frame, rest = acom.acom_extract_frame(partiel)
    assert frame is None
    assert rest == partiel  # rien perdu, la suite arrivera au prochain lot


def test_extract_frame_valide():
    f = _frame()
    frame, rest = acom.acom_extract_frame(f)
    assert frame == f
    assert rest == b''


def test_extract_frame_ignore_octets_parasites_avant():
    f = _frame()
    frame, rest = acom.acom_extract_frame(b'\x00\x99' + f)
    assert frame == f
    assert rest == b''


def test_extract_frame_checksum_invalide_rejetee():
    f = bytearray(_frame())
    f[71] ^= 0xFF  # casse la somme de contrôle
    frame, rest = acom.acom_extract_frame(bytes(f))
    assert frame is None
    assert rest == b''  # la trame corrompue est bien consommée, pas rejouée en boucle


def test_extract_frame_deux_trames_a_la_suite():
    f1, f2 = _frame(power=10), _frame(power=20)
    frame, rest = acom.acom_extract_frame(f1 + f2)
    assert frame == f1
    frame2, rest2 = acom.acom_extract_frame(rest)
    assert frame2 == f2
    assert rest2 == b''


# ═══════════════════════════════════════════════════════════════════════════
#  Fonctions pures — décodage
# ═══════════════════════════════════════════════════════════════════════════

def test_parse_telemetry_longueur_invalide():
    assert acom.acom_parse_telemetry(b'\x55\x2F') is None
    assert acom.acom_parse_telemetry(None) is None


def test_parse_telemetry_champs_de_base():
    f = _frame(status=7, band_idx=5, power=250, drive_raw=800, reflected=3,
               swr_raw=115, dc8=0, dc9=20, error=0xFF)
    d = acom.acom_parse_telemetry(f)
    assert d['status'] == 'TRANSMIT'
    assert d['status_code'] == 7
    assert d['band'] == '20m'
    assert d['power_w'] == 250
    assert d['drive_w'] == 80.0   # 800 / 10.0, confirmé par DrivePowerDisplay
    assert d['reflected_raw'] == 3
    assert d['swr'] == 1.15
    assert d['dc_power_w'] == 20 * 25.6
    assert d['error_code'] is None
    assert d['error_message'] is None


def test_parse_telemetry_sans_modele_pas_de_temperature():
    d = acom.acom_parse_telemetry(_frame(temp_raw=310), model=None)
    assert d['temp_c'] is None
    assert d['model'] is None


def test_parse_telemetry_avec_modele_calibre_la_temperature():
    d = acom.acom_parse_telemetry(_frame(temp_raw=310), model='700S')
    assert d['temp_c'] == 310 - acom.ACOM_MODELS['700S']['temp_offset']
    assert d['model'] == '700S'


def test_parse_telemetry_modele_inconnu_pas_de_temperature():
    d = acom.acom_parse_telemetry(_frame(temp_raw=310), model='9999X')
    assert d['temp_c'] is None


def test_parse_telemetry_erreur_connue():
    d = acom.acom_parse_telemetry(_frame(error=0x06))
    assert d['error_code'] == 0x06
    assert "excitation" in d['error_message'].lower()


def test_parse_telemetry_erreur_inconnue_ne_devine_pas_de_libelle():
    d = acom.acom_parse_telemetry(_frame(error=0x55))
    assert d['error_code'] == 0x55
    assert 'voir' in d['error_message'].lower()


def test_parse_telemetry_statut_inconnu_retombe_unknown():
    d = acom.acom_parse_telemetry(_frame(status=0))
    assert d['status'] == 'UNKNOWN'


def test_parse_telemetry_toutes_les_bandes_sans_exception():
    for idx in range(16):
        d = acom.acom_parse_telemetry(_frame(band_idx=idx))
        assert d['band'] == acom.BAND_NAMES[idx]


# ═══════════════════════════════════════════════════════════════════════════
#  Réglages
# ═══════════════════════════════════════════════════════════════════════════

def test_acom_settings_defaut_desactive():
    assert acom.acom_settings({})['enabled'] is False
    assert acom.acom_settings(None)['enabled'] is False


def test_acom_settings_modele_reconnu_normalise_en_majuscules():
    s = acom.acom_settings({'acom_model': '700s'})
    assert s['model'] == '700S'


def test_acom_settings_modele_inconnu_retombe_none():
    s = acom.acom_settings({'acom_model': 'ACOM-9999'})
    assert s['model'] is None


def test_acom_settings_borne_timeout_absurde():
    assert acom.acom_settings({'acom_timeout': 999999})['timeout'] == acom.MAX_TIMEOUT_S
    assert acom.acom_settings({'acom_timeout': -5})['timeout'] == acom.MIN_TIMEOUT_S
    assert acom.acom_settings({'acom_timeout': 5})['timeout'] == 5.0


# ═══════════════════════════════════════════════════════════════════════════
#  Faux transport série (interface AcomPort) + intégration
# ═══════════════════════════════════════════════════════════════════════════

class _FakeSerialPort:
    """Double MINIMAL de AcomPort — même interface (send_command/
    read_one_frame/close), sans jamais toucher pyserial ni un vrai port."""

    def __init__(self, device, baudrate, timeout, frames=None, fail_open=False):
        if fail_open:
            raise RuntimeError('port série introuvable (faux transport)')
        self.device, self.baudrate, self.timeout = device, baudrate, timeout
        self._frames = list(frames or [])
        self.sent = []
        self.closed = False

    def send_command(self, data):
        self.sent.append(data)

    def read_one_frame(self, timeout):
        if self._frames:
            return self._frames.pop(0)
        return None

    def close(self):
        self.closed = True


def _fresh():
    """Réinitialise l'état persistant du module entre les tests (même motif
    que _fresh() dans test_powergenius.py)."""
    acom.disconnect_persistent()


def test_get_state_disabled():
    _fresh()
    assert acom.get_state({}) == {'enabled': False}
    assert acom.get_state(None) == {'enabled': False}


def test_get_state_ok(monkeypatch):
    _fresh()
    frame = _frame(status=7, power=100, temp_raw=310)

    def factory(device, baudrate, timeout):
        return _FakeSerialPort(device, baudrate, timeout, frames=[frame])

    monkeypatch.setattr(acom, '_open_serial', factory)
    cfg = {'acom_enabled': True, 'acom_port': 'COM7', 'acom_model': '700S'}
    st = acom.get_state(cfg)
    assert st['ok'] is True and st['enabled'] is True
    assert st['status'] == 'TRANSMIT'
    assert st['power_w'] == 100
    assert st['temp_c'] == 310 - acom.ACOM_MODELS['700S']['temp_offset']
    _fresh()


def test_get_state_port_manquant():
    _fresh()
    cfg = {'acom_enabled': True, 'acom_port': ''}
    st = acom.get_state(cfg)
    assert st['ok'] is False
    assert 'port' in st['error'].lower()


def test_get_state_pas_de_telemetrie_dans_le_delai(monkeypatch):
    _fresh()

    def factory(device, baudrate, timeout):
        return _FakeSerialPort(device, baudrate, timeout, frames=[])

    monkeypatch.setattr(acom, '_open_serial', factory)
    cfg = {'acom_enabled': True, 'acom_port': 'COM7', 'acom_timeout': 1.0}
    st = acom.get_state(cfg)
    assert st['ok'] is False and st['enabled'] is True
    _fresh()


def test_set_operate_envoie_la_bonne_trame_pour_chaque_mode(monkeypatch):
    _fresh()
    created = []

    def factory(device, baudrate, timeout):
        p = _FakeSerialPort(device, baudrate, timeout)
        created.append(p)
        return p

    monkeypatch.setattr(acom, '_open_serial', factory)
    cfg = {'acom_enabled': True, 'acom_port': 'COM7'}
    for mode, cmd in (('operate', acom.CMD_OPERATE), ('standby', acom.CMD_STANDBY),
                       ('off', acom.CMD_OFF)):
        r = acom.set_operate(cfg, mode)
        assert r == {'ok': True, 'mode': mode}
    # même connexion persistante réutilisée pour les 3 appels (même port)
    assert len(created) == 1
    assert created[0].sent == [acom.CMD_OPERATE, acom.CMD_STANDBY, acom.CMD_OFF]
    _fresh()


def test_set_operate_mode_inconnu():
    _fresh()
    r = acom.set_operate({'acom_enabled': True, 'acom_port': 'COM7'}, 'turbo')
    assert r['ok'] is False and 'inconnu' in r['error'].lower()


def test_set_operate_desactive():
    _fresh()
    r = acom.set_operate({}, 'operate')
    assert r['ok'] is False and 'désactivé' in r['error']


def test_test_connection_ok():
    def factory(device, baudrate, timeout):
        return _FakeSerialPort(device, baudrate, timeout, frames=[_frame()])

    r = acom.test_connection('COM7', model='700S', opener=factory)
    assert r['ok'] is True
    assert r['telemetry']['model'] == '700S'


def test_test_connection_port_manquant():
    assert acom.test_connection('') == {'ok': False, 'error': 'Port série manquant'}


def test_test_connection_echec_ouverture():
    def factory(device, baudrate, timeout):
        raise RuntimeError('port série introuvable (faux transport)')

    r = acom.test_connection('COM7', opener=factory)
    assert r['ok'] is False


def test_test_connection_timeout():
    def factory(device, baudrate, timeout):
        return _FakeSerialPort(device, baudrate, timeout, frames=[])

    r = acom.test_connection('COM7', timeout=1.0, opener=factory)
    assert r['ok'] is False


def test_test_connection_ne_touche_pas_la_persistante(monkeypatch):
    """Même garantie que test_test_connection_ne_touche_pas_la_persistante()
    dans test_powergenius.py : le test éphémère (bouton CONFIG) doit ouvrir
    sa PROPRE connexion, jamais réutiliser/casser celle du polling logbook."""
    _fresh()
    created = []

    def factory(device, baudrate, timeout):
        p = _FakeSerialPort(device, baudrate, timeout, frames=[_frame()])
        created.append(p)
        return p

    monkeypatch.setattr(acom, '_open_serial', factory)
    cfg = {'acom_enabled': True, 'acom_port': 'COM7'}
    st1 = acom.get_state(cfg)
    assert st1['ok'] is True
    assert len(created) == 1

    r = acom.test_connection('COM7', opener=factory)
    assert r['ok'] is True
    assert len(created) == 2               # connexion éphémère séparée
    assert created[1].closed is True        # fermée après le test
    assert created[0].closed is False       # la persistante n'a jamais été touchée
    _fresh()


# ═══════════════════════════════════════════════════════════════════════════
#  AcomPort réel (pyserial mocké au niveau du constructeur sous-jacent) —
#  même patron que test_cat.py::_FakeUnderlyingSerial, pour exercer la
#  VRAIE classe (construction RTS/DTR bas, close() envoie bien
#  CMD_DISABLE_TELEMETRY) plutôt que le double _FakeSerialPort ci-dessus,
#  qui ne touche jamais pyserial et ne peut donc pas prouver ce comportement.
# ═══════════════════════════════════════════════════════════════════════════

class _FakeUnderlyingSerial:
    """Même interface minimale que serial.Serial() — aucun argument au
    constructeur, propriétés posées ensuite, comme le vrai pyserial 3.5
    (voir mémoire piege-pyserial-rts-dtr-constructeur)."""

    def __init__(self):
        self.port = None
        self.baudrate = None
        self.timeout = None
        self.bytesize = None
        self.parity = None
        self.stopbits = None
        self.rts = None
        self.dtr = None
        self.opened = False
        self.closed = False
        self.written = []
        self.in_waiting = 0

    def open(self):
        self.opened = True

    def close(self):
        self.closed = True

    def write(self, data):
        self.written.append(data)

    def read(self, n):
        return b''


def test_acom_port_construit_ferme_puis_pose_rts_dtr_bas(monkeypatch):
    """Reproduit test_cat.py::test_serialport_ouvre_avec_rts_dtr_bas pour
    AcomPort : construction fermée (port=None), propriétés posées, PUIS
    open() -- jamais rts=/dtr= en kwargs du constructeur (pyserial 3.5 les
    rejette, voir docstring du module)."""
    if not acom.HAS_PYSERIAL:
        import pytest
        pytest.skip("pyserial non installé dans cet environnement")
    fake = _FakeUnderlyingSerial()
    monkeypatch.setattr(acom._pyserial, 'Serial', lambda: fake)
    acom.AcomPort('COM99', baudrate=9600, timeout=1.0)
    assert fake.port == 'COM99'
    assert fake.baudrate == 9600
    assert fake.rts is False
    assert fake.dtr is False
    assert fake.opened is True


def test_acom_port_close_envoie_disable_telemetry_avant_de_fermer(monkeypatch):
    """Constat réel de la revue adversariale (09/08/2026) : CMD_DISABLE_
    TELEMETRY était défini mais jamais envoyé -- MainWindow_Closed() du vrai
    ACOM Controller l'envoie bien avant de fermer le port. Corrigé dans
    AcomPort.close() ; ce test prouve que le fix touche la VRAIE classe, pas
    seulement le double _FakeSerialPort (qui ne l'aurait jamais détecté)."""
    if not acom.HAS_PYSERIAL:
        import pytest
        pytest.skip("pyserial non installé dans cet environnement")
    fake = _FakeUnderlyingSerial()
    monkeypatch.setattr(acom._pyserial, 'Serial', lambda: fake)
    port = acom.AcomPort('COM99')
    port.close()
    assert fake.written == [acom.CMD_DISABLE_TELEMETRY]
    assert fake.closed is True


def test_acom_port_close_ignore_erreur_ecriture(monkeypatch):
    """Un port déjà en défaut ne doit pas empêcher la fermeture -- même
    prudence que le reste de close() (try/except déjà présent autour de
    self._ser.close())."""
    if not acom.HAS_PYSERIAL:
        import pytest
        pytest.skip("pyserial non installé dans cet environnement")

    class _BrokenWrite(_FakeUnderlyingSerial):
        def write(self, data):
            raise OSError('port déjà fermé côté OS')

    fake = _BrokenWrite()
    monkeypatch.setattr(acom._pyserial, 'Serial', lambda: fake)
    port = acom.AcomPort('COM99')
    port.close()   # ne doit lever aucune exception
    assert fake.closed is True
