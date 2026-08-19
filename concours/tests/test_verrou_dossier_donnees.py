# -*- coding: utf-8 -*-
"""Instance unique : le DOSSIER DE DONNÉES doit être verrouillé, pas seulement
le port.

logx_singleton protégeait déjà contre deux serveurs sur le MÊME PORT — sa
docstring le dit : « deux serveurs LogX AI ne doivent JAMAIS servir le même
port ». Mais ce qui fait perdre des QSO n'est pas de partager un port, c'est de
partager un DOSSIER : logx.db et shared_log.json sont des chemins RELATIFS au
répertoire de travail. Deux serveurs lancés dans le même dossier sur deux
ports DIFFÉRENTS écrivent donc dans le même carnet, chacun avec sa propre copie
en mémoire, et le premier qui sauvegarde grave son état par-dessus celui de
l'autre — sans erreur, sans trace.

Ces tests lancent de VRAIS processus. Un verrou de fichier ne se teste pas
dans un seul interpréteur : le système accorde volontiers deux verrous au même
processus, et un test mono-processus serait vert quoi qu'il arrive.

DÉFAUT TROUVÉ PAR CE TEST, avant qu'il n'existe : la première version de
verrouiller_dossier_donnees() appelait os.name sans que `os` soit importé dans
le module. Le NameError tombait dans un `except Exception: return True`, et la
fonction annonçait un verrou pris alors qu'elle n'en avait aucun. Les deux
processus démarraient. C'est exactement le motif « exception avalée » que tout
ce lot combat.
"""
import os
import subprocess
import sys

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, CONCOURS)

import logx_singleton as sg

_PRENDRE = (
    'import sys; sys.path.insert(0, r"%s"); '
    'import logx_singleton as sg; '
    'print("VERROU=%%s" %% sg.verrouiller_dossier_donnees())' % CONCOURS)

# Prend le verrou PUIS attend sur l'entrée standard : le processus reste
# vivant, donc le verrou reste tenu, tant qu'on ne ferme pas son stdin.
_TENIR = (
    'import sys; sys.path.insert(0, r"%s"); '
    'import logx_singleton as sg; '
    'print("VERROU=%%s" %% sg.verrouiller_dossier_donnees(), flush=True); '
    'sys.stdin.read()' % CONCOURS)


def _essayer(dossier):
    r = subprocess.run([sys.executable, '-c', _PRENDRE], cwd=str(dossier),
                       capture_output=True, text=True, timeout=60)
    assert 'VERROU=' in r.stdout, (r.stdout, r.stderr[-400:])
    return r.stdout.split('VERROU=')[1].strip().startswith('True')


def test_un_seul_processus_a_la_fois_dans_un_dossier(tmp_path):
    """LA propriété. Deux serveurs dans le même dossier, c'est un carnet qui
    s'efface tout seul."""
    tenant = subprocess.Popen([sys.executable, '-c', _TENIR], cwd=str(tmp_path),
                              stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                              text=True)
    try:
        premiere = tenant.stdout.readline()
        assert 'VERROU=True' in premiere, premiere
        assert not _essayer(tmp_path), (
            'un SECOND processus a obtenu le verrou du même dossier')
    finally:
        tenant.stdin.close()
        tenant.wait(timeout=30)


def test_deux_dossiers_DIFFERENTS_ne_se_genent_pas(tmp_path):
    """Le verrou porte sur le dossier, pas sur la machine : deux stations de
    travail (ou un serveur de test dans un worktree) doivent cohabiter."""
    a, b = tmp_path / 'a', tmp_path / 'b'
    a.mkdir()
    b.mkdir()
    tenant = subprocess.Popen([sys.executable, '-c', _TENIR], cwd=str(a),
                              stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                              text=True)
    try:
        assert 'VERROU=True' in tenant.stdout.readline()
        assert _essayer(b), 'un autre dossier a été bloqué à tort'
    finally:
        tenant.stdin.close()
        tenant.wait(timeout=30)


