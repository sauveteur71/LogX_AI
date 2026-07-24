# -*- coding: utf-8 -*-
"""Proposition d'un raccourci bureau au premier lancement de l'exécutable figé.

LogX AI se distribue sans installeur classique — un .exe à double-cliquer
(voir INSTALL.md). « Lors de l'installation » correspond donc en pratique au
PREMIER LANCEMENT de cet exécutable figé (PyInstaller, logx_bootstrap.is_frozen()).
Ce module ne fait QUE la logique d'état (faut-il proposer ? a-t-on déjà
répondu ?) ; la création réelle du raccourci Windows (invocation PowerShell)
vit dans logx_winshell.py — voir sa docstring, réutilisable pour tout futur
dialogue/action native.

Marqueur : un fichier vide « .shortcut_offered » dans le dossier de données
utilisateur (logx_bootstrap.user_data_dir(), %APPDATA%\\LogXAI sous Windows).
Son absence = jamais proposé. Il est posé dès que l'utilisateur a répondu —
OUI ou NON — pour ne JAMAIS reproposer la bannière ensuite, y compris si la
création du raccourci a échoué (sinon la bannière réapparaîtrait à chaque
lancement pour un opérateur qui a déjà dit non, ou dont PowerShell est cassé).

Ne se déclenche QUE si is_frozen() est vrai : en mode développement
(python logx_serveur.py), should_offer() renvoie toujours False — il n'y a
pas d'exécutable figé à raccourcir, et sys.executable pointerait vers
l'interpréteur Python lui-même.
"""
import os

from logx_bootstrap import is_frozen, user_data_dir

MARKER_NAME = '.shortcut_offered'

SHORTCUT_NAME = 'LogX AI'
SHORTCUT_DESCRIPTION = 'LogX AI — logiciel de log radioamateur'


def _marker_path():
    return os.path.join(user_data_dir(), MARKER_NAME)


def should_offer():
    """True seulement en exécutable figé ET si la bannière n'a encore jamais
    reçu de réponse (marqueur absent). Ne lève jamais d'exception : une
    erreur d'accès disque au dossier de données doit dégrader vers "ne pas
    proposer", pas planter la page principale au chargement."""
    if not is_frozen():
        return False
    try:
        return not os.path.exists(_marker_path())
    except Exception:
        return False


def mark_offered():
    """Pose le marqueur — quelle que soit la réponse de l'utilisateur (OUI ou
    NON), ou même en cas d'échec de création du raccourci : dans tous les cas,
    la question a été posée une fois, elle ne doit plus jamais l'être."""
    try:
        with open(_marker_path(), 'w', encoding='utf-8') as f:
            f.write('1')
    except Exception:
        pass  # tant pis : au pire la bannière réapparaîtra une fois de plus


def create_and_mark():
    """Crée le raccourci bureau (délègue à logx_winshell, Windows uniquement
    pour l'instant) PUIS pose systématiquement le marqueur — succès ou échec,
    voir mark_offered(). Renvoie le résultat de logx_winshell.create_desktop_shortcut
    (ou une erreur explicite si le module ne peut pas être importé)."""
    import sys
    try:
        import logx_winshell as winshell
        res = winshell.create_desktop_shortcut(
            target=sys.executable,
            name=SHORTCUT_NAME,
            description=SHORTCUT_DESCRIPTION,
        )
    except Exception as e:
        res = {'ok': False, 'error': str(e)}
    mark_offered()
    return res
