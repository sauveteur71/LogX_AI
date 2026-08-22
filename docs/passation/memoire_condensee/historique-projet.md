---
name: historique-projet
description: "Histoire condensée de LogX AI, de la Phase 0 (15/07/2026) à mi-août — fusion de ~140 fiches chantier individuelles (21/08/2026). Pour l'état ACTUEL et le travail en cours, voir docs/passation/PASSATION.md, pas ce fichier."
metadata: 
  node_type: memory
  type: project
  originSessionId: e5854853-072f-4b5f-895a-57c4ab0111d2
  modified: 2026-08-21T03:34:11.879Z
---

Consolidation du 21/08/2026. Les fiches d'origine (`chantier-*.md`, `radiocontest-phase0-done.md`, `qso-director-parity.md`, `rebrand-logx-ai.md`, etc.) restent archivées telles quelles dans `docs/passation/memoire/` (git-trackées, PR #118) — ce fichier est un résumé de navigation, pas le détail. Pour du détail ligne-à-ligne d'un chantier précis, remonter au fichier d'origine ou à `git log`/aux PR GitHub, qui font autorité sur le « quoi a changé exactement ». **Pour l'état actuel du projet et le travail en cours, lire `docs/passation/PASSATION.md` — c'est lui la source vivante, ce fichier-ci s'arrête à mi-août 2026.**

## Genèse — Phases 0 à 5 (15-19/07/2026)

Le projet est né `RadioContest AI` (renommé `LogX AI` le 20/07). Phase 0 : découpage du monolithe `serveur.py` (4029 lignes) en modules, `contest_schema.json` comme contrat formel. Phase 1 (UX) : statusbar, assistant nouveau concours, mode débutant/expert. Phase 2 : moteur de score générique à briques (`calc_qso_value`), équivalence prouvée par 44 064 comparaisons contre l'ancien moteur. Phase 3 : lecture IA des règlements (PDF natif Anthropic, sortie JSON forcée, checklist de vérification adversariale à 8 pièges). Phase 4 : calendrier WA7BNM, 13 concours EU/monde ajoutés. `eval_extraction.py` : 19/19 champs corrects.

Suivent dans la même poussée (16-19/07) : coach stratégique déterministe (le LLM ne sert QUE via le bouton dédié, jamais à décider un score), CAT natif (CI-V/ASCII, autodétection), rotor rotctld, TCI (WebSocket écrit à la main, aucune lib dispo), pont WSJT-X (auto-log FT8/FT4), QRZ.com, propagation (solaire N0NBH, MUF ionosonde, tropo, météores, RBN, grey-line, carte de propagation mondiale 24h), archivage par concours, packaging PyInstaller autonome, i18n 8 langues (moteur par correspondance de texte, pas de balises), agent IA multilingue, carnet permanent (déjà-contacté, diplômes, QSL, band map), pilotage radio CAT natif complet (recherche manufacturer, bug BCD Icom corrigé avant codage), mode expédition (écran mural, Club Log Live).

**Durcissement sécurité du 16/07** : traversée de répertoire, secrets sortis de git, auth token, CORS restreint. **Audit du 20/07** : 113 constats confirmés dont une vraie clé API en clair (révoquée), traversée de fichiers non authentifiée, perte totale du log si `logx.db` verrouillé au démarrage — tous corrigés le jour même.

## Roadmap « dépasser QSO Director » (17-19/07/2026) — 10/10 items + extras

Analyse comparative demandée par F4GLD contre un concurrent. Livré un par un : activation POTA/SOTA/IOTA/WWFF (puis ARLHS/WCA), bandscope/activité de bande, callbook en cascade QRZ→HamQTH→HamDB, toggles cluster individuels (code mort `fetch_dxwatch_hf` découvert au passage — jamais branché), QSO Upload unifié (QRZCQ + HRDLog, protocole reverse-engineered depuis une lib cliente open-source), constructeur de règles d'alerte, layouts nommés + détachement généralisé, Cloud Sync (3 niveaux, anti-collision par fichier propre à chaque poste), réseau ADIF générique (protocole N1MM UDP `<contactinfo>`, vérifié contre la doc officielle plutôt qu'inventé), import ADIF (cassé depuis toujours, corrigé). Puis Worked Matrix + Great Circle en extra (§3.9). **Motif récurrent** : creuser sérieusement chaque item de roadmap a systématiquement débusqué un bug préexistant (code mort, champ jamais posé, détection silencieuse) — la comparaison externe a servi de prétexte à un audit qualité.

