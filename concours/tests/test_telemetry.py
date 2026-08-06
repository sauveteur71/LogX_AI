# -*- coding: utf-8 -*-
"""Télémétrie d'usage anonyme (logx_telemetry) — le module SEUL est testé ici
(paramètres, contenu exact du payload, cadence, envoi) ; le câblage HTTP
(/telemetry/test) est testé en bas de fichier avec un vrai serveur, même
harnais que tests/test_cat_proprietaire_dispatch.py.

Fichiers d'état (`_STAMP_FILE`/`_ID_FILE`) TOUJOURS redirigés vers un
répertoire temporaire (jamais le dossier partagé du dépôt — voir
piege-tests-ecrivent-dans-le-depot dans la mémoire de session)."""
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_telemetry as tel


def _isole_fichiers(monkeypatch, tmp_path):
    monkeypatch.setattr(tel, '_STAMP_FILE', str(tmp_path / 'telemetry_sync.json'))
    monkeypatch.setattr(tel, '_ID_FILE', str(tmp_path / 'telemetry_id.json'))


# ─── telemetry_settings() : SEUL toggle réseau du projet activé par défaut ──

def test_telemetry_settings_active_par_defaut_config_vide():
    assert tel.telemetry_settings({})['enabled'] is True
    assert tel.telemetry_settings(None)['enabled'] is True


def test_telemetry_settings_champ_jamais_sauvegarde_reste_active():
    """Config d'un opérateur qui n'a jamais ouvert la popup CONFIG (donc le
    champ 'telemetry_enabled' est absent, pas juste vide/false) : doit rester
    activé — c'est tout le sens d'un opt-out."""
    cfg = {'callsign_contest': 'F4GLD', 'cat_enabled': True}
    assert 'telemetry_enabled' not in cfg
    assert tel.telemetry_settings(cfg)['enabled'] is True


def test_telemetry_settings_desactivee_explicitement():
    assert tel.telemetry_settings({'telemetry_enabled': False})['enabled'] is False


def test_telemetry_settings_desactivee_chaine_vide():
    """Le <select> CONFIG envoie un booléen JS (!!value), mais une config
    éditée à la main / migrée d'une ancienne version pourrait stocker ''."""
    assert tel.telemetry_settings({'telemetry_enabled': ''})['enabled'] is False


def test_telemetry_settings_activee_explicitement():
    assert tel.telemetry_settings({'telemetry_enabled': True})['enabled'] is True


def test_telemetry_settings_endpoint_vide_par_defaut():
    assert tel.telemetry_settings({})['endpoint'] == ''


def test_telemetry_settings_endpoint_configure():
    s = tel.telemetry_settings({'telemetry_endpoint': ' https://example.org/hb '})
    assert s['endpoint'] == 'https://example.org/hb'


# ─── install_id() : jeton aléatoire, jamais dérivé d'une donnée identifiante ─

def test_install_id_genere_et_persiste(monkeypatch, tmp_path):
    _isole_fichiers(monkeypatch, tmp_path)
    id1 = tel._install_id()
    id2 = tel._install_id()
    assert id1 == id2   # même jeton relu, pas régénéré à chaque appel
    assert os.path.exists(tel._ID_FILE)


def test_install_id_est_bien_un_uuid_hex():
    import uuid
    new_id = uuid.uuid4().hex
    assert len(new_id) == 32
    assert all(c in '0123456789abcdef' for c in new_id)


def test_install_id_deux_dossiers_differents_donnent_deux_jetons(monkeypatch, tmp_path):
    """Confirme que le jeton n'est dérivé de RIEN d'identifiant côté machine
    (pas du callsign, pas du nom d'utilisateur) — juste un tirage aléatoire à
    la première génération."""
    monkeypatch.setattr(tel, '_ID_FILE', str(tmp_path / 'a' / 'telemetry_id.json'))
    os.makedirs(tmp_path / 'a')
    id_a = tel._install_id()
    monkeypatch.setattr(tel, '_ID_FILE', str(tmp_path / 'b' / 'telemetry_id.json'))
    os.makedirs(tmp_path / 'b')
    id_b = tel._install_id()
    assert id_a != id_b


