---
name: chantier-rtty-sstv-emission-2026-08-06
description: "Émission RTTY et SSTV natives ajoutées au LOGBOOK — les décodeurs existaient déjà, seule l'émission manquait"
metadata: 
  node_type: memory
  type: project
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-08-06T09:25:13.095Z
---

Suite directe de la question "quels modes numériques sont désormais
intégrés émission/réception ?" — la réponse a montré que RTTY et SSTV
n'avaient que la RÉCEPTION (décodeurs natifs déjà en place, encodeurs
existants mais utilisés SEULEMENT pour l'auto-test des décodeurs, jamais
branchés à une vraie émission). L'utilisateur a demandé de compléter les
deux.

**Implémentation** : même modèle que [[chantier-panadapter-audio-et-civ-2026-08]]
et le décodeur/émetteur FT8 natif (`logx_ft8.html`) — PTT via `/rig/ptt`
(déjà générique, pas de nouveau endpoint), lecture Web Audio avec
`setSinkId` pour router vers un périphérique de SORTIE choisi, case
"Activer l'émission" non cochée par défaut (aucune émission automatique).
RTTY : 4 macros fixes réutilisant `expandMacro()` (mêmes jetons {CALL}/
{LOC}/{NR} que les macros CW F1-F8). SSTV : sélection d'image + mode (14
modes Martin/Scottie/Robot/PD), étirée aux dimensions exactes du mode,
suivi de progression par temps écoulé (l'encodeur produit la forme d'onde
complète d'un coup, pas de flux — PD120 prend ~2 min à émettre).

**Deux bugs réels trouvés en vérification navigateur** (pas en écrivant le
code — voir [[piege-instance-isolee-partage-server-config]] pour la
méthode de vérif utilisée, cette fois strictement en lecture) :
1. Le bouton QTC (`✉ QTC : 0`), converti en icône SVG lors du lot 4
   d'icônes monochromes le même jour, perdait son icône dès le premier
   appel de `refreshQTC()` — `.textContent` réécrivait tout le bouton.
   Corrigé en séparant l'icône fixe d'un `<span id="qtcCount">` dédié.
2. `renderRttyMacroBtns()` appelée en fin de fichier (comme
   `voiceRefreshSlots()`) ne trouvait jamais son élément DOM : le panneau
   RTTY est positionné APRÈS les `<script>` dans `logx_logbook.html` (un
   `<script>` s'exécute avant que le HTML qui le SUIT dans le fichier soit
   parsé). Déplacée dans `updateKeyerPanels()`, qui ne s'exécute qu'après
   un DOM complet (poll d'état radio, changement de mode).
3. `.cw-body` n'avait pas de défilement interne (`position:fixed;
   bottom:0`, grandit vers le HAUT sans limite) — le panneau SSTV, agrandi
   par les nouveaux contrôles d'émission, débordait du haut de l'écran sur
   un viewport de test à 910px de haut. `max-height:calc(100vh - 60px)
   ;overflow-y:auto` ajouté sur `.cw-body` (CW/RTTY/SSTV partagent la
   classe), sans effet sur les panneaux qui tenaient déjà.

Livré : `18b68fc` (main), CI verte.
