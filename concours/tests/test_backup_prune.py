# -*- coding: utf-8 -*-
"""Non-régression : la rétention des sauvegardes (_prune) doit être
CHRONOLOGIQUE, pas lexicographique sur le nom complet.

Les bases s'appellent logx_{indicatif}_{AAAAMMJJ-HHMMSS} : l'indicatif
précède l'horodatage. Avec un tri lexicographique du nom entier, un
changement d'indicatif (indicatif concours TM5X pendant un contest, puis
retour à l'indicatif personnel F4GLD qui trie avant) faisait supprimer la
sauvegarde toute neuve à la seconde où run_backup l'écrivait, tant qu'il
restait >= KEEP vieux jeux de l'ancien indicatif — silencieusement
(run_backup répondait ok:True et status() affichait une date fraîche).
"""
import os
import sys
import pathlib

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_backup as bk


def _make_set(folder, call, stamp):
    for ext in ('db', 'json', 'adi'):
        pathlib.Path(folder, f'logx_{call}_{stamp}.{ext}').write_text(
            'x', encoding='utf-8')


def test_prune_garde_la_sauvegarde_la_plus_recente_apres_changement_indicatif(tmp_path):
    """20 vieux jeux TM5X (2026) + 1 jeu neuf F4GLD (2027) : le jeu neuf
    doit survivre et c'est le PLUS VIEUX jeu TM5X qui doit partir."""
    folder = str(tmp_path)
    old_stamps = [f'202601{i:02d}-120000' for i in range(1, 21)]
    for stamp in old_stamps:
        _make_set(folder, 'TM5X', stamp)
    _make_set(folder, 'F4GLD', '20270115-090000')

    bk._prune(folder)

    rest = os.listdir(folder)
    assert any('F4GLD_20270115' in f for f in rest), (
        'la sauvegarde la plus récente (F4GLD 2027) a été supprimée : '
        'tri lexicographique sur le nom au lieu de l\'horodatage')
    # KEEP jeux conservés au total, et c'est le plus ancien (TM5X du 01/01)
    # qui a été élagué pour faire de la place.
    assert len(rest) == bk.KEEP * 3
    assert not any(old_stamps[0] in f for f in rest)
    assert any(old_stamps[-1] in f for f in rest)


def test_prune_ordre_chronologique_conserve_sans_changement_indicatif(tmp_path):
    """Cas nominal (indicatif stable) : comportement inchangé — on garde
    les KEEP plus récents, on supprime les plus anciens."""
    folder = str(tmp_path)
    stamps = [f'2026{m:02d}01-000000' for m in range(1, 13)] + \
             [f'202701{i:02d}-000000' for i in range(1, 13)]  # 24 jeux
    for stamp in stamps:
        _make_set(folder, 'F4GLD', stamp)

    bk._prune(folder)

    rest = os.listdir(folder)
    assert len(rest) == bk.KEEP * 3
    kept = sorted({f.rsplit('.', 1)[0] for f in rest})
    expected = sorted(f'logx_F4GLD_{s}' for s in stamps[-bk.KEEP:])
    assert kept == expected
