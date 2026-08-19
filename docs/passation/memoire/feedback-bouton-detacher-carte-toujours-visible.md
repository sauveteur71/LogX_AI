---
name: feedback-bouton-detacher-carte-toujours-visible
description: "Le bouton ⇱ DÉTACHER de CARTE IA doit rester visible dans TOUS les modes (Simple ET Expert), jamais expert-only — confirmé explicitement par F4GLD le 14/08/2026"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 98b0707f-1a89-40bf-8422-4ab7b88ba78a
  modified: 2026-08-14T03:38:51.481Z
---

Le bouton `#detachMapBtn` (« ⇱ DÉTACHER », `concours/logx_carte.html`, détache
la carte dans une fenêtre séparée pour un 2e écran) doit **toujours** avoir la
classe `cfg-btn` seule, **jamais** `expert-only` — visible en mode Simple
comme en mode Expert.

**Why** : lors de la session du 13-14/08/2026, une revue de code automatique
(Workflow adversarial) a suggéré de le passer en `expert-only` au nom de la
règle générale « masquer tout ce qui n'est pas indispensable au chemin
critique d'un débutant » (voir [[chantier-carte-ia-detachable-persistance-echap-2026-08-13]]
pour l'implémentation initiale). Le correctif n'a PAS été appliqué car il
contredisait une demande explicite de F4GLD la même nuit (il s'était plaint
que ce bouton était invisible à cause d'`expert-only` et j'avais retiré la
classe sur sa demande). Le 14/08/2026, revenu de sa pause, F4GLD a confirmé
explicitement : « le bouton detacher de carte only doit apparaitre dans tout
les mode ».

**How to apply** : c'est une exception assumée et permanente à la règle
générale « intuitivité » du projet (CLAUDE.md) — ne pas la re-signaler comme
un manquement lors d'un futur audit d'intuitivité ou d'une revue de code sur
`logx_carte.html`. Si une revue automatique (Workflow, code-review) la
signale à nouveau, la rejeter directement en citant cette mémoire plutôt que
de re-solliciter F4GLD sur un point déjà tranché deux fois.
