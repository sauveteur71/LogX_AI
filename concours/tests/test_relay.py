# -*- coding: utf-8 -*-
"""Tests du panneau Station Control (logx_relay) — série (KMTronic/Denkovi/
générique) et WebSwitch (HTTP), avec transport/urlopen INJECTÉS (jamais de
vrai port série ni de vraie requête réseau)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_relay as relay


class FakeSerial:
    """Capture les octets écrits, sans jamais toucher un vrai port."""
    instances = []

    def __init__(self, port, baudrate=9600):
        self.port = port
        self.baudrate = baudrate
        self.written = []
        self.closed = False
        FakeSerial.instances.append(self)

    def write(self, data):
        self.written.append(bytes(data))

    def close(self):
        self.closed = True


class FailingSerial:
    def __init__(self, port, baudrate=9600):
        raise OSError('port introuvable')


class FakeResponse:
    def __init__(self, status=200):
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def fake_urlopen_factory(calls, status=200, raise_exc=None):
    def _urlopen(req, timeout=None):
        calls.append({'url': req.full_url, 'headers': dict(req.header_items())})
        if raise_exc:
            raise raise_exc
        return FakeResponse(status)
    return _urlopen


def _reset():
    FakeSerial.instances.clear()
    relay._auto_state['last_band'] = None


# ─── relay_settings() ───────────────────────────────────────────────────────

def test_relay_settings_defauts_surs():
    s = relay.relay_settings({})
    assert s['enabled'] is False
    assert s['kind'] == 'kmtronic_serial'
    assert s['baud'] == 9600
    assert s['relay_count'] == 4
    assert s['auto_band_enabled'] is False
    assert s['band_map'] == {}


def test_relay_settings_parse_band_map_tolerant():
    s = relay.relay_settings({'relay_band_map': {'14': 1, '7': '2', 'x': 'oops', '3.5': None}})
    # '14'->1 et '7'->'2' (coercition str->int) gardés ; 'x' et '3.5'(None) rejetés.
    assert s['band_map'] == {'14': 1, '7': 2}


def test_relay_settings_enabled_variantes():
    for v in ('1', 'true', 'True', 'on'):
        assert relay.relay_settings({'relay_enabled': v})['enabled'] is True
    assert relay.relay_settings({'relay_enabled': ''})['enabled'] is False
    assert relay.relay_settings({'relay_enabled': '0'})['enabled'] is False


# ─── set_relay() — série ────────────────────────────────────────────────────

def test_set_relay_serial_on_envoie_les_3_octets_kmtronic():
    _reset()
    cfg = {'relay_kind': 'kmtronic_serial', 'relay_port': 'COM5', 'relay_baud': 19200}
    r = relay.set_relay(cfg, 3, True, open_serial=FakeSerial)
    assert r['ok']
    ser = FakeSerial.instances[0]
    assert ser.port == 'COM5' and ser.baudrate == 19200
    assert ser.written == [bytes([0xFF, 3, 0x01])]
    assert ser.closed   # le port est refermé après chaque commande


def test_set_relay_serial_off():
    _reset()
    cfg = {'relay_kind': 'kmtronic_serial', 'relay_port': 'COM5'}
    relay.set_relay(cfg, 2, False, open_serial=FakeSerial)
    assert FakeSerial.instances[0].written == [bytes([0xFF, 2, 0x00])]


def test_set_relay_serial_sans_port_configure():
    _reset()
    r = relay.set_relay({'relay_kind': 'kmtronic_serial', 'relay_port': ''}, 1, True, open_serial=FakeSerial)
    assert not r['ok'] and 'port' in r['error'].lower()
    assert not FakeSerial.instances   # jamais tenté d'ouvrir


def test_set_relay_serial_echec_ouverture_ne_leve_pas():
    _reset()
    r = relay.set_relay({'relay_kind': 'kmtronic_serial', 'relay_port': 'COM9'}, 1, True,
                        open_serial=FailingSerial)
    assert not r['ok'] and 'introuvable' in r['error']


# ─── set_relay() — WebSwitch ────────────────────────────────────────────────

def test_set_relay_webswitch_url_et_auth():
    _reset()
    calls = []
    cfg = {'relay_kind': 'webswitch', 'relay_host': '192.168.1.60',
           'relay_user': 'admin', 'relay_password': 'secret'}
    r = relay.set_relay(cfg, 4, True, urlopen=fake_urlopen_factory(calls))
    assert r['ok']
    assert calls[0]['url'] == 'http://192.168.1.60/outlet?4=ON'
    assert calls[0]['headers'].get('Authorization', '').startswith('Basic ')


def test_set_relay_webswitch_off():
    calls = []
    cfg = {'relay_kind': 'webswitch', 'relay_host': '192.168.1.60'}
    relay.set_relay(cfg, 4, False, urlopen=fake_urlopen_factory(calls))
    assert calls[0]['url'] == 'http://192.168.1.60/outlet?4=OFF'


def test_set_relay_webswitch_sans_host():
    r = relay.set_relay({'relay_kind': 'webswitch', 'relay_host': ''}, 1, True,
                        urlopen=fake_urlopen_factory([]))
    assert not r['ok']


def test_set_relay_webswitch_erreur_reseau():
    r = relay.set_relay({'relay_kind': 'webswitch', 'relay_host': '10.0.0.5'}, 1, True,
                        urlopen=fake_urlopen_factory([], raise_exc=OSError('injoignable')))
    assert not r['ok'] and 'injoignable' in r['error']


# ─── test_connection() — ne bascule JAMAIS de relais ────────────────────────

def test_connection_serial_ouvre_et_ferme_sans_ecrire():
    _reset()
    r = relay.test_connection({'relay_kind': 'kmtronic_serial', 'relay_port': 'COM5'},
                              open_serial=FakeSerial)
    assert r['ok']
    ser = FakeSerial.instances[0]
    assert ser.written == []   # AUCUNE commande de commutation envoyée
    assert ser.closed


def test_connection_webswitch_ne_touche_pas_un_outlet():
    calls = []
    relay.test_connection({'relay_kind': 'webswitch', 'relay_host': '192.168.1.60'},
                          urlopen=fake_urlopen_factory(calls))
    assert calls[0]['url'] == 'http://192.168.1.60/'   # pas de "?outlet="


# ─── apply_band_relay() — commutateur exclusif ──────────────────────────────

def test_apply_band_relay_active_le_bon_coupe_les_autres():
    _reset()
    calls = []
    cfg = {'relay_enabled': '1', 'relay_auto_band': '1', 'relay_kind': 'webswitch',
           'relay_host': 'h', 'relay_band_map': {'14': 1, '7': 2, '3.5': 3}}
    r = relay.apply_band_relay(cfg, '14', urlopen=fake_urlopen_factory(calls))
    assert r['ok'] and r['activated'] == 1
    urls = sorted(c['url'] for c in calls)
    assert urls == ['http://h/outlet?1=ON', 'http://h/outlet?2=OFF', 'http://h/outlet?3=OFF']


def test_apply_band_relay_bande_non_mappee():
    cfg = {'relay_enabled': '1', 'relay_auto_band': '1',
           'relay_band_map': {'14': 1}}
    r = relay.apply_band_relay(cfg, '432', urlopen=fake_urlopen_factory([]))
    assert not r['ok']


def test_apply_band_relay_desactive():
    cfg = {'relay_enabled': '', 'relay_auto_band': '1', 'relay_band_map': {'14': 1}}
    r = relay.apply_band_relay(cfg, '14', urlopen=fake_urlopen_factory([]))
    assert not r['ok']


# ─── maybe_apply_band() — dédupliqué, ne rejoue pas à chaque poll ──────────

def test_maybe_apply_band_ne_rejoue_pas_la_meme_bande():
    _reset()
    calls = []
    cfg = {'relay_enabled': '1', 'relay_auto_band': '1', 'relay_kind': 'webswitch',
           'relay_host': 'h', 'relay_band_map': {'14': 1, '7': 2}}
    r1 = relay.maybe_apply_band(cfg, '14', urlopen=fake_urlopen_factory(calls))
    assert r1['ok'] and not r1.get('skipped')
    n_apres_premier = len(calls)
    r2 = relay.maybe_apply_band(cfg, '14', urlopen=fake_urlopen_factory(calls))
    assert r2.get('skipped') is True
    assert len(calls) == n_apres_premier   # AUCUN appel réseau supplémentaire


def test_maybe_apply_band_rejoue_si_la_bande_change():
    _reset()
    calls = []
    cfg = {'relay_enabled': '1', 'relay_auto_band': '1', 'relay_kind': 'webswitch',
           'relay_host': 'h', 'relay_band_map': {'14': 1, '7': 2}}
    relay.maybe_apply_band(cfg, '14', urlopen=fake_urlopen_factory(calls))
    n_apres_premier = len(calls)
    r2 = relay.maybe_apply_band(cfg, '7', urlopen=fake_urlopen_factory(calls))
    assert not r2.get('skipped')
    assert len(calls) > n_apres_premier
