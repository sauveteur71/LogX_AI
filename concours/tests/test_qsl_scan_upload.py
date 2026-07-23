# -*- coding: utf-8 -*-
"""Tests pour le scan de carte QSL papier attaché à un QSO :
  - logx_qsl_scan.py : stockage disque pur (extension, écriture, suppression) ;
  - logx_http._parse_multipart_form : parseur multipart minimal (pas de
    cgi.FieldStorage, supprimé en Python 3.13) ;
  - POST /qsl_scan/upload de bout en bout (vrai serveur, comme
    tests/test_http_scope_endpoints.py).

À ne pas confondre avec tests/test_qsl_upload.py (services de confirmation EN
LIGNE eQSL/ClubLog/QRZCQ/HRDLog — logx_qsl.py, un module différent)."""
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

import logx_qsl_scan as qslscan
import logx_http as httpmod

JPEG_BYTES = b'\xff\xd8\xff\xe0' + b'\x00' * 40 + b'\xff\xd9'   # en-tête/pied JPEG minimal


# ─── logx_qsl_scan : stockage disque pur ─────────────────────────────────────

def test_save_scan_extension_refusee(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ValueError, match='non accepté'):
        qslscan.save_scan(1, 'carte.exe', b'contenu')


def test_save_scan_fichier_vide(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ValueError, match='vide'):
        qslscan.save_scan(1, 'carte.jpg', b'')


