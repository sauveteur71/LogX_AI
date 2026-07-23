# -*- coding: utf-8 -*-
"""Tests carnet permanent : diplômes (awards), historique station, parseur ADIF
des confirmations QSL et fusion."""
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_awards as awards
import logx_qsl as qsl


def _log():
    return [
        {'call': 'DL1AA', 'band': '144', 'mode': 'SSB', 'contest': 'X',
         'date': '20260101', 'time': '10:00', 'locator': 'JO40AA'},
        {'call': 'DL1AA', 'band': '432', 'mode': 'SSB', 'contest': 'X',
         'date': '20260101', 'time': '10:05', 'locator': 'JO40AA'},
        {'call': 'G3XYZ', 'band': '144', 'mode': 'CW', 'contest': 'X',
         'date': '20260102', 'time': '11:00', 'locator': 'IO91'},
    ]


# ─── Historique station ──────────────────────────────────────────────────────

def test_history_regroupe_les_qso():
    awards.invalidate()
    h = awards.history('DL1AA', _log())
    assert h['count'] == 2
    assert set(h['bands']) == {'144', '432'}
    assert h['country'] in ('Fed. Rep. of Germany', 'Germany')


def test_history_inconnu():
    awards.invalidate()
    assert awards.history('ZZ9ZZ', _log())['count'] == 0


# ─── Nouveau à vie ───────────────────────────────────────────────────────────
# Isolation complète (même raison que _isolate_awards_et_callhistory plus bas) :
# new_one() fusionne shared_log avec les VRAIES archives/qso_archive du poste
# via collect_all_qsos() — sans ce monkeypatch, le test dépend de l'historique
# réel de la station (ex. un JA déjà travaillé un jour rendrait 'JA1AAA' non
# nouveau, cassant l'hypothèse du test "on n'a que EU dans le log").

def _isolate_awards(monkeypatch):
    monkeypatch.setattr(awards, '_read_archives', lambda: [])
    monkeypatch.setattr(awards, '_read_qso_archive', lambda: [])
    awards.invalidate()


def test_new_one_pays_jamais_contacte(monkeypatch):
    _isolate_awards(monkeypatch)
    # Un indicatif japonais alors qu'on n'a que EU dans le log
    res = awards.new_one('JA1AAA', '144', shared_log=_log())
    assert any(n['type'] == 'dxcc' and n['scope'] == 'atlantic' for n in res)


def test_new_one_rien_si_deja_fait(monkeypatch):
    _isolate_awards(monkeypatch)
    res = awards.new_one('DL1AA', '144', shared_log=_log())
    assert not any(n['scope'] == 'atlantic' for n in res)


# ─── Cibles proactives (spotted_new_ones) ────────────────────────────────────
# Isolation complète (comme department_targets) : on ne veut PAS dépendre de
# calldb.json/archives/qso_archive réels de ce poste — seule la logique compte.

def _isolate_awards_et_callhistory(monkeypatch):
    monkeypatch.setattr(awards, '_read_archives', lambda: [])
    monkeypatch.setattr(awards, '_read_qso_archive', lambda: [])
    awards.invalidate()
    import logx_callhistory as ch
    monkeypatch.setattr(ch, '_load_archives', lambda: None)
    monkeypatch.setattr(ch, '_load_qso_archive', lambda: None)
    monkeypatch.setattr(ch, '_load_calldb', lambda: None)
    ch._index = {}
    ch._built_at = 0.0
    return ch


def test_spotted_new_ones_pays_jamais_travaille(monkeypatch):
    _isolate_awards_et_callhistory(monkeypatch)
    spots = {'20m': [{'dx': 'JA1AAA', 'freq': '14025'}]}
    out = awards.spotted_new_ones(_log(), spots)
    assert any(t['type'] == 'dxcc' and t['call'] == 'JA1AAA' for t in out)


