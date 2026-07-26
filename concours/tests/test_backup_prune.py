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


def _make_cloudsync(folder, call, iid):
    """Fichiers écrits par Cloud Sync dans CE MÊME dossier : cloudsync_settings
    replie cloudsync_folder sur backup_folder (repli documenté dans CONFIG,
    « vide = même dossier que SAUVEGARDE »)."""
    import logx_cloudsync as cs
    names = [f'{cs.SYNC_PREFIX}{call}_{iid}.json',
             f'{cs.TOMB_PREFIX}{call}_{iid}.json']
    for n in names:
        pathlib.Path(folder, n).write_text('[]', encoding='utf-8')
    return names


def test_prune_ne_touche_pas_aux_fichiers_cloudsync(tmp_path):
    """Le dossier de sauvegarde EST aussi le dossier Cloud Sync par défaut.

    logx_cloudsync_<call>_<id>.json et logx_cloudtomb_<call>_<id>.json
    matchent 'logx_*', mais leur suffixe est l'identifiant d'installation
    (uuid4().hex[:8]), pas un horodatage : un id commençant par 0/1/2 trie
    AVANT tout horodatage '2026…' et les faisait élaguer dès qu'il y avait
    plus de KEEP jeux (~5 h au réglage par défaut). Le fichier de tombstones
    étant la SEULE trace persistante des suppressions individuelles
    (logx_storage.deleted_qsos est en mémoire de process), le détruire fait
    RESSUSCITER au redémarrage les QSO supprimés, depuis le fichier d'un
    autre poste — exactement la panne que ce mécanisme existe pour empêcher.
    """
    for iid in ('0f3a2b1c', '1a2b3c4d', '20000000', 'ab12cd34'):
        folder = str(tmp_path / iid)
        os.makedirs(folder)
        for i in range(1, 26):                      # 25 jeux > KEEP
            _make_set(folder, 'TX7L', f'20260726-{i:02d}0000')
        names = _make_cloudsync(folder, 'TX7L', iid)

        bk._prune(folder)

        rest = os.listdir(folder)
        for n in names:
            assert n in rest, (
                f'{n} détruit par la rotation des sauvegardes (id {iid}) : '
                'suppressions ressuscitées / log publié perdu')
        # …et il reste bien KEEP VRAIS jeux : les 2 fichiers Cloud Sync ne
        # doivent pas non plus consommer 2 emplacements de rétention.
        assert len([f for f in rest if f.endswith('.db')]) == bk.KEEP


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
