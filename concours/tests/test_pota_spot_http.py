# -*- coding: utf-8 -*-
"""Tests HTTP de bout en bout pour POST /pota/spot (auto-spot POTA, cf.
logx_pota.post_spot) — même harnais que tests/test_http_scope_endpoints.py
(vrai serveur sur port éphémère). logx_pota.post_spot est monkeypatché : ces
tests couvrent le CÂBLAGE du handler (config -> arguments, repli
freq_mhz->freq_khz, référence par défaut, code HTTP selon le résultat), pas
le réseau (déjà couvert par tests/test_pota.py et tests/test_utils.py)."""
import http.server
import json
import os
import sys
import threading
import urllib.error
import urllib.request

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_http as httpmod
import logx_pota as pota


@pytest.fixture
def server():
    srv = http.server.HTTPServer(('127.0.0.1', 0), httpmod.Handler)
    port = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        yield f'http://127.0.0.1:{port}'
    finally:
        srv.shutdown()
        t.join(timeout=5)


def _post(base, path, payload):
    body = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(
        base + path, data=body, method='POST',
        headers={'Content-Type': 'application/json',
                 'X-RC-Token': httpmod.AUTH_TOKEN})
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, json.loads(r.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode('utf-8'))


def test_indicatif_manquant_rejete_avant_pota(server, monkeypatch):
    """Sans indicatif configuré, aucun appel à pota.post_spot (le mock lève)."""
    monkeypatch.setattr(httpmod, 'current_config', {'callsign': '', 'contest': ''})
    monkeypatch.setattr(pota, 'post_spot', lambda *a, **k: (_ for _ in ()).throw(
        AssertionError('post_spot ne doit pas être appelé')))
    status, d = _post(server, '/pota/spot', {'reference': 'FR-0123', 'freq_khz': 14285, 'mode': 'SSB'})
    assert status == 400 and d['ok'] is False and 'Indicatif' in d['error']


def test_reference_par_defaut_depuis_la_config(server, monkeypatch):
    """Le body n'envoie pas de référence -> repli sur my_activation_ref (la
    référence actuellement activée), comme /cluster/spot replie sur l'indicatif
    de connexion plutôt que d'exiger que le client la retape à chaque appel."""
    monkeypatch.setattr(httpmod, 'current_config',
                        {'callsign': 'F4GLD', 'contest': '', 'my_activation_ref': 'FR-0123'})
    captured = {}
    def fake_post_spot(activator, reference, freq_khz, mode, spotter='', comment=''):
        captured.update(activator=activator, reference=reference, freq_khz=freq_khz,
                        mode=mode, spotter=spotter)
        return {'ok': True, 'response': 'ok'}
    monkeypatch.setattr(pota, 'post_spot', fake_post_spot)

    status, d = _post(server, '/pota/spot', {'freq_khz': 14285, 'mode': 'SSB'})
    assert status == 200 and d['ok'] is True
    assert captured == {'activator': 'F4GLD', 'reference': 'FR-0123', 'freq_khz': 14285,
                        'mode': 'SSB', 'spotter': 'F4GLD'}


def test_freq_mhz_converti_en_khz(server, monkeypatch):
    monkeypatch.setattr(httpmod, 'current_config', {'callsign': 'F4GLD', 'contest': ''})
    captured = {}
    def fake_post_spot(activator, reference, freq_khz, mode, spotter='', comment=''):
        captured['freq_khz'] = freq_khz
        return {'ok': True}
    monkeypatch.setattr(pota, 'post_spot', fake_post_spot)

    status, d = _post(server, '/pota/spot',
                      {'reference': 'FR-0123', 'freq_mhz': 14.285, 'mode': 'SSB'})
    assert status == 200
    assert captured['freq_khz'] == pytest.approx(14285.0)


def test_echec_pota_remonte_en_502(server, monkeypatch):
    monkeypatch.setattr(httpmod, 'current_config',
                        {'callsign': 'F4GLD', 'contest': '', 'my_activation_ref': 'FR-0123'})
    monkeypatch.setattr(pota, 'post_spot',
                        lambda *a, **k: {'ok': False, 'error': 'api.pota.app injoignable (réseau)'})

    status, d = _post(server, '/pota/spot', {'freq_khz': 14285, 'mode': 'SSB'})
    assert status == 502 and d['ok'] is False and 'injoignable' in d['error']


def test_callsign_contest_prioritaire_sur_callsign(server, monkeypatch):
    """Comme les autres routes (cf. logx_http.py, callsign_contest partout) :
    en mode CONCOURS, l'indicatif du concours prime sur l'indicatif de base."""
    monkeypatch.setattr(httpmod, 'current_config',
                        {'callsign': 'F4GLD', 'callsign_contest': 'F4GLD/P',
                         'contest': '', 'my_activation_ref': 'FR-0123'})
    captured = {}
    def fake_post_spot(activator, reference, freq_khz, mode, spotter='', comment=''):
        captured['activator'] = activator
        captured['spotter'] = spotter
        return {'ok': True}
    monkeypatch.setattr(pota, 'post_spot', fake_post_spot)

    _post(server, '/pota/spot', {'freq_khz': 14285, 'mode': 'SSB'})
    assert captured['activator'] == 'F4GLD/P' and captured['spotter'] == 'F4GLD/P'
