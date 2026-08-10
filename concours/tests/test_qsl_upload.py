# -*- coding: utf-8 -*-
"""Tests des destinations d'upload QSL : QRZCQ (API JSON documentée,
qrzcq.com/page/developers) et HRDLog.net (aucune doc publique — implémenté
depuis le code source réel de la lib cliente open-source iw1qlh/HRDLOG-net-
library, endpoint NewEntry.aspx, conçu PAR QSO unique). Plus le dispatch
unifié qsl.upload_log qui remplace les branches if/elif par service."""
import json
import os
import sys
import threading

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_qsl as qsl

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


def test_hrdlog_coupe_circuit_apres_echecs_consecutifs(monkeypatch):
    """Hors ligne : ne doit pas retenter les 2 hôtes pour CHAQUE QSO restant
    (40 min de gel possible sur 150 QSO avant ce correctif) — s'arrête après
    HRDLOG_FAIL_CIRCUIT échecs consécutifs et compte le reste en échec."""
    calls = {'n': 0}
    def boom(host, call, code, rec, timeout=8):
        calls['n'] += 1
        raise OSError('injoignable')
    monkeypatch.setattr(qsl, '_hrdlog_post_one', boom)
    qsos = [dict(QSO, call=f'DL{i}AA') for i in range(20)]
    r = qsl.upload_hrdlog(HRDLOG_CFG, qsos)
    assert not r['ok'] and r['sent'] == 0 and r['failed'] == 20
    assert calls['n'] == qsl.HRDLOG_FAIL_CIRCUIT * len(qsl.HRDLOG_HOSTS)
    assert 'Arrêt anticipé' in r['error']


def test_hrdlog_pas_de_coupe_circuit_si_succes_intermittents(monkeypatch):
    """Un succès remet le compteur d'échecs consécutifs à zéro — pas de coupure
    tant que le réseau répond, même par intermittence."""
    def alterne(host, call, code, rec, timeout=8):
        if host == qsl.HRDLOG_HOSTS[0]:
            raise OSError('injoignable')
        return '<NewEntry><insert>1</insert></NewEntry>'
    monkeypatch.setattr(qsl, '_hrdlog_post_one', alterne)
    qsos = [dict(QSO, call=f'DL{i}AA') for i in range(10)]
    r = qsl.upload_hrdlog(HRDLOG_CFG, qsos)
    assert r['ok'] and r['sent'] == 10 and r['failed'] == 0


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


# ─── Club Log Live Stream (realtime.php) ─────────────────────────────────────
# Format vérifié contre la doc officielle Club Log (clublog.freshdesk.com,
# "How To Upload QSOs In Real-Time") : POST url-encodé email/password/
# callsign/adif, `adif` = EXACTEMENT un enregistrement (pas de lot, pas
# d'en-tête) ; throttle stricte -> un 403 doit couper les essais suivants.
# Chaque test utilise des identifiants DISTINCTS : le disjoncteur (module-
# level) se réarme automatiquement dès que les identifiants changent (voir
# _clublog_creds_fp), ce qui isole les tests entre eux sans fixture dédiée.

def _clublog_cfg(suffix):
    return {'clublog_email': f'{suffix}@example.com', 'clublog_callsign': 'F6KQJ',
            'clublog_password': f'app-password-{suffix}', 'clublog_api_key': f'key-{suffix}'}


def test_realtime_push_envoie_un_seul_enregistrement_sans_en_tete(monkeypatch):
    """Régression : l'ancien code envoyait export.build_adif() complet (en-tête
    <adif_ver>/<programid>/<EOH> inclus) alors que Club Log exige EXACTEMENT
    un enregistrement terminé par <EOR> pour cette route temps réel."""
    captured = {}
    def fake_post_url_form(url, fields, timeout=20, headers=None):
        captured['url'] = url
        captured['fields'] = fields
        return 200, 'OK'
    monkeypatch.setattr('logx_utils.post_url_form', fake_post_url_form)

    r = qsl.realtime_push(_clublog_cfg('s1'), QSO)
    assert r['ok'] is True
    assert captured['url'] == 'https://clublog.org/realtime.php'
    assert '<EOH>' not in captured['fields']['adif'] and '<adif_ver' not in captured['fields']['adif']
    assert captured['fields']['adif'].rstrip().endswith('<EOR>')
    assert captured['fields']['email'] == 's1@example.com'
    assert 'api' not in captured['fields']  # realtime.php n'attend pas de clé API (contrairement à putlogs.php)


