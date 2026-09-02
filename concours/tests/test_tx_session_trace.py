# -*- coding: utf-8 -*-
"""Trace serveur de la SESSION FT8 autonome (armement/arrêt + session_id) dans
le journal d'audit d'émission existant (logx_tx_consent) — Tâche 6 du plan
FT8 copilote niveaux 3/4.

Politique (skill tx-human-consent) : même journal d'audit que
journal_copilote_emission, UTC, non modifiable. Le PTT reste côté client ;
ceci trace l'AUTORISATION de session (armée par un geste humain) et sa fin,
consultable via /tx/audit même navigateur fermé ensuite."""
import datetime
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
os.chdir(BASE)

import logx_tx_consent as tx  # noqa: E402

UTC = datetime.timezone.utc


def test_journal_session_armed_puis_ended():
    tx.vider_audit()
    t0 = datetime.datetime(2026, 9, 2, 12, 0, 0, tzinfo=UTC)
    tx.journal_session('TX_SESSION_ARMED', 'sid42',
                        {'band': '20m', 'dial_hz': 14074000, 'mode': 'USB-D', 'power_w': 20},
                        now=t0)
    tx.journal_session('TX_SESSION_ENDED', 'sid42', {'raison': 'stop'},
                        now=t0 + datetime.timedelta(minutes=3))
    # Lecteur réel du journal d'audit (celui qui alimente GET /tx/audit) :
    # logx_tx_consent.audit_entries(limite) — pas 'lire_audit', qui n'existe
    # pas dans ce module.
    audit = tx.audit_entries(200)
    evs = [e for e in audit if e.get('consent_token') is None and e.get('session_id') == 'sid42']
    kinds = [e['event'] for e in evs]
    assert 'TX_SESSION_ARMED' in kinds and 'TX_SESSION_ENDED' in kinds
    armed = next(e for e in evs if e['event'] == 'TX_SESSION_ARMED')
    assert armed['timestamp_utc'].endswith('Z') or '+00:00' in armed['timestamp_utc']
    assert armed['details']['band'] == '20m'
    ended = next(e for e in evs if e['event'] == 'TX_SESSION_ENDED')
    assert ended['details']['raison'] == 'stop'
    # 3 minutes plus tard, bien après l'ARMED
    assert ended['timestamp_utc'] > armed['timestamp_utc']


def test_journal_session_details_non_dict_ne_leve_jamais():
    """Contrat verrouillé « ne lève JAMAIS » : la route /tx/session est un appel
    fire-and-forget (le PTT est déjà côté client). Un `details` malformé (chaîne,
    entier) doit être TOLÉRÉ — coercé en {} — et l'entrée quand même GRAVÉE, pas
    une exception qui ferait perdre la trace ET renverrait un 500."""
    tx.vider_audit()
    t0 = datetime.datetime(2026, 9, 2, 12, 0, 0, tzinfo=UTC)
    # Ne doit RIEN lever (assert implicite : pas d'exception propagée)
    e1 = tx.journal_session('TX_SESSION_ARMED', 'sid1', 'not-a-dict', now=t0)
    e2 = tx.journal_session('TX_SESSION_ARMED', 'sid2', 123, now=t0)
    # details non-dict -> {} (pas d'entrée corrompue)
    assert e1['details'] == {} and e2['details'] == {}
    # RÉELLEMENT gravé dans le journal (la trace n'est pas perdue)
    audit = tx.audit_entries(200)
    sids = {a.get('session_id') for a in audit if a.get('event') == 'TX_SESSION_ARMED'}
    assert 'sid1' in sids and 'sid2' in sids
    for a in audit:
        if a.get('session_id') in ('sid1', 'sid2'):
            assert isinstance(a['details'], dict)
