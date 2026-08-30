# -*- coding: utf-8 -*-
"""Mise à jour hebdomadaire de la base des sommets SOTA (demande F4GLD).

Le cache disque est re-téléchargé depuis storage.sota.org.uk au 1er accès une
fois qu'il dépasse SUMMITS_MAX_AGE_DAYS. On vérifie la cadence (7 j) et que la
péremption déclenche bien un téléchargement — sans rapatrier les 25 Mo réels.
"""
import os
import sys

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CONCOURS not in sys.path:
    sys.path.insert(0, CONCOURS)

import logx_sota as sota    # noqa: E402
import logx_utils           # noqa: E402


def test_cadence_hebdomadaire():
    assert sota.SUMMITS_MAX_AGE_DAYS == 7


def test_cache_perime_declenche_le_telechargement(monkeypatch):
    appels = []
    # Cache réputé plus vieux que la cadence -> pas de lecture disque, on télécharge.
    monkeypatch.setattr(logx_utils, 'age_days', lambda f: sota.SUMMITS_MAX_AGE_DAYS + 1)

    def fake_fetch(url, timeout=60, user_agent=None):
        appels.append((url, user_agent))
        return None   # échec réseau simulé -> abandon propre, pas d'écrasement

    monkeypatch.setattr(logx_utils, 'fetch_url', fake_fetch)
    snap = dict(sota._summits)
    try:
        sota._load_from_disk_or_network()
    finally:
        sota._summits.clear()
        sota._summits.update(snap)
    assert len(appels) == 1 and appels[0][0] == sota.SOTA_SUMMITS_URL   # péremption -> re-téléchargement tenté
    # Le téléchargement s'identifie auprès de SOTA (User-Agent LogX-AI/version).
    assert (appels[0][1] or '').startswith('LogX-AI/')
