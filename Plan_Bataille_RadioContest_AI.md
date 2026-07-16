# PLAN DE BATAILLE — RadioContest AI (F6KQJ)
**Date d'analyse :** 15 juillet 2026 — **mis à jour le 15 juillet 2026 : Phase 0 terminée ✅**
**Base :** repo GitHub `radioaamateur-program-Contest`, croisé avec `RAPPORT_RELECTURE_v3.md` (18 juin 2026)

---

## 1. ÉTAT DES LIEUX RÉEL

### Ce qui existe déjà (et c'est du sérieux)

- **Moteur de scoring générique** (`calc_qso_value`) : 10 types de scoring déjà implémentés (km, km×locators, km×grands carrés, zone/pays CQ, préfixes WPX, état/province ARRL, classe Field Day, département REF, sommet SOTA, parc POTA).
- **Base de 25 concours codés en dur** (`CONTEST_DEFINITIONS`) : tout le calendrier REF (RPH, National THF, Printemps, Été, CDF THF/HF SSB/CW, QRP, 160m), IARU R1 (VHF/UHF/50MHz/Marconi), CQ WW/WPX (SSB+CW), ARRL DX (SSB+CW), ARRL Field Day, SOTA, POTA.
- **Amorce de lecture automatique de règlements** : `fetch_contest_rules()` télécharge le PDF et en extrait le texte — mais par une regex maison sur les flux PDF bruts (pas de vraie lib PDF), et ce texte n'alimente que le **contexte de chat de l'IA**, pas la config structurelle de l'appli.
- **Chargeur de concours externes (WA7BNM)** : la fonction `fetch_wa7bnm_calendar()` existe et est appelée, mais `external_contests.json` est vide → le pipeline n'est pas encore branché bout en bout.
- **Copilote IA en direct** (`build_system_prompt`, 540 lignes) : recommande les meilleurs QSO en fonction du spot, de la propagation, de la distance et de l'impact sur le score.
- **Multi-clusters** : F5LEN, DXSummit, DXWatch, HamQTH, HamSpirit, DXMaps, ON4KST, cluster telnet — large couverture des sources de spots VHF/UHF et HF.
- **Depuis le rapport de juin, tu as déjà corrigé** : logbook.html complet, raccourci F9, export Cabrillo, mode jour/nuit (les 3 pages), validation temps réel du locator, champs EDI dynamiques (`ediClub`, `ediRName`...), gestion de clé API par provider.
- ~~**Reste en attente du rapport de juin** : backup automatique localStorage toutes les 5 min (item D — toujours absent).~~ **Vérifié le 15/07 : l'item D était en fait déjà implémenté** (`backupLog()` dans logbook.html : backup immédiat au démarrage + toutes les 5 min + affichage "Backup: HH:MM UTC" en pied de page). Le rapport de juin peut être classé.

### Le vrai diagnostic

Ton logiciel n'est **pas un logiciel générique qui lit un règlement et s'adapte** — c'est un logiciel qui gère très bien 25 concours **pré-câblés à la main**, avec une tentative d'IA de règlement qui ne fait qu'informer le chat, sans jamais reconfigurer l'appli elle-même. C'est le vrai chantier si tu veux tenir la promesse "n'importe quel concours, quasi automatique".

Deuxième diagnostic : c'est **un seul fichier Python de 4029 lignes** et **trois HTML de 1000 à 4000 lignes** avec logique et présentation mélangées. Ça marche, mais chaque nouvelle fonctionnalité devient plus risquée à ajouter sans casser l'existant — exactement la sensation de "on s'y perd" que tu décris, autant pour toi en dev que pour l'opérateur en session.

---

## 2. AXES D'AMÉLIORATION

