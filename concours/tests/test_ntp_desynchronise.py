# -*- coding: utf-8 -*-
"""interroger() acceptait un serveur NTP DÉSYNCHRONISÉ (LI=3, strate 16).

Le code lisait le mode et traitait le Kiss-o'-Death (strate 0), mais ne
vérifiait JAMAIS l'indicateur de saut (LI = octet0 >> 6) ni la strate 16. Un
serveur en état d'alarme répond LI=3 / strate=16 tout en renvoyant mode 4 : ses
horodatages viennent alors de son propre quartz libre — exactement le défaut que
ce module doit détecter côté client. interroger() renvoyait ok:True/sur:True,
et un opérateur FT8 se calait sur une référence FAUSSE en croyant l'avoir validée.

Correctif : rejeter LI==3 ou strate>=16 (RFC 5905). Logique de parsing extraite
dans _analyser_reponse() pour être testable avec des octets fabriqués.
"""
import os
import struct
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

import logx_ntp as ntp  # noqa: E402


def _reponse(li, mode, strate, t2_posix=None, t3_posix=None):
    b = bytearray(48)
    b[0] = ((li & 0b11) << 6) | (mode & 0b111)
    b[1] = strate & 0xFF

    def put(off, tposix):
        if tposix is None:
            return
        entier = (int(tposix) + ntp.ERE_NTP_VERS_POSIX) & 0xFFFFFFFF
        b[off:off + 8] = struct.pack('!II', entier, 0)
    put(32, t2_posix)
    put(40, t3_posix)
    return bytes(b)


def test_rejette_serveur_desynchronise_li3_strate16():
    r = ntp._analyser_reponse(_reponse(3, 4, 16), 'srv', 0.0, 0.0)
    assert r['ok'] is False and 'synchron' in r['error'].lower(), r


def test_rejette_strate_16_seule():
    assert ntp._analyser_reponse(_reponse(0, 4, 16), 'srv', 0.0, 0.0)['ok'] is False


def test_rejette_li3_seul():
    assert ntp._analyser_reponse(_reponse(3, 4, 2), 'srv', 0.0, 0.0)['ok'] is False


def test_kod_strate0_toujours_rejete():
    assert ntp._analyser_reponse(_reponse(0, 4, 0), 'srv', 0.0, 0.0)['ok'] is False


def test_accepte_un_serveur_sain():
    T = 1_700_000_000
    r = ntp._analyser_reponse(_reponse(0, 4, 2, t2_posix=T, t3_posix=T),
                              'srv', float(T), float(T))
    assert r['ok'] is True and r['sur'] is True, r
