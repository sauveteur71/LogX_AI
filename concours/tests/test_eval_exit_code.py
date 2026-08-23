# -*- coding: utf-8 -*-
"""logx_eval : un run qui n'évalue AUCUN champ sortait en code 0 (faux vert).

Si --only ne matche aucun cas (faute de frappe) ou si le corpus est vide, la
boucle n'incrémente rien : total=0, total_ok=0, donc `0 == 0` -> sys.exit(0).
Un harnais d'éval qui n'a rien testé ne doit pas se lire comme un succès pour
la CI/un script appelant.
"""
import os
import sys

import pytest

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

import logx_eval   # noqa: E402


def test_eval_aucun_champ_evalue_ne_sort_pas_en_succes(monkeypatch):
    # --mock évite tout accès réseau / clé API ; --only sans correspondance ->
    # la boucle ne joue aucun cas -> total == 0.
    monkeypatch.setattr(sys, 'argv',
                        ['logx_eval.py', '--mock', '--only', '___nexiste_pas___'])
    with pytest.raises(SystemExit) as ei:
        logx_eval.main()
    code = ei.value.code
    assert code not in (0, None), \
        "un run qui n'évalue aucun champ ne doit pas retourner un succès"