def test_spotted_new_ones_ignore_pays_deja_travaille(monkeypatch):
    _isolate_awards_et_callhistory(monkeypatch)
    # DL (Allemagne) est déjà dans _log() -> pas une nouveauté
    spots = {'144': [{'dx': 'DL2XYZ', 'freq': '145500'}]}
    out = awards.spotted_new_ones(_log(), spots)
    assert not out


def test_spotted_new_ones_departement_jamais_travaille(monkeypatch):
    ch = _isolate_awards_et_callhistory(monkeypatch)
    monkeypatch.setattr(ch, '_load_calldb', lambda: ch._feed('F5ABC', dept='33'))
    # La France est DÉJÀ travaillée (dept 75, différent de 33) : sans ça, F5ABC
    # remonterait comme nouveau PAYS (priorité dxcc > dept) et masquerait le cas
    # qu'on veut isoler ici — le département jamais travaillé.
    log = _log() + [{'call': 'F1XYZ', 'band': '144', 'mode': 'SSB', 'contest': 'X',
                     'date': '20260101', 'time': '09:00', 'locator': 'JN18',
                     'num_rcvd': '75'}]
    spots = {'80m': [{'dx': 'F5ABC', 'freq': '3600'}]}
    out = awards.spotted_new_ones(log, spots)
    assert any(t['type'] == 'dept' and t['call'] == 'F5ABC' and '33' in t['label']
               for t in out)


def test_spotted_new_ones_rien_si_aucun_spot(monkeypatch):
    _isolate_awards_et_callhistory(monkeypatch)
    assert awards.spotted_new_ones(_log(), {}) == []


# ─── Résumé diplômes ─────────────────────────────────────────────────────────

def test_award_summary():
    # collect_all_qsos fusionne AUSSI les vraies archives de la station :
    # on vérifie donc des minorants, pas des égalités exactes.
    awards.invalidate()
    s = awards.award_summary(_log())
    assert s['dxcc']['worked'] >= 2          # au moins DL + G
    assert '144' in s['per_band']
    assert s['per_band']['144']['qso'] >= 2  # les 2 QSO du log de test + éventuelles archives


# ─── Activité par jour (petite vue statistique, popup Diplômes) ─────────────

def test_activity_by_day_fenetre_ancree_sur_aujourdhui(monkeypatch):
    """La fenêtre doit couvrir EXACTEMENT les `days` derniers jours jusqu'à
    aujourd'hui (UTC) — pas jusqu'à la dernière date de QSO du log, sans quoi
    l'activité paraîtrait figée après une pause dans le trafic."""
    _isolate_awards(monkeypatch)
    today = datetime.datetime.utcnow().strftime('%Y%m%d')
    log = [{'call': 'DL1AA', 'band': '14', 'mode': 'SSB', 'date': today, 'time': '10:00'}]
    out = awards.activity_by_day(log, days=7)
    assert len(out) == 7
    assert out[-1]['date'] == today
    assert out[-1]['qso'] == 1


def test_activity_by_day_compte_plusieurs_qso_le_meme_jour():
    d = (datetime.datetime.utcnow() - datetime.timedelta(days=2)).strftime('%Y%m%d')
    log = [{'call': 'DL1AA', 'band': '14', 'mode': 'SSB', 'date': d, 'time': '10:00'},
           {'call': 'G3XYZ', 'band': '14', 'mode': 'SSB', 'date': d, 'time': '10:05'}]
    out = awards.activity_by_day(log, days=10)
    row = next(r for r in out if r['date'] == d)
    assert row['qso'] >= 2


def test_activity_by_day_jour_hors_fenetre_ignore(monkeypatch):
    """Un QSO trop ancien (hors des `days` derniers jours) ne doit pas fausser
    le total ni apparaître dans la fenêtre renvoyée."""
    _isolate_awards(monkeypatch)
    old = (datetime.datetime.utcnow() - datetime.timedelta(days=400)).strftime('%Y%m%d')
    log = [{'call': 'DL1AA', 'band': '14', 'mode': 'SSB', 'date': old, 'time': '10:00'}]
    out = awards.activity_by_day(log, days=5)
    assert old not in [r['date'] for r in out]
    assert sum(r['qso'] for r in out) == 0


