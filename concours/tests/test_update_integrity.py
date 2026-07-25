# -*- coding: utf-8 -*-
"""Vérification d'intégrité (SHA-256) du mécanisme de mise à jour + les 3
chemins de téléchargement — voir logx_update.py (docstring du module pour le
compromis de sécurité retenu) :
  A) direct depuis GitHub (_do_download)
  B) via une passerelle réseau (chemin prioritaire, _do_download_via_network
     mode='gateway', relayé par /app/update_relay)
  C) via un pair local — SECOURS uniquement (_do_download_via_network
     mode='peer', servi par /app/update_serve)

Chaque chemin est couvert pour le cas NOMINAL (hash correct → accepté) ET le
cas hash invalide (→ refusé, rien n'est jamais accepté à l'aveugle). Les
téléchargements sont STREAMÉS (voir _CHUNK dans logx_update.py) : les tests
n'ont pas besoin de vérifier ça directement (pas de moyen simple de
l'observer depuis l'extérieur), seul le comportement — refus/acceptation —
est testé ici."""
import hashlib
import http.server
import json
import os
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_http as httpmod
import logx_update as upd


# ─── Fixtures communes ────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _isolate_download_state(monkeypatch, tmp_path):
    """État module-level (_download, _cache) remis à neuf à chaque test —
    sinon un test précédent (téléchargement 'done') fausserait le suivant.
    user_data_dir() redirigé vers tmp_path : jamais d'écriture dans le vrai
    dossier APPDATA/LogXAI pendant les tests (même pattern que
    tests/test_shortcut.py)."""
    monkeypatch.setattr(upd, '_download', {
        'status': 'idle', 'pct': 0, 'error': '', 'path': '',
        'verified': False, 'sha256': '', 'version': '',
        'via': 'direct', 'via_peer': '',
    })
    monkeypatch.setattr(upd, '_cache', {'ts': 0, 'result': None})
    monkeypatch.setattr(upd, 'user_data_dir', lambda: str(tmp_path))
    yield


def _wait_download_terminal(timeout=5):
    """Attend que _download sorte de l'état 'downloading' (thread de fond de
    start_download/start_download_via_network)."""
    start = time.time()
    while time.time() - start < timeout:
        st = upd.get_download_status()
        if st['status'] in ('done', 'error'):
            return st
        time.sleep(0.02)
    raise TimeoutError('téléchargement non terminé dans le délai imparti')


def _sha256(data):
    return hashlib.sha256(data).hexdigest()


# ═══ A) _parse_digest / _build_result : extraction depuis l'API GitHub ═══════

def test_parse_digest_valide():
    hexpart = 'a' * 64
    assert upd._parse_digest(f'sha256:{hexpart}') == hexpart


def test_parse_digest_algo_different_rejete():
    """Un digest sha1 (plus faible) ou tout algo non-sha256 doit être traité
    comme ABSENT — jamais une fausse confiance sur un algorithme plus faible."""
    assert upd._parse_digest('sha1:' + 'a' * 40) is None


def test_parse_digest_format_invalide_rejete():
    assert upd._parse_digest('sha256:pastoutafaithex') is None
    assert upd._parse_digest('') is None
    assert upd._parse_digest(None) is None


def test_build_result_extrait_sha256_size_tag(monkeypatch):
    monkeypatch.setattr(upd, '_platform_key', lambda: 'win')
    digest_hex = 'b' * 64
    data = {
        'tag_name': 'v1.2.3', 'html_url': '', 'body': '',
        'assets': [{'name': 'LogXAI-v1.2.3.exe', 'browser_download_url': 'https://x/win.exe',
                    'size': 12345, 'digest': f'sha256:{digest_hex}'}],
    }
    result = upd._build_result(data)
    assert result['tag'] == 'v1.2.3'
    assert result['asset_sha256'] == digest_hex
    assert result['asset_size'] == 12345


def test_build_result_digest_absent_champ_vide(monkeypatch):
    """Asset sans digest exposé par l'API : asset_sha256 doit rester vide —
    c'est ce qui déclenche le refus dans _do_download, jamais un défaut
    silencieux vers 'accepté'."""
    monkeypatch.setattr(upd, '_platform_key', lambda: 'win')
    data = {'tag_name': 'v1.2.3', 'html_url': '', 'body': '',
            'assets': [{'name': 'LogXAI-v1.2.3.exe', 'browser_download_url': 'https://x/win.exe',
                        'size': 12345}]}
    result = upd._build_result(data)
    assert result['asset_sha256'] == ''


