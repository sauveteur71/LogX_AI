# -*- coding: utf-8 -*-
"""Tests du push temps réel QRZ Logbook (logx_qrz_push.py) — format vérifié
contre la doc officielle QRZ (qrz.com/docs/logbook/QRZLogbookAPI.html) :
POST form-urlencoded KEY/ACTION/ADIF, réponse elle-même form-urlencoded
(RESULT=OK|FAIL|REPLACE|AUTH, LOGID, REASON), pas du JSON."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_qrz_push as qrzpush

QSO = {'call': 'DL1AA', 'band': '14', 'mode': 'SSB', 'date': '20260710',
       'time': '1230', 'rst_sent': '59', 'rst_rcvd': '59'}
CFG = {'qrz_logbook_key': 'ABCD-0A0B-1C1D-2E2F', 'qrz_logbook_push': '1'}


# ─── Réglages ─────────────────────────────────────────────────────────────────

def test_settings_vide_par_defaut_inactif():
    s = qrzpush.qrz_logbook_settings({})
    assert not s['configured'] and not s['push_enabled']


def test_settings_cle_seule_sans_toggle_ne_push_pas_auto():
    """Comme clublog_live : la clé seule ne suffit pas, il faut aussi le
    bouton d'envoi auto activé — laisse la possibilité d'un usage manuel
    futur sans pousser automatiquement chaque QSO."""
    s = qrzpush.qrz_logbook_settings({'qrz_logbook_key': 'ABCD'})
    assert s['configured'] and not s['push_enabled']


def test_settings_cle_et_toggle_active_push():
    s = qrzpush.qrz_logbook_settings(CFG)
    assert s['configured'] and s['push_enabled']


# ─── push_qso (INSERT) ────────────────────────────────────────────────────────

def test_push_qso_non_configure():
    r = qrzpush.push_qso({}, QSO)
    assert not r['ok'] and 'non configuré' in r['error']


def test_push_qso_succes(monkeypatch):
    captured = {}
    def fake_post_url_form(url, fields, timeout=10, headers=None):
        captured['url'] = url
        captured['fields'] = fields
        captured['headers'] = headers
        return 200, 'RESULT=OK&LOGID=123&COUNT=1'
    monkeypatch.setattr('logx_utils.post_url_form', fake_post_url_form)

    r = qrzpush.push_qso(CFG, QSO)
    assert r['ok'] is True and r['logid'] == '123'
    assert captured['url'] == qrzpush.QRZ_LOGBOOK_URL
    assert captured['fields']['KEY'] == 'ABCD-0A0B-1C1D-2E2F'
    assert captured['fields']['ACTION'] == 'INSERT'
    # Un seul enregistrement ADIF, sans en-tête <EOH> (cf. logx_qsl._single_qso_adif).
    assert '<EOH>' not in captured['fields']['ADIF']
    assert captured['fields']['ADIF'].rstrip().endswith('<EOR>')
    assert 'LogXAI/' in captured['headers']['User-Agent']


def test_push_qso_cle_refusee(monkeypatch):
    monkeypatch.setattr('logx_utils.post_url_form',
                        lambda url, fields, timeout=10, headers=None: (200, 'RESULT=AUTH&REASON=Invalid+API+Key'))
    r = qrzpush.push_qso(CFG, QSO)
    assert not r['ok'] and r['result'] == 'AUTH' and 'Invalid' in r['error']


def test_push_qso_doublon_fail(monkeypatch):
    monkeypatch.setattr('logx_utils.post_url_form',
                        lambda url, fields, timeout=10, headers=None: (200, 'RESULT=FAIL&REASON=Duplicate'))
    r = qrzpush.push_qso(CFG, QSO)
    assert not r['ok'] and 'Duplicate' in r['error']


def test_push_qso_injoignable(monkeypatch):
    monkeypatch.setattr('logx_utils.post_url_form',
                        lambda url, fields, timeout=10, headers=None: (None, None))
    r = qrzpush.push_qso(CFG, QSO)
    assert not r['ok'] and 'injoignable' in r['error']


def test_push_qso_replace_compte_comme_succes(monkeypatch):
    """OPTION=REPLACE (non envoyé ici mais accepté côté serveur) peut renvoyer
    RESULT=REPLACE plutôt que OK — les deux sont un succès."""
    monkeypatch.setattr('logx_utils.post_url_form',
                        lambda url, fields, timeout=10, headers=None: (200, 'RESULT=REPLACE&LOGID=99&COUNT=1'))
    r = qrzpush.push_qso(CFG, QSO)
    assert r['ok'] is True and r['result'] == 'REPLACE'


# ─── test_connection (ACTION=STATUS) ──────────────────────────────────────────

def test_connection_sans_cle():
    r = qrzpush.test_connection({})
    assert not r['ok']


def test_connection_ok(monkeypatch):
    captured = {}
    def fake(url, fields, timeout=10, headers=None):
        captured['fields'] = fields
        return 200, 'RESULT=OK&TOTALQSO=1234&CONFIRMED=56'
    monkeypatch.setattr('logx_utils.post_url_form', fake)
    r = qrzpush.test_connection(CFG)
    assert r['ok'] is True
    assert r['status']['TOTALQSO'] == '1234'
    assert captured['fields']['ACTION'] == 'STATUS'


def test_connection_refusee(monkeypatch):
    monkeypatch.setattr('logx_utils.post_url_form',
                        lambda url, fields, timeout=10, headers=None: (200, 'RESULT=AUTH&REASON=Invalid+API+Key'))
    r = qrzpush.test_connection(CFG)
    assert not r['ok'] and 'Invalid' in r['error']