**Piège répété 4 fois pendant cette période** : naviguer vers `carte.html`/`configuration.html` en vérification reposte le `localStorage` périmé du navigateur de test vers `/config/save`, qui REMPLACE toute la config (jamais de fusion) — a effacé la vraie clé API à plusieurs reprises, restaurée à chaque fois. Règle stricte qui en a résulté : ne jamais naviguer vers ces deux pages en vérification, piloter par `fetch()` depuis une page sûre (calendrier/logbook/départements/propagation), toujours avec un payload de config COMPLET.

## Robustesse réseau et diffusion publique (20-22/07)

F4GLD a cadré : diffusion publique à des inconnus, jamais de blocage pour IP figée/antivirus/absence réseau (usage terrain en zone blanche = cas central). Audit dédié (46+14 constats) : appels réseau externes synchrones dans le thread HTTP avec timeouts cumulables jusqu'à 80s, voire blocage indéfini (Cloud Sync sur un dossier cloud en mode placeholder). Corrigé par un patron uniforme (`fetch_url()` avec `ThreadPoolExecutor` + timeout dur, disjoncteurs, deadline recalculée à chaque `recv()` de boucle telnet) réutilisé depuis pour tout nouvel appel réseau du projet.

Le 21/07 : correctif de la portée concours+année (`shared_log` est un log global unique — un motif bogué traitait un QSO sans tag concours comme un joker pour N'IMPORTE QUEL concours filtré). Introduit `qso_scope_id`/`active_scope_id`/`cfg_scope_id` (`logx_storage.py`), désormais la référence pour tout filtrage par concours.

Distribution aux amis testeurs (22/07) : 19 vrais défauts trouvés dont le chat multi-op totalement mort depuis des semaines (4 bugs empilés après un refactoring d'id HTML, invisible faute de grep global après renommage). Publication `LogXAI.exe` v0.9-beta1, historique git purgé des données perso.

## Grande vague de fonctionnalités et de qualité (fin juillet - début août)

- **DXpéditions + décodeur CW + POTA/SOTA/WWFF/IOTA/WCA** (22/07) : contrainte retenue durablement — en expédition les postes tournent jusqu'à 15 jours 24h/24, toute fuite de ressource devient fatale à cette échelle (mesurer sur des milliers de cycles, pas des tests courts, et vérifier si la courbe plafonne avant de conclure à une fuite).
- **Vocabulaire radioamateur imposé** (30/07) : voir `regles-produit-permanentes.md`.
- **i18n approfondi** : ~190 chaînes JS fabriquées trouvées, 5 pages ne chargeaient pas le moteur i18n du tout (bande/mobile/panel/scope/wall — même famille que l'absence de thème jour/nuit sur ces mêmes pages).
- **Audit pré-bêta** (05/08) : 58 correctifs, 2 critiques.
- **Panadapter audio + scope CI-V** (04/08) : un bug critique invisible à 43 tests verts.
- **Keyer vocal** : synthèse TTS multi-voix/multilangue en local (Piper).
- **Design « graphite & cuivre »** (03/08) : refonte visuelle complète + icônes monochromes, piège SVG sans `width`/`height` généralisé après coup.
- **Audit sécurité/qualité** (02/08) : 94 correctifs + revue post-fusion (21 constats de plus, dont un jeton LAN diffusé en clair, du XSS résiduel, une fonctionnalité de sécurité jamais câblée côté UI).
- **Étude « apports IA »** (01/08) : sur 6 évolutions livrées comme améliorations IA, 4 étaient en réalité des bugs corrigés.
- **Campagne EV-7** (fin juillet - 09/08) : factorisation progressive de `logx_logbook.js` (monolithe ~6300 lignes au départ) en modules `logx_*.js` séparés, par incréments prudents guidés par des inventaires Workflow successifs (16e, 23e, 3e-27e...) classant chaque candidat FAIBLE/MOYEN/ÉLEVÉ selon sa dépendance au chemin critique (`setupDone`, `submitQSO`, `renderLog`, `bearing`/`cardinalDir`…). Synthèse : ~36 incréments, ~7500→3668 lignes. Piège de méthode récurrent et bien documenté : un appel TOP-LEVEL oublié dans le fichier hôte casse tous les tests qui évaluent le fichier en entier, pas seulement ceux liés à la fonctionnalité extraite (voir `pieges-techniques.md`).
- **Lint ruff en CI** (10/08), **dialogues non bloquants** (alert()/confirm() natifs remplacés), **VOACAP embarqué** (voacapl.exe natif compilé, endpoint dédié), **École CW**, **designer de carte QSL imprimable**, **score à battre + import anciens logs**, **détection auto du concours à l'import**.

## Deuxième vague d'audits (11-12/08)

Audit sécurité/obsolète/bugs (11/08) : RCE via `autostart_programs` + 3 XSS — corrigé, bind par défaut passé de `0.0.0.0` à `127.0.0.1` (accès LAN devient un opt-in explicite). Réorg nav + fusion PROPAG/FOCUS. Deux passages d'audit "triage" massifs (12/08) : 2e passage à 617 agents en boucle jusqu'à épuisement (322 constats, 20 critiques dont un LOGBOOK cassé en prod), puis triage sémantique (~55 correctifs majeurs), puis triage des 162 constats mineurs restants (117 corrigés). Build de release resté cassé 2 jours sans que personne le sache (`Tree()` vs `Analysis()` PyInstaller) — leçon : toujours vérifier un tag via un vrai build local, jamais seulement via le code source.

**Version 1.0** publiée le 12/08 (i18n MODE NUMÉRIQUE/RTTY/FT8 corrigé, release multi-OS).

## Mi-août : refonte structurelle, radio-club, panneau CONFIG, sécurité

- **Analyse concurrentielle approfondie** (10/08, contre Wavelog/GridTracker2/AllMySat/SmartLogger/World Radio League/Log4OM) : atouts confirmés (CAT natif multi-marques inégalé, suivi satellite avec pointage rotor auto, codec FT8 propre, IA intégrée), lacunes réelles comblées (protection anti-écrasement concours perso, prefetch POTA/SOTA/WWFF au démarrage, diplôme zones ITU).
- **CAT plug-and-play** (03/08) puis **décodeur CW + 5 évolutions issues d'une 2e veille concurrentielle** (15/08 : upload LoTW auto, bandmap multi-bandes, upload POTA, mini-grille progression bande×mode, clavier CW matériel) — occasion de la règle « jamais citer un concurrent ».
- **Lot 1 pré-déploiement RADIO-CLUB** (18/08, PR #108) : sécurité CW, id QSO, filet d'erreurs — la revue adversariale a trouvé 3 défauts DANS le lot, dont 2 qui retournaient les correctifs contre leur but.
- **CONFIG plein écran + fermeture uniforme vers LOGBOOK** (16/08, PR #103), point statut 17 champs secrets (PR #104).
- **CARTE IA détachable + backlog clos** (13-18/08) : bandeau connectivité, projection de score, VOACAP 12 mois. OCR carnet papier explicitement abandonné (13/08, décision F4GLD — ne plus reproposer).
- **AUDIT ARCHITECTURE COMPLET** (18/08, 32 agents, 6,2M jetons) : cartographie + top 10 valeur/effort. A tranché deux points ouverts de F4GLD (règle K≥5 déjà supprimée du code ; l'indice A solaire est calculé mais n'atteint JAMAIS le contexte de l'IA malgré deux commentaires qui l'affirmaient — leçon générale : un commentaire qui affirme un comportement n'est pas une preuve, grep le chemin réel). Question de positionnement (concours+expédition vs carnet généraliste) laissée ouverte à F4GLD.
- **Décision de renommage de dépôt planifiée** (12/08, pas encore faite à cette date) : rapatrier le code sur `sauveteur71/LogX_AI` plutôt que sur `radioaamateur-program-Contest` — voir `decisions-produit-et-references.md`.

## Où s'arrête ce fichier

Le 19/08/2026, la perte du carnet (9871 QSO), les garde-fous qui en ont suivi (PR #127), le séquenceur FT8 automatique, et tout le chantier FT8 natif (natif, décodage en Web Worker, séparation de fréquence, VOX sans CAT…) qui a suivi jusqu'au 20-21/08 (v1.1-beta5 puis beta6) sont documentés dans `docs/passation/PASSATION.md`, à jour et faisant autorité pour cette période — ne pas dupliquer ici.
