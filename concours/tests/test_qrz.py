# -*- coding: utf-8 -*-
"""Tests de la recherche QRZ.com (parsing XML, session, cache) — sans réseau."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_qrz as qrz

AUTH_OK = ('<QRZDatabase><Session><Key>ABC123SESSION</Key>'
           '<SubExp>Mon Dec 31</SubExp></Session></QRZDatabase>')
AUTH_ERR = ('<QRZDatabase><Session><Error>Username/password incorrect</Error>'
            '</Session></QRZDatabase>')
LOOKUP_OK = ('<QRZDatabase><Callsign><call>F6KQJ</call>'
             '<fname>Radio-Club</fname><name>GCEBP43</name>'
             '<addr2>Le Puy-en-Velay</addr2><state></state>'
             '<country>France</country><grid>JN15XC</grid><dxcc>227</dxcc>'
             '<image>https://cdn-xml.qrz.com/z/f6kqj/f6kqj.jpg</image>'
             '</Callsign><Session><Key>ABC123SESSION</Key></Session></QRZDatabase>')
LOOKUP_SANS_PHOTO = ('<QRZDatabase><Callsign><call>F6KQJ</call>'
             '<fname>Radio-Club</fname><name>GCEBP43</name>'
             '<addr2>Le Puy-en-Velay</addr2><state></state>'
             '<country>France</country><grid>JN15XC</grid><dxcc>227</dxcc>'
             '</Callsign><Session><Key>ABC123SESSION</Key></Session></QRZDatabase>')
LOOKUP_PHOTO_SCHEME_INVALIDE = ('<QRZDatabase><Callsign><call>F6KQJ</call>'
             '<fname>Radio-Club</fname><name>GCEBP43</name>'
             '<image>javascript:alert(1)</image>'
             '</Callsign><Session><Key>ABC123SESSION</Key></Session></QRZDatabase>')
LOOKUP_NOTFOUND = ('<QRZDatabase><Session><Error>Not found: ZZ9ZZZ</Error>'
                   '</Session></QRZDatabase>')


def _reset():
    qrz._session.update(key='', ts=0)
    qrz._lookup_cache.clear()


def test_tag_extraction():
    assert qrz._tag(AUTH_OK, 'Key') == 'ABC123SESSION'
    assert qrz._tag(AUTH_ERR, 'Error') == 'Username/password incorrect'
    assert qrz._tag(LOOKUP_OK, 'grid') == 'JN15XC'


def test_lookup_ok(monkeypatch):
    _reset()
    calls = iter([AUTH_OK, LOOKUP_OK])
    monkeypatch.setattr('logx_utils.fetch_url', lambda url, timeout=15, log_url=True: next(calls))
    r = qrz.lookup('F6KQJ', 'user', 'pw')
    assert r['ok'] and r['call'] == 'F6KQJ'
    assert r['name'] == 'Radio-Club GCEBP43'
    assert r['qth'] == 'Le Puy-en-Velay' and r['grid'] == 'JN15XC'
    assert r['country'] == 'France'
    assert r['image'] == 'https://cdn-xml.qrz.com/z/f6kqj/f6kqj.jpg'


def test_lookup_sans_photo(monkeypatch):
    _reset()
    calls = iter([AUTH_OK, LOOKUP_SANS_PHOTO])
    monkeypatch.setattr('logx_utils.fetch_url', lambda url, timeout=15, log_url=True: next(calls))
    r = qrz.lookup('F6KQJ', 'user', 'pw')
    assert r['ok'] and r['image'] == ''


def test_lookup_photo_schema_non_http_rejete(monkeypatch):
    """Une balise <image> avec un schéma autre que http(s) (ex. javascript:)
    n'est jamais renvoyée au client — elle serait injectée telle quelle dans
    un <img src> côté logbook."""
    _reset()
    calls = iter([AUTH_OK, LOOKUP_PHOTO_SCHEME_INVALIDE])
    monkeypatch.setattr('logx_utils.fetch_url', lambda url, timeout=15, log_url=True: next(calls))
    r = qrz.lookup('F6KQJ', 'user', 'pw')
    assert r['ok'] and r['image'] == ''


def test_auth_refusee(monkeypatch):
    _reset()
    monkeypatch.setattr('logx_utils.fetch_url', lambda url, timeout=15, log_url=True: AUTH_ERR)
    r = qrz.lookup('F6KQJ', 'user', 'badpw')
    assert not r['ok'] and 'incorrect' in r['error']


def test_indicatif_introuvable(monkeypatch):
    _reset()
    calls = iter([AUTH_OK, LOOKUP_NOTFOUND])
    monkeypatch.setattr('logx_utils.fetch_url', lambda url, timeout=15, log_url=True: next(calls))
    r = qrz.lookup('ZZ9ZZZ', 'user', 'pw')
    assert not r['ok'] and 'introuvable' in r['error'].lower() or 'Not found' in r['error']


def test_cache_evite_double_requete(monkeypatch):
    _reset()
    n = {'c': 0}
    seq = iter([AUTH_OK, LOOKUP_OK])
    def fake(url, timeout=15, log_url=True):
        n['c'] += 1
        return next(seq)
    monkeypatch.setattr('logx_utils.fetch_url', fake)
    qrz.lookup('F6KQJ', 'user', 'pw')
    qrz.lookup('F6KQJ', 'user', 'pw')      # 2e appel : depuis le cache
    assert n['c'] == 2                       # auth + 1 lookup, pas 4


def test_pas_didentifiants():
    _reset()
    r = qrz.lookup('F6KQJ', '', '')
    assert not r['ok'] and 'configur' in r['error'].lower()


def test_settings():
    assert qrz.qrz_settings({})['enabled'] is False
    s = qrz.qrz_settings({'qrz_user': 'F6KQJ', 'qrz_password': 'x'})
    assert s['enabled'] and s['user'] == 'F6KQJ'
