# -*- coding: utf-8 -*-
"""mqtt_settings() : une désactivation EXPLICITE (mqtt_enabled=False dans cfg) ne
doit pas être ré-activée par un config.json périmé.

`enabled = enabled or bool(m.get('enabled'))` ré-activait MQTT dès que le fichier
disque portait encore enabled:true, ignorant le False voulu en mémoire (motif
« x or fichier » destructeur pour un booléen). Correctif : ne consulter le repli
disque pour `enabled` que si la clé est ABSENTE de cfg.
"""
import json
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

import logx_mqtt as mqtt  # noqa: E402


def _config(tmp):
    with open('config.json', 'w', encoding='utf-8') as f:
        json.dump({'mqtt': {'enabled': True, 'host': 'broker'}}, f)


def test_desactivation_explicite_non_reactivee(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _config(tmp_path)
    s = mqtt.mqtt_settings({'mqtt_enabled': False, 'mqtt_host': None})
    assert s['enabled'] is False, "un mqtt_enabled=False explicite ne doit pas être ré-activé"


def test_cle_absente_utilise_le_repli(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _config(tmp_path)
    s = mqtt.mqtt_settings({})          # mqtt_enabled absent -> repli config.json
    assert s['enabled'] is True
    assert s['host'] == 'broker'
