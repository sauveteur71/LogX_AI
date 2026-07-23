# -*- coding: utf-8 -*-
"""Test d'intégration : les points d'accroche MQTT dans logx_http.py
(add_qso_to_log -> logx/qso + logx/score, _rig_state_dict -> logx/rig/freq)
appellent VRAIMENT logx_mqtt lors d'un usage réel — pas seulement logx_mqtt.py
testé isolément (voir test_mqtt.py) ni le câblage relu sans être exécuté.

threading.Thread est remplacé par une variante synchrone le temps du test
(le thread fire-and-forget s'exécute immédiatement dans l'appelant) afin de
pouvoir vérifier son effet sans dépendre d'un minuscule délai d'attente.

Le remplacement cible UNIQUEMENT le nom `threading` du module logx_http (pas
le vrai module threading global) : add_qso_to_log() recalcule aussi les
points via un ThreadPoolExecutor (concurrent.futures), qui utilise SES
PROPRES threads internes — patcher threading.Thread globalement casse ce
recalcul (le worker interne de l'executor est alors appelé sans ses
arguments). Un faux module local pour logx_http.threading laisse
concurrent.futures totalement intact."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_http as http
import logx_mqtt as mqtt_bridge


class _SyncThread:
    """Remplace threading.Thread : exécute la cible immédiatement dans
    start(), au lieu de la déléguer à un vrai thread — rend le fire-and-forget
    déterministe/synchrone pour l'assertion qui suit."""
    def __init__(self, target=None, daemon=None, **kw):
        self._target = target

    def start(self):
        if self._target:
            self._target()


class _FakeThreadingModule:
    Thread = _SyncThread


def _prep(monkeypatch, cfg, log=None):
    monkeypatch.setattr(http, 'threading', _FakeThreadingModule)
    monkeypatch.setattr(http, 'shared_log', log if log is not None else [])
    monkeypatch.setattr(http, 'save_log_to_disk', lambda: None)
    monkeypatch.setattr(http, 'current_config', cfg)


def test_add_qso_publie_qso_et_score_sur_mqtt(monkeypatch):
    _prep(monkeypatch, {'mqtt_enabled': True, 'mqtt_host': '127.0.0.1'})
    published = {}
    monkeypatch.setattr(mqtt_bridge, 'publish_qso', lambda cfg, qso: published.__setitem__('qso', qso))
    monkeypatch.setattr(mqtt_bridge, 'publish_score',
                        lambda cfg, score, contest: published.update(score=score, contest=contest))

    qso = {'call': 'DL1ABC', 'band': '14', 'mode': 'SSB', 'contest': 'X',
           'date': '20270101', 'time': '10:00'}
    ok, _info = http.add_qso_to_log(qso)
    assert ok
    assert published['qso']['call'] == 'DL1ABC'
    # Le score publié doit être celui réellement recalculé côté serveur pour
    # CE QSO (voir test_log_points_recalc.py), pas une valeur arbitraire.
    assert published['score'] == http.shared_log[0]['points']
    assert published['contest'] == 'X'


def test_add_qso_ne_touche_pas_mqtt_si_desactive(monkeypatch):
    _prep(monkeypatch, {})   # mqtt_enabled absent -> désactivé par défaut
    called = []
    monkeypatch.setattr(mqtt_bridge, 'publish_qso', lambda cfg, qso: called.append('qso'))
    monkeypatch.setattr(mqtt_bridge, 'publish_score', lambda cfg, score, contest: called.append('score'))

    ok, _info = http.add_qso_to_log({'call': 'DL1ABC', 'band': '14', 'mode': 'SSB',
                                     'contest': 'X', 'date': '20270101', 'time': '10:00'})
    assert ok
    assert called == []


def test_rig_state_dict_publie_la_frequence_si_elle_change(monkeypatch):
    _prep(monkeypatch, {'mqtt_enabled': True, 'mqtt_host': '127.0.0.1'})
    monkeypatch.setattr(http, '_rig_state_dict_impl',
                        lambda cfg: {'enabled': True, 'ok': True, 'freq_khz': 14074.0, 'mode': 'USB'})
    monkeypatch.setattr(mqtt_bridge, '_last_freq_khz', None)
    published = {}
    monkeypatch.setattr(mqtt_bridge, 'publish_rig_freq',
                        lambda cfg, freq_khz, mode: published.update(freq_khz=freq_khz, mode=mode))

    cfg = {'mqtt_enabled': True, 'mqtt_host': '127.0.0.1'}
    st = http._rig_state_dict(cfg)
    assert st['freq_khz'] == 14074.0
    assert published == {'freq_khz': 14074.0, 'mode': 'USB'}

    # Deuxième appel, MÊME fréquence -> pas de republication (anti-spam).
    published.clear()
    http._rig_state_dict(cfg)
    assert published == {}

    # QSY réel -> republication.
    monkeypatch.setattr(http, '_rig_state_dict_impl',
                        lambda cfg: {'enabled': True, 'ok': True, 'freq_khz': 21074.0, 'mode': 'USB'})
    http._rig_state_dict(cfg)
    assert published == {'freq_khz': 21074.0, 'mode': 'USB'}


def test_rig_state_dict_ne_publie_rien_si_radio_injoignable(monkeypatch):
    _prep(monkeypatch, {'mqtt_enabled': True, 'mqtt_host': '127.0.0.1'})
    monkeypatch.setattr(http, '_rig_state_dict_impl',
                        lambda cfg: {'enabled': True, 'ok': False, 'error': 'timeout'})
    called = []
    monkeypatch.setattr(mqtt_bridge, 'publish_rig_freq', lambda *a, **k: called.append(1))
    st = http._rig_state_dict({'mqtt_enabled': True, 'mqtt_host': '127.0.0.1'})
    assert st['ok'] is False
    assert called == []
