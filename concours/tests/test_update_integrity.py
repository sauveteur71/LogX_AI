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


def test_start_download_via_network_refuse_sans_reference_locale(fake_gateway, monkeypatch):
    """Ce poste n'a JAMAIS contacté GitHub avec succès (aucune référence
    locale, ni en mémoire — _cache resté à {'ts': 0, 'result': None} via la
    fixture d'isolation — ni persistée sur disque — user_data_dir() redirigé
    vers un tmp_path vierge) : refus IMMÉDIAT, sans même sonder le réseau.
    _checking forcé : le cache vide déclencherait sinon un VRAI _refresh de
    fond (contact GitHub réel + écriture d'une référence persistée hors du
    tmp_path une fois le monkeypatch restauré)."""
    monkeypatch.setattr(upd, '_checking', True)
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


# ═══ Priorité B>C restreinte CÔTÉ SERVEUR (pas seulement côté client) ═══════
# Défaut corrigé : mode='peer' était accepté sans jamais vérifier qu'aucune
# passerelle n'était disponible — seule une convention côté client (voir
# logx_logbook.js _renderNetworkUpdatePath) empêchait de le proposer dans
# l'IHM, mais un appel HTTP direct à /app/update_download_via_network avec
# {"mode":"peer", ...} passait toujours, même en présence d'une passerelle
# valide et disponible sur le LAN.

class _FakeDualHandler(http.server.BaseHTTPRequestHandler):
    """Simule un poste qui répond À LA FOIS disponible comme passerelle (B)
    ET comme pair de secours (C) — utilisé pour prouver que (C) est refusé
    dès qu'une passerelle répond, même demandé explicitement en mode='peer'."""
    gateway_available = True
    serve_available = True
    asset_bytes = b'contenu-servi-par-ce-double-role' * 100

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
        elif self.path == '/app/update_serve_status':
            self._send(200, 'application/json',
                       json.dumps({'available': self.serve_available}).encode())
        elif self.path == '/app/update_serve':
            self._send(200, 'application/octet-stream', self.asset_bytes)
        else:
            self._send(404, 'application/json', b'{}')


@pytest.fixture
def fake_dual(monkeypatch):
    handler_cls = type('H', (_FakeDualHandler,), {})
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


def test_peer_secours_refuse_si_le_candidat_est_aussi_passerelle(fake_dual, monkeypatch):
    """Reproduit l'appel direct décrit dans la revue de sécurité : mode='peer'
    avec un unique candidat qui se trouve être — lui-même — disponible comme
    passerelle. Avant le correctif, ceci téléchargeait via le secours sans
    la moindre vérification de disponibilité d'une passerelle. Après :
    refus, rien n'est téléchargé via le pair.
    Ce test simule un poste DISTANT sur la boucle locale (seul moyen pratique
    sur une seule machine) : l'exclusion de soi-même (_is_self_ip, correctif
    auto-découverte — voir la section dédiée en fin de fichier) est donc
    neutralisée ICI SEULEMENT, sinon elle filtrerait le candidat simulé."""
    monkeypatch.setattr(upd, '_is_self_ip', lambda ip: False)
    handler_cls = fake_dual
    handler_cls.gateway_available = True
    handler_cls.serve_available = True
    _set_local_reference('v3.0', handler_cls.asset_bytes)
    ok, err = upd.start_download_via_network('peer', ['127.0.0.1'])
    assert ok, err  # démarre le thread — la vérification réseau est asynchrone
    st = _wait_download_terminal()
    assert st['status'] == 'error'
    assert st['verified'] is False
    assert 'passerelle' in st['error'].lower()


def test_peer_secours_nominal_toujours_ok_si_aucune_passerelle(fake_dual):
    """Non-régression : le secours (C) doit rester utilisable normalement
    quand AUCUNE passerelle n'est disponible parmi les candidats — le
    correctif ne doit pas bloquer le cas nominal légitime."""
    handler_cls = fake_dual
    handler_cls.gateway_available = False
    handler_cls.serve_available = True
    _set_local_reference('v3.0b', handler_cls.asset_bytes)
    ok, err = upd.start_download_via_network('peer', ['127.0.0.1'])
    assert ok, err
    st = _wait_download_terminal()
    assert st['status'] == 'done'
    assert st['verified'] is True
    assert st['via'] == 'peer'


class _FakeGatewayOnlyHandler(http.server.BaseHTTPRequestHandler):
    """Simule une passerelle disponible qui ne répond QUE sur son propre
    endpoint (/app/gateway_status) — jamais interrogée comme pair de secours
    dans ces tests."""
    gateway_available = True

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
        else:
            self._send(404, 'application/json', b'{}')


def test_peer_secours_refuse_via_passerelle_connue_du_serveur_hors_ips(fake_peer, monkeypatch):
    """Variante la plus forte de l'attaque décrite : l'appelant (contournant
    l'IHM cliente) ne fournit dans `ips` QUE le pair (127.0.0.1, voir
    fake_peer), en omettant délibérément l'IP d'une passerelle par ailleurs
    disponible sur le LAN. Le serveur la connaît quand même via
    `known_lan_ips` (dans la vraie vie : logx_http.peer_versions, alimenté
    UNIQUEMENT par l'IP socket réelle des connexions entrantes — jamais par
    le corps JSON d'un appelant) : le secours doit donc être refusé même si
    aucune passerelle ne figure dans `ips`.
    Postes DISTANTS simulés sur la boucle locale : exclusion de soi-même
    neutralisée ICI SEULEMENT (voir la section dédiée en fin de fichier)."""
    monkeypatch.setattr(upd, '_is_self_ip', lambda ip: False)
    handler_cls = fake_peer
    handler_cls.available = True
    _set_local_reference('v3.1', handler_cls.asset_bytes)

    gw_cls = type('GW', (_FakeGatewayOnlyHandler,), {})
    gw_srv = http.server.HTTPServer(('127.0.0.2', upd.PORT), gw_cls)
    gw_thread = threading.Thread(target=gw_srv.serve_forever, daemon=True)
    gw_thread.start()
    try:
        ok, err = upd.start_download_via_network('peer', ['127.0.0.1'], known_lan_ips=['127.0.0.2'])
        assert ok, err
        st = _wait_download_terminal()
        assert st['status'] == 'error'
        assert st['verified'] is False
        assert 'passerelle' in st['error'].lower()
        assert '127.0.0.2' in st['error']
    finally:
        gw_srv.shutdown()
        gw_thread.join(timeout=5)


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


