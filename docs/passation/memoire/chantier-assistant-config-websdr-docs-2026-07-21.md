---
name: chantier-assistant-config-websdr-docs-2026-07-21
description: "Assistant IA config, annuaire WebSDR, guide utilisateur + doc promo — branche feat/aide-config-websdr-guide, 21/07/2026"
metadata: 
  node_type: memory
  type: project
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-07-21T06:32:13.534Z
---

Sur la branche `feat/aide-config-websdr-guide` (partie de `fix/audit-securite-robustesse-perf`, elle-même pas encore mergée dans `main` à cette date), 3 commits en plus de [[audit-securite-qualite-2026-07-20]] :

**1. Assistant de configuration** (`logx_configuration.html`) : icône ❓ auto-ajoutée à côté de ~65 champs connus (dict `CONFIG_HELP` en JS, aide statique sans réseau) + panneau flottant 🤖 qui cherche d'abord dans cette base locale, et si `api_key` est déjà rempli dans le formulaire, interroge `/proxy/ai` avec un system prompt restreint au contenu réel de `CONFIG_HELP` (pour ne jamais halluciner un champ).

**2. Annuaire WebSDR** (`logx_websdr.py` + `logx_websdr.html`, nouvel onglet nav "📡 WEBSDR" sur les 6 pages principales) : 7 récepteurs réels vérifiés par recherche web croisée (SHTSF Le Havre, F4KJI, Twente NL, Northern Utah, MWRS Australie, ZR6AIC Afrique du Sud, APPR Brésil). Test de disponibilité léger côté client (fetch no-cors, une fois au chargement). **Piège découvert** : beaucoup de WebSDR communautaires (ports non-standards 8901/8073, HTTP sans TLS) font échouer WebFetch (`Socket is closed`) — normal, pas un bug outil ; s'appuyer sur WebSearch croisé pour vérifier existence/URL dans ce cas. sdr.hu (l'ancien annuaire de référence) **a fermé** — ne plus le proposer.

**3. Docs** : [`docs/GUIDE_UTILISATEUR.md`](../docs/GUIDE_UTILISATEUR.md) (à tenir à jour à chaque évolution — noté en tête de fichier) et `docs/LogX_AI_Presentation.docx` (document de promotion), tous deux rédigés à partir d'une cartographie de 196 fonctionnalités (120 différenciatrices) produite par un Workflow de 15 agents Explore en parallèle.

**Piège outillage** : ce poste n'a **ni Node/npm, ni pandoc, ni LibreOffice** — le skill docx standard (docx-js) est inutilisable ici. Solution de repli qui marche : `pip install python-docx`, générer le .docx directement en Python (styles/tableaux/image via l'API `docx`). Impossible de faire le rendu PDF de vérification recommandé par le skill (pas de `soffice`) — vérification a minima faite en rouvrant le docx avec `Document()` et en contrôlant les headings/tableaux/mots. Le même souci bloque `esprima`-style validation JS de temps en temps mais celui-là s'installe via pip sans problème (voir [[audit-securite-qualite-2026-07-20]] pour `scratchpad/jscheck.py`).

**Piège classifieur navigate** : `mcp__Claude_Browser__navigate` et parfois `WebFetch` retournent une erreur "temporairement indisponible / denied" de façon intermittente sur ce poste/session — pas un bug de code, retenter plus tard ou utiliser une validation alternative (esprima, tests pytest) en attendant.

**4. Fix scroll latéral logbook** (`logx_logbook.html`) : `.log-panel` (flex item) sans `min-width:0` + `.log-table-wrap` sans `overflow-x` → un tableau à 12 colonnes en `white-space:nowrap` refusait de se rétrécir et poussait tout le layout (bandmap + logbook), scroll horizontal sur toute l'interface. Fix : `min-width:0` sur `.log-panel` et `.log-table-wrap`, `overflow-x:auto` sur `.log-table-wrap`, + réduction padding/letter-spacing des cellules. **Diagnostiqué et vérifié en LIVE sur le serveur réel de l'utilisateur** (`localhost:8080`, déjà lancé, 9389 QSO) via `mcp__Claude_Browser__preview_start` pointé directement dessus + mesure JS `scrollWidth/clientWidth` — pas un serveur de test statique. À sa résolution réelle (1911px) le scroll disparaît totalement (diff 193px→0px) ; sur un écran plus étroit (1536px) un léger scroll réapparaît mais reste confiné au tableau (comportement correct, ne casse plus la page). **Technique réutilisable** : pour tout bug de layout signalé par capture d'écran, vérifier d'abord `netstat -ano | grep :8080` — si le serveur de l'utilisateur tourne déjà, se connecter dessus directement plutôt que de recréer un environnement de test, ça donne un diagnostic exact avec les vraies données.
