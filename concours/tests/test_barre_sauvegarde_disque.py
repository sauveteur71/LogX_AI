# -*- coding: utf-8 -*-
"""La barre de statut doit montrer la sauvegarde DISQUE, pas la copie navigateur.

L'indicateur « Sauvegarde » affichait en priorité `rc_log_backup_time`, une
copie faite par la page LOGBOOK qui vit dans le cache du navigateur et part
avec lui. Un opérateur y lisait « sauvegardé » alors que rien n'existait hors
du navigateur — le malentendu qui a accompagné la perte du 19/08/2026.

Depuis, une sauvegarde disque existe TOUJOURS. C'est elle qu'il faut montrer.

🚨 PROPRIÉTÉ LA PLUS IMPORTANTE DE CE BANC : `derniere_sauvegarde()` ne doit
faire AUCUNE I/O sur le dossier de sauvegarde. Elle alimente `/log/status`,
que les 15 pages interrogent toutes les 20 s ; or ce dossier PEUT être un
partage réseau, et `os.path.isdir` sur un SMB injoignable bloque ~21 s
(mesuré, voir STATUS_SCAN_TIMEOUT dans logx_cloudsync.py). Y glisser une I/O
réseau gèlerait des threads serveur en continu. C'est exactement pourquoi
cette fonction est SÉPARÉE de status(), qui, lui, fait un glob.
"""
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_backup as bk          # noqa: E402

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _poser_horodateur(dossier, valeur):
    with io.open(os.path.join(dossier, bk._STAMP), 'w', encoding='utf-8') as f:
        json.dump({'last': valeur, 'folder': '/peu/importe', 'files': []}, f)


