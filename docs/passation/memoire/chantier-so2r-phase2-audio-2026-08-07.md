---
name: chantier-so2r-phase2-audio-2026-08-07
description: "SO2R Phase 2 livrée : périphérique vocal (voicekeyer_device2) + second décodeur CW par radio — merge fe7efd7"
metadata: 
  node_type: memory
  type: project
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-08-07T11:45:44.315Z
---

Suite directe de [[chantier-so2r-phase0-1-2026-08-07]], sur simple « ok la
suite » de F4GLD après le récapitulatif Phase 0/1.

**Découverte d'architecture qui a réduit le scope prévu par
`docs/ETUDE_SO2R.md`** : la Phase 2 y listait périphérique vocal + décodeur
CW + panadapter comme 3 chantiers nécessitant chacun un remap SO2R
côté serveur. En lisant le code réel avant d'implémenter, seul le keyer
vocal en a réellement besoin (`/rig/voice` passe par le serveur, remap
`voicekeyer_device` <- `voicekeyer_device2` ajouté dans
`so2r.config_radio_active()`, même motif que `omnirig_rig_num` en Phase 1).
Le décodeur CW (`logx_cwdecoder.js`, `CwAudioDecoder`) et la source audio du
panadapter (`logx_panadapter.html`) sont **100% client-side** — `getUserMedia`
+ `AnalyserNode`/Goertzel, zéro aller-retour serveur — donc **zéro couplage
au focus SO2R possible ou nécessaire** : c'est l'opérateur qui choisit quel
périphérique d'entrée physique correspond à quelle radio, LogX AI ne peut
pas le déduire côté serveur. Livré : un second panneau décodeur CW
(`#cwPanel2`, dupliqué avec suffixe 2 — même convention que `cat_port`/
`cat2_port` — `CwAudioDecoder` déjà réentrante, tourne en VRAI PARALLÈLE du
premier, pas de bascule). Le panadapter n'a nécessité AUCUN changement
(ses sources CI-V/TCI suivent déjà le focus depuis la Phase 0).

**Piège CSS trouvé en vérifiant** : `.cw-panel` (classe) est `position:fixed`
par défaut (pensée pour `#sstvPanel`, resté flottant) ; `#cwPanel` a un
override `position:static` pour s'intégrer dans `.keyer-dock` (bandeau
plein largeur). Dupliquer le HTML avec juste un nouvel id (`#cwPanel2`) sans
dupliquer CET override aurait fait flotter le second panneau par-dessus tout
au lieu de s'empiler proprement dans le bandeau — repéré en lisant le CSS
avant de tester, pas après.

**Piège outillage** : `node` indisponible sur ce poste (ni Bash/git-bash ni
PowerShell) — impossible de faire un `node --check` de syntaxe JS rapide.
Vérification faite entièrement en navigateur réel à la place (console
d'erreurs + `typeof` sur les nouvelles fonctions/variables + `getBoundingClientRect()`
pour confirmer l'absence de chevauchement entre les deux panneaux). Le
`resize_window` du Browser pane n'a pas suffi seul : la hauteur réelle du
body restait bloquée à 415px même avec le préréglage "desktop" — il a fallu
un `resize_window({width, height})` EXPLICITE (1280×1400) pour que
`.keyer-dock` sorte de son état "starved for space" (0-2px) et révèle son
vrai comportement (`max-height:300px` + scroll interne).

**Revue adversariale sautée délibérément** (contrairement à Phase 0/1) :
risque jugé bien plus faible (aucun pilotage TX/PTT impliqué, le remap
vocal suit exactement le motif déjà validé en Phase 1, le décodeur CW ne
touche à AUCUN code serveur) — relu directement à la place. Décision
proportionnée au risque réel, pas un raccourci systématique à reproduire
pour un futur chantier qui toucherait, lui, au pilotage radio.

Reste ouvert (Phase 3 : CAT natif dual + OTRSP matériel, bloquée sans
boîtier disponible ; Phase 4 : UI double-radio, après le refactor frontend
EV-7) — inchangé depuis la fin de Phase 0/1.
