# -*- coding: utf-8 -*-
"""Bulletin hebdomadaire REF (logx_ref_bulletin) : extraction de la rubrique
concours depuis une fixture réelle (bulletin Semaine 33/2026, capturé le
13/08/2026), cache disque avec TTL 7 jours, réseau mocké — même patron que
tests/test_dxpeditions.py et tests/test_wca.py (CACHE_FILE redirigé vers
tmp_path, jamais le vrai fichier du dépôt)."""
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_ref_bulletin as refbul
import logx_utils


# Extrait réel (raccourci) du bulletin Semaine 33/2026, avec les sentinelles
# et un texte francophone accentué pour vérifier l'absence de mojibake.
FIXTURE_BULLETIN = """==============================
Bulletin allégé.
==============================
Bulletin F8REF – 2026 Semaine 33

RÉSEAU des ÉMETTEURS FRANÇAIS

 INFOS NATIONALES

Revue Radio-REF
La revue de juillet-août 2026 a été déposée à la poste.

Commission des concours.

Les prochaines soirées d'activité THF:
- le 13/08 19h - 23h locale sur 50 MHz - le 18/08 19h - 23h locale sur 1296 MHz
Infos sur http://concours.r-e-f.org/tools/sat/index.php

Les concours DX importants du prochain week-end:
ARRL 10 GHz and Up Contest 0900Z, Aug 15 to 0759Z, Aug 17
https://www.contestcalendar.com/weeklycontdetails.php?ref=003dqi4o

Source: WA7BNM http://www.hornucopia.com/contestcal/index.html
Bonne chance à tous!
73 la commission des concours.

INFOS DÉPARTEMENTALES

65 – Hautes-Pyrénées
Une info départementale sans rapport avec les concours.
"""


def _reset_state(monkeypatch, tmp_path):
    monkeypatch.setattr(refbul, 'REF_BULLETIN_CACHE_FILE', str(tmp_path / 'ref_bulletin_cache.json'))
    refbul.REF_BULLETIN_CACHE = {}


# ─── _extract_concours_section() ────────────────────────────────────────────

def test_extract_section_isole_le_bloc_entre_sentinelles():
    section = refbul._extract_concours_section(FIXTURE_BULLETIN)
    assert section.startswith('Commission des concours.')
    assert section.endswith('73 la commission des concours.')
    assert 'INFOS NATIONALES' not in section
    assert 'INFOS DÉPARTEMENTALES' not in section
    assert 'Hautes-Pyrénées' not in section


def test_extract_section_conserve_les_accents():
    section = refbul._extract_concours_section(FIXTURE_BULLETIN)
    assert "activité THF" in section
    assert "à tous" in section
    assert '�' not in section  # aucun caractère de remplacement (mojibake)


def test_extract_section_normalise_crlf():
    section = refbul._extract_concours_section(FIXTURE_BULLETIN.replace('\n', '\r\n'))
    assert '\r' not in section


def test_extract_section_absente_renvoie_chaine_vide():
    assert refbul._extract_concours_section('Un bulletin sans la rubrique concours.') == ''


def test_week_re_extrait_annee_et_semaine():
    m = refbul.WEEK_RE.search(FIXTURE_BULLETIN)
    assert m is not None
    assert m.group(1) == '2026'
    assert m.group(2) == '33'


# ─── fetch_ref_bulletin() : réseau mocké ────────────────────────────────────

def test_fetch_ref_bulletin_ok(monkeypatch):
    monkeypatch.setattr(logx_utils, 'fetch_url', lambda *a, **k: FIXTURE_BULLETIN)
    data = refbul.fetch_ref_bulletin()
    assert data['year'] == 2026
    assert data['week'] == 33
    assert data['text'].startswith('Commission des concours.')
    assert data['source_url'] == refbul.REF_BULLETIN_URL


def test_fetch_ref_bulletin_reseau_injoignable_renvoie_none(monkeypatch):
    monkeypatch.setattr(logx_utils, 'fetch_url', lambda *a, **k: None)
    assert refbul.fetch_ref_bulletin() is None


