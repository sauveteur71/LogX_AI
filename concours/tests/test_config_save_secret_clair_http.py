# -*- coding: utf-8 -*-
"""Audit BASSE 612 (câblage HTTP) : quand un secret n'a pas pu être chiffré et a
été écrit EN CLAIR, /config/save doit remonter un avertissement VISIBLE dans sa
réponse (le client l'affiche en toast). Harnais serveur réel sur port éphémère,
comme tests/test_pota_export_adif_http.py — sans jamais écrire la vraie config."""
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
import logx_crypto as crypto


@pytest.fixture
def server():
    srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), httpmod.Handler)
    port = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        yield f'http://127.0.0.1:{port}'
    finally:
        srv.shutdown()
        srv.server_close()
        t.join(timeout=5)


def _post(base, path, payload):
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(
        base + path, data=data, method='POST',
        headers={'X-RC-Token': httpmod.AUTH_TOKEN, 'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, r.read().decode('utf-8')
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode('utf-8')


def _sans_ecriture_disque(monkeypatch):
    # _save_config_to_disk déclenche le chiffrement (donc le flag d'échec) SANS
    # écrire le vrai .server_config.json pendant le test.
    monkeypatch.setattr(httpmod, '_save_config_to_disk',
                        lambda cfg: crypto.encrypt_config(cfg))


def test_echec_chiffrement_remonte_un_avertissement(server, monkeypatch):
    _sans_ecriture_disque(monkeypatch)
    # Force un échec réel de chiffrement (lib « présente », clé illisible).
    monkeypatch.setattr(crypto, 'HAS_CRYPTOGRAPHY', True)
    monkeypatch.setattr(crypto, '_load_or_create_key',
                        lambda: (_ for _ in ()).throw(RuntimeError('clé illisible')))
    status, body = _post(server, '/config/save',
                         {'callsign': 'F4TEST', 'qrz_password': 'motdepasse'})
    assert status == 200
    data = json.loads(body)
    assert data.get('ok') is True
    assert 'secret_clair_avertissement' in data, "l'écriture en clair doit être signalée"
    assert 'CLAIR' in data['secret_clair_avertissement']


def test_chiffrement_ok_pas_d_avertissement(server, monkeypatch):
    _sans_ecriture_disque(monkeypatch)
    crypto.reset_key_cache()
    # Chiffrement réussi (ou lib absente = dégradation connue, non alarmante) :
    # aucun avertissement d'écriture-en-clair-par-échec.
    status, body = _post(server, '/config/save',
                         {'callsign': 'F4TEST', 'qrz_password': 'motdepasse'})
    assert status == 200
    data = json.loads(body)
    assert 'secret_clair_avertissement' not in data
