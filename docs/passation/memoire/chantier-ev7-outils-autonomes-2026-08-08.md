---
name: chantier-ev7-outils-autonomes-2026-08-08
description: "8e incrément EV-7 livré — première extraction multi-points non contigus (5 blocs) vers logx_outils_autonomes.js + fusion qslLastSync/qslAction dans logx_awards.js ; agent Explore a cartographié les dispatchers cœur restants et confirmé le reliquat 'gros bloc unique' épuisé"
metadata:
  type: project
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-08-07T22:05:52.886Z
---

Chantier livré et fusionné sur `main` le 08/08/2026 (commit `a46e0ba`, merge
de `feat/ev7-refactor-outils-autonomes`, commit de contenu `abab1ae`).

## Contexte

8e incrément consécutif du refactor EV-7 (7 précédents : CW panel, 4 outils
maintenance LOGBOOK, panneau STATS, panneaux VÉRIFIER/DIPLÔMES, SECOND
ÉCRAN+SELF-SPOT, QTC, IMPORT ADIF+EXPORT ON4KST), toujours sur la même
session longue autonome (« je vais me coucher tu as 7h devant toi »).
Ultracode confirmé actif par system-reminder.

Avant ce chantier, un agent Explore dédié a fait un audit EXHAUSTIF du
reliquat de `logx_logbook.js` (7613 lignes) et conclu que le stock de blocs
CONTIGUS de 100+ lignes sans dépendance cœur était épuisé — trouvant au
passage 2 nouveaux pièges non documentés (RTTY+SSTV via
`updateKeyerPanels()`←`pickMode()`, RADIO CAT/AMPLI/ROTOR via
`refreshHardware()`, MACROS F1-F8 + SO2R + band map via le handler clavier
global, SCAN QSL/CHAMPS ADIF via `editQSO()`, busted-pastille + ESM via
`submitQSO()`). Seule option restante : combiner plusieurs PETITS blocs
propres et NON CONTIGUS dans un même nouveau fichier.

## Ce qui a été livré

**Première extraction multi-points de toute la campagne EV-7** (jusqu'ici,
chaque incrément coupait UN SEUL bloc contigu). `concours/logx_outils_autonomes.js`
(nouveau, 218 lignes) combine 5 blocs découpés à des endroits différents de
`logx_logbook.js` :
- ÉCOUTER SUR UN WEBSDR (`ecouterSpot`/`sEcouter`)
- GARDE-FOU « MULT FANTÔME » zone CQ vs cty.dat (`checkExchangeZone`/
  `clearExchWarn`/`askExchangePlausible`) — **piège de découpage évité** :
  `corrigerBusted()`, fonctionnalité voisine mais DISTINCTE (pastille
  indicatif « busted »), physiquement adjacente dans le fichier source,
  soigneusement laissée dans `logx_logbook.js`.
- MÉTÉO DU POINT HAUT (`refreshWeather`)
- RESET LOG (`archiveLog`/`resetLog`)
- GPS → LOCATOR MAIDENHEAD (`latLonToMaidenhead`/`getGPSLocator`), avec
  suppression assumée d'un commentaire de section orphelin (« DÉMARRAGE AUTO
  DEPUIS CONFIG », 2 lignes sans code sous lui, laissé par une extraction
  antérieure)

`qslLastSync()`/`qslAction()` déplacées dans `concours/logx_awards.js`
(fichier déjà existant du 4e incrément) plutôt que dans le nouveau fichier :
elles n'avaient qu'un seul consommateur réel, `showAwards()`, déjà dans ce
fichier — l'en-tête de `logx_awards.js` documentait déjà cette dépendance
comme « pas déplacée ici, autre fonctionnalité » depuis le 4e incrément ;
ce chantier referme le trou.

`logx_logbook.js` : 7613 → 7375 lignes (-238, 8 incréments cumulés depuis
9193 lignes de départ).

## Méthode pour l'extraction multi-points (nouvelle par rapport aux incréments précédents)

Chaque bloc supprimé selon la convention « contenu + ligne vide finale »
(garde la ligne vide qui PRÉCÈDE le bloc comme séparateur unique avec la
section suivante) pour éviter les doubles lignes vides aux points de
suture. Retrait fait via un script Python en UNE SEULE passe (un set de
tous les numéros de ligne à retirer, calculé à partir de 6 plages
1-indexées confirmées une par une par lecture directe du fichier), plutôt
que des Edit séquentiels qui auraient décalé les numéros de ligne à chaque
étape. Les 6 points de suture relus individuellement après coup pour
confirmer l'absence de double ligne vide et la présence intacte du code
voisin (notamment `corrigerBusted()`).

## Vérification

Suite pytest complète (2 passes vertes, 1re passe verte du premier coup
malgré la complexité). Navigateur réel sur les 12 fonctions : `typeof`
confirmé pour toutes ; `latLonToMaidenhead(48.8566, 2.3522)` = "JN18EU"
(locator correct pour Paris) ; `ecouterSpot()` appelée pour de vrai contre
le vrai backend WebSDR production (URL réelle f5lfe.fr retournée,
`window.open` stubbé pour ne pas ouvrir de fenêtre) ; `refreshWeather()`
confirmée avec les vraies données météo (18°C). **`archiveLog()`/
`resetLog()`/`qslAction()` volontairement PAS appelées en conditions
réelles** (écriture réelle dans le log de production / upload réel vers
services QSL tiers) — vérifiées uniquement par diff strict.

Revue adversariale Workflow renforcée (3 agents, prompts détaillant
explicitement les 6 points de coupure un par un plutôt qu'un seul bloc) :
**équivalent** (diff vide sur les 6 éléments + le bloc ajouté à
`logx_awards.js`, `corrigerBusted()`/`vieillirPastilleBusted()` confirmées
intactes), **rien à signaler** (aucun doublon, ordre de script correct,
`test_logbook_render_window_reset.py` vérifié fonctionnellement correct
pour le chemin historique e68907d), **aucune dépendance problématique**
(les 7 points de vérification explicites tous sains, y compris la nuance
`qslAction()`→`setTimeout(showAwards,800)` confirmée comme cohésion
INTERNE au module optionnel, pas une dépendance vers le cœur).

## Reliquat et fin (provisoire) de la campagne EV-7 sur cette session

~7375 lignes restent dans `logx_logbook.js`. Le reliquat restant est
désormais **cartographié en détail** par 2 audits Explore successifs comme
massivement entremêlé avec le cœur via des dispatchers auto-appelés
(`updateKeyerPanels`, `refreshHardware`, `refreshBandMap`, `setupDone`,
`init()`, `submitQSO()`, `onCallInput()`, le handler clavier global). Aller
plus loin nécessiterait une VRAIE restructuration (pas un simple
copié-collé) : séparer chaque dispatcher cœur de ses implémentations
optionnelles via un bus d'événements (`document.dispatchEvent`/
`addEventListener` plutôt que des appels directs) — proposé en détail par
le dernier agent Explore (voir son rapport complet dans la transcription de
session) pour RTTY/SSTV, CLOCK, RADIO CAT/AMPLI/ROTOR, MACROS F1-F8, SO2R,
scan QSL/champs ADIF, busted-pastille, ESM. C'est un chantier distinct, à
netre pas confondre avec le principe « extraction TEL QUEL » suivi jusqu'ici
— à proposer explicitement à F4GLD plutôt qu'à entreprendre sans discussion,
vu son ampleur et son risque architectural plus élevé.
