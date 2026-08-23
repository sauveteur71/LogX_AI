# -*- coding: utf-8 -*-
"""Auto-spot cluster marqué refusé à tort (logx_clusters.py) — Strate 2, haute.

publish_self_spot() envoie le spot, puis demande sh/dx/5 pour confirmer que le
nôtre apparaît. Le contrôle de « refus » (mots 'dup', 'error', 'sorry',
'invalid'…) était appliqué à TOUT l'écho, sh/dx/5 inclus : les COMMENTAIRES des
spots d'AUTRES opérateurs contiennent régulièrement ces mots, ce qui marquait
notre spot pourtant réussi comme refusé.

Le jugement est désormais isolé dans _juger_self_spot() : le refus n'est cherché
que dans la réponse à NOTRE commande de spot, jamais dans la liste sh/dx/5.
"""
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

import logx_clusters as cl   # noqa: E402


def test_confirme_malgre_commentaires_dautres_spots():
    spot_echo = 'DX de F4GLD: your spot has been sent\r\n>'
    # la liste sh/dx/5 : spots d'AUTRES avec des mots piégeant l'ancien refus
    list_echo = ('14074.0  T88XX    dup? sorry error\r\n'
                 '14075.0  DL1ABC   invalid junk\r\n>')
    r = cl._juger_self_spot(spot_echo, list_echo, 'T88XX', 14074.0)
    assert r['ok'] is True and r['confirmed'] is True, (
        "notre spot est confirmé dans la liste : les commentaires d'autres "
        "spots ne doivent pas le faire passer pour refusé : %r" % r
    )


def test_vrai_refus_toujours_detecte():
    spot_echo = 'Sorry, you are not registered on this node\r\n>'
    r = cl._juger_self_spot(spot_echo, '>', 'T88XX', 14074.0)
    assert r['ok'] is False, "un vrai refus dans la réponse au spot doit rester détecté"


def test_envoye_mais_non_confirme():
    # réponse propre mais notre spot n'apparaît pas dans la liste
    r = cl._juger_self_spot('spot sent\r\n>', '14075.0 DL1ABC\r\n>', 'T88XX', 14074.0)
    assert r['ok'] is True and r['confirmed'] is False, r
