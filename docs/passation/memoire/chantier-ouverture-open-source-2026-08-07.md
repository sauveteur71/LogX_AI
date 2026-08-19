---
name: chantier-ouverture-open-source-2026-08-07
description: "Finalisation de l'ouverture open-source du dépôt (CONTRIBUTING.md, CODE_OF_CONDUCT.md, gabarits issue/PR, README) — EV-6.1/EV-6.4 du PRD"
metadata: 
  node_type: memory
  type: project
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-08-07T13:05:41.926Z
---

Chantier livré et fusionné sur `main` le 07/08/2026 (commit `b9a5f7b`, merge de
`feat/ouverture-open-source`, commit de contenu `05c7c29`) : finalisation de
l'ouverture open-source de `sauveteur71/radioaamateur-program-Contest`, points
EV-6.1/EV-6.4 du PRD (`docs/LogX_AI_PRD.md`).

Livré :
- `CONTRIBUTING.md` — install (venv, `pip install -r requirements.txt`),
  `python -m pytest -q` depuis `concours/`, `python logx_validate.py` pour les
  règlements, conventions (français partout y compris code/commits,
  commentaires POURQUOI pas QUOI, test de reproduction encouragé, pas de
  dépendance lourde sans discussion), processus de PR.
- `CODE_OF_CONDUCT.md` — Contributor Covenant v2.1, **traduction officielle
  française récupérée verbatim** (WebFetch sur contributor-covenant.org),
  même logique que le LICENSE GPLv3 récupéré via `gh api licenses/gpl-3.0`
  plus tôt dans le projet : texte légal/officiel toujours récupéré tel quel,
  jamais reconstruit de mémoire.
- `.github/ISSUE_TEMPLATE/feature.yml` — gabarit "💡 Proposer une idée" (3
  champs : besoin/idée/contexte). Avant ce chantier, **aucun moyen d'ouvrir
  une issue de suggestion** — seul `bug.yml` existait.
- `.github/PULL_REQUEST_TEMPLATE.md` — checklist (pytest, logx_validate.py,
  testé en navigateur, nouveaux tests).
- `README.md` — version corrigée (`0.9-beta22` stale → `0.9-beta25`) +
  nouvelle section `## Contribuer`.
- 3 nouveaux tests dans `concours/tests/test_release_ci_config.py` (mêmes
  patterns que les tests `bug.yml` existants) : champs présents, types/ids
  valides, `besoin` obligatoire / `idee` non obligatoire.

## Décision autonome à signaler à F4GLD

Sous instruction explicite "non pas de pause continue" (ne pas s'arrêter pour
demander), décision prise seule : le champ contact de la section application
de `CODE_OF_CONDUCT.md` (template `[INSÉRER UNE ADRESSE EMAIL]`) **ne pointe
PAS vers une adresse email personnelle** — remplacé par un mécanisme GitHub
(ouvrir un ticket confidentiel, ou message privé au profil
[@sauveteur71](https://github.com/sauveteur71)).

**Pourquoi** : aucune adresse email n'avait été fournie ni validée pour cet
usage public ; publier une adresse personnelle dans un document public est
irréversible une fois indexé/caché, alors que le choix inverse (ajouter une
adresse plus tard) est trivial.

**Comment appliquer** : si F4GLD préfère une adresse email dédiée pour ce
rôle, il suffit d'éditer la section correspondante de `CODE_OF_CONDUCT.md` —
ce n'est PAS un choix figé, juste le défaut le plus prudent en l'absence
d'instruction.

## Piège confirmé pendant ce chantier (déjà documenté ailleurs, reconfirmé ici)

`gh run watch` a affiché "✗ Process completed with exit code 1" alors que le
run était en réalité `conclusion:"success"` (vérifié via
`gh api .../actions/runs/<id> --jq '{status,conclusion}'`) — sur CETTE branche
ET sur le merge commit sur `main`. Annotation Node.js-deprecation trompeuse,
pas un vrai échec. Toujours vérifier via l'API directe avant de conclure à un
échec CI, ne jamais se fier au texte de `gh run watch` seul.
