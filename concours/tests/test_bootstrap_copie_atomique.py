# -*- coding: utf-8 -*-
"""bootstrap() doit copier les fichiers de référence de façon ATOMIQUE.

shutil.copy2(src, dst) écrit directement sur la destination finale, protégé par
`if not os.path.exists(dst)`. Si la copie échoue en cours (disque plein, I/O,
process tué), dst existe déjà mais TRONQUÉ ; au lancement suivant le garde
d'existence saute la re-copie -> fichier de référence (cty.dat,
custom_contests.json…) corrompu de façon PERMANENTE.

Correctif : copier dans un .tmp puis os.replace() (atomique) — un dst tronqué ne
peut plus subsister, donc la copie est re-tentée au prochain démarrage.
"""
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

import logx_bootstrap as bs  # noqa: E402


def test_echec_de_copie_ne_laisse_pas_de_dst_tronque(tmp_path, monkeypatch):
    data = tmp_path / 'data'
    res = tmp_path / 'res'
    data.mkdir()
    res.mkdir()
    for n in bs._SEED_FILES:
        (res / n).write_text('x' * 100, encoding='utf-8')

    monkeypatch.setattr(bs, 'is_frozen', lambda: True)
    monkeypatch.setattr(bs, 'user_data_dir', lambda: str(data))
    monkeypatch.setattr(bs, 'resource_dir', lambda: str(res))
    monkeypatch.setattr(bs.os, 'chdir', lambda p: None)   # ne pas bouger le cwd du test

    def _copy_qui_echoue(src, dst):
        # simule une copie interrompue : un fichier partiel est créé PUIS erreur
        with open(dst, 'w', encoding='utf-8') as f:
            f.write('partiel')
        raise OSError('disque plein')
    monkeypatch.setattr(bs.shutil, 'copy2', _copy_qui_echoue)

    bs.bootstrap()   # ne doit pas lever

    # aucun fichier de référence FINAL ne doit subsister (copie échouée ->
    # re-tentable au prochain lancement, pas de dst tronqué qui bloque la reprise)
    for n in bs._SEED_FILES:
        assert not os.path.exists(data / n), f"{n} tronqué laissé en place"
