---
name: analyse-concurrence-logx-ai-2026-08-10
description: "Analyse concurrentielle (Wavelog, GridTracker2, AllMySat, SmartLogger, World Radio League, Log4OM, OpenHPSDR-Thetis) + 3 chantiers actionnables qui en découlent"
metadata: 
  node_type: memory
  type: project
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-08-10T14:03:20.618Z
---

Demandé le 10/08/2026 : analyser GridTracker2 (dossier local Electron) et Wavelog
3.1.0 (source local + GitHub) + recherche web sur 4 autres concurrents, plus un
changelog Log4OM collé par l'utilisateur. Fait via Workflow (7 agents : 2 lecture
de code local, 5 recherche web), synthèse + vérification manuelle croisée dans le
code réel de LogX AI avant toute conclusion (grep systématique, pas de confiance
aveugle aux affirmations des agents). Artefact publié :
https://claude.ai/code/artifact/139be3e1-56eb-4397-b293-d8ea41f5c420

## Constats principaux (vérifiés dans le code, pas supposés)

**Atouts LogX AI confirmés, pas juste perçus** :
- Pilotage CAT natif multi-marques (CI-V/Yaesu/Kenwood/Hamlib/OmniRig/FlexRadio) —
  aucun des 7 concurrents ne va aussi loin ; Log4OM lance tout juste CAT4OM pour
  rattraper ce retard.
- Suivi satellite avec **pointage automatique du rotor** pendant le passage
  (`logx_sat_track.py` — pré-pointage avant l'AOS, arrêt au LOS) — plus poussé que
  Wavelog (juste des prédictions) ou AllMySat (aide au pointage manuel/AR).
- Codec FT8 propre écrit en JS pur — les compagnons WSJT-X (GridTracker2 inclus)
  se contentent d'écouter le flux UDP d'un WSJT-X déjà installé.
- Assistant IA intégré — aucun concurrent étudié n'en a.

**Vraies lacunes identifiées** :
- Pas de designer visuel de carte QSL imprimable (Wavelog/Log4OM/WRL en ont tous
  une forme) — pas encore traité, reste le chantier #371 (designer minimal
  PNG/JPG, différé, plus gros scope que les 3 autres).
- Catalogue de diplômes plus étroit que Wavelog (20+) — traité, voir
  [[chantier-audit-diplomes-vs-concurrence-2026-08-10]].
- ~~Pas de prédiction VOACAP point à point~~ — décision initialement assumée de
  NE PAS le construire (gros projet scientifique), **réexaminée le jour même** :
  F4GLD a explicitement demandé d'engager ce chantier après tout. Voir
  [[chantier-voacap-moteur-point-a-point-2026-08-10]] — vrai moteur NTIA/ITS
  compilé nativement pour Windows (pas une approximation), UI point-à-point sur
  LOGBOOK + vérification à la demande sur CARTE IA.
- Ne pas copier le modèle « leaderboard cloud public » de World Radio League —
  décision assumée : positionnement structurellement différent (poste local vs
  cloud spectateur), changement d'architecture majeur pour un bénéfice incertain.

## Les 3 chantiers actionnables déjà faits (PR #11, #12, #13, tous mergés)

1. **Protection anti-écrasement des concours perso** (PR #11) — vérifié que
   `logx_bootstrap.bootstrap()` protège déjà `custom_contests.json` d'une
   mise à jour (garde `if not os.path.exists(dst)`, copie une seule fois au
   1er lancement). La garantie existait déjà dans le code mais n'était ni
   testée ni énoncée explicitement — 4 tests ajoutés + commentaire explicite.
   Inspiré du pattern Log4OM « rapports protégés + sauvegarde/restauration
   automatique ».
2. **Prefetch POTA/SOTA/WWFF/IOTA/WCA au démarrage** (PR #12) — ces bases
   n'étaient chargées qu'au tout premier appel de `/activation_db/search`
   (1re frappe dans MA RÉFÉRENCE ACTIVÉE), laissant une fenêtre vide de
   plusieurs secondes sur un poste neuf. Même patron que cty.dat/TLE/LoTW déjà
   préchargés en tâche de fond dans `logx_serveur.py`. Inspiré de Wavelog qui
   peuple ces mêmes référentiels dès sa migration de mise à jour.
3. **Diplôme zones ITU** (PR #13) — voir
   [[chantier-audit-diplomes-vs-concurrence-2026-08-10]] pour le détail.

## Piège de vérification navigateur rencontré (chantier 3, zones ITU)

Après avoir édité `logx_awards.py` (Python, backend), le panneau DIPLÔMES du
serveur de dev déjà lancé (port 8080, jamais redémarré — règle permanente)
n'affichait PAS la nouvelle ligne, MÊME après un rechargement JS forcé
(fetch+eval du script frais, confirmé contenir bien le nouveau code). Cause :
un fichier `.py` édité sur disque n'est PAS rechargé par un process Python déjà
lancé — contrairement à un `.js` statique, re-fetché à chaque requête HTTP par
le serveur sans aucune mise en cache côté Python. Diagnostiqué en confirmant
d'un côté que `fetch('/logx_awards.js?bust=...')` renvoyait bien le nouveau
JS, et de l'autre qu'un **nouveau process Python séparé** (`python -c
"import logx_awards..."`) calculait bien la nouvelle donnée correctement sur
le vrai log — donc le code était juste, seul le process serveur DÉJÀ EN COURS
avait l'ancienne version en mémoire. Ne PAS redémarrer le serveur de prod pour
vérifier un changement Python — s'appuyer sur un process Python isolé +
la suite pytest complète à la place.
