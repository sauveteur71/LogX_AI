---
name: chantier-ev7-popout-selfspot-2026-08-07
description: "5e incrément EV-7 livré — SECOND ÉCRAN + SELF-SPOT extraits vers logx_popout_selfspot.js ; 3e candidat trouvé propre après 2 candidats piégés identifiés par un agent Explore ; 3e régression texte trouvée par la suite pytest malgré un grep préalable"
metadata:
  type: project
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-08-07T20:25:33.814Z
---

Chantier livré et fusionné sur `main` le 07/08/2026 (commit `9c4233b`, merge
de `feat/ev7-refactor-popout-selfspot`, commit de contenu `260feae`).

## Contexte

5e incrément du refactor EV-7, lancé sur un simple « go » de F4GLD (Ultracode
PAS explicitement réactivé cette fois, contrairement au 4e incrément). Le
reliquat de `logx_logbook.js` (~8038 lignes après le 4e incrément) est noté
dans "[[chantier-ev7-panneau-stats-2026-08-07]]" comme "plus entangled avec
le cœur — nécessitera un découpage plus fin, pas juste couper un bloc
contigu". Confirmé en pratique cette fois : les 2 premiers candidats évalués
manuellement (cluster KEYER VOCAL/ENREGISTREUR/CALLBOT, cluster CHAT/VUE
PARTNER) se sont révélés PIÉGÉS à l'examen :
- Cluster vocal/audio : `captureQsoAudioClip(qso)` est appelée depuis le flux
  de sauvegarde de QSO (chemin critique) — dépendance cœur→optionnel.
- Cluster chat/partner : contient `_reserveBottomSpace()`/`_majReservesBas()`,
  utilitaires génériques de mise en page réutilisés par SSTV et d'autres
  panneaux ailleurs dans le fichier.

Face à cette complexité, délégué à un **agent Explore** (recherche seule,
pas d'écriture) un audit systématique de ~10 candidats restants avec grep
exhaustif des appelants de chaque fonction. Résultat : 6 autres candidats
piégés identifiés (CARTE QSO Leaflet via `renderLog()`→`refreshMapLayers()`,
COMPAS INLINE via le flux SAISIE, BANDSCOPE/WATERFALL/FILTRE SPOTS via
`refreshBandMap()` en `setInterval`, PONT WSJT-X+WAIT-AND-POUNCE via
`refreshHardware()` en polling adaptatif, RAPPEL ON4KST via `setupDone()`,
RACCOURCI BUREAU via `init()`, BROADCAST CHANNEL via `submitQSO()`/
`deleteQSO()`) et 2 candidats propres validés (IMPORT ADIF, ÉCOUTER SUR UN
WEBSDR — trop petit seul).

## Ce qui a été livré

`concours/logx_popout_selfspot.js` (nouveau, 145 lignes) : `popoutScope`,
`popoutPanadapter`, `popoutWall`, `popoutBandes` (fenêtres détachables
multi-moniteur) + `selfSpot`, `selfSpotPota`, `selfSpotActivation`,
`selfSpotSota` (publication de spot sur cluster DX / API POTA / SOTAwatch3).
Choisi plutôt qu'IMPORT ADIF pour sa taille idéale (145 lignes) une fois
vérifié lui aussi sans dépendance à l'envers (vérification manuelle
personnelle en plus de celle de l'agent Explore — "trust but verify").
`logx_logbook.js` : 8038 → 7893 lignes (5 incréments cumulés : 9193 → 7893).

## 3e régression texte trouvée par la suite pytest complète (pas par le grep préalable)

Cette fois, j'ai grepé PROACTIVEMENT les 8 noms de fonction dans `tests/`
AVANT d'extraire (leçon du 4e incrément) et trouvé 2 fichiers avec des
assertions textuelles directes sur le corps des fonctions
(`test_panneaux_multi_fenetres.py`, `test_fenetres_bande.py`) — corrigés
avant même de lancer pytest la première fois. Mais un 3e est passé au
travers : `test_vocabulaire_portable.py::test_LES_MESSAGES_QUI_CITENT_LA_SECTION_ONT_SUIVI`
vérifiait que `logx_logbook.js` contient encore le libellé « EXPÉDITION/
PORTABLE » (renommage CONFIG suivi dans les messages) — présent uniquement
dans le message de confirmation de `selfSpotSota()`, qui a déplacé cette
chaîne hors de `logx_logbook.js`. Mon grep préalable cherchait les NOMS DES
8 FONCTIONS dans `tests/`, pas les CHAÎNES DE TEXTE qu'elles contiennent —
angle mort différent de celui trouvé au 4e incrément (qui cherchait des
fragments HTML). **Généralisation à retenir pour tout incrément futur** :
un grep par nom de fonction ne suffit PAS à couvrir tous les tests textuels
— il faudrait aussi grep chaque CHAÎNE DE MESSAGE UTILISATEUR distinctive
du bloc à extraire dans `tests/`, ou accepter qu'une régression de ce genre
ne se révèle qu'à la suite pytest complète (ce qui reste le filet de sécurité
final, jamais à sauter). Corrigé en restructurant le test pour vérifier
l'ancien libellé absent de `logx_sota_spot.py` + `logx_logbook.js` +
`logx_popout_selfspot.js`, et le nouveau libellé présent dans
`logx_sota_spot.py` + `logx_popout_selfspot.js` (plus dans `logx_logbook.js`,
qui ne le contient plus du tout).

## Vérification

Suite pytest complète (2 passes vertes). Navigateur réel : `window.open`
stubbé pour observer `popoutScope`/`popoutPanadapter`/`popoutWall` sans
ouvrir de vraie fenêtre (URLs/noms corrects confirmés) ; `popoutBandes()`
confirmé sur son propre garde-fou « >12 bandes actives » (20 bandes réelles
sur le poste de test → notification au lieu d'ouvrir 20 fenêtres, comme
prévu par le code). **`selfSpot`/`selfSpotPota`/`selfSpotSota` volontairement
PAS appelées en conditions réelles** : elles ont un effet de bord réseau réel
(publication sur cluster DX / API publique POTA / SOTAwatch3, visible par de
vrais chasseurs) — vérifiées uniquement par diff strict (contenu extrait
byte-identique à l'original) et par `typeof` + wiring DOM (`onclick`
attributes confirmés). Pas de revue adversariale par workflow cette fois
(Ultracode off) — auto-review du diff (un seul hunk contigu de 145 lignes,
rien d'autre touché) en remplacement.

## Reliquat

~7893 lignes restent dans `logx_logbook.js`. IMPORT ADIF (~96 lignes,
`triggerImport`/`previewImportAdif`/`confirmImportAdif`/`closeImportOverlay`)
reste un candidat propre validé mais pas encore extrait — bon point de
départ pour un 6e incrément (peut-être à combiner avec un voisin non
contigu pour atteindre une taille plus confortable). La liste des candidats
piégés ci-dessus (carte Leaflet, compas, bandscope/waterfall/filtre spots,
WSJT-X/wait-and-pounce, rappel ON4KST, raccourci bureau, broadcast channel,
vocal/audio, chat/partner) est désormais bien cartographiée — à ne PAS
re-tenter sans restructuration plus profonde (ex. séparer le dispatcher
cœur de l'implémentation optionnelle, comme fait pour le moteur de filtre
au 2e incrément).
