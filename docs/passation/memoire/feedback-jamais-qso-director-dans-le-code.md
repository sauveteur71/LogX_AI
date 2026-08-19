---
name: feedback-jamais-qso-director-dans-le-code
description: "Ne jamais écrire les mots 'QSO Director' dans le code/UI de RadioContest AI (concours/), même en comparaison ou commentaire"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: e727f52a-b66b-4617-abb1-afba96fda04d
---

Ne jamais faire apparaître les mots « QSO Director » (ni variantes de casse) dans un fichier sous `concours/` — code source, UI, JS, JSON, commentaires, noms de fichiers. Interdiction absolue, répétée verbatim deux fois par l'utilisateur dans la même session (18/07/2026) : « pense a ne jamais reprendre les mots "qso director" dans mon programme ! ».

**Pourquoi** : QSO Director est le logiciel concurrent analysé pour en tirer des idées fonctionnelles (voir [[qso-director-parity]]) — l'utilisateur ne veut aucune trace de son nom dans SON propre logiciel, probablement pour éviter toute confusion de marque ou référence à un concurrent dans un produit qui doit rester 100 % RadioContest AI.

**Comment appliquer** : la mémoire de travail (fichiers sous `.claude/projects/.../memory/`) et le document `Analyse_QSODirector_Roadmap.md` (à la racine du projet, HORS de `concours/`, jamais committé avec l'appli) peuvent continuer à nommer QSO Director pour le suivi interne — seul `concours/` (l'application livrée) est concerné par l'interdiction. Avant tout commit touchant `concours/`, vérifier par un grep insensible à la casse (`grep -ri "qso.?director" concours/`) que rien n'a fuité — fait systématiquement lors des lots liés à cette roadmap, toujours resté propre jusqu'ici.
