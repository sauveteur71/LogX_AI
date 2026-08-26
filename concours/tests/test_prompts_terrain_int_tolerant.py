# -*- coding: utf-8 -*-
"""Audit BASSE 717 : build_terrain_context faisait int(alert_dx_km) /
int(spotter_reliable_km) sans protection. Une config non-numérique (corrompue
ou éditée à la main) levait ValueError, alors que build_system_prompt utilise
ces mêmes champs sans jamais planter. On retombe sur les défauts."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_prompts as prompts


def test_terrain_context_champs_km_non_numeriques_ne_levent_pas():
    cfg = {'locator': 'JN18', 'contest': 'X',
           'alert_dx_km': 'abc', 'spotter_reliable_km': ''}
    out = prompts.build_terrain_context({}, {}, cfg)   # ne doit PAS lever
    assert isinstance(out, str)