def test_http_update_download_via_network_refuse_sans_reference(server, monkeypatch):
    # _checking forcé : même raison que test_start_download_via_network_
    # refuse_sans_reference_locale (jamais de vrai _refresh de fond en test).
    monkeypatch.setattr(upd, '_checking', True)
    upd._cache.update({'ts': 0, 'result': None})
    code, d = _post(server, '/app/update_download_via_network',
                     {'mode': 'gateway', 'ips': ['127.0.0.1']})
    assert code == 400
    assert 'error' in d


def test_http_update_download_via_network_peer_refuse_si_passerelle_connue_hors_ips(
        server, monkeypatch):
    """Bout-en-bout, exactement le scénario d'attaque de la revue de
    sécurité : POST direct à /app/update_download_via_network avec
    {"mode":"peer", "ips":[...]} — ici le corps JSON de l'attaquant ne cite
    QUE le pair (127.0.0.1), en omettant délibérément l'IP de la passerelle
    (127.0.0.2). Les DEUX sont connues du SERVEUR via httpmod.peer_versions
    (jamais via le corps JSON de CETTE requête — un autre correctif de la
    même revue restreint déjà `ips` aux pairs connus de peer_versions, voir
    _known_peer_ips ci-dessus ; c'est le `known_lan_ips` transmis en plus,
    indépendamment de ce que le client a cité dans `ips`, qui doit détecter
    la passerelle ici). Avant CE correctif, ce POST aurait démarré un
    téléchargement via secours pair-à-pair sans la moindre vérification de
    disponibilité d'une passerelle ; après, la requête doit refuser.
    Postes DISTANTS simulés sur la boucle locale : exclusion de soi-même
    neutralisée ICI SEULEMENT (voir la section dédiée en fin de fichier)."""
    monkeypatch.setattr(upd, '_is_self_ip', lambda ip: False)
    handler_cls = type('GW', (_FakeGatewayOnlyHandler,), {'gateway_available': True})
    gw_srv = http.server.HTTPServer(('127.0.0.2', 0), handler_cls)
    gw_port = gw_srv.server_address[1]
    gw_thread = threading.Thread(target=gw_srv.serve_forever, daemon=True)
    gw_thread.start()
    monkeypatch.setattr(upd, 'PORT', gw_port)
    # Simule que CE serveur a lui-même vu 127.0.0.1 (pair) ET 127.0.0.2
    # (passerelle) se connecter par le passé (comme le ferait /log/list?ver=
    # en conditions réelles) — jamais une donnée fournie par l'attaquant dans
    # le corps de CETTE requête.
    monkeypatch.setattr(httpmod, 'peer_versions', {
        '127.0.0.1': {'version': '1.0', 'last_seen': time.time()},
        '127.0.0.2': {'version': '1.0', 'last_seen': time.time()},
    })
    try:
        _set_local_reference('v4.0', b'peu importe le contenu ici' * 10)
        code, d = _post(server, '/app/update_download_via_network',
                         {'mode': 'peer', 'ips': ['127.0.0.1']})
        assert code == 200 and d.get('ok'), d
        # La décision (refus) est asynchrone (thread de fond, jamais le
        # thread HTTP — voir docstring du module) : on la lit via le status.
        deadline = time.time() + 5
        st = None
        while time.time() < deadline:
            _, st = _get(server, '/app/update_status')
            if st.get('status') in ('done', 'error'):
                break
            time.sleep(0.05)
        assert st is not None
        assert st['status'] == 'error', st
        assert st.get('verified') is False
        assert 'passerelle' in st.get('error', '').lower()
        assert '127.0.0.2' in st.get('error', '')
    finally:
        gw_srv.shutdown()
        gw_thread.join(timeout=5)


def test_http_update_install_refuse_si_non_verifie(server, tmp_path, monkeypatch):
    """Dernier verrou avant apply_update_and_relaunch (remplacement de
    l'exécutable en cours) : même si un état incohérent apparaissait en amont
    — status=='done' + 'path' rempli mais verified=False, ce que les 4 sites
    d'écriture actuels (_do_download, _do_download_via_network B/C) ne
    produisent jamais ensemble, mais qu'une régression future pourrait
    introduire — /app/update_install DOIT refuser SANS MÊME APPELER
    apply_update_and_relaunch. Avant le correctif, seul 'status'/'path'
    étaient contrôlés ici : le code passait bien l'appel jusqu'à
    apply_update_and_relaunch, qui n'était bloqué que par is_frozen()==False
    en environnement de développement (donc HTTP 400 pour la MAUVAISE
    raison ici) — silencieusement dangereux en exécutable figé (PyInstaller,
    l'environnement réel de production), où is_frozen() vaut True et rien
    n'aurait plus arrêté le remplacement. On simule ce cas en gardant
    is_frozen() à sa valeur normale (False en test) MAIS en instrumentant
    apply_update_and_relaunch pour prouver qu'il n'est jamais invoqué du
    tout — la seule preuve qui distingue 'refusé pour la bonne raison' de
    'refusé accidentellement par is_frozen()'."""
    calls = []
    monkeypatch.setattr(upd, 'apply_update_and_relaunch',
                         lambda path: calls.append(path) or (True, ''))
    p = tmp_path / 'LogXAI-non-verifie.exe'
    p.write_bytes(b'contenu-jamais-verifie')
    upd._download.update(status='done', path=str(p), verified=False,
                          sha256='', version='v1')
    code, d = _post(server, '/app/update_install', {})
    assert code == 400
    assert 'error' in d
    # Preuve directe du verrou : apply_update_and_relaunch — qui remplace
    # l'exécutable en cours — ne doit JAMAIS être appelé pour un fichier non
    # vérifié, peu importe status/path.
    assert calls == [], (
        "apply_update_and_relaunch a été appelé avec un fichier non vérifié "
        f"(verified=False) : {calls!r}")
    # Le fichier non vérifié ne doit jamais avoir été touché.
    assert p.exists()
    assert p.read_bytes() == b'contenu-jamais-verifie'


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


