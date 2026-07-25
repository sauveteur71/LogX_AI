# Contrats de données — LogX AI

Ce document fixe la politique de versionnage des schémas de données publics du projet (PRD §5.2, EV-6.2) : des contributeurs externes et des outils tiers peuvent s'appuyer dessus, donc leur évolution doit être prévisible.

## Schéma concours (`concours/contest_schema.json`)

**Statut : v1.1.0** (25/07/2026).

JSON Schema (draft 2020-12) validant chaque entrée de `CONTEST_DEFINITIONS` (`logx_definitions.py`) — qu'elle soit écrite à la main, importée du calendrier WA7BNM ou extraite d'un règlement par l'IA. Validé par `logx_validate.py` (utilise la lib `jsonschema` si installée, sinon une vérification minimale de secours).

### Format de version

Semver (`MAJOR.MINOR.PATCH`), champ `"version"` au niveau racine du fichier.

- **MAJOR** — changement cassant : un champ `required` est retiré/renommé, ou le type d'un champ change de façon incompatible avec les définitions existantes. Toute définition de concours déjà écrite (36 intégrées + celles issues de WA7BNM/IA) doit alors être migrée. Le `$id` du schéma est mis à jour dans ce cas.
- **MINOR** — évolution rétrocompatible : nouveau champ optionnel, nouvelle valeur d'énumération, assouplissement d'une contrainte. Aucune définition existante n'a besoin d'être modifiée.
- **PATCH** — clarification de `description`, correction de coquille, sans changement de structure validable.

Le `$id` (`https://f6kqj.local/contest_schema.json`) reste **stable** d'une version mineure/patch à l'autre — il ne change qu'en cas de MAJOR, pour signaler explicitement qu'une définition validée contre l'ancien `$id` n'est plus garantie valide contre le nouveau.

### Politique de migration (en cas de MAJOR)

1. La nouvelle version est développée sur une branche dédiée, jamais directement sur `main`.
2. Toutes les définitions intégrées (`logx_definitions.py`) sont migrées et re-validées (`python logx_validate.py`) avant fusion — critère de non-régression déjà en place (44 064 comparaisons ancien/nouveau moteur, cf. PRD §4.1).
3. Le changement est documenté dans cette page (section "Historique" ci-dessous) avec la liste précise des champs affectés et l'impact pour un contributeur externe (définition custom, outil tiers).
4. Une définition écrite contre l'ancienne version continue si possible d'être acceptée pendant une période de transition (le validateur peut détecter l'absence du nouveau champ requis et proposer une valeur par défaut plutôt que de rejeter), sauf si le changement rend cela impossible.

### Historique

- **1.0.0** (21/07/2026) — première version explicitement numérotée. Aucun changement de structure à cette étape : le schéma existait déjà (draft 2020-12, `required`/`additionalProperties: false`), seul le numéro de version et cette politique sont nouveaux.

## Schéma QSO

**Statut : à créer** — n'existe pas encore comme fichier séparé. Aujourd'hui la forme d'un QSO (`id`, `call`, `band`, `mode`, `contest`, `date`, `time`, `points`, `locator`, `num_rcvd`/`num_sent`, `rst_sent`/`rst_rcvd`...) est implicite, déduite du code (`logx_storage.py` `_CORE`, `add_qso_to_log` dans `logx_http.py`) plutôt que documentée comme un contrat formel. C'est un point ouvert du PRD (§5.2, EV-6.2) — à traiter avant de considérer les contrats de données "figés" pour l'open-source.