def test_realtime_push_403_declenche_le_disjoncteur(monkeypatch):
    """Un 403 doit arrêter immédiatement les tentatives suivantes (pas de
    retry agressif) — le 2e appel ne doit PLUS toucher le réseau."""
    calls = {'n': 0}
    def fake_post_url_form(url, fields, timeout=20, headers=None):
        calls['n'] += 1
        return 403, 'blocked'
    monkeypatch.setattr('logx_utils.post_url_form', fake_post_url_form)

    cfg = _clublog_cfg('s2')
    r1 = qsl.realtime_push(cfg, QSO)
    assert r1['ok'] is False and r1.get('blocked') is True

    r2 = qsl.realtime_push(cfg, dict(QSO, call='G3XYZ'))
    assert r2['ok'] is False and r2.get('blocked') is True
    assert calls['n'] == 1   # le 2e appel n'a PAS retenté le réseau


def test_realtime_push_disjoncteur_se_reinitialise_si_identifiants_changent(monkeypatch):
    """Changer les identifiants (l'utilisateur corrige sa config) redonne sa
    chance — le disjoncteur ne doit pas bloquer indéfiniment."""
    calls = {'n': 0}
    def fake_post_url_form(url, fields, timeout=20, headers=None):
        calls['n'] += 1
        return 403, 'blocked'
    monkeypatch.setattr('logx_utils.post_url_form', fake_post_url_form)

    cfg = _clublog_cfg('s3')
    qsl.realtime_push(cfg, QSO)
    assert calls['n'] == 1

    new_cfg = _clublog_cfg('s3-corrige')
    monkeypatch.setattr('logx_utils.post_url_form', lambda *a, **k: (200, 'OK'))
    r = qsl.realtime_push(new_cfg, QSO)
    assert r['ok'] is True


def test_realtime_push_erreur_non_403_ne_declenche_pas_le_disjoncteur(monkeypatch):
    """Une erreur transitoire (500) ne doit pas bloquer les QSO suivants,
    contrairement à un 403 (refus explicite)."""
    calls = {'n': 0}
    def fake_post_url_form(url, fields, timeout=20, headers=None):
        calls['n'] += 1
        return 500, 'server error'
    monkeypatch.setattr('logx_utils.post_url_form', fake_post_url_form)

    cfg = _clublog_cfg('s4')
    r1 = qsl.realtime_push(cfg, QSO)
    assert r1['ok'] is False and not r1.get('blocked')
    qsl.realtime_push(cfg, dict(QSO, call='G3XYZ'))
    assert calls['n'] == 2   # bien retenté (pas de disjoncteur sur une simple erreur serveur)


def test_realtime_push_reseau_injoignable(monkeypatch):
    monkeypatch.setattr('logx_utils.post_url_form', lambda *a, **k: (None, None))
    r = qsl.realtime_push(_clublog_cfg('s5'), QSO)
    assert not r['ok'] and 'injoignable' in r['error']


def test_realtime_push_protege_le_disjoncteur_par_un_verrou_dedie(monkeypatch):
    """_clublog_rt_breaker est un dict global lu ET modifié par
    realtime_push(), appelé fire-and-forget depuis un thread PAR QSO ajouté
    (add_qso_to_log) — donc potentiellement en concurrence, sans protection
    avant ce fix.

    Reproduction : le thread de TEST prend lui-même qsl._clublog_rt_lock
    (exactement comme le ferait un autre realtime_push() déjà en train de
    lire/modifier le disjoncteur) puis lance un realtime_push() dans un
    thread séparé. Si la lecture+écriture du disjoncteur passe bien par ce
    verrou, ce thread doit rester bloqué AVANT même d'atteindre le réseau
    tant qu'on ne relâche pas le verrou — sans le fix, il n'y a tout
    simplement pas de qsl._clublog_rt_lock (AttributeError immédiate) et
    rien n'empêcherait deux threads de lire/modifier le dict en même temps."""
    reached_network = threading.Event()

    def fake_post_url_form(url, fields, timeout=20, headers=None):
        reached_network.set()
        return 200, 'OK'
    monkeypatch.setattr('logx_utils.post_url_form', fake_post_url_form)

    cfg = _clublog_cfg('lock1')
    qsl._clublog_rt_lock.acquire()
    try:
        t = threading.Thread(target=qsl.realtime_push, args=(cfg, QSO))
        t.start()
        # Le thread concurrent doit être bloqué SUR LE VERROU : il ne doit
        # pas avoir atteint le réseau tant qu'on tient _clublog_rt_lock.
        assert not reached_network.wait(timeout=0.3)
    finally:
        qsl._clublog_rt_lock.release()
    t.join(timeout=5)
    assert reached_network.wait(timeout=5)   # débloqué dès le relâchement du verrou