# ═══ Défaut corrigé : relais anonyme sans borne (revue adversariale) ════════
# Les 4 routes /app/gateway_status, /app/update_relay, /app/update_serve_
# status, /app/update_serve n'ont JAMAIS de jeton de session (appels
# backend-à-backend entre postes distincts, voir logx_update._peer_get_json)
# — mais avant correction, n'importe quel appareil capable d'atteindre le
# serveur (0.0.0.0 : tout le LAN, voire depuis internet si le port est
# redirigé par une box) pouvait déclencher /app/update_relay (une VRAIE
# requête HTTPS sortante vers GitHub) en boucle serrée, sans aucune limite.
# Corrigé par _is_lan_ip (self.client_address, jamais falsifiable par un
# en-tête HTTP) + _relay_rate_limited (fenêtre glissante par IP).

def test_is_lan_ip_rejette_les_adresses_publiques():
    assert httpmod._is_lan_ip('8.8.8.8') is False
    assert httpmod._is_lan_ip('203.0.113.5') is False
    assert httpmod._is_lan_ip('') is False
    assert httpmod._is_lan_ip(None) is False


def test_is_lan_ip_accepte_les_plages_privees_et_boucle_locale():
    assert httpmod._is_lan_ip('127.0.0.1') is True
    assert httpmod._is_lan_ip('192.168.1.42') is True
    assert httpmod._is_lan_ip('10.0.0.7') is True
    assert httpmod._is_lan_ip('172.16.0.1') is True
    assert httpmod._is_lan_ip('172.31.255.255') is True
    # Hors de la plage RFC1918 172.16-31.x.x (172.32.x.x n'est PAS privé) :
    assert httpmod._is_lan_ip('172.32.0.1') is False


@pytest.fixture(autouse=True)
def _isolate_relay_rate_limit(monkeypatch):
    """État module-level du rate-limiter remis à neuf à chaque test — sinon
    un test précédent fausserait le suivant (fenêtre glissante partagée)."""
    monkeypatch.setattr(httpmod, '_relay_attempts', {})
    yield


class _SpoofedSourceServer(http.server.HTTPServer):
    """Serveur de test qui force l'IP source vue par le Handler (self.
    client_address) à une valeur choisie par le test, tout en acceptant une
    VRAIE connexion TCP loopback — exerce donc exactement le même chemin de
    code que la production (qui ne consulte jamais que self.client_address,
    jamais un en-tête HTTP falsifiable) sans dépendre d'une IP réellement
    routable jusqu'à la machine de test."""
    spoofed_ip = '203.0.113.5'  # TEST-NET-3 (RFC 5737), non-LAN par construction

    def get_request(self):
        request, real_addr = super().get_request()
        return request, (self.spoofed_ip, real_addr[1])


@pytest.fixture
def spoofed_server():
    srv = _SpoofedSourceServer(('127.0.0.1', 0), httpmod.Handler)
    port = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        yield f'http://127.0.0.1:{port}'
    finally:
        srv.shutdown()
        t.join(timeout=5)


@pytest.mark.parametrize('path', [
    '/app/gateway_status',
    '/app/update_relay?tag=v1.0&platform=win',
    '/app/update_serve_status',
    '/app/update_serve',
])
def test_endpoints_relais_bloques_pour_ip_hors_lan(spoofed_server, path):
    """Scénario d'attaque du rapport : un appelant dont l'IP source N'EST PAS
    dans le LAN (ex. port du serveur redirigé par erreur depuis internet)
    doit recevoir 403 sur les 4 routes visées — jamais le comportement
    normal (200/400) qu'elles avaient avant correction."""
    upd._cache.update({'ts': time.time(), 'result': {'x': 1}})
    code, d = _get(spoofed_server, path)
    assert code == 403
    assert 'error' in d


def test_gateway_status_toujours_accessible_depuis_le_lan(server):
    """Non-régression : une IP LAN authentique (127.0.0.1 dans le test, voir
    fixture `server`) continue de passer — la correction ne doit pas casser
    l'usage légitime backend-à-backend entre postes du LAN."""
    upd._cache.update({'ts': time.time(), 'result': {'x': 1}})
    code, d = _get(server, '/app/gateway_status')
    assert code == 200
    assert d['gateway_available'] is True


def test_update_relay_rate_limited_apres_rafale(server):
    """Scénario d'attaque du rapport : rejouer /app/update_relay en boucle
    serrée depuis la MÊME IP doit finir par être bloqué (429), jamais laissé
    déclencher une requête sortante GitHub indéfiniment. On force un échec de
    validation (tag invalide -> 400) pour isoler le rate-limit lui-même sans
    dépendre du réseau réel : le compteur incrémente AVANT la validation du
    tag (voir do_GET), donc la limite est bien atteinte même sur des appels
    qui échouent tous en 400."""
    upd._cache.update({'ts': time.time(), 'result': {'x': 1}})
    codes = []
    for _ in range(httpmod._RELAY_ATTEMPT_LIMIT + 3):
        code, _d = _get(server, '/app/update_relay?tag=' + urllib.parse.quote('; rm -rf /') + '&platform=win')
        codes.append(code)
    assert codes[:httpmod._RELAY_ATTEMPT_LIMIT] == [400] * httpmod._RELAY_ATTEMPT_LIMIT
    assert codes[httpmod._RELAY_ATTEMPT_LIMIT:] == [429] * (len(codes) - httpmod._RELAY_ATTEMPT_LIMIT)


def test_update_serve_rate_limited_apres_rafale(server, tmp_path):
    """Même scénario que ci-dessus pour /app/update_serve (chemin C, sert un
    fichier depuis le disque local — coûteux en bande passante/threads)."""
    p = tmp_path / 'LogXAI-v1.exe'
    content = b'binaire-servi-en-secours' * 300
    p.write_bytes(content)
    upd._download.update(status='done', verified=True, path=str(p),
                          sha256=_sha256(content), version='v1')
    codes = []
    for _ in range(httpmod._RELAY_ATTEMPT_LIMIT + 3):
        try:
            with urllib.request.urlopen(server + '/app/update_serve', timeout=5) as r:
                codes.append(r.status)
        except urllib.error.HTTPError as e:
            codes.append(e.code)
    assert codes[:httpmod._RELAY_ATTEMPT_LIMIT] == [200] * httpmod._RELAY_ATTEMPT_LIMIT
    assert codes[httpmod._RELAY_ATTEMPT_LIMIT:] == [429] * (len(codes) - httpmod._RELAY_ATTEMPT_LIMIT)


