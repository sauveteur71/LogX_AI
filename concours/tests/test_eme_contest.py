# -*- coding: utf-8 -*-
"""European EME Contest (DUBUS/REF) — 7 parties dans CONTEST_DEFINITIONS.
Verrouille : présence des 7 IDs, structure (CW/SSB, 1 bande, scoring préfixe)
et DATES 2026 conformes au règlement officiel
(marsport.org.uk/dubus/EMEContest2026.pdf). Les date_rule sont interprétés par
le moteur générique logx_rules.calc_contest_date — ce test prouve qu'ils
produisent les bonnes dates, pas juste qu'ils sont écrits."""
import os
import sys

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CONCOURS not in sys.path:
    sys.path.insert(0, CONCOURS)

import logx_definitions as D   # noqa: E402
import logx_rules as R         # noqa: E402

EME = ['EME_432', 'EME_2320', 'EME_5760', 'EME_1296', 'EME_10368', 'EME_24048', 'EME_3400']


def test_les_7_parties_sont_definies():
    manquantes = [c for c in EME if c not in D.CONTEST_DEFINITIONS]
    assert not manquantes, manquantes


def test_structure_cw_ssb_scoring_prefixe():
    for cid in EME:
        d = D.CONTEST_DEFINITIONS[cid]
        assert d['modes'] == ['CW', 'SSB'], (cid, d['modes'])
        assert len(d['bands']) == 1, (cid, d['bands'])
        assert d['scoring']['type'] == 'prefix_multiplier', cid
        assert d['scoring']['points_dx'] == 100, cid
        assert d['organizer'] == 'DUBUS/REF', cid


def test_dates_2026_conformes_au_reglement():
    # Dates officielles DUBUS 2026 (une partie par bande/date).
    attendu = {
        'EME_432':   '31/01/2026',   # dernier samedi janvier
        'EME_2320':  '28/02/2026',   # dernier samedi février
        'EME_5760':  '21/03/2026',   # 3e samedi mars
        'EME_1296':  '18/04/2026',   # 3e week-end complet avril (VK3UM Memorial)
        'EME_10368': '16/05/2026',   # 3e samedi mai
        'EME_24048': '13/06/2026',   # 2e samedi juin
        'EME_3400':  '11/07/2026',   # 2e samedi juillet
    }
    for cid, jour in attendu.items():
        dr = D.CONTEST_DEFINITIONS[cid]['date_rule']
        calc = str(R.calc_contest_date(dr, 2026))
        assert jour in calc, (cid, dr, calc)
