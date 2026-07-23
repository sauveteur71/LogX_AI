# -*- coding: utf-8 -*-
"""Tests HTTP de bout en bout (vrai serveur sur port éphémère) pour les
endpoints de logx_http.py corrigés lors du passage à la portée concours+année
(qso_scope_id/active_scope_id/cfg_scope_id, voir logx_storage.py et
tests/test_contest_scope.py pour les tests unitaires des fonctions pures).

Ces routes vivent dans do_GET/do_POST (dispatch monolithique du Handler) et
n'avaient jusqu'ici AUCUNE couverture de test au niveau HTTP — exactement
pourquoi plusieurs endroits continuaient de passer le nom brut du concours
(sans année) au lieu de la portée à des fonctions déjà corrigées ailleurs,
sans qu'aucun test ne le remarque."""
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

import logx_http as httpmod


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


def _get(base, path):
    with urllib.request.urlopen(base + path, timeout=5) as r:
        return json.loads(r.read().decode('utf-8'))


def _post(base, path, payload):
    body = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(
        base + path, data=body, method='POST',
        headers={'Content-Type': 'application/json',
                 'X-RC-Token': httpmod.AUTH_TOKEN})
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, json.loads(r.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode('utf-8'))


def _qso(**kw):
    base = {'id': 1, 'call': 'F5ABC', 'band': '14', 'mode': 'SSB',
            'contest': 'REF_QRP', 'date': '20270718', 'time': '10:00',
            'points': 3}
    base.update(kw)
    return base


# ─── /log/archive : le bug de perte de données le plus critique ─────────────

def test_log_archive_clear_sans_concours_ne_vide_pas_tout(server, monkeypatch):
    """Régression critique : archiver+vider (clear=true) SANS concours
    sélectionné ne doit PAS effacer tout shared_log (tout l'historique
    d'autres concours/années) — seulement les QSO NON TAGUÉS."""
    tagged = _qso(id=1, contest='REF_CDF_HF_SSB', date='20270220')
    untagged = _qso(id=2, contest='', call='F6XYZ')
    monkeypatch.setattr(httpmod, 'shared_log', [tagged, untagged])
    monkeypatch.setattr(httpmod, 'save_log_to_disk', lambda: None)
    monkeypatch.setattr(httpmod, 'current_config', {'usage_mode': 'contest', 'contest': ''})
    status, res = _post(server, '/log/archive', {'clear': True})
    assert status == 200 and res.get('ok') and res.get('cleared')
    remaining_ids = {q['id'] for q in httpmod.shared_log}
    assert remaining_ids == {1}, ('le QSO taggé REF_CDF_HF_SSB doit survivre — '
                                  'seul le QSO non tagué devait être archivé+effacé')


def test_log_archive_clear_avec_concours_ne_touche_pas_les_autres(server, monkeypatch):
    this_year = _qso(id=1, contest='REF_QRP', date='20270718')
    other_contest = _qso(id=2, contest='REF_RPH', date='20270110', call='F6XYZ')
    monkeypatch.setattr(httpmod, 'shared_log', [this_year, other_contest])
    monkeypatch.setattr(httpmod, 'save_log_to_disk', lambda: None)
    monkeypatch.setattr(httpmod, 'current_config',
                        {'usage_mode': 'contest', 'contest': 'REF_QRP',
                         'contest_start_date': '2027-07-18'})
    status, res = _post(server, '/log/archive', {'clear': True})
    assert status == 200 and res.get('ok')
    remaining_ids = {q['id'] for q in httpmod.shared_log}
    assert remaining_ids == {2}


# ─── /log/check : badge doublon conscient de l'année ────────────────────────

def test_log_check_meme_concours_annee_precedente_pas_doublon(server, monkeypatch):
    old = _qso(date='20260718')   # même concours, l'an dernier
    monkeypatch.setattr(httpmod, 'shared_log', [old])
    monkeypatch.setattr(httpmod, 'current_config',
                        {'usage_mode': 'contest', 'contest': 'REF_QRP',
                         'contest_start_date': '2027-07-18'})
    res = _get(server, '/log/check?call=F5ABC&band=14&mode=SSB')
    assert res.get('status') != 'doublon'