# ═══ Anti-SSRF : 'ip'/'ips' fourni par le client n'est jamais utilisé tel
# quel pour construire une requête sortante ═══════════════════════════════════
# Défaut corrigé (revue sécurité, angle SSRF) : scan_network_candidates()/
# _peer_get_json()/_do_download_via_network() construisaient
# f'http://{ip}:{PORT}{path}' avec `ip` pris tel quel dans le corps JSON du
# client — ni un littéral IPv4/IPv6 valide, ni une IP connue de ce serveur
# (peer_versions) n'étaient exigés. Un appelant en possession du jeton (voir
# rc_token, obtenu en chargeant n'importe quelle page tant qu'aucun mot de
# passe d'accès n'est configuré) pouvait donc forcer ce serveur à émettre de
# VRAIES requêtes HTTP sortantes vers un hôte/domaine arbitraire de son choix.
# Double correctif : (1) logx_update._is_valid_ip rejette tout ce qui n'est
# pas un littéral IP (jamais de nom d'hôte, jamais de résolution DNS) ;
# (2) logx_http._known_peer_ips restreint, AVANT même d'atteindre
# logx_update, `ips` aux seules IP que CE serveur a lui-même vues comme pairs
# réels (peer_versions, alimenté depuis l'IP socket des connexions entrantes,
# jamais depuis un corps de requête).

class _HitCounterHandler(http.server.BaseHTTPRequestHandler):
    """Service externe factice qui compte simplement le nombre de requêtes
    reçues (peu importe le chemin) — utilisé pour PROUVER qu'aucune requête
    sortante n'a été émise vers lui, pas seulement que le résultat renvoyé au
    client est vide (une régression future pourrait renvoyer un résultat vide
    tout en continuant à sonder discrètement)."""
    hits = []

    def log_message(self, fmt, *a):
        pass

    def do_GET(self):
        self.__class__.hits.append(self.path)
        body = json.dumps({'gateway_available': True, 'available': True}).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)


@pytest.fixture
def hit_counter(monkeypatch):
    """Démarre le service factice ci-dessus et pointe logx_update.PORT dessus
    (comme fake_gateway/fake_peer) — réutilisé pour les deux volets (appel
    direct logx_update ET bout-en-bout HTTP via logx_http)."""
    handler_cls = type('H', (_HitCounterHandler,), {'hits': []})
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


def test_is_valid_ip_accepte_ipv4_ipv6_rejette_le_reste():
    assert upd._is_valid_ip('127.0.0.1') is True
    assert upd._is_valid_ip('192.168.1.42') is True
    assert upd._is_valid_ip('::1') is True
    assert upd._is_valid_ip('localhost') is False
    assert upd._is_valid_ip('evil.example.com') is False
    assert upd._is_valid_ip('127.0.0.1:8080') is False  # port collé -> pas un littéral IP pur
    assert upd._is_valid_ip('') is False
    assert upd._is_valid_ip(None) is False
    assert upd._is_valid_ip('   ') is False
    assert upd._is_valid_ip(' 127.0.0.1 ') is True  # espaces en bord tolérés (strip())


def test_peer_get_json_refuse_hostname_jamais_de_requete_emise(hit_counter):
    """Reproduction EXACTE de l'attaque confirmée dans le rapport :
    _peer_get_json('localhost', ...) ne doit JAMAIS émettre la moindre
    requête — avant le correctif, le service factice recevait un GET
    /app/gateway_status malgré 'localhost' n'étant ni une IP ni un pair
    connu."""
    assert upd._peer_get_json('localhost', '/app/gateway_status', timeout=2) is None
    assert hit_counter.hits == []


def test_scan_network_candidates_ignore_hostname_non_ip(hit_counter):
    """Reproduction du repro exact du rapport : scan_network_candidates(
    ['localhost']) devait auparavant sonder le service factice (résultat
    observé : {'gateways': ['localhost'], 'peers': []} + une requête reçue).
    Après correctif : ni sondé, ni retenu comme candidat."""
    result = upd.scan_network_candidates(['localhost'])
    assert result == {'gateways': [], 'peers': []}
    assert hit_counter.hits == []


def test_do_download_via_network_refuse_hostname_non_ip(hit_counter):
    """Même reproduction pour le chemin téléchargement (_do_download_via_
    network) : un 'ip' qui n'est pas un littéral IP ne doit jamais aboutir à
    la moindre connexion sortante, même en appelant la fonction directement
    (contournement de start_download_via_network)."""
    upd._do_download_via_network('gateway', ['localhost'], 'v1.0', 'win',
                                  'a' * 64, 0)
    assert hit_counter.hits == []
    st = upd.get_download_status()
    assert st['status'] == 'error'
    assert 'invalide' in st['error'].lower()


def test_http_update_network_scan_ignore_ip_inconnue_du_serveur(server, hit_counter, monkeypatch):
    """Variante bout-en-bout de l'attaque décrite dans le rapport, via le
    VRAI endpoint HTTP : {"ips": ["<ip jamais vue par ce serveur>"]}. Même si
    l'IP fournie est un littéral IPv4 valide et réellement joignable (le
    service factice ci-dessus), le serveur ne doit PAS la sonder tant qu'elle
    ne figure pas dans peer_versions (jamais un pair connu de CE serveur —
    voir logx_http._known_peer_ips)."""
    monkeypatch.setattr(httpmod, 'peer_versions', {})  # isolation : aucun pair connu
    code, d = _post(server, '/app/update_network_scan', {'ips': ['127.0.0.1']})
    assert code == 200
    assert d == {'gateways': [], 'peers': []}
    assert hit_counter.hits == []


