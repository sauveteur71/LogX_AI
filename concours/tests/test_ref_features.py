# -*- coding: utf-8 -*-
"""Tests du paquet REF : validateur de log, historique d'indicatifs (SCP),
chasse aux départements, débrief."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from radiocontest_validator import validate_log
from radiocontest_callhistory import exchange_wants, suggest, build_index
import radiocontest_callhistory as ch


CFG_THF = {'contest': 'REF_QRP', 'contest_start_date': '2026-07-18',
           'contest_end_date': '2026-07-19', 'contest_end_utc': '14:00',
           'locator': 'JN15WD'}


def _qso(**kw):
    base = {'contest': 'REF_QRP', 'call': 'F1ABC', 'band': '144', 'mode': 'SSB',
            'date': '20260718', 'time': '15:00', 'locator': 'JN25GO',
            'num_rcvd': '001', 'rst_rcvd': '59'}
    base.update(kw)
    return base


# ─── Validateur ──────────────────────────────────────────────────────────────

def test_validate_log_propre():
    r = validate_log([_qso()], 'REF_QRP', CFG_THF)
    assert r['ok'] and r['counts']['erreur'] == 0


def test_validate_doublon_meme_bande():
    """Règle REF : 1 QSO/station/bande — même en changeant de mode."""
    r = validate_log([_qso(), _qso(mode='CW', time='16:00')], 'REF_QRP', CFG_THF)
    assert any(f['code'] == 'doublon' for f in r['findings'])
    assert not r['ok']


def test_validate_locator_manquant_et_invalide():
    r = validate_log([_qso(call='F5AAA', locator=''),
                      _qso(call='F5BBB', locator='ZZ99')], 'REF_QRP', CFG_THF)
    codes = {f['code'] for f in r['findings']}
    assert 'locator_manquant' in codes and 'locator_invalide' in codes


def test_validate_hors_fenetre():
    r = validate_log([_qso(date='20260717', time='10:00')], 'REF_QRP', CFG_THF)
    assert any(f['code'] == 'hors_fenetre' for f in r['findings'])


def test_validate_distance_suspecte_144():
    """EA8 (Canaries, ~2600 km) sur 144 MHz : exceptionnel → attention."""
    r = validate_log([_qso(call='EA8AA', locator='IL18SD')], 'REF_QRP', CFG_THF)
    assert any(f['code'] == 'distance_suspecte' for f in r['findings'])
    assert r['ok']   # attention ≠ erreur


def test_validate_dept_concours_hf():
    """REF HF : département invalide pour une station française = erreur."""
    cfg = {'contest': 'REF_CDF_HF_CW', 'contest_start_date': '2026-01-24',
           'contest_end_date': '2026-01-25', 'contest_end_utc': '18:00',
           'locator': 'JN15WD'}
    log = [_qso(contest='REF_CDF_HF_CW', call='F5AAA', band='14',
                date='20260124', time='10:00', locator='', num_rcvd='43'),
           _qso(contest='REF_CDF_HF_CW', call='F5BBB', band='14',
                date='20260124', time='10:05', locator='', num_rcvd='99')]
    r = validate_log(log, 'REF_CDF_HF_CW', cfg)
    bad = [f for f in r['findings'] if f['code'] == 'dept_invalide']
    assert len(bad) == 1 and bad[0]['call'] == 'F5BBB'


# ─── Historique / SCP ────────────────────────────────────────────────────────

def test_exchange_wants_ref():
    from radiocontest_definitions import CONTEST_DEFINITIONS
    assert exchange_wants(CONTEST_DEFINITIONS['REF_QRP']) == \
        {'dept': False, 'locator': True}
    assert exchange_wants(CONTEST_DEFINITIONS['REF_CDF_HF_CW']) == \
        {'dept': True, 'locator': False}


def test_suggest_prefixe_puis_fragment():
    ch.build_index(force=True)
    # préfixe : tous les résultats commencent par F6K
    pre = suggest('F6K')
    assert pre and all(s['call'].startswith('F6K') for s in pre[:3])
    # fragment (check partial) : « 6KQ » matche F6KQJ sans en être le préfixe
    frag = suggest('6KQ')
    assert any('6KQ' in s['call'] and not s['call'].startswith('6KQ')
               for s in frag)


def test_index_marque_les_travailles():
    log = [{'call': 'F9ZZZ', 'locator': 'JN15AA', 'date': '20260704',
            'num_rcvd': '', 'contest': 'X'}]
    idx = ch.build_index(log, force=True)
    assert idx['F9ZZZ']['qso_count'] >= 1
    s = suggest('F9ZZ', log)
    assert s and s[0]['worked']
    ch.build_index(force=True)   # nettoie pour les autres tests


# ─── Chasse aux départements ─────────────────────────────────────────────────

def test_department_targets_spotte_en_tete():
    from radiocontest_departments import department_targets
    t = department_targets([], '', {'144 MHz': [{'dx': 'F1MOZ', 'freq': 144.3}]})
    assert t['missing_total'] == 96          # rien travaillé
    first = t['targets'][0]
    assert first['spotted'] and first['spotted'][0]['call'] == 'F1MOZ'


# ─── Débrief ─────────────────────────────────────────────────────────────────

def test_wall_state_expedition():
    import radiocontest_wall as wall
    log = [
        {'call': 'DL1AA', 'band': '14', 'mode': 'CW', 'operator': 'OP1',
         'date': '20260718', 'time': '14:00', 'locator': 'JO31', 'points': 1, 'contest': 'X'},
        {'call': 'DL1AA', 'band': '14', 'mode': 'SSB', 'operator': 'OP2',
         'date': '20260718', 'time': '14:01', 'locator': 'JO31', 'points': 1, 'contest': 'X'},
        {'call': 'EA5ZZ', 'band': '7', 'mode': 'FT8', 'operator': 'OP3',
         'date': '20260718', 'time': '14:02', 'locator': 'IM98', 'points': 1, 'contest': 'X'},
    ]
    st = wall.wall_state(log, {'contest': 'X', 'locator': 'JN15WD'})
    assert st['qso_total'] == 3
    assert st['unique_calls'] == 2          # DL1AA compté une fois
    assert st['per_band']['14'] == 2 and st['per_mode']['FT8'] == 1
    assert set(st['per_op']) == {'OP1', 'OP2', 'OP3'}
    assert st['recent'][0]['call'] == 'EA5ZZ'   # le plus récent en tête
    assert st['odx']['km'] > 0


def test_wall_state_ignore_contest_mismatch():
    """Régression : l'écran mural ne doit PAS masquer les QSO parce que le
    concours actif côté serveur diffère de celui des QSO (bug expédition :
    4 QSO en 'REF_QRP' invisibles quand la config était sur 'REF_RPH')."""
    import radiocontest_wall as wall
    log = [
        {'call': 'F6IRG', 'band': '144', 'mode': 'SSB', 'operator': 'OP1',
         'date': '20260717', 'time': '14:00', 'locator': 'JN15', 'contest': 'REF_QRP'},
        {'call': 'F2AI', 'band': '144', 'mode': 'SSB', 'operator': 'OP1',
         'date': '20260717', 'time': '14:01', 'locator': 'JN25', 'contest': 'REF_QRP'},
    ]
    # cfg annonce un AUTRE concours que celui des QSO
    st = wall.wall_state(log, {'contest': 'REF_RPH', 'locator': 'JN15WD'})
    assert st['qso_total'] == 2          # tous les QSO restent visibles
    assert st['unique_calls'] == 2
    # Un filtrage explicite reste possible si on le demande vraiment
    st2 = wall.wall_state(log, {'locator': 'JN15WD'}, contest_id='REF_RPH')
    assert st2['qso_total'] == 0


def test_flags_drapeau_pays():
    import radiocontest_flags as fl
    assert fl.flag_emoji('FR') == '🇫🇷'
    assert fl.flag_emoji('') == '' and fl.flag_emoji('X') == ''
    f = fl.flag_and_country('DL1ABC')
    assert f['flag'] == '🇩🇪' and 'Allemagne' in f['country']
    us = fl.flag_and_country('K1ABC')
    assert us['flag'] == '🇺🇸'
    # Indicatif inconnu : pas d'exception, drapeau vide
    unk = fl.flag_and_country('')
    assert unk['flag'] == ''


def test_wall_state_enrichissement_et_champs():
    import radiocontest_wall as wall
    log = [
        {'call': 'DL1AA', 'band': '144', 'mode': 'CW', 'operator': 'OP1',
         'date': '20260718', 'time': '14:00', 'locator': 'JO31',
         'freq': '144.055', 'rst_rcvd': '559'},
    ]
    st = wall.wall_state(log, {'locator': 'JN15WD'})
    # wall_fields présents (défaut) + enrichissement drapeau/pays/rst/freq
    assert isinstance(st['wall_fields'], dict) and 'flag' in st['wall_fields']
    r = st['recent'][0]
    assert r['flag'] == '🇩🇪' and 'Allemagne' in r['country']
    assert r['rst_rcvd'] == '559' and r['freq'] == '144.055'
    # wall_fields depuis la config (chaînes tolérées)
    st2 = wall.wall_state(log, {'wall_fields': {'country': False, 'name': '1'}})
    assert st2['wall_fields']['country'] is False
    assert st2['wall_fields']['name'] is True


def test_clublog_realtime_non_configure():
    import radiocontest_qsl as qsl
    r = qsl.realtime_push({}, {'call': 'DL1AA', 'band': '14', 'mode': 'CW'})
    assert r['ok'] is False and 'ClubLog' in r['error']


def test_build_debrief():
    from radiocontest_coach import build_debrief
    log = [_qso(), _qso(call='DK2ZZ', locator='JO62QD', time='16:00', num_rcvd='002')]
    d = build_debrief(CFG_THF, log)
    assert d['stats']['qso_total'] == 2
    assert d['stats']['per_band']['144']['qso'] == 2
    assert d['stats']['per_band']['144']['best_km'] > 500   # DK2ZZ loin
    assert 'DÉBRIEF' in d['debrief_prompt']
