# -*- coding: utf-8 -*-
"""IA-2 — enrichissement DÉTERMINISTE du log (voir la proposition
docs/superpowers/specs/2026-08-24-ia2-enrichissement-PROPOSITION.md).

Lot 1 (cœur, décision-free) : dérive du PAYS DXCC, du CONTINENT et des ZONES
CQ/ITU à partir du seul INDICATIF, via logx_dxcc (cty.dat, déjà dans le dépôt) —
aucune table de domaine inventée ici, aucune décision produit. Fonction PURE :
ne modifie rien, ne remplit QUE les cases vides du QSO, et renvoie uniquement
les champs qu'elle a pu dériver.

Là où APPLIQUER cet enrichissement (à l'export ? à l'enregistrement ? les
deux ?) et QUELS champs activer restent des décisions de F4GLD (§4 de la
proposition) : ce module ne fait que la DÉRIVATION, jamais l'application.
"""
import logx_dxcc

# (clé interne du log, clé renvoyée par logx_dxcc.lookup). Les clés internes
# dxcc_country / continent / cqz / ituz existent déjà dans le code (logbook,
# awards, export B).
_CHAMPS_DEPUIS_INDICATIF = (
    ('dxcc_country', 'country'),
    ('continent', 'continent'),
    ('cqz', 'cq_zone'),
    ('ituz', 'itu_zone'),
)


def enrichir(qso, cfg=None):
    """Champs dérivables MANQUANTS pour ce QSO, sous forme {clé_interne: valeur}.

    Ne dérive que depuis l'indicatif (lot 1). Ne renvoie JAMAIS un champ déjà
    renseigné par l'opérateur (on ne remplit que le vide, sa saisie fait foi).
    Renvoie {} si pas d'indicatif ou indicatif inconnu de cty.dat."""
    qso = qso or {}
    call = str(qso.get('call', '') or '').strip()
    if not call:
        return {}
    fiche = logx_dxcc.lookup(call)
    if not fiche:
        return {}
    out = {}
    for interne, source in _CHAMPS_DEPUIS_INDICATIF:
        if str(qso.get(interne, '') or '').strip():
            continue                      # déjà saisi -> ne pas écraser
        val = fiche.get(source)
        if val not in (None, ''):
            out[interne] = str(val)
    return out
