# Plan visuel & captures d'écran à fournir

> Les images de banque d'InVideo ne connaissent pas LogX AI. Pour un rendu crédible,
> on remplace le maximum de plans par de **vraies captures**. Voici la liste exacte,
> dans l'ordre du script, avec l'écran, l'état à préparer, et le **nom de fichier**
> à donner (range-les dans `docs/presentation/invideo/captures/`).
>
> **Astuce clé — pas besoin de radio branchée** : active le **MODE DÉMO** (CONFIG →
> Assistant IA → *Mode démo* = Oui). Le panneau **Opportunités** et le fil IA se
> remplissent alors de **spots synthétiques** étiquetés « DÉMO » — parfait pour
> filmer sans antenne. Pense à le **désactiver** pour les captures qui doivent
> montrer des données réelles (ton vrai carnet, tes vrais diplômes).
>
> **Conseil de tournage** : écran en **1080p**, curseur lent, **1 s de pause** entre
> les gestes, thème au choix (nuit = plus « poste de pilotage »). Capture en PNG.

## Assets déjà disponibles dans le dépôt (à réutiliser tels quels)

| Fichier | Usage |
|---|---|
| `docs/logoXAI.png`, `docs/logoXAI2.png`, `concours/logx_logo.png` | Logo intro/outro, filigrane de coin |
| `docs/presentation/logx_presentation_radioamateurs.html` | Ouverture animée (spectre) — **filme-la à l'écran** pour l'intro |
| `docs/presentation/logx_presentation_grand_public.html` | Plans de transition « grand public » |
| `docs/presentation/logx_presentation_technique.html` | Schémas d'architecture (2 couloirs, invariants) pour la conclusion |

## Captures à réaliser (ordre du script)

| # | Section script | Écran / geste à filmer | État à préparer | Nom de fichier |
|---|---|---|---|---|
| 01 | INTRODUCTION | Logo LogX AI plein écran (ou 1re slide de la présentation web #1) | — | `01_logo_intro.png` |
| 02 | LE PROBLÈME | *(banque InVideo : bureau encombré / multi-fenêtres — pas de capture app)* | — | *(stock)* |
| 03 | LA SOLUTION | Écran d'**accueil / cockpit** : opportunités + progression + état station + bouton **Reprendre** | Mode démo ON | `03_accueil_cockpit.png` |
| 04 | LA SOLUTION | Schéma **3 nœuds** (décodage → proposition → geste) | depuis présentation technique | `04_schema_3noeuds.png` |
| 05 | DÉMO — carnet | **LOGBOOK** : je tape un indicatif → auto-remplissage pays/distance/azimut | — | `05_saisie_enrichissement.png` |
| 06 | DÉMO — carnet | **Provenance par champ** (sous la saisie) : d'où vient chaque donnée | — | `06_provenance.png` |
| 07 | DÉMO — opportunités | Panneau **Opportunités** avec badge **DÉMO**, une fiche **dépliée** (FAIT / CALCUL / PROPOSITION) | Mode démo ON | `07_opportunites_deplie.png` |
| 08 | DÉMO — fil IA | Fil **« Ce que l'IA remarque »** en haut à droite, plusieurs lignes | Mode démo ON | `08_fil_ia.png` |
| 09 | DÉMO — après-QSO | Enregistrer un QSO → pastille **« +1 nouveau pays »** | — | `09_apres_qso.png` |
| 10 | DÉMO — émission | **FT8** : un décodage + la **barre de consentement** qui se prépare | — | `10_ft8_consentement.png` |
| 11 | DÉMO — émission | Boutons **ÉMETTRE** et **Stop TX** (+ optionnel : journal d'audit d'émission) | — | `11_emettre_stoptx.png` |
| 12 | DÉMO — concours | Sélection d'un concours + **bandeau score** + compte à rebours + bandeau **MULTS** | — | `12_concours_score.png` |
| 13 | DÉMO — concours | Écran **analyse de règlement** (URL/PDF → champs extraits, relecture humaine) | — | `13_analyse_reglement.png` |
| 14 | DÉMO — planif *(option)* | **Plan de session** : durée + objectif + bandes → plan par créneaux | — | `14_plan_session.png` |
| 15 | DÉMO — progression | Tableau de bord **diplômes** : DXCC / zones / départements, travaillé vs confirmé | données réelles | `15_diplomes.png` |
| 16 | DÉMO — station | Écran **Santé** : tuiles colorées (radio, rotor, FT8, callbook, synchro, DXCC, TX, conso IA) + horloge UTC | — | `16_sante_station.png` |
| 17 | DÉMO — multi-poste *(option)* | Carte d'**occupation des bandes** multi-postes | — | `17_multiposte_bandes.png` |
| 18 | DÉMO — autonomie | Config **IA** : choix du fournisseur + sélecteur **Mode local uniquement** + **Mode démo** | — | `18_config_ia_modelocal.png` |
| 19 | DÉMO — autonomie | Écran Santé zoomé sur la **conso IA en jetons** | — | `19_conso_tokens.png` |
| 20 | CONCLUSION | Schéma **architecture 2 couloirs** + **tableau des invariants** | depuis présentation technique | `20_archi_invariants.png` |
| 21 | CONCLUSION | Fondu **logo** + phrase finale « L'IA prépare. L'opérateur déclenche. » | — | `21_outro_logo.png` |

## Photos d'ambiance (optionnel, pour les respirations)

Si tu veux personnaliser les transitions plutôt que d'utiliser la banque InVideo :
antenne au coucher de soleil, poste HF, casque + manipulateur CW, pylône, station
portable en pleine nature (illustre l'autonomie). 3 à 5 photos suffisent.

## Règle de contenu (ne pas dépasser)

Ne montrer que ce que l'app fait **réellement** (copilotes en proposition seule,
sécurité d'émission, déterministe vs IA, autonomie, clé perso / mode local, HUD /
fil / après-QSO / santé / planificateur / cockpit / mode démo). Voir
`../logx_decks_claude_design.md` § « Rappels de contenu factuel ».
