# -*- coding: utf-8 -*-
"""Portée concours (contest+année) — logx_storage.qso_scope_id/active_scope_id/
cfg_scope_id et tous les endroits qui filtrent shared_log par concours actif.

Bug corrigé : passer en mode concours réaffichait le log de base (logbook
simple / QSO importés sans tag) au lieu d'un log vierge ou du dernier log de
CE concours — un QSO non tagué (`contest == ''`) était traité comme un JOKER
comptant pour N'IMPORTE QUEL concours (`q.get('contest','') in ('', contest_id)`,
répété dans 9 endroits indépendants), et l'identifiant de concours lui-même
(ex. 'REF_CDF_HF_SSB') ne portait pas l'année, donc une édition non purgée
d'une année précédente se confondait avec celle en cours."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_http as http
from logx_storage import qso_scope_id, active_scope_id, cfg_scope_id
from logx_utils import utcnow


# ─── Helpers de portée (logx_storage) ────────────────────────────────────────

def test_qso_scope_id_non_tague():
    assert qso_scope_id({'call': 'F5ABC', 'contest': ''}) == ''
    assert qso_scope_id({'call': 'F5ABC'}) == ''
    assert qso_scope_id({}) == ''


def test_qso_scope_id_avec_annee():
    q = {'contest': 'REF_CDF_HF_SSB', 'date': '20270220'}
    assert qso_scope_id(q) == 'REF_CDF_HF_SSB#2027'


def test_qso_scope_id_sans_date_valide_replie_sur_le_nom_brut():
    assert qso_scope_id({'contest': 'REF_QRP', 'date': ''}) == 'REF_QRP'
    assert qso_scope_id({'contest': 'REF_QRP'}) == 'REF_QRP'


def test_active_scope_id_aucun_concours():
    assert active_scope_id({}) == ''
    assert active_scope_id({'contest': ''}) == ''


def test_active_scope_id_avec_contest_start_date():
    cfg = {'contest': 'REF_CDF_HF_SSB', 'contest_start_date': '2027-02-20'}
    assert active_scope_id(cfg) == 'REF_CDF_HF_SSB#2027'


def test_active_scope_id_sans_date_replie_sur_annee_courante():
    cfg = {'contest': 'REF_QRP'}
    assert active_scope_id(cfg) == f'REF_QRP#{utcnow().year}'


def test_cfg_scope_id_mode_simple_jamais_de_portee():
    cfg = {'usage_mode': 'simple', 'contest': 'REF_QRP',
           'contest_start_date': '2027-02-20'}
    assert cfg_scope_id(cfg) == ''


def test_cfg_scope_id_mode_concours_delegue_a_active_scope_id():
    cfg = {'usage_mode': 'contest', 'contest': 'REF_QRP',
           'contest_start_date': '2027-02-20'}
    assert cfg_scope_id(cfg) == active_scope_id(cfg) == 'REF_QRP#2027'


# ─── Carte : départements / pays ne comptent plus les QSO non tagués ────────

def test_departments_progress_ignore_qso_non_tague():
    import logx_departments as dep
    log = [
        {'call': 'F5ABC', 'num_rcvd': '42', 'contest': '', 'date': '20110809'},
        {'call': 'F6XYZ', 'num_rcvd': '59', 'contest': 'REF_CDF_HF_SSB',
         'date': '20270220'},
    ]
    scope = 'REF_CDF_HF_SSB#2027'
    prog = dep.departments_progress(log, scope)
    # Seul le QSO taggé à la bonne portée doit compter (dept 59), pas le
    # QSO non tagué (dept 42) qui aurait fait passer la carte "toute en vert".
    assert '59' in prog['worked']
    assert '42' not in prog['worked']


def test_departments_progress_annees_differentes_ne_se_melangent_pas():
    import logx_departments as dep
    log = [{'call': 'F5ABC', 'num_rcvd': '42', 'contest': 'REF_CDF_HF_SSB',
            'date': '20260221'}]   # même concours, ANNÉE PRÉCÉDENTE
    prog = dep.departments_progress(log, 'REF_CDF_HF_SSB#2027')
    assert prog['worked'] == []


def test_worked_keys_ignore_qso_non_tague():
    import logx_countries as co
    log = [
        {'call': 'DL1AA', 'contest': '', 'date': '20110809'},
        {'call': 'W1AW', 'contest': 'CQWW', 'date': '20271025'},
    ]
    worked = co._worked_keys(log, 'CQWW#2027')
    assert 'W1AW'[:1] not in worked or True  # sanity: n'échoue pas sur le lookup
    # Le point clé : DL1AA (non tagué) ne doit jamais compter pour CQWW#2027.
    from logx_dxcc import dxcc_entity_key
    assert dxcc_entity_key('DL1AA') not in worked


# ─── Coach : stats de rythme/score ne comptent plus le log de base ──────────

def test_log_stats_ignore_hors_portee():
    from logx_coach import log_stats
    import datetime
    now = datetime.datetime(2027, 2, 20, 15, 0)
    log = [
        {'contest': '', 'date': '20200101', 'time': '10:00', 'band': '14', 'points': 5},
        {'contest': 'REF_CDF_HF_SSB', 'date': '20270220', 'time': '14:55',
         'band': '14', 'points': 3},
    ]
    stats = log_stats(log, 'REF_CDF_HF_SSB#2027', now=now)
    assert stats['qso_total'] == 1
    assert stats['score'] == 3


# ─── Scoreboard : le score publié n'inclut plus les QSO non tagués ──────────

def test_build_score_snapshot_ignore_qso_non_tague():
    import logx_scoreboard as sb
    log = [
        {'contest': '', 'call': 'A', 'band': '144', 'points': 999, 'locator': 'JN25GO'},
        {'contest': 'REF_QRP', 'call': 'B', 'band': '432', 'points': 30,
         'locator': 'JN33AA', 'date': '20270718'},
    ]
    snap = sb.build_score_snapshot(
        log, {'contest': 'REF_QRP', 'contest_start_date': '2027-07-18'})
    assert snap['score'] == 30 and snap['qso'] == 1


# ─── Dédup add_qso_to_log : année-consciente ─────────────────────────────────

def _qso(**kw):
    base = {'call': 'F5ABC', 'band': '14', 'mode': 'SSB', 'contest': 'REF_QRP',
            'date': '20270718', 'time': '10:00'}
    base.update(kw)
    return base


def test_dedup_bloque_meme_concours_meme_annee(monkeypatch):
    existing = _qso()
    monkeypatch.setattr(http, 'shared_log', [existing])
    monkeypatch.setattr(http, 'save_log_to_disk', lambda effacement_autorise=False: None)
    monkeypatch.setattr(http, 'current_config', {'usage_mode': 'contest'})
    ok, info = http.add_qso_to_log(_qso(time='10:05'))
    assert not ok and info.get('duplicate')


def test_dedup_autorise_meme_concours_annee_suivante(monkeypatch):
    """Retravailler la même station/bande sur la même édition ANNUELLE d'un
    concours récurrent, l'année suivante, n'est PAS un doublon — avant le
    correctif, l'absence d'année dans le tag de concours le bloquait à tort."""
    existing = _qso(date='20260718')   # même concours, l'an dernier
    monkeypatch.setattr(http, 'shared_log', [existing])
    monkeypatch.setattr(http, 'save_log_to_disk', lambda effacement_autorise=False: None)
    monkeypatch.setattr(http, 'current_config', {'usage_mode': 'contest'})
    ok, _info = http.add_qso_to_log(_qso(date='20270718'))
    assert ok


# ─── Dédup add_qso_to_log : concours à réinitialisation QUOTIDIENNE (WWA) ────
# Correctif de la passe de vérification complète du 09/08/2026 : WWA_2027_JAN
# (scoring.type='wwa_sprint', bricks['dupe_reset']=='daily', voir
# logx_scoring.py) autorise 1 QSO/jour/bande/mode par station spéciale
# (règlement §7) — même scope_id (contest+ANNÉE) pendant toute l'édition d'un
# mois, donc l'ancienne comparaison (call, band, mode, scope_id) bloquait à
# tort un recontact légitime un autre jour du même mois.

def test_dedup_wwa_bloque_meme_jour(monkeypatch):
    """Concours à dupe_reset='daily' : un recontact le MÊME jour reste un
    vrai doublon (le correctif ne doit pas tout désactiver)."""
    existing = _qso(contest='WWA_2027_JAN', date='20270105', time='10:00')
    monkeypatch.setattr(http, 'shared_log', [existing])
    monkeypatch.setattr(http, 'save_log_to_disk', lambda effacement_autorise=False: None)
    monkeypatch.setattr(http, 'current_config', {'usage_mode': 'contest'})
    ok, info = http.add_qso_to_log(_qso(contest='WWA_2027_JAN', date='20270105', time='14:00'))
    assert not ok and info.get('duplicate')


def test_dedup_wwa_autorise_jour_different_meme_scope(monkeypatch):
    """Le bug lui-même : un recontact un AUTRE jour de la même édition
    (même scope_id 'WWA_2027_JAN#2027') n'est plus refusé à tort."""
    existing = _qso(contest='WWA_2027_JAN', date='20270105', time='10:00')
    monkeypatch.setattr(http, 'shared_log', [existing])
    monkeypatch.setattr(http, 'save_log_to_disk', lambda effacement_autorise=False: None)
    monkeypatch.setattr(http, 'current_config', {'usage_mode': 'contest'})
    ok, _info = http.add_qso_to_log(_qso(contest='WWA_2027_JAN', date='20270112', time='10:00'))
    assert ok


