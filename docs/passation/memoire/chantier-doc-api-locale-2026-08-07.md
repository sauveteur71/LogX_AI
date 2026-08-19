---
name: chantier-doc-api-locale-2026-08-07
description: "docs/API.md créé — 222 routes HTTP locales documentées (EV-6.5 du PRD), dernier point ouvert des exigences open-source"
metadata: 
  node_type: memory
  type: project
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-08-07T15:08:12.695Z
---

Chantier livré et fusionné sur `main` le 07/08/2026 (commit `e16a135`, merge
de `feat/doc-api-locale`, commit de contenu `10b68db`).

## Contenu

`docs/API.md` (1997 lignes) : 222 routes de `concours/logx_http.py` (7455
lignes) en 27 catégories fonctionnelles, sommaire avec ancres, ~11 exemples
curl sur les routes centrales (log/config/spots), section sécurité et section
« comment s'authentifier depuis un script tiers ». Lien ajouté dans
`README.md` juste avant `## Licence`. Referme EV-6.5, le dernier point
`EV-6.x` du PRD encore ouvert après "[[chantier-ouverture-open-source-2026-08-07]]".

## Méthode

Workflow 2 phases : 4 agents d'EXTRACTION en parallèle (plages de lignes non
chevauchantes sur `logx_http.py`, sortie structurée) → 1 agent
d'ASSEMBLAGE qui ne recopie PAS les données d'extraction telles quelles :
consigne explicite de revérifier lui-même dans le code tout ce qui semblait
douteux avant d'écrire la doc finale.

## Qualité vérifiée après coup (moi, pas l'agent)

Grep de contrôle sur les affirmations de sécurité les plus sensibles
(bind `0.0.0.0`, cookie `rc_token`/en-tête `X-RC-Token`, PBKDF2-HMAC-SHA256
200000 itérations, anti-bruteforce 5 essais/60s) : toutes exactes au chiffre
près. L'agent d'assemblage avait fait le même travail de vérification de son
côté (visible dans son rapport) — double confirmation, pas juste une
affirmation prise sur parole.

## Point réel trouvé par l'agent, pas par moi

Une tâche de mon propre suivi (« routes `/log/bulk_resolve` non actives sur
le serveur en cours ») était **obsolète** — l'agent d'assemblage a vérifié
dans le code que ces routes sont bien enregistrées et actives, contredisant
ma propre note. Tâche supprimée après vérification. Rappel : une note prise
dans une session passée peut devenir fausse si le code a bougé depuis —
toujours vérifier avant de la reporter telle quelle dans une doc publique.

## Pourquoi pas de CI à attendre

`.github/workflows/check.yml` ne se déclenche que sur `concours/**` et
`.github/ISSUE_TEMPLATE/**` (commit `8194b55`, décision déjà actée). Un
commit qui ne touche que `docs/`/`README.md` ne déclenche donc PAS la CI —
comportement attendu, pas un oubli. Suite pytest complète lancée en local
avant fusion à la place (verte, code de sortie 0) : suffisant pour une
modification purement documentaire, sans changement de comportement.
