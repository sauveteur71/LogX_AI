"""Garde-fou du service worker (logx_sw.js) : le repli hors-ligne du SHELL.

Constat d'audit (Strate 2, critique) : la regex du garde 'donnees live' de la
ligne `if (/.../.test(url.pathname)) return;` contenait l'alternative `log`
SANS frontiere de fin. Elle matchait donc le prefixe `log` de TOUS les fichiers
`/logx_*` (logbook.html/.js, mobile.html, statusbar.js, i18n.js, icon.svg), qui
sont justement 6 des 7 entrees du SHELL. Ces requetes tombaient dans le `return`
(reseau uniquement) et n'etaient JAMAIS servies depuis le cache : le repli
hors-ligne etait casse pour l'essentiel de l'app.

Ce test extrait la regex REELLE du fichier et verifie, via le meme moteur que
le navigateur (V8), que les fichiers du SHELL ne sont PAS court-circuites, et
que les endpoints de donnees live le restent bien.
"""
import re
import pathlib
import pytest

py_mini_racer = pytest.importorskip("py_mini_racer")

_SW = pathlib.Path(__file__).resolve().parent.parent / "logx_sw.js"


def _guard_regex():
    src = _SW.read_text(encoding="utf-8")
    # Ligne : if (/^\/(...)/.test(url.pathname)) return;  -> capturer le litteral regex.
    m = re.search(r"(/\^.*/)\.test\(url\.pathname\)", src)
    assert m, "garde regex 'donnees live' introuvable dans logx_sw.js"
    return m.group(1)


# 6 des 7 entrees du SHELL commencent par /logx_ ; elles NE doivent PAS matcher.
_SHELL_FICHIERS = [
    "/logx_logbook.html", "/logx_logbook.js", "/logx_mobile.html",
    "/logx_statusbar.js", "/logx_i18n.js", "/logx_icon.svg",
]

# Endpoints de donnees live : ils DOIVENT rester en reseau direct (return).
_DONNEES_LIVE = [
    "/log/add", "/log/list", "/data/world_map", "/config", "/config/save",
    "/agent/stream", "/rig/state", "/coach/state", "/cluster/spots",
    "/countries", "/departments", "/rotor/state", "/activation/status",
    "/proxy/ai",
]


def _teste(paths):
    ctx = py_mini_racer.MiniRacer()
    rx = _guard_regex()
    return {p: ctx.eval("%s.test(%s)" % (rx, __import__("json").dumps(p))) for p in paths}


def test_les_fichiers_du_shell_ne_sont_pas_court_circuites():
    res = _teste(_SHELL_FICHIERS)
    faux = [p for p, v in res.items() if v]
    assert not faux, (
        "Ces fichiers du SHELL sont court-circuites par le garde (repli "
        "hors-ligne casse) : %r" % faux
    )


def test_les_endpoints_de_donnees_live_restent_en_reseau_direct():
    res = _teste(_DONNEES_LIVE)
    rates = [p for p, v in res.items() if not v]
    assert not rates, (
        "Ces endpoints de donnees live ne sont PLUS court-circuites (risque de "
        "cache perime sur des donnees vivantes) : %r" % rates
    )
