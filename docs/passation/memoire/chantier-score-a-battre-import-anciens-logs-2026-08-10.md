---
name: chantier-score-a-battre-import-anciens-logs-2026-08-10
description: Score à battre par concours (archives) + import ADIF/Cabrillo d'anciens logs jamais loggués dans LogX AI, PR #19
metadata:
  type: project
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-08-10T18:16:15.994Z
---

Demande F4GLD (10/08/2026) : « lorsqu'un concours est choisi je voudrais
que si le concours a déjà ete fait dans les années passées il faudrait que
le meilleur nombre de qso et de point obtenu apparaisse quelque part comme
score a battre ! » — puis, en observant qu'un tel bandeau resterait vide
pour tout ce qu'il n'a pas encore loggué dans LogX AI : « j'ai des logs de
concours que je n'ai pas encore importé en stock ! » (avec capture d'écran
d'une autre plateforme web de gestion de logs, ~10 logs de concours passés,
CRX/CRX-Log).

## Livré (PR #19, branche feat/score-a-battre-archives)

- `logx_archive.best_for_contest(contest_id)` : parcourt `list_archives()`
  filtrées par `contest`, lit chaque `log.json`, retourne le meilleur
  `qso_count` ET le meilleur score `points` — PAS FORCÉMENT LA MÊME ÉDITION
  (une année à beaucoup de QSO à 1 pt vs une année à moins de QSO mais
  multiplicateurs plus généreux). Endpoint `GET /log/archives/best?contest=`.
- UI : bandeau `#contest_best_score` (`expert-only`) sous la grille de
  concours en CONFIG, peuplé par `refreshContestBestScore(id)` appelée
  depuis `selectContest()`/`deselectContest()`.
- `logx_archive.import_external_log(text, fmt, contest_id, cfg, manual_score)` :
  importe un VIEUX log (ADIF via `logx_import.parse_adif_to_qsos()` déjà
  existant, ou Cabrillo via un parseur minimal maison `_parse_cabrillo()`)
  comme ARCHIVE PERMANENTE — jamais dans le log actif (sans rapport avec
  `/log/import_adif/*`, qui fusionne dans la session en cours). Endpoint
  `POST /log/archives/import`.
- UI : panneau `expert-only` "IMPORTER D'ANCIENS LOGS" (select format +
  select concours peuplé par `populateImportContestSelect()` depuis
  `CONTESTS` + champ score optionnel + input file) juste sous le bandeau
  score à battre.

## Décisions de conception notables

- **`archive_log()` a gagné un paramètre `when=None`** : sans lui, une
  édition de 2019 importée aujourd'hui se serait vue archivée sous la date
  du jour (le nom de dossier `<contest>_<YYYYMMDD-HHMMSS>` vient de
  `utcnow()`), donc affichée comme un record de CETTE année dans le score à
  battre — silencieusement faux. `import_external_log()` dérive `when` de
  la première date QSO trouvée dans le fichier importé.
- **Cabrillo n'a pas de parseur existant dans le dépôt** (seul
  `build_cabrillo()` en écriture existe, `logx_export.py`). `_parse_cabrillo()`
  écrit pour ce chantier est volontairement MINIMAL : n'extrait que les 4
  premiers jetons après `QSO:` (freq/mode/date/time — POSITION FIXE, norme
  Cabrillo v3, fiable) + `CLAIMED-SCORE:`. N'essaie PAS de parser
  l'indicatif DX ni le détail de l'échange (longueur VARIABLE selon
  `cabrillo_exchange` du concours) — inutile ici, `best_for_contest()` ne
  lit que `len(qsos)` et `sum(points)`, jamais le détail par-QSO d'une
  archive.
- **Répartition du score total** : ADIF ne transporte aucun point par QSO
  côté LogX AI (`parse_adif_to_qsos()` pose `points:0` partout), Cabrillo ne
  donne qu'un total (`CLAIMED-SCORE`). Le score connu (calculé ou
  `manual_score` fourni par l'opérateur) est posé entièrement sur le
  PREMIER QSO importé, les autres à 0 — hack assumé et documenté en
  commentaire, sans conséquence car `best_for_contest()` ne fait que sommer.
- **`manual_score`** : obligatoire en pratique pour l'ADIF (sinon score à
  0, seul le nombre de QSO est fiable) ; en Cabrillo sert de correctif si
  `CLAIMED-SCORE` est absent/faux, sinon le fichier fait foi.
- **`expert-only`** appliqué aux DEUX ajouts (bandeau + panneau d'import)
  dès la création, conformément au réflexe standing CLAUDE.md — aucun des
  deux n'est sur le chemin critique débutant.

## Piège de test rencontré (et évité proprement)

Un premier jet du test "meilleur QSO et meilleur score sur deux éditions
différentes" appelait `archive_log()` deux fois dans le même test → collision
de nom de dossier dans la MÊME SECONDE (`<contest>_<timestamp>-2`), que
`list_archives()` ne sait pas dater (regex `$` ancrée, piège déjà documenté
ailleurs en mémoire — [[chantier-archive-regex-collision]] si jamais créé).
Corrigé en écrivant les dossiers d'archive DIRECTEMENT (`_write_archive()`
helper dans le test) plutôt qu'en dépendant du timing réel de deux appels
successifs — cf. [[piege-artefacts-perimes-verification]] pour la famille de
pièges "état réel vs état simulé artificiellement".