# ═══ verify_file_sha256 (streamé, réutilisé par les 3 chemins) ═══════════════

def test_verify_file_sha256_ok(tmp_path):
    p = tmp_path / 'f.bin'
    p.write_bytes(b'contenu de test' * 1000)
    assert upd.verify_file_sha256(str(p), _sha256(p.read_bytes())) is True


def test_verify_file_sha256_mismatch(tmp_path):
    p = tmp_path / 'f.bin'
    p.write_bytes(b'contenu de test')
    assert upd.verify_file_sha256(str(p), 'f' * 64) is False


def test_verify_file_sha256_sans_reference_refuse(tmp_path):
    p = tmp_path / 'f.bin'
    p.write_bytes(b'x')
    assert upd.verify_file_sha256(str(p), '') is False


# ═══ A) Téléchargement DIRECT (_do_download) ═════════════════════════════════

class _FakeResp:
    """Contexte simulant urllib.request.urlopen() pour _do_download — expose
    .headers.get / .read(n) comme la vraie réponse, sans vrai réseau."""
    def __init__(self, data):
        self._data = data
        self._pos = 0
        self.headers = {'Content-Length': str(len(data))}

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self, n):
        chunk = self._data[self._pos:self._pos + n]
        self._pos += len(chunk)
        return chunk


def test_do_download_nominal_verifie(monkeypatch, tmp_path):
    data = b'contenu-exe-simule' * 500
    digest = _sha256(data)
    monkeypatch.setattr(upd.urllib.request, 'urlopen', lambda *a, **k: _FakeResp(data))
    upd._do_download('https://x/LogXAI-v1.exe', digest, len(data))
    st = upd.get_download_status()
    assert st['status'] == 'done'
    assert st['verified'] is True
    assert st['sha256'] == digest
    assert os.path.exists(st['path'])


def test_do_download_hash_invalide_refuse(monkeypatch, tmp_path):
    data = b'contenu-exe-simule' * 500
    wrong_digest = 'a' * 64
    monkeypatch.setattr(upd.urllib.request, 'urlopen', lambda *a, **k: _FakeResp(data))
    upd._do_download('https://x/LogXAI-v1.exe', wrong_digest, len(data))
    st = upd.get_download_status()
    assert st['status'] == 'error'
    assert st['verified'] is False
    assert not st['path']
    # Rien ne doit rester sur disque (ni .part, ni fichier final) — voir
    # nettoyage dans _do_download.
    leftovers = list((tmp_path / 'update').glob('*')) if (tmp_path / 'update').exists() else []
    assert leftovers == []


def test_do_download_sans_reference_refuse_sans_reseau(monkeypatch):
    """Aucun digest de référence connu : refus IMMÉDIAT, sans même tenter la
    moindre requête réseau (voir docstring du module — 'REFUSER plutôt que
    faire confiance aveugle')."""
    called = []
    monkeypatch.setattr(upd.urllib.request, 'urlopen', lambda *a, **k: called.append(1) or _FakeResp(b'x'))
    upd._do_download('https://x/LogXAI-v1.exe', '', 0)
    st = upd.get_download_status()
    assert st['status'] == 'error'
    assert not called, "aucune requête réseau ne doit être tentée sans référence de hash"


# ═══ resolve_relay_asset / gateway_status (chemin B, côté passerelle) ═══════

def test_resolve_relay_asset_tag_invalide():
    upd._cache.update({'ts': time.time(), 'result': {'x': 1}})
    ok, msg = upd.resolve_relay_asset('; rm -rf /', 'win')
    assert ok is False
    assert 'tag' in msg.lower()


def test_resolve_relay_asset_platform_invalide():
    upd._cache.update({'ts': time.time(), 'result': {'x': 1}})
    ok, msg = upd.resolve_relay_asset('v1.0', 'bogus-os')
    assert ok is False


def test_resolve_relay_asset_refuse_sans_internet_confirme():
    """Ce poste n'a pas de contact GitHub récent en cache : ne peut pas se
    déclarer passerelle, même pour un tag/plateforme valides."""
    upd._cache.update({'ts': 0, 'result': None})
    ok, msg = upd.resolve_relay_asset('v1.0', 'win')
    assert ok is False


