---
name: feedback-installeur-windows-pas-a-chaque-commit
description: "Ne pas reconstruire l'exécutable Windows (.exe PyInstaller) à chaque commit git — seulement à la fin d'un chantier ou sur demande explicite"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: e727f52a-b66b-4617-abb1-afba96fda04d
---

Un `git commit` dans ce projet est UNIQUEMENT un commit de code source. Ne jamais lancer `pyinstaller radiocontest.spec` (reconstruire le `.exe` Windows autonome) automatiquement après chaque commit — l'utilisateur pensait que c'était déjà le cas et a précisé que ce n'est pas souhaité.

**Pourquoi** : l'utilisateur a explicitement clarifié le 19/07/2026 qu'il ne veut PAS que l'installeur soit reconstruit à chaque commit — seulement « à la fin ou sur demande ». Reconstruire à chaque fois serait un gaspillage de temps/ressources pour un artefact qui n'est utile qu'au moment de livrer une version testable.

**Comment appliquer** : continuer à commit normalement (git) après chaque lot de fonctionnalités comme déjà établi dans cette session. Ne proposer/lancer un build PyInstaller (`pyinstaller radiocontest.spec`, voir [[radiocontest-phase0-done]] pour le contexte du packaging initial commit 0502e76) que si l'utilisateur le demande explicitement, ou en toute fin d'un chantier majeur (ex. la roadmap complète) où livrer un exécutable à jour a un sens réel.
