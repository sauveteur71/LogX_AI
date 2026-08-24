# -*- coding: utf-8 -*-
"""Garde-fou d'émission CW (F4GLD 23/08/2026, Phase 1 keyer CW natif).

Le keying CW passe par POST /rig/cw. Deux garde-fous à refus BLOQUANT : TX-enable
maître (`armed`) + mode CW (+ hors plan de bande). Depuis l'unification de la
sécurité TX (24/08/2026), cette logique est PARTAGÉE avec la voix : elle vit dans
`logx_tx_guard` (garde-fou paramétré par famille de mode). Ce module reste
l'ADAPTATEUR CW — il conserve l'API publique historique (`cw_tx_autorise`,
`est_mode_cw`) attendue par /rig/cw et ses tests, et délègue au garde-fou unifié
avec la famille 'cw'. Aucune duplication de règle.

Écrire ce garde-fou n'émet rien : l'essai sur l'air reste le geste supervisé de
l'opérateur (TX réellement armé + matériel branché).
"""

from logx_tx_guard import est_mode_cw, tx_autorise  # noqa: F401  (réexport public)


def cw_tx_autorise(payload):
    """Autorise (ou non) une requête de keying /rig/cw.

    Adaptateur : délègue au garde-fou TX unifié, famille CW. `payload` : le dict
    JSON de la requête (au moins {armed, mode}). Retourne (ok: bool, raison: str)
    — `raison` est vide si autorisé, sinon un message prêt à afficher."""
    return tx_autorise(payload, 'cw')