def test_log_check_meme_concours_meme_annee_est_doublon(server, monkeypatch):
    existing = _qso(date='20270718')
    monkeypatch.setattr(httpmod, 'shared_log', [existing])
    monkeypatch.setattr(httpmod, 'current_config',
                        {'usage_mode': 'contest', 'contest': 'REF_QRP',
                         'contest_start_date': '2027-07-18'})
    res = _get(server, '/log/check?call=F5ABC&band=14&mode=SSB')
    assert res.get('status') == 'doublon'


# ─── /qtc/add : plafond de 10 QTC/station conscient de la portée ────────────

def test_qtc_add_plafond_respecte_la_portee(server, monkeypatch):
    import logx_storage as storage
    monkeypatch.setattr(httpmod, 'current_config',
                        {'usage_mode': 'contest', 'contest': 'EU_HF_CHAMP',
                         'contest_start_date': '2027-06-05'})
    monkeypatch.setattr(storage, 'save_qtc_to_disk', lambda: None)
    with storage.qtc_lock:
        storage.qtc_log[:] = [{'call': 'F5ABC', 'count': 10, 'contest': 'EU_HF_CHAMP',
                               'date': '20270605', 'time': '10:00'}]
    status, res = _post(server, '/qtc/add', {'call': 'F5ABC', 'count': 1})
    assert status == 400 and not res['ok'] and 'F5ABC' in res['error']


def test_qtc_add_annee_precedente_ne_compte_pas_dans_le_plafond(server, monkeypatch):
    import logx_storage as storage
    monkeypatch.setattr(httpmod, 'current_config',
                        {'usage_mode': 'contest', 'contest': 'EU_HF_CHAMP',
                         'contest_start_date': '2027-06-05'})
    monkeypatch.setattr(storage, 'save_qtc_to_disk', lambda: None)
    with storage.qtc_lock:
        storage.qtc_log[:] = [{'call': 'F5ABC', 'count': 10, 'contest': 'EU_HF_CHAMP',
                               'date': '20260606', 'time': '10:00'}]   # l'an dernier
    status, res = _post(server, '/qtc/add', {'call': 'F5ABC', 'count': 1})
    assert status == 200 and res['ok']


# ─── /qtc/add : saisie détaillée (heure/indicatif/n° — règlement WAE) ───────

def _qtc_entries(n):
    return [{'time': f'00{i:02d}'[-4:], 'call': f'DL{i}XX', 'nr': str(100 + i)}
            for i in range(n)]


def test_qtc_add_serie_detaillee_stocke_les_entrees(server, monkeypatch):
    import logx_storage as storage
    monkeypatch.setattr(httpmod, 'current_config',
                        {'usage_mode': 'contest', 'contest': 'WAEDC_SSB',
                         'contest_start_date': '2027-09-11'})
    monkeypatch.setattr(storage, 'save_qtc_to_disk', lambda: None)
    with storage.qtc_lock:
        storage.qtc_log[:] = []
    entries = _qtc_entries(3)
    status, res = _post(server, '/qtc/add', {
        'call': 'DL0XM', 'direction': 'sent', 'band': '14', 'mode': 'CW',
        'series_number': 1, 'entries': entries})
    # with_call (pas 'total', qui dépend de la date réelle du système au
    # moment du test vs. l'année codée en dur de contest_start_date ci-dessus)
    assert status == 200 and res['ok'] and res['with_call'] == 3
    stored = storage.qtc_log[-1]
    assert stored['call'] == 'DL0XM' and stored['direction'] == 'sent'
    assert stored['count'] == 3      # dérivé de len(entries), jamais du 'count' brut
    assert stored['entries'] == entries
    assert isinstance(stored['id'], int)


def test_qtc_add_serie_ligne_incomplete_refusee(server, monkeypatch):
    import logx_storage as storage
    monkeypatch.setattr(httpmod, 'current_config',
                        {'usage_mode': 'contest', 'contest': 'WAEDC_SSB',
                         'contest_start_date': '2027-09-11'})
    monkeypatch.setattr(storage, 'save_qtc_to_disk', lambda: None)
    with storage.qtc_lock:
        storage.qtc_log[:] = []
    status, res = _post(server, '/qtc/add', {
        'call': 'DL0XM', 'entries': [{'time': '0030', 'call': 'YU1ZZ', 'nr': ''}]})
    assert status == 400 and not res['ok']
    assert not storage.qtc_log      # rien n'a été enregistré


