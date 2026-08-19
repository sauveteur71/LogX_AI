---
name: projet-ocr-carnet-papier-abandonne
description: "F4GLD a explicitement abandonné l'idée OCR carnet papier — ne plus la reproposer dans le backlog CARTE IA"
metadata: 
  node_type: memory
  type: project
  originSessionId: 98b0707f-1a89-40bf-8422-4ab7b88ba78a
  modified: 2026-08-13T10:02:04.509Z
---

L'idée « OCR carnet papier » (photographier une page de carnet de log papier
pour en extraire les QSO automatiquement) est abandonnée définitivement,
sur décision explicite de F4GLD le 13/08/2026 : « on va oublier l'histoire
de la reconnaissance OCR ».

**Contexte** : cette idée faisait partie du reliquat du backlog de la
refonte CARTE IA. Une recherche préalable (agent dédié) avait déjà conclu
que ce n'était pas buildable dans un lot raisonnable — aucune dépendance
OCR dans le projet (qui n'utilise que la bibliothèque standard + quelques
dépendances optionnelles documentées dans `concours/requirements.txt`), et
le vrai obstacle est la reconnaissance d'écriture manuscrite non
standardisée (pas juste un OCR de texte imprimé), nécessitant un choix de
dépendance à valider + un prototype UX de correction QSO par QSO.

**Comment l'appliquer** : ne plus mentionner cette idée en proposition de
backlog CARTE IA, même si elle réapparaît dans une réflexion sur les
usages Expédition (saisie hors-ligne, carnet de secours). Si le sujet
revient un jour, c'est F4GLD qui le rouvrira lui-même — ne pas la
reproposer proactivement.