def test_fetch_ref_bulletin_rubrique_absente_renvoie_none(monkeypatch):
    monkeypatch.setattr(logx_utils, 'fetch_url', lambda *a, **k: 'Bulletin sans rubrique concours.')
    assert refbul.fetch_ref_bulletin() is None


# ─── refresh_ref_bulletin() : ne jamais écraser un cache valide par du vide ─

def test_refresh_ecrit_le_cache_sur_disque(monkeypatch, tmp_path):
    _reset_state(monkeypatch, tmp_path)
    monkeypatch.setattr(logx_utils, 'fetch_url', lambda *a, **k: FIXTURE_BULLETIN)
    data = refbul.refresh_ref_bulletin()
    assert data['week'] == 33
    assert os.path.exists(refbul.REF_BULLETIN_CACHE_FILE)
    with open(refbul.REF_BULLETIN_CACHE_FILE, encoding='utf-8') as f:
        on_disk = json.load(f)
    assert on_disk['week'] == 33
    assert refbul.REF_BULLETIN_CACHE['week'] == 33


def test_refresh_reponse_vide_conserve_le_cache_existant(monkeypatch, tmp_path):
    _reset_state(monkeypatch, tmp_path)
    refbul.REF_BULLETIN_CACHE = {'week': 20, 'year': 2026, 'text': 'ancien cache'}
    monkeypatch.setattr(logx_utils, 'fetch_url', lambda *a, **k: None)
    result = refbul.refresh_ref_bulletin()
    assert result['week'] == 20
    assert refbul.REF_BULLETIN_CACHE['week'] == 20


# ─── load_ref_bulletin() : fraîcheur du cache disque ────────────────────────
# On ne patche PAS threading.Thread lui-même (module partagé par tout le
# process, un mock au niveau classe déborderait sur d'autres tests) : on
# remplace la fonction refresh_ref_bulletin par un stub qui s'exécute dans le
# VRAI thread daemon lancé par load_ref_bulletin(), puis on attend (poll
# court) qu'il ait tourné -- comportement observé, pas mécanisme interne.
def _wait_for(predicate, timeout=2.0):
    import time
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return predicate()


def test_load_sans_cache_disque_lance_un_refresh_en_fond(monkeypatch, tmp_path):
    _reset_state(monkeypatch, tmp_path)
    called = []
    monkeypatch.setattr(refbul, 'refresh_ref_bulletin', lambda: called.append(True))
    refbul.load_ref_bulletin()
    assert _wait_for(lambda: called)


def test_load_cache_recent_ne_relance_pas_de_refresh(monkeypatch, tmp_path):
    _reset_state(monkeypatch, tmp_path)
    fresh = {'week': 33, 'year': 2026, 'text': 'Commission des concours.\n...\n73 la commission des concours.',
             'updated': datetime.datetime.now().isoformat()}
    with open(refbul.REF_BULLETIN_CACHE_FILE, 'w', encoding='utf-8') as f:
        json.dump(fresh, f)
    called = []
    monkeypatch.setattr(refbul, 'refresh_ref_bulletin', lambda: called.append(True))
    refbul.load_ref_bulletin()
    assert not _wait_for(lambda: called, timeout=0.3)
    assert refbul.REF_BULLETIN_CACHE['week'] == 33


def test_load_cache_perime_relance_un_refresh(monkeypatch, tmp_path):
    _reset_state(monkeypatch, tmp_path)
    old = {'week': 20, 'year': 2026, 'text': 'Commission des concours.\n...\n73 la commission des concours.',
           'updated': (datetime.datetime.now() - datetime.timedelta(days=10)).isoformat()}
    with open(refbul.REF_BULLETIN_CACHE_FILE, 'w', encoding='utf-8') as f:
        json.dump(old, f)
    called = []
    monkeypatch.setattr(refbul, 'refresh_ref_bulletin', lambda: called.append(True))
    refbul.load_ref_bulletin()
    assert _wait_for(lambda: called)
