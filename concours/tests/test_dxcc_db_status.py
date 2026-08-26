# -*- coding: utf-8 -*-
"""DXCC — état de base explicite pour l'UI (décision F4GLD ②(a)+(b)). L'ancien
mode dégradé imprimait « repli heuristique préfixes » alors qu'AUCUN heuristique
n'existe : lookup() renvoie None pour tout indicatif quand cty.dat manque.
db_status() expose désormais l'état réel (database_missing / ready / …) avec un
message honnête, pour que l'interface affiche « DXCC indisponible »."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_dxcc as dxcc  # noqa: E402


def _reset(monkeypatch, path):
    monkeypatch.setattr(dxcc, 'CTY_FILE', str(path))
    monkeypatch.setattr(dxcc, '_loaded', False)
    monkeypatch.setattr(dxcc, '_db_status', 'unloaded')
    monkeypatch.setattr(dxcc, '_PREFIXES', {})
    monkeypatch.setattr(dxcc, '_EXACT', {})
    # Le cache de résolution est un global module qui PERSISTE entre tests :
    # sans ce reset, un test antérieur ayant résolu un indicatif avec une vraie
    # base le laisserait en cache et fausserait ce test (vu en CI, pas en local).
    monkeypatch.setattr(dxcc, '_lookup_cache', {})


def test_cty_absent_est_signale_database_missing(monkeypatch, tmp_path):
    _reset(monkeypatch, tmp_path / 'absent.dat')
    s = dxcc.db_status()
    assert s['status'] == 'database_missing'
    assert s['available'] is False
    assert 'désactivée' in s['message']
    # Pas de « valeurs fausses » : lookup renvoie None, pas un pays inventé.
    assert dxcc.lookup('F4GLD') is None


def test_message_ne_ment_plus_sur_un_heuristique():
    assert 'heuristique' not in dxcc._DB_STATUS_MSG['database_missing'].lower()


def test_mode_degrade_vide_le_cache_de_resolution(monkeypatch, tmp_path):
    # Un indicatif déjà résolu (cache peuplé) ne doit PAS ressortir en mode
    # dégradé : la base est indisponible → None, pas la valeur périmée.
    monkeypatch.setattr(dxcc, '_lookup_cache',
                        {'F4GLD': {'country': 'France', 'continent': 'EU'}})
    monkeypatch.setattr(dxcc, '_PREFIXES', {'F': ('France', 'EU', 14, 27, 'F', None, None)})
    monkeypatch.setattr(dxcc, 'CTY_FILE', str(tmp_path / 'parti.dat'))
    monkeypatch.setattr(dxcc, '_loaded', False)
    monkeypatch.setattr(dxcc, '_db_status', 'unloaded')
    dxcc.load_cty()
    assert dxcc.lookup('F4GLD') is None


def test_cty_valide_est_ready(monkeypatch, tmp_path):
    cty = tmp_path / 'cty.dat'
    cty.write_text("Fed. Rep. of Germany: 14: 28: EU: 51.00: 10.00: -1.0: DL:\n"
                   "    DA,DB;\n", encoding='utf-8')
    _reset(monkeypatch, cty)
    s = dxcc.db_status()
    assert s['status'] == 'ready'
    assert s['available'] is True
    assert s['message'] == ''


def test_cty_present_mais_vide_est_invalid(monkeypatch, tmp_path):
    cty = tmp_path / 'cty.dat'
    cty.write_text("   \n\n", encoding='utf-8')   # aucune entrée exploitable
    _reset(monkeypatch, cty)
    s = dxcc.db_status()
    assert s['status'] == 'database_invalid'
    assert s['available'] is False
