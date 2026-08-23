# -*- coding: utf-8 -*-
"""Import ADIF : affecter le lot à une activité (F4GLD 23/08).

Un log externe d'événement spécial (TM6KJS, TM43REF…) porte souvent l'indicatif
en STATION_CALLSIGN SANS CONTEST_ID -> il arriverait non tagué et l'export par
activité ne le retrouverait pas. `commit_import(..., activite='TM6KJS')` tague
les QSO neufs SANS concours propre ; un CONTEST_ID déjà présent n'est jamais
écrasé. `preview_import(..., activite=...)` compte d'avance (to_tag).

Modules purs (aucun I/O) — testés directement.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_import as imp

# Deux QSO valides SANS CONTEST_ID (cas typique d'un log d'événement spécial).
ADIF_SANS_CONTEST = (
    "<adif_ver:5>3.1.4<EOH>\n"
    "<CALL:5>F5AAA<BAND:3>20m<MODE:2>CW<QSO_DATE:8>20260801<TIME_ON:4>1000<EOR>\n"
    "<CALL:5>F5BBB<BAND:3>40m<MODE:3>SSB<QSO_DATE:8>20260801<TIME_ON:4>1005<EOR>\n"
)

# Un QSO qui porte DÉJÀ son concours (CONTEST_ID) + un QSO sans concours.
ADIF_MIXTE = (
    "<adif_ver:5>3.1.4<EOH>\n"
    "<CALL:5>F5CCC<BAND:3>20m<MODE:2>CW<QSO_DATE:8>20260802<TIME_ON:4>1100"
    "<CONTEST_ID:6>CQ-WPX<EOR>\n"
    "<CALL:5>F5DDD<BAND:3>20m<MODE:2>CW<QSO_DATE:8>20260802<TIME_ON:4>1105<EOR>\n"
)


def test_commit_tague_les_qso_sans_concours():
    new, _ = imp.commit_import(ADIF_SANS_CONTEST, existing_log=[], activite='TM6KJS')
    assert len(new) == 2
    assert all(q['contest'] == 'TM6KJS' for q in new), [q.get('contest') for q in new]


def test_commit_ne_ecrase_pas_un_contest_id_existant():
    new, _ = imp.commit_import(ADIF_MIXTE, existing_log=[], activite='TM6KJS')
    par_call = {q['call']: q for q in new}
    assert par_call['F5CCC']['contest'] == 'CQ-WPX'   # propre CONTEST_ID préservé
    assert par_call['F5DDD']['contest'] == 'TM6KJS'   # le sans-tag reçoit l'activité


def test_commit_sans_activite_laisse_le_contest_vide():
    new, _ = imp.commit_import(ADIF_SANS_CONTEST, existing_log=[], activite='')
    assert all(not q.get('contest') for q in new), [q.get('contest') for q in new]


def test_commit_activite_par_defaut_inchange():
    # signature rétro-compatible : sans le paramètre, comportement d'origine
    new, _ = imp.commit_import(ADIF_SANS_CONTEST, existing_log=[])
    assert all(not q.get('contest') for q in new)


def test_preview_compte_les_qso_a_taguer():
    p = imp.preview_import(ADIF_MIXTE, existing_log=[], activite='TM6KJS')
    assert p['to_tag'] == 1        # seul F5DDD (F5CCC a déjà son CONTEST_ID)
    p0 = imp.preview_import(ADIF_MIXTE, existing_log=[], activite='')
    assert p0['to_tag'] == 0       # pas d'activité saisie -> rien à taguer


def test_tag_ne_change_pas_la_dedup():
    # le tag ne doit ni créer ni perdre de QSO (dedup = call+band+mode+date+time)
    a, _ = imp.commit_import(ADIF_SANS_CONTEST, existing_log=[], activite='TM6KJS')
    b, _ = imp.commit_import(ADIF_SANS_CONTEST, existing_log=[])
    assert len(a) == len(b) == 2
