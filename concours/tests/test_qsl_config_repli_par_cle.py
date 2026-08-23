# -*- coding: utf-8 -*-
"""qsl_settings() : le repli vers config.json doit être PAR CLÉ, pas tout-ou-rien.

Le repli n'était tenté que si AUCUN identifiant n'était déjà renseigné
(`if not any(s.values())`). Dès qu'UNE valeur était présente côté client (ex.
eqsl_user), le repli était entièrement sauté — les identifiants des AUTRES
services stockés uniquement dans config.json n'étaient jamais chargés (LoTW/HRDLog
annoncés « non configurés » alors qu'ils existaient côté serveur).
"""
import json
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

import logx_qsl as qsl  # noqa: E402


def test_repli_config_json_par_cle(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with open('config.json', 'w', encoding='utf-8') as f:
        json.dump({'qsl': {'lotw_user': 'F4GLD', 'lotw_password': 'x',
                           'hrdlog_callsign': 'F4GLD', 'hrdlog_code': '123'}}, f)

    # cfg client : SEULEMENT eqsl renseigné -> avant, le repli était sauté
    s = qsl.qsl_settings({'eqsl_user': 'a', 'eqsl_password': 'b'})

    assert s['eqsl_enabled'] is True       # vient du client
    assert s['lotw_enabled'] is True       # doit venir de config.json (avant : False)
    assert s['hrdlog_enabled'] is True     # idem


def test_client_prime_sur_config(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with open('config.json', 'w', encoding='utf-8') as f:
        json.dump({'qsl': {'eqsl_user': 'DEPUIS_CONFIG', 'eqsl_password': 'z'}}, f)
    s = qsl.qsl_settings({'eqsl_user': 'client', 'eqsl_password': 'b'})
    assert s['eqsl_user'] == 'CLIENT' or s['eqsl_user'] == 'client'   # la valeur client n'est pas écrasée
    assert s['eqsl_user'].lower() == 'client'