## Vérification faite

Suite pytest complète verte (2 passes ; `test_amp.py` flaky sous charge une
fois, vert isolément — famille déjà documentée
[[suite-tests-flakes-sous-charge]]), `ruff check` propre, vérification
navigateur bout en bout sur port isolé 8099 (jamais 8080) : panneau visible
en mode expert (331 concours dans le select), import Cabrillo réel via le
VRAI chemin de code (fetch, pas un mock), bandeau confirmant "2 QSO / 500
pts (2024)" — l'année du LOG importé, pas la date du jour de l'import.

## Volet 2 (même PR #19, même branche, commit séparé) : extraction du script inline

`logx_configuration.html` (9339 lignes) contenait DEUX blocs `<script>`
adjacents jamais externalisés (contrairement à `logx_logbook.html`, qui a
eu 36 incréments EV-7) — demandé dans le MÊME message utilisateur, en
séquence après le score à battre. Interprété "extraire LE script inline"
(singulier) comme un déplacement en UN SEUL fichier, PAS une décomposition
EV-7 par fonctionnalité (le phrasé de F4GLD ne demandait pas ce niveau de
granularité).

- Extraction mécanique (script Python jetable, lignes 2958-3346 +
  3348-9337 vérifiées par assert avant toute écriture) vers
  `logx_configuration.js` (6375 lignes) ; le HTML retombe à 2960 lignes
  avec une seule `<script src="logx_configuration.js"></script>`.
- **Piège majeur, découvert par pytest et non anticipé avant coup** : **27
  fichiers de test** lisaient `logx_configuration.html` pour en extraire du
  JS (comptage d'accolades `_extract_function`/`_extract_braces`, regex sur
  des `const`/objets). Sur ces 27, **17 cassaient réellement** — les 10
  autres référençaient juste le NOM de fichier comme cible de lien/page,
  sans lire son contenu JS. Cassure en DEUX VAGUES : 8 fichiers cassaient
  dès la COLLECTE pytest (lecture au niveau module, donc visible tout de
  suite) ; 9 autres cassaient seulement à l'EXÉCUTION du test (lecture
  différée dans une fonction, invisible tant que pytest n'avait pas
  vraiment tourné) — la 2e vague n'a été trouvée qu'en relançant la suite
  complète une 2e fois après avoir cru le chantier fini. **Réflexe pour
  toute suite** : après avoir extrait du JS d'un fichier source, ne jamais
  se fier à un grep préalable pour lister les tests concernés — lancer
  pytest, lire les VRAIES erreurs de collecte ET d'exécution, corriger,
  relancer, jusqu'à un run propre.
- **Correctif appliqué, identique dans les 17 fichiers** : la variable qui
  contient la source lue (`_HTML_SRC`, `src`, selon le fichier) est
  complétée par le contenu de `logx_configuration.js` s'il existe, APRÈS
  celui de `.html` — même texte concaténé qu'avant l'extraction, donc
  aucune logique de test à réécrire, seulement le préambule de lecture.
  Motif dupliqué tel quel partout : `if os.path.exists(js_path): ... src
  += '\n' + f.read()`. Pour les fichiers avec un helper `_lire(nom)`/
  `_lire(path)` générique (utilisé pour PLUSIEURS fichiers différents),
  le if est conditionné au nom/chemin exact de `logx_configuration.html`
  pour ne pas polluer la lecture des autres fichiers.
- **Piège subtil trouvé dans ce lot** (`test_review_modal_zindex.py`) :
  un test CSS pur (z-index de `.cat-modal`) cassait alors que le
  sélecteur CSS réel (`.cat-modal{display:none}`) n'a JAMAIS eu de
  z-index — le texte que la regex trouvait réellement avant l'extraction
  était une PHRASE EN COMMENTAIRE JS (`// .cat-modal{z-index:9000} — donc
  chaque popup...`) qui matchait accidentellement le même motif. Confirmé
  par `git stash` (le test passait avant, échouait après, donc causé par
  l'extraction et pas préexistant) avant de corriger — ne jamais supposer
  qu'un échec CSS-only est sans rapport avec un refactor JS sans l'avoir
  vérifié.
- Vérification navigateur post-extraction (port isolé 8099, jamais 8080) :
  `typeof selectContest/refreshContestBestScore/init/CONTESTS` tous
  définis après chargement du fichier externe, sélection de concours
  fonctionnelle, aucune erreur console liée au JS (les `ERR_CONNECTION_
  REFUSED` observés une fois venaient d'un ancien process 8099 pas encore
  tué, pas de l'extraction).

## Reste à faire

- F4GLD a montré une capture d'écran d'une AUTRE plateforme web (CRX/CRX-Log,
  pas LogX AI) où dorment ~10 anciens logs de concours (LOG de Base 9882 QSO,
  TM43REF 1357, log coupe du ref 2024 583, etc.). Pas de scraping/accès
  automatisé fait ni proposé (identifiants d'un service tiers, hors
  périmètre) — réponse donnée : exporter chaque log en ADIF/Cabrillo depuis
  CE site (bouton "Importer/Exporter des QSO" visible sur la capture), puis
  utiliser le nouveau panneau d'import une fois la PR #19 mergée.
- PR #19 ouverte, NON fusionnée à la fin de cette session — attend
  l'autorisation explicite de F4GLD comme les PR précédentes.
