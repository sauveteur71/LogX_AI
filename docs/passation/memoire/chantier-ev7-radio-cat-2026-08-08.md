---
name: chantier-ev7-radio-cat-2026-08-08
description: "EV-7 phase 2, 2e chantier livré — extraction MÉCANIQUE (pas bus d'événements) du bloc RADIO CAT/AMPLI/ROTOR/WSJT-X vers logx_hardware_cat.js ; un vrai bug d'ordre de chargement <script> trouvé et corrigé (invisible aux tests py_mini_racer) ; bug préexistant esmSend() trouvé et signalé, non corrigé"
metadata:
  type: project
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-08-08T06:56:31.694Z
---

Chantier livré et fusionné sur `main` le 08/08/2026 (commit `e2cec50`, merge
de `feat/ev7-eventbus-radio-cat`, commit de contenu `dc32c51`).

## Contexte

F4GLD a autorisé explicitement : « ok go radio cat.. », en réponse directe
au message précédent sur la suite de la phase 2 EV-7 (voir
[[chantier-ev7-eventbus-pilote-scan-qsl-2026-08-08]]). Ce candidat avait été
préalablement écarté au moment du pilote SCAN QSL car jugé « en réalité 3
sous-systèmes entremêlés » — cette fois investigué pour de vrai avant de
choisir un motif.

## Découverte principale : ce n'était PAS un cas bus d'événements

Une investigation Workflow (4 agents en parallèle) a montré que
`applyWsjtxState()` → `refreshPounce()`/`appliquerSuiviCarres()` (l'
entrelacement qui avait fait peur au pilote précédent) est un appel INTERNE
au même bloc — les deux bouts restent dans le même futur fichier, donc pas
une dépendance cœur→optionnel. La VRAIE dépendance cœur→bloc est ailleurs :
12 LECTURES directes (pas des appels) de `rigState`/`rotorState` depuis des
fonctions cœur dispersées (bandmap, ESM, macros F1-F8, fréquence de saisie,
boussole rotor). 11 de ces 12 étaient déjà défensivement gardées par
`typeof rigState !== 'undefined'` (l'appli tolérait déjà l'absence de CAT,
antérieurement à ce chantier) ; la 12e (`copyMacro()`) a reçu le même garde
avant l'extraction. **Conclusion générale pour la suite de la phase 2** :
avant de présumer qu'un bloc a besoin du motif bus d'événements, toujours
vérifier D'ABORD si les lectures cœur→bloc sont déjà défensivement gardées
— si oui, une extraction MÉCANIQUE simple (comme les incréments 1-9) suffit,
pas besoin d'inventer un mécanisme d'événements.