def test_activity_by_day_vide(monkeypatch):
    _isolate_awards(monkeypatch)
    assert awards.activity_by_day([], days=3) == [
        {'date': d, 'qso': 0} for d in
        [(datetime.datetime.utcnow() - datetime.timedelta(days=i)).strftime('%Y%m%d')
         for i in (2, 1, 0)]
    ]


# ─── Parseur ADIF des confirmations (le bug <EOR> corrigé) ───────────────────

ADIF = ("En-tête libre\n<adif_ver:5>3.1.4<programid:4>test<EOH>\n"
        "<CALL:5>DL1AA<BAND:2>2m<MODE:3>SSB<QSL_RCVD:1>Y<QSLRDATE:8>20260110<EOR>\n"
        "<CALL:5>DL1AA<BAND:4>70cm<MODE:3>SSB<QSL_RCVD:1>Y<EOR>\n"
        "<CALL:5>F5XXX<BAND:3>20m<MODE:2>CW<QSL_RCVD:1>N<EOR>\n")


def test_parse_adif_separe_les_records():
    """Chaque <EOR> ferme bien un record (bug historique : les records
    fusionnaient car <EOR> n'a pas de longueur)."""
    recs = qsl._parse_adif_records(ADIF)
    assert len(recs) == 3
    assert recs[0]['CALL'] == 'DL1AA' and recs[0]['BAND'] == '2m'
    assert recs[1]['BAND'] == '70cm'


def test_parse_confirmations_bande_alignee_sur_le_log():
    """La bande ADIF '2m' devient '144' pour matcher la clé du log."""
    conf = qsl.parse_confirmations(ADIF, 'lotw')
    assert 'DL1AA|144|SSB' in conf
    assert 'DL1AA|432|SSB' in conf
    # QSL_RCVD:N n'est PAS confirmé
    assert 'F5XXX|14|CW' not in conf


def test_confirmations_remontent_dans_awards(tmp_path):
    """Fusion des confirmations → history marque confirmé, award_summary compte."""
    cf = awards.CONFIRM_FILE
    backup = None
    if os.path.exists(cf):
        with open(cf, encoding='utf-8') as f:
            backup = f.read()
        os.remove(cf)
    try:
        conf = qsl.parse_confirmations(ADIF, 'lotw')
        qsl.merge_confirmations(conf)
        awards.invalidate()
        h = awards.history('DL1AA', _log())
        assert h['confirmed'] == 2
        s = awards.award_summary(_log())
        assert s['confirmed_total'] == 2
        assert s['has_confirmations'] is True
    finally:
        if os.path.exists(cf):
            os.remove(cf)
        if backup is not None:
            with open(cf, 'w', encoding='utf-8') as f:
                f.write(backup)
        awards.invalidate()


# ─── Worked Matrix (grille bande × CW/Phone/Digital) ─────────────────────────

def test_mode_category():
    assert awards._mode_category('CW') == 'CW'
    assert awards._mode_category('SSB') == 'PHONE'
    assert awards._mode_category('FM') == 'PHONE'
    assert awards._mode_category('FT8') == 'DIGITAL'
    assert awards._mode_category('') == 'DIGITAL'


def test_worked_matrix_structure():
    awards.invalidate()
    m = awards.worked_matrix(_log())
    assert set(m['categories']) == {'CW', 'PHONE', 'DIGITAL'}
    assert '144' in m['bands'] and '432' in m['bands']
    # _log() garantit : 1 QSO SSB (Phone) sur 144 (DL1AA), 1 QSO CW sur 144
    # (G3XYZ), 1 QSO SSB sur 432 (DL1AA) — >= plutôt que == car
    # collect_all_qsos() fusionne aussi les vraies archives de la station,
    # voir la remarque de test_award_summary un peu plus haut.
    assert m['grid']['144']['PHONE']['qso'] >= 1
    assert m['grid']['144']['CW']['qso'] >= 1
    assert m['grid']['432']['PHONE']['qso'] >= 1
    assert m['grid']['144']['DIGITAL']['qso'] == 0


