# -*- coding: utf-8 -*-
"""Occupation des bandes multi-postes — carte « qui est sur quelle bande/mode ».

Pour un LOG PARTAGÉ (radioclub / expédition / activation spéciale type TM6KJS)
où plusieurs postes opèrent le même indicatif : rend visible qui occupe quelle
bande/mode, et signale les recouvrements (règle F4GLD : jamais deux postes sur la
MÊME bande ET le MÊME mode ; même bande + mode différent = permis).

Ce module est TRANSPORT-AGNOSTIQUE. Il reçoit des « statuts » de postes déjà
collectés depuis N'IMPORTE quel canal actif — LAN (instantané, même réseau),
Cloud Sync (dossier partagé, distant) ou MySQL (distant temps réel) — fusionnés
en une seule liste. La logique d'ici :

  - « PRIORITÉ LOCALE » : quand un même poste est vu par plusieurs canaux, on
    garde le statut le PLUS FRAIS (le LAN est plus récent que le cloud) — émerge
    naturellement du latest-ts-wins, sans code spécifique par canal.
  - un poste muet depuis plus de `ttl_s` est oublié (comme le registre de pairs
    LAN) — pas d'occupation fantôme.

Statut = dict {station, call, band, mode, ts} (ts = epoch secondes). `station`
est l'identifiant d'installation (iid), unique par poste — jamais l'indicatif
(tous partagent le même en activation spéciale).
"""


def vue_occupation(statuts, maintenant, ttl_s=180):
    """statuts (list[dict]) -> {'stations': [...], 'conflits': [...]}.

    - stations : un par poste vivant (statut le plus frais), trié bande puis
      indicatif ;
    - conflits : recouvrements bande+mode (au moins deux postes distincts sur le
      même couple bande/mode) = {'band', 'mode', 'stations': [ids triés]}.
    """
    # PRIORITÉ LOCALE : un seul statut par poste, le plus frais gagne.
    par_station = {}
    for s in (statuts or []):
        if not isinstance(s, dict):
            continue
        st = s.get('station')
        if not st:
            continue                       # statut sans identifiant de poste -> ignoré
        ts = s.get('ts', 0) or 0
        if st not in par_station or ts > (par_station[st].get('ts', 0) or 0):
            par_station[st] = s

    # Oubli des postes muets depuis trop longtemps (pas d'occupation fantôme).
    vivants = [s for s in par_station.values()
               if (maintenant - (s.get('ts', 0) or 0)) <= ttl_s]
    vivants.sort(key=lambda s: (str(s.get('band', '')), str(s.get('call', ''))))

    # Conflits : deux postes distincts sur le MÊME couple bande/mode.
    par_bm = {}
    for s in vivants:
        cle = (str(s.get('band', '')), str(s.get('mode', '')))
        par_bm.setdefault(cle, []).append(s)
    conflits = []
    for (band, mode), groupe in par_bm.items():
        stations = sorted({g.get('station') for g in groupe})
        if band and len(stations) > 1:     # bande vide = inconnu, pas un conflit
            conflits.append({'band': band, 'mode': mode, 'stations': stations})
    conflits.sort(key=lambda c: (c['band'], c['mode']))

    return {'stations': vivants, 'conflits': conflits}
