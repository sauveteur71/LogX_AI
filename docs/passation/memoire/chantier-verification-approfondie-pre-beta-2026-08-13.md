---
name: chantier-verification-approfondie-pre-beta-2026-08-13
description: "Vérification approfondie avant bêta (bugs/qualité/simplification/intuitivité) — 2 workflows, 37 correctifs confirmés dont un bug de score CQ WPX, PR #59"
metadata: 
  node_type: memory
  type: project
  originSessionId: 98b0707f-1a89-40bf-8422-4ab7b88ba78a
  modified: 2026-08-13T11:21:46.796Z
---

Demande F4GLD 13/08/2026 : « vérification approfondie bugs verification du codage
simplification allegement... et surtout l'intuitivité » avant d'envisager une bêta.
Corrigé initialement pour cibler CARTE IA seule, puis élargi explicitement par
F4GLD (« pas que la carte ia tout le programme! ») — leçon : quand on demande une
vérification "avant bêta", partir du principe que c'est tout le programme sauf
précision contraire.

**Méthode** : 2 Workflows en parallèle (recherche par dimension → vérification
adversariale 2 votes/constat, réfutation par défaut → correctifs en worktrees
isolés). Premier scopé à CARTE IA + code ajouté dans la session (6 dimensions,
21/24 constats confirmés). Second sur le reste du programme — 104 fichiers Python
+ 3 pages HTML jamais retouchées cette session, découpé en 7 domaines fonctionnels
(scoring/diplômes, stockage/log, serveur HTTP/sécurité, matériel CAT, cluster/
propagation/activation, réseau multi-poste/IA, pages restantes+intuitivité globale)
— 16/16 constats confirmés (taux de confirmation exceptionnellement élevé, signal
propre). PR #59, 37 correctifs fusionnés au total.

**Le plus important trouvé** : le score CQ WPX (SSB et CW) n'implémentait JAMAIS
le doublement de points sur les bandes basses (80/40/160m) exigé par le règlement
officiel — faussait silencieusement le score EN DIRECT et le CLAUDE-SCORE du
fichier Cabrillo réellement soumis au comité CQ, pour n'importe quel opérateur
ayant joué ce concours depuis son introduction dans le logiciel. Personne ne
l'avait remarqué car aucun test n'exerçait la valeur réelle de calc_qso_value()
pour ce concours précis — seul un agent qui a exécuté le moteur en réel (pas
juste lu le code) l'a détecté. Voir aussi le bug SO2R (bouton STOP routait vers
la radio ayant le FOCUS, pas celle qui émettait réellement) et l'injection
Cabrillo via le champ `band` non assaini à l'import ADIF.

**2 décisions produit laissées ouvertes, pas des bugs à corriger sans arbitrage** :
- `answer_text()` (logx_coach.py, réponse serveur `/coach/answer`) ne couvre que
  5 des 10 topics de CARTE IA (score/prop/openings/mults/resume) — performance/
  debrief/coordbrief/memoire ont leur propre fonction+endpoint dédiés côté client
  mais retombent sur `return ''` si jamais on appelle `/coach/answer` directement
  pour eux. Unifier les deux tables (ou étendre answer_text) est un choix à
  trancher consciemment, pas une simplification sûre — non fait.
- `debriefIA()` (logx_carte.html) fait un double fetch de `/coach/debrief` en
  palier Basique (une fois pour vérifier qso_total>0, une fois dans
  basiqueDebriefAnswer()) — réutiliser le premier appel introduirait une fenêtre
  de données plus périmées qu'aujourd'hui (le log peut changer entre les deux
  appels). Laissé tel quel.

**Piège d'orchestration confirmé (déjà documenté ailleurs, revu ici)** : les
rapports texte libre des agents de correction se trompent parfois sur le nom de
LEUR PROPRE branche/worktree (plusieurs ont annoncé "feature/carte-ia-backlog-suite"
alors que `git worktree list` donnait la vraie réponse, un nom sans rapport d'une
branche déjà fusionnée et supprimée plus tôt dans la session) — toujours vérifier
via `git worktree list`, jamais faire confiance à la prose de l'agent pour le nom
de branche à fusionner.

Voir aussi [[piege-continuer-nouveau-chantier-sur-branche-pr-deja-creee]] pour la
discipline de branche déjà établie, et le chantier CARTE IA (refonte 3 paliers)
pour le contexte du code vérifié.