def test_un_plantage_ne_laisse_PAS_de_verrou_fantome(tmp_path):
    """C'est la raison de choisir un verrou système plutôt qu'un fichier .pid :
    le système le libère tout seul quand le processus meurt. Un .pid resté sur
    le disque après une coupure de courant empêcherait le logiciel de
    redémarrer — et vérifier qu'un pid est vivant n'est pas portable (sous
    Windows, os.kill(pid, 0) TUE le processus au lieu de le sonder)."""
    assert _essayer(tmp_path)          # ce processus-là est déjà terminé
    assert _essayer(tmp_path), (
        'le verrou du processus précédent, pourtant mort, bloque encore')


def test_la_poignee_est_CONSERVEE(tmp_path):
    """Fermer le fichier relâcherait le verrou. Le rendre à une variable
    locale suffirait à le perdre au premier passage du ramasse-miettes."""
    r = subprocess.run(
        [sys.executable, '-c',
         'import sys; sys.path.insert(0, r"%s"); import logx_singleton as sg; '
         'sg.verrouiller_dossier_donnees(); '
         'print("TENUE=%%s" %% (sg._poignee_verrou is not None))' % CONCOURS],
        cwd=str(tmp_path), capture_output=True, text=True, timeout=60)
    assert 'TENUE=True' in r.stdout, (r.stdout, r.stderr[-400:])


def test_le_message_dit_QUOI_FAIRE(tmp_path):
    """Un refus de démarrage sans explication est pire qu'un démarrage
    dangereux : l'opérateur croit le logiciel cassé."""
    msg = sg.message_dossier_verrouille(str(tmp_path))
    assert str(tmp_path) in msg, 'le dossier en cause doit être nommé'
    bas = msg.lower()
    assert 'ferme' in bas, 'le message doit dire quoi faire'
    assert 'effacer' in bas or 'efface' in bas, (
        'le message doit dire POURQUOI on refuse, sinon il passe pour un bug')


def test_le_repli_ne_ment_JAMAIS_en_silence():
    """Si le verrouillage est impossible (système de fichiers exotique), on
    démarre — mais on le DIT. C'est en avalant cette exception que la première
    version annonçait un verrou qu'elle n'avait pas pris."""
    import inspect
    src = inspect.getsource(sg.verrouiller_dossier_donnees)
    lignes = [l for l in src.split('\n') if not l.strip().startswith('#')]

    # On ne vise QUE les « return True » qui sortent d'un except, c'est-à-dire
    # ceux qui prétendent « tout va bien » après un échec. Le except qui avale
    # l'écriture du pid n'est pas concerné : à ce stade le verrou EST tenu, et
    # ne pas savoir écrire le numéro de processus ne change rien. Première
    # version du test : trop large, elle attrapait ce cas-là. Resserrée.
    # Le critère est l'INDENTATION : le « return True » de succès est au niveau
    # de la fonction (4 espaces), ceux des replis sont dans un bloc except
    # (8 espaces ou plus). Remonter à l'aveugle sur N lignes ne les distinguait
    # pas — le return de succès suivait le `except: pass` de l'écriture du pid,
    # et le test rougissait sur du code sain. Deux versions vacantes de ce test
    # avant celle-ci ; la lettre du dépôt s'applique aussi aux tests.
    controles = 0
    for i, ligne in enumerate(lignes):
        if ligne.strip() != 'return True':
            continue
        if len(ligne) - len(ligne.lstrip()) <= 4:
            continue                     # retour de succès, au niveau fonction
        bloc = []
        for j in range(i - 1, -1, -1):
            bloc.insert(0, lignes[j])
            if lignes[j].lstrip().startswith('except '):
                controles += 1
                assert any('print(' in b for b in bloc), (
                    'un repli silencieux qui rend True fait croire le dossier '
                    'protégé alors qu\'aucun verrou n\'a été pris : %r' % bloc)
                break
            if lignes[j].lstrip().startswith(('try:', 'def ')):
                break
    assert controles == 2, (
        'les deux replis « impossible de verrouiller » doivent être contrôlés, '
        '%d trouvé(s)' % controles)