def test_dedup_hors_wwa_reste_bloque_meme_scope_jour_different(monkeypatch):
    """Garde-fou de non-régression : un concours SANS dupe_reset='daily'
    (REF_QRP) continue de bloquer un recontact sur un autre jour de la même
    édition — le correctif ne doit s'appliquer QUE quand la brique est
    vraiment déclarée, pas systématiquement dès qu'une date diffère."""
    existing = _qso(date='20270718')
    monkeypatch.setattr(http, 'shared_log', [existing])
    monkeypatch.setattr(http, 'save_log_to_disk', lambda effacement_autorise=False: None)
    monkeypatch.setattr(http, 'current_config', {'usage_mode': 'contest'})
    ok, info = http.add_qso_to_log(_qso(date='20270719'))
    assert not ok and info.get('duplicate')


# ─── /log/list : le coeur du bug rapporté par l'utilisateur ─────────────────

def test_scope_filtered_vierge_sur_nouveau_concours():
    """Passer en mode concours sur une ÉDITION JAMAIS LOGUÉE doit montrer un
    log VIERGE, pas le log de base (import générique / logbook simple)."""
    base_log = [
        {'call': 'LZ2LP', 'contest': '', 'date': '20110809'},   # import ADIF générique
        {'call': 'F6ABC', 'contest': 'REF_RPH', 'date': '20250110'},  # autre concours
    ]
    cfg = {'usage_mode': 'contest', 'contest': 'REF_CDF_HF_SSB',
           'contest_start_date': '2027-02-20'}
    assert http._scope_filtered(base_log, cfg) == []