def test_http_update_network_scan_accepte_un_pair_reellement_connu(server, hit_counter, monkeypatch):
    """Non-régression : le cas légitime doit continuer à fonctionner —
    une fois l'IP effectivement vue comme pair (poll réel de /log/list?ver=,
    donc peer_versions alimenté par l'IP SOCKET réelle, jamais par le corps
    JSON), le scan doit à nouveau la sonder normalement.
    Le pair 'réellement connu' est simulé sur la boucle locale (seul moyen
    pratique sur une seule machine) : exclusion de soi-même neutralisée ICI
    SEULEMENT (voir la section dédiée en fin de fichier)."""
    monkeypatch.setattr(upd, '_is_self_ip', lambda ip: False)
    monkeypatch.setattr(httpmod, 'peer_versions', {})
    _get(server, '/log/list?ver=0.9-beta9')  # enregistre 127.0.0.1 comme pair connu
    code, d = _post(server, '/app/update_network_scan', {'ips': ['127.0.0.1']})
    assert code == 200
    assert d == {'gateways': ['127.0.0.1'], 'peers': []}
    assert hit_counter.hits == ['/app/gateway_status']


def test_http_update_download_via_network_refuse_ip_inconnue_du_serveur(server, hit_counter, monkeypatch):
    """Même vérification bout-en-bout pour le second endpoint concerné par le
    rapport : /app/update_download_via_network avec une IP jamais vue par ce
    serveur doit être refusé SANS ouvrir la moindre connexion sortante vers
    elle (aucun sondage, aucun octet transféré) — même avec une référence
    SHA-256 locale valide (ce qui, avant ce correctif précis, aurait laissé
    passer l'IP jusqu'à _do_download_via_network)."""
    monkeypatch.setattr(httpmod, 'peer_versions', {})
    _set_local_reference('v9.0', b'peu importe le contenu ici' * 10)
    code, d = _post(server, '/app/update_download_via_network',
                     {'mode': 'gateway', 'ips': ['127.0.0.1']})
    assert code == 400
    assert 'error' in d
    assert hit_counter.hits == []
    assert upd.get_download_status()['status'] in ('idle', 'error')


# ═══ Défaut corrigé : le poste se découvrait LUI-MÊME comme passerelle ═══════
# (auto-découverte 127.0.0.1). peer_versions contient TOUJOURS '127.0.0.1'
# dès qu'un navigateur local est ouvert (le serveur invite à ouvrir
# http://127.0.0.1:PORT — usage nominal), et rien n'excluait jamais le poste
# DEMANDEUR de ses propres candidats : le scan sondait
# http://127.0.0.1:PORT/app/gateway_status = le serveur lui-même, dont
# gateway_status() répond 'disponible' tant que le cache GitHub a moins de
# CHECK_TTL (6 h) — précisément le cas du poste qui VIENT de perdre internet
# (scénario DXpédition visé par le module). Conséquences observées avant
# correctif : (a) scan -> gateways=['127.0.0.1'] (relayer GitHub via
# soi-même, sans internet -> échec garanti), (b) une vraie passerelle était
# masquée (tri par IP : 127.0.0.1 en tête, le client ne propose que
# gateways[0]), (c) mode='peer' refusé en s'auto-citant comme passerelle.
# Correctif : _is_self_ip (boucle locale + IP des interfaces de CE poste)
# appliqué dans logx_update.scan_network_candidates ET dans
# logx_http._known_peer_ips — un poste n'est JAMAIS son propre candidat.

def test_is_self_ip_boucle_locale_interfaces_et_ips_distantes():
    """Le prédicat lui-même : toute la boucle locale (127.0.0.0/8, ::1, forme
    IPv6-mappée), l'adresse non spécifiée et chaque adresse d'interface
    locale sont 'soi-même' ; une IP distante (TEST-NET/publique) ou un
    non-littéral ne le sont jamais."""
    assert upd._is_self_ip('127.0.0.1') is True
    assert upd._is_self_ip('127.0.0.2') is True   # toute la plage 127/8
    assert upd._is_self_ip('::1') is True
    assert upd._is_self_ip('::ffff:127.0.0.1') is True
    assert upd._is_self_ip('0.0.0.0') is True
    for own_ip in upd._local_interface_ips():
        assert upd._is_self_ip(own_ip) is True, own_ip
    assert upd._is_self_ip('192.0.2.1') is False   # TEST-NET-1, jamais locale
    assert upd._is_self_ip('203.0.113.5') is False
    assert upd._is_self_ip('localhost') is False   # pas un littéral IP
    assert upd._is_self_ip('') is False
    assert upd._is_self_ip(None) is False


def test_known_peer_ips_exclut_le_navigateur_local(server, monkeypatch):
    """Cause racine : le navigateur LOCAL poll /log/list?ver= depuis
    127.0.0.1, donc peer_versions contenait toujours la boucle locale et
    _known_peer_ips la laissait passer comme 'pair candidat'. Après
    correctif : peer_versions garde bien l'entrée (le badge de versions
    /log/status -> peer_list continue d'afficher tous les postes vus), mais
    _known_peer_ips ne la propose plus jamais comme candidat de mise à
    jour."""
    monkeypatch.setattr(httpmod, 'peer_versions', {})
    _get(server, '/log/list?ver=0.9-beta3')  # poll réel du navigateur local
    assert '127.0.0.1' in httpmod.peer_versions        # badge intact
    assert '127.0.0.1' not in httpmod._known_peer_ips()  # jamais candidat


def test_scan_network_candidates_ne_sonde_jamais_soi_meme(fake_gateway):
    """Reproduction directe de la conséquence (a) : un serveur répond
    'passerelle disponible' sur 127.0.0.1:PORT — en prod c'est le poste
    DEMANDEUR lui-même (même IP, même PORT). Avant correctif :
    {'gateways': ['127.0.0.1']} (le poste se découvre lui-même). Après :
    jamais sondé, jamais retenu."""
    handler_cls = fake_gateway
    handler_cls.gateway_available = True
    assert upd.scan_network_candidates(['127.0.0.1']) == {'gateways': [], 'peers': []}


