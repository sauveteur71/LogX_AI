# -*- coding: utf-8 -*-
"""Ouverture du port multi-poste dans le pare-feu Windows (logx_firewall).

On teste ce qui est déterministe : les arguments netsh de la règle et la commande
d'élévation PowerShell (quoting sûr, RunAs). L'ajout réel exige l'admin et n'est
pas testé ici.
"""
import os
import sys

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CONCOURS not in sys.path:
    sys.path.insert(0, CONCOURS)

import logx_firewall as fw    # noqa: E402


def test_nom_de_regle_sans_espace():
    # Sans espace -> pas de galère de quoting quand netsh est relancé via PowerShell.
    assert ' ' not in fw.RULE_NAME


def test_add_argv_ouvre_le_bon_port_en_entree():
    a = fw._add_argv(8080)
    assert a[:4] == ['advfirewall', 'firewall', 'add', 'rule']
    assert 'name=' + fw.RULE_NAME in a
    assert 'dir=in' in a and 'action=allow' in a
    assert 'protocol=TCP' in a and 'localport=8080' in a
    assert all(' ' not in x for x in a)     # aucun argument espacé


def test_commande_elevation_runas_et_quoting_sur():
    ps = fw._elevate_powershell(fw._add_argv(8080))
    assert 'Start-Process -FilePath netsh' in ps
    assert '-Verb RunAs' in ps
    assert "'localport=8080'" in ps
    assert "'name=" + fw.RULE_NAME + "'" in ps
