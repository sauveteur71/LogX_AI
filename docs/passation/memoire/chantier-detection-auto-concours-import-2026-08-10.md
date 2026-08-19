---
name: chantier-detection-auto-concours-import-2026-08-10
description: Détection automatique du concours à l'import d'un ancien log (ADIF/Cabrillo) dans le panneau score-à-battre, PR #21
metadata:
  type: project
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-08-11T04:58:49.818Z
---

Suite directe de [[chantier-score-a-battre-import-anciens-logs-2026-08-10]] :
F4GLD, après avoir compris que le panneau d'import demandait de choisir le
concours dans ~330 entrées : « il faudrait que je puisse télécharger
certains log de concours sans avoir à choisir le concours et qu'ils soient
reconnu si c'est possible ».

## Livré (PR #21)

- `logx_archive.guess_contest_id(raw_name)` : normalise (espaces/underscores
  → tiret, casse ignorée) et compare contre `CONTEST_DEFINITIONS` — soit la
  clé interne elle-même (la grande majorité des concours n'ont pas de
  `cabrillo_name` distinct, voir `build_cabrillo()` qui retombe alors sur
  l'ID interne), soit le `cabrillo_name` explicite (une douzaine de concours
  dont le code officiel diverge, ex. `CQ_WW_CW` → `CQ-WW-CW`, `REF_CDF_HF_SSB`
  → `CDF-HF-SSB`). `None` si rien ne correspond — jamais de déduction
  hasardeuse sur un archivage permanent.
- `_parse_cabrillo()` extrait maintenant aussi la ligne `CONTEST:` de l'en-tête
  (3e valeur de retour, appelants existants mis à jour).
- `import_external_log(text, fmt, contest_id=None, ...)` : `contest_id`
  devient optionnel. Vide → tente `guess_contest_id()` sur la ligne
  `CONTEST:` (Cabrillo) ou le tag `CONTEST_ID` du premier QSO ADIF qui le
  porte. Échec de détection → `{'ok': False, 'needs_manual': True, ...}`
  plutôt qu'un `contest_id` vide accepté silencieusement. Succès → le
  résultat porte `'contest'` (l'id retenu) et `'detected'` (bool) pour que
  le client affiche ce qui a été deviné.
- UI (`logx_configuration.js`) : `populateImportContestSelect()` ajoute une
  option `« — Détection automatique — »` (valeur vide) en tête, sélectionnée
  par défaut. `importOldLog()` n'exige plus un concours choisi ; sur succès
  affiche `« Importé pour X (détecté automatiquement) »`, sur échec de
  détection affiche un message clair + focus sur le select (repli manuel
  intact, jamais bloqué).

## Décision de conception

Détection **toujours visible et corrigeable**, jamais silencieuse : le
statut affiché nomme explicitement le concours retenu et précise "détecté
automatiquement" quand c'est le cas — l'opérateur voit ce qui a été deviné
avant que ce soit définitif (l'archive est déjà écrite à ce stade, mais le
nom du concours est visible immédiatement dans le message de résultat).
Cohérent avec le principe intuitivité CLAUDE.md (pas de magie invisible).

## Piège de test rencontré (attendu, pas une surprise)

`CABRILLO_SAMPLE` (fixture existante de [[chantier-score-a-battre-import-anciens-logs-2026-08-10]])
porte déjà `CONTEST: REF-160M` dans son en-tête — les 2 tests qui vérifiaient
« contest_id vide → erreur » (`test_import_sans_concours_refuse`,
`test_endpoint_import_sans_concours_400`) sont devenus des tests de succès
par détection automatique une fois ce chantier livré (comportement correct,
pas une régression). Corrigés en introduisant `CABRILLO_SAMPLE_SANS_CONTEST`
(même contenu, sans la ligne `CONTEST:`) pour tester spécifiquement le
chemin "rien à détecter" — `_parse_cabrillo()`/`import_external_log()`
changeant de signature (3-uplet, `contest_id` optionnel), tous les appelants
existants ont dû être revus, pas seulement les 2 tests en échec direct.

## Vérification faite

Suite pytest complète + `ruff check` verts. Navigateur réel (port isolé
8099) : select sur « Détection automatique » par défaut sans y toucher →
import d'un Cabrillo avec `CONTEST: REF-160M` → `« Importé pour REF_160M
(détecté automatiquement) : 2 QSO archivés »` ; import d'un Cabrillo SANS
ligne `CONTEST:` → `« Concours non détecté automatiquement — choisis-le
dans la liste, puis réessaie »` (repli manuel confirmé fonctionnel).

PR #21 fusionnée sur main le 10/08/2026.
