# -*- coding: utf-8 -*-
"""Régression : couverture CONFIG_HELP pour les champs SO2R/WINKEYER (trouvés
sans aucune entrée d'aide par l'audit trouvabilité du 09/08/2026, WINKEYER
étant en plus visible en mode débutant) et pour 7 champs mineurs déjà
identifiés à l'époque du correctif B4 (#45) mais réapparus depuis (relay
port/baud/host/user/password, acom_enabled, mysql_password)."""
import os
import re

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML_PATH = os.path.join(BASE, 'logx_configuration.html')

SO2R_WINKEYER_IDS = [
    'cat2_enabled', 'cat2_mode', 'cat2_brand', 'cat2_port', 'cat2_baudrate',
    'cat2_omnirig_rig_num', 'voicekeyer_device2', 'so2r_enabled', 'so2r_port',
    'so2r_stereo', 'winkeyer_enabled', 'winkeyer_port', 'winkeyer_wpm',
]
MINEUR_IDS = [
    'relay_port', 'relay_baud', 'relay_host', 'relay_user', 'relay_password',
    'acom_enabled', 'mysql_password',
]


def _config_help_keys():
    with open(HTML_PATH, encoding='utf-8') as f:
        src = f.read()
    # Script inline extrait vers logx_configuration.js (10/08/2026).
    js_path = os.path.join(BASE, 'logx_configuration.js')
    if os.path.exists(js_path):
        with open(js_path, encoding='utf-8') as f:
            src += '\n' + f.read()
    m = re.search(r'const CONFIG_HELP = \{(.*?)\n\};', src, re.S)
    assert m, 'objet CONFIG_HELP introuvable dans logx_configuration.html'
    body = m.group(1)
    return set(re.findall(r'^\s*(\w+):', body, re.M))


def test_champs_so2r_winkeyer_ont_une_entree_config_help():
    keys = _config_help_keys()
    missing = [k for k in SO2R_WINKEYER_IDS if k not in keys]
    assert not missing, f"champs SO2R/WINKEYER sans entrée CONFIG_HELP : {missing}"


def test_champs_mineurs_relay_acom_mysql_ont_une_entree_config_help():
    keys = _config_help_keys()
    missing = [k for k in MINEUR_IDS if k not in keys]
    assert not missing, f"champs sans entrée CONFIG_HELP : {missing}"
