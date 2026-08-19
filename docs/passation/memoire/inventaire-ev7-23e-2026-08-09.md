---
name: inventaire-ev7-23e-2026-08-09
description: "EV-7 : 2e inventaire Workflow complet (21 candidats évalués) après épuisement de la liste FAIBLE du 16e incrément — 5 candidats FAIBLE recommandés, 15 à éviter/prudence documentés avec raison précise"
metadata:
  type: project
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-08-09T00:52:30.979Z
---

2e inventaire Workflow complet de la campagne (le 1er est
[[inventaire-ev7-16e-candidat-2026-08-08]]), lancé après épuisement des 6-7
candidats FAIBLE identifiés au 16e incrément (16e-22e incréments extraits).
`logx_logbook.js` fait désormais ~5033 lignes (contre ~6310 au début).
3 phases (cartographie → évaluation parallèle de 21 candidats ≥60 lignes →
synthèse), ~3.2M tokens, 708 appels d'outils, ~25 min.

## 5 candidats FAIBLE recommandés (par ordre de sûreté)

1. ~~**Moteur de correspondance du filtre avancé** — `matchesAdvancedFilter`~~
   **REJETÉ, ne pas extraire malgré le score "le plus sûr des 21
   candidats"** : le bloc porte lui-même un commentaire explicite
   (`concours/logx_logbook.js` juste avant `FILTER_FIELDS`) documentant
   qu'une revue adversariale ANTÉRIEURE a délibérément choisi de le garder
   dans `logx_logbook.js` — le sens inverse (moteur dans un fichier
   extrait) ferait dépendre `renderLog()` (chemin critique, jamais déplacé)
   d'un fichier "fonctionnalité optionnelle", violant la convention EV-7
   établie (cœur ne dépend jamais d'un fichier optionnel, même via un garde
   conditionnel comme `advancedFilter && matchesAdvancedFilter(...)`).
   L'agent d'évaluation de cet inventaire a bien repéré l'appel technique
   mais a mal pesé sa gravité face à cette décision déjà actée et
   documentée dans le code — retenir la leçon : toujours lire le
   commentaire d'en-tête existant d'un bloc AVANT de faire confiance au
   verdict FAIBLE d'un inventaire, un bloc peut porter sa propre
   justification d'exclusion invisible à une évaluation purement
   technique/statistique.
2. **Export ADIF + CSV** — `buildAdifText` (+ `ADIF_BAND`/`adifBandLabel`/
   `exportCSV`), 112 lignes. Bornes nettes, 1 seul site d'usage externe
   (`logx_filter_builder.js`, corps de fonction). 2 fichiers de test au
   motif JS_EXTRAITS_EV7 déjà éprouvé.
3. **Édition QSO** — `editQSO`/`saveEdit` (+ `renderEditExtraFields`/
   `deleteQSO`/`undoLastQSO`), 206 lignes. 12 identifiants grepés
   exhaustivement, zéro top-level, zéro appel depuis les 4 fonctions cœur
   inspectées intégralement. 1 seul fichier de test dédié.