def test_scan_vraie_passerelle_plus_masquee_par_soi_meme(monkeypatch):
    """Conséquence (b) : une VRAIE passerelle du LAN ne doit plus être
    masquée par l'auto-découverte. Topologie simulée sur une machine :
    127.0.0.1 = le poste demandeur lui-même, 127.0.0.2 = la vraie passerelle
    distante (déclarée 'distante' en restreignant _is_self_ip à 127.0.0.1
    — sur le terrain ce serait 192.168.x.x). Avant correctif, le scan
    renvoyait ['127.0.0.1', '127.0.0.2'] et le client ne proposait que
    gateways[0] = soi-même ; après, seule la vraie passerelle reste."""
    monkeypatch.setattr(upd, '_is_self_ip', lambda ip: ip == '127.0.0.1')
    gw_cls = type('GW', (_FakeGatewayOnlyHandler,), {'gateway_available': True})
    gw_srv = http.server.HTTPServer(('127.0.0.2', 0), gw_cls)
    gw_thread = threading.Thread(target=gw_srv.serve_forever, daemon=True)
    gw_thread.start()
    monkeypatch.setattr(upd, 'PORT', gw_srv.server_address[1])
    try:
        scan = upd.scan_network_candidates(['127.0.0.1', '127.0.0.2'])
        assert scan['gateways'] == ['127.0.0.2']
        assert '127.0.0.1' not in scan['gateways'] + scan['peers']
    finally:
        gw_srv.shutdown()
        gw_thread.join(timeout=5)


def test_http_scenario_dxpedition_auto_decouverte_corrigee(server, monkeypatch):
    """Bout-en-bout, la reproduction EXACTE du rapport (topologie prod :
    upd.PORT = port du serveur, donc toute sonde vers 127.0.0.1 atteint le
    serveur DEMANDEUR lui-même) : poste en DXpédition qui VIENT de perdre
    internet (cache GitHub frais < CHECK_TTL, gateway_status() répond donc
    'disponible'), navigateur local enregistré comme pair par un poll réel
    de /log/list?ver=. Avant correctif : le scan renvoyait
    {'gateways': ['127.0.0.1']} et mode='peer' répondait ok puis s'annulait
    avec « Passerelle disponible sur le réseau local (127.0.0.1) » — le
    poste se bloquait LUI-MÊME pendant 6 h. Après : le scan ne renvoie
    jamais soi-même, et mode='peer' refuse proprement faute de candidat (au
    lieu de s'auto-citer comme passerelle).
    Serveur MULTI-THREAD ici (comme logx_serveur en prod, contrairement à la
    fixture `server`) : indispensable pour que la sonde du serveur vers
    lui-même puisse réellement aboutir — c'est exactement ce chemin
    auto-sonde qui constituait le bug."""
    import socketserver

    class _ThreadingSrv(socketserver.ThreadingMixIn, http.server.HTTPServer):
        daemon_threads = True

    monkeypatch.setattr(httpmod, 'peer_versions', {})
    srv = _ThreadingSrv(('127.0.0.1', 0), httpmod.Handler)
    base = f'http://127.0.0.1:{srv.server_address[1]}'
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    monkeypatch.setattr(upd, 'PORT', srv.server_address[1])  # topologie prod
    try:
        _get(base, '/log/list?ver=0.9-beta3')        # le navigateur local se fait voir
        _set_local_reference('v9.9', b'reference locale' * 10)  # cache frais -> gateway dispo
        assert upd.gateway_status()['gateway_available'] is True

        code, scan = _post(base, '/app/update_network_scan', {'ips': ['127.0.0.1']})
        assert code == 200
        assert scan == {'gateways': [], 'peers': []}, (
            f"le poste s'est découvert lui-même : {scan}")

        code, d = _post(base, '/app/update_download_via_network',
                         {'mode': 'peer', 'ips': ['127.0.0.1']})
        assert code == 400, (
            "mode='peer' aurait dû être refusé immédiatement (aucun candidat) au "
            f"lieu de démarrer puis s'auto-bloquer : HTTP {code} {d}")
        assert 'candidat' in d.get('error', '').lower()
        assert '127.0.0.1' not in d.get('error', '')  # jamais d'auto-citation
    finally:
        srv.shutdown()
        t.join(timeout=5)


# ═══ Défaut corrigé : la référence locale ne survivait pas au redémarrage ════
# La docstring du module (et le commit d'origine) promettent que le poste
# receveur s'appuie sur SA référence obtenue par un contact direct ANTÉRIEUR
# avec GitHub, « même périmé en fraîcheur — un digest de release publiée est
# stable indéfiniment ». Or cette référence ne vivait que dans le dict
# module-level _cache, jamais persisté : après un simple redémarrage de
# LogXAI.exe (coupure secteur, déplacement du poste — routinier en
# DXpédition), un poste sans internet retombait sur le refus « jamais
# contacté GitHub » alors qu'il avait bien une référence la session
# précédente. Correctif : _save_reference (appelé par _refresh à chaque
# contact réussi, écriture atomique dans user_data_dir()/update/) +
# _load_persisted_reference (rechargé en secours par
# start_download_via_network quand le cache mémoire est vide).
# Le « redémarrage » est simulé exactement comme un processus frais : _cache
# remis à {'ts': 0, 'result': None} (l'état initial du module) tandis que
# user_data_dir() (tmp_path, fixture d'isolation) est conservé — c'est le
# disque, pas la mémoire, qui doit porter la référence.

def _fake_release(tag, asset_bytes, platform='win'):
    """Payload minimal de l'API GitHub Releases pour le tag+contenu donnés —
    même schéma de nom d'asset que _build_result."""
    suffix, ext = upd._ASSET_SUFFIX_BY_PLATFORM[platform]
    return {
        'tag_name': tag, 'html_url': '', 'body': '',
        'assets': [{'name': f'LogXAI-{tag}{suffix}{ext}',
                    'browser_download_url': f'https://x/LogXAI-{tag}{suffix}{ext}',
                    'size': len(asset_bytes),
                    'digest': f'sha256:{_sha256(asset_bytes)}'}],
    }


