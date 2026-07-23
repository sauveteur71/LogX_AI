# -*- coding: utf-8 -*-
"""Tests des fonctions pures de logx_utils — cas vérifiés à la main."""
import io
import json as _json
import os
import sys
import urllib.error

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_utils
from logx_utils import (locator_to_latlon, haversine, bearing,
                                cardinal, is_digital_mode, post_url_json)


# ─── locator_to_latlon ───────────────────────────────────────────────────────
# Référence : centre de carré Maidenhead calculé à la main.
# JN15XC : J=9 → lon 9×20−180=0 ; '1' → +2 ; X=23 → +23×(2/24) ; +1/24 (centre)
#          N=13 → lat 13×10−90=40 ; '5' → +5 ; C=2 → +2/24 ; +0.5/24 (centre)

def test_locator_jn15xc():
    lat, lon = locator_to_latlon('JN15XC')
    assert abs(lat - 45.1042) < 0.001
    assert abs(lon - 3.9583) < 0.001


def test_locator_minuscules_acceptees():
    assert locator_to_latlon('jn15xc') == locator_to_latlon('JN15XC')


def test_locator_invalide():
    assert locator_to_latlon('') == (None, None)
    assert locator_to_latlon('JN1') == (None, None)      # trop court (3 car.)
    assert locator_to_latlon('J') == (None, None)
    assert locator_to_latlon(None) == (None, None)


def test_locator_4_caracteres_complete_avec_mm():
    # Correctif M8 : un locator à 4 caractères est un Maidenhead valide (déjà
    # accepté par le formulaire de config et par locatorToLatLon() côté JS,
    # qui le complète elle-même) — il ne doit plus être rejeté ici, sous peine
    # de casser en silence les appelants qui ne compensent pas déjà (ex.
    # logx_psk.py, dont les locators PSK Reporter font souvent 4 caractères).
    assert locator_to_latlon('JN15') == locator_to_latlon('JN15MM')
    assert locator_to_latlon('jn15') == locator_to_latlon('JN15')


# ─── haversine ───────────────────────────────────────────────────────────────

def test_haversine_meme_point():
    assert haversine(45.0, 3.0, 45.0, 3.0) == 0


def test_haversine_jn15xc_jn18du():
    """Chaspinhac → région parisienne : ~435 km (vérifié par calcul manuel :
    Δlat 3.75°≈417 km, Δlon 1.67°×cos(47°)≈126 km → √(417²+126²)≈436 km)."""
    d = haversine(45.1042, 3.9583, 48.8542, 2.2917)
    assert 425 <= d <= 445


def test_haversine_un_degre_latitude():
    """1° de latitude ≈ 111 km partout sur le globe."""
    d = haversine(45.0, 3.0, 46.0, 3.0)
    assert 110 <= d <= 112


# ─── bearing / cardinal ──────────────────────────────────────────────────────

def test_bearing_nord():
    assert bearing(45.0, 3.0, 46.0, 3.0) == 0


def test_bearing_est_sur_equateur():
    assert bearing(0.0, 0.0, 0.0, 1.0) == 90


def test_bearing_sud():
    assert bearing(46.0, 3.0, 45.0, 3.0) == 180


def test_cardinal_points_principaux():
    assert cardinal(0) == 'N'
    assert cardinal(90) == 'E'
    assert cardinal(180) == 'S'
    assert cardinal(270) == 'O'      # convention française (Ouest)
    assert cardinal(225) == 'SO'
    assert cardinal(360) == 'N'      # bouclage


# ─── is_digital_mode ─────────────────────────────────────────────────────────

def test_modes_numeriques_detectes():
    assert is_digital_mode('FT8')
    assert is_digital_mode('ft4')                      # insensible à la casse
    assert is_digital_mode('gros pileup RTTY 20m')     # détection en contexte


def test_modes_analogiques_ignores():
    assert not is_digital_mode('SSB')
    assert not is_digital_mode('CW')
    assert not is_digital_mode('FM 145.500')


# ─── post_url_json ───────────────────────────────────────────────────────────
# Pattern des tests réseau du projet (cf. tests/test_qsl_upload.py) : on
# monkeypatch urllib.request.urlopen, jamais un vrai appel réseau.

class _FakeHeaders:
    def get_content_charset(self):
        return 'utf-8'


class _FakeResp:
    def __init__(self, text, status=200):
        self._text = text.encode('utf-8')
        self.status = status
        self.headers = _FakeHeaders()
    def read(self):
        return self._text
    def __enter__(self):
        return self
    def __exit__(self, *a):
        return False


def test_post_url_json_succes(monkeypatch):
    captured = {}
    def fake_urlopen(req, timeout=10, context=None):
        captured['url'] = req.full_url
        captured['method'] = req.get_method()
        captured['body'] = _json.loads(req.data.decode('utf-8'))
        captured['content_type'] = req.get_header('Content-type')
        captured['user_agent'] = req.get_header('User-agent')
        return _FakeResp('{"ok":true}')
    monkeypatch.setattr(logx_utils.urllib.request, 'urlopen', fake_urlopen)

    status, text = post_url_json('https://api.pota.app/spot/', {'a': 1},
                                  headers={'User-Agent': 'LogXAI/9.9'})
    assert status == 200
    assert text == '{"ok":true}'
    assert captured['url'] == 'https://api.pota.app/spot/'
    assert captured['method'] == 'POST'
    assert captured['body'] == {'a': 1}
    assert captured['content_type'] == 'application/json'
    assert captured['user_agent'] == 'LogXAI/9.9'   # écrase le défaut du module


def test_post_url_json_erreur_http_remontee_avec_le_corps(monkeypatch):
    """Un 4xx/5xx doit remonter (status, corps) — PAS (None, None), pour que
    l'appelant distingue « refusé par le serveur » de « injoignable »."""
    def fake_urlopen(req, timeout=10, context=None):
        raise urllib.error.HTTPError(req.full_url, 400, 'Bad Request',
                                     None, io.BytesIO(b'reference invalide'))
    monkeypatch.setattr(logx_utils.urllib.request, 'urlopen', fake_urlopen)

    status, text = post_url_json('https://api.pota.app/spot/', {'a': 1})
    assert status == 400
    assert 'reference invalide' in text


def test_post_url_json_reseau_injoignable(monkeypatch):
    def boom(req, timeout=10, context=None):
        raise OSError('timeout')
    monkeypatch.setattr(logx_utils.urllib.request, 'urlopen', boom)

    assert post_url_json('https://api.pota.app/spot/', {'a': 1}) == (None, None)
