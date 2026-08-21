# -*- coding: utf-8 -*-
"""Tests des moteurs propagation/compétition : météores, avion, tropo,
RBN (parseur), scoreboard, backup."""
import datetime
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ─── Météores ────────────────────────────────────────────────────────────────

def test_meteores_perseides_actif_a_laube():
    import logx_meteors as met
    q = met.ms_quality(datetime.datetime(2026, 8, 12, 6, 0))
    assert q['level'] == 'excellent'
    assert any(s['active'] and s['name'] == 'Perséides' for s in q['showers'])


def test_meteores_faible_hors_creneau_hiver():
    import logx_meteors as met
    q = met.ms_quality(datetime.datetime(2026, 3, 1, 15, 0))
    assert q['level'] in ('faible', 'moyen')


# ─── Ouvertures par région (paths) ───────────────────────────────────────────

def test_paths_sun_elevation():
    import logx_paths as p
    # Équateur, équinoxe : ~90° à midi UTC, ~-90° à minuit
    assert p.sun_elevation(0, 0, datetime.datetime(2026, 3, 21, 12, 0)) > 80
    assert p.sun_elevation(0, 0, datetime.datetime(2026, 3, 21, 0, 0)) < -80


# ─── Widget Time of Day (HOME vs DX) ─────────────────────────────────────────

def test_time_of_day_home_seul():
    import logx_paths as p
    when = datetime.datetime(2026, 3, 21, 12, 0)
    st = p.time_of_day_state('JN15XC', when=when)   # Le Puy-en-Velay, midi équinoxe
    assert st['utc'] == '12:00'
    assert st['home']['is_day'] is True
    assert 'dx' not in st


def test_time_of_day_home_vs_dx_oppose():
    """Le Puy-en-Velay (midi, jour) vs un locator antipodal (nuit) — vérifie
    que les deux côtés sont bien évalués indépendamment."""
    import logx_paths as p
    when = datetime.datetime(2026, 3, 21, 12, 0)
    st = p.time_of_day_state('JN15XC', dx_locator='RE78ex', when=when)
    assert st['home']['is_day'] is True
    assert st['dx']['is_day'] is False


def test_time_of_day_locator_invalide_renvoie_none():
    import logx_paths as p
    st = p.time_of_day_state('', when=datetime.datetime(2026, 3, 21, 12, 0))
    assert st['home'] is None


def test_time_of_day_sans_dx_absent_du_resultat():
    import logx_paths as p
    st = p.time_of_day_state('JN15XC', dx_locator='', when=datetime.datetime(2026, 3, 21, 12, 0))
    assert 'dx' not in st


# ─── Graphe de rythme sur la session complète (coach) ────────────────────────

def test_hourly_rate_series_vide_sans_qso():
    import logx_coach as coach
    assert coach.hourly_rate_series([]) == []


def test_hourly_rate_series_comble_les_heures_sans_qso():
    import logx_coach as coach
    entries = [
        {'date': '20260801', 'time': '1005'},
        {'date': '20260801', 'time': '1230'},
        {'date': '20260801', 'time': '1305'},
        {'date': '20260801', 'time': '1310'},
    ]
    series = coach.hourly_rate_series(entries)
    assert [s['hour'][-5:] for s in series] == ['10:00', '11:00', '12:00', '13:00']
    assert [s['count'] for s in series] == [1, 0, 1, 2]


def test_hourly_rate_series_ignore_les_entrees_sans_date_valide():
    import logx_coach as coach
    entries = [{'date': '20260801', 'time': '1000'}, {'date': '', 'time': ''}]
    series = coach.hourly_rate_series(entries)
    assert len(series) == 1 and series[0]['count'] == 1


def test_paths_hiva_oa_vers_europe_long_path():
    import logx_paths as p
    hiva = (-9.75, -139.0)
    solar = {'muf': {'muf_mhz': 22}, 'solar': {'sfi': 140, 'k_index': 2}}
    d = p.path_openings(hiva[0], hiva[1], 'EU',
                        datetime.datetime(2026, 7, 17, 18, 0), solar)
    assert d['distance_km'] > 13000          # très longue distance
    assert d['long_path'] is True
    assert d['bands'][0]['score'] >= d['bands'][-1]['score']   # trié
    assert 0 <= d['bands'][0]['score'] <= 100


def test_paths_context_block_et_regions():
    import logx_paths as p
    txt = p.context_block(48.8, 2.3, datetime.datetime(2026, 7, 17, 20, 0),
                          {'muf': {'muf_mhz': 18}, 'solar': {'sfi': 130}})
    assert 'Europe' in txt and 'UTC' in txt
    regs = p.all_regions(48.8, 2.3, solar={})
    assert len(regs) == len(p.REGIONS)
    assert all('best_band' in r for r in regs)


def test_paths_context_block_sert_l_indice_a_a_l_ia():
    """Constat de l'audit du 18/08/2026 : l'indice A était calculé et stocké
    (all_regions()['a_index']) mais context_block() -- le texte RÉELLEMENT
    envoyé à l'agent IA -- ne le mentionnait jamais, malgré deux commentaires
    de logx_paths.py qui affirmaient à tort qu'il était « servi à l'IA »."""
    import logx_paths as p
    txt = p.context_block(48.8, 2.3, datetime.datetime(2026, 7, 17, 20, 0),
                          {'muf': {'muf_mhz': 18}, 'solar': {'sfi': 130, 'a_index': 12}})
    assert 'Indice A' in txt and '12' in txt


