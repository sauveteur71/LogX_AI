# -*- coding: utf-8 -*-
"""Le suivi satellite ignore le protocole rotor configuré (logx_sat_track.py) — Strate 2, haute.

logx_rotor expose get_position/set_position/stop avec un paramètre proto
('rotctld' par défaut, 'gs232' pour les boîtiers Yaesu/Kenpro natifs). rs, issu
de station.rotor_defaut(), porte bien rs['proto'] — mais AUCUN appel de
sat_track ne le transmettait : tout le suivi satellite parlait rotctld, même
sur un boîtier GS-232, qui ne répond pas. Ce test vérifie que le proto
configuré atteint bien les commandes rotor.
"""
import os
import re
import sys
import threading

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

import logx_sat_track as st   # noqa: E402


def test_boucle_suivi_transmet_le_proto_au_rotor(monkeypatch):
    captured = {}
    monkeypatch.setattr(st.rotor, 'stop',
                        lambda host, port, proto='rotctld': (captured.__setitem__('proto', proto)
                                                             or {'ok': True}))
    monkeypatch.setattr(st, '_fin', lambda *a, **k: None)
    ev = threading.Event()
    ev.set()   # arrêt immédiat -> premier tour prend le chemin rotor.stop
    # Sur le code d'origine, _boucle_suivi_corps n'accepte PAS proto -> TypeError
    # (témoin rouge) ; corrigé, proto='gs232' atteint rotor.stop.
    st._boucle_suivi_corps('SAT', 'h', 1, 45.0, 5.0, 100, {}, ev,
                           cadence_s=1, duree_max_s=60, deadband_deg=1.0,
                           offset_az=0.0, proto='gs232')
    assert captured.get('proto') == 'gs232', (
        "le protocole rotor configuré n'atteint pas rotor.stop : %r" % captured
    )


def test_tous_les_sites_rotor_passent_le_proto():
    src = (open(os.path.join(BASE, 'logx_sat_track.py'), encoding='utf-8').read())
    # plus aucun appel rotor « nu » (sans proto)
    assert not re.search(r'rotor\.stop\(host, port\)\s*\n', src), "un rotor.stop() sans proto subsiste"
    assert not re.search(r'rotor\.get_position\(host, port\)\s*\n', src), "un rotor.get_position() sans proto subsiste"
    assert not re.search(r'rotor\.set_position\(host, port, az_envoi, cible_el\)\s*\n', src), \
        "rotor.set_position() sans proto"
    # la vérif d'atteignabilité (demarrer_suivi) passe aussi le proto de rs
    assert re.search(r"rotor\.get_position\(rs\['host'\], rs\['port'\], proto=", src), \
        "la vérif d'atteignabilité n'utilise pas le proto configuré"
