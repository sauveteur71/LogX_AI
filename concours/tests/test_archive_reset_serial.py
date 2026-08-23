# -*- coding: utf-8 -*-
"""archiveLog(clear) ne réinitialisait pas le n° de série (logx_outils_autonomes.js) — Strate 2.

La branche « log vidé » d'archiveLog() vidait qsoLog mais, contrairement à
resetLog(), ne remettait PAS serialByBand à zéro ni n'appelait
updateSerialDisplay() : après « Archiver et vider », le n° de série proposé
continuait (041 au lieu de 001) pour le concours suivant.
"""
import re
import pathlib

_JS = pathlib.Path(__file__).resolve().parent.parent / "logx_outils_autonomes.js"


def test_archive_vider_reinitialise_le_numero_de_serie():
    src = _JS.read_text(encoding="utf-8")
    m = re.search(r"if\(d\.cleared\)\{[^}]*\}", src)
    assert m, "branche d.cleared d'archiveLog introuvable"
    branche = m.group(0)
    assert "serialByBand" in branche and "{}" in branche, (
        "archiveLog(clear) doit remettre serialByBand à zéro (comme resetLog)"
    )
    assert "updateSerialDisplay" in branche, (
        "archiveLog(clear) doit rafraîchir l'affichage du n° de série"
    )
