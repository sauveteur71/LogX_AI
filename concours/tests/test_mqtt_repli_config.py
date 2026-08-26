# -*- coding: utf-8 -*-
"""Audit : mqtt_settings ne consultait le repli config.json que si host/enabled
manquaient. Un cfg fournissant host mais PAS port/prefix (redémarrage sans
/config/save) ignorait donc le port/prefix du disque. Corrigé : repli dès qu'un
champ manque."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_mqtt as mqtt


def test_port_prefix_repli_disque_meme_si_host_fourni(monkeypatch, tmp_path):
    (tmp_path / 'config.json').write_text(
        json.dumps({'mqtt': {'port': 1884, 'topic_prefix': 'homelab'}}), encoding='utf-8')
    monkeypatch.chdir(tmp_path)
    s = mqtt.mqtt_settings({'mqtt_enabled': True, 'mqtt_host': 'broker'})
    assert s['host'] == 'broker'
    assert s['port'] == 1884, "le port du config.json doit servir de repli"
    assert s['prefix'] == 'homelab', "le prefix du config.json doit servir de repli"