def test_reference_locale_survit_au_redemarrage_du_processus(monkeypatch):
    """LE test de non-régression du défaut : session 1 = contact direct
    GitHub réussi (via _refresh, le vrai chemin de production — pas une
    écriture directe du fichier, qui passerait même sans le correctif côté
    _refresh) ; session 2 = processus frais (cache mémoire vierge), la garde
    de référence de start_download_via_network doit PASSER grâce à la
    référence persistée. Preuve du franchissement SANS aucun réseau (même
    sonde que la revue adversariale) : _download préréglé à 'downloading',
    donc un franchissement de la garde répond « déjà en cours » — situé
    APRÈS elle — au lieu du refus « jamais réussi »."""
    asset = b'asset-de-la-session-precedente' * 50
    monkeypatch.setattr(upd, '_platform_key', lambda: 'win')
    monkeypatch.setattr(upd, '_fetch_latest_release',
                         lambda: _fake_release('v7.7', asset))
    upd._refresh(force=True)  # session 1 : contact direct réussi -> persistance
    assert upd._cache['result']['asset_sha256'] == _sha256(asset)

    # ── Redémarrage simulé : mémoire du processus perdue, disque conservé ──
    monkeypatch.setattr(upd, '_cache', {'ts': 0, 'result': None})
    monkeypatch.setattr(upd, '_checking', True)  # aucun thread de refresh réel
    monkeypatch.setattr(upd, '_download', dict(upd._download, status='downloading'))

    ok, err = upd.start_download_via_network('gateway', ['192.0.2.1'])
    assert ok is False
    assert 'jamais réussi' not in err, (
        "après un simple redémarrage, le poste est retraité comme « jamais "
        f"contacté GitHub » : la référence n'a pas survécu ({err!r})")
    assert 'cours' in err  # la garde de référence a bien été franchie


def test_reference_persistee_transmise_au_telechargement(monkeypatch):
    """Le secours disque ne doit pas seulement franchir la garde : c'est bien
    LA référence persistée (tag + sha + taille de la session 1) qui doit être
    transmise au thread de téléchargement — jamais une valeur vide."""
    asset = b'contenu-verifie-en-session-1' * 40
    monkeypatch.setattr(upd, '_platform_key', lambda: 'win')
    monkeypatch.setattr(upd, '_fetch_latest_release',
                         lambda: _fake_release('v8.8', asset))
    upd._refresh(force=True)

    monkeypatch.setattr(upd, '_cache', {'ts': 0, 'result': None})
    monkeypatch.setattr(upd, '_checking', True)
    captured = {}

    def _capture(target=None, args=(), daemon=None):
        captured['args'] = args
        return type('T', (), {'start': lambda self: None})()

    monkeypatch.setattr(upd.threading, 'Thread', _capture)
    ok, err = upd.start_download_via_network('gateway', ['192.0.2.1'])
    assert ok is True, err
    mode, ips, ref_tag, platform, ref_sha, ref_size, known = captured['args']
    assert ref_tag == 'v8.8'
    assert ref_sha == _sha256(asset)
    assert ref_size == len(asset)


def test_reference_persistee_corrompue_refusee(monkeypatch, tmp_path):
    """Défense en profondeur : un fichier de référence corrompu (JSON cassé,
    tag hors _TAG_RE — il finit dans une URL de relais —, sha non-hex) est
    traité comme ABSENT : refus sûr, jamais une confiance sur du contenu
    douteux."""
    monkeypatch.setattr(upd, '_checking', True)
    ref_path = upd._reference_path()
    os.makedirs(os.path.dirname(ref_path), exist_ok=True)
    for garbage in (
            b'pas du json du tout {',
            json.dumps({'tag': '; rm -rf /', 'asset_sha256': 'a' * 64,
                        'asset_size': 1}).encode(),
            json.dumps({'tag': 'v1.0', 'asset_sha256': 'zz' * 32,
                        'asset_size': 1}).encode(),
            json.dumps(['pas', 'un', 'objet']).encode()):
        with open(ref_path, 'wb') as f:
            f.write(garbage)
        assert upd._load_persisted_reference() is None, garbage
        ok, err = upd.start_download_via_network('gateway', ['192.0.2.1'])
        assert ok is False
        assert 'jamais réussi' in err


def test_reference_sans_digest_necrase_pas_la_bonne(monkeypatch):
    """Une vérification réussie dont l'asset n'expose PAS de digest (champ
    absent côté API) ne doit JAMAIS écraser une bonne référence persistée
    antérieure : un digest de release publiée est stable indéfiniment, mieux
    vaut une référence ancienne complète que rien."""
    asset = b'release-avec-digest' * 30
    monkeypatch.setattr(upd, '_platform_key', lambda: 'win')
    monkeypatch.setattr(upd, '_fetch_latest_release',
                         lambda: _fake_release('v5.5', asset))
    upd._refresh(force=True)

    sans_digest = _fake_release('v6.0', b'nouvelle-release')
    del sans_digest['assets'][0]['digest']
    monkeypatch.setattr(upd, '_fetch_latest_release', lambda: sans_digest)
    upd._refresh(force=True)

    ref = upd._load_persisted_reference()
    assert ref is not None, "la bonne référence antérieure a été perdue"
    assert ref['tag'] == 'v5.5'
    assert ref['asset_sha256'] == _sha256(asset)


# ═══ Écriture du .bat de mise à jour : chemins accentués (mojibake cmd) ═════
# Défaut corrigé (audit + vérification adversariale) : apply_update_and_
# relaunch écrivait _apply_update.bat en UTF-8 avec les chemins EN DUR. Or
# cmd.exe ne lit JAMAIS un .bat en UTF-8 — et la page réellement utilisée
# n'est même pas prévisible : OEM (cp850) avec une console, mais ANSI
# (cp1252) quand cmd est lancé en DETACHED_PROCESS sans console (le mode de
# lancement réel ici), où `chcp 65001` est de surcroît inopérant (les trois
# mesurés sur poste Windows français, OEMCP=850/ACP=1252). Dès qu'un chemin
# contenait un accent (« C:\Users\Frédéric\... » — nom d'utilisateur dans
# %APPDATA% pour new_exe_path, ou dossier où l'utilisateur a posé LogXAI.exe
# pour current_exe : cas ultra-courant pour le public francophone visé),
# 'é' UTF-8 (0xC3 0xA9) était relu comme 2 caractères, move /Y échouait 30
# fois, `start` n'était jamais atteint : l'application se fermait (os._exit
# du caller /app/update_install) et ne redémarrait JAMAIS — sans même le
# marqueur .update_failed.txt de :giveup, écrit lui aussi vers le chemin
# mangé. Correctif : .bat 100 % ASCII (identique dans TOUTES les pages de
# code), chemins transmis par variables d'environnement (UTF-16 de bout en
# bout via CreateProcessW, expansion %VAR% en mémoire par cmd — aucun
# aller-retour par un encodage de fichier).

