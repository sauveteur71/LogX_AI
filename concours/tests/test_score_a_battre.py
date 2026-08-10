# -*- coding: utf-8 -*-
"""Tests du "score à battre" (meilleur QSO count / meilleur score déjà
réalisés pour un concours, toutes éditions archivées confondues) :
- logx_archive.best_for_contest() : logique pure (voir test_archive.py pour
  le reste de l'archivage)
- /log/archives/best : câblage HTTP (vrai serveur sur port éphémère, même
  motif que test_callhistory_http.py)
- logx_archive.import_external_log()/_parse_cabrillo() + /log/archives/import :
  import d'un VIEUX log (ADIF/Cabrillo) jamais loggué dans LogX AI comme
  archive permanente, pour qu'il alimente le score à battre (demande F4GLD
  10/08/2026 : « j'ai des logs de concours que je n'ai pas encore importé
  en stock »)."""
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

import logx_archive as arch
import logx_http as httpmod

CFG = {'callsign': 'F6KQJ', 'locator': 'JN15XC'}

CABRILLO_SAMPLE = """START-OF-LOG: 3.0
CONTEST: REF-160M
CALLSIGN: F6KQJ
CATEGORY-OPERATOR: SINGLE-OP
CLAIMED-SCORE: 348
QSO: 14000 CW 2024-03-02 1200 F6KQJ       59 001            DL1ABC        59 012
QSO:  7000 CW 2024-03-02 1215 F6KQJ       59 002            F5XYZ         59 045
QSO: 14000 CW 2024-03-02 1230 F6KQJ       59 003            G4ZZZ         59 077
END-OF-LOG:
"""

ADIF_SAMPLE = (
    "En-tête\n<adif_ver:5>3.1.4<programid:5>LogX<EOH>\n"
    "<CALL:5>DL1AA<BAND:3>20m<MODE:2>CW<QSO_DATE:8>20230115<TIME_ON:4>1230<EOR>\n"
    "<CALL:5>F5XYZ<BAND:3>20m<MODE:2>CW<QSO_DATE:8>20230115<TIME_ON:4>1245<EOR>\n"
)


def _qsos(n, points_each=1, date='20260801'):
    return [{'call': f'F{i}ABC', 'band': '14', 'mode': 'CW', 'date': date,
             'time': '12:00', 'points': points_each, 'num_rcvd': '01'}
            for i in range(n)]


def _write_archive(tmp_path, folder_name, qsos):
    """Crée directement un dossier d'archive (log.json seul) au nom donné --
    contourne archive_log()/son horodatage à la seconde près quand un test a
    besoin de deux éditions à des DATES distinctes garanties."""
    folder = tmp_path / 'archives' / folder_name
    folder.mkdir(parents=True)
    (folder / 'log.json').write_text(json.dumps(qsos), encoding='utf-8')


# ─── logique pure ───────────────────────────────────────────────────────────

