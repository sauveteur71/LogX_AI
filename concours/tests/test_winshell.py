# -*- coding: utf-8 -*-
"""Tests unitaires de logx_winshell.pick_folder (dialogue natif Windows via
PowerShell, invoqué par POST /backup/pick_folder). subprocess.run est
monkeypatché : ces tests couvrent le PARSING de la sortie PowerShell et le
repli hors Windows, pas le dialogue réel (impossible à automatiser en CI,
et non souhaitable — voir tests/test_backup_pick_folder_http.py pour le
câblage HTTP)."""
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_winshell as winshell


class _FakeCompletedProcess:
    def __init__(self, stdout='', stderr=''):
        self.stdout = stdout
        self.stderr = stderr


def test_hors_windows_repli_sans_invoquer_powershell(monkeypatch):
    """macOS/Linux : message clair, aucun subprocess lancé (pas de crash en
    tentant d'invoquer powershell.exe absent)."""
    monkeypatch.setattr(sys, 'platform', 'linux')

    def _boom(*a, **k):
        raise AssertionError('subprocess.run ne doit pas être appelé hors Windows')
    monkeypatch.setattr(winshell.subprocess, 'run', _boom)

    res = winshell.pick_folder()
    assert res['ok'] is False
    assert res['error'] == 'plateforme non supportee'
    assert 'Windows' in res['message']
    assert 'manuellement' in res['message']


def test_dossier_choisi_est_parse_depuis_stdout(monkeypatch):
    monkeypatch.setattr(sys, 'platform', 'win32')
    monkeypatch.setattr(winshell.subprocess, 'run',
                         lambda *a, **k: _FakeCompletedProcess(
                             stdout='LOGXAI_PICKED:C:\\Users\\test\\logs\r\n'))

    res = winshell.pick_folder()
    assert res == {'ok': True, 'path': 'C:\\Users\\test\\logs'}


def test_annulation_utilisateur_nest_pas_une_erreur_bloquante(monkeypatch):
    monkeypatch.setattr(sys, 'platform', 'win32')
    monkeypatch.setattr(winshell.subprocess, 'run',
                         lambda *a, **k: _FakeCompletedProcess(stdout='LOGXAI_CANCELLED\r\n'))

    res = winshell.pick_folder()
    assert res == {'ok': False, 'error': 'annule'}


def test_delai_depasse_remonte_une_erreur_dediee(monkeypatch):
    monkeypatch.setattr(sys, 'platform', 'win32')

    def _raise_timeout(*a, **k):
        raise subprocess.TimeoutExpired(cmd='powershell', timeout=winshell.TIMEOUT_S)
    monkeypatch.setattr(winshell.subprocess, 'run', _raise_timeout)

    res = winshell.pick_folder()
    assert res['ok'] is False
    assert 'delai' in res['error']


def test_echec_powershell_avant_dialogue_remonte_stderr(monkeypatch):
    """Ni LOGXAI_PICKED ni LOGXAI_CANCELLED sur stdout (ex. assembly
    introuvable, politique d'exécution) : le message d'erreur vient de
    stderr plutôt que d'un message générique muet."""
    monkeypatch.setattr(sys, 'platform', 'win32')
    monkeypatch.setattr(winshell.subprocess, 'run',
                         lambda *a, **k: _FakeCompletedProcess(
                             stdout='', stderr='Erreur PowerShell : assembly introuvable'))

    res = winshell.pick_folder()
    assert res == {'ok': False, 'error': 'Erreur PowerShell : assembly introuvable'}


def test_exception_a_linvocation_ne_remonte_pas(monkeypatch):
    """subprocess.run peut lever autre chose qu'un TimeoutExpired (ex.
    FileNotFoundError si powershell.exe est introuvable) : pick_folder ne
    doit jamais laisser fuiter une exception (voir contrat de la docstring)."""
    monkeypatch.setattr(sys, 'platform', 'win32')

    def _raise(*a, **k):
        raise FileNotFoundError('powershell.exe introuvable')
    monkeypatch.setattr(winshell.subprocess, 'run', _raise)

    res = winshell.pick_folder()
    assert res['ok'] is False and 'introuvable' in res['error']


def test_ps_quote_echappe_les_apostrophes():
    """Seul caractère à doubler dans un littéral PowerShell entre guillemets
    simples — sans ce doublage, un titre ou un chemin contenant une
    apostrophe casserait le script (fin de chaîne prématurée)."""
    assert winshell._ps_quote("dossier d'un utilisateur") == "'dossier d''un utilisateur'"
    assert winshell._ps_quote('') == "''"
    assert winshell._ps_quote(None) == "''"


def test_script_powershell_embarque_le_dossier_initial_quand_fourni():
    script = winshell._build_pick_folder_script('Choisir', 'C:\\logs')
    assert "$init = 'C:\\logs'" in script
    assert 'ShowNewFolderButton = $true' in script
    assert 'FolderBrowserDialog' in script
