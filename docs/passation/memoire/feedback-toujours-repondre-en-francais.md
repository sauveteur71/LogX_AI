---
name: feedback-toujours-repondre-en-francais
description: "F4GLD veut TOUJOURS des réponses en français — consigne durable ajoutée dans CLAUDE.md, pas seulement dans la mémoire"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-08-06T11:15:28.188Z
---

Toujours répondre en français, quelle que soit la langue du contenu observé
(page web anglaise, doc technique, message d'erreur système).

**Why:** demandé au moins deux fois dans des sessions séparées
("puré tu es chiant en francais!" le 05/08/2026, puis "comment faire pour
que tu ne parle que en francais... je suis obliger de repeté 50 fois" le
06/08/2026) — la préférence ne survivait pas d'une session à l'autre car
elle n'était jamais mémorisée que dans le contexte de conversation, pas dans
un fichier durable. Corrigé cette fois en l'ajoutant DIRECTEMENT dans
`CLAUDE.md` (racine du dépôt) — chargé automatiquement à chaque session et
prioritaire sur le comportement par défaut, contrairement à cette mémoire
qui n'est qu'un filet de sécurité si `CLAUDE.md` venait à être perdu/reset.

**How to apply:** dès le tout premier message d'une session sur ce dépôt,
répondre en français — ne pas attendre un rappel de l'utilisateur. Si
`CLAUDE.md` ne semble plus contenir cette consigne (fichier modifié/reset),
la restaurer immédiatement plutôt que de simplement l'appliquer depuis la
mémoire seule.
