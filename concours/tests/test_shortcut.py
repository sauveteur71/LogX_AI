# -*- coding: utf-8 -*-
"""Tests unitaires de logx_shortcut (logique d'état de la bannière "Créer un
raccourci sur le bureau ?", premier lancement de l'exécutable figé).
logx_bootstrap.is_frozen()/user_data_dir() sont monkeypatchés — ces tests ne
lancent jamais de vrai exécutable PyInstaller ni de vrai PowerShell (voir
tests/test_winshell.py pour le parsing PowerShell, et
tests/test_shortcut_http.py pour le câblage HTTP)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_shortcut as shortcut
import logx_winshell as winshell


def test_should_offer_false_en_mode_developpement(tmp_path, monkeypatch):
    """Coeur de la demande : is_frozen()==False (mode dev) → jamais de
    bannière, même si aucun marqueur n'existe encore."""
    monkeypatch.setattr(shortcut, 'is_frozen', lambda: False)
    monkeypatch.setattr(shortcut, 'user_data_dir', lambda: str(tmp_path))
    assert shortcut.should_offer() is False


def test_should_offer_true_en_frozen_sans_marqueur(tmp_path, monkeypatch):
    monkeypatch.setattr(shortcut, 'is_frozen', lambda: True)
    monkeypatch.setattr(shortcut, 'user_data_dir', lambda: str(tmp_path))
    assert shortcut.should_offer() is True


def test_should_offer_false_en_frozen_si_marqueur_present(tmp_path, monkeypatch):
    monkeypatch.setattr(shortcut, 'is_frozen', lambda: True)
    monkeypatch.setattr(shortcut, 'user_data_dir', lambda: str(tmp_path))
    (tmp_path / shortcut.MARKER_NAME).write_text('1', encoding='utf-8')
    assert shortcut.should_offer() is False


def test_mark_offered_cree_le_fichier_marqueur(tmp_path, monkeypatch):
    monkeypatch.setattr(shortcut, 'user_data_dir', lambda: str(tmp_path))
    assert not (tmp_path / shortcut.MARKER_NAME).exists()
    shortcut.mark_offered()
    assert (tmp_path / shortcut.MARKER_NAME).exists()


def test_mark_offered_ne_leve_pas_si_dossier_illisible(monkeypatch):
    """Un dossier de données inaccessible (permissions, disque plein...) ne
    doit jamais faire planter le clic Oui/Non de l'utilisateur."""
    monkeypatch.setattr(shortcut, 'user_data_dir', lambda: 'Z:\\introuvable\\vraiment')
    shortcut.mark_offered()  # ne lève pas


def test_should_offer_repli_false_si_user_data_dir_leve(monkeypatch):
    """Symétrique : une erreur côté lecture (pas seulement écriture) doit
    dégrader vers "ne pas proposer", jamais planter le chargement de la page."""
    def _boom():
        raise OSError('disque inaccessible')
    monkeypatch.setattr(shortcut, 'is_frozen', lambda: True)
    monkeypatch.setattr(shortcut, 'user_data_dir', _boom)
    assert shortcut.should_offer() is False


def test_create_and_mark_delegue_a_winshell_avec_sys_executable(tmp_path, monkeypatch):
    """create_and_mark() doit passer sys.executable (l'exe en cours
    d'exécution lui-même) — jamais un chemin codé en dur — à
    logx_winshell.create_desktop_shortcut."""
    monkeypatch.setattr(shortcut, 'user_data_dir', lambda: str(tmp_path))
    captured = {}

    def fake_create(target, name='', description=''):
        captured['target'] = target
        captured['name'] = name
        captured['description'] = description
        return {'ok': True, 'path': 'C:\\Users\\test\\Desktop\\LogX AI.lnk'}
    monkeypatch.setattr(winshell, 'create_desktop_shortcut', fake_create)

    res = shortcut.create_and_mark()
    assert res['ok'] is True
    assert captured['target'] == sys.executable
    assert captured['name'] == shortcut.SHORTCUT_NAME
    assert captured['description'] == shortcut.SHORTCUT_DESCRIPTION


def test_create_and_mark_pose_le_marqueur_meme_en_cas_dechec(tmp_path, monkeypatch):
    """Piège explicitement visé par la demande : un échec de création (ex.
    PowerShell cassé) ne doit PAS faire reproposer la bannière indéfiniment —
    le marqueur est posé quel que soit le résultat."""
    monkeypatch.setattr(shortcut, 'user_data_dir', lambda: str(tmp_path))
    monkeypatch.setattr(winshell, 'create_desktop_shortcut',
                         lambda target, name='', description='': {'ok': False, 'error': 'boom'})

    res = shortcut.create_and_mark()
    assert res['ok'] is False
    assert (tmp_path / shortcut.MARKER_NAME).exists()


def test_create_and_mark_pose_le_marqueur_meme_si_winshell_leve(tmp_path, monkeypatch):
    monkeypatch.setattr(shortcut, 'user_data_dir', lambda: str(tmp_path))
    def _boom(target, name='', description=''):
        raise RuntimeError('powershell introuvable')
    monkeypatch.setattr(winshell, 'create_desktop_shortcut', _boom)

    res = shortcut.create_and_mark()
    assert res['ok'] is False
    assert (tmp_path / shortcut.MARKER_NAME).exists()
