# -*- coding: utf-8 -*-
"""Tests des destinations d'upload QSL : QRZCQ (API JSON documentée,
qrzcq.com/page/developers) et HRDLog.net (aucune doc publique — implémenté
depuis le code source réel de la lib cliente open-source iw1qlh/HRDLOG-net-
library, endpoint NewEntry.aspx, conçu PAR QSO unique). Plus le dispatch
unifié qsl.upload_log qui remplace les branches if/elif par service."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import radiocontest_qsl as qsl

QRZCQ_CFG = {'qrzcq_callsign': 'F6KQJ', 'qrzcq_api_key': 'ABCDEF'}
HRDLOG_CFG = {'hrdlog_callsign': 'F6KQJ', 'hrdlog_code': '0000000000'}
QSO = {'call': 'DL1AA', 'band': '14', 'mode': 'SSB', 'date': '20260710',
       'time': '1230', 'rst_sent': '59', 'rst_rcvd': '59'}


class _FakeResp:
    def __init__(self, text):
        self._text = text.encode('utf-8')
    def read(self):
        return self._text
    def __enter__(self):
        return self
    def __exit__(self, *a):
        return False


# ─── QRZCQ ──────────────────────────────────────────────────────────────────

def test_qrzcq_non_configure():
    r = qsl.upload_qrzcq({}, 'adif')
    assert not r['ok'] and 'non configuré' in r['error']


def test_qrzcq_upload_ok(monkeypatch):
    captured = {}
    def fake_urlopen(req, timeout=30, context=None):
        captured['url'] = req.full_url
        captured['body'] = json.loads(req.data.decode('utf-8'))
        captured['content_type'] = req.get_header('Content-type')
        return _FakeResp('{"status":"OK","message":"DATA_QUEUED"}')
    monkeypatch.setattr(qsl.urllib.request, 'urlopen', fake_urlopen)
    r = qsl.upload_qrzcq(QRZCQ_CFG, 'ADIF-CONTENT')
    assert r['ok'] and r['service'] == 'QRZCQ' and r['response'] == 'DATA_QUEUED'
    assert captured['url'] == qsl.QRZCQ_UPLOAD_URL
    assert captured['content_type'] == 'application/json'
    assert captured['body'] == {'auth': {'call': 'F6KQJ', 'key': 'ABCDEF'},
                                'data': {'adif': 'ADIF-CONTENT'}}


def test_qrzcq_upload_erreur_status(monkeypatch):
    monkeypatch.setattr(qsl.urllib.request, 'urlopen',
                        lambda req, timeout=30, context=None: _FakeResp('{"status":"ERROR","message":"BAD_KEY"}'))
    r = qsl.upload_qrzcq(QRZCQ_CFG, 'adif')
    assert not r['ok'] and r['error'] == 'BAD_KEY'


def test_qrzcq_reponse_illisible(monkeypatch):
    monkeypatch.setattr(qsl.urllib.request, 'urlopen',
                        lambda req, timeout=30, context=None: _FakeResp('pas du json'))
    r = qsl.upload_qrzcq(QRZCQ_CFG, 'adif')
    assert not r['ok'] and 'pas du json' in r['error']


def test_qrzcq_injoignable(monkeypatch):
    def boom(req, timeout=30, context=None):
        raise OSError('timeout')
    monkeypatch.setattr(qsl.urllib.request, 'urlopen', boom)
    r = qsl.upload_qrzcq(QRZCQ_CFG, 'adif')
    assert not r['ok'] and 'injoignable' in r['error']


# ─── HRDLog ─────────────────────────────────────────────────────────────────

def test_hrdlog_non_configure():
    r = qsl.upload_hrdlog({}, [QSO])
    assert not r['ok'] and 'non configuré' in r['error']


def test_hrdlog_aucun_qso():
    r = qsl.upload_hrdlog(HRDLOG_CFG, [])
    assert not r['ok'] and 'Aucun QSO' in r['error']


def test_single_qso_adif_sans_en_tete():
    record = qsl._single_qso_adif(QSO, {})
    assert '<EOH>' not in record and '<adif_ver' not in record
    assert record.startswith('<call:5>DL1AA') and record.rstrip().endswith('<EOR>')


def test_hrdlog_tous_envoyes_ok(monkeypatch):
    monkeypatch.setattr(qsl, '_hrdlog_post_one', lambda host, call, code, rec, timeout=8: '<NewEntry><insert>1</insert></NewEntry>')
    r = qsl.upload_hrdlog(HRDLOG_CFG, [QSO, dict(QSO, call='G3XYZ')])
    assert r['ok'] and r['sent'] == 2 and r['failed'] == 0


def test_hrdlog_echec_partiel(monkeypatch):
    calls = {'n': 0}
    def fake(host, call, code, rec, timeout=8):
        calls['n'] += 1
        if 'G3XYZ' in rec:
            raise OSError('injoignable')
        return '<NewEntry><insert>1</insert></NewEntry>'
    monkeypatch.setattr(qsl, '_hrdlog_post_one', fake)
    r = qsl.upload_hrdlog(HRDLOG_CFG, [QSO, dict(QSO, call='G3XYZ')])
    assert r['ok'] is True  # au moins un envoyé -> ok global
    assert r['sent'] == 1 and r['failed'] == 1


def test_hrdlog_repli_second_host(monkeypatch):
    """Le host primaire (robot.hrdlog.net) échoue -> le secours (www) est tenté
    avant de compter le QSO en échec."""
    tried = []
    def fake(host, call, code, rec, timeout=8):
        tried.append(host)
        if host == qsl.HRDLOG_HOSTS[0]:
            raise OSError('injoignable')
        return '<NewEntry><insert>1</insert></NewEntry>'
    monkeypatch.setattr(qsl, '_hrdlog_post_one', fake)
    r = qsl.upload_hrdlog(HRDLOG_CFG, [QSO])
    assert r['sent'] == 1 and tried == list(qsl.HRDLOG_HOSTS)


def test_hrdlog_reponse_avec_erreur_xml(monkeypatch):
    monkeypatch.setattr(qsl, '_hrdlog_post_one',
                        lambda host, call, code, rec, timeout=8: '<error>Duplicate</error>')
    r = qsl.upload_hrdlog(HRDLOG_CFG, [QSO])
    assert not r['ok'] and r['sent'] == 0 and r['failed'] == 1
    assert 'Duplicate' in r['error']


def test_hrdlog_insert_zero_sans_balise_error_est_bien_un_echec(monkeypatch):
    """Régression : vérifié en direct contre le vrai serveur HRDLog — des
    identifiants invalides renvoient '<insert>0</insert>' SANS balise <error>.
    Une détection basée sur la seule absence de <error> classait ça en succès."""
    real_response = ('<?xml version="1.0" ?>\n<HrdLog xmlns="http://xml.hrdlog.com">\n'
                     '<NewEntry>\n<insert>0</insert>\n<id>0</id></NewEntry>\n</HrdLog>\n')
    monkeypatch.setattr(qsl, '_hrdlog_post_one', lambda host, call, code, rec, timeout=8: real_response)
    r = qsl.upload_hrdlog(HRDLOG_CFG, [QSO])
    assert r['ok'] is False and r['sent'] == 0 and r['failed'] == 1


# ─── Dispatch unifié ────────────────────────────────────────────────────────

def test_upload_log_service_inconnu():
    r = qsl.upload_log({}, 'inexistant', [QSO])
    assert not r['ok'] and 'inconnu' in r['error'].lower()


def test_upload_log_dispatch_construit_adif_une_fois(monkeypatch):
    captured = {}
    def fake_eqsl(cfg, adif):
        captured['adif'] = adif
        return {'ok': True, 'service': 'eQSL'}
    monkeypatch.setattr(qsl, '_ADIF_UPLOAD_HANDLERS', {'eqsl': fake_eqsl})
    r = qsl.upload_log({}, 'eqsl', [QSO])
    assert r['ok'] and '<call:5>DL1AA' in captured['adif']


def test_upload_log_dispatch_hrdlog_recoit_les_qso_bruts(monkeypatch):
    captured = {}
    def fake_hrdlog(cfg, qsos):
        captured['qsos'] = qsos
        return {'ok': True, 'sent': len(qsos), 'failed': 0}
    monkeypatch.setattr(qsl, 'upload_hrdlog', fake_hrdlog)
    r = qsl.upload_log({}, 'hrdlog', [QSO])
    assert r['ok'] and captured['qsos'] == [QSO]


# ─── Réglages ───────────────────────────────────────────────────────────────

def test_qsl_settings_qrzcq_hrdlog():
    s = qsl.qsl_settings({'qrzcq_callsign': 'f6kqj', 'qrzcq_api_key': 'x',
                          'hrdlog_callsign': 'f6kqj', 'hrdlog_code': 'y'})
    assert s['qrzcq_enabled'] and s['qrzcq_callsign'] == 'F6KQJ'
    assert s['hrdlog_enabled'] and s['hrdlog_callsign'] == 'F6KQJ'


def test_qsl_status_expose_qrzcq_hrdlog():
    st = qsl.qsl_status(QRZCQ_CFG)
    assert st['qrzcq'] is True and st['hrdlog'] is False
