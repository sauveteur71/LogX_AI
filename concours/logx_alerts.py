# -*- coding: utf-8 -*-
"""Constructeur de règles d'alerte personnalisées (au-delà des 2 alertes
fixes — nouveau multiplicateur / mention ON4KST). L'opérateur combine
quelques critères simples (préfixe d'indicatif, continent, zone CQ, bande,
statut travaillé, texte du commentaire de spot) — chaque règle nommée,
activable individuellement.

Volontairement PAS de critère "Most Wanted" (aucune source de données
DXCC ranking disponible dans le projet) ni de sélecteur pays exhaustif
(le continent + la zone CQ couvrent l'essentiel des usages réels pour un
constructeur simple, sans UI de recherche pays à construire).

Déterministe, hors-ligne : évalue chaque règle contre la liste de spots déjà
classée par build_ranked_spots (logx_scoring.py), consommée par
/data/spots_ranked (logx_http.py) qui ajoute alert_matches à sa
réponse — pas d'aller-retour réseau supplémentaire côté client."""


def evaluate_rule(rule, spot):
    """Un spot satisfait une règle si TOUS ses critères non vides sont vrais
    (ET logique). Un critère absent/vide de la règle = joker (ne filtre pas).
    Ne lève jamais d'exception, même sur un spot incomplet."""
    if not rule.get('enabled', True):
        return False

    call = str(spot.get('call', '') or '').upper()
    prefixes = [p.strip().upper() for p in (rule.get('call_prefix') or '').split(',') if p.strip()]
    if prefixes and not any(call.startswith(p) for p in prefixes):
        return False

    continent = (rule.get('continent') or '').strip().upper()
    if continent and str(spot.get('dx_continent', '') or '').upper() != continent:
        return False

    cq_zones = [z.strip() for z in str(rule.get('cq_zone') or '').split(',') if z.strip()]
    if cq_zones and str(spot.get('dx_cq_zone', '') or '') not in cq_zones:
        return False

    bands = [b.strip() for b in (rule.get('band') or '').split(',') if b.strip()]
    if bands and str(spot.get('band', '') or '') not in bands:
        return False

    status = rule.get('status', 'any')
    if status not in ('any', ''):
        # Un critère de statut qu'on ne sait pas évaluer doit échouer FERMÉ :
        # sinon une valeur inconnue (typo, ou futur enum ajouté à l'UI mais pas
        # ici) traverse silencieusement le filtre et déclenche des alertes
        # parasites (fail-open). On ne laisse passer que les statuts connus.
        if status == 'new_mult':
            if not spot.get('new_mult'):
                return False
        elif status == 'already_done':
            if not spot.get('already_done'):
                return False
        else:
            return False

    comment = (rule.get('comment_contains') or '').strip().lower()
    if comment and comment not in str(spot.get('info', '') or '').lower():
        return False

    return True


def check_alerts(rules, spots):
    """Retourne les correspondances {rule_id, rule_name, spot} — un spot peut
    déclencher plusieurs règles, chacune remontée séparément (l'anti-répétition
    par règle+indicatif est gérée côté client, comme pour les mults)."""
    matches = []
    for rule in (rules or []):
        name = (rule.get('name') or '').strip()
        if not name:
            continue
        for spot in (spots or []):
            if evaluate_rule(rule, spot):
                matches.append({'rule_id': rule.get('id', ''), 'rule_name': name, 'spot': spot})
    return matches
