# -*- coding: utf-8 -*-
"""CHASSE : réchauffage du cache de spots HF depuis /data/spots_ranked.

DÉFAUT F4GLD (27/08/2026, capture « CLUSTER — NEED LIST : Aucun spot ») : la
page CHASSE LIT le cache de spots cluster (_spots_from_caches) mais ne le
REMPLIT jamais. Hors concours HF, et sans être passé par CARTE IA (ANALYSER) ou
PROPAG, SPOTS_CACHE['HF'] reste vide -> « 0 spots » dans la need list, alors que
les panneaux POTA/SOTA/WWFF (autres sources) s'affichent. C'est le MÊME défaut
que /data/focus corrigé le 25/08 (voir test_propag_spots_warm.py) — jamais
appliqué à CHASSE.

Correctif : /data/spots_ranked réchauffe le cache HF en tâche de fond (throttlé
par _warm_band_spots, déjà couvert par test_propag_spots_warm.py). Ce fichier
vérifie SEULEMENT le câblage : que le handler appelle bien le réchauffage HF.
"""
import os
import re
import sys

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CONCOURS not in sys.path:
    sys.path.insert(0, CONCOURS)
os.chdir(CONCOURS)


def test_spots_ranked_appelle_le_rechauffage_hf():
    """Le handler /data/spots_ranked doit réchauffer le cache HF AVANT de lire
    les caches (build_ranked_spots), sinon la need list reste vide hors
    concours. On exige la structure exacte de l'appel (une bande HF -> clé
    'HF'), pas une simple présence de la chaîne."""
    src = open(os.path.join(CONCOURS, 'logx_http.py'), encoding='utf-8').read()
    m = re.search(
        r"if path == '/data/spots_ranked':.*?ranked, meta = build_ranked_spots",
        src, re.S)
    assert m, 'handler /data/spots_ranked introuvable'
    handler = m.group(0)
    # Un appel à _warm_band_spots avec une bande HF (mappée sur la clé 'HF' par
    # _warm_key_for_band) et le snapshot de config.
    assert re.search(r"_warm_band_spots\('(1\.8|3\.5|7|10|14|18|21|24|28)', cfg_snap\)",
                     handler), \
        "spots_ranked ne rechauffe pas le cache HF (_warm_band_spots manquant)"
