---
name: chantier-comparaison-opslog-et-flake-rotor-2026-08-06
description: "Comparaison factuelle LogX AI vs le logiciel concurrent OpsLog (F4BPO) ; flake de test réel trouvé et corrigé pendant le merge (course thread dans test_sat_track.py)"
metadata:
  node_type: memory
  type: project
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-08-06T12:03:12.783Z
---

L'utilisateur a collé la description complète d'un AUTRE logiciel radioamateur,
OpsLog (F4BPO, stack Go/Wails/React — pas dans ce dépôt), en demandant si LogX
AI fait "bien tout ça". Après clarification (AskUserQuestion), l'utilisateur a
choisi une comparaison factuelle catégorie par catégorie plutôt qu'un audit ou
une implémentation. Fait par un agent Explore qui a grepé le code réel plutôt
que de deviner depuis les noms de fichiers.

**Écarts réels confirmés** (LogX AI n'a pas) : OmniRig, API SmartSDR FlexRadio
native (LogX ne parle que CAT générique/rigctld/TCI), Icom CI-V à distance par
internet (protocole natif remplaçant RS-BA1), PowerGenius XL, ACOM (exclu
explicitement en commentaire code — "non documenté officiellement"), Antenna
Genius, panneau Station Control (relais WebSwitch/KMTronic/Denkovi), contrôle
de net (roster/log groupé), concepteur de cartes QSL (LogX ne fait que
stocker des scans de cartes déjà existantes), MySQL partagé/profils multiples,
constructeur de filtre avancé, télémétrie d'usage.

**LogX AI a en mieux** : 7 langues (vs bilingue EN/FR), amplis Elecraft
KPA500/KPA1500 réseau + Icom IC-PW2/PW-1 (absents de la liste OpsLog), keyer
vocal TTS dynamique multi-langue (vs WAV statiques), le concours (contest
logging) qui est le cœur historique de LogX.

**Partiel/différent notable** : diplômes DXCC/WAS/WAZ/WAC oui mais PAS
WPX/IOTA/POTA/SOTA/WWFF comme diplômes (existent côté LogX seulement comme
bases de spots pour la chasse) ; rotor via GS-232/rotctld (compatible serveur
GS-232 exposé par PstRotator) mais pas le protocole UDP natif de PstRotator ni
celui du 4O3A Rotor Genius ; coffre-fort AES-256-GCM sans phrase de passe
utilisateur (clé locale auto, protège contre l'exposition accidentelle du
fichier, pas contre un accès complet au poste).

## Flake réel trouvé pendant la fusion (pas dans le scope initial)

En fusionnant deux chantiers sans rapport (règle de langue française +
mise en page FT8 3 colonnes), la CI sur `main` a échoué sur
`test_les_NaN_du_rotor_ne_partent_pas_dans_le_JSON`
(`concours/tests/test_sat_track.py`) — aucun rapport avec les fichiers
fusionnés. `gh run watch` avait déjà signalé un "failed" prématuré une fois
plus tôt dans la session (cf. [[chantier-navigateur-mode-application-2026-08-06]]) ;
cette fois `gh run list` a confirmé un échec réel (`status:completed,
conclusion:failure`), pas une fausse alerte.

**Cause racine** : `demarrer_suivi()` (`logx_sat_track.py`) filtre
correctement les NaN/Inf du rotor de façon SYNCHRONE avant de démarrer un
vrai thread de fond. Le test ne neutralisait pas ce thread et relisait l'état
juste après `demarrer_suivi()` sans synchronisation — une pure course :
localement le thread n'a pas le temps de tourner avant l'assertion, sur un
runner CI plus chargé il a le temps de faire un tour et d'écraser
`rotor_az=None` par l'azimut CIBLE calculé (180.0, valeur du mock
`sp.position`, pas liée au bug NaN testé). Corrigé en neutralisant
`_boucle_suivi` via monkeypatch pour ce test précis — il ne teste que le
filtrage synchrone, pas le comportement de la boucle (déjà couvert ailleurs
dans le même fichier). Vérifié par 10 exécutions consécutives sans échec.

**Réflexe pour la suite** : un test qui démarre un VRAI thread puis lit
l'état immédiatement après sans join()/synchronisation est intrinsèquement
raciness, même s'il passe systématiquement en local — le comportement
d'ordonnancement des threads diffère selon la charge de la machine.

Livré : `46a0537` (langue), `13dc2e0` (FT8 3 colonnes), `acfb2e8` (correctif
flake), tous sur `main`, CI verte confirmée par double vérification
(`gh run watch` + `gh run list`).