def test_worked_matrix_bandes_triees_par_frequence():
    awards.invalidate()
    log = [{'call': 'F1AAA', 'band': '432', 'mode': 'SSB', 'contest': 'X',
            'date': '20260101', 'time': '10:00'},
           {'call': 'F1BBB', 'band': '14', 'mode': 'CW', 'contest': 'X',
            'date': '20260101', 'time': '10:01'},
           {'call': 'F1CCC', 'band': '144', 'mode': 'SSB', 'contest': 'X',
            'date': '20260101', 'time': '10:02'}]
    m = awards.worked_matrix(log)
    idx = {b: i for i, b in enumerate(m['bands'])}
    assert idx['14'] < idx['144'] < idx['432']


def test_worked_matrix_scope_id_filtre_par_concours():
    """scope_id restreint la grille aux QSO d'UN concours précis (même format
    que qso_scope_id() : 'contest#annee') — les QSO d'un autre concours ('Y')
    disparaissent, ceux du concours demandé ('X') restent."""
    awards.invalidate()
    log = _log() + [
        {'call': 'PA1ZZZ', 'band': '21', 'mode': 'CW', 'contest': 'Y',
         'date': '20260101', 'time': '12:00'},
    ]
    m_scoped = awards.worked_matrix(log, scope_id='X#2026')
    assert '21' not in m_scoped['bands']
    assert m_scoped['grid']['144']['PHONE']['qso'] >= 1
    assert m_scoped['grid']['144']['CW']['qso'] >= 1


def test_worked_matrix_scope_id_vide_egale_vie_entiere():
    """scope_id='' (défaut) doit rester identique au comportement historique
    (carnet permanent, popup Diplômes) — pas de régression pour cet appelant."""
    awards.invalidate()
    log = _log()
    assert awards.worked_matrix(log, scope_id='') == awards.worked_matrix(log)


def test_worked_matrix_vide():
    awards.invalidate()
    m = awards.worked_matrix([])
    # Peut contenir des QSO de vraies archives de la station -> pas d'assertion
    # d'égalité stricte, juste la structure de base.
    assert 'bands' in m and 'categories' in m and 'totals' in m


def test_worked_matrix_confirmations(tmp_path):
    cf = awards.CONFIRM_FILE
    backup = None
    if os.path.exists(cf):
        with open(cf, encoding='utf-8') as f:
            backup = f.read()
        os.remove(cf)
    try:
        conf = qsl.parse_confirmations(ADIF, 'lotw')
        qsl.merge_confirmations(conf)
        awards.invalidate()
        m = awards.worked_matrix(_log())
        assert m['grid']['144']['PHONE']['confirmed'] >= 1
        assert m['grid']['432']['PHONE']['confirmed'] >= 1
    finally:
        if os.path.exists(cf):
            os.remove(cf)
        if backup is not None:
            with open(cf, 'w', encoding='utf-8') as f:
                f.write(backup)
        awards.invalidate()


# ─── Dégradation gracieuse (services non configurés) ─────────────────────────

def test_qsl_non_configure():
    assert qsl.upload_eqsl({}, 'adif')['ok'] is False
    assert qsl.upload_clublog({}, 'adif')['ok'] is False
    assert qsl.sync_lotw({})['ok'] is False
    st = qsl.qsl_status({})
    assert st['eqsl'] is False and st['lotw'] is False


def test_qsl_settings_depuis_cfg():
    s = qsl.qsl_settings({'eqsl_user': 'F4GLD', 'eqsl_password': 'x'})
    assert s['eqsl_enabled'] is True
    assert s['lotw_enabled'] is False
