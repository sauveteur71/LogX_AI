# -*- coding: utf-8 -*-
"""Tests de la publication MQTT optionnelle (logx_mqtt.py) : réglages, repli
sans paho-mqtt installé, câblage topics/payloads, anti-spam de /rig/freq.

Aucun test ne se connecte à un vrai broker — un client MQTT factice est
injecté à la place de paho.mqtt.client.Client, ce qui garde la suite
déterministe/hors-ligne que le paquet optionnel soit installé ou non sur la
machine qui lance pytest (il ne l'est PAS par défaut, voir requirements.txt)."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_mqtt as lm


class _FakeMqttClient:
    """Remplace paho.mqtt.client.Client : mêmes méthodes utilisées par
    logx_mqtt, aucune E/S réseau — permet de vérifier le câblage (host/port,
    topics, payloads) sans broker ni dépendance réellement installée."""
    instances = []

    def __init__(self, *a, **k):
        self.published = []
        self.connected_to = None
        self.loop_started = False
        _FakeMqttClient.instances.append(self)

    def connect_async(self, host, port, keepalive=30):
        self.connected_to = (host, port)

    def loop_start(self):
        self.loop_started = True

    def loop_stop(self):
        pass

    def disconnect(self):
        pass

    def publish(self, topic, payload, qos=0, retain=False):
        self.published.append((topic, payload))


def _reset(monkeypatch, has_paho=True):
    """Repart d'un module MQTT vierge (pas de client connecté), avec un
    faux paho injecté — évite qu'un test contamine le suivant via l'état
    global _client/_client_target (singleton du module)."""
    monkeypatch.setattr(lm, 'HAS_PAHO', has_paho)
    monkeypatch.setattr(lm, 'mqtt', type('_FakeMqttModule', (), {'Client': _FakeMqttClient}))
    monkeypatch.setattr(lm, '_client', None)
    monkeypatch.setattr(lm, '_client_target', None)
    monkeypatch.setattr(lm, '_last_freq_khz', None)
    _FakeMqttClient.instances.clear()


# ─── RÉGLAGES (mqtt_settings) ─────────────────────────────────────────────────

def test_settings_desactive_par_defaut():
    s = lm.mqtt_settings({})
    assert s['enabled'] is False
    assert s['port'] == lm.DEFAULT_PORT
    assert s['prefix'] == 'logx'
    assert s['host'] == 'localhost'


def test_settings_lit_la_config():
    s = lm.mqtt_settings({'mqtt_enabled': True, 'mqtt_host': '192.168.1.50',
                          'mqtt_port': '1884', 'mqtt_topic_prefix': '/shack/'})
    assert s == {'enabled': True, 'host': '192.168.1.50', 'port': 1884, 'prefix': 'shack'}


def test_settings_port_invalide_repli_sur_defaut():
    s = lm.mqtt_settings({'mqtt_enabled': True, 'mqtt_host': 'x', 'mqtt_port': 'abc'})
    assert s['port'] == lm.DEFAULT_PORT


# ─── DÉGRADATION SANS paho-mqtt ───────────────────────────────────────────────
# HAS_PAHO=False (paquet non installé, cas par défaut du projet) : toute
# l'API doit rester silencieusement inopérante, jamais lever d'exception —
# add_qso_to_log ne doit jamais échouer à cause d'une dépendance optionnelle
# absente.

def test_publish_sans_paho_ne_leve_jamais(monkeypatch):
    _reset(monkeypatch, has_paho=False)
    cfg = {'mqtt_enabled': True, 'mqtt_host': 'localhost'}
    lm.publish_qso(cfg, {'call': 'F4GLD', 'band': '14'})
    lm.publish_score(cfg, 120, 'CQ_WW_SSB')
    lm.publish_rig_freq(cfg, 14074.0)
    assert _FakeMqttClient.instances == []   # aucune tentative de connexion


def test_publish_desactive_ne_cree_aucun_client(monkeypatch):
    """MQTT désactivé (réglage par défaut) : même avec paho disponible,
    aucune tentative de connexion au broker."""
    _reset(monkeypatch, has_paho=True)
    lm.publish_qso({}, {'call': 'F4GLD'})
    assert _FakeMqttClient.instances == []


# ─── CÂBLAGE TOPICS/PAYLOADS (paho factice) ──────────────────────────────────

def test_publish_qso_topic_et_payload(monkeypatch):
    _reset(monkeypatch)
    cfg = {'mqtt_enabled': True, 'mqtt_host': '127.0.0.1', 'mqtt_port': 1883}
    lm.publish_qso(cfg, {'call': 'F4GLD', 'band': '14', 'mode': 'SSB', 'points': 3})
    client = _FakeMqttClient.instances[-1]
    assert client.connected_to == ('127.0.0.1', 1883)
    topic, payload = client.published[-1]
    assert topic == 'logx/qso'
    body = json.loads(payload)
    assert body['call'] == 'F4GLD' and body['band'] == '14' and body['points'] == 3


def test_publish_qso_resout_lid_de_creneau_en_indicatif_reel(monkeypatch):
    """L'ID de créneau brut ('OP1') ne doit jamais partir vers un tableau de
    bord tiers (Node-RED, Home Assistant, overlay de streaming...) — même bug
    que LOGBOOK/export ADIF (signalement F4GLD 08/08/2026)."""
    _reset(monkeypatch)
    cfg = {'mqtt_enabled': True, 'mqtt_host': '127.0.0.1',
           'operators': [{'call': 'F1ABC'}]}
    lm.publish_qso(cfg, {'call': 'DL1AA', 'band': '14', 'operator': 'OP1'})
    client = _FakeMqttClient.instances[-1]
    body = json.loads(client.published[-1][1])
    assert body['operator'] == 'F1ABC'


def test_publish_score_topic_et_payload(monkeypatch):
    _reset(monkeypatch)
    cfg = {'mqtt_enabled': True, 'mqtt_host': '127.0.0.1'}
    lm.publish_score(cfg, 42, 'CQ_WW_SSB')
    topic, payload = _FakeMqttClient.instances[-1].published[-1]
    assert topic == 'logx/score'
    assert json.loads(payload) == {'score': 42, 'contest': 'CQ_WW_SSB'}


def test_publish_rig_freq_topic_et_prefix_personnalise(monkeypatch):
    _reset(monkeypatch)
    cfg = {'mqtt_enabled': True, 'mqtt_host': '127.0.0.1', 'mqtt_topic_prefix': 'shack'}
    lm.publish_rig_freq(cfg, 14074.5, 'FT8')
    topic, payload = _FakeMqttClient.instances[-1].published[-1]
    assert topic == 'shack/rig/freq'
    assert json.loads(payload) == {'freq_khz': 14074.5, 'mode': 'FT8'}


def test_ensure_client_idempotent_meme_host_port(monkeypatch):
    """Deux publications de suite vers le MÊME broker ne doivent PAS
    recréer/reconnecter un client à chaque fois (voir _ensure_client)."""
    _reset(monkeypatch)
    cfg = {'mqtt_enabled': True, 'mqtt_host': '127.0.0.1', 'mqtt_port': 1883}
    lm.publish_score(cfg, 10, 'X')
    lm.publish_score(cfg, 20, 'X')
    assert len(_FakeMqttClient.instances) == 1
    assert len(_FakeMqttClient.instances[0].published) == 2


def test_ensure_client_reconnecte_si_le_broker_change(monkeypatch):
    _reset(monkeypatch)
    lm.publish_score({'mqtt_enabled': True, 'mqtt_host': '127.0.0.1'}, 1, 'X')
    lm.publish_score({'mqtt_enabled': True, 'mqtt_host': '192.168.1.99'}, 2, 'X')
    assert len(_FakeMqttClient.instances) == 2


# ─── ANTI-SPAM DE /rig/freq (freq_changed) ───────────────────────────────────

def test_freq_changed_detecte_un_vrai_changement(monkeypatch):
    monkeypatch.setattr(lm, '_last_freq_khz', None)
    assert lm.freq_changed(14074.0) is True
    assert lm.freq_changed(14074.0) is False       # inchangé
    assert lm.freq_changed(14074.02) is False      # sous la tolérance (0.05 kHz)
    assert lm.freq_changed(14100.0) is True         # vrai QSY


def test_freq_changed_none_ignore():
    assert lm.freq_changed(None) is False
