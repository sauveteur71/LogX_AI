---
name: feedback-jamais-citer-concurrents-sauf-open-source
description: "Ne jamais nommer un logiciel concurrent (code/UI/commits/docs) en s'en inspirant, sauf s'il est réellement open source — et viser plus soigné visuellement que lui"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 98b0707f-1a89-40bf-8422-4ab7b88ba78a
  modified: 2026-08-16T07:20:16.391Z
---

Quand une fonctionnalité de LogX AI s'inspire d'un concurrent (ex. SwissLog,
SmartLogger, DXAtlas...), ne JAMAIS citer son nom dans le code, l'UI, les
messages de commit ou la documentation — sauf si ce concurrent est lui-même
un projet réellement **open source** (ex. OmniRig, dont le dépôt GitHub est
public), auquel cas le citer est acceptable. Systématiquement viser un rendu
**plus soigné visuellement** que l'inspiration d'origine, jamais un simple
équivalent.

**Why:** Demandé explicitement le 15/08/2026, au moment d'approuver les 5
évolutions issues d'une recherche concurrentielle (upload LoTW automatique,
bandmap multi-bandes, upload POTA, mini-grille de progression bande×mode,
clavier CW matériel) : « j'ai pas envie que l'on dise qu'on a copié sur les
autres ». Ce n'est pas une pudeur ponctuelle sur ce chantier précis — c'est
une règle de positionnement produit durable : LogX AI doit pouvoir revendiquer
ses fonctionnalités comme les siennes, pas comme des copies visiblement
inspirées d'un concurrent propriétaire nommé.

**How to apply:** Avant de committer une fonctionnalité dont l'idée vient
d'une comparaison concurrentielle (recherche, capture d'écran envoyée par
F4GLD, etc.) : grep le nom du produit source dans le diff (code, docstrings,
commentaires, message de commit, wiki) et le retirer, sauf s'il s'agit d'un
projet open source authentique. Reformuler la fonctionnalité en termes
génériques du domaine (« upload LoTW automatique », « bandmap multi-bandes »)
plutôt qu'en référence à l'implémentation d'un tiers (« comme SwissLog »).
S'applique à tout chantier futur né d'une veille concurrentielle, pas
seulement à celui du 15/08/2026 — voir [[chantier-recherche-concurrentielle-et-decodeur-cw-2026-08-15]]
pour le contexte où c'est apparu et la liste des 5 évolutions approuvées.