def test_paths_context_block_sans_indice_a_ne_plante_pas():
    """Repli explicite : aucune valeur A remontée par la source solaire (NOAA
    injoignable, champ absent) -- pas de ligne fantôme ni de plantage."""
    import logx_paths as p
    txt = p.context_block(48.8, 2.3, datetime.datetime(2026, 7, 17, 20, 0),
                          {'muf': {'muf_mhz': 18}, 'solar': {'sfi': 130}})
    assert 'Indice A' not in txt


# ─── Tropo (physique de réfractivité) ────────────────────────────────────────

def test_tropo_refractivite_decroit_avec_altitude():
    import logx_tropo as tr
    n_bas = tr._refractivity(1000, 15, 70)
    n_haut = tr._refractivity(900, 9, 55)
    assert n_bas > n_haut                      # N décroît normalement
    g = (n_haut - n_bas) / ((990 - 110) / 1000)
    level, score = tr._classify(g)
    assert level in ('normal', 'super')


def test_tropo_classification_ducting():
    import logx_tropo as tr
    assert tr._classify(-200)[0] == 'ducting'
    assert tr._classify(-100)[0] == 'super'
    assert tr._classify(-40)[0] == 'normal'
    assert tr._classify(10)[0] == 'sous'


# ─── RBN (parseur, sans réseau) ──────────────────────────────────────────────

def test_rbn_parse_mes_spots():
    import logx_rbn as rbn
    txt = ('DX de DL0ABC-#:  14025.0  F6KQJ  CW    22 dB  28 wpm  CQ    1432Z\n'
           'DX de W3ZZZ-#:  14025.1  F6KQJ  CW  15 dB 25 wpm CQ 1433Z\n'
           'DX de X-#:  7005.0  OTHER  CW  30 dB  20 wpm  CQ  1434Z\n')
    sp = rbn.parse_rbn(txt, 'F6KQJ')
    assert len(sp) == 2                        # OTHER exclu
    assert sp[0]['snr'] == 22 and sp[0]['band'] == '14'
    assert all(s['spotter'] in ('DL0ABC', 'W3ZZZ') for s in sp)


# ─── Scoreboard ──────────────────────────────────────────────────────────────

def test_scoreboard_snapshot_et_xml():
    import logx_scoreboard as sb
    # date + contest_start_date de la même année : la portée QSO (contest+année,
    # voir logx_storage.active_scope_id) doit matcher pour que ces QSO comptent.
    log = [{'contest': 'X', 'call': 'A', 'band': '144', 'points': 45,
            'locator': 'JN25GO', 'date': '20260315'},
           {'contest': 'X', 'call': 'B', 'band': '432', 'points': 30,
            'locator': 'JN33AA', 'date': '20260315'}]
    snap = sb.build_score_snapshot(log, {'contest': 'X', 'contest_start_date': '2026-03-15'})
    assert snap['score'] == 75 and snap['qso'] == 2 and snap['mults'] == 2
    xml = sb.build_n1mm_xml(snap, {'callsign_contest': 'F6KQJ'})
    assert '<score>75</score>' in xml and '<dynamicresults>' in xml


def test_scoreboard_desactive_par_defaut():
    import logx_scoreboard as sb
    assert sb.push({}, [{'call': 'A'}])['ok'] is False


# ─── Backup ──────────────────────────────────────────────────────────────────

def test_backup_ecrit_et_retention():
    import logx_backup as bk
    d = tempfile.mkdtemp()
    try:
        log = [{'call': 'F1ABC', 'band': '144', 'mode': 'SSB', 'date': '20260718'}]
        r = bk.run_backup({'callsign': 'F6KQJ', 'backup_folder': d}, log)
        assert r['ok']
        assert any(f.endswith('.json') for f in r['files'])
        assert bk.status({'backup_folder': d})['backups_kept'] >= 0
    finally:
        import shutil
        shutil.rmtree(d, ignore_errors=True)
        for f in ('backup_state.json',):
            if os.path.exists(f):
                os.remove(f)


def test_backup_sans_dossier(tmp_path, monkeypatch):
    """Sans dossier configuré, la sauvegarde RÉUSSIT désormais.

    Ce test affirmait l'inverse (`['ok'] is False`) — il figeait le défaut qui
    a coûté 9 871 QSO le 19/08/2026 : sans `backup_folder`, rien n'était
    jamais écrit. Depuis, `backup_settings()` replie sur `sauvegardes/`
    (logx_backup.dossier_par_defaut) et l'écriture aboutit.

    Le `monkeypatch.chdir` n'est pas décoratif : le repli est résolu depuis le
    répertoire courant, et sans lui ce test écrivait dans `concours/` du
    dépôt. Constaté en le faisant."""
    import logx_backup as bk
    monkeypatch.chdir(tmp_path)
    res = bk.run_backup({}, [])
    assert res['ok'] is True, res
    assert os.path.isdir(os.path.join(str(tmp_path), bk.DOSSIER_DEFAUT))
