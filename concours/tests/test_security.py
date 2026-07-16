# -*- coding: utf-8 -*-
"""Tests de sécurité du serveur HTTP — traversée de répertoire (_resolve)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from radiocontest_http import Handler


def resolve(path):
    # _resolve n'utilise que des attributs de classe : on passe la classe
    # elle-même comme self, sans instancier de connexion HTTP.
    return Handler._resolve(Handler, path)


def test_traversal_parent_rejete():
    """GET /../config.json ne doit JAMAIS sortir du dossier servi."""
    assert resolve('/../config.json') is None


def test_traversal_profond_rejete():
    assert resolve('/../../../../Windows/win.ini') is None
    assert resolve('/..\\..\\Windows\\win.ini') is None


def test_traversal_encode_rejete():
    """Variante encodée %2e%2e%2f (unquote appliqué avant résolution)."""
    assert resolve('/%2e%2e/config.json') is None
    assert resolve('/%2e%2e%2f%2e%2e%2fWindows/win.ini') is None


def test_fichier_cle_api_jamais_servi():
    """La clé API vit dans le dossier servi : liste noire obligatoire."""
    assert resolve('/clef API.txt') is None
    assert resolve('/clef%20API.txt') is None


def test_fichier_legitime_servi():
    p = resolve('/radiocontest_logbook.html')
    assert p is not None and p.endswith('radiocontest_logbook.html')


def test_json_legitime_servi():
    assert resolve('/contest_schema.json') is not None