# ─── build_payload() : le contrat central — CES clés et RIEN d'autre ────────

def test_build_payload_champs_exacts(monkeypatch, tmp_path):
    _isole_fichiers(monkeypatch, tmp_path)
    payload = tel.build_payload()
    assert set(payload.keys()) == {'install_id', 'version', 'os'}


def test_build_payload_ne_contient_aucun_callsign(monkeypatch, tmp_path):
    _isole_fichiers(monkeypatch, tmp_path)
    payload = tel.build_payload()
    texte = json.dumps(payload)
    assert 'F4GLD' not in texte
    assert 'callsign' not in texte.lower()
    assert 'qso' not in texte.lower()


def test_build_payload_os_est_platform_system(monkeypatch, tmp_path):
    _isole_fichiers(monkeypatch, tmp_path)
    import platform
    assert tel.build_payload()['os'] == platform.system()


def test_build_payload_version_est_app_version(monkeypatch, tmp_path):
    _isole_fichiers(monkeypatch, tmp_path)
    from logx_version import APP_VERSION
    assert tel.build_payload()['version'] == APP_VERSION


# ─── heartbeat_due() : fonction pure, cadence quotidienne ───────────────────

def test_heartbeat_due_jamais_envoye():
    assert tel.heartbeat_due(None, datetime.datetime(2026, 8, 6, 12, 0)) is True
    assert tel.heartbeat_due('', datetime.datetime(2026, 8, 6, 12, 0)) is True


def test_heartbeat_due_recent_pas_du_tout():
    now = datetime.datetime(2026, 8, 6, 12, 0)
    last = '2026-08-06 11:00'   # 1h -> pas dû
    assert tel.heartbeat_due(last, now) is False


def test_heartbeat_due_perime():
    now = datetime.datetime(2026, 8, 7, 13, 0)
    last = '2026-08-06 12:00'   # 25h -> dû
    assert tel.heartbeat_due(last, now) is True


def test_heartbeat_due_pile_24h_moins_la_marge():
    now = datetime.datetime(2026, 8, 7, 11, 56)   # 23h56 après 'last'
    last = '2026-08-06 12:00'
    assert tel.heartbeat_due(last, now) is True   # >= 24h - 300s = 23h55


def test_heartbeat_due_stamp_illisible_ne_plante_pas():
    assert tel.heartbeat_due('n\'importe quoi', datetime.datetime(2026, 8, 6, 12, 0)) is True


# ─── status() : lecture du stamp, jamais d'exception ─────────────────────────

def test_status_sans_fichier(monkeypatch, tmp_path):
    _isole_fichiers(monkeypatch, tmp_path)
    assert tel.status() == {'last': {}}


def test_status_fichier_corrompu_ne_plante_pas(monkeypatch, tmp_path):
    _isole_fichiers(monkeypatch, tmp_path)
    with open(tel._STAMP_FILE, 'w', encoding='utf-8') as f:
        f.write('{ceci n\'est pas du json')
    assert tel.status() == {'last': {}}


# ─── send_heartbeat() : dispatch réseau, jamais d'appel si désactivé/sans URL ─

def test_send_heartbeat_desactivee_ne_tente_rien(monkeypatch, tmp_path):
    _isole_fichiers(monkeypatch, tmp_path)
    monkeypatch.setattr(tel, 'post_url_json',
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError('ne doit jamais être appelé')))
    r = tel.send_heartbeat({'telemetry_enabled': False, 'telemetry_endpoint': 'https://x'})
    assert r['ok'] is False


def test_send_heartbeat_sans_endpoint_ne_tente_rien(monkeypatch, tmp_path):
    _isole_fichiers(monkeypatch, tmp_path)
    monkeypatch.setattr(tel, 'post_url_json',
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError('ne doit jamais être appelé')))
    r = tel.send_heartbeat({})   # activé par défaut, mais endpoint vide
    assert r['ok'] is False and r.get('skipped') is True