def test_save_scan_ecrit_et_renvoie_chemin_relatif(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    rel = qslscan.save_scan(42, 'carte.JPG', JPEG_BYTES)   # extension en majuscules
    assert rel.startswith('qsl_scans/qso_42_') and rel.endswith('.jpg')
    assert os.path.isfile(rel)
    with open(rel, 'rb') as f:
        assert f.read() == JPEG_BYTES


def test_save_scan_noms_uniques_si_appels_rapproches(tmp_path, monkeypatch):
    """Deux scans pour le même QSO ne doivent jamais s'écraser silencieusement
    (2 photos rapprochées, ex. recto/verso) — le nom inclut un horodatage ms."""
    monkeypatch.chdir(tmp_path)
    r1 = qslscan.save_scan(7, 'a.jpg', JPEG_BYTES)
    r2 = qslscan.save_scan(7, 'b.jpg', JPEG_BYTES + b'\x00')
    assert r1 != r2
    assert os.path.isfile(r1) and os.path.isfile(r2)


def test_delete_scan_supprime_le_fichier(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    rel = qslscan.save_scan(1, 'carte.png', JPEG_BYTES)
    assert os.path.isfile(rel)
    qslscan.delete_scan(rel)
    assert not os.path.isfile(rel)


def test_delete_scan_absent_ne_leve_pas(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    qslscan.delete_scan('qsl_scans/inexistant.jpg')   # ne doit rien lever


def test_delete_scan_ignore_chemin_hors_scans_dir(tmp_path, monkeypatch):
    """Défense en profondeur : un chemin hors du dossier scans (ex. traversée
    '../') ne doit jamais être supprimé, même s'il existe réellement."""
    monkeypatch.chdir(tmp_path)
    secret = tmp_path / 'secret.txt'
    secret.write_text('ne pas toucher')
    qslscan.delete_scan('../secret.txt')
    qslscan.delete_scan(str(secret))
    assert secret.is_file()


# ─── logx_http._parse_multipart_form : parseur minimal ──────────────────────

def _multipart_body(boundary, fields=None, files=None):
    """Construit un corps multipart/form-data (mêmes conventions que le
    FormData du navigateur) pour tester le parseur/l'endpoint sans dépendance
    externe (requests, etc. — hors du strict nécessaire pour ce projet)."""
    parts = []
    for name, value in (fields or {}).items():
        parts.append(
            f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n'
            f'{value}\r\n'.encode('utf-8'))
    for name, (filename, data, content_type) in (files or {}).items():
        head = (f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"; '
                f'filename="{filename}"\r\nContent-Type: {content_type}\r\n\r\n')
        parts.append(head.encode('utf-8') + data + b'\r\n')
    parts.append(f'--{boundary}--\r\n'.encode('utf-8'))
    return b''.join(parts)


def test_parse_multipart_champs_et_fichier():
    boundary = 'TestBoundary1'
    body = _multipart_body(boundary, fields={'qso_id': '99'},
                           files={'file': ('scan.jpg', JPEG_BYTES, 'image/jpeg')})
    fields, files = httpmod._parse_multipart_form(
        body, f'multipart/form-data; boundary={boundary}')
    assert fields == {'qso_id': '99'}
    assert files['file']['filename'] == 'scan.jpg'
    assert files['file']['data'] == JPEG_BYTES


def test_parse_multipart_sans_boundary_renvoie_vide():
    fields, files = httpmod._parse_multipart_form(b'peu importe', 'application/json')
    assert fields == {} and files == {}


def test_parse_multipart_plusieurs_champs_texte():
    boundary = 'B2'
    body = _multipart_body(boundary, fields={'a': '1', 'b': 'deux'})
    fields, files = httpmod._parse_multipart_form(
        body, f'multipart/form-data; boundary={boundary}')
    assert fields == {'a': '1', 'b': 'deux'} and files == {}


# ─── POST /qsl_scan/upload : bout en bout (vrai serveur) ────────────────────

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


def _post_multipart(base, path, fields=None, files=None):
    boundary = 'PyTestUploadBoundary'
    body = _multipart_body(boundary, fields, files)
    req = urllib.request.Request(
        base + path, data=body, method='POST',
        headers={'Content-Type': f'multipart/form-data; boundary={boundary}',
                 'X-RC-Token': httpmod.AUTH_TOKEN})
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, json.loads(r.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode('utf-8'))


def test_upload_qso_introuvable(server, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(httpmod, 'shared_log', [])
    status, res = _post_multipart(server, '/qsl_scan/upload',
                                  fields={'qso_id': '123'},
                                  files={'file': ('scan.jpg', JPEG_BYTES, 'image/jpeg')})
    assert status == 404 and not res['ok']


def test_upload_champ_manquant(server, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(httpmod, 'shared_log', [{'id': 1, 'call': 'F5ABC'}])
    status, res = _post_multipart(server, '/qsl_scan/upload', fields={'qso_id': '1'})   # pas de fichier
    assert status == 400 and not res['ok']


def test_upload_extension_refusee(server, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(httpmod, 'shared_log', [{'id': 1, 'call': 'F5ABC'}])
    monkeypatch.setattr(httpmod, 'save_log_to_disk', lambda: None)
    status, res = _post_multipart(server, '/qsl_scan/upload',
                                  fields={'qso_id': '1'},
                                  files={'file': ('scan.exe', b'MZ...', 'application/octet-stream')})
    assert status == 400 and not res['ok'] and 'accepté' in res['error']


def test_upload_ok_attache_le_scan_au_qso(server, tmp_path, monkeypatch):
    """Cas nominal : le QSO reçoit le champ qsl_scan et le fichier est
    récupérable en GET par le service de fichiers statique habituel, avec le
    bon Content-Type (voir l'ajout image/jpeg dans Handler.do_GET)."""
    monkeypatch.chdir(tmp_path)
    qso = {'id': 555, 'call': 'F5ABC', 'band': '14', 'mode': 'SSB'}
    monkeypatch.setattr(httpmod, 'shared_log', [qso])
    monkeypatch.setattr(httpmod, 'save_log_to_disk', lambda: None)

    status, res = _post_multipart(server, '/qsl_scan/upload',
                                  fields={'qso_id': '555'},
                                  files={'file': ('carte.jpg', JPEG_BYTES, 'image/jpeg')})
    assert status == 200 and res['ok']
    rel_path = res['qsl_scan']
    assert rel_path.startswith('qsl_scans/qso_555_')
    assert qso['qsl_scan'] == rel_path   # posé sur le QSO en mémoire

    with urllib.request.urlopen(f'{server}/{rel_path}', timeout=5) as r:
        assert r.headers.get('Content-Type') == 'image/jpeg'
        assert r.read() == JPEG_BYTES


def test_upload_remplace_lancien_scan_et_supprime_le_fichier(server, tmp_path, monkeypatch):
    """Un 2e upload sur le même QSO remplace la référence ET supprime
    l'ancien fichier sur disque (pas d'accumulation silencieuse)."""
    monkeypatch.chdir(tmp_path)
    qso = {'id': 9, 'call': 'F5ABC'}
    monkeypatch.setattr(httpmod, 'shared_log', [qso])
    monkeypatch.setattr(httpmod, 'save_log_to_disk', lambda: None)

    _, res1 = _post_multipart(server, '/qsl_scan/upload', fields={'qso_id': '9'},
                              files={'file': ('v1.jpg', JPEG_BYTES, 'image/jpeg')})
    old_path = res1['qsl_scan']
    assert os.path.isfile(old_path)

    _, res2 = _post_multipart(server, '/qsl_scan/upload', fields={'qso_id': '9'},
                              files={'file': ('v2.jpg', JPEG_BYTES + b'\x00', 'image/jpeg')})
    new_path = res2['qsl_scan']
    assert new_path != old_path
    assert not os.path.isfile(old_path)   # ancien fichier nettoyé
    assert os.path.isfile(new_path)
    assert qso['qsl_scan'] == new_path
