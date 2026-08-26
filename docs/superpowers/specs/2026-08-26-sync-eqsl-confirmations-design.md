# Synchronisation descendante des confirmations eQSL — Design

**Date** : 2026-08-26 · **Décidé avec** F4GLD · **Maillon copilote** : 6 (agent de synchro)

## But

Descendre automatiquement les confirmations **eQSL** dans le carnet (aujourd'hui
eQSL est upload-only), les fusionner dans le magasin de confirmations existant,
et **recalculer les diplômes sans jamais accorder de faux crédit** (eQSL n'est
pas accrédité par toutes les organisations). ClubLog reste hors scope
(upload/OQRS uniquement — décision F4GLD). Aucune émission, non destructif.

## Contrainte capitale — matrice de crédit SOURCÉE

Une confirmation eQSL est une **confirmation indépendante**, distincte du
**crédit de diplôme**. Le crédit est évalué par une **matrice d'accréditation
par (diplôme × source)**, chaque règle portant `status`, `source_url`,
`verified_at_utc`, `rules_version`. **Inconnu ⇒ aucun crédit automatique.**
Jamais de règle globale « eQSL crédite tout sauf X ».

`status ∈ {ALLOWED, DENIED, CONDITIONAL, UNKNOWN}`.

### Règles initiales (sourcées)

| award_id (interne) | source | status | source_url | vérifié |
|---|---|---|---|---|
| ARRL_DXCC | EQSL | DENIED | arrl.org/e-qsl-policy | 2026-08-26 |
| ARRL_DXCC_CHALLENGE | EQSL | DENIED | arrl.org/e-qsl-policy | 2026-08-26 |
| ARRL_WAS | EQSL | DENIED | arrl.org/e-qsl-policy | 2026-08-26 |
| ARRL_VUCC | EQSL | DENIED | arrl.org/e-qsl-policy | 2026-08-26 |
| ARRL_WAC | EQSL | DENIED | arrl.org/e-qsl-policy | 2026-08-26 |
| CQ_WAZ / CQ_WAZ_ITU | EQSL | UNKNOWN | *à sourcer (CQ WAZ)* | — |
| DX_FIELD / DEPARTEMENTS | EQSL | UNKNOWN | *à sourcer* | — |
| *(toute source LoTW)* | LOTW | ALLOWED (DXCC) | inchangé | — |

Source ARRL vérifiée : « Photocopies and electronically transmitted
confirmations ... are not currently acceptable for DXCC purposes. Exception:
... Logbook of the World ... are acceptable. »

## Architecture

### Lot 1 — `sync_eqsl(cfg, since=None)` dans `logx_qsl.py` (calqué sur `sync_lotw`)

Flux en 2 temps (l'API eQSL renvoie une page HTML avec un lien, pas l'ADIF direct) :

1. `GET https://www.eQSL.cc/qslcard/DownloadInBox.cfm` avec
   `UserName`, `Password` (identifiants eQSL **existants**, chiffrés au repos),
   `ConfirmedOnly=1`, `HamOnly=1`, et `RcvdSince=YYYYMMDDHHMM` si `since` fourni
   (incrémental). Via `_NET_EXECUTOR` + timeout, comme `sync_lotw`.
2. Parser le HTML pour extraire le lien `.adi` (deux `<a href>` `.adi`/`.txt`,
   contenu identique).
3. `GET` l'ADIF.
4. `parse_confirmations(adif, 'eqsl')` — lit **déjà** `EQSL_QSL_RCVD` (l.197).
5. `merge_confirmations(conf)` — existe, invalide **déjà** `awards`.
6. Détection d'échec : creds refusés ⇒ page **sans** lien de download ⇒ erreur
   explicite. Retour `{ok, service:'eQSL', confirmed_downloaded, newly_added,
   total_confirmations}`.

### Lot 2 — Matrice de crédit `logx_award_credit.py` (neuf)

- `CreditStatus` (enum) ; `AwardCreditRule` (award_id, source, status,
  conditions[], source_url, verified_at_utc, rules_version) ; `AWARD_RULES`
  (règles initiales ci-dessus) ; `evaluer_credit(award_id, source, ...) ->
  {status, reason}`. Défaut absent ⇒ `UNKNOWN` (aucun crédit).

### Lot 3 — `award_summary` source-aware (garde-fou anti-faux-crédit)

`award_summary` compte aujourd'hui `is_conf = bool(conf.get(key))` **toutes
sources** pour tous les diplômes (`logx_awards.py:871`) — dès qu'`eqsl` entre
dans le magasin, le DXCC afficherait un faux crédit. Correctif : pour chaque
diplôme, ne compter « confirmé » que les confirmations dont la source est
`ALLOWED` (ou `CONDITIONAL` satisfait) pour CE diplôme via la matrice. Les
alertes « besoin DXCC » (`_creneaux_confirmes_lotw`) sont déjà source-aware
(`lotw` only) — inchangées. Ajout d'un compteur « confirmé eQSL » distinct et
d'un indicateur « confirmé (tous services) » séparé du crédit-diplôme.

### Lot 4 — Endpoint + UI

- `/qsl/sync` (existant pour LoTW) : ajouter le service `eqsl` (ou route dédiée
  `/qsl/sync/eqsl`). Journal d'audit (horodatage, service, téléchargés/ajoutés,
  erreur). Non destructif.
- Panneau QSL : bouton « eQSL — synchroniser mes confirmations » à côté du sync
  LoTW ; aperçu des compteurs ; badge « confirmé eQSL » distinct du crédit.

## Sécurité / garde-fous copilote

- Niveau d'autorisation : **Automatisation limitée** (tâche NON radio). Pas de
  PTT/émission. Non destructif (n'ajoute que des confirmations, ne modifie
  jamais un QSO).
- Identifiants eQSL réutilisés (déjà chiffrés AES-256-GCM au repos). Jamais en
  clair.
- **Journal d'audit** de chaque sync.

## Tests (TDD, réponses simulées)

1. `sync_eqsl` : HTML→lien→ADIF simulé ⇒ confirmations mergées, compteurs justes.
2. Incrémental : `since` ⇒ `RcvdSince` correct dans l'URL.
3. Creds refusés : page sans lien ⇒ `{ok:False}` (jamais d'exception).
4. **🔴 `test_eqsl_ne_credite_jamais_le_dxcc`** : une confirmation eQSL ⇒
   `award_summary` DXCC confirmé **inchangé** (crédit DENIED).
5. `evaluer_credit` : ARRL_DXCC/EQSL ⇒ DENIED ; award inconnu ⇒ UNKNOWN ;
   CQ_WAZ/EQSL ⇒ UNKNOWN (pas de crédit auto tant que non sourcé).
6. eQSL affiché « confirmé eQSL » même quand crédit DENIED/UNKNOWN.
7. Non-régression : une confirmation LoTW continue de créditer le DXCC.

## Hors scope (assumé)

ClubLog (upload/OQRS), sourcing complet des règles CQ/REF (ajout incrémental à
la matrice), programmes eWAZ/eWAS (diplômes électroniques à règles propres).