def test_resolve_relay_asset_nominal_construit_url_officielle():
    upd._cache.update({'ts': time.time(), 'result': {'x': 1}})
    ok, info = upd.resolve_relay_asset('v0.9-beta3', 'win')
    assert ok is True
    assert info['asset_url'] == (
        f'https://github.com/{upd.GITHUB_REPO}/releases/download/v0.9-beta3/LogXAI-v0.9-beta3.exe')


def test_gateway_status_frais_vs_perime():
    upd._cache.update({'ts': time.time(), 'result': {'x': 1}})
    assert upd.gateway_status()['gateway_available'] is True
    upd._cache.update({'ts': time.time() - upd.CHECK_TTL - 10, 'result': {'x': 1}})
    assert upd.gateway_status()['gateway_available'] is False


# ═══ serve_status (chemin C, côté pair qui sert le fichier) ═════════════════

def test_serve_status_rien_disponible():
    st = upd.serve_status()
    assert st['available'] is False


def test_serve_status_disponible_apres_verification(tmp_path):
    p = tmp_path / 'LogXAI-v1.exe'
    p.write_bytes(b'binaire-verifie')
    upd._download.update(status='done', verified=True, path=str(p),
                          sha256=_sha256(p.read_bytes()), version='v1')
    st = upd.serve_status()
    assert st['available'] is True
    assert st['version'] == 'v1'
    assert st['size'] == len(b'binaire-verifie')


def test_serve_status_faux_si_pas_verifie(tmp_path):
    """Un téléchargement 'done' mais PAS marqué verified (ne devrait jamais
    arriver avec le code actuel, mais défense en profondeur) ne doit jamais
    être proposé en secours à un pair."""
    p = tmp_path / 'LogXAI-v1.exe'
    p.write_bytes(b'binaire')
    upd._download.update(status='done', verified=False, path=str(p))
    assert upd.serve_status()['available'] is False


# ═══ B) Relais via passerelle réseau (_do_download_via_network mode=gateway) ═

class _FakeGatewayHandler(http.server.BaseHTTPRequestHandler):
    """Simule un AUTRE poste du LAN agissant comme passerelle (chemin B) —
    sert /app/gateway_status et /app/update_relay avec un contenu fixé par
    la classe (surchargé par test via une sous-classe dynamique)."""
    gateway_available = True
    asset_bytes = b'contenu-relaye-par-la-passerelle' * 200

    def log_message(self, fmt, *a):
        pass

    def _send(self, code, ctype, body):
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == '/app/gateway_status':
            self._send(200, 'application/json',
                       json.dumps({'gateway_available': self.gateway_available}).encode())
        elif self.path.startswith('/app/update_relay'):
            self._send(200, 'application/octet-stream', self.asset_bytes)
        else:
            self._send(404, 'application/json', b'{}')


@pytest.fixture
def fake_gateway(monkeypatch):
    """Démarre un faux poste-passerelle sur un port éphémère et pointe
    logx_update.PORT dessus (les 3 chemins réseau utilisent tous ce même
    module-level PORT pour joindre un pair — voir _peer_get_json/_do_
    download_via_network)."""
    handler_cls = type('H', (_FakeGatewayHandler,), {})
    srv = http.server.HTTPServer(('127.0.0.1', 0), handler_cls)
    port = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    monkeypatch.setattr(upd, 'PORT', port)
    try:
        yield handler_cls
    finally:
        srv.shutdown()
        t.join(timeout=5)


def _set_local_reference(tag, asset_bytes):
    """Simule 'ce poste a déjà contacté GitHub avec succès' — remplit le
    cache local comme le ferait un vrai get_cached_check() réussi."""
    upd._cache.update({'ts': time.time(), 'result': {
        'available': False, 'current': '0.1', 'latest': '0.1', 'tag': tag,
        'release_url': '', 'notes': '', 'asset_url': '',
        'asset_sha256': _sha256(asset_bytes), 'asset_size': len(asset_bytes),
        'installable': False, 'checking': False, 'repo': upd.GITHUB_REPO,
    }})


