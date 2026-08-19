---
name: chantier-lot1-deploiement-club-2026-08-18
description: "Lot 1 pré-déploiement radio-club FUSIONNÉ (PR #108) : sécurité CW, id QSO, filet d'erreurs. La revue adversariale a trouvé 3 défauts DANS le lot, dont 2 qui retournaient les correctifs contre leur propre but"
metadata: 
  node_type: memory
  type: project
  originSessionId: 98b0707f-1a89-40bf-8422-4ab7b88ba78a
  modified: 2026-08-18T11:47:46.996Z
---

Suite de [[audit-architecture-complet-2026-08-18]]. F4GLD a annoncé un
**radio-club qui va utiliser LogX AI en conditions réelles** (concours,
activations spéciales, phonie, **beaucoup de CW**, EME, numérique), en usage
**« trafic courant / entraînement » d'abord** — pas de dépôt de log imminent.

## Ce que ça a tranché

Q1 (concours VS carnet) **s'est dissoute** : le club fait du trafic courant
maintenant et du concours plus tard, donc l'ordre temporel décide. A04
(conformité EDI) et A10 (score × multiplicateurs) — fonctionnellement les plus
importants — ont été **volontairement repoussés** au moment où un concours se
profilera.

Fait marquant relevé dans le carnet de F4GLD (`logx.db`, lecture seule) :
**9 869 QSO sur 15 ans, 0 avec un CONTEST_ID, 97,9 % SSB, 20 QSO CW.**
Il construit donc massivement du CW/contest qu'il ne pratique pas lui-même —
d'où l'importance des essais matériels avec le club (aucun WinKeyer ni OTRSP
jamais branché, écrit dans ses propres docstrings).

## Livré (PR #108, fusionnée)

- **A06** sécurité CW : `/hardware/state` expose le WinKeyer, `#cwStopPanel`
  hors de `#rigPanel` et jamais expert-only, Échap câblé, macros routées vers
  la clé, nouveau jeton `{HISCALL}`.
- **A02** : `/log/add` renvoie l'id attribué ; adopté par le client sur
  **4 chemins** (submitQSO nominal, doublon forcé, netLogQso, syncOfflineQueue).
- **A03** : `handle_error` surchargé + filet 500 JSON sur do_GET/do_POST,
  enveloppés **par délégation** (`_do_GET_impl`/`_do_POST_impl`) plutôt que par
  réindentation de ~5 460 lignes.

## Les 3 défauts trouvés PAR la revue adversariale (33 bruts → 19 confirmés, 14 réfutés)

1. **Le filet d'erreurs polluait le rapport de bogue.** Aucun filtre : une
   déconnexion client normale était journalisée comme un bogue, et
   `formatLastErrorForReport()` ne joint que la **dernière** entrée — la
   déconnexion chassait la vraie panne du signalement. **Le correctif A03
   dégradait exactement ce qu'il visait.** D'où `_est_incident_reseau()`.
2. **`_corps_lu` : invariant faux.** Jamais réinitialisé alors que
   `BaseHTTPRequestHandler` **réutilise la même instance** sur une connexion
   persistante ; et non posé par `/auth/login` qui lit rfile pour son compte →
   relecture → **blocage du fil 30 s** sur une route non authentifiée.
3. **Le coupe-circuit CW dépendait du mode.** Un message parti continue de se
   vider du tampon du manipulateur : changer de mode faisait disparaître le
   bouton ET désarmait Échap **pendant** une émission. Séparé en
   `cwPiloteDisponible()` (arrêt, sans condition de mode) vs
   `cwEmissionPossible()` (routage des macros, avec mode).

## Réflexes confirmés / nouveaux

- **Un correctif de robustesse peut se retourner contre son objectif.** Ne pas
  se contenter de « ça journalise maintenant » : vérifier ce que ça journalise
  et QUI lit le journal en bout de chaîne.
- **Attribut d'instance sur un handler HTTP = état PAR CONNEXION, pas par
  requête** (l'instance est réutilisée). Toujours réinitialiser en tête de
  méthode.
- **Marquer l'INTENTION de consommer, pas la consommation réussie** : poser le
  drapeau AVANT `rfile.read()`, sinon un read qui lève laisse un état faux.
- **Chercher TOUS les sites d'un motif** : j'avais vérifié logbook/mobile/ft8
  pour l'adoption d'id, et manqué `logx_net_control.js` — or le contrôle de net
  est le cas le PLUS exposé (tout un lot enregistré d'un coup = collision d'id).
- **Un test qui fige la forme EXACTE d'une réponse** (`res == {...}`) casse au
  premier champ ajouté sans qu'il y ait régression. Assertions par champ.
  Même famille que le piège des titres à préfixe emoji.
- **L'alias `!` de N1MM a été écrit puis RETIRÉ** : substitution silencieuse de
  tout point d'exclamation, y compris par le presse-papier en phonie. À rouvrir
  en OPTION seulement.
- Changer un libellé passé à `trT()` **casse ses 7 traductions** et laisse
  autant de clés mortes — mettre à jour `logx_i18n.js` dans le même geste.

## Échecs de tests établis comme ÉTRANGERS au lot (ne pas re-suspecter)

- `test_voacap.py::test_predict_reel_avec_le_vrai_binaire` — piège worktree
  déjà documenté, vert sur le dépôt principal (6e+ occurrence).
- `test_update_integrity.py::test_peer_annoncant_le_bon_asset_toujours_accepte`
  — flake intermittent (2/8 en worktree, 0/8 sur le principal, puis 0/12).
  **Démonstration qu'il est étranger au lot** : le test monte son PROPRE
  `ThreadingHTTPServer` + `BaseHTTPRequestHandler`, donc n'emprunte ni
  `LogXHTTPServer` (dont le lot surcharge `handle_error`) ni
  `logx_http.Handler` (dont le lot enveloppe do_GET/do_POST). 3e occurrence du
  motif de [[suite-tests-flakes-sous-charge]] sur ce module — confié au
  chantier séparé task_23bcb4e9. **Les 2 fois précédentes, c'était un VRAI bug
  produit : ne pas le classer flake sans investigation.**

## Suite prévue

Lot 2 (pendant leurs premières semaines) : mode débutant sur FT8/RTTY/SSTV
(**0 élément `expert-only`** sur ces 3 pages, mesuré), étage 1 (nom/QTH/
commentaire récupérés par l'annuaire puis JETÉS à l'enregistrement), A08.
Lot 3 (quand un concours se profile) : A04 puis A10.
Plus : une soirée d'essais avec le matériel du club (WinKeyer, multi-poste).
