# -*- coding: utf-8 -*-
"""_vkIsLikelyVirtual() (logx_configuration.js) : le groupement des
périphériques audio du keyer vocal doit reconnaître les cartes son USB
intégrées des postes récents.

Bug réel signalé par F4GLD (14/08/2026) : « je n'ai pas trouvé usb audio
codec pour le keyer vocal » — beaucoup de postes (IC-7300 et bien d'autres)
embarquent une carte son USB reconnue par Windows sous le nom générique du
pilote standard (« USB Audio CODEC »/« USB Audio Device »), pas sous le nom
du poste. Ce nom ne correspondait à aucun motif reconnu, donc retombait
dans le groupe « Autres sorties (haut-parleurs, casque…) » au lieu d'être
groupé avec les interfaces recommandées — alors que c'est exactement
l'usage prévu.

Ce module extrait la VRAIE fonction du fichier source (par comptage
d'accolades, pas retapée) — même technique que
test_config_bands_modes_from_server.py."""
import os

import pytest

py_mini_racer = pytest.importorskip(
    'py_mini_racer', reason='py_mini_racer absent (voir requirements.txt) — test JS réel ignoré')

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS_PATH = os.path.join(BASE, 'logx_configuration.js')

with open(JS_PATH, encoding='utf-8') as _f:
    _JS_SRC = _f.read()


def _extract_function(src, name):
    start = src.index(f'function {name}(')
    brace_open = src.index('{', start)
    depth = 0
    i = brace_open
    while True:
        c = src[i]
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                return src[start:i + 1]
        i += 1


_FUNC_SRC = _extract_function(_JS_SRC, '_vkIsLikelyVirtual')


@pytest.fixture
def ctx():
    c = py_mini_racer.MiniRacer()
    c.eval(_FUNC_SRC)
    return c


@pytest.mark.parametrize('nom', [
    'USB Audio CODEC',
    'USB Audio Device',
    'USB Audio CODEC (IC-7300)',
    '2- USB Audio CODEC',
])
def test_carte_son_usb_generique_reconnue(ctx, nom):
    """Nom générique attribué par Windows aux interfaces USB Audio Class
    sans pilote OEM dédié — le cas exact de l'IC-7300 signalé par F4GLD."""
    assert ctx.eval("_vkIsLikelyVirtual(%r)" % nom) is True


@pytest.mark.parametrize('nom', [
    'VB-Audio Virtual Cable',
    'Voicemeeter Input',
    'microHAM USB Device',
    'SignaLink USB',
    'RigBlaster Advantage',
    'DigiRig Mobile',
])
def test_interfaces_deja_reconnues_non_regression(ctx, nom):
    assert ctx.eval("_vkIsLikelyVirtual(%r)" % nom) is True


@pytest.mark.parametrize('nom', [
    'Haut-parleurs (Realtek High Definition Audio)',
    'Casque (Bluetooth)',
    'Microphone intégré',
])
def test_sorties_physiques_restent_non_recommandees(ctx, nom):
    assert ctx.eval("_vkIsLikelyVirtual(%r)" % nom) is False


def test_nom_vide_ou_absent_ne_plante_pas(ctx):
    assert ctx.eval("_vkIsLikelyVirtual('')") is False
    assert ctx.eval("_vkIsLikelyVirtual(null)") is False
    assert ctx.eval("_vkIsLikelyVirtual(undefined)") is False