| Axe | Constat | Impact |
|---|---|---|
| **A. Auto-adaptation réelle** | Le parsing de règlement n'alimente que le chat, pas le moteur de score | Bloque l'objectif n°1 de ta demande |
| **B. Couverture calendrier** | 25 concours FR/IARU/CQ/ARRL couverts ; gros contests EU manquants (WAEDC, UBA, EU Sprint, Stew Perry, All Asian, YOTA, Russian DX...) ; pipeline WA7BNM non branché | Bloque l'objectif n°3 |
| **C. UX / onboarding concours** | Config station+concours dans un seul `config.json` statique ; pas d'assistant "nouveau concours en 3 clics" | Cause directe du "on s'y perd" |
| **D. Dette technique** | 1 fichier de 4000 lignes pour le backend, logique métier mêlée au HTML | Ralentit toute évolution future |
| **E. Reliquat du rapport de juin** | Backup auto localStorage manquant | Petit, mais risque réel de perte de log terrain |
| **F. Fiabilité extraction PDF** | Regex maison sur bytes bruts, pas de vraie lib PDF | Base fragile pour l'axe A |

---

## 3. PLAN DE BATAILLE — 5 PHASES

### Phase 0 — Nettoyage et fondations ✅ TERMINÉE (15/07/2026)
- ~~Finir le reliquat du rapport de juin : backup auto localStorage (5 min).~~ Déjà implémenté (voir §1).
- ✅ `serveur.py` (4029 lignes) découpé en 8 modules + point d'entrée léger :
  `utils.py` (réseau, géodésie locator), `contest_definitions.py` (données concours),
  `storage.py` (log partagé + persistance), `rules.py` (dates, MAJ annuelle, WA7BNM),
  `scoring.py` (moteur de score), `clusters.py` (sources de spots), `prompts.py` (IA),
  `http_handler.py` (endpoints + do_refresh), `serveur.py` (démarrage, ~75 lignes).
  Vérifié : compilation, analyse des noms non résolus, aucun nom perdu, smoke test
  serveur réel (pages, /data/calendar, /data/rules_status, /log/status avec les 71 QSO,
  /chat, /data/external_contests). L'original est conservé dans `serveur.py.bak_pre_phase0`.
- ✅ **Bug corrigé au passage** : la route POST `/data/spots` (push des spots HF par le
  navigateur, car le serveur ne peut pas accéder à HTTPS) était dans `do_GET` avec un test
  `method == 'POST'` jamais vrai — elle ne fonctionnait donc **jamais**. Déplacée dans
  `do_POST`, testée OK. Le copilote IA reçoit maintenant vraiment les spots navigateur.
- ✅ `CONTEST_SCHEMA` formel créé : `contest_schema.json` (JSON Schema 2020-12, calé sur
  les 22 concours réels : 10 types de scoring, 21 règles de dates, 3 formats de log)
  + `validate_definitions.py` (garde-fou : 22/22 conformes). C'est le contrat que devront
  respecter les configs générées par l'IA (Phase 3) et les imports WA7BNM (Phase 4).
- Nota : la base contient 22 concours (et non 25 comme estimé initialement).

