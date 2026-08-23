# -*- coding: utf-8 -*-
"""Garde de cohérence du catalogue rigs (concours/logx_rigs) — chantier catalogue.

Vérifie que le catalogue de métadonnées et les profils sourcés sont bien formés
et cohérents. Ne teste PAS de commandes CAT (aucune n'est activée à l'exécution
à ce stade) — c'est un garde de données.
"""
import json
import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RIGS = os.path.join(BASE, "logx_rigs")

_CAT_SUPPORT = {"native", "network_native", "serial_external", "partial", "none", "research"}
_DOC_STATUS = {"documented", "verified", "à sourcer"}


def test_catalogue_bien_forme():
    with open(os.path.join(RIGS, "catalogue.json"), encoding="utf-8") as f:
        data = json.load(f)
    rigs = data["rigs"]
    assert rigs and data["count"] == len(rigs)
    ids = set()
    for r in rigs:
        for champ in ("id", "manufacturer", "model", "status", "protocol", "cat_support",
                      "ft8_support", "documentation_status"):
            assert r.get(champ), "champ manquant %r dans %r" % (champ, r.get("id"))
        assert r["id"] not in ids, "id dupliqué : %s" % r["id"]
        ids.add(r["id"])
        assert r["cat_support"] in _CAT_SUPPORT, r
        assert r["documentation_status"] in _DOC_STATUS, r


def test_profils_references_existent_et_sont_sources():
    with open(os.path.join(RIGS, "catalogue.json"), encoding="utf-8") as f:
        rigs = json.load(f)["rigs"]
    for r in rigs:
        prof = r.get("profile")
        if not prof:
            continue
        chemin = os.path.join(RIGS, prof)
        assert os.path.isfile(chemin), "profil référencé absent : %s" % prof
        with open(chemin, encoding="utf-8") as f:
            p = json.load(f)
        # Règle d'or : un profil de commandes DOIT citer sa source et ne pas
        # prétendre être vérifié matériel tant qu'il ne l'est pas.
        assert p.get("source"), "profil %s sans source" % prof
        assert "verified_on_hardware" in p, "profil %s sans verified_on_hardware" % prof
        assert p.get("commands"), "profil %s sans commands" % prof
