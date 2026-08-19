---
name: chantier-ev7-macros-2026-08-09
description: "EV-7 32e incrément : extraction NON CONTIGUE MACROS F1-F8 vers logx_macros.js (09/08, merge 0168205) — le plus délicat structurellement de la campagne, i18n et adaptivePoll() restés intacts dans le cœur, 3 fichiers déjà extraits mis à jour avec gardes typeof, F3 réel confirmé en navigateur, 0 constat"
metadata: 
  node_type: memory
  type: project
  modified: 2026-08-09T07:38:03.404Z
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
---

32e incrément de la campagne, DERNIER candidat MOYEN du 3e inventaire
([[inventaire-ev7-3e-2026-08-09]]) hormis le 33e — et le PLUS DÉLICAT
structurellement de toute la campagne EV-7. Extraction NON CONTIGUE : dans
`concours/logx_logbook.js` d'origine, le code des macros F1-F8 était
entrecoupé de DEUX sections qui DEVAIENT RESTER dans le cœur (i18n : `trT`/
`trF`/`notify`, réutilisées par toute l'app ; `adaptivePoll()`, réutilisée
par `pollChat()`). 3 sous-blocs disjoints extraits vers `concours/logx_macros.js`
(nouveau, 133 lignes) : `DEFAULT_MACROS`/`getMacros()`/`saveMacros()`/
`expandMacro()`/`renderMacroPanel()` (62 lignes), `copyMacro()` (23 lignes,
séparé du 1er sous-bloc par la section i18n restée en place), `editMacro()`
(10 lignes, séparé du 2e sous-bloc par `adaptivePoll()` restée en place).
3 pointeurs distincts laissés dans `logx_logbook.js`, à chacun des 3
emplacements — pas un seul pointeur global.

**Méthode d'extraction changée pour ce chantier** : ancrage par recherche
de chaîne (`src.index(...)`) plutôt que numéros de ligne fixes, pour
localiser précisément chaque sous-bloc sans risque d'erreur de décalage —
plus robuste que le découpage ligne-à-ligne utilisé pour les extractions
contiguës précédentes, à réutiliser systématiquement pour toute future
extraction non contiguë.

**3 fichiers déjà extraits mis à jour** (sens de dépendance INHABITUEL :
ces fichiers chargent AVANT `logx_macros.js`, alors que d'ordinaire les
fichiers EV-7 ne dépendent que de symboles chargés avant eux) :
- `logx_theme_shortcuts.js` (22e incrément) : garde
  `if(typeof getMacros === 'function' && typeof copyMacro === 'function')`
  ajoutée autour de l'appel dans le gestionnaire keydown F1-F8, SANS
  affecter `e.preventDefault()` (doit continuer à s'exécuter dans tous les
  cas, sinon régression F5 recharge la page).
- `logx_rtty_panel.js` (15e incrément) : garde typeof ajoutée pour
  `expandMacro()` (variable locale `expand`), 2 sites d'appel dans
  `renderRttyMacroBtns()`.
- `logx_esm_callbot.js` (19e incrément) : commentaire d'en-tête mis à jour
  uniquement — avait déjà une garde `typeof copyMacro==='function'`
  préexistante, non modifiée.

Ces 3 dépendances restent sûres malgré l'ordre inhabituel car tous les
appels sont différés après la fin du chargement complet de la page
(gestionnaire clavier, rendu déclenché par `DOMContentLoaded`) — jamais
synchrones au chargement du script.

2 fichiers de test mis à jour : `test_macro_cw_serie_bande.py` (le plus
critique, exerce `expandMacro`/`copyMacro`/`editMacro`/`renderMacroPanel`
via un scénario complet ESM/CW) et `test_logbook_menu_debut_fin.py`. 2
autres fichiers mentionnant les macros (`test_macros_au_clavier.py`,
`test_notify_dynamic_i18n.py`) vérifiés indépendamment par la revue
adversariale comme ne nécessitant AUCUN changement (mocks/prose
uniquement).

Suite pytest complète (8792 tests) verte. Vérification navigateur réelle :
`renderMacroPanel()` rend 8 boutons avec titres réellement expansés
(indicatif réel de la config) ; un VRAI `KeyboardEvent('keydown', {key:
'F3'})` dispatché sur `document` (donc passant par le vrai gestionnaire de
`logx_theme_shortcuts.js`) a déclenché `copyMacro(2)` — confirme
l'intégration cross-fichier bout en bout, sens inhabituel compris ;
`renderRttyMacroBtns()` a rendu 4 boutons avec titres expansés ;
`editMacro()` a réellement modifié et persisté une macro.

Revue adversariale (extraction-fidelity + dependency-integrity, 2 agents,
98 appels d'outils, ~43 min) : 0 constat — aucune duplication ni perte des
sections i18n/adaptivePoll restées dans le cœur, gardes typeof correctement
placées.

`logx_logbook.js` : ~4111 → ~4001 lignes.

Suite : dernier candidat MOYEN du 3e inventaire — FILTRE D'AFFICHAGE DES
SPOTS + refreshBandMap (33e incrément, ~208 lignes, impacte ~15 fichiers de
test host-wide), avant de lancer un 4e inventaire Workflow.
