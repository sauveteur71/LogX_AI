---
name: piege-serveur-8080-sert-depot-principal-pas-worktree
description: "PIÈGE worktree : le logx_serveur.py déjà lancé sur localhost:8080 sert le DÉPÔT PRINCIPAL (racine SynologyDrive), pas le .claude/worktrees/<nom> courant -- une édition dans le worktree n'apparaît jamais en navigateur tant qu'on pointe sur ce port, même après Ctrl+Shift+R"
metadata: 
  node_type: memory
  type: project
  originSessionId: 0fb18354-9d18-4afb-bdc8-1de32a1b06df
  modified: 2026-08-08T16:35:18.431Z
---

Trouvé le 08/08/2026 en investiguant [[chantier-fix-adaptivepoll-domcontentloaded-2026-08-08]] :
après avoir corrigé `concours/logx_hardware_cat.js` dans le worktree
`nervous-swartz-e7b9bc` et vérifié en navigateur (même avec un vrai
Ctrl+Shift+R, voir [[piege-cache-navigateur-masque-changement-js]]), l'ancien
code buggé continuait de s'exécuter. `fetch('/logx_hardware_cat.js')` depuis
la page elle-même confirmait que le serveur servait bien l'ANCIEN contenu
(setTimeout(0)), identique au fichier sur disque dans le DÉPÔT PRINCIPAL
(`C:\...\Programme pour contest\concours\`, PAS le worktree).

**Cause** : `.claude/launch.json` de ce worktree pointe explicitement
`logx-serveur` vers le chemin absolu du dépôt principal (`runtimeArgs:
["C:/Users/.../Programme pour contest/concours/logx_serveur.py"]`), pas vers
un chemin relatif au worktree — configuration volontaire (probablement pour
que plusieurs sessions/worktrees partagent UN SEUL serveur avec accès au
vrai matériel radio/config, plutôt que d'en faire tourner plusieurs). Le
serveur tournait déjà (processus `python logx_serveur.py`, PID trouvé via
`Get-CimInstance Win32_Process`, cwd = dépôt principal) AVANT le début de la
session — consigne de la tâche : « ne JAMAIS le redémarrer ».

**Comment l'avoir détecté plus tôt** : comparer le contenu réellement servi
(`fetch('/chemin.js').then(r=>r.text())` depuis la page) au contenu du
fichier édité DANS LE WORKTREE (pas juste constater une divergence et
soupçonner le cache) — si l'un correspond au dépôt principal et pas au
worktree, c'est un problème de RÉPERTOIRE SERVI, pas de cache navigateur.

**Comment vérifier un changement JS en navigateur sans toucher au serveur
partagé ni redémarrer quoi que ce soit** : lancer une instance STATIQUE
isolée (`python -m http.server <port> --directory concours`, ajoutée comme
config `.claude/launch.json` locale au worktree, non trackée par git) sur un
port different (8099). Zéro risque : pas de backend donc aucun endpoint
`/config/save` ne peut être appelé par accident (contrairement au piège
[[piege-instance-isolee-partage-server-config]] qui concerne une VRAIE
instance `logx_serveur.py` sur un autre port — celle-là partage quand même
`.server_config.json` avec la prod). Suffisant pour tout bug de comportement
JS pur (ordre de script, timing, rendu) qui ne dépend pas d'un vrai endpoint
serveur ; insuffisant si le test a besoin de vraies données backend (dans ce
cas, il faut soit modifier le dépôt principal temporairement puis `git
checkout --` pour revenir à HEAD après vérification, soit demander à
l'utilisateur).

**How to apply** : dans CE dépôt, avant de conclure qu'un correctif JS "ne
marche pas" en vérification navigateur alors que le fichier sur disque du
worktree est bien à jour, vérifier `.claude/launch.json` du worktree pour
voir si le serveur pointé est un chemin ABSOLU vers le dépôt principal —
si oui, soit appliquer temporairement le même correctif là-bas (fichier non
modifié par ailleurs uniquement, `git checkout --` après coup), soit monter
une instance statique isolée comme ci-dessus.