def test_send_heartbeat_ok_stamp_ecrit(monkeypatch, tmp_path):
    _isole_fichiers(monkeypatch, tmp_path)
    monkeypatch.setattr(tel, 'post_url_json', lambda url, payload, timeout=10, headers=None: (200, 'ok'))
    r = tel.send_heartbeat({'telemetry_endpoint': 'https://example.org/hb'})
    assert r == {'ok': True}
    assert os.path.exists(tel._STAMP_FILE)
    with open(tel._STAMP_FILE, encoding='utf-8') as f:
        assert json.load(f).get('last')


def test_send_heartbeat_destination_injoignable(monkeypatch, tmp_path):
    _isole_fichiers(monkeypatch, tmp_path)
    monkeypatch.setattr(tel, 'post_url_json', lambda url, payload, timeout=10, headers=None: (None, None))
    r = tel.send_heartbeat({'telemetry_endpoint': 'https://example.org/hb'})
    assert r['ok'] is False and 'injoignable' in r['error']


def test_send_heartbeat_erreur_http(monkeypatch, tmp_path):
    _isole_fichiers(monkeypatch, tmp_path)
    monkeypatch.setattr(tel, 'post_url_json', lambda url, payload, timeout=10, headers=None: (500, 'boom'))
    r = tel.send_heartbeat({'telemetry_endpoint': 'https://example.org/hb'})
    assert r['ok'] is False and '500' in r['error']


def test_send_heartbeat_paylod_envoye_est_build_payload(monkeypatch, tmp_path):
    _isole_fichiers(monkeypatch, tmp_path)
    captured = {}
    monkeypatch.setattr(tel, 'post_url_json',
                        lambda url, payload, timeout=10, headers=None:
                        captured.update(payload) or (200, 'ok'))
    tel.send_heartbeat({'telemetry_endpoint': 'https://example.org/hb'})
    assert set(captured.keys()) == {'install_id', 'version', 'os'}


# ─── Câblage HTTP /telemetry/test (vrai serveur, port éphémère) ─────────────

import http.server
import threading
import urllib.error
import urllib.request

import pytest

import logx_http as httpmod


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
    body = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(
        base + path, data=body, method='POST',
        headers={'Content-Type': 'application/json', 'X-RC-Token': httpmod.AUTH_TOKEN})
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, json.loads(r.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode('utf-8'))


def test_http_telemetry_test_utilise_endpoint_saisi_pas_celui_sauvegarde(server, monkeypatch, tmp_path):
    """Comme /winkeyer/test et /so2r/test : le champ saisi dans la popup CONFIG
    (pas encore enregistré) doit primer sur celui déjà sauvegardé, pour
    pouvoir tester avant de cliquer Enregistrer."""
    _isole_fichiers(monkeypatch, tmp_path)   # sinon _stamp()/_install_id() écrivent dans concours/
    monkeypatch.setattr(httpmod, 'current_config',
                        {'telemetry_enabled': False, 'telemetry_endpoint': 'https://ancien'})
    captured = {}
    monkeypatch.setattr(tel, 'post_url_json',
                        lambda url, payload, timeout=10, headers=None:
                        captured.update(url=url) or (200, 'ok'))
    status, d = _post(server, '/telemetry/test', {'endpoint': 'https://nouveau/hb'})
    assert status == 200 and d == {'ok': True}
    assert captured['url'] == 'https://nouveau/hb'


def test_http_telemetry_test_echec_reseau_renvoie_400(server, monkeypatch, tmp_path):
    _isole_fichiers(monkeypatch, tmp_path)
    monkeypatch.setattr(httpmod, 'current_config', {})
    monkeypatch.setattr(tel, 'post_url_json', lambda *a, **k: (None, None))
    status, d = _post(server, '/telemetry/test', {'endpoint': 'https://x/hb'})
    assert status == 400 and d['ok'] is False
