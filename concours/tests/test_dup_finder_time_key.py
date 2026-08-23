# -*- coding: utf-8 -*-
"""Clé de doublon 'même minute' incompatible entre formats d'heure (logx_dup_finder.js) — Strate 2.

dupKeyOf() prenait time.slice(0,5). Les QSO natifs ont l'heure au format
'HH:MM(:SS)' (avec deux-points) ; les QSO importés (ADIF TIME_ON) l'ont au format
'HHMM(SS)' (sans deux-points). slice(0,5) donne donc '14:30' d'un côté et '1430'
de l'autre pour la MÊME minute : les doublons entre une saisie manuelle et un
import ADIF échappaient à la détection « même minute ».

Correctif : normaliser l'heure en chiffres seuls (HHMM) avant de la clé.
"""
import json
import re
import pathlib
import pytest

py_mini_racer = pytest.importorskip("py_mini_racer")

_JS = pathlib.Path(__file__).resolve().parent.parent / "logx_dup_finder.js"


def _ctx():
    src = _JS.read_text(encoding="utf-8")
    m = re.search(r"function dupKeyOf\(q\)\{.*?\n\}", src, re.S)
    assert m, "dupKeyOf introuvable"
    ctx = py_mini_racer.MiniRacer()
    ctx.eval("var dupOptions={sameDay:false,sameMinute:true};")
    ctx.eval(m.group(0))
    return ctx


def test_meme_minute_formats_natif_et_importe_donnent_la_meme_cle():
    ctx = _ctx()
    natif = {"call": "F1ABC", "band": "20m", "mode": "SSB", "time": "14:30:00", "date": "20260101"}
    importe = {"call": "F1ABC", "band": "20m", "mode": "SSB", "time": "1430", "date": "20260101"}
    k1 = ctx.eval("dupKeyOf(%s)" % json.dumps(natif))
    k2 = ctx.eval("dupKeyOf(%s)" % json.dumps(importe))
    assert k1 == k2, ("clés différentes pour la même minute (natif vs importé)", k1, k2)


def test_minutes_differentes_donnent_des_cles_differentes():
    ctx = _ctx()
    a = {"call": "F1ABC", "band": "20m", "mode": "SSB", "time": "14:30", "date": "20260101"}
    b = {"call": "F1ABC", "band": "20m", "mode": "SSB", "time": "14:31", "date": "20260101"}
    assert ctx.eval("dupKeyOf(%s)" % json.dumps(a)) != ctx.eval("dupKeyOf(%s)" % json.dumps(b))
