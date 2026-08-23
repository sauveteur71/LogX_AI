# -*- coding: utf-8 -*-
"""Garde-fou d'émission CW (F4GLD 23/08/2026, Phase 1 keyer CW natif).

Le keying CW passe par POST /rig/cw. Avant ce module, RIEN côté serveur
n'empêchait d'émettre : ni interrupteur maître, ni vérification du mode. Deux
garde-fous, refus BLOQUANT (jamais un simple avertissement) :

  1. TX-ENABLE MAÎTRE : le client doit ARMER explicitement l'émission (`armed`).
     Désarmé par défaut à chaque ouverture -> aucune émission par inadvertance
     (Échap réflexe, macro cliquée, texte tapé au clavier…).
  2. MODE CW : si le mode courant du poste est CONNU et n'est PAS un mode CW,
     on refuse (on ne manipule pas la clé en SSB/FT8/RTTY). Mode inconnu (champ
     vide, WinKeyer sans CAT) -> on ne bloque pas sur ce seul critère, l'arme
     reste requise.

Fonction PURE (aucune I/O) pour être testable sans poste ni serveur. Écrire ce
garde-fou n'émet rien : l'essai sur l'air reste le geste supervisé de
l'opérateur (TX réellement armé + matériel branché).
"""


def est_mode_cw(mode):
    """True pour tout mode CW du poste : CW, CWR, CW-R, CW-U, CW-L, CW-N…"""
    m = str(mode or '').upper().replace('_', '-').strip()
    return m.startswith('CW')


def cw_tx_autorise(payload):
    """Autorise (ou non) une requête de keying /rig/cw.

    `payload` : le dict JSON de la requête (au moins {armed, mode}). Retourne
    (ok: bool, raison: str) — `raison` est vide si autorisé, sinon un message
    prêt à afficher à l'opérateur."""
    if not isinstance(payload, dict):
        return False, "Requête CW invalide."
    if not payload.get('armed'):
        return False, ("TX non armé — arme l'émission (interrupteur maître) "
                       "avant d'envoyer du CW.")
    mode = payload.get('mode', '')
    if mode and not est_mode_cw(mode):
        return False, (f"Le poste est en « {mode} » — passe-le en CW "
                       "avant d'émettre du CW.")
    # HORS PLAN DE BANDE : si la fréquence est CONNUE (CAT) et hors de toute
    # bande amateur, on refuse (émission illégale). Fréquence inconnue (pas de
    # CAT) -> en_bande_amateur() renvoie None et on NE bloque PAS sur ce critère.
    freq = payload.get('freq_khz')
    if freq not in (None, ''):
        import logx_frequences as freq_mod
        if freq_mod.en_bande_amateur(freq) is False:
            return False, (f"Fréquence {freq} kHz hors des bandes amateur — "
                           "vérifie le VFO avant d'émettre.")
    return True, ''
