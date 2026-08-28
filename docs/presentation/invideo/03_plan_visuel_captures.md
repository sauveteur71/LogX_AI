# Plan visuel & captures — mappées au script

> **Les captures sont déjà faites** (dossier `captures/`), sur la vraie station
> (TM6KJS, ~10 000 QSO, 174 DXCC) — pas des images de banque. Ci-dessous, quelle
> capture va sur quelle partie du script `02_script_narration.md`, dans l'ordre.
>
> **Conseil InVideo** : garde chaque capture affichée pendant la phrase
> correspondante ; utilise la banque InVideo (ou tes photos de station) seulement
> pour l'INTRODUCTION et LE PROBLÈME, où il n'y a pas d'écran LogX AI à montrer.

## Assets déjà dans le dépôt (réutiliser tels quels)

| Fichier | Usage |
|---|---|
| `docs/logoXAI.png`, `docs/logoXAI2.png`, `concours/logx_logo.png` | Logo intro/outro, filigrane de coin |
| `docs/presentation/logx_presentation_radioamateurs.html` | Ouverture animée (spectre) — filme-la à l'écran pour l'INTRO |
| `docs/presentation/logx_presentation_technique.html` | Schémas d'architecture (2 couloirs, invariants) pour la CONCLUSION |

## Captures → script (dans `captures/`)

| Section script | Capture | Ce qu'elle montre |
|---|---|---|
| INTRODUCTION | *(logo + présentation web #1)* | Accroche, identité |
| LE PROBLÈME | *(banque InVideo : multi-fenêtres)* | Jongler entre dix outils |
| LA SOLUTION | `03_accueil_cockpit.png` | Cockpit « que faire maintenant » + choix d'activité (grandit avec l'op.) |
| DÉMO — carnet | `05_saisie_enrichissement.png` | **Plan héros** : indicatif résolu + provenance + fil IA + opportunités |
| DÉMO — carnet | `06_provenance.png` | D'où vient chaque donnée (fait sourcé vs calcul) |
| DÉMO — opportunités | `07_opportunites_deplie.png` | Fiche dépliée FAIT / CALCUL / PROPOSITION |
| DÉMO — fil IA | `08_fil_ia.png` | « Ce que l'IA remarque » |
| DÉMO — émission | `10_ft8_consentement.png` | FT8 natif + case « Activer l'émission » (consentement) |
| DÉMO — modes | `25_modes_numeriques.png` | FT8/RTTY/SSTV, fenêtres détachables, 2e écran |
| DÉMO — CW | `24_ecole_cw.png` | École de CW (« dans le casque, jamais sur l'air ») |
| DÉMO — concours | `12_concours_selection.png` | Base de règlements connus + « IA + relecture » |
| DÉMO — concours | `23_calendrier.png` | Calendrier des concours à venir (bulletin REF, DÉMARRER) |
| DÉMO — propagation | `22_propagation.png` | Bandes, ouvertures, cluster, carrés à reprendre |
| DÉMO — progression | `15_diplomes.png` | **Carte monde DXCC** : pays faits (vert) vs à faire (sombre) |
| DÉMO — multi-poste | `20_ecran_mural.png` | Écran mural d'expédition (QSO, ODX, carte, conditions) |
| DÉMO — planif | `14_plan_session.png` | Planificateur de session (durée/objectif/bandes) |
| CONCLUSION — autonomie | `18_config_ia_modelocal.png` | Fournisseurs IA + mode local + mode démo (BYOK, budget) |
| CONCLUSION — archi | *(présentation technique)* | Déterministe d'abord / invariants verrouillés |
| CONCLUSION — clôture | `docs/logoXAI.png` | Logo + « L'IA prépare. L'opérateur déclenche. » |

## Bonus disponibles (à glisser où tu veux)

| Capture | Ce qu'elle montre |
|---|---|
| `16_sante_station.png` | Écran Santé : tuiles + progression (bon pour « tout est prêt ? ») |
| `bonus_carte_ia.png` | Carte + COACH (nudges réels : « nouveau pays Fiji, appelle-le ! ») |
| `bonus_chasse_spots.png` | CHASSE : spots en direct classés |
| `26_bandscope.png` | Bandscope 2 m (cadre OK mais bande calme — visuel faible) |

## Deux visuels qui manquent encore (à toi de décider)

1. **Bannière de score/mults en direct** — n'apparaît que si un **concours est activé**
   (écriture de config). Dis-moi si tu veux que j'active temporairement un concours
   pour la capturer (puis je remets « aucun concours »), ou fais-le toi-même et je
   re-capture.
2. **Plan de session généré** (le vrai résultat, pas le formulaire) — nécessite ta
   **clé API** dans la config du serveur (le plan appelle le LLM). Configure-la et je
   génère + capture un plan réel.

## Photos d'ambiance (optionnel)

Antenne au coucher de soleil, poste HF, casque + manipulateur CW, pylône, station
portable en pleine nature (illustre l'autonomie / l'expédition). 3 à 5 suffisent,
pour les respirations INTRODUCTION / LE PROBLÈME.

## Règle de contenu (ne pas dépasser)

Ne montrer que ce que l'app fait réellement. Bornes : `../logx_decks_claude_design.md`
§ « Rappels de contenu factuel » et le script minuté `../logx_video_script_13min.md`.
