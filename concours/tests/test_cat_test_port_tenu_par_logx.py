# -*- coding: utf-8 -*-
"""« Tester la connexion » / « Auto-détecter » sur un port que LogX AI tient déjà.

Signalé par F4GLD le 24/10/2026 (COM20) : « je n'ai que mon poste de connecté
au PC et que LogX AI en route » — et pourtant « COM20 est déjà utilisé par un
AUTRE programme … PermissionError(13, 'Accès refusé.') ».

Cause : test_connection() ouvrait une DEUXIÈME fois le port déjà tenu par la
connexion persistante de LogX AI (lecture de fréquence). Sous Windows un port
COM ne s'ouvre qu'une fois. Sous Linux la double ouverture passe : la CI ne
pouvait pas le voir. Ces tests utilisent donc un double de port qui applique
la règle WINDOWS (exclusivité), sinon ils seraient verts par construction."""
import os
import sys
import threading

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, CONCOURS)

import pytest  # noqa: E402

import logx_cat as cat  # noqa: E402


class PortExclusifWindows:
    """Double de SerialPort : un seul « handle » ouvert par port, comme Windows."""
    ouverts = {}            # 'COM20' -> instance
    ouvertures = []

    def __init__(self, device, baudrate=19200, timeout=1.0):
        cle = device.upper()
        if cle in PortExclusifWindows.ouverts:
            raise OSError("could not open port '%s': PermissionError(13, 'Accès refusé.', None, 5)"
                          % device)
        self.device, self.baudrate, self.ferme = device, baudrate, False
        self.rts = self.dtr = False
        PortExclusifWindows.ouverts[cle] = self
        PortExclusifWindows.ouvertures.append(device)

    def regler_ligne(self, ligne, actif, attente=1.0):
        setattr(self, ligne, bool(actif))
        return True

    def baisser_lignes(self, attente=0.3):
        self.rts = self.dtr = False
        return True

    def close(self):
        if not self.ferme:
            self.ferme = True
            PortExclusifWindows.ouverts.pop(self.device.upper(), None)

    def transceive(self, *a, **k):
        return b''

    def write(self, *a, **k):
        pass

    def read(self, *a, **k):
        return b''


SETTINGS = {'enabled': True, 'mode': 'native', 'port': 'COM20', 'brand': 'icom',
            'model': 'IC-7300', 'baudrate': 19200, 'civ_addr': 0x94}


@pytest.fixture(autouse=True)
def _etat_neuf(monkeypatch):
    PortExclusifWindows.ouverts = {}
    PortExclusifWindows.ouvertures = []
    monkeypatch.setattr(cat, '_open_serial', PortExclusifWindows)
    monkeypatch.setattr(cat, '_retry_sleep', lambda s: None)
    cat.disconnect_persistent()
    yield
    cat.disconnect_persistent()
    with cat._persistent_lock:
        cat._ports_reserves_test.clear()


def _logx_tient_le_port():
    driver, err = cat._ensure_connected(dict(SETTINGS))
    assert err is None and driver is not None
    assert 'COM20' in PortExclusifWindows.ouverts       # LogX AI tient bien COM20


def test_le_double_applique_bien_la_regle_windows():
    """Témoin : sans quoi les tests ci-dessous seraient vacants."""
    PortExclusifWindows('COM20')
    with pytest.raises(OSError):
        PortExclusifWindows('COM20')


def test_tester_la_connexion_n_accuse_plus_un_autre_programme():
    _logx_tient_le_port()
    res = cat.test_connection('icom', 'IC-7300', 'COM20', 19200)
    err = res.get('error') or ''
    assert 'AUTRE programme' not in err and 'PermissionError' not in err, err
    # Le test a vraiment ouvert le port (2e ouverture réussie, après libération)
    assert PortExclusifWindows.ouvertures.count('COM20') == 2


def test_la_lecture_de_frequence_reprend_apres_le_test():
    _logx_tient_le_port()
    cat.test_connection('icom', 'IC-7300', 'COM20', 19200)
    assert 'COM20' not in PortExclusifWindows.ouverts      # le test a bien refermé
    driver, err = cat._ensure_connected(dict(SETTINGS))     # prochain polling
    assert err is None and driver is not None
    assert 'COM20' in PortExclusifWindows.ouverts


def test_le_polling_ne_reprend_pas_le_port_pendant_le_test(monkeypatch):
    """Un appel de polling qui tombe PENDANT le test ne doit pas rouvrir le
    port (sinon le test échouerait à son tour, ou lui volerait le port)."""
    _logx_tient_le_port()
    pendant = {}

    def get_freq_espion(self):
        t = threading.Thread(target=lambda: pendant.update(
            r=cat._ensure_connected(dict(SETTINGS))))
        t.start(); t.join(5)
        return {'ok': True, 'freq_hz': 14074000}

    monkeypatch.setattr(cat.CivRadio, 'get_freq', get_freq_espion)
    res = cat.test_connection('icom', 'IC-7300', 'COM20', 19200)
    assert res.get('ok'), res
    driver, err = pendant['r']
    assert driver is None and 'test' in err.lower()
    assert 'AUTRE programme' not in err


def test_un_autre_port_n_est_pas_touche():
    _logx_tient_le_port()
    cat.test_connection('icom', 'IC-7300', 'COM7', 19200)
    assert 'COM20' in PortExclusifWindows.ouverts          # la connexion de COM20 est intacte


def test_un_vrai_autre_programme_est_toujours_signale():
    """Si c'est VRAIMENT un autre logiciel qui tient le port, le message reste."""
    PortExclusifWindows('COM20')                            # « WSJT-X » tient COM20
    res = cat.test_connection('icom', 'IC-7300', 'COM20', 19200)
    assert 'AUTRE programme' in (res.get('error') or '')


def test_auto_detecter_meme_correctif():
    _logx_tient_le_port()
    res = cat.autodetect_scan('COM20', bauds=[19200])
    err = res.get('error') or ''
    assert 'AUTRE programme' not in err and 'PermissionError' not in err, err