def _fake_exes_chemin_accentue(tmp_path, dirname):
    """Un faux LogXAI.exe (OLD) + un faux exécutable téléchargé (NEW) dans un
    dossier au nom accentué — reproduit la disposition réelle du rapport."""
    accent = tmp_path / dirname
    accent.mkdir()
    old = accent / 'LogXAI.exe'
    new = accent / 'LogXAI-v0.9-beta5.exe'
    old.write_bytes(b'OLD BINARY')
    new.write_bytes(b'NEW BINARY')
    return old, new


def test_bat_pur_ascii_et_chemins_via_environnement(monkeypatch, tmp_path):
    """Le test qui ÉCHOUE sans le correctif : le .bat généré ne doit contenir
    AUCUN octet non-ASCII (avant correctif : les chemins accentués y étaient
    encodés en UTF-8, mojibakés ensuite par cmd) et les chemins doivent
    passer par l'environnement du processus cmd, jamais par le contenu du
    fichier. Exécutable partout (Linux CI compris) : branche Windows forcée,
    constantes DETACHED_PROCESS/CREATE_NEW_PROCESS_GROUP fournies si
    absentes, Popen intercepté (jamais de vrai cmd lancé ici)."""
    old, new = _fake_exes_chemin_accentue(tmp_path, 'Frédéric_Téléchargements')
    monkeypatch.setattr(upd, 'is_frozen', lambda: True)
    monkeypatch.setattr(sys, 'executable', str(old))
    monkeypatch.setattr(sys, 'platform', 'win32')
    monkeypatch.setattr(upd.subprocess, 'DETACHED_PROCESS', 0x00000008, raising=False)
    monkeypatch.setattr(upd.subprocess, 'CREATE_NEW_PROCESS_GROUP', 0x00000200, raising=False)
    calls = {}

    def fake_popen(args, **kw):
        calls['args'] = args
        calls['kw'] = kw
        return None

    monkeypatch.setattr(upd.subprocess, 'Popen', fake_popen)
    ok, err = upd.apply_update_and_relaunch(str(new))
    assert ok, err
    assert list(calls['args'][:2]) == ['cmd', '/c']
    helper = calls['args'][-1]
    with open(helper, 'rb') as f:
        data = f.read()
    # Avant correctif : b'Fr\xc3\xa9d\xc3\xa9ric...' (UTF-8) présent -> échec.
    non_ascii = [b for b in data if b >= 0x80]
    assert non_ascii == [], (
        'octets non-ASCII dans le .bat — relus dans une page de code '
        f'imprévisible par cmd, chemins mojibakés : {non_ascii!r}')
    # Les chemins ne transitent plus par le fichier mais par %VAR% + env :
    assert b'%LOGX_UPDATE_NEW%' in data
    assert b'%LOGX_UPDATE_CURRENT%' in data
    env = calls['kw'].get('env')
    assert env is not None, 'aucun environnement transmis à cmd'
    assert env['LOGX_UPDATE_NEW'] == str(new)
    assert env['LOGX_UPDATE_CURRENT'] == str(old)


@pytest.mark.skipif(not sys.platform.startswith('win'),
                    reason='exécution réelle de cmd.exe (Windows uniquement)')
@pytest.mark.parametrize('dirname', [
    # Cas réel du rapport : accents français (UTF-8 divergent de cp850/cp1252).
    'Frédéric_Téléchargements',
    # Hors cp850 ET cp1252 : aucune page de code SBCS ne peut représenter ces
    # chemins — seule la transmission UTF-16 par l'environnement fonctionne.
    'Dossier_Δ₿',
], ids=['accents_francais', 'hors_pages_de_code'])
def test_move_reel_via_cmd_detache_chemin_accentue(monkeypatch, tmp_path, dirname):
    """Exécution RÉELLE de bout en bout : le .bat généré par le vrai
    apply_update_and_relaunch est lancé par un vrai cmd /c avec les MÊMES
    creationflags que la production (DETACHED_PROCESS, sans console) et doit
    réussir le move — avant correctif, le contenu restait b'OLD BINARY'
    pendant que cmd épuisait ses 30 tentatives sur des chemins mojibakés.
    Seul `start ""` est neutralisé (rem), au niveau octets, pour ne pas
    tenter de lancer le faux .exe en fin de script."""
    old, new = _fake_exes_chemin_accentue(tmp_path, dirname)
    monkeypatch.setattr(upd, 'is_frozen', lambda: True)
    monkeypatch.setattr(sys, 'executable', str(old))
    real_popen = upd.subprocess.Popen

    def popen_start_neutralise(args, **kw):
        helper = args[-1]
        with open(helper, 'rb') as f:
            data = f.read()
        assert b'start ""' in data
        with open(helper, 'wb') as f:
            f.write(data.replace(b'start ""', b'rem __ ""'))
        return real_popen(args, **kw)

    monkeypatch.setattr(upd.subprocess, 'Popen', popen_start_neutralise)
    ok, err = upd.apply_update_and_relaunch(str(new))
    assert ok, err
    # Nominal : ~2 s (timeout /t 2 puis move réussi). Borne large : 40 s
    # couvre le comportement pré-correctif (30 tentatives x 1 s -> ~32 s).
    deadline = time.time() + 40
    while time.time() < deadline and old.read_bytes() != b'NEW BINARY':
        time.sleep(0.25)
    assert old.read_bytes() == b'NEW BINARY', (
        'move /Y jamais abouti — chemins mojibakés dans le .bat ?')
    assert not new.exists(), 'le nouvel exécutable n a jamais été déplacé'
