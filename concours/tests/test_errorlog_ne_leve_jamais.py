# -*- coding: utf-8 -*-
"""_record() doit tenir sa promesse « ne lève jamais », même si l'exception a un
__str__ cassé.

La construction de tb_text (traceback.format_exception) et de message
(str(exc_value)) était faite AVANT le bloc try. Une exception dont __str__ lève
(args non imprimables, objet en finalisation à l'arrêt de l'interpréteur…)
faisait donc PROPAGER _record. Dans _excepthook, _record est appelé AVANT
sys.__excepthook__ et le gel de fenêtre : s'il lève, l'exe se referme sans rien
afficher ni journaliser — exactement le symptôme que ce module existe pour
supprimer.

Correctif : construire tb_text/message de façon défensive.
"""
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

import logx_errorlog as el  # noqa: E402


class _StrCasse(Exception):
    def __str__(self):
        raise RuntimeError('__str__ cassé')


def test_record_ne_leve_pas_sur_str_casse(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)   # errors.log dans le tmp, pas dans le dépôt
    try:
        raise _StrCasse('x')
    except _StrCasse as e:
        entry = el._record(type(e), e, e.__traceback__, 'testthread')
    # ne lève pas -> on obtient une entrée exploitable
    assert entry['type'] == '_StrCasse'
    assert entry['message']       # un repli lisible, pas une exception
    assert entry['thread'] == 'testthread'
