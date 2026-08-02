# -*- coding: utf-8 -*-
"""Défenses SSRF de logx_rules_ai._download_bytes (revue sécurité post-fusion,
02/08/2026) — 3 correctifs :

  1. DNS rebinding : la validation d'hôte (au 1er lookup) et la connexion
     réseau réelle (à un 2e lookup indépendant chez urllib) pouvaient recevoir
     deux IP différentes pour le même nom (TTL DNS court) — un attaquant
     répond une IP publique à la validation, une IP privée/loopback à la
     connexion. On épingle désormais la connexion à l'IP déjà validée.
  2. socket.getaddrinfo() sans timeout dans le thread HTTP /rules/analyze —
     borné via le pool partagé logx_utils._FETCH_EXECUTOR + .result(timeout=).
  3. 100.64.0.0/10 (CGNAT/RFC 6598) : ipaddress.IPv4Address.is_private EXCLUT
     explicitement cette plage (documenté dans le module lui-même) — aucun des
     5 prédicats classiques ne la couvre.
"""
import http.server
import ipaddress
import os
import socket
import sys
import threading
import time

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CONCOURS not in sys.path:
    sys.path.insert(0, CONCOURS)

import logx_rules_ai as rai   # noqa: E402


# ─── Défaut 3 : CGNAT/RFC 6598 doit être refusé ─────────────────────────────

@pytest.mark.parametrize('ip_str,expected', [
    ('100.64.0.1', False),      # CGNAT — début de plage
    ('100.100.100.100', False), # CGNAT — milieu de plage
    ('100.127.255.254', False), # CGNAT — fin de plage
    ('100.63.255.255', True),   # juste AVANT la plage — publique normale
    ('100.128.0.0', True),      # juste APRÈS la plage — publique normale
    ('8.8.8.8', True),          # publique ordinaire
    ('127.0.0.1', False),       # loopback (prédicat existant)
    ('192.168.1.1', False),     # privé RFC1918 (prédicat existant)
    ('169.254.1.1', False),     # lien-local (prédicat existant)
    ('224.0.0.1', False),       # multicast (prédicat existant)
])
def test_is_safe_ip_cgnat_range(ip_str, expected):
    ip = ipaddress.ip_address(ip_str)
    assert rai._is_safe_ip(ip) is expected


def test_stdlib_is_private_ne_couvre_pas_cgnat():
    """Documente le piège lui-même : la stdlib ne suffit pas seule, d'où le
    test dédié ci-dessus plutôt qu'une confiance aveugle en is_private."""
    assert ipaddress.ip_address('100.64.5.5').is_private is False


def test_is_safe_host_rejette_une_ip_cgnat(monkeypatch):
    monkeypatch.setattr(rai, '_resolve_host_ips',
                         lambda h: [ipaddress.ip_address('100.64.0.1')])
    assert rai._is_safe_host('cgnat.example') is False


def test_resolve_safe_ip_rejette_une_ip_cgnat(monkeypatch):
    monkeypatch.setattr(rai, '_resolve_host_ips',
                         lambda h: [ipaddress.ip_address('100.64.0.1')])
    with pytest.raises(ValueError):
        rai._resolve_safe_ip('cgnat.example')


# ─── Défaut 2 : résolution DNS bornée dans le temps ─────────────────────────

def test_resolve_host_ips_borne_un_resolveur_qui_ne_repond_jamais(monkeypatch):
    """socket.getaddrinfo() qui ne revient jamais ne doit PAS geler l'appelant
    au-delà de _DNS_TIMEOUT (même piège que logx_utils.fetch_url)."""
    def hanging_getaddrinfo(*a, **k):
        time.sleep(30)
        raise AssertionError('ne devrait jamais revenir dans ce test')
    monkeypatch.setattr(socket, 'getaddrinfo', hanging_getaddrinfo)
    monkeypatch.setattr(rai, '_DNS_TIMEOUT', 1)

    t0 = time.time()
    ips = rai._resolve_host_ips('jamais-de-reponse.example')
    elapsed = time.time() - t0

    assert ips == []
    assert elapsed < 5, f"l'appelant est resté bloqué {elapsed:.1f}s"