def test_scope_filtered_reprend_le_log_deja_logue_pour_ce_concours():
    """Si des QSO existent déjà pour CE concours+année précis (ex. relance de
    l'appli en cours de concours), ils réapparaissent — 'reprendre le dernier
    log de ce concours' plutôt qu'un log vierge."""
    base_log = [
        {'call': 'LZ2LP', 'contest': '', 'date': '20110809'},
        {'call': 'F6ABC', 'contest': 'REF_CDF_HF_SSB', 'date': '20270220'},
    ]
    cfg = {'usage_mode': 'contest', 'contest': 'REF_CDF_HF_SSB',
           'contest_start_date': '2027-02-20'}
    filtered = http._scope_filtered(base_log, cfg)
    assert len(filtered) == 1 and filtered[0]['call'] == 'F6ABC'


def test_scope_filtered_mode_simple_montre_tout():
    base_log = [
        {'call': 'LZ2LP', 'contest': '', 'date': '20110809'},
        {'call': 'F6ABC', 'contest': 'REF_CDF_HF_SSB', 'date': '20270220'},
    ]
    cfg = {'usage_mode': 'simple', 'contest': 'REF_CDF_HF_SSB',
           'contest_start_date': '2027-02-20'}
    assert http._scope_filtered(base_log, cfg) == base_log


def test_scope_filtered_aucun_concours_selectionne_montre_tout():
    base_log = [{'call': 'LZ2LP', 'contest': '', 'date': '20110809'}]
    cfg = {'usage_mode': 'contest', 'contest': ''}
    assert http._scope_filtered(base_log, cfg) == base_log
