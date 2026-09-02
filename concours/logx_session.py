# -*- coding: utf-8 -*-
"""Planificateur de session — CONSULTATIF (propose-only).

À partir des contraintes de l'opérateur (durée, objectif, mode(s), bande(s),
puissance), l'IA propose un PLAN découpé en créneaux horaires avec des critères
d'arrêt. C'est un CONSEIL : l'opérateur garde le contrôle de chaque QSY et de
chaque émission. Ce module ne fait que construire l'ENTRÉE du LLM (déterministe,
testable) ; l'appel LLM et l'endpoint vivent dans logx_http. Aucune action, aucune
émission n'est déclenchée ici.
"""

SESSION_PLAN_SYSTEM = (
    "Tu es un assistant de planification pour un opérateur radioamateur. À partir "
    "de ses contraintes (durée, objectif, mode(s), bande(s), puissance), propose un "
    "PLAN DE SESSION découpé en créneaux courts (temps relatif, ex. « 0-10 min », "
    "« 10-25 min »…), avec pour CHAQUE créneau : la bande/mode à privilégier, la "
    "cible ou zone visée, et l'objectif concret. Termine par des CRITÈRES D'ARRÊT "
    "clairs (aucune activité pendant N minutes, niveau de bruit trop élevé, CAT "
    "déconnecté, plus de station décodable).\n"
    "Reste CONSULTATIF : l'opérateur garde le contrôle de CHAQUE changement de "
    "fréquence et de CHAQUE émission. Ne propose JAMAIS d'émettre automatiquement. "
    "Présente une prévision comme une PROBABILITÉ (« ouverture probable vers… »), "
    "jamais comme une certitude. Réponds en français, format compact (listes)."
)


def build_session_message(params):
    """Message utilisateur DÉTERMINISTE résumant les contraintes de session.
    `params` : dict {duree_min, objectif, mode, bandes (str ou liste), puissance_w}.
    Tolère les champs absents."""
    p = params or {}
    duree = p.get('duree_min')
    objectif = str(p.get('objectif') or '').strip()
    mode = str(p.get('mode') or '').strip()
    bandes = p.get('bandes')
    if isinstance(bandes, (list, tuple)):
        bandes = ', '.join(str(b) for b in bandes if b)
    else:
        bandes = str(bandes or '').strip()
    puissance = p.get('puissance_w')

    lignes = ["Planifie ma session radio avec ces contraintes :"]
    if duree:
        lignes.append(f"- Durée disponible : {duree} minutes")
    if objectif:
        lignes.append(f"- Objectif : {objectif}")
    if mode:
        lignes.append(f"- Mode(s) : {mode}")
    if bandes:
        lignes.append(f"- Bande(s) : {bandes}")
    if puissance:
        lignes.append(f"- Puissance : {puissance} W")
    lignes.append("Donne un plan par créneaux (temps UTC relatif) avec, à la fin, "
                  "des critères d'arrêt. Reste consultatif : je garde le contrôle de "
                  "chaque QSY et de chaque émission.")
    return "\n".join(lignes)
