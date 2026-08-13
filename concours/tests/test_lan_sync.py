# -*- coding: utf-8 -*-
"""Synchro LAN directe (logx_lan_sync) : registre de pairs (beacon + TTL) et
tirage/fusion HTTP contre un FAUX poste pair. Jamais de vraie diffusion UDP ici
— on teste la logique, pas la couche réseau broadcast."""
import http.server
import json
import os
import sys
import threading
import time

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CONCOURS not in sys.path:
    sys.path.insert(0, CONCOURS)

import logx_lan_sync as lan   # noqa: E402


@pytest.fixture(autouse=True)
def _reset(monkeypatch):
    # iid stable et connu -> on peut fabriquer « notre » beacon et celui d'un pair
    monkeypatch.setattr(lan, '_my_iid', lambda: 'MOI')
    with lan._peers_lock:
        lan._peers.clear()
    yield
    with lan._peers_lock:
        lan._peers.clear()


def _beacon(iid, port, call='F4ABC'):
    return json.dumps({'logx': 1, 'iid': iid, 'http_port': port, 'call': call}).encode()


# ─── Registre de pairs ───────────────────────────────────────────────────────

def test_note_beacon_enregistre_un_pair():
    lan.note_beacon('192.168.1.42', _beacon('AUTRE', 8080))
    p = lan.peers()
    assert len(p) == 1 and p[0]['ip'] == '192.168.1.42'
    assert p[0]['http_port'] == 8080 and p[0]['callsign'] == 'F4ABC'


def test_note_beacon_ignore_le_notre():
    lan.note_beacon('192.168.1.10', _beacon('MOI', 8080))
    assert lan.peers() == []


def test_note_beacon_ignore_le_bruit():
    lan.note_beacon('10.0.0.9', b'pas du json')
    lan.note_beacon('10.0.0.9', json.dumps({'autre_appli': 1}).encode())
    assert lan.peers() == []


def test_peers_purge_le_ttl(monkeypatch):
    lan.note_beacon('192.168.1.5', _beacon('AUTRE', 8080))
    assert len(lan.peers()) == 1
    # Vieillit l'entrée au-delà du TTL
    with lan._peers_lock:
        lan._peers['192.168.1.5']['last_seen'] = time.time() - lan.PEER_TTL_S - 5
    assert lan.peers() == []


# ─── Tirage + fusion contre un faux poste pair ──────────────────────────────

class _FakePeerHandler(http.server.BaseHTTPRequestHandler):
    QSOS = []

    def do_GET(self):
        if self.path == '/log/lan/export':
            body = json.dumps({'enabled': True, 'iid': 'AUTRE',
                               'qsos': self.QSOS}).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, *a):
        pass


@pytest.fixture
def fake_peer():
    _FakePeerHandler.QSOS = [
        {'call': 'DL1ABC', 'band': '20', 'mode': 'SSB', 'date': '20260101', 'time': '1200'},
        {'call': 'EA7XYZ', 'band': '40', 'mode': 'CW', 'date': '20260101', 'time': '1230'},
    ]
    srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), _FakePeerHandler)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield port
    srv.shutdown()


def test_pull_and_merge_tire_les_qso_neufs(fake_peer):
    lan.note_beacon('127.0.0.1', _beacon('AUTRE', fake_peer))
    ajoutes = []
    r = lan.pull_and_merge(lambda: [], lambda q: (ajoutes.append(q) or True))
    assert r['peers'] == 1 and r['pulled'] == 2
    assert {q['call'] for q in ajoutes} == {'DL1ABC', 'EA7XYZ'}


def test_pull_and_merge_saute_ce_qu_on_a_deja(fake_peer):
    lan.note_beacon('127.0.0.1', _beacon('AUTRE', fake_peer))
    deja = [{'call': 'DL1ABC', 'band': '20', 'mode': 'SSB', 'date': '20260101', 'time': '1200'}]
    ajoutes = []
    r = lan.pull_and_merge(lambda: deja, lambda q: (ajoutes.append(q) or True))
    # Un seul QSO neuf tiré (EA7XYZ) — DL1ABC est déjà dans notre log.
    assert r['pulled'] == 1 and [q['call'] for q in ajoutes] == ['EA7XYZ']


def test_pull_and_merge_sans_pair_ne_fait_rien():
    r = lan.pull_and_merge(lambda: [], lambda q: True)
    assert r == {'peers': 0, 'pulled': 0}


def test_pull_and_merge_ne_ressuscite_pas_un_qso_supprime_localement(fake_peer, monkeypatch):
    # DL1ABC porte l'id 1 chez le pair distant, et CE poste vient de le
    # supprimer via /log/delete (donc il n'est plus dans get_log(), mais son
    # id est resté sous tombstone dans logx_storage.deleted_qsos). Le pair ne
    # le sait pas encore et le repropose au cycle suivant : il ne doit pas
    # ressusciter.
    _FakePeerHandler.QSOS = [
        {'id': 1, 'call': 'DL1ABC', 'band': '20', 'mode': 'SSB',
         'date': '20260101', 'time': '1200'},
        {'id': 2, 'call': 'EA7XYZ', 'band': '40', 'mode': 'CW',
         'date': '20260101', 'time': '1230'},
    ]
    import logx_storage as storage
    monkeypatch.setattr(storage, 'deleted_qsos', [{'id': 1, 'v': 1}])
    lan.note_beacon('127.0.0.1', _beacon('AUTRE', fake_peer))
    ajoutes = []
    r = lan.pull_and_merge(lambda: [], lambda q: (ajoutes.append(q) or True))
    # Seul EA7XYZ (non supprimé) est tiré ; DL1ABC reste écarté malgré
    # l'absence de doublon dans get_log().
    assert r['pulled'] == 1
    assert [q['call'] for q in ajoutes] == ['EA7XYZ']
