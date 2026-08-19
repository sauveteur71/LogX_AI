---
name: chantier-triage-et-fixnow-mineur-2026-08-12
description: "Triage sémantique + application des 117 correctifs fix_now sur les 162 constats \"mineur\" du 2e audit (PR #43) — clôture le chantier ouvert par PR #41/#42"
metadata: 
  node_type: memory
  type: project
  originSessionId: 98b0707f-1a89-40bf-8422-4ab7b88ba78a
  modified: 2026-08-12T09:39:03.005Z
---

Suite et clôture de [[chantier-differes-majeur-et-lancement-triage-mineur-2026-08-12]].
Le bucket "majeur" (PR #41+#42) et le bucket "mineur" (PR #43, ce fichier) du
2e passage d'audit sont maintenant TOUS LES DEUX clos — plus de constat non
trié restant de ce passage d'audit (`audit_r2_summary.tsv`, 322 constats au
total : critique/majeur déjà couverts par les chantiers précédents, mineur
couvert ici).

## Méthodologie à deux Workflows successifs (nouveau, à réutiliser)

**Workflow 1 (triage)** : 11 agents en parallèle (~15 constats chacun, lisent
le VRAI code, pas le résumé tronqué) + 1 agent de synthèse qui déduplique en
groupes `fix_now`/`defer_needs_discussion`/`reject_not_worth_it`. Sur 162
constats bruts -> 137 groupes après dédup (117 fix_now, 11 rejetés car déjà
corrigés ou non pertinents, 9 différés).

**Workflow 2 (application)**, nouveauté par rapport à PR #41 : au lieu de
tout corriger moi-même à la main (impraticable à cette échelle, 117 groupes
sur 72 fichiers), un 2e Workflow séparé applique les fix_now :
- **Risque identifié AVANT de lancer** : plusieurs groupes de "duplication"
  déplacent du code vers `logx_utils.py` (fichier UNIQUE, partagé). Si on
  laisse `pipeline()` traiter tous les fichiers en parallèle (concurrence
  ~10-16), plusieurs agents éditeraient `logx_utils.py` en même temps ->
  risque réel de perte d'édition ou de structure cassée.
  **Solution** : sortir ces 7 groupes dans une PHASE SÉQUENTIELLE séparée
  (`for (const g of UTILS_GROUPS) { await agent(...) }`, pas `parallel()`
  ni `pipeline()`) qui tourne AVANT la phase principale en `pipeline()` sur
  les 65 fichiers restants (chacun édité par UN SEUL agent, aucun autre
  fichier n'étant partagé entre deux groupes de façon à créer un vrai risque
  d'écriture concurrente au même endroit).
- **Chevauchement non anticipé, mais absorbé sans casse** : un même
  `group_key` (ex. suppression de règles CSS `.nav-spacer`/`.nav-info`
  dupliquées dans 3 fichiers HTML) apparaissait comme item séparé dans
  PLUSIEURS entrées du pipeline (une par fichier de son `finding_refs`), et
  chaque agent avait pour consigne d'appliquer TOUT le plan (les 3 fichiers)
  s'il le jugeait pertinent. Deux agents ont donc tenté d'éditer le MÊME
  3e fichier (`logx_configuration.html`) en parallèle. Résultat réel : l'un
  des deux a réussi, l'autre a relu le fichier avant d'éditer, vu que
  c'était déjà fait, et a répondu `skipped_already_fixed` au lieu de
  planter ou d'écraser — la consigne « relis avant d'éditer, si déjà fait
  ne force pas » (donnée explicitement dans le prompt de chaque agent) a
  servi de filet de sécurité efficace pour ce cas non anticipé.
- **Consigne clé qui a bien fonctionné** : chaque agent devait, avant toute
  suppression de "code mort", grep le DÉPÔT ENTIER (pas seulement son
  fichier) pour vérifier l'absence d'appelant. Résultat : **5 correctifs
  correctement REFUSÉS** (`skipped_risky`) parce que la synthèse initiale
  n'avait grepé que le code de PRODUCTION, pas les fichiers de test —
  `nudge.level` (2x, coach.py+statusbar.js), `VOICE_MACROS_DEFAULT`
  (voicekeyer.py), `resume()` (spotfilter.py) ont un vrai appelant dans
  `tests/`. Aucun de ces 4 n'a été supprimé — le filet a fonctionné 2 étapes
  après le triage initial, sans intervention manuelle.

## Régressions réelles trouvées par la suite pytest COMPLÈTE, pas par relecture

Malgré une relecture manuelle ciblée (logx_http.py en entier, logx_callbook.py,
logx_iota.py, logx_utils.py) qui n'a rien détecté, la suite pytest complète a
trouvé 2 vraies régressions :
1. **`connected_peers`** : le fix "purger les pairs déconnectés" (perf-mineur,
   pas dans le lot différé précédent) a changé la structure de `set()` à
   `dict()` côté serveur (nécessaire pour stocker un timestamp par IP), mais
   2 fixtures pytest (`test_peer_versions_http.py`, `test_peer_version_xss.py`)
   monkeypatchaient encore `httpmod.connected_peers = set()` — l'agent,
   scopé à `logx_http.py` seul, n'avait aucune raison de regarder les tests.
   Corrigé manuellement (`set()` -> `{}` dans les 2 fixtures).
2. **`logx_coach.py`** : le `fix_plan` généré par l'agent de SYNTHÈSE lui-même
   disait littéralement "remplacer par `datetime.datetime.utcnow().date()`"
   — texte du plan lui-même faux, l'agent d'application l'a suivi fidèlement.
   Le dépôt a un test verrou (`test_utcnow_migration.py`, AST-based, interdit
   tout appel direct à `.utcnow()` dans `logx_*.py`) qui impose `utcnow()`
   depuis `logx_utils` (déjà importé dans ce fichier). Corrigé manuellement.
   **Leçon reconduite d'une leçon déjà connue** (voir `is_french` dans
   [[chantier-triage-et-correctifs-majeur-2026-08-12]]) : un agent de
   synthèse peut halluciner un détail d'implémentation même quand le
   root-cause est juste — ne jamais traiter un `fix_plan` comme vérité
   absolue, la suite de tests COMPLÈTE reste le seul filet fiable, pas la
   relecture manuelle ciblée (aussi minutieuse soit-elle sur les fichiers
   « à risque »).

## Piège technique rencontré en préparant le Workflow d'application

Voir [[piege-crlf-invisible-workflow-scriptpath]] — `Workflow({scriptPath})`
a rejeté le script généré ("control characters") à cause de `\r` invisibles
introduits par un `open(..., 'w')` Python en mode texte sur Windows, lors de
la génération intermédiaire des fichiers JSON embarqués. Fix : `newline=''`
sur CHAQUE écriture de la chaîne de génération.

## Chiffres finaux

- 162 constats mineur bruts -> 137 groupes dédupliqués -> 117 fix_now appliqués
  (82 fichiers touchés au total avec les 2 corrections manuelles), 11 rejetés,
  9 différés (documentés dans le message de commit PR #43, à reprendre
  seulement sur décision explicite de F4GLD).
- Pipeline complet : pytest 9010 verts, ruff propre, vérification navigateur
  sur 6 pages (LOGBOOK classe log-table confirmée, CHASSE fetch /config
  confirmé au réseau, CALENDRIER bascule d'onglet avec jeton de génération
  confirmée sans reste périmé, MODE NUMÉRIQUE contraste jour confirmé par
  capture d'écran au survol, ÉCRAN MURAL règle CSS day-mode confirmée par
  lecture de source).
