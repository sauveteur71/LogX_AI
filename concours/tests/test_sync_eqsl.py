# -*- coding: utf-8 -*-
"""Lot 1 — sync_eqsl : téléchargement descendant des confirmations eQSL.

L'API eQSL DownloadInBox.cfm renvoie une page HTML contenant un lien vers un
fichier .adi (pas l'ADIF directement) — flux en 2 temps. sync_eqsl calque
sync_lotw : GET DownloadInBox → parse le lien → GET l'ADIF →
parse_confirmations(…, 'eqsl') → merge_confirmations. Réseau injecté via
_http_get (jamais de vraie requête)."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_qsl as qsl

_HTML_AVEC_LIEN = (
    '<html><body>Your inbox is ready. '
    '<a href="/downloadedfiles/F4TEST_inbox.adi">Download ADI</a> '
    '<a href="/downloadedfiles/F4TEST_inbox.txt">Download TXT</a></body></html>')

_ADIF_1_CONFIRME = (
    'eQSL.cc DownloadInBox\n<PROGRAMID:6>eQSL.cc<EOH>\n'
    '<CALL:5>F4ABC<BAND:3>20M<MODE:3>SSB<QSL_RCVD:1>Y<QSLRDATE:8>20260810<EOR>\n')


def _fake_http(mapping, journal=None):
    def _get(url, timeout=20):
        if journal is not None:
            journal.append(url)
        for frag, rep in mapping.items():
            if frag in url:
                return rep
        return ''
    return _get


def _prep(monkeypatch, tmp_path):
    monkeypatch.setattr(qsl, 'qsl_settings',
                        lambda cfg: {'eqsl_enabled': True,
                                     'eqsl_user': 'F4TEST', 'eqsl_password': 'secret'})
    monkeypatch.setattr(qsl, 'CONFIRM_FILE', str(tmp_path / 'conf.json'))


def test_sync_eqsl_descend_et_merge_les_confirmations(monkeypatch, tmp_path):
    _prep(monkeypatch, tmp_path)
    monkeypatch.setattr(qsl, '_http_get', _fake_http(
        {'DownloadInBox': _HTML_AVEC_LIEN, '.adi': _ADIF_1_CONFIRME}))
    res = qsl.sync_eqsl({})
    assert res['ok'] is True
    assert res['confirmed_downloaded'] == 1
    assert res['newly_added'] == 1
    db = json.load(open(str(tmp_path / 'conf.json'), encoding='utf-8'))
    # Bande interne = fréquence MHz : ADIF '20M' -> '14' (clé CALL|MHz|MODE).
    assert 'F4ABC|14|SSB' in db and 'eqsl' in db['F4ABC|14|SSB']


def test_sync_eqsl_incremental_passe_rcvdsince(monkeypatch, tmp_path):
    _prep(monkeypatch, tmp_path)
    journal = []
    monkeypatch.setattr(qsl, '_http_get', _fake_http(
        {'DownloadInBox': _HTML_AVEC_LIEN, '.adi': _ADIF_1_CONFIRME}, journal))
    qsl.sync_eqsl({}, since='202601010000')
    dl = next(u for u in journal if 'DownloadInBox' in u)
    assert 'RcvdSince=202601010000' in dl


def test_sync_eqsl_creds_refuses_sans_lien(monkeypatch, tmp_path):
    _prep(monkeypatch, tmp_path)
    monkeypatch.setattr(qsl, '_http_get', _fake_http(
        {'DownloadInBox': '<html>Password incorrect</html>'}))
    res = qsl.sync_eqsl({})   # page sans lien .adi -> échec propre, pas d'exception
    assert res['ok'] is False


def test_sync_eqsl_non_configure(monkeypatch):
    monkeypatch.setattr(qsl, 'qsl_settings', lambda cfg: {'eqsl_enabled': False})
    res = qsl.sync_eqsl({})
    assert res['ok'] is False and 'eQSL' in res['error']
