# -*- coding: utf-8 -*-
"""Auto-lancement de logiciels tiers au démarrage (WSJT-X, N1MM, un
décodeur, tout exécutable que l'opérateur veut voir prêt en même temps que
LogX) — configuré en CONFIG (`autostart_programs`), lancé UNE fois au
démarrage du serveur (logx_serveur.py), en tâche de fond et jamais
bloquant : un exécutable manquant ou lent à scanner par l'antivirus ne doit
jamais retarder l'ouverture de LogX lui-même.

« skip si déjà lancés » : un contrôle LÉGER (tasklist sous Windows, pgrep
ailleurs) évite de dupliquer un programme que l'opérateur a déjà ouvert à la
main avant de lancer LogX — pas un verrou, juste une vérification au meilleur
effort. Un contrôle qui échoue (commande absente, erreur quelconque) laisse
passer le lancement plutôt que de bloquer silencieusement : mieux vaut un
doublon exceptionnel qu'un programme jamais lancé sans qu'on sache pourquoi.
"""
import os
import platform
import shlex
import subprocess


def _deja_lance_windows(nom_exe):
    try:
        out = subprocess.run(
            ['tasklist', '/FI', f'IMAGENAME eq {nom_exe}', '/NH'],
            capture_output=True, text=True, timeout=5)
        return nom_exe.lower() in out.stdout.lower()
    except Exception:
        return False


def _deja_lance_unix(nom_exe):
    try:
        out = subprocess.run(['pgrep', '-f', nom_exe], capture_output=True,
                             text=True, timeout=5)
        return out.returncode == 0
    except Exception:
        return False


def deja_lance(chemin):
    nom = os.path.basename(str(chemin or '').strip())
    if not nom:
        return False
    if platform.system() == 'Windows':
        return _deja_lance_windows(nom)
    return _deja_lance_unix(nom)


def _chemin_local_valide(chemin, exists_fn):
    """`chemin` doit désigner un exécutable DÉJÀ présent sur cette machine.

    `autostart_programs` arrive tel quel depuis POST /config/save, qui
    n'accepte QUE le cookie rc_token comme protection — distribué
    automatiquement à tout appareil du LAN tant qu'aucun mot de passe d'accès
    n'est configuré (comportement par défaut, voir la section « SÉCURITÉ
    D'ACCÈS » de CONFIG). Sans ce garde-fou, un chemin UNC ou pointant vers un
    exécutable non présent transformerait ce mécanisme d'auto-lancement en
    exécution de code arbitraire au prochain démarrage du serveur — corrigé
    ici en refusant tout chemin qui n'est pas un fichier LOCAL déjà sur le
    disque : LogX AI ne peut plus que relancer un programme déjà installé,
    jamais en atteindre un via le réseau."""
    if chemin.startswith('\\\\') or chemin.startswith('//'):
        return False   # chemin UNC : jamais autorisé, quoi qu'il désigne
    return exists_fn(chemin)


def lancer(entree, deja_lance_fn=None, popen=None, exists_fn=None):
    """Un seul programme. `entree` : {'path', 'args', 'name', 'enabled'}.
    `deja_lance_fn`/`popen`/`exists_fn` injectables pour les tests (jamais de
    vrai process lancé pendant la suite pytest)."""
    chemin = str((entree or {}).get('path', '')).strip()
    if not chemin:
        return {'ok': False, 'error': 'Chemin vide'}
    exists = exists_fn or os.path.isfile
    if not _chemin_local_valide(chemin, exists):
        return {'ok': False, 'error':
                 'Chemin invalide ou introuvable sur cette machine (protection anti-execution-a-distance)'}
    check = deja_lance_fn or deja_lance
    if check(chemin):
        return {'ok': True, 'skipped': True}
    args_raw = (entree or {}).get('args', '')
    args = shlex.split(args_raw) if isinstance(args_raw, str) else list(args_raw or [])
    launcher = popen or subprocess.Popen
    try:
        # CREATE_NO_WINDOW (Windows) : un exécutable console (ex. un script
        # de décodage) ne doit pas ouvrir une fenêtre noire supplémentaire —
        # sans effet ailleurs (l'attribut n'existe pas hors Windows).
        kwargs = {}
        if platform.system() == 'Windows':
            kwargs['creationflags'] = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
        launcher([chemin] + args, **kwargs)
        return {'ok': True, 'skipped': False}
    except Exception as e:
        return {'ok': False, 'error': str(e)}


def lancer_tous(cfg, deja_lance_fn=None, popen=None, exists_fn=None):
    """Appelée UNE fois au démarrage — jamais d'exception vers l'appelant
    (chaque échec individuel est journalisé, pas remonté)."""
    entrees = (cfg or {}).get('autostart_programs') or []
    resultats = []
    for e in entrees:
        if not isinstance(e, dict) or e.get('enabled') is False:
            continue
        try:
            r = lancer(e, deja_lance_fn=deja_lance_fn, popen=popen, exists_fn=exists_fn)
        except Exception as ex:
            r = {'ok': False, 'error': str(ex)}
        r['name'] = e.get('name') or os.path.basename(str(e.get('path', '')))
        resultats.append(r)
        if r.get('skipped'):
            print(f"[AUTOSTART] {r['name']} : déjà lancé, ignoré")
        elif r['ok']:
            print(f"[AUTOSTART] {r['name']} : lancé")
        else:
            print(f"[AUTOSTART] {r['name']} : échec — {r.get('error', '?')}")
    return resultats
