# -*- coding: utf-8 -*-
"""Tests de la galerie SSDV côté HTTP (cadrage 12/09/2026) :
- GET /ssdv/images (liste, JSON, lecture du dossier réel isolé par test) ;
- service du JPEG par le serveur de fichiers statique GÉNÉRIQUE
  (GET /ssdv_images/<fichier>, aucun endpoint dédié) ;
- câblage logx_http._ssdv_paquet_recu (le callback réel du client KISS,
  qui remplace le no-op de l'incrément précédent) vers logx_ssdv_galerie,
  testé en direct sans passer par un vrai socket/thread."""
import http.server
import json
import os
import sys
import threading
import urllib.error
import urllib.request

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CONCOURS not in sys.path:
    sys.path.insert(0, CONCOURS)

import logx_http as h                  # noqa: E402
import logx_ssdv_galerie as galerie    # noqa: E402
from test_ssdv_reception import _paquet_ssdv   # noqa: E402


def _get(base, path):
    with urllib.request.urlopen(base + path, timeout=10) as r:
        return r.status, r.headers.get('Content-Type'), r.read()


def _serveur():
    srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), h.Handler)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, 'http://127.0.0.1:%d' % port


def _reset_galerie():
    galerie.registre.clear()


def test_ssdv_images_liste_vide_sans_dossier(tmp_path, monkeypatch):
    monkeypatch.setattr(galerie, 'DOSSIER_DEFAUT', str(tmp_path / 'absent'))
    srv, base = _serveur()
    try:
        with urllib.request.urlopen(base + '/ssdv/images', timeout=10) as r:
            code = r.status
            j = json.loads(r.read())
        assert code == 200
        assert j == []
    finally:
        srv.shutdown()


def test_ssdv_images_liste_le_contenu_reel_du_dossier(tmp_path, monkeypatch):
    monkeypatch.setattr(galerie, 'DOSSIER_DEFAUT', str(tmp_path))
    (tmp_path / 'F4GLD_1_100.jpg').write_bytes(b'\xff\xd8\xff')
    srv, base = _serveur()
    try:
        with urllib.request.urlopen(base + '/ssdv/images', timeout=10) as r:
            code = r.status
            j = json.loads(r.read())
        assert code == 200
        assert j == [{'fichier': 'F4GLD_1_100.jpg', 'indicatif': 'F4GLD',
                       'image_id': 1, 'recu_le': 100}]
    finally:
        srv.shutdown()


def test_ssdv_images_jpeg_servi_par_le_serveur_statique_generique():
    """Pas d'endpoint dédié : /ssdv_images/<fichier> passe par le même
    chemin que /vendor/leaflet.min.js -- Handler._resolve() + Content-Type
    déduit de l'extension. Écrit dans le VRAI dossier par défaut (sans quoi
    _resolve(), confiné à concours/, ne peut pas le trouver) puis nettoie."""
    os.makedirs(galerie.DOSSIER_DEFAUT, exist_ok=True)
    chemin = os.path.join(galerie.DOSSIER_DEFAUT, 'TEST_9_1.jpg')
    with open(chemin, 'wb') as f:
        f.write(b'\xff\xd8\xff\xdb\x00\x43')
    srv, base = _serveur()
    try:
        code, ct, corps = _get(base, '/ssdv_images/TEST_9_1.jpg')
        assert code == 200
        assert ct == 'image/jpeg'
        assert corps == b'\xff\xd8\xff\xdb\x00\x43'
    finally:
        srv.shutdown()
        os.remove(chemin)


def test_ssdv_paquet_recu_alimente_le_registre_sans_completer():
    _reset_galerie()
    try:
        paquet = _paquet_ssdv(packet_id=0, indicatif='F4GLD', image_id=1)
        h._ssdv_paquet_recu(paquet)
        assert ('F4GLD', 1) in galerie.registre
    finally:
        _reset_galerie()


def test_ssdv_paquet_recu_sauvegarde_quand_limage_se_complete(monkeypatch, tmp_path):
    _reset_galerie()
    appels = []
    monkeypatch.setattr(galerie, 'sauver_image',
                         lambda reg, cle, **k: appels.append(cle) or {'ok': True})
    try:
        # un seul paquet portant déjà le fanion EOI = image complète d'un coup.
        paquet = _paquet_ssdv(packet_id=0, indicatif='F4GLD', image_id=1, eoi=True)
        h._ssdv_paquet_recu(paquet)
        assert appels == [('F4GLD', 1)]
    finally:
        _reset_galerie()


def test_ssdv_paquet_recu_ne_sauvegarde_pas_tant_quincomplet(monkeypatch):
    _reset_galerie()
    appels = []
    monkeypatch.setattr(galerie, 'sauver_image',
                         lambda reg, cle, **k: appels.append(cle) or {'ok': True})
    try:
        paquet = _paquet_ssdv(packet_id=0, indicatif='F4GLD', image_id=1)   # pas d'EOI
        h._ssdv_paquet_recu(paquet)
        assert appels == []
    finally:
        _reset_galerie()
