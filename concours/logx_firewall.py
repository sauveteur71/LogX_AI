# -*- coding: utf-8 -*-
"""Ouverture du port multi-poste dans le pare-feu Windows — pour que le LAN
« marche tout seul », sans que l'opérateur bricole les réglages Windows.

Le problème (vécu, 30/08/2026) : même quand le serveur écoute sur 0.0.0.0 (accès
LAN activé), un 2e poste ne peut PAS se connecter si le réseau Wi-Fi est classé
« Public » — le pare-feu Windows bloque alors les connexions entrantes vers
Python (les règles Python autorisées ne valent que pour le profil « Privé »).

La parade : une règle entrante ciblée (TCP, le port, TOUS profils) ajoutée UNE
fois pour toutes. Ajouter une règle exige l'élévation (admin) :
  - au démarrage (LAN activé) on TENTE en best-effort (silencieux si refusé) ;
  - la page CONFIG offre un bouton qui relance la commande AVEC élévation (UAC),
    pour un correctif permanent en un clic.
Nom de règle SANS espace : évite tout problème de quoting quand netsh est relancé
via PowerShell Start-Process.
"""
import subprocess
import sys

RULE_NAME = 'LogX_AI_multiposte'


def is_windows():
    return sys.platform.startswith('win')


def _add_argv(port):
    """Arguments netsh pour AJOUTER la règle entrante (sans le mot 'netsh')."""
    return ['advfirewall', 'firewall', 'add', 'rule', 'name=' + RULE_NAME,
            'dir=in', 'action=allow', 'protocol=TCP', 'localport=%d' % int(port)]


def _show_argv():
    return ['advfirewall', 'firewall', 'show', 'rule', 'name=' + RULE_NAME]


def rule_exists(port):
    """La règle d'ouverture du port existe-t-elle déjà ? (lecture, sans admin).
    netsh show renvoie un code non nul et « No rules match » si absente."""
    if not is_windows():
        return False
    try:
        r = subprocess.run(['netsh'] + _show_argv(), capture_output=True, text=True, timeout=10)
    except Exception:
        return False
    return r.returncode == 0 and ('localport' in r.stdout.lower()) and (str(int(port)) in r.stdout)


def add_rule(port):
    """Ajoute la règle en best-effort (SANS élévation). Retourne (ok, message).
    Échoue proprement (« accès refusé ») si le process n'est pas admin."""
    if not is_windows():
        return (False, 'non-Windows')
    try:
        r = subprocess.run(['netsh'] + _add_argv(port), capture_output=True, text=True, timeout=15)
        return (r.returncode == 0, (r.stdout + r.stderr).strip()[:200])
    except Exception as e:  # noqa: BLE001
        return (False, str(e))


def _elevate_powershell(argv):
    """Commande PowerShell qui relance `netsh <argv>` AVEC élévation (UAC).
    Pur (testable) : aucun argument ne contient d'espace, le quoting est simple."""
    arglist = ','.join("'%s'" % a for a in argv)
    return ("Start-Process -FilePath netsh -Verb RunAs -WindowStyle Hidden "
            "-ArgumentList %s" % arglist)


def add_rule_elevated(port):
    """Ajoute la règle AVEC élévation : ouvre une fenêtre UAC que l'opérateur
    confirme. Retourne (lancé, message). Ne bloque pas : on ne connaît pas l'issue
    de l'UAC ici — l'appelant re-vérifiera rule_exists() ensuite."""
    if not is_windows():
        return (False, 'non-Windows')
    ps = _elevate_powershell(_add_argv(port))
    try:
        subprocess.Popen(['powershell', '-NoProfile', '-NonInteractive', '-Command', ps])
        return (True, 'Fenêtre Windows (UAC) ouverte — confirme pour autoriser le port.')
    except Exception as e:  # noqa: BLE001
        return (False, str(e))


def ensure_at_startup(port):
    """Au démarrage quand l'accès LAN est activé : si la règle manque, tente de
    l'ajouter en best-effort. Silencieux si refusé (pas d'admin) — la CONFIG
    proposera alors le bouton élévé. Ne lève jamais."""
    try:
        if not is_windows() or rule_exists(port):
            return
        ok, _ = add_rule(port)
        if ok:
            print('[FIREWALL] port %d ouvert pour le multi-poste (regle %s)' % (int(port), RULE_NAME))
    except Exception:  # noqa: BLE001
        pass
