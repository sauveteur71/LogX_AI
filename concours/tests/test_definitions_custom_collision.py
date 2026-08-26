# -*- coding: utf-8 -*-
"""Audit BASSE 623 : load_custom_contests() écrasait silencieusement une
définition INTÉGRÉE en cas de collision d'id, alors que save_custom_contest()
refuse justement d'écraser un concours de la base codée (asymétrie). Un fichier
custom_contests.json (édité à la main, ou réutilisant un id ajouté depuis à la
base intégrée) remplaçait donc en silence les règles curées d'un concours."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_definitions as d


def test_load_custom_n_ecrase_pas_un_concours_integre(tmp_path, monkeypatch):
    cid = 'REF_RPH'   # concours INTÉGRÉ (présent dans la base codée)
    assert cid in d.CONTEST_DEFINITIONS and cid not in d.CUSTOM_CONTEST_IDS
    original = d.CONTEST_DEFINITIONS[cid]

    f = tmp_path / 'custom.json'
    f.write_text(json.dumps({cid: {'definition': {'name': 'PIRATE', 'bidon': True}}}),
                 encoding='utf-8')
    monkeypatch.setattr(d, 'CUSTOM_CONTESTS_FILE', str(f))
    try:
        d.load_custom_contests()
        assert d.CONTEST_DEFINITIONS[cid] is original, \
            "un concours INTÉGRÉ a été écrasé par le fichier custom"
        assert cid not in d.CUSTOM_CONTEST_IDS
    finally:
        d.CONTEST_DEFINITIONS[cid] = original
        d.CUSTOM_CONTEST_IDS.discard(cid)


def test_load_custom_charge_bien_un_id_neuf(tmp_path, monkeypatch):
    cid = 'ZZ_TEST_CUSTOM_NEUF'   # id absent de la base intégrée
    assert cid not in d.CONTEST_DEFINITIONS
    f = tmp_path / 'custom.json'
    f.write_text(json.dumps({cid: {'definition': {'name': 'Mon concours'}}}), encoding='utf-8')
    monkeypatch.setattr(d, 'CUSTOM_CONTESTS_FILE', str(f))
    try:
        d.load_custom_contests()
        assert d.CONTEST_DEFINITIONS.get(cid, {}).get('name') == 'Mon concours'
        assert cid in d.CUSTOM_CONTEST_IDS
    finally:
        d.CONTEST_DEFINITIONS.pop(cid, None)
        d.CUSTOM_CONTEST_IDS.discard(cid)