def test_resolve_host_ips_utilise_le_pool_partage(monkeypatch):
    """Vérifie que la résolution passe bien par logx_utils._FETCH_EXECUTOR
    (même pool que fetch_url/logx_clusters), pas par un thread ad hoc ni un
    appel direct dans le thread appelant."""
    from logx_utils import _FETCH_EXECUTOR
    submitted = []
    real_submit = _FETCH_EXECUTOR.submit

    def spy_submit(fn, *a, **k):
        submitted.append(fn)
        return real_submit(fn, *a, **k)

    monkeypatch.setattr(_FETCH_EXECUTOR, 'submit', spy_submit)
    rai._resolve_host_ips('localhost')
    assert socket.getaddrinfo in submitted


# ─── Défaut 1 : DNS rebinding — fermeture de la fenêtre validation/connexion ─

def test_rebinding_entre_validation_et_connexion_est_bloque(monkeypatch):
    """LE scénario d'attaque : le 1er lookup (fait par _validate_download_url
    à l'entrée de _download_bytes) répond une IP publique, le 2e lookup (fait
    par le handler épinglé juste avant la connexion réelle) répond une IP
    loopback — TTL DNS court / serveur DNS malveillant. Doit être refusé, et
    la résolution doit avoir été appelée exactement 2 fois (validation +
    épinglage), prouvant qu'aucune 3e résolution non validée n'a lieu
    (contrairement à l'ancien code, où opener.open() laissait http.client
    refaire une résolution totalement indépendante et non vérifiée)."""
    calls = {'n': 0}

    def rebinding_resolve(hostname):
        calls['n'] += 1
        if calls['n'] == 1:
            return [ipaddress.ip_address('93.184.216.34')]   # public au 1er lookup
        return [ipaddress.ip_address('127.0.0.1')]            # rebind au 2e

    monkeypatch.setattr(rai, '_resolve_host_ips', rebinding_resolve)

    with pytest.raises(ValueError, match='local/priv'):
        rai._download_bytes('http://attacker-controlled.example/rules.pdf', timeout=5)

    assert calls['n'] == 2


def test_connexion_pinnee_atteint_bien_lip_validee():
    """Bout en bout sur un vrai serveur HTTP local : le nom demandé
    ('example.test') ne résout jamais réellement — seule l'IP retournée par
    _resolve_host_ips (patchée ici sur 127.0.0.1, le serveur de test) doit
    être contactée, et le Host: header doit rester celui d'origine (SNI/Host
    non altérés par l'épinglage de la connexion TCP)."""
    received_host = {}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            received_host['value'] = self.headers.get('Host', '')
            body = b'contenu-du-reglement'
            self.send_response(200)
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass

    srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    port = srv.server_address[1]
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()

    orig_is_safe_ip = rai._is_safe_ip
    orig_resolve = rai._resolve_host_ips
    # Isole le mécanisme d'épinglage du prédicat loopback (testé séparément
    # ci-dessus) : ce test vérifie SEULEMENT que la connexion TCP réelle suit
    # l'IP validée, pas les prédicats de sécurité eux-mêmes.
    rai._is_safe_ip = lambda ip: True
    rai._resolve_host_ips = lambda hostname: [ipaddress.ip_address('127.0.0.1')]
    try:
        data = rai._download_bytes(f'http://example.test:{port}/rules.txt', timeout=5)
    finally:
        rai._is_safe_ip = orig_is_safe_ip
        rai._resolve_host_ips = orig_resolve
        srv.shutdown()

    assert data == b'contenu-du-reglement'
    assert received_host['value'].startswith('example.test')


def test_hote_local_toujours_refuse_sans_patch():
    """Non-régression du comportement d'origine, sans aucun monkeypatch."""
    with pytest.raises(ValueError):
        rai._download_bytes('http://127.0.0.1:1/rules.pdf', timeout=2)
    with pytest.raises(ValueError):
        rai._download_bytes('http://localhost/rules.pdf', timeout=2)


def test_schema_non_autorise_toujours_refuse():
    with pytest.raises(ValueError):
        rai._download_bytes('file:///etc/passwd', timeout=2)
