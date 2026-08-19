---
name: piege-tests-ecrivent-dans-le-depot
description: "RÉSOLU 01/08/2026 — 26 tests écrivaient des fichiers d'état PARTAGÉS dans concours/ ; le 26e n'était visible QUE parce que le garde-fou photographie la date des DOSSIERS, pas seulement des fichiers"
metadata: 
  node_type: memory
  type: project
  originSessionId: b42ab63e-796d-4e24-a8cf-722d11be6584
  modified: 2026-08-01T12:33:32.654Z
---

Mesuré le 01/08/2026 en cherchant l'intermittence de
`test_awards_activity_days_enorme_est_borne`. **26 tests de la suite écrivaient
dans le répertoire du dépôt**, sur 8 fichiers d'état partagés :
`qsl_confirmations.json` (2 tests), `cloudsync_state.json` + `.cloudsync_instance_id`
(14), `qsl_sync.json` (5), `calldb.json` (2), `cty.dat` (1), `archives/` (2),
`backup_state.json` (1).

**Le mécanisme, reproduit :** deux suites lancées dans le MÊME répertoire
suivent le même ordre, donc arrivent sur le même test à quelques ms d'écart.
`test_awards_qsl.py::test_confirmations_remontent_dans_awards` recevait
`tmp_path` **et ne s'en servait jamais** : il écrivait `qsl_confirmations.json`
dans le cwd puis le supprimait dans son `finally`. Le `os.remove()` de l'une
tombe entre les deux relectures du fichier de l'autre (`history()` puis
`award_summary()` relisent chacune le disque) → `assert 0 == 2`, en 8 ms.
2 échecs sur 6 exécutions concurrentes. Le serveur en direct tourne depuis ce
même répertoire et écrit `calldb.json`, `cty.dat`, `cloudsync_state.json` : une
seule suite suffit alors à créer la course.

## LA leçon de conception du garde-fou

**Une photo avant/après des seuls FICHIERS laisse passer le motif exact qui a
causé le flake.** « J'écris le fichier, je le supprime dans mon `finally` » ne
laisse aucune trace entre deux photos. Il faut photographier **la date des
DOSSIERS** : créer puis supprimer une entrée change le mtime du dossier qui la
contient (vérifié sur NTFS). C'est ainsi qu'a été trouvé le **26e** test,
`test_propagation_plus.py::test_backup_ecrit_et_retention` — absent de
l'inventaire initial, et pire que les autres : il supprimait `backup_state.json`
de la station **sans même le restaurer**.

Deux détails qui coûtent cher si on les oublie :
- deux modules portent chacun leur PROPRE constante du même fichier
  (`logx_awards.CONFIRM_FILE` **et** `logx_qsl.CONFIRM_FILE`) : patcher une
  seule ne protège de rien ;
- `calldb.json` n'a **aucune** constante de module (nom en dur dans
  `logx_qrz`, `logx_callhistory`, `logx_departments`, `logx_wall`) → c'est
  `monkeypatch.chdir(tmp_path)` qu'il faut, pas un `setattr`.

Coût mesuré du garde-fou : **+17 s sur 274 s** (6 %, ~7 ms/test) avec
`os.scandir` — mais **+33 s** avec `os.walk`, qui jette l'information de stat
déjà obtenue par l'énumération et impose un `os.stat()` par fichier.
Échappatoire `LOGX_GARDE_DEPOT=0` si le serveur de la station tourne pendant la
suite (ses écritures seraient imputées à un test innocent).

## Un test VERT uniquement grâce à la pollution

`test_ref_features.py::test_suggest_prefixe_puis_fragment` cherchait `F6KQJ`
dans l'index d'indicatifs. Ses 4 sources (`master_scp.json`, `calldb.json`,
`archives/`, `logx.db`) sont **toutes dans .gitignore** : sur un poste neuf ou
en CI, `suggest('F6K')` ne peut rendre qu'une liste vide. Il ne passait que
parce que `test_qrz.py` injectait F6KQJ dans le `calldb.json` du dépôt. Nettoyer
la pollution l'a fait tomber — **corriger une fuite peut démasquer un test qui
ne testait rien**.

## Vérification

22 exécutions de suites concurrentes (`pytest tests/ -q -p no:randomly` × 2 dans
le même répertoire) : **zéro occurrence de la course**, contre 2 échecs sur 6
avant correction. Résidus déplacés en quarantaine dans
`C:\Users\parri\SynologyDrive\RADIOAMATEUR\_residus_tests_LogX_2026-08-01`
(1402 dossiers d'archive + `qsl_confirmations.json`) ; les 2 vraies archives et
`logx.db` intacts.

**Piège de protocole rencontré :** j'ai édité trois fichiers de tests PENDANT
une passe concurrente ; le garde-fou les a signalés comme écriture dans le
dépôt, et j'ai failli compter mes propres retouches comme un défaut des tests.
Ne rien modifier dans l'arbre pendant une mesure — et lire *quels* fichiers sont
nommés avant de conclure.

## Deux leçons de méthode (inchangées)

1. **Prouver l'invariance avant de chasser une course.** L'hypothèse de départ
   (« la longueur varie donc il y a une course sur le cache TTL ») était
   impossible : le clamp est inconditionnel et la boucle empile exactement
   `days` entrées — vérifié sur **les 21 têtes de branches**.
2. **Ne jamais conclure « famine de l'ordonnanceur, on desserre le délai »
   sans mesure côté serveur.** Sur 15 suites complètes, dont 3 sous charge
   délibérée, **aucune requête au-dessus de 1 s**. Le délai client de 30 s des
   tests HTTP ne doit pas bouger.

## RESTE OUVERT — deux flakes PRÉ-EXISTANTS, sans rapport avec les fichiers

Mesurés indépendants du garde-fou (ils tombent aussi avec `LOGX_GARDE_DEPOT=0`) :

- `test_review_3ab2986_http::test_awards_activity_days_enorme_est_borne` —
  3 fois sur 22. `ConnectionResetError(10054)` **dans `r.read()`**, en-têtes
  reçus et **corps tronqué** alors que `do_GET` a répondu en moins d'une
  seconde. Même famille que le RST corrigé en `8fe6dca`. Reprendre avec un
  reproducteur court sur ce seul endpoint, pas des suites de 5 minutes.
- `test_update_integrity::test_peer_annoncant_le_bon_asset_toujours_accepte` —
  1 fois sur 22, `status='error'` au lieu de `'done'`. La fixture prend un port
  éphémère (pas de collision entre suites) : suspect n° 1 = l'état `_download`,
  **global de module**, lu comme terminal alors qu'il vient d'un test
  précédent. Famille de l'épisode 2 de [[suite-tests-flakes-sous-charge]].

Voir aussi [[suite-tests-flakes-sous-charge]] (les deux fois où un flake était
un vrai bug produit) et [[piege-artefacts-perimes-verification]] (le dépôt
principal est partagé : 10 déplacements de HEAD et des passes pytest
concurrentes le même matin).
