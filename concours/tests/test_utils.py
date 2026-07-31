# -*- coding: utf-8 -*-
"""Tests des fonctions pures de logx_utils — cas vérifiés à la main."""
import io
import json as _json
import os
import sys
import urllib.error

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_utils
from logx_utils import (locator_to_latlon, haversine, bearing,
                                cardinal, is_digital_mode, post_url_json,
                                post_url_form)


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


def test_locator_4_caracteres_donne_le_CENTRE_DU_CARRE():
    """Correctif M8 : un locator à 4 caractères est un Maidenhead valide, les
    spots PSK Reporter en donnent souvent — il ne doit pas être rejeté.

    CE TEST AFFIRMAIT AUTRE CHOSE, et c'était le défaut : il exigeait
    `locator_to_latlon('JN15') == locator_to_latlon('JN15MM')`, c'est-à-dire
    la façon dont le calcul était FAIT, pas le résultat attendu. Or 'M' est la
    13ᵉ lettre et le milieu des 24 lettres n'en est aucune — il tombe entre
    'L' et 'M'. Le complément par 'MM' plaçait donc le point 3,8 km au
    nord-est du centre, systématiquement, sur tout locator à 4 caractères.
    Aucun complément par lettres ne peut donner le centre : il faut le calculer.
    """
    lat, lon = locator_to_latlon('JN15')
    # Coin bas-gauche de JN15 : J=9 → 9×20−180 = 0, +1×2 = 2° E
    #                           N=13 → 13×10−90 = 40, +5 = 45° N
    # Centre du carré 2°×1° : +1° de longitude, +0,5° de latitude.
    assert abs(lon - 3.0) < 1e-9, lon
    assert abs(lat - 45.5) < 1e-9, lat
    assert locator_to_latlon('jn15') == locator_to_latlon('JN15')


def test_le_centre_du_carre_est_bien_au_milieu_de_ses_sous_carres():
    """Vérification croisée, indépendante de la formule : le centre du carré
    doit tomber à mi-chemin entre les sous-carrés extrêmes AA et XX."""
    la_aa, lo_aa = locator_to_latlon('JN15AA')
    la_xx, lo_xx = locator_to_latlon('JN15XX')
    la, lo = locator_to_latlon('JN15')
    assert abs(la - (la_aa + la_xx) / 2) < 1e-9
    assert abs(lo - (lo_aa + lo_xx) / 2) < 1e-9


# ─── Locators invalides : refusés, plus jamais « plausibles » ────────────────
# Il n'y avait AUCUNE validation, et le `except:` nu ne rattrapait que le int()
# des chiffres. Les locators arrivent du cluster, de PSK Reporter, de l'import
# ADIF d'un log tiers et surtout de la SAISIE MANUELLE en concours, où la faute
# de frappe est la règle. En THF, un locator faux c'est un multiplicateur faux
# et une distance fausse — des points refusés au dépouillement.

@pytest.mark.parametrize('loc,pourquoi', [
    ('JN18ZZ', "sous-carré 'Z' : au-delà de X, le point sortait de son carré"),
    ('JN18YY', "sous-carré 'Y' : idem"),
    ('ZZ99XX', "champ 'Z' : au-delà de R, longitude de 339° rendue sans erreur"),
    ('SS00AA', "champ 'S' : au-delà de R"),
    ('JN18@@', 'caractères non alphabétiques : point situé AVANT le coin'),
    ('J1N8DA', 'lettres et chiffres intervertis'),
    ('JNAADA', 'lettres à la place des chiffres du carré'),
    ('12 34', 'saisie qui n\'a rien d\'un locator'),
])
def test_un_locator_invalide_est_REFUSE(loc, pourquoi):
    assert locator_to_latlon(loc) == (None, None), (loc, pourquoi)


@pytest.mark.parametrize('loc', ['JN15XC', 'jn15xc', 'JN15', 'AA00AA',
                                 'RR99XX', 'JN18DA', ' JN15XC '])
def test_un_locator_valide_passe_toujours(loc):
    """Garde-fou en miroir : la validation ne doit rien refuser de légitime.
    82 appels dans le code en dépendent."""
    lat, lon = locator_to_latlon(loc)
    assert lat is not None and lon is not None, loc
    assert -90 <= lat <= 90 and -180 <= lon <= 180, (loc, lat, lon)


def test_le_locator_etendu_a_8_caracteres_reste_accepte():
    """L'ADIF autorise un GRIDSQUARE à 8 caractères. On ignore la subdivision
    supplémentaire — le sous-carré suffit pour une distance ou un azimut — mais
    le refuser casserait l'import d'un log tiers."""
    assert locator_to_latlon('JN15XC25') == locator_to_latlon('JN15XC')


def test_toute_position_rendue_est_sur_la_Terre():
    """Le vrai invariant : quoi qu'on donne en entrée, on ne renvoie jamais un
    point qui n'existe pas. 'ZZ99XX' rendait une longitude de 339°."""
    essais = ['JN15XC', 'JN15', 'AA00AA', 'RR99XX', 'ZZ99XX', 'SS00AA',
              'JN18ZZ', 'JN18@@', '', None, 'X', '////']
    for loc in essais:
        lat, lon = locator_to_latlon(loc)
        if lat is None:
            continue
        assert -90 <= lat <= 90, (loc, lat)
        assert -180 <= lon <= 180, (loc, lon)


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


# ─── post_url_form ────────────────────────────────────────────────────────────
# Même pattern que post_url_json ci-dessus, mais corps
# application/x-www-form-urlencoded — utilisé par QRZ Logbook, Club Log
# realtime.php, SOTA SSO (token exchange)...

def test_post_url_form_succes(monkeypatch):
    captured = {}
    def fake_urlopen(req, timeout=10, context=None):
        captured['url'] = req.full_url
        captured['method'] = req.get_method()
        captured['body'] = req.data.decode('utf-8')
        captured['content_type'] = req.get_header('Content-type')
        return _FakeResp('RESULT=OK&LOGID=42')
    monkeypatch.setattr(logx_utils.urllib.request, 'urlopen', fake_urlopen)

    status, text = post_url_form('https://logbook.qrz.com/api',
                                  {'KEY': 'abc', 'ACTION': 'STATUS'},
                                  headers={'User-Agent': 'LogXAI/9.9'})
    assert status == 200 and text == 'RESULT=OK&LOGID=42'
    assert captured['method'] == 'POST'
    assert captured['content_type'] == 'application/x-www-form-urlencoded'
    assert captured['body'] == 'KEY=abc&ACTION=STATUS'


def test_post_url_form_erreur_http_remontee_avec_le_corps(monkeypatch):
    def fake_urlopen(req, timeout=10, context=None):
        raise urllib.error.HTTPError(req.full_url, 403, 'Forbidden',
                                     None, io.BytesIO(b'quota exceeded'))
    monkeypatch.setattr(logx_utils.urllib.request, 'urlopen', fake_urlopen)

    status, text = post_url_form('https://clublog.org/realtime.php', {'a': 1})
    assert status == 403
    assert 'quota exceeded' in text


def test_post_url_form_reseau_injoignable(monkeypatch):
    def boom(req, timeout=10, context=None):
        raise OSError('timeout')
    monkeypatch.setattr(logx_utils.urllib.request, 'urlopen', boom)

    assert post_url_form('https://clublog.org/realtime.php', {'a': 1}) == (None, None)