def test_gateway_nominal_telecharge_et_verifie(fake_gateway):
    handler_cls = fake_gateway
    handler_cls.asset_bytes = b'octets-authentiques-de-github' * 300
    handler_cls.gateway_available = True
    _set_local_reference('v1.0', handler_cls.asset_bytes)
    ok, err = upd.start_download_via_network('gateway', ['127.0.0.1'])
    assert ok, err
    st = _wait_download_terminal()
    assert st['status'] == 'done'
    assert st['verified'] is True
    assert st['via'] == 'gateway'
    assert st['via_peer'] == '127.0.0.1'


def test_gateway_hash_invalide_refuse(fake_gateway):
    """La passerelle relaie un contenu qui NE correspond PAS à la référence
    locale (altéré en route, ou mauvaise plateforme) : rejeté, jamais
    accepté à l'aveugle sous prétexte que ça vient 'de la passerelle'."""
    handler_cls = fake_gateway
    handler_cls.asset_bytes = b'contenu-altere-ou-mauvaise-plateforme' * 100
    handler_cls.gateway_available = True
    # Référence locale pour un AUTRE contenu que celui réellement servi :
    _set_local_reference('v1.0', b'ce-nest-pas-le-meme-contenu' * 100)
    ok, err = upd.start_download_via_network('gateway', ['127.0.0.1'])
    assert ok, err
    st = _wait_download_terminal()
    assert st['status'] == 'error'
    assert st['verified'] is False


def test_gateway_indisponible_bascule_pas_automatiquement(fake_gateway):
    """Le pair candidat n'est PAS déclaré passerelle : aucun octet n'est
    relayé, échec propre (pas de confusion avec le chemin C, qui exige un
    appel explicite séparé côté client)."""
    handler_cls = fake_gateway
    handler_cls.gateway_available = False
    _set_local_reference('v1.0', b'peu importe' * 10)
    ok, err = upd.start_download_via_network('gateway', ['127.0.0.1'])
    assert ok, err
    st = _wait_download_terminal()
    assert st['status'] == 'error'


def test_start_download_via_network_refuse_sans_reference_locale(fake_gateway):
    """Ce poste n'a JAMAIS contacté GitHub avec succès (aucune référence
    locale) : refus IMMÉDIAT, sans même sonder le réseau (voir _cache resté
    à {'ts': 0, 'result': None} via la fixture d'isolation)."""
    ok, err = upd.start_download_via_network('gateway', ['127.0.0.1'])
    assert ok is False
    assert upd.get_download_status()['status'] == 'idle'


# ═══ C) Pair-à-pair — SECOURS (_do_download_via_network mode=peer) ══════════

class _FakePeerHandler(http.server.BaseHTTPRequestHandler):
    """Simule un pair du LAN qui a DÉJÀ téléchargé + vérifié un exécutable et
    le sert en secours (chemin C) — /app/update_serve_status +
    /app/update_serve."""
    available = True
    asset_bytes = b'executable-deja-verifie-par-ce-pair' * 200

    def log_message(self, fmt, *a):
        pass

    def _send(self, code, ctype, body):
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == '/app/update_serve_status':
            self._send(200, 'application/json', json.dumps({'available': self.available}).encode())
        elif self.path == '/app/update_serve':
            self._send(200, 'application/octet-stream', self.asset_bytes)
        else:
            self._send(404, 'application/json', b'{}')


@pytest.fixture
def fake_peer(monkeypatch):
    handler_cls = type('H', (_FakePeerHandler,), {})
    srv = http.server.HTTPServer(('127.0.0.1', 0), handler_cls)
    port = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    monkeypatch.setattr(upd, 'PORT', port)
    try:
        yield handler_cls
    finally:
        srv.shutdown()
        t.join(timeout=5)


def test_peer_secours_nominal_telecharge_et_verifie(fake_peer):
    handler_cls = fake_peer
    handler_cls.asset_bytes = b'binaire-deja-verifie-par-le-pair' * 150
    handler_cls.available = True
    _set_local_reference('v2.0', handler_cls.asset_bytes)
    ok, err = upd.start_download_via_network('peer', ['127.0.0.1'])
    assert ok, err
    st = _wait_download_terminal()
    assert st['status'] == 'done'
    assert st['verified'] is True
    assert st['via'] == 'peer'