`adaptivePoll()` (polling générique) reste dans `logx_logbook.js` car
`pollChat()` (cœur, chat multi-poste) le réutilise aussi — seule fonction du
bloc à avoir un VRAI appelant externe en JS (les 20 autres n'ont que des
`onclick=`/`onchange=` HTML comme point d'entrée).

## Bug réel trouvé et corrigé (invisible aux tests py_mini_racer)

L'extraction initiale laissait `adaptivePoll(refreshHardware, 3000, 20000,
...)` en tant qu'appel de fin de fichier dans `logx_hardware_cat.js` —
chargé AVANT `logx_logbook.js` (convention EV-7 : fichiers extraits avant le
cœur). Comme `adaptivePoll` est DÉFINIE dans `logx_logbook.js`, cet appel
levait une `ReferenceError` silencieuse au chargement de page : **le poll
matériel (rig/ampli/rotor/WSJT-X) ne démarrait JAMAIS automatiquement**, une
régression fonctionnelle réelle qui aurait affecté tous les utilisateurs
avec du CAT configuré.

**Comment ça a été trouvé** : la revue adversariale Workflow (agent
« equivalence ») a soulevé le risque en raisonnant sur l'ordre des
`<script>`. Vérifié empiriquement en navigateur avec un test isolé (2
`<script>` minimaux reproduisant exactement l'ordre appel-avant-définition)
→ `ReferenceError` confirmée à 100%.

**Piège de vérification rencontré pendant la correction** : le premier
correctif (`setTimeout(fn, 0)`) semblait ne PAS fonctionner lors des tests
navigateur suivants (`rigState.enabled` restait `false` même après le
correctif) — en réalité c'était le **cache HTTP du navigateur** qui servait
une version PÉRIMÉE du script malgré une navigation "force:true" répétée.
Confirmé en comparant le contenu réellement exécuté (absent de logs de
diagnostic ajoutés temporairement) au contenu réellement servi (`fetch()`
direct, qui lui montrait bien le nouveau code). Résolu par un vrai
rechargement forcé (Ctrl+Shift+R) — SEULEMENT à ce moment le correctif s'est
révélé fonctionner. **Leçon pour toute vérification navigateur future sur
ce projet** : une `navigate({force:true})` répétée sur la MÊME URL peut ne
PAS invalider le cache HTTP des sous-ressources (`<script src>`) — en cas de
doute sur un changement JS qui ne semble "pas prendre effet", toujours
tester un Ctrl+Shift+R avant de conclure qu'un correctif ne marche pas.

**Leçon structurelle plus large** : ce type de bug (ordre d'exécution entre
plusieurs `<script>` classiques, un appel synchrone à une fonction pas
encore définie) est **totalement invisible aux tests py_mini_racer de ce
projet**, qui concatènent systématiquement tout le JS en un seul
`ctx.eval()` — dans un seul appel `eval()`, TOUTES les déclarations
`function` du texte entier sont hoistées avant toute exécution, donc l'ordre
texte n'a aucune importance (contrairement à plusieurs balises `<script>`
séparées dans un vrai navigateur, où chaque script s'exécute intégralement
avant que le suivant ne soit même chargé). **Pour toute future extraction
EV-7 dont le fichier extrait contient un appel synchrone de niveau module
vers une fonction du cœur (pas juste une définition/un `addEventListener`),
la vérification navigateur réelle (pas seulement pytest vert) est
OBLIGATOIRE, pytest ne peut structurellement pas attraper ce cas.**

Correctif retenu : différer l'appel via `setTimeout(fn, 0)` (s'exécute après
l'exécution synchrone de TOUS les `<script>` classiques de la page, une fois
`adaptivePoll` définie) — garde la logique d'amorçage du polling dans le
fichier auquel elle appartient conceptuellement, plutôt que de la
rapatrier dans `logx_logbook.js`.

## Bug préexistant trouvé, SIGNALÉ mais NON corrigé (hors scope)

`esmSend()` (`logx_logbook.js`, ~ligne 2258 avant extraction) utilise
`rigState.enabled` comme condition de routage CW/voix — contrairement à
`updateKeyerPanels()` juste à côté qui gère correctement le repli CW-sans-
CAT (`rigState.mode || currentMode`, sans exiger `.enabled`). Conséquence
concrète : un opérateur en CW manuel (clé/manip externe, sans CAT branché)
qui utilise ESM peut voir jouer un **message vocal réel et audible** au lieu
du CW attendu — pas une dégradation gracieuse, un résultat FAUX et audible
sur l'air. Ce bug est ANTÉRIEUR à ce chantier (pas causé par l'extraction),
non corrigé (hors périmètre d'une extraction mécanique), signalé
explicitement à F4GLD en fin de chantier pour décision.

## Vérification

4 passes pytest complètes (la 3e a eu un flake d'infrastructure sans
rapport — `ConnectionResetError` sur un serveur HTTP éphémère de test sous
charge concurrente, confirmé par ré-exécution isolée, motif déjà documenté
dans [[suite-tests-flakes-sous-charge]]). Vérification navigateur réelle
contre données de production (CAT réellement configuré sur ce poste :
`rigState.enabled` bascule à `true` automatiquement après rechargement
forcé, `rigctld` signalé injoignable — comportement identique à avant
l'extraction). `copyMacro()` avec le nouveau garde testé pour de vrai
(chemin presse-papier, `currentMode` confirmé ≠ CW avant l'appel pour éviter
tout envoi CW réel). Aucune commande matérielle à effet réel déclenchée
(`armerPounce`/`toggleAmpOperate`/`rigStopCW`/`couperEmissionWsjtx` non
invoquées pour de vrai).

Revue adversariale Workflow (3 agents) : équivalence stricte confirmée
(diff byte-à-byte sauf les 3 exceptions annoncées), dépendance cœur→bloc
saine (12/12 lectures gardées après correction), couverture de tests
vérifiée sur 8 fichiers de test (5 déjà corrigés + 5 supplémentaires
vérifiés sans risque).

## Reliquat pour la suite de la phase 2

Toujours en attente, cadrage cas par cas requis : RTTY/SSTV
(`updateKeyerPanels()`), MACROS F1-F8+SO2R+band-map (handler clavier
global), busted-pastille+ESM (`submitQSO()`), CHAMPS ADIF PERSONNALISÉS
(dépendance bidirectionnelle, motif pas encore conçu). Aucune cible
suivante choisie.
