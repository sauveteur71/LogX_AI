# -*- coding: utf-8 -*-
"""Non-régression : le libellé du journal dans le contexte terrain envoyé au
copilote IA (build_terrain_context(), logx_prompts.py) ne doit affirmer
« LOG PARTAGÉ MULTI-OPÉRATEUR » que si le journal contient RÉELLEMENT 2+
opérateurs distincts — pas dès qu'il contient des QSO.

Signalement F4GLD (08/08/2026) : sur un profil en LOGBOOK SIMPLE (un seul
opérateur, aucune synchro réseau active — mysql_mode='off', cloudsync_mode
vide, confirmé en lisant .server_config.json), le coach IA de la carte a
répondu que le log était "partagé" à cause d'une "connexion Cloud Sync
active" — une explication INVENTÉE par le LLM à partir du libellé
« LOG PARTAGÉ MULTI-OPÉRATEUR (N QSO) », injecté SANS CONDITION dès que
`shared_log` (liste en mémoire, partagée entre les ONGLETS d'un même
serveur — pas entre plusieurs stations réseau) contenait des QSO. Le
chiffre (~9800 QSO) était réel : c'était juste l'historique local complet
de l'opérateur, accumulé sur plusieurs mois."""
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

import logx_prompts as prompts  # noqa: E402


def _cfg():
    return {'locator': 'JN15WD', 'contest': 'CUSTOM', 'callsign': 'F4GLD'}


def test_libelle_reste_neutre_avec_un_seul_operateur(monkeypatch):
    """Cas exact du signalement : log volumineux mais un seul opérateur."""
    monkeypatch.setattr(prompts, 'shared_log', [
        {'call': 'F5DJL', 'operator': 'F4GLD', 'time': '10:00', 'locator': 'JN18DT', 'points': 1}
        for _ in range(50)
    ])
    ctx = prompts.build_terrain_context({}, {}, _cfg())
    assert 'LOG LOGX AI (50 QSO)' in ctx
    assert 'MULTI-OPÉRATEUR' not in ctx


def test_libelle_reste_neutre_sans_champ_operator_du_tout():
    """QSO importés sans champ operator (ex. import ADIF externe) : ne doit
    pas non plus être qualifié de multi-opérateur."""
    fake_log = [{'call': 'F5DJL', 'time': '10:00', 'locator': 'JN18DT', 'points': 1}]
    import logx_prompts as p
    orig = p.shared_log
    p.shared_log = fake_log
    try:
        ctx = p.build_terrain_context({}, {}, _cfg())
        assert 'MULTI-OPÉRATEUR' not in ctx
    finally:
        p.shared_log = orig


def test_libelle_multi_operateur_conserve_si_reellement_plusieurs_ops(monkeypatch):
    """Radioclub réel (2+ opérateurs distincts effectivement tagués) : le
    libellé multi-opérateur reste correct et doit être conservé."""
    monkeypatch.setattr(prompts, 'shared_log', [
        {'call': 'F5DJL', 'operator': 'F4GLD', 'time': '10:00', 'locator': 'JN18DT', 'points': 1},
        {'call': 'LZ2LP', 'operator': 'F1ABC', 'time': '10:05', 'locator': 'JN18DT', 'points': 1},
    ])
    ctx = prompts.build_terrain_context({}, {}, _cfg())
    assert 'LOG PARTAGÉ MULTI-OPÉRATEUR (2 QSO)' in ctx


def test_libelle_absent_si_log_vide(monkeypatch):
    monkeypatch.setattr(prompts, 'shared_log', [])
    ctx = prompts.build_terrain_context({}, {}, _cfg())
    assert 'LOG LOGX AI' not in ctx
    assert 'MULTI-OPÉRATEUR' not in ctx


def test_libelle_reste_neutre_meme_operateur_sous_deux_formats(monkeypatch):
    """Un même opérateur physique peut écrire des QSO sous DEUX formats
    différents selon la voie utilisée : l'ID de créneau LOGBOOK ('OP1') et
    son indicatif réel (page FT8 native, WSJT-X, import ADIF) — sans
    résolution avant comparaison, distinct_ops verrait à tort 2 valeurs et
    redéclencherait exactement le faux positif que ce fichier de test existe
    pour garder sous contrôle (revue adversariale du 08/08/2026)."""
    monkeypatch.setattr(prompts, 'shared_log', [
        {'call': 'F5DJL', 'operator': 'OP1', 'time': '10:00', 'locator': 'JN18DT', 'points': 1},
        {'call': 'LZ2LP', 'operator': 'F4GLD', 'time': '10:05', 'locator': 'JN18DT', 'points': 1},
        {'call': 'DL1AA', 'operator': 'f4gld', 'time': '10:10', 'locator': 'JN18DT', 'points': 1},
    ])
    ctx = prompts.build_terrain_context({}, {}, _cfg())
    assert 'LOG LOGX AI (3 QSO)' in ctx
    assert 'MULTI-OPÉRATEUR' not in ctx