def test_aucune_archive_renvoie_none(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert arch.best_for_contest('REF_160M') is None


def test_contest_id_vide_renvoie_none(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    arch.archive_log(_qsos(3), 'REF_160M', CFG)
    assert arch.best_for_contest('') is None
    assert arch.best_for_contest(None) is None


def test_une_seule_edition(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    arch.archive_log(_qsos(5, points_each=2), 'REF_160M', CFG)
    r = arch.best_for_contest('REF_160M')
    assert r['ok'] and r['editions'] == 1
    assert r['best_qso'] == 5 and r['best_points'] == 10


def test_meilleur_qso_et_meilleur_score_peuvent_venir_d_editions_differentes(tmp_path, monkeypatch):
    """Le "meilleur nombre de QSO" et le "meilleur score" ne sont pas
    forcément la même édition -- ex. une édition à beaucoup de QSO à 1 point
    chacun vs une édition à moins de QSO mais des multiplicateurs plus
    généreux. Dossiers créés directement (pas via archive_log() deux fois) :
    deux appels dans la même seconde produiraient un nom en collision
    (suffixe -2) que list_archives() ne sait pas dater -- piège déjà connu
    du regex `(.+)_(\\d{8})-(\\d{6})$`, pas dans le périmètre de ce test."""
    monkeypatch.chdir(tmp_path)
    _write_archive(tmp_path, 'REF_160M_20240301-120000', _qsos(20, points_each=1))
    _write_archive(tmp_path, 'REF_160M_20250301-120000', _qsos(8, points_each=5))
    r = arch.best_for_contest('REF_160M')
    assert r['editions'] == 2
    assert r['best_qso'] == 20 and r['best_qso_year'] == '2024'
    assert r['best_points'] == 40 and r['best_points_year'] == '2025'


def test_filtre_par_concours_ignore_les_autres(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    arch.archive_log(_qsos(10), 'REF_160M', CFG)
    arch.archive_log(_qsos(50), 'CQ_WW_SSB', CFG)
    r = arch.best_for_contest('REF_160M')
    assert r['editions'] == 1 and r['best_qso'] == 10


def test_annee_associee_au_record(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    arch.archive_log(_qsos(3), 'REF_160M', CFG)
    r = arch.best_for_contest('REF_160M')
    assert r['best_qso_year'] and len(r['best_qso_year']) == 4
    assert r['best_points_year'] == r['best_qso_year']


# ─── câblage HTTP ────────────────────────────────────────────────────────────

@pytest.fixture
def server():
    srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), httpmod.Handler)
    port = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        yield f'http://127.0.0.1:{port}'
    finally:
        srv.shutdown()
        srv.server_close()
        t.join(timeout=5)
        srv.server_close()


def _get(base, path):
    with urllib.request.urlopen(base + path, timeout=5) as r:
        return json.loads(r.read().decode('utf-8'))


def test_endpoint_sans_archive(server, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    res = _get(server, '/log/archives/best?contest=REF_160M')
    assert res['ok'] is False


def test_endpoint_avec_archives(server, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    arch.archive_log(_qsos(12, points_each=2), 'REF_160M', CFG)
    res = _get(server, '/log/archives/best?contest=REF_160M')
    assert res['ok'] and res['best_qso'] == 12 and res['best_points'] == 24


def test_endpoint_sans_parametre_contest(server, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    res = _get(server, '/log/archives/best')
    assert res['ok'] is False


# ─── _parse_cabrillo() : parseur minimal, lecture seule ─────────────────────

def test_parse_cabrillo_extrait_score_et_qso():
    qsos, claimed = arch._parse_cabrillo(CABRILLO_SAMPLE)
    assert claimed == 348
    assert len(qsos) == 3
    assert qsos[0]['band'] == '14' and qsos[0]['mode'] == 'CW'
    assert qsos[0]['date'] == '20240302' and qsos[0]['time'] == '1200'
    assert qsos[1]['band'] == '7'


def test_parse_cabrillo_sans_claimed_score():
    text = "START-OF-LOG: 3.0\nQSO: 14000 CW 2024-03-02 1200 F6KQJ 59 001 DL1ABC 59 012\nEND-OF-LOG:\n"
    qsos, claimed = arch._parse_cabrillo(text)
    assert claimed is None and len(qsos) == 1


def test_parse_cabrillo_texte_vide():
    assert arch._parse_cabrillo('') == ([], None)


# ─── import_external_log() : logique pure ───────────────────────────────────

def test_import_cabrillo_utilise_claimed_score_par_defaut(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    r = arch.import_external_log(CABRILLO_SAMPLE, 'cabrillo', 'REF_160M', CFG)
    assert r['ok'] and r['qso_count'] == 3
    best = arch.best_for_contest('REF_160M')
    assert best['best_qso'] == 3 and best['best_points'] == 348
    assert best['best_qso_year'] == '2024'   # date du LOG importé, pas la date du jour


def test_import_cabrillo_manual_score_remplace_claimed_score(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    r = arch.import_external_log(CABRILLO_SAMPLE, 'cabrillo', 'REF_160M', CFG, manual_score=999)
    assert r['ok']
    assert arch.best_for_contest('REF_160M')['best_points'] == 999


def test_import_adif_sans_score_manuel_reste_a_zero(tmp_path, monkeypatch):
    """L'ADIF ne transporte pas de points par QSO côté LogX AI (voir
    logx_import.parse_adif_to_qsos) -- sans score fourni, le score de
    l'édition importée reste à 0 (seul le nombre de QSO est fiable)."""
    monkeypatch.chdir(tmp_path)
    r = arch.import_external_log(ADIF_SAMPLE, 'adif', 'REF_160M', CFG)
    assert r['ok'] and r['qso_count'] == 2
    best = arch.best_for_contest('REF_160M')
    assert best['best_qso'] == 2 and best['best_points'] == 0
    assert best['best_qso_year'] == '2023'


def test_import_adif_avec_score_manuel(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    r = arch.import_external_log(ADIF_SAMPLE, 'adif', 'REF_160M', CFG, manual_score=150)
    assert r['ok']
    assert arch.best_for_contest('REF_160M')['best_points'] == 150


def test_import_sans_concours_refuse(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    r = arch.import_external_log(CABRILLO_SAMPLE, 'cabrillo', '', CFG)
    assert not r['ok'] and 'oncours' in r['error']


def test_import_format_inconnu_refuse(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    r = arch.import_external_log('peu importe', 'n1mm', 'REF_160M', CFG)
    assert not r['ok'] and 'ormat' in r['error']


def test_import_fichier_sans_qso_refuse(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    r = arch.import_external_log('START-OF-LOG: 3.0\nEND-OF-LOG:\n', 'cabrillo', 'REF_160M', CFG)
    assert not r['ok'] and 'Aucun QSO' in r['error']


def test_import_alimente_best_for_contest_meme_annee_que_le_fichier_pas_aujourdhui(tmp_path, monkeypatch):
    """Le coeur du correctif `when=` de archive_log() : un log de 2024 importé
    aujourd'hui doit apparaître daté 2024, pas de la date du jour de
    l'import -- sans quoi le "score à battre" mentirait sur l'année."""
    monkeypatch.chdir(tmp_path)
    arch.import_external_log(CABRILLO_SAMPLE, 'cabrillo', 'REF_160M', CFG)
    archives = arch.list_archives()
    assert len(archives) == 1
    assert archives[0]['date'].startswith('2024-03-02')


# ─── /log/archives/import : câblage HTTP ─────────────────────────────────────

def _post(base, path, payload, token=True):
    body = json.dumps(payload).encode('utf-8')
    headers = {'Content-Type': 'application/json'}
    if token:
        headers['X-RC-Token'] = httpmod.AUTH_TOKEN
    req = urllib.request.Request(base + path, data=body, method='POST', headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, json.loads(r.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode('utf-8'))


def test_endpoint_import_cabrillo_succes(server, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    status, res = _post(server, '/log/archives/import',
                         {'format': 'cabrillo', 'text': CABRILLO_SAMPLE, 'contest': 'REF_160M'})
    assert status == 200 and res['ok'] and res['qso_count'] == 3
    best = _get(server, '/log/archives/best?contest=REF_160M')
    assert best['ok'] and best['best_points'] == 348


def test_endpoint_import_avec_score_manuel(server, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    status, res = _post(server, '/log/archives/import',
                         {'format': 'adif', 'text': ADIF_SAMPLE, 'contest': 'REF_160M', 'score': 77})
    assert status == 200 and res['ok']
    best = _get(server, '/log/archives/best?contest=REF_160M')
    assert best['best_points'] == 77


def test_endpoint_import_sans_token_refuse(server, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    status, res = _post(server, '/log/archives/import',
                         {'format': 'cabrillo', 'text': CABRILLO_SAMPLE, 'contest': 'REF_160M'}, token=False)
    assert status == 403
    assert arch.list_archives() == []   # rien écrit


def test_endpoint_import_sans_concours_400(server, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    status, res = _post(server, '/log/archives/import',
                         {'format': 'cabrillo', 'text': CABRILLO_SAMPLE, 'contest': ''})
    assert status == 400 and res['ok'] is False
