---
name: chantier-audit-pre-beta-2026-08-05
description: "Audit complet bug/sécurité/qualité avant future bêta — 58 constats confirmés, 2 critiques, appliqués + vérifiés (`2eae891`, 05/08/2026)"
metadata: 
  node_type: memory
  type: project
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-08-05T08:46:18.324Z
---

Demande F4GLD : « fait une passe de verification complete bug, corection de
code, securité ect avant de lancer la future beta ». Ultracode actif →
traité comme un chantier à deux workflows successifs :

1. **Revue** (30 lots domaine, tout le dépôt ~77k lignes backend+frontend,
   serveur HTTP découpé en 7 tranches vu sa taille/criticité) → 127 agents,
   58 constats confirmés après vérification adversariale (2 critiques, 12
   hauts, 27 moyens, 17 bas). Repère utile : sur un dépôt déjà audité 3 fois
   par le passé (94+113+21 correctifs), la densité de bugs neufs trouvés
   reste élevée — ne jamais supposer qu'un code "déjà audité" est clean.
2. **Correction** (33 lots PAR FICHIER, disjoints exprès pour paralléliser
   sans conflit d'édition) → chaque agent applique le correctif déjà
   pré-mâché par la vérification adversariale (fichier+ligne+code exact).

**2 bugs critiques trouvés** : pilotage ampli (KpaAmp/IcomAmp/SpeAmp)
appelait `self.t.read_until()` sur un transport qui ne l'exposait pas —
AttributeError garanti sur tout ampli RÉEL, masqué par des mocks de test qui
définissaient `read_until` alors que le vrai `SerialPort` ne l'avait pas
(même famille que [[piege-pyserial-rts-dtr-constructeur]] : le mock est plus
permissif que la réalité). Et XSS stocké via `/log/add` (indicatif non
échappé dans `updateBandRecap()`), exécuté automatiquement chez TOUS les
opérateurs connectés dès qu'un QSO forgé devient "meilleur DX" d'une bande.

🚨 **PIÈGE MAJEUR découvert pendant l'exécution — à relire avant tout futur
chantier à agents parallèles sur ce dépôt** : le dossier de travail est sous
`SynologyDrive\...`. Sur PLUSIEURS agents indépendants du lot de correction
(cloudsync, logbook_js, qsl, prompts, rules, utils_clusters, tci — au moins
7 sur 33), un fichier édité avec succès a été **silencieusement ramené à son
contenu d'AVANT édition** entre deux appels d'outils, détecté seulement par
relecture (`Read`/`git diff`) — jamais signalé par une erreur explicite sauf
le message Edit "modifié sur disque depuis la dernière lecture". La plupart
des agents ont détecté et corrigé eux-mêmes le problème et l'ont documenté
dans leur rapport final — **mais PAS TOUS** : `logx_cloudsync.py` (constat
#3) et `logx_update.py` (constat #23) sont restés silencieusement NON
corrigés malgré le rapport de l'agent affirmant le contraire ("Tests : Tous
verts... Correctif appliqué"). Trouvé uniquement par une **passe de
vérification indépendante par grep sur les 58 constats un par un**, faite
par l'agent orchestrateur (moi) après coup, PAS en faisant confiance aux
rapports. Corrigés manuellement après coup. **Leçon actionnable pour la
prochaine fois** : après tout chantier à agents parallèles éditant des
fichiers dans ce dépôt (workflow OU agents `Agent` classiques), TOUJOURS
regrepper soi-même chaque changement attendu contre le disque avant de
committer — ne jamais se contenter du rapport `testsResult`/`notes` d'un
agent, même détaillé et même quand il affirme avoir lui-même détecté et
corrigé un incident similaire. Cause probable : synchronisation cloud du
dossier de travail entrant en course avec l'écriture locale — pas confirmée
avec certitude, mais le motif (perte transitoire puis fichier stable) colle.

**Bug supplémentaire trouvé par la vérification navigateur EN DIRECT**
(hors des 58 constats de l'audit) : horloge d'en-tête (`updateClockAndCondown`
dans `logx_logbook.js`) faisait `document.getElementById('clock').textContent
= ...` sans garde, plantait en boucle (`setInterval` 1s) sur un onglet neuf
au tout début du chargement de page — le voisin `setCountdownLabel()` juste
au-dessus avait déjà la garde `if(!lbl)return`, celle-ci avait été oubliée.
Trouvé en ouvrant un ONGLET NEUF (jamais réutilisé) après le déploiement des
correctifs — un onglet réutilisé de la session gardait un historique de
console trompeur qui semblait indiquer un bug permanent alors qu'il
s'agissait d'anciens logs jamais vidés. Réflexe à garder : pour une revue
console propre, toujours un onglet fraîchement créé, jamais un onglet déjà
navigué plusieurs fois dans la session.

**Incident sans rapport avec le code** : le serveur de production (port
8080) s'est arrêté de lui-même en cours de session (aucun processus Python
trouvé) — pas causé par moi (je n'ai fait qu'éditer des fichiers sur
disque), signalé à l'utilisateur sans redémarrage de ma part (règle
d'environnement), l'utilisateur l'a relancé lui-même ("c'est relancé").

Suite pytest complète (194 fichiers) verte après CHAQUE étape (revue, lots
de correction, réapplication des 2 pertes, fix horloge). Commit unique
`51bd749` → merge `2eae891` sur `main`, CI verte confirmée avant et après
merge.