4. **Exports EDI + Cabrillo** — `exportEDI`/`exportCabrillo` (+
   `ediSerial`/`remindSubmitLog`), 212 lignes. Seul point d'entrée externe :
   le dispatch générique par nom du menu (`window[fn]()`, agnostique).
   1 piège classe 3 bien circonscrit (`test_cabrillo_conforme.py`,
   correctif d'une ligne), 3 fichiers de test au total.
5. **Sélecteurs OPÉRATEUR/BANDE/MODE + fréquence** — `pickBand`/
   `setFreqForBand` (+ `pickOp`/`pickMode`/`onFreqInput`/`freqFromRig`),
   198 lignes. Tous les sites externes en corps de fonction. Point de
   vigilance : `test_export_adif_client_bande.py` (jamais touché par un
   incrément précédent) à mettre à jour EN PLUS de
   `test_macro_cw_serie_bande.py`.

## Candidats ÉLEVÉ (à ne jamais reproposer)

- **SAISIE — onCallInput/bearing/cardinalDir/submitQSO/clearForm**
  (L2489-2774, ~286L) : `bearing()`/`cardinalDir()` appelées directement
  par `renderLog()` (chemin critique déjà exclu) et `updateBandRecap()` —
  déborde vers le rendu intouchable. **Piège classe 3 le plus dangereux
  trouvé : un FAUX VERT SILENCIEUX** dans `test_busted_call.py`
  (`js.find()` renvoie -1, l'assertion passe quand même sans détecter la
  régression).
- **Pipeline de synchronisation du log** — `fetchLog`/`_mergeLogDelta`/
  `syncOfflineQueue`/`backupLog`/`startRefresh`/`initShareLink`
  (L2987-3156) : couplage bidirectionnel avec les 2 blocs ÉLEVÉ déjà exclus
  (état global + renderLog). `setupDone()` appelle `startRefresh()` ET
  `fetchLog()` directement. `fetchLog()` est la boucle de poll centrale
  (5s) — régression y serait silencieuse en plein concours multi-poste.
- **Préremplissage modal démarrage** — `prefillSetupFromConfig` : appelle
  DIRECTEMENT `setupDone()` en son propre corps — prolongement du bloc déjà
  exclu, pas une extraction indépendante.

## Candidats MOYEN (prudence particulière, raison précise documentée)

- **Menu DÉBUT/FIN + `applyUsageModeToLogbook`** : mélange 2 sous-systèmes,
  contrainte d'ORDRE entre 2 symboles qui doivent rester ensemble.
  Recommandation : scinder en 2 plutôt qu'extraire tel quel.
- **Mode activation POTA/SOTA/IOTA/WWFF** — `ACT_MIN`/`applyActivationMode`/
  `refreshActivation` : piège classe 2 (`submitQSO()` → `refreshActivation()`).
  **NE SURTOUT PAS inclure `nextRPHWeekendUTC()`/`CONTEST_SCHEDULE`** —
  `CONTEST_SCHEDULE` contient un appel TOP-LEVEL (IIFE) qui casserait
  ~25 fichiers de test d'un coup si déplacé avec le reste.
- **Scoring piloté serveur** — `calcPoints`/`evalPointsFromDef`/`calcDist` :
  `locLL()`/`hav()` partagées avec `bearing()` (bloc SAISIE cœur), appelé
  par `renderLog()` pour CHAQUE ligne dès qu'un locator ≥6 caractères est
  présent — 6+ fichiers de test impactés.
- **QSO Timer** — `updateQsoTimer`/`isDup`/`nextSerial` : `setInterval`
  top-level cible une fonction du MÊME bloc — doit partir d'un seul tenant,
  pas de cherry-pick possible.
- **Band map complet** (396L, le plus volumineux) : 3 fichiers de test à
  extraction par sous-chaîne distincts. Recommandation : scinder en 2
  incréments (liste+filtre+S&P / bandscope+waterfall).
- **Enregistreur audio par QSO** : piège classe 1 confirmé
  (`initAudioRecorderPanel()` top-level L1886) — 16 fichiers de test à
  mettre à jour.
- **Affichage panneaux CW/RTTY/SSTV selon le mode** —
  `updateKeyerPanels`/`toggleCwPanelForce` : piège classe 1
  (`setTimeout(updateKeyerPanels,300)` top-level) — 16 fichiers de test.
- **Bandes & modes par concours + `escHtml` embarqué** : `escHtml()` est un
  utilitaire XSS générique consommé par 13+ fichiers, sans rapport
  thématique, présent par proximité physique — à garder dans
  `logx_logbook.js`, n'extraire que les tables/rendus bandes-modes. Piège
  classe 2 sur `test_peer_version_xss.py` (ReferenceError).
- **Statut de version + mise à jour réseau** : piège "dépendance cachée via
  un 3e fichier déjà extrait" confirmé (`logx_verif_panel.js` ET
  `logx_lookup.js` appellent de vraies fonctions du bloc). Touche un test
  de SÉCURITÉ (`test_peer_version_xss.py`).
- **Tableau de bord de rythme** — `updateStats`/`updateBandRecap`/
  `drawHourChart` : 8 fichiers de test impactés dont 2 nécessitant une
  VRAIE réécriture de logique de test.
- **Macros F1-F8** — `getMacros`/`expandMacro`/`copyMacro` : découpage
  NON-CONTIGU obligatoire (3 segments distincts) en excluant précisément
  `trT`/`trF`/`notify`/`adaptivePoll` entrelacés (utilisés 237 fois sur
  21 fichiers) — risque structurel de découpe, pas d'exécution.
- **Chat multi-opérateur + vue Partner** : piège classe 2
  (`clearForm()` → `broadcastTyping()`). `_reserveBottomSpace()` est un
  utilitaire DOM générique sans rapport avec le chat, consommé aussi par
  `logx_sstv_panel.js` et le panneau CW.
- **Wrappers décodeur CW + utilitaires audio génériques** : 2 sous-systèmes
  sans rapport réunis par adjacence textuelle seulement.

## Suite

Le 23e incrément cible le candidat n°1 (Moteur de correspondance du filtre
avancé, `matchesAdvancedFilter`, 62 lignes). Pour les suivants, reprendre
cette liste dans l'ordre — les numéros de ligne cités ici seront périmés
dès le 1er incrément suivant, relocaliser par grep de fonction à chaque
fois (méthode déjà systématique depuis le 21e incrément).
