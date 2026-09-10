# -*- coding: utf-8 -*-
"""Corbeille de QSO — récupération après une suppression individuelle.

Contexte (incident du 19/08/2026, voir docs/passation/PASSATION.md) : 248 QSO
supprimés par erreur, récupérés à la main par carving SQLite (lecture des
pages libérées). Le tombstone existant (logx_storage.mark_qso_deleted) ne
retient que {'id', 'v'} — rien à restaurer, il sert uniquement à empêcher un
pair déjà synchronisé de réafficher un QSO supprimé. Ce module capture la
donnée COMPLÈTE du QSO au moment de sa suppression, pour une fenêtre de temps
bornée, dans un fichier DÉDIÉ (jamais shared_log.json ni .server_config.json —
un bug ici ne peut pas corrompre le carnet).

Rétention : 30 jours (fenêtre « corbeille récente », pas un archivage long
terme) + plafond de sécurité sur le nombre d'entrées, pour qu'une purge en
masse ne fasse pas grossir le fichier sans limite.

Toutes les fonctions ci-dessous sont PURES (entrée -> sortie, aucune I/O) —
la persistance disque (charger/enregistrer) est un mince wrapper autour, pour
rester testable sans fichier."""
import threading

FICHIER = '.corbeille.json'
RETENTION_S = 30 * 86400          # 30 jours
MAX_ENTREES = 2000                # plafond de sécurité (mass-delete)

_lock = threading.Lock()


def capturer(qsos, now):
    """Une entrée corbeille par QSO de `qsos` (liste de dicts). Un QSO sans
    'id' est ignoré (on ne pourrait jamais le restaurer sans identifiant)."""
    return [{'qso': dict(q), 'deleted_at': now}
            for q in qsos if isinstance(q, dict) and q.get('id') is not None]


def purger_perimes(entrees, now, retention_s=RETENTION_S, max_entrees=MAX_ENTREES):
    """Retire les entrées plus vieilles que la rétention, puis borne le
    nombre (garde les plus RÉCENTES en cas de dépassement)."""
    fraiches = [e for e in entrees
                if isinstance(e, dict) and (now - e.get('deleted_at', 0)) <= retention_s]
    if len(fraiches) > max_entrees:
        fraiches = sorted(fraiches, key=lambda e: e.get('deleted_at', 0))[-max_entrees:]
    return fraiches


def lister(entrees, now, retention_s=RETENTION_S):
    """Entrées valides (dans la fenêtre de rétention), les plus RÉCENTES
    d'abord — c'est l'ordre attendu par l'UI (dernier supprimé en tête)."""
    fraiches = [e for e in entrees
                if isinstance(e, dict) and (now - e.get('deleted_at', 0)) <= retention_s]
    return sorted(fraiches, key=lambda e: e.get('deleted_at', 0), reverse=True)


def restaurer(entrees, qso_id):
    """Retire l'entrée dont qso.id == qso_id (la plus récente si dupliquée —
    ne devrait pas arriver, mais un comportement déterministe vaut mieux
    qu'un choix arbitraire). Renvoie (qso_restauré_ou_None, entrees_restantes).
    N'écrase JAMAIS un id déjà repris par un QSO courant — c'est à l'appelant
    (côté serveur, qui connaît shared_log) de trancher ce conflit."""
    trouve, idx = None, None
    for i, e in enumerate(entrees):
        if not (isinstance(e, dict) and isinstance(e.get('qso'), dict)):
            continue
        if e['qso'].get('id') != qso_id:
            continue
        if trouve is None or e.get('deleted_at', 0) >= trouve.get('deleted_at', 0):
            trouve, idx = e, i
    if idx is None:
        return None, entrees
    reste = entrees[:idx] + entrees[idx + 1:]
    return dict(trouve['qso']), reste


def resume(entree):
    """Vue COMPACTE d'une entrée pour la liste UI (pas le QSO entier — la
    fiche complète ne sort qu'à la restauration). Champs absents -> chaîne
    vide, jamais d'exception sur un QSO partiel/importé."""
    q = entree.get('qso') or {}
    return {
        'id': q.get('id'),
        'call': q.get('call', ''),
        'band': q.get('band', ''),
        'mode': q.get('mode', ''),
        'date': q.get('date', ''),
        'time': q.get('time', ''),
        'deleted_at': entree.get('deleted_at', 0),
    }


# ─── Persistance disque (fichier DÉDIÉ, écriture atomique) ─────────────────

def charger(now=None):
    """Entrées persistées, DÉJÀ purgées des périmées. Fichier absent ou
    illisible -> corbeille vide (jamais d'exception). `now` injectable
    (comme logx_tx_consent) pour rester testable sans horloge réelle."""
    import json
    import time
    now = time.time() if now is None else now
    try:
        with open(FICHIER, encoding='utf-8') as f:
            brut = json.load(f)
    except (OSError, ValueError):
        return []
    if not isinstance(brut, list):
        return []
    return purger_perimes(brut, now)


def enregistrer(entrees):
    """Écrit ATOMIQUEMENT (isolé du reste, même convention que
    logx_operator_goals.enregistrer)."""
    import logx_storage
    logx_storage.save_json_atomic(FICHIER, entrees, lock=_lock)


def capturer_et_persister(qsos, now=None):
    """Glue appelée par les 2 endpoints de suppression (do_DELETE + le
    fallback POST) : capture + fusionne avec la corbeille déjà sur disque +
    purge + réécrit. `now` injectable pour les tests."""
    import time
    now = time.time() if now is None else now
    nouvelles = capturer(qsos, now)
    if not nouvelles:
        return
    actuelles = charger(now)
    enregistrer(purger_perimes(actuelles + nouvelles, now))


def restaurer_et_persister(qso_id, now=None):
    """Glue de restauration : retire l'entrée de la corbeille persistée,
    réécrit le fichier, renvoie le QSO restauré (ou None si introuvable).
    `now` injectable pour les tests."""
    actuelles = charger(now)
    qso, reste = restaurer(actuelles, qso_id)
    if qso is not None:
        enregistrer(reste)
    return qso
