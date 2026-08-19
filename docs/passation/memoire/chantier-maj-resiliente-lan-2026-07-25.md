---
name: chantier-maj-resiliente-lan-2026-07-25
description: "Mise à jour LogX AI résiliente en DXpedition/multi-op (passerelle réseau + relais pair-à-pair de secours), avec vérification SHA-256 — bloqué une fois par le garde-fou anti-RCE, débloqué après autorisation explicite de l'architecture précise"
metadata: 
  node_type: memory
  type: project
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-07-25T11:09:08.508Z
---

Suite directe du retour beta-testeur F6BC ([[chantier-feedback-batch2-2026-07-24]] et la série de chantiers du 25/07). Commits 42f8215 (build) + 1c0ff53/7a41e68/914c1db (3 fixes sécurité issus de la revue adversariale).

**PIÈGE process important** : une première tentative ("le poste A sert directement son exécutable à B, qui l'exécute automatiquement") a été **bloquée par le garde-fou de sécurité anti-RCE** de l'outil Workflow — le classifieur a jugé que "vas-y, lance-le" ne constituait pas une autorisation *spécifique* pour une architecture qui télécharge-puis-exécute un binaire fourni par un pair réseau. Ne pas essayer de contourner ce genre de blocage en reformulant la même tâche : revenir vers l'utilisateur, décrire l'architecture précise (nouveau point HTTP, quoi transite, qui l'exécute), et obtenir une confirmation qui porte sur CES détails-là. Ici, l'utilisateur a répondu via AskUserQuestion en confirmant l'architecture exacte décrite, puis a précisé "1 et 3 en secours" (passerelle réseau en priorité 1, pair-à-pair uniquement si aucun poste n'a internet) — cette clarification a suffi à débloquer le second lancement.

**Architecture retenue (3 volets)** :
- **A (prérequis)** : l'API GitHub Releases expose un champ `digest` (`sha256:<hex>`) par asset — vérifié en direct, présent sur toutes les releases de ce dépôt. Aucun téléchargement (direct/passerelle/pair) n'est accepté sans hash correspondant ; absence de digest fiable → refus, jamais confiance aveugle.
- **B (passerelle réseau, priorité)** : un poste qui a internet relaie une requête vers l'asset GitHub officiel reconstruit **côté serveur** (jamais une URL fournie par l'appelant — anti-SSRF), retransmet en flux. Le contenu reste authentiquement celui de GitHub.
- **C (pair-à-pair, secours STRICT)** : un poste qui a déjà téléchargé+vérifié sert son fichier via un point dédié, toujours le même chemin interne (jamais un chemin client). Activé uniquement si B est indisponible — **vérifié côté serveur** (pas qu'une convention IHM) depuis le fix 914c1db.

**Garantie clé (à ne jamais affaiblir)** : le poste RECEVEUR doit toujours posséder SA PROPRE référence de hash obtenue par contact direct antérieur avec GitHub — jamais une référence fournie par la passerelle ou le pair eux-mêmes. Sans ça, une seule machine compromise pourrait fournir à la fois le contenu ET la preuve de son intégrité.

**3 vraies vulnérabilités trouvées et corrigées par la revue adversariale (pas des faux positifs)** :
1. `/app/update_install` ne contrôlait jamais le flag `verified` avant `apply_update_and_relaunch` — corrigé en verrou défensif explicite, avec un test qui **instrumente** la fonction dangereuse pour prouver qu'elle n'est jamais appelée (pas seulement vérifier le code HTTP 400, qui pouvait être vrai pour la mauvaise raison via `is_frozen()==False` en dev).
2. **SSRF réel** : le champ `ips` du corps JSON client était utilisé tel quel pour construire des requêtes HTTP sortantes serveur → un client pouvait faire sonder/télécharger n'importe quelle IP arbitraire. Corrigé via allowlist stricte aux pairs réellement vus par CE serveur (`peer_versions`, alimenté depuis l'IP socket réelle, jamais un corps de requête) + restriction LAN (regex RFC1918 sur `self.client_address[0]`) + rate limit.
3. Priorité B>C n'était qu'une convention côté `logx_logbook.js` — un appel direct à l'API pouvait forcer le secours même passerelle disponible. Corrigé en sondant `known_lan_ips` côté serveur avant d'autoriser `mode='peer'`.

Vérification indépendante : suite complète 1138/1138 (reproduite 2x), 58 tests dédiés (`tests/test_update_integrity.py`), CI GitHub Actions confirmée verte après push, lecture ligne à ligne des 4 commits (pas que les résumés) avant validation.
