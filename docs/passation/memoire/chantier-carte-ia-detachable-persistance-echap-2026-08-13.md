---
name: chantier-carte-ia-detachable-persistance-echap-2026-08-13
description: "CARTE IA : détacher la carte (?panel=map), menu PLUS, persistance du chat, annulation Échap, texte agrandi — PR #60"
metadata:
  type: project
  originSessionId: 98b0707f-1a89-40bf-8422-4ab7b88ba78a
  modified: 2026-08-13T12:04:27.728Z
---

Suite directe de [[chantier-verification-approfondie-pre-beta-2026-08-13]]. F4GLD
a testé la CARTE IA après la vérification pré-bêta et remonté 4 retours en une
seule session, tous corrigés dans PR #60 (branche
`feature/carte-ia-detachable-persistance-ux`) :

1. **Détacher la carte sur un 2e écran** — bouton "⇱ DÉTACHER" à côté du
   bouton 3D. Choix de conception : réutiliser `logx_carte.html` LUI-MÊME
   comme fenêtre détachée via `?panel=map` (masque `.chat-panel`, laisse
   `.map-panel` prendre 100% via son `flex:1` déjà existant), plutôt que de
   construire un mini-panneau simplifié comme `logx_panel.html`. Garantit une
   parité fonctionnelle à 100 % (globe 3D, GREAT CIRCLE, CARRÉS QRA, VOACAP)
   sans aucune duplication de code, contrairement aux panneaux détachés
   existants (COACH/CLUSTER/etc. via `logx_panel.html`) qui sont des rendus
   réduits dédiés. `window.ouvrirFenetreDetachee()` (déjà existant, ajouté
   lors du chantier pré-bêta) réutilisé pour le repli "popup bloquée".
2. **Menu "⋯ PLUS"** — 13 boutons secondaires (DÉBRIEF/MÉMOIRE/SON/CHASSE
   ASSISTÉE/SCORE/SPOTS/PROP/OUVERTURES/MULTS/RÉSUMÉ/BILAN/COORDINATION/
   FENÊTRE VOACAP) déplacés dans un panneau flottant `position:absolute`
   (jamais un `<details>`, qui aurait repoussé la zone de saisie). COACH/
   ANALYSER + les 2 sélecteurs de réglage restent toujours visibles (chemin
   le plus fréquent).
3. **Chat qui perdait son contenu en changeant d'onglet** — F4GLD avait
   raison de douter que CHASSE ASSISTÉE soit seule en cause (« je suis pas
   sur que chasse assisté soit le seul a faire exeption! ») : en grepant le
   fichier, AUCUN mécanisme de persistance n'existait nulle part, pour aucun
   chemin. Corrigé par un `MutationObserver` (débounce 400ms) sur `#chatMsgs`
   → `localStorage['rc_carte_chat_v1']`, plutôt que d'instrumenter chaque
   site de `conversationHistory.push()` (~10+ sites, dispersés) — le bug
   initial était justement l'absence totale de mécanisme, un patch par site
   aurait reproduit la même classe de risque (site oublié). Restauration via
   `addMsg()` rejoué message par message plutôt qu'un `innerHTML` brut : le
   bouton 🔊 (`addSpeakIcon`) attache son handler en propriété JS
   (`b.onclick=...`), perdu par une resérialisation `innerHTML`.
4. **Annulation Échap** — retour F4GLD après un clic sur le mauvais bouton :
   « je voudrais pouvoir annuler sa recherche en cliquant sur escape ».
   Implémenté via un flag partagé `_analysisCancelled` vérifié à CHAQUE point
   de reprise asynchrone (callback SSE fermé via `.close()`, ticks de
   `pollAnalyze()`/`pollAct()`), pas via un vrai `AbortController` sur les
   fetch — suffisant : le job continue éventuellement en tâche de fond côté
   serveur (aucun endpoint d'arrêt n'existe, décision assumée, pas un bug),
   mais son résultat n'est plus jamais affiché ni repris au rechargement
   (localStorage `rc_analyze` vidé). Point de vigilance trouvé et corrigé
   PENDANT l'implémentation (pas après) : la fenêtre entre le POST initial
   `/agent/analyze` et l'obtention de l'id — annuler PENDANT ce court laps ne
   doit pas laisser le `.then` qui suit relancer `streamAnalyze()` après coup
   ; gardé par un check `if(_analysisCancelled) return;` juste après avoir
   reçu l'id, avant l'appel à `streamAnalyze()`.
5. **Texte du panneau chat/coach jugé trop petit** — bulles de chat 14px→15px,
   panneau coach (rate/bands/hints) 12px→13px, horloge coach/indicateur
   "Analyse en cours" 13px→14px. Volontairement PAS touché : `.qbtn`/
   `.skill-sel`/`.cfg-btn` (chrome de boutons dense, pas du texte à lire),
   pour ne pas re-casser la mise en page tout juste libérée par le menu PLUS.

**Piège d'environnement rencontré (pas un bug produit)** : la Browser pane
du sandbox de test ne supporte pas les vraies fenêtres popup séparées —
`window.open(url, nom, options)` avec un nom déjà utilisé renavigue l'onglet
COURANT en place plutôt que d'ouvrir un second onglet réellement isolé
(confirmé : après appel, `location.href` de l'onglet actif contenait bien
`?panel=map`). `window.ouvrirFenetreDetachee()` lui-même ne navigue JAMAIS la
page courante (vérifié en lisant sa source dans `logx_statusbar.js` — son
seul repli est un toast si `window.open` renvoie null) : le comportement
observé vient donc bien du sandbox, pas du code. Contournement de
vérification : mocker `window.ouvrirFenetreDetachee` pour renvoyer un faux
objet fenêtre (`{closed:false, focus(){}, close(){...}}`) et vérifier la
LOGIQUE de bascule de classes (`body.map-detached`/bouton RÉINTÉGRER) sans
dépendre d'un vrai popup — et vérifier séparément le rendu `?panel=map`
directement en y naviguant. Les deux se sont révélés corrects indépendamment.

**Bonus mineur (même PR)** : rappel de l'avertissement Windows SmartScreen
ajouté au README (`## Démarrage rapide`, étape 1) — le contenu détaillé
existait déjà dans `docs/GUIDE_UTILISATEUR.md` ET dans le wiki
(`Installation.md`, worktree `wt-wiki/`) depuis une session antérieure
(12/08), juste absent du README lui-même à l'endroit où se trouve le lien de
téléchargement.

PR #60, branche `feature/carte-ia-detachable-persistance-ux`, aucun fichier
`.py` touché (pas de redémarrage serveur nécessaire après fusion).
