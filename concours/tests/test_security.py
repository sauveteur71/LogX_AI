# -*- coding: utf-8 -*-
"""Tests de sécurité du serveur HTTP — traversée de répertoire (_resolve)."""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from logx_http import Handler


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
    p = resolve('/logx_logbook.html')
    assert p is not None and p.endswith('logx_logbook.html')


def test_json_legitime_servi():
    assert resolve('/contest_schema.json') is not None


# ── Contournement de la liste noire par écriture équivalente du chemin ───────
# La liste noire filtrait os.path.basename() de l'URL BRUTE alors que le
# confinement anti-traversée, lui, travaillait sur realpath(). Un simple slash
# final vidait le basename ('.auth_token/' -> '') : le filtre laissait passer,
# puis realpath() ramenait sur le vrai secret. GET /.auth_token/ livrait donc
# le jeton d'écriture à tout le LAN, sans authentification (ces routes sont
# dans do_GET, avant toute vérification), ce qui déverrouillait ensuite
# /config/save, /log/reset, /log/archive?clear…

@pytest.fixture
def dossier_leurre(tmp_path, monkeypatch):
    """Sert des LEURRES depuis un cwd temporaire.

    Indispensable : les vrais .auth_token / .server_config.json / logx.db sont
    gitignorés, donc absents d'un dépôt fraîchement cloné. Sans ces leurres le
    test passerait pour la MAUVAISE raison (fichier inexistant) au lieu de
    vérifier que la liste noire fait son travail.
    """
    for nom, contenu in [
        ('.auth_token', 'LEURRE-TOKEN'),
        ('.server_config.json', '{"api_key": "LEURRE"}'),
        ('.cloudsync_instance_id', 'LEURRE-INSTANCE'),
        ('shared_log.json', '[]'),
        ('logx.db', 'LEURRE-SQLITE'),
        ('logx.db.bak', 'LEURRE-BACKUP'),
        ('index.html', '<html>leurre</html>'),
    ]:
        (tmp_path / nom).write_text(contenu, encoding='utf-8')
    cache = tmp_path / '.git'
    cache.mkdir()
    (cache / 'config').write_text('[remote "origin"]', encoding='utf-8')
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_leurres_reellement_servis_par_defaut(dossier_leurre):
    """Garde-fou du garde-fou : si ce test échoue, les cas ci-dessous
    passeraient sans rien prouver (cwd non pris en compte par _resolve)."""
    assert (dossier_leurre / '.auth_token').is_file()
    assert resolve('/index.html') is not None


@pytest.mark.parametrize('url', [
    '/.auth_token',
    '/.auth_token/',            # basename('') — contournement historique
    '/.auth_token%2F',          # unquote() appliqué AVANT le calcul du basename
    '/x/../.auth_token/',       # segment bidon + slash final
    '/.auth_token/.',
    '/.server_config.json/',    # clé API + identifiants ON4KST/QRZ
    '/.cloudsync_instance_id/',
])
def test_secret_cache_insensible_a_l_ecriture_du_chemin(dossier_leurre, url):
    assert resolve(url) is None


@pytest.mark.parametrize('url', [
    '/shared_log.json/',
    '/logx.db/',
    '/logx.db.bak/',            # le filtre par suffixe se contournait aussi
])
def test_liste_noire_nommee_insensible_au_slash_final(dossier_leurre, url):
    assert resolve(url) is None


def test_flux_de_donnees_alternatif_ntfs_refuse(dossier_leurre):
    """'shared_log.json::$DATA' ouvre bel et bien shared_log.json sous NTFS,
    mais le nom vu par la liste noire ('shared_log.json::$data') n'y figure
    pas. Aucun fichier légitimement servi ne contient ':'."""
    assert resolve('/shared_log.json::$DATA') is None
    assert resolve('/logx.db::$DATA') is None


def test_dossier_cache_bloque_pas_seulement_son_dernier_segment(dossier_leurre):
    """Le basename de '/.git/config' est 'config' : c'est le SEGMENT de tête
    qui est caché. La règle doit porter sur tous les segments du chemin."""
    assert resolve('/.git/config') is None
    assert resolve('/.git/HEAD') is None