def test_qtc_add_serie_plus_de_10_qtc_refusee(server, monkeypatch):
    import logx_storage as storage
    monkeypatch.setattr(httpmod, 'current_config',
                        {'usage_mode': 'contest', 'contest': 'WAEDC_SSB',
                         'contest_start_date': '2027-09-11'})
    monkeypatch.setattr(storage, 'save_qtc_to_disk', lambda: None)
    with storage.qtc_lock:
        storage.qtc_log[:] = []
    status, res = _post(server, '/qtc/add', {'call': 'DL0XM', 'entries': _qtc_entries(11)})
    assert status == 400 and not res['ok']


def test_qtc_add_serie_detaillee_respecte_le_plafond_par_station(server, monkeypatch):
    """Le plafond de 10 QTC/station (voir test_qtc_add_plafond_respecte_la_portee)
    doit aussi s'appliquer quand le décompte vient d'une série détaillée."""
    import logx_storage as storage
    monkeypatch.setattr(httpmod, 'current_config',
                        {'usage_mode': 'contest', 'contest': 'WAEDC_SSB',
                         'contest_start_date': '2027-09-11'})
    monkeypatch.setattr(storage, 'save_qtc_to_disk', lambda: None)
    with storage.qtc_lock:
        storage.qtc_log[:] = [{'call': 'DL0XM', 'count': 8, 'contest': 'WAEDC_SSB',
                               'date': '20270911', 'time': '10:00'}]
    status, res = _post(server, '/qtc/add', {'call': 'DL0XM', 'entries': _qtc_entries(3)})
    assert status == 400 and not res['ok'] and 'DL0XM' in res['error']


# ─── /qtc/delete/<id> : corriger une série mal saisie ────────────────────────

def test_qtc_delete_supprime_la_serie(server, monkeypatch):
    import logx_storage as storage
    monkeypatch.setattr(httpmod, 'current_config',
                        {'usage_mode': 'contest', 'contest': 'WAEDC_SSB',
                         'contest_start_date': '2027-09-11'})
    monkeypatch.setattr(storage, 'save_qtc_to_disk', lambda: None)
    with storage.qtc_lock:
        storage.qtc_log[:] = []
    status, res = _post(server, '/qtc/add', {'call': 'DL0XM', 'entries': _qtc_entries(2)})
    assert status == 200
    qtc_id = res['id']
    req = urllib.request.Request(server + f'/qtc/delete/{qtc_id}', method='DELETE',
                                  headers={'X-RC-Token': httpmod.AUTH_TOKEN})
    with urllib.request.urlopen(req, timeout=5) as r:
        d = json.loads(r.read().decode('utf-8'))
    assert d['ok'] and d['deleted'] == 1
    assert not any(q.get('id') == qtc_id for q in storage.qtc_log)


# ─── /log/reset : archivage groupé par portée (contest+année), pas par nom brut ─

def test_log_reset_groupe_par_portee_pas_par_nom_brut(server, monkeypatch, tmp_path):
    import logx_archive as arch
    monkeypatch.setattr(arch, 'ARCHIVE_DIR', str(tmp_path))
    y2026 = _qso(id=1, contest='REF_QRP', date='20260606')
    y2027 = _qso(id=2, contest='REF_QRP', date='20270605', call='F6XYZ')
    monkeypatch.setattr(httpmod, 'shared_log', [y2026, y2027])
    monkeypatch.setattr(httpmod, 'save_log_to_disk', lambda: None)
    import logx_storage as storage
    monkeypatch.setattr(storage, 'archive_current_log', lambda: [])
    monkeypatch.setattr(httpmod, 'current_config', {'usage_mode': 'contest'})
    status, res = _post(server, '/log/reset', {'confirm': 'RESET'})
    assert status == 200 and res.get('ok')
    # Deux éditions annuelles distinctes -> DEUX dossiers d'archive séparés,
    # pas un seul dossier fusionné 'REF_QRP_<timestamp>'.
    assert len(res['folders']) == 2
    assert any('2026' in f for f in res['folders'])
    assert any('2027' in f for f in res['folders'])