def test_peer_secours_hash_invalide_refuse(fake_peer):
    handler_cls = fake_peer
    handler_cls.asset_bytes = b'contenu-different-de-la-reference' * 80
    handler_cls.available = True
    _set_local_reference('v2.0', b'reference-attendue-differente' * 80)
    ok, err = upd.start_download_via_network('peer', ['127.0.0.1'])
    assert ok, err
    st = _wait_download_terminal()
    assert st['status'] == 'error'
    assert st['verified'] is False


def test_peer_secours_rien_disponible_refuse(fake_peer):
    handler_cls = fake_peer
    handler_cls.available = False
    _set_local_reference('v2.0', b'peu importe' * 10)
    ok, err = upd.start_download_via_network('peer', ['127.0.0.1'])
    assert ok, err
    st = _wait_download_terminal()
    assert st['status'] == 'error'


def test_start_download_via_network_mode_invalide():
    ok, err = upd.start_download_via_network('n_importe_quoi', ['127.0.0.1'])
    assert ok is False


def test_start_download_via_network_sans_ip_refuse():
    _set_local_reference('v1.0', b'x' * 10)
    ok, err = upd.start_download_via_network('gateway', [])
    assert ok is False


# ═══ Endpoints HTTP (câblage logx_http.py) ═══════════════════════════════════

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


def _get(base, path):
    try:
        with urllib.request.urlopen(base + path, timeout=5) as r:
            return r.status, json.loads(r.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode('utf-8'))


def _post(base, path, payload):
    body = json.dumps(payload).encode('utf-8')
    headers = {'Content-Type': 'application/json', 'X-RC-Token': httpmod.AUTH_TOKEN}
    req = urllib.request.Request(base + path, data=body, method='POST', headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, json.loads(r.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode('utf-8'))


def test_http_gateway_status_reflete_upd(server):
    upd._cache.update({'ts': time.time(), 'result': {'x': 1}})
    code, d = _get(server, '/app/gateway_status')
    assert code == 200
    assert d['gateway_available'] is True


def test_http_update_relay_tag_invalide_400(server):
    upd._cache.update({'ts': time.time(), 'result': {'x': 1}})
    code, d = _get(server, '/app/update_relay?tag=' + urllib.parse.quote('; rm -rf /') + '&platform=win')
    assert code == 400


def test_http_update_relay_sans_passerelle_400(server):
    upd._cache.update({'ts': 0, 'result': None})
    code, d = _get(server, '/app/update_relay?tag=v1.0&platform=win')
    assert code == 400


def test_http_update_serve_status_rien_disponible(server):
    code, d = _get(server, '/app/update_serve_status')
    assert code == 200
    assert d['available'] is False


def test_http_update_serve_404_si_rien_verifie(server):
    code, d = _get(server, '/app/update_serve')
    assert code == 404


def test_http_update_serve_sert_le_fichier_verifie(server, tmp_path):
    p = tmp_path / 'LogXAI-v1.exe'
    content = b'binaire-servi-en-secours' * 300
    p.write_bytes(content)
    upd._download.update(status='done', verified=True, path=str(p),
                          sha256=_sha256(content), version='v1')
    with urllib.request.urlopen(server + '/app/update_serve', timeout=5) as r:
        assert r.status == 200
        received = r.read()
    assert received == content
    assert _sha256(received) == _sha256(content)


def test_http_update_network_scan_sans_ip(server):
    code, d = _post(server, '/app/update_network_scan', {'ips': []})
    assert code == 200
    assert d['gateways'] == [] and d['peers'] == []


def test_http_update_download_via_network_refuse_sans_reference(server):
    upd._cache.update({'ts': 0, 'result': None})
    code, d = _post(server, '/app/update_download_via_network',
                     {'mode': 'gateway', 'ips': ['127.0.0.1']})
    assert code == 400
    assert 'error' in d


def test_http_update_download_via_network_sans_jeton_refuse(server):
    """Comme toutes les autres routes POST (voir do_POST) : jeton exigé."""
    body = json.dumps({'mode': 'gateway', 'ips': []}).encode('utf-8')
    req = urllib.request.Request(server + '/app/update_download_via_network',
                                  data=body, method='POST',
                                  headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            code = r.status
    except urllib.error.HTTPError as e:
        code = e.code
    assert code == 403
