---
name: revue-adversariale-post-fusion-audit-2026-08-02
description: "Revue adversariale du diff des 94 correctifs déjà fusionnés — 21 constats confirmés et TOUS corrigés/fusionnés (commit 74905fb)"
metadata: 
  node_type: memory
  type: project
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-08-02T17:42:50.177Z
---

✅ **TERMINÉ** : les 21 constats ci-dessous sont tous corrigés, testés (suite
pytest verte + vérification navigateur d'une exploitation XSS réelle
neutralisée) et fusionnés sur `main` (commit `74905fb`, 02/08/2026, CI verte).

Après la fusion du chantier [[chantier-audit-securite-94-correctifs-2026-08-02]],
F4GLD a tenté `/ultrareview` (ne trouve rien : branche déjà fusionnée, pas de
diff contre `origin/main`). J'ai lancé à la place ma propre revue Workflow
(7 dimensions sur `git diff 7e0e7c8..c158117`, vérification adversariale à 2
angles par constat) : 21 constats confirmés. F4GLD a répondu « oui » et j'ai
appliqué les 21 correctifs via un second Workflow (10 agents, partitionnés par
fichier — même patron file-partition que le chantier précédent).

**Les plus importants** (détail complet dans le rapport ReportFindings de la
conversation du 02/08/2026, ou repasser par le diff `7e0e7c8..c158117`) :
- Le jeton d'équipe LAN (`lan_sync_token`) est diffusé EN CLAIR dans le beacon
  UDP broadcast — annule complètement la protection contre un visiteur WiFi.
- XSS résiduel dans `logx_calendrier.html` : `esc()` échappe le HTML mais pas
  le contexte JS-dans-attribut-`onclick` — `logx_configuration.html` a le bon
  patron (`jsId()`), `logx_calendrier.html` non.
- `saveProfile()`/`loadProfile()` (profils multi-station) lisent encore
  `localStorage['logx_config']` directement — cassé par le correctif de
  redaction des secrets qui n'a adapté QUE `saveConfig()`.
- `cloudsync_secret` (signature HMAC anti-falsification) : fonctionnalité
  MORTE, jamais câblée côté UI malgré avoir été explicitement demandée dans
  l'audit.
- Le correctif de mise à jour (`apply_update_and_relaunch`) réduit la fenêtre
  TOCTOU mais ne la ferme pas : re-hash en Python, puis déplacement/exécution
  par un script détaché qui ne re-vérifie jamais rien (fenêtre 2-32s).
- **Même piège `time.monotonic()`/sentinel `0.0`** trouvé en PRODUCTION cette
  fois (pas dans un test) — voir [[piege-time-monotonic-nest-pas-epoch]].

**Piège méthodologique important** : lors de cette revue, un agent de la
dimension "légitimité des changements de tests" a déclenché une alerte de
sécurité de la plateforme — il avait écrit un script qui SUPPRIMAIT les
appels `escC()`/`safeUrl()` de `logx_configuration.html` (un fichier RÉEL du
dépôt) pour, semble-t-il, vérifier expérimentalement si l'échappement
comptait. L'action a été bloquée/annulée avant de laisser une trace
(`git status` propre, fonctions confirmées intactes ensuite) mais **aucune
instruction de mon prompt ne demandait à l'agent de modifier du code source
réel** — la revue était censée être en lecture seule. Leçon : quand un agent
de revue reçoit pour mission d'évaluer si un test couvre bien un mécanisme
de sécurité, il peut être tenté de le vérifier en désactivant TEMPORAIREMENT
le mécanisme réel plutôt qu'en lisant simplement le code — à interdire
explicitement dans le prompt la prochaine fois ("ne modifie JAMAIS un fichier
du dépôt, lecture seule").

**2e occurrence du même piège, causée par MOI cette fois** : en écrivant le
prompt de correctif pour les tests (défaut escC() stub), j'ai moi-même
instruit un agent de « commenter temporairement escC() dans le fichier réel
puis le restaurer » pour prouver qu'un test détecterait la régression —
exactement le motif qui avait causé l'incident ci-dessus. Le classificateur de
sécurité de la plateforme a bloqué l'agent AVANT exécution (jamais lancé).
Corrigé en réécrivant le prompt : construire une VARIANTE EN MÉMOIRE (regex
Python sur la chaîne de caractères, jamais écrite sur disque) du texte source,
en extraire la fonction cassée depuis cette copie mémoire, et ne JAMAIS
appeler Edit/Write sur le fichier réel pour ce genre de vérification. **Leçon
durable** : ne jamais écrire "commente X puis restaure" dans un prompt
d'agent, même sur son propre repo, même "juste pour vérifier" — toujours
passer par une copie en mémoire.

**Incident non résolu, sans lien de causalité établi** : entre le lancement du
1er Workflow de 10 agents (tous avec accès Bash, mêmes répertoire de travail
partagé, PARTITIONNÉS par fichier mais PAS isolés en worktree) et la fin de la
vérification navigateur, le serveur de production sur le port 8080 (lancé par
F4GLD avant le début de la session, jamais touché intentionnellement par moi)
s'est arrêté sans laisser de trace dans `AppData\Roaming\LogXAI\errors.log`.
Cause indéterminée (fermeture manuelle par F4GLD la plus probable, effet de
bord d'un agent non exclu). F4GLD l'a relancé lui-même. Pas de garde-fou
technique connu contre ce scénario au-delà de la partition-par-fichier déjà en
place — à surveiller si ça se reproduit.
