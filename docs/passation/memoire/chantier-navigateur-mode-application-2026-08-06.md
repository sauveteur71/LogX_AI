---
name: chantier-navigateur-mode-application-2026-08-06
description: "LogX AI ouvre désormais Chrome/Edge en mode application (sans barre d'adresse ni onglets) au démarrage, plutôt qu'un onglet classique"
metadata: 
  node_type: memory
  type: project
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-08-06T09:25:33.698Z
---

Demande utilisateur, capture d'écran à l'appui : le navigateur s'ouvrait au
démarrage avec toute la barre du navigateur visible (onglets, favoris,
adresse) — gênant pour une appli utilisée comme un logiciel de bureau.

La Fullscreen API du navigateur ne peut PAS être déclenchée automatiquement
au chargement d'une page (restriction de sécurité universelle à tous les
navigateurs modernes, exige un geste utilisateur explicite) — donc rien
n'était possible côté JS/HTML de la page elle-même. La solution vient du
PROCESS Python qui lance le navigateur : Chrome et Edge acceptent l'argument
`--app=URL`, qui ouvre une fenêtre SANS barre d'adresse/onglets/favoris —
pas un vrai kiosk (fenêtre normale, redimensionnable, alt-tab possible,
important puisque l'opérateur bascule souvent vers d'autres logiciels en
concours), juste démarrée maximisée.

`open_browser_app_mode()` (`logx_bootstrap.py`) détecte Chrome/Edge (PATH
via `shutil.which`, puis chemins Windows/macOS connus) et retombe sur
`webbrowser.open()` (onglet classique) si aucun des deux n'est trouvé ou si
le lancement échoue (permissions, exécutable cassé) — ne bloque jamais le
démarrage de l'appli. Seul point d'appel modifié : `start_network_diagnosis()`
dans le même fichier (celui qui ouvre RÉELLEMENT le navigateur, via
`then_open_browser=True`).

**Piège CI trouvé au premier vrai passage (pas en local)** : un test
comparait le résultat à un chemin Windows écrit en dur avec des antislashs
littéraux (`r'C:\Program Files (x86)\Microsoft\Edge\...'`). `os.path.join()`
traite les antislashs comme séparateurs sous Windows mais comme caractères
littéraux sous POSIX — le runner CI (Linux) assemblait donc un résultat
différent. Passait en local (Windows), cassait en CI. Corrigé en calculant
la valeur attendue avec le MÊME `os.path.join()` que le code testé, au lieu
de l'écrire en dur — le test compare alors deux valeurs construites
identiquement quelle que soit la plateforme. Réflexe pour toute future
manipulation de chemin Windows testée en CI multi-plateforme : ne jamais
comparer à un chemin `r'C:\...'` écrit en dur si le test peut tourner sous
Linux — toujours reconstruire l'attendu avec les mêmes primitives que le
code.

Livré : `9179bc0` (main), CI verte. 8 tests, transport/finder injectés
(comme `_open_serial` dans `logx_cat.py`) pour ne dépendre d'aucune
installation Chrome/Edge réelle sur la machine de test.