### Phase 1 — UX : ne plus jamais se perdre ✅ TERMINÉE (15/07/2026)
- ✅ **Assistant "Nouveau concours"** : le ▶ DÉMARRER du calendrier ouvre la config avec
  `?contest=ID` (paramètre qui existait mais n'était jamais lu !) → concours sélectionné,
  bandes/modes du règlement appliqués, dates auto-calculées, bannière récapitulative avec
  bouton "🚀 TOUT EST BON — LANCER". 3 clics : calendrier → DÉMARRER → LANCER.
- ✅ **Sélecteur de concours unifié** : la grille de `configuration.html` fusionne la liste
  locale + la base serveur (badge vert "✓ RÈGLEMENT SUIVI", 22 concours) + le calendrier
  WA7BNM (badge jaune "⚠ À CONFIRMER", visible dès que le pipeline Phase 4 sera branché).
  Badges identiques dans `calendrier.html`, avec bouton ▶ PRÉPARER sur les externes.
- ✅ **Barre de statut permanente** (`statusbar.js`, incluse sur les 4 pages) : concours
  actif · compte à rebours seconde par seconde (début dans X j / reste H:MM:SS / terminé) ·
  dernier backup log / config · date du dernier check règlements + alertes.
- ✅ **Mode débutant/expert** (bouton 🎚 dans l'en-tête de la config, persisté) : masque
  ASSISTANT IA, PROMPT SYSTÈME et toute l'étape 4 PROPAGATION (clusters, seuils, ON4KST,
  alertes) ; la navigation saute l'étape 4 dans les deux sens. Défaut : débutant si
  aucune station configurée, expert sinon.
- ✅ **Corrections au passage** : dates du concours héritées de la config précédente
  présentées comme "calculées" (l'assistant vérifie maintenant pour QUEL concours elles
  ont été calculées, et les champs sont vidés si non calculables) ; `/data/calendar`
  expose désormais `duration_h`/`start_utc` pour calculer début/fin côté client sans
  dupliquer les règles de dates ; la carte du concours sauvegardé n'était jamais
  surlignée au rechargement (attribut `data-id` manquant).
- Vérifié en conditions réelles dans le navigateur : flux calendrier → config → assistant,
  badges, mode débutant, compte à rebours live sur les 4 pages, aucune erreur console.

### Phase 2 — Moteur de score vraiment générique ✅ TERMINÉE (15/07/2026)
- ✅ Le `if/elif` géant de `calc_qso_value()` est remplacé par un **moteur à briques
  composables** (scoring.py) : règles de points ordonnées avec prédicats nommés
  (`same_country`, `different_continent`, `is_na`...), valeurs fixes / `per_km` /
  paramètres du règlement, 7 familles de multiplicateurs (`locator`, `large_square`,
  `zone_dxcc`, `prefix`, `dept_dxcc`, `na_section`, `na_state`), briques de validité
  (ex. Field Day : NA uniquement) et options transverses (bonus même carré, boost
  propagation, plafond ON4KST). Un concours jamais vu se déclare en JSON
  (`'scoring': {'bricks': {...}}`) sans coder de branche — c'est le format que
  produira la lecture IA de la Phase 3.
- ✅ Les 10 types historiques sont convertis via `LEGACY_SCORING_PRESETS` —
  **prouvé identique à l'octet près** : 44 064 comparaisons ancien/nouveau moteur
  (matrice stations × distances × bandes × états de log × sources × propagation),
  zéro différence sur les types vivants.
- ✅ **Bug majeur corrigé** : 4 types déclarés n'avaient EN FAIT aucune branche dans
  l'ancien moteur (`prefix_multiplier`, `power_state`, `summit_points`, `park_points`)
  — CQ WPX, ARRL DX, SOTA et POTA scoraient silencieusement 0. Ils scorent
  désormais réellement (WPX : points par continent × préfixes ; ARRL DX : 3 pts W/VE
  × états/provinces ; SOTA/POTA : points de base).
- ✅ Le moteur lit les paramètres déclarés dans les définitions (`points_dx`,
  `points_same_continent`, `same_square_bonus`...) au lieu de valeurs codées en dur.
- ✅ `contest_schema.json` étendu : un scoring est soit `type` (historique) soit
  `bricks` (composition explicite, entièrement décrite dans le schema).
  `validate_definitions.py` valide les briques **contre le moteur lui-même**
  (prédicats/familles importés de scoring.py — désynchronisation impossible).

### Phase 3 — Lecture automatique de règlement (la vraie IA) ✅ TERMINÉE (15/07/2026)
- ✅ **Extraction PDF fiable** (rules.py) : pymupdf (déjà installé) en premier choix, puis
  pdfplumber/pypdf si présents, regex maison en dernier recours ; pages HTML gérées aussi.
  Testé sur le règlement RPH local : texte propre et complet (vs charabia de l'ancienne regex).
- ✅ **Module `rules_ai.py`** : prompt d'extraction qui embarque le `contest_schema.json`
  complet et la grammaire des dates (auto-synchronisé — impossible de dériver), appel du
  fournisseur IA configuré (Anthropic/OpenAI/Gemini, même mécanique que le chat),
  **citations sources obligatoires** pour chaque champ, warnings explicites, et validation
  immédiate de la proposition contre le schema ET le moteur de score.
- ✅ **Relecture humaine obligatoire** : `/rules/analyze` ne sauvegarde JAMAIS rien. La
  proposition s'ouvre dans un modal de relecture (configuration.html, étape CONCOURS →
  « 🤖 ANALYSER UN RÈGLEMENT ») : chaque champ éditable avec sa citation du règlement
  dessous, erreurs de validation bloquantes, warnings de l'IA visibles. L'enregistrement
  passe par `/rules/save_definition` qui re-valide côté serveur.
- ✅ **Réutilisable chaque année** : les concours validés vont dans `custom_contests.json`,
  fusionnés dans la base au démarrage — dates recalculées annuellement comme les autres,
  badge « 🤖 IA + RELECTURE » dans le sélecteur, scoring par le moteur à briques.
- ✅ **Grammaire de dates étendue** : `calc_contest_date` accepte maintenant
  `{first..fourth|last}_full_weekend_{mois}` en plus des règles existantes — le vocabulaire
  est une grammaire ouverte (regex `DATE_RULE_PATTERN`, source de vérité unique pour le
  calcul, la validation et le prompt IA).
- Vérifié : 22 tests unitaires (grammaire, validation, persistance, parsing, pipeline avec
  IA mockée) + intégration serveur réelle (save/calendar/delete, avec date calculée juste)
  + cycle complet dans le navigateur (modal → enregistrer → badge → dates auto).
- ✅ **Premier test réel réussi (WAEDC, 15/07)** : définition de qualité extraite de la page
  DARC en anglais, briques choisies spontanément, restriction EU↔DX rattrapée en relecture
  puis encodée (`validity: different_continent`) et mults pondérés ×4/×3/×2 ajoutés.

### Phase 3+ — Extraction de classe mondiale ✅ TERMINÉE (16/07/2026)
Suite au test WAEDC réel, six renforts pour la polyvalence mondiale :
- ✅ **PDF natif** : avec Anthropic, le PDF part tel quel au modèle (vision) — tableaux de
  points, règlements scannés et mise en page compris. Fallback texte pour les autres
  fournisseurs et les gros documents (garde-fous 25 Mo / 90 pages).
- ✅ **Sortie JSON forcée** : tool use Anthropic (le `contest_schema.json` réel EST le
  contrat de l'appel), json_object OpenAI, responseMimeType Gemini — plus d'échec de parsing.
- ✅ **Passe de vérification adversariale** : un 2e appel relit le règlement contre la
  définition avec une checklist de 8 pièges (restrictions de participants, off-time, mults
  pondérés, points par bande, échange exact, heures UTC, QTC, deadline). Les corrections
  valides sont appliquées et tracées dans le modal de relecture ; une correction invalide
  est refusée avec warning. C'est le filet qui aurait attrapé le coup du WAE tout seul.
- ✅ **Multilingue explicite** : règlements DE/EN/ES/JA/RU... acceptés, définition en français.
- ✅ **Nouvelles briques** (issues du WAE) : règles de points filtrables par bande
  (WPX : 6 pts bandes basses) et `mult_weight_by_band` (WAE : pays ×4 sur 80m, ×3 sur 40m).
  Non-régression prouvée : les 44 064 comparaisons du test d'or restent identiques.
- ✅ **Partage communautaire** : export/import de `custom_contests.json` entre stations
  (boutons dans CONFIG → étape 2), chaque définition re-validée à l'import — une relecture
  humaine faite dans un club profite à tous.
- ✅ **Corpus d'évaluation** (`eval_extraction.py`) : 3 règlements réels avec champs attendus
  vérifiés à la main (RPH PDF français, WAEDC HTML anglais, CQ WW), scoring champ par champ,
  mode --no-verify pour mesurer l'apport de la vérification, --mock pour tester le harnais.
  À lancer avec ta clé (`set ANTHROPIC_API_KEY=...` puis `python eval_extraction.py`) après
  chaque évolution du prompt.

### Phase 4 — Couverture calendrier FR + Europe + Monde ✅ TERMINÉE (16/07/2026)
- ✅ **Pipeline WA7BNM enfin branché** : le parseur attendait du markdown alors que
  contestcalendar.com sert du HTML — il ne trouvait donc JAMAIS rien (d'où le
  `external_contests.json` vide depuis le début). Réécrit sur le format réel :
  **358 concours mondiaux 2026** (+ 2027) dans le cache, rafraîchi automatiquement
  au démarrage si le cache est vide, d'une autre année ou vieux de plus de 7 jours.
  Visibles dans l'onglet 🌍 MONDIAL du calendrier avec bouton ▶ PRÉPARER chacun.
- ✅ **13 gros contests EU/monde ajoutés à la base intégrée** (dates recoupées avec le
  calendrier WA7BNM fraîchement récupéré) : WAE SSB + RTTY (complètent le CW analysé
  par IA), UBA DX SSB/CW, European HF Championship, Russian DX, SP DX, HA DX,
  All Asian CW/SSB, Stew Perry Topband, ARRL 10m, ARRL 160m. Tous en briques
  composables, avec restrictions de participants encodées (SP DX : contacts SP
  uniquement via `prefix_in` ; All Asian : `is_asia` ; ARRL 160 : `is_na`) et
  barèmes incertains marqués « à confirmer via 🤖 » dans les notes.
- ✅ **Moteur enrichi au passage** : prédicats `is_asia`/`is_eu`, filtre `prefix_in`
  sur les règles de points (UBA : 10 pts pour un ON), validité par préfixes
  ({'prefix_in': ['SP',...]}), heure de début sur les règles week-end complet
  (`last_full_weekend_january_13h`). Test d'or 44 064 : toujours identique.
- Non ajoutés volontairement : EU Sprint et YOTA (éditions multiples courtes dans
  l'année — ne rentrent pas dans une règle de date unique ; passer par
  🤖 ANALYSER UN RÈGLEMENT au moment voulu).
- Total : **36 concours prêts à l'emploi** (22 d'origine + 1 analysé par IA + 13 Phase 4)
  + 358 concours mondiaux préparables en un clic.

### Phase 5 — Validation terrain
- Tester en conditions réelles sur un concours REF (retour rapide) puis sur un concours étranger nouvellement ajouté (validation du pipeline Phase 3).
- Ajuster l'ergonomie selon le retour F1OMQ/F1HAW/l'équipe F6KQJ.

---

## 4. ORDRE DE PRIORITÉ RECOMMANDÉ

1. **Phase 0** — sans ça, tout le reste devient plus dur à chaque étape.
2. **Phase 1** — répond directement à ta douleur "on s'y perd", gain immédiat, indépendant du reste.
3. **Phase 2** — condition technique pour que la Phase 3 ait un endroit où atterrir.
4. **Phase 3** — le morceau le plus ambitieux et le plus différenciant.
5. **Phase 4** — peut démarrer en parallèle dès la Phase 0 (ajout manuel de quelques contests majeurs pendant que le reste avance).

---

## 5. PROCHAINE ÉTAPE CONCRÈTE

**Phases 0 à 4 terminées (15-16/07/2026).** Il reste la **Phase 5 — validation terrain** : utiliser le logiciel en conditions réelles sur un concours REF (retour rapide), puis sur un concours étranger nouvellement ajouté, et ajuster l'ergonomie selon les retours F1OMQ/F1HAW/équipe F6KQJ. Prochaines occasions au calendrier : **EU HF Championship (01/08)**, **WAE DX CW (08-09/08)** — le concours analysé par IA, boucle bouclée — puis All Asian SSB (05-06/09) et WAE SSB (12-13/09). Penser aussi à lancer `eval_extraction.py` avec la clé API pour mesurer la qualité d'extraction.