# ── 1. Elle lit bien l'horodateur ─────────────────────────────────────────
def test_rend_l_horodatage_de_la_derniere_sauvegarde(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _poser_horodateur(str(tmp_path), '2026-08-19 16:44')
    assert bk.derniere_sauvegarde() == '2026-08-19 16:44'


def test_rend_vide_quand_rien_n_a_encore_ete_sauvegarde(tmp_path, monkeypatch):
    """Cas réel : le premier quart d'heure après un démarrage."""
    monkeypatch.chdir(tmp_path)
    assert bk.derniere_sauvegarde() == ''


def test_ne_leve_jamais_sur_un_horodateur_illisible(tmp_path, monkeypatch):
    """Un fichier tronqué par une coupure ne doit pas casser /log/status."""
    monkeypatch.chdir(tmp_path)
    io.open(os.path.join(str(tmp_path), bk._STAMP), 'w',
            encoding='utf-8').write('{ ceci n est pas du JSON')
    assert bk.derniere_sauvegarde() == ''

    io.open(os.path.join(str(tmp_path), bk._STAMP), 'w',
            encoding='utf-8').write('null')
    assert bk.derniere_sauvegarde() == ''


# ── 2. 🚨 Aucune I/O sur le dossier de sauvegarde ─────────────────────────
def test_ne_touche_jamais_au_dossier_de_sauvegarde(tmp_path, monkeypatch):
    """Propriété de comportement : on SABOTE toute I/O de dossier.

    Si `derniere_sauvegarde()` appelait `glob` ou `os.path.isdir` — ce que
    fait `status()` — ce test lèverait. C'est la garantie qu'un dossier de
    sauvegarde sur NAS injoignable ne peut pas geler /log/status."""
    monkeypatch.chdir(tmp_path)
    _poser_horodateur(str(tmp_path), '2026-08-19 16:44')

    def interdit(*a, **k):
        raise AssertionError(
            'I/O sur le dossier de sauvegarde depuis derniere_sauvegarde() : '
            'sur un partage réseau injoignable, cela gèlerait un thread '
            'serveur à chaque interrogation de /log/status')

    monkeypatch.setattr(bk.glob, 'glob', interdit)
    monkeypatch.setattr(bk.os.path, 'isdir', interdit)

    assert bk.derniere_sauvegarde() == '2026-08-19 16:44'


def test_status_lui_fait_bien_du_glob(tmp_path, monkeypatch):
    """Contre-épreuve du test précédent : il ne serait pas concluant si
    PERSONNE ne faisait de glob. status() en fait, et c'est pour ça que les
    deux fonctions sont séparées."""
    monkeypatch.chdir(tmp_path)
    vu = []
    vrai_glob = bk.glob.glob
    monkeypatch.setattr(bk.glob, 'glob',
                        lambda *a, **k: (vu.append(a), vrai_glob(*a, **k))[1])
    bk.status({'backup_folder': str(tmp_path)})
    assert vu, 'status() ne fait plus de glob — les deux fonctions ont ' \
               'convergé, le test de non-I/O ne prouve donc plus rien'


# ── 3. La valeur est bien exposée par /log/status ─────────────────────────
def test_log_status_expose_la_sauvegarde():
    """Assertion de STRUCTURE sur le handler, pas une recherche de mot."""
    src = io.open(os.path.join(RACINE, 'logx_http.py'), encoding='utf-8').read()
    debut = src.index("if path == '/log/status':")
    # Le corps s'arrête au `return` du handler — borner sur un nombre de
    # caractères tronquait la ligne cherchée (constaté en écrivant ce test).
    corps = src[debut:src.index('return', src.index("'persistance':", debut))]

    assert "'sauvegarde':" in corps, \
        '/log/status n\'expose plus l\'horodatage de sauvegarde'
    assert 'derniere_sauvegarde()' in corps, \
        'la valeur ne vient plus de logx_backup.derniere_sauvegarde()'
    # 🚨 status() fait un glob sur le dossier de sauvegarde : l'appeler ici
    # exposerait /log/status — sondé toutes les 20 s par 15 pages — au gel
    # d'un partage réseau injoignable.
    ligne = [ln for ln in corps.split('\n') if "'sauvegarde':" in ln][0]
    assert 'status(' not in ligne, (
        f'/log/status appelle status(), qui fait un glob : {ligne.strip()}')


# ── 4. La barre affiche le DISQUE en priorité ─────────────────────────────
def test_la_barre_prefere_le_disque_au_navigateur():
    """Ordre des branches, pas simple présence : c'est l'ORDRE qui porte la
    propriété. Une version qui contiendrait les deux lignes dans le mauvais
    sens afficherait encore la copie navigateur."""
    js = io.open(os.path.join(RACINE, 'logx_statusbar.js'),
                 encoding='utf-8').read()
    debut = js.index('function refreshSave()')
    # Borné sur la FIN de la fonction (le 'jamais' de dernier repli), pas sur
    # un nombre de caractères : une fenêtre fixe se retrouve trop courte dès
    # qu'on ajoute un commentaire, et le test échoue pour rien.
    corps = js[debut:js.index("'jamais'", debut)]
    # On retire les commentaires : un commentaire qui EXPLIQUE la priorité
    # satisferait une recherche naïve.
    code = '\n'.join(ligne for ligne in corps.split('\n')
                     if not ligne.strip().startswith('//'))
    # On compare les BRANCHES, pas les mentions : `logBackup` est DÉCLARÉ en
    # tête de fonction, donc une comparaison sur la première occurrence du
    # nom conclurait toujours à tort (constaté en écrivant ce test).
    i_disque = code.find('if (_sauvegardeDisque)')
    i_navig = code.find('if (logBackup)')
    assert i_disque != -1, 'la barre ne teste plus la sauvegarde disque'
    assert i_navig != -1, 'la branche de repli navigateur a disparu'
    assert i_disque < i_navig, (
        'la copie navigateur est testée AVANT la sauvegarde disque : '
        'l\'opérateur verra « navigateur » alors qu\'une vraie sauvegarde '
        'existe')


def test_la_barre_alimente_le_disque_depuis_log_status():
    js = io.open(os.path.join(RACINE, 'logx_statusbar.js'),
                 encoding='utf-8').read()
    debut = js.index('function refreshPersistance()')
    corps = js[debut:debut + 900]
    assert 'd.sauvegarde' in corps, \
        'refreshPersistance ne lit plus le champ sauvegarde de /log/status'
    assert '_sauvegardeDisque' in corps
    assert 'refreshSave()' in corps, \
        'la barre n\'est pas rafraîchie après réception de l\'horodatage'
