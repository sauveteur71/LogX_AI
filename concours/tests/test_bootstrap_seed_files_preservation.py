# -*- coding: utf-8 -*-
"""Garantie « mise à jour ne doit jamais écraser une personnalisation
utilisateur » (analyse concurrentielle 10/08/2026, recommandation P1 inspirée
du pattern Log4OM « rapports protégés » + sauvegarde/restauration auto).

logx_bootstrap.bootstrap() recopie au 1er lancement (mode figé PyInstaller)
les fichiers de référence embarqués dans le bundle vers le dossier
inscriptible de l'utilisateur (_SEED_FILES, dont custom_contests.json — les
concours personnalisés de l'opérateur). Le point crucial : cette copie ne
doit JAMAIS se reproduire si le fichier existe déjà côté utilisateur, sinon
une mise à jour qui embarque une nouvelle version de référence écraserait
silencieusement les personnalisations (concours perso, barèmes...) à chaque
nouveau lancement après mise à jour.

Ce test verrouille ce comportement — sans lui, rien ne l'aurait fait
échouer si le garde `if not os.path.exists(dst)` avait un jour été
simplifié/retiré par erreur."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_bootstrap as boot


def _prepare(tmp_path, monkeypatch):
    """Bundle (resource_dir) et dossier utilisateur (user_data_dir) isolés
    dans tmp_path, mode figé simulé — reproduit la disposition réelle en
    exécutable PyInstaller sans toucher au vrai APPDATA de la machine."""
    res = tmp_path / 'bundle'
    data = tmp_path / 'userdata'
    res.mkdir()
    data.mkdir()
    monkeypatch.setattr(boot, 'is_frozen', lambda: True)
    monkeypatch.setattr(boot, 'resource_dir', lambda: str(res))
    monkeypatch.setattr(boot, 'user_data_dir', lambda: str(data))
    monkeypatch.chdir(tmp_path)  # bootstrap() fait os.chdir(data) -- repartir d'un cwd neutre
    return res, data


def test_premier_lancement_copie_les_fichiers_de_reference(tmp_path, monkeypatch):
    res, data = _prepare(tmp_path, monkeypatch)
    (res / 'custom_contests.json').write_text('{"contests": {}}', encoding='utf-8')

    boot.bootstrap()

    assert (data / 'custom_contests.json').exists()
    assert json.loads((data / 'custom_contests.json').read_text(encoding='utf-8')) == {'contests': {}}


def test_mise_a_jour_necrase_jamais_un_concours_personnalise_existant(tmp_path, monkeypatch):
    """Le cas central : l'utilisateur a déjà un custom_contests.json à lui
    (créé via l'UI) quand une mise à jour arrive avec une NOUVELLE version
    du fichier de référence dans le bundle -- bootstrap() ne doit RIEN
    recopier par-dessus."""
    res, data = _prepare(tmp_path, monkeypatch)
    perso = {'contests': {'MON_CONCOURS_PERSO': {'label': 'Mon rallye local'}}}
    (data / 'custom_contests.json').write_text(json.dumps(perso), encoding='utf-8')
    # La "nouvelle" release embarque un fichier de référence différent
    (res / 'custom_contests.json').write_text('{"contests": {"AUTRE": {}}}', encoding='utf-8')

    boot.bootstrap()

    assert json.loads((data / 'custom_contests.json').read_text(encoding='utf-8')) == perso, \
        "un concours personnalisé existant ne doit jamais être écrasé par le fichier embarqué d'une mise à jour"


def test_tous_les_seed_files_beneficient_de_la_meme_garantie():
    """Pas seulement custom_contests.json -- vérifie que le garde
    `if not os.path.exists(dst)` s'applique à toute la liste _SEED_FILES,
    pas à un sous-ensemble oublié lors d'un futur ajout à cette liste."""
    with open(boot.__file__, encoding='utf-8') as f:
        src = f.read()
    deb = src.index('def bootstrap()')
    fin = src.index('\n\n\n', deb)
    corps = src[deb:fin]
    assert 'for name in _SEED_FILES' in corps, \
        "la boucle de copie doit couvrir toute la liste _SEED_FILES, pas un fichier codé en dur"
    assert 'if not os.path.exists(dst)' in corps, \
        "le garde anti-écrasement doit rester présent -- c'est lui qui protège les personnalisations utilisateur"


def test_mode_developpement_ne_touche_a_rien():
    """En mode dev (python logx_serveur.py, pas de bundle figé), bootstrap()
    ne doit faire AUCUNE copie ni changement de dossier -- custom_contests.json
    reste le fichier du dépôt de travail tel quel (jamais suivi par git,
    donc jamais menacé par un git pull/merge non plus)."""
    assert boot.is_frozen() is False, \
        "ce test tourne sous pytest normal (jamais PyInstaller) -- is_frozen() doit rester False ici"
    cwd_avant = os.getcwd()
    result = boot.bootstrap()
    assert result == cwd_avant
    assert os.getcwd() == cwd_avant
