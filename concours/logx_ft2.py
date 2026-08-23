# -*- coding: utf-8 -*-
"""Contrôle TX FT2 — Phase 5 : LogX pilote la TX via Reply UDP à Decodium.

LogX ne génère PAS l'audio FT2 : il envoie une commande Reply (type 4, protocole
WSJT-X) à l'instance Decodium, qui gère encodeur / horloge slot 3,75 s / CAT /
Split-Fake It / PTT. Règle de sûreté (F4GLD, 23/08) : JAMAIS de Reply
AUTOMATIQUE (ex. double-clic sur un décodage) — seulement après confirmation
explicite, TX armé par l'opérateur, fréquence autorisée par le profil actif, et
UNIQUEMENT vers l'IP:port de l'instance Decodium qui a émis le datagramme reçu
(jamais une adresse devinée — recommandation du protocole WSJT-X).

can_send_ft2_reply() est une fonction PURE (aucune I/O) : la barrière de sûreté
testable. Écrire ce code n'émet rien ; l'essai on-air reste supervisé (F4GLD).
"""


def can_send_ft2_reply(ctx):
    """Autorise (ou non) l'envoi d'un Reply FT2 à Decodium. `ctx` : dict d'état.
    Retourne (ok: bool, raison: str). TOUTES les conditions doivent être vraies —
    refus BLOQUANT sinon (émission = sûreté d'abord)."""
    if not isinstance(ctx, dict):
        return False, "Contexte FT2 invalide"
    if ctx.get('protocol_variant') != 'FT2_DECODIUM':
        return False, "Variante FT2 non compatible Decodium"
    if not ctx.get('decodium_udp_connected'):
        return False, "Decodium UDP indisponible"
    if not ctx.get('decodium_accept_commands'):
        return False, "Decodium refuse les commandes externes (« Accept commands » désactivé)"
    if not ctx.get('tx_enabled_by_operator'):
        return False, "TX désactivée par l'opérateur"
    if not ctx.get('frequency_is_allowed'):
        return False, "Fréquence non autorisée par le profil actif"
    if not ctx.get('user_confirmed_tx'):
        return False, "Confirmation TX requise"
    return True, ''


def envoyer_reply_decodium(sock, decode, wsjtx_id, addr, ctx):
    """Envoie un Reply FT2 à Decodium — UNIQUEMENT si can_send_ft2_reply passe,
    et UNIQUEMENT vers `addr` (l'IP:port de l'instance Decodium qui a émis le
    datagramme reçu ; jamais une adresse devinée). Ne lève JAMAIS.
    Retourne (ok: bool, raison: str)."""
    ok, raison = can_send_ft2_reply(ctx)
    if not ok:
        return False, raison
    if not addr:
        return False, "Adresse Decodium inconnue (aucun datagramme reçu)"
    try:
        import logx_wsjtx as wsjtx
        sock.sendto(wsjtx.construire_reply(decode, wsjtx_id), addr)
        return True, ''
    except Exception as e:
        return False, "Envoi Reply Decodium échoué (%s)" % e


def envoyer_halt_tx_decodium(sock, wsjtx_id, addr):
    """Halt TX (type 5) vers Decodium — COUPE-CIRCUIT : jamais gardé (arrêter une
    émission ne doit dépendre d'aucune condition), toujours disponible (Échap
    prioritaire). Ne lève jamais. Retourne (ok: bool, raison: str)."""
    if not addr:
        return False, "Adresse Decodium inconnue"
    try:
        import logx_wsjtx as wsjtx
        sock.sendto(wsjtx.construire_halt_tx(wsjtx_id), addr)
        return True, ''
    except Exception as e:
        return False, "Envoi Halt TX échoué (%s)" % e
