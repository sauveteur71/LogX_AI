# ✅ FAIT — LIVRÉ DANS MAIN (annoté le 2026-09-05)

> **Ce backlog est PÉRIMÉ (livré).** LLOTA intégré (validation syntaxique, programme XOTA,
> `sig`/`sig_info`) — **PR #459** (`c9e079d`, merge `0e1b919`). Format de référence confirmé
> **`LLxx-nnnn`** (ex. `LLNZ-0359`, correctif `b9d07d8`, merge `31d85b2`). Fichiers :
> `concours/logx_activation.py`, `logx_logbook.js`, `docs/XOTA_SOURCES.md`, tests
> `test_activation_llota.py`. Conservé pour mémoire des décisions d'architecture.

---

# BACKLOG — Intégration LLOTA (Lakes and Lagoons On The Air) — à faire APRÈS l'EME

Demandé par F4GLD le 2026-09-01, PENDANT l'exécution EME, avec une spec provisoire détaillée.
Séquencement : file d'attente APRÈS le chantier EME (et vraisemblablement avec/après la carte XOTA).
Note de travail durable NON commitée (survit au changement de branche). F4GLD peut rebattre la priorité.

## Ce qu'est LLOTA
Programme XOTA « plans d'eau » (lacs, lagunes, réservoirs, barrages). Références forme `CL-0001`
(`^[A-Z]{2}-[0-9]{4,}$`), associées à des coordonnées GPS. Site : https://llota.app/

## État de confiance (source F4GLD, à re-confirmer sur les pages officielles)
- CONFIRMÉ : site officiel, explorateur de références (https://llota.app/referencias.html),
  doc (documentacion.html), page de règles (reglas.html) existe.
- NON confirmé / VALEUR À SOURCER : contenu des règles (page non récupérée), API publique
  (passerait par proxy + clé privée non exposée → PAS une API publique documentée), export massif,
  redistribution de la base. Champs ADIF (MY_SIG=LLOTA / MY_SIG_INFO=réf) rapportés, à confirmer au règlement.
- Rapportés concordants mais NON officiellement récupérés : 10 QSO min, ≤ 200 m du bord,
  seuil 400 m² d'admissibilité. → configurables, jamais codés en dur comme bloquants.

## ADIF (aligné sur l'existant du dépôt)
- Portable/expédition : `MY_SIG=LLOTA`, `MY_SIG_INFO=<réf>`. Contact d'un correspondant portable :
  `SIG=LLOTA`, `SIG_INFO=<réf distante>`. Longueur ADIF TOUJOURS calculée (jamais codée en dur) —
  le dépôt a déjà `adif_field`/l'enrichissement sig ; réutiliser, ne pas réécrire.

## ALIGNEMENT ARCHITECTURE — divergences avec la proposition de F4GLD (rulings de design à acter)
1. **PAS de tables SQL dédiées** (`llota_sites`, `llota_activations`, `llota_import_runs` proposées).
   Casse la règle VERROUILLÉE « carnet unique chronologique, activité = vue » (CLAUDE.md). À la place :
   - programme enregistré comme les autres XOTA : `logx_ref_info.js` PROGRAMMES + `docs/XOTA_SOURCES.md`
     (mêmes conventions que WWBOTA/GMA/ARLHS/WCA, PR #417-421/#429) ;
   - QSO dans le carnet unique, `sig/sig_info` (déjà géré par le mode chasseur/portable) ;
   - validation (10 QSO, 200 m) = logique sur le log filtré à la sortie, PAS une table d'activations ;
   - catalogue de références = même mécanisme que les autres XOTA (ActivationDatabase bulk+cache
     OU lookup par référence pour base protégée — voir mémoire xota-sources-architecture).
2. **API non confirmée → pas de scraping ni d'import massif** tant que règlement + CGU/API non confirmés
   (cohérent « bases protégées → lookup par référence », ILLW écarté pour cette raison). Ne pas contourner
   auth/clé/anti-bot/limitation. v1 = saisie manuelle + validation syntaxique + lookup par référence si dispo.
3. **Vocabulaire** : « portable »/« expédition » en texte visible, jamais « activation/activateur »
   (la spec de F4GLD utilise « activation/activateur » — à traduire dans l'UI).

## v1 (périmètre recommandé par F4GLD lui-même, compatible pattern XOTA)
Programme enregistré · saisie manuelle de référence · validation syntaxique `^[A-Z]{2}-[0-9]{4,}$` ·
enrichissement `MY_SIG/MY_SIG_INFO` · compteur 10 QSO · contrôle 200 m (configurable) · export ADIF ·
statut « officiel à confirmer ». **PAS encore** : synchro auto, import massif, API privée, géofencing,
validation auto du seuil 400 m².

## Prochaine étape (après EME)
brainstorming (probablement BOUNDED — suit le pattern XOTA déjà rodé) → confirmer les règles depuis
llota.app (source citable) → spec/plan. Voir docs/XOTA_SOURCES.md (registre) et la mémoire
xota-sources-architecture pour le motif bulk vs lookup-par-référence.
