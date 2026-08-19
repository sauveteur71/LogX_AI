---
name: chantier-panadapter-audio-et-civ-2026-08
description: "Panadapter LogX AI, 2 volets : audio universel (`7fdcf16`) + scope CI-V 0x27 Icom large bande (`598321e`), bug critique trouvé par revue adversariale (04/08/2026)"
metadata: 
  node_type: memory
  type: project
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-08-04T13:43:17.329Z
---

Suite de l'[[chantier-etude-panadapter]] (si elle existe — sinon voir l'échange
du 04/08/2026 où F4GLD a demandé de lancer les 3 chantiers recommandés par
l'étude). Deux des trois livrés ce jour ; le 3e (TCI, `logx_tci.py`) est resté
en attente — voir section finale.

## Volet 1 — Panadapter AUDIO universel (`logx_panadapter.html`, `7fdcf16`)

Nouvelle fenêtre détachable sur le modèle de `logx_bande.html`/`logx_scope.html` :
Web Audio `AnalyserNode` (fftSize 4096) → spectre `<canvas>` + chute d'eau
(défilement par décalage d'image). Réutilise le MÊME flux audio que le
décodeur CW (`logx_cwdecoder.js`), jamais le micro du PC. Largeur réglable
0-3/6/12/24 kHz, case "échelle RF" optionnelle (USB/LSB seulement — CW/AM/FM
gardent l'audio brut, pas de convention fiable à deviner). Bouton d'accès
ajouté au toolbar Band Map de `logx_logbook.html` (`popoutPanadapter()`).

Vérifié en injectant une tonalité 1 kHz synthétique via un faux
`getUserMedia()` (le vrai micro est bloqué dans le bac à sable navigateur de
ce siège) puis clic RÉEL sur Démarrer/Arrêter — pic au bon endroit sur les
deux canvas, aucune erreur console.

## Volet 2 — Scope CI-V 0x27 natif Icom (`598321e`), large bande sans matériel

Les Icom déjà pilotés en CAT natif (IC-7300/7610/9700/705/7851) publient leur
spectre déjà calculé en interne sur la MÊME liaison série CI-V que le CAT
(commande `0x27`, sous-commande `00` "Scope Waveform Data") — jusqu'à 500 kHz
de span, zéro matériel supplémentaire. Protocole reconstruit depuis les PDF
officiels Icom (IC-7300MK2, IC-705 CI-V Reference Guides, lus intégralement
par un agent de recherche) — **pas de code tiers réutilisé** (wfview, qui a
fait le même travail de reverse-engineering, est sous licence GPL : seule sa
documentation-en-prose a été consultée, jamais son code).

### Implémenté via un WORKFLOW à 4 agents (implémenter → 2 revues adversariales en parallèle → corriger)

Décision : ce chantier touche un protocole binaire (offsets d'octets, BCD,
découpage en 11 paquets) sur du matériel qu'aucun agent ne peut tester en
vrai — le risque d'un bug d'offset silencieux justifiait une revue
adversariale structurée plutôt qu'une implémentation solo. Chaque agent de
revue a reçu la MÊME spec source (pas le raisonnement de l'implémenteur) pour
rester vraiment indépendant.

### 🚨 Bug CRITIQUE trouvé par la revue "qualité/robustesse" — jamais par la revue "protocole"

`CivRadio.read_scope_line()` appelait `self.t.read_until()` **directement**
sur le transport injecté — le SEUL endroit de tout `logx_cat.py` à faire ça.
Or `SerialPort` (le transport de PRODUCTION) n'expose que `write()`,
`transceive()` et `close()` — **pas `read_until()`**. Conséquence vérifiée
empiriquement par l'agent de revue (transport factice avec l'interface
publique EXACTE de `SerialPort`) : `AttributeError` sur TOUTE radio réelle,
scope 100% mort dès le premier appel malgré 43 tests verts (les tests
utilisaient `QueuedCivTransport`, qui implémente `read_until()` — invisible
tant qu'on ne compare pas à l'interface RÉELLE du transport de prod).

Pire : `scope_configure()`/`scope_line()` attrapent cette exception dans un
`except Exception` générique qui la traduit en *"Radio injoignable"*
(message trompeur — masque un bug logiciel en panne matérielle) **et appelle
`disconnect_persistent()`**. Comme `logx_panadapter.html` poll
`/rig/scope_line` toutes les 500 ms dès que la source CI-V est sélectionnée,
activer le panadapter CI-V aurait démonté/rouvert en boucle la connexion CAT
**persistante et PARTAGÉE** avec `/rig/state` (pollée par toutes les pages
ouvertes) — dégradant tout le CAT pendant que le panadapter est actif, pas
juste laissant le scope vide. Exactement le piège
[[piege-verifier-sur-donnees-reelles]] : tests verts, fonctionnalité morte —
et ici, pire, fonctionnalité morte qui casse autre chose au passage.

**Correctif** : nouvelle méthode `SerialPort.transceive_listen(terminator,
timeout, on_frame)` — écoute PASSIVE de plusieurs trames consécutives,
**verrou d'instance tenu sur TOUTE la fenêtre** (pas relâché entre paquets,
contrairement à ce qu'aurait fait un simple `read_until()` en boucle) : une
ligne de spectre enchaîne jusqu'à 11 lectures sur plusieurs secondes, et un
thread concurrent (`/rig/state`, pollé toutes les 4s) qui s'intercalerait
entre deux paquets pourrait sinon corrompre la ligne en cours de réception —
même risque déjà documenté sur `transceive()`, juste étalé sur une fenêtre
plus longue. `read_scope_line()` utilise `transceive_listen()` si le
transport l'expose, avec repli sur l'ancienne boucle `read_until()` pour les
doubles de test minimalistes (synchrones, sans thread concurrent — pas
besoin de toucher tous les tests existants).

### Constats mineurs (déjà corrigés au moment de la revue, ou par moi ensuite)

- Garde-fou modèle manquant côté `scope_configure()`/`scope_line()` (seul
  `scope_civ_available()`, utilisé pour l'UI, filtrait par
  `MODELES_SCOPE_CIV`) — corrigé par l'agent de correction : même filtre
  répété aux deux endpoints d'action, message d'erreur clair au lieu d'un
  refus radio silencieux pour un modèle non listé (ex. IC-7100).
- Span (`27 15`) non validé contre les 8 valeurs discrètes documentées
  (2.5-500 kHz) avant envoi — **déjà corrigé côté endpoint HTTP** par l'agent
  (je l'avais d'abord cru manquant en lisant seulement le rapport de revue,
  piège de re-vérifier le CODE et pas seulement le résumé). J'ai ajouté une
  validation redondante dans `civ_scope_configure_frames()` elle-même
  (défense en profondeur : sécurise aussi tout futur appelant Python direct,
  pas seulement l'endpoint HTTP).

### Ma propre vérification complète après le workflow (demandée explicitement par F4GLD)

Le rapport final de l'agent de correction s'est arrêté sur une phrase
tronquée ("en attente de la fin du pytest complet") — **jamais faire confiance
au résumé d'un agent sans relire le code soi-même**, surtout après un
finding critique. Vérifié moi-même : lecture directe de `read_scope_line()`/
`SerialPort.transceive_listen()` (le correctif est bien en place et bien
conçu), du test `test_cat_scope_civ.py` (43 tests, piège BCD 0x10≠0x0A confirmé
par lecture directe, pas seulement le rapport), du diff JS complet de
`logx_panadapter.html`. Vérification navigateur réelle : source CI-V simulée
(`/rig/scope_available` mocké), clic RÉEL sur les boutons DOM (`.click()`,
`.onchange()` — accessibles même si les fonctions internes sont
IIFE-scopées), ligne de spectre simulée avec un pic → spectre ET chute d'eau
correctement dessinés (vérifié par lecture de pixels canvas, pas juste
absence d'erreur), aucune erreur console. Suite pytest complète relancée une
dernière fois après mon propre correctif de validation de span : verte.

## Volet 3 (TCI) — LIVRÉ le même jour, voir [[chantier-panadapter-tci-2026-08]]

FFT pur Python écrite à la main (`f00e9c8`) — le plus gros des 3 volets, pas
de commande "spectre pré-calculé" côté TCI contrairement à CI-V, tout le
calcul se fait côté serveur à partir du flux IQ brut. 2 constats mineurs
trouvés par la revue adversariale et corrigés (détails dans le fichier lié).
