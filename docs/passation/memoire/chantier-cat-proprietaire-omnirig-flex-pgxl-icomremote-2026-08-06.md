---
name: chantier-cat-proprietaire-omnirig-flex-pgxl-icomremote
description: "OmniRig, FlexRadio SmartSDR, Icom réseau (désactivé), PowerGenius XL livrés (06/08/2026, merge 506b944) — recherche doc → 4 pilotes en worktrees parallèles → 2 revues adversariales → intégration dispatch"
metadata: 
  node_type: memory
  type: project
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-08-06T18:10:03.359Z
---

Dernier volet du grand chantier de parité OpsLog (batch ~15 items commencé
plus tôt dans la session) : les 4 protocoles CAT/ampli propriétaires
restants. Livré le 06/08/2026, fusionné sur `main` en `506b944`.

## Déroulé

1. **Recherche documentaire poussée** (mémoire [[reference-protocoles-cat-proprietaires-2026-08-06]])
   — OmniRig/FlexRadio/PowerGenius XL ont une doc OFFICIELLE exploitable ;
   Icom réseau (remote-internet, pas CI-V série) n'a que de la
   rétro-ingénierie communautaire (wfview/kappanhang) ; ACOM n'a AUCUNE
   source nulle part (confirmé deux fois, laissé en attente sur demande
   explicite de F4GLD plutôt qu'écarté comme Antenna Genius).
2. **Implémentation en 4 workflows parallèles**, chacun dans son propre git
   worktree isolé (`agent(..., {isolation:'worktree'})`) pour éviter les
   conflits de fichiers entre agents concurrents — `logx_omnirig.py`,
   `logx_flexradio.py`, `logx_powergenius.py`, `logx_icomremote.py`, chacun
   avec sa suite de tests (98 tests au total), consigne explicite « ne
   jamais mentir sur la confiance » (flaguer en commentaire tout détail
   inféré plutôt que vérifié par WebFetch).
3. **1re revue adversariale** (sur l'implémentation) : 3 des 4 modules avaient
   des bugs réels — exécuteur COM d'OmniRig qui se grippe définitivement
   après un seul blocage (corrigé par auto-guérison, remplacement de
   l'executor après N timeouts consécutifs) ; FlexRadio tuait son thread de
   lecture en silence sur une valeur non finie (`OverflowError` non
   attrapée) + handshake avec le mauvais timeout ; PowerGenius XL avait un
   timeout réseau non borné venant de la config (pouvait geler le thread
   HTTP) + un test cassé par une erreur de précédence Python
   (`A and B or C`). Icom-remote : verdict « prêt tel quel » — désactivé par
   conception (aucune E/S réseau, table de passcode introuvable de façon
   fiable via WebFetch sur du binaire).
4. **Intégration** (câblage dispatch) faite directement par moi (pas
   délégué) — logique de pilotage matériel réel, gardée sous contrôle
   direct : nouvelles branches `cat_mode` 'omnirig'/'flex'/'icom_remote'
   dans `_rig_state_dict_impl()`, le bloc `/rig/qsy`+`/rig/cw`+`/rig/stop`,
   `/rig/connect_test`, `_set_ptt()` ; PowerGenius XL est resté un module
   SÉPARÉ (pas un "brand" de `logx_amp.py`, protocole réseau propre à lui,
   architecture incompatible avec `_make_driver()`/`TcpAmpPort`) avec son
   propre endpoint `/pgxl/test` et sa clé dans `/hardware/state`. CONFIG UI
   : 3 nouvelles options du sélecteur MODE DE PILOTAGE + une section 18
   PowerGenius XL complète (hub+popup+CONFIG_SECTIONS+_catStatus/renderHub).
5. **2e revue adversariale** (sur le câblage d'intégration, 4 dimensions en
   parallèle + vérification adversariale de chaque constat) : 7/7 constats
   confirmés, mais aucun bug de dispatch/sécurité réel — le dispatch et le
   risque matériel étaient corrects. Que des trous de couverture de tests
   (18 tests HTTP de bout en bout ajoutés : `/rig/qsy` refuse proprement en
   mode 'flex' car `logx_flexradio.py` n'a pas de `set_freq`, `/rig/cw`+
   `/rig/stop` refusent pour les 3 nouveaux modes, `/pgxl/test`,
   `/hardware/state` contient bien 'pgxl') + 1 bug cosmétique réel (le
   toggle `pgxl_enabled` n'appelait pas `updateEnabledFieldsVisibility()`
   au chargement/restauration — même défaut « M5 » déjà vu sur
   amp_enabled/rotor_enabled/cloudsync_mode/mqtt_enabled, corrigé).

## Pièges rencontrés PENDANT cette phase (pas avant)

- **`/rig/qsy` et `/rig/connect_test` renvoient 502 en cas d'échec, PAS
  400** (contrairement à `/rig/cw`/`/rig/stop`/`/pgxl/test` qui renvoient
  400) — mes premiers tests HTTP de bout en bout supposaient 400 partout et
  ont échoué ; la convention réelle dépend du endpoint, à revérifier au cas
  par cas plutôt que supposer une constante.
- **`dict.setdefault(k, v) or {...}` n'est PAS `dict.update(k=v) or {...}`**
  — dans un lambda de test, `captured.setdefault('rig_num', 2) or {'ok':True}`
  renvoie `2` (la valeur, un int truthy) au lieu du dict, parce que
  `setdefault()` renvoie la valeur posée, pas `None` comme `update()`. Bug
  dans MON PROPRE test, pas dans le code testé — a fait planter le serveur
  de test avec `AttributeError: 'int' object has no attribute 'get'`.
- **GitHub Actions a de nouveau raté le déclenchement automatique sur push**
  (2 fois dans cette même session, sur 2 pushes différents) — `gh run list`
  restait vide 45-60s après un push qui touchait pourtant bien
  `concours/**`. `gh workflow run "Check LogX AI" --ref <branche>` a
  fonctionné pour forcer le déclenchement manuel (a échoué une fois avec
  HTTP 500 — panne d'infra transitoire côté GitHub, a réussi au 2e essai
  quelques dizaines de secondes plus tard). Réflexe : après un push, si
  `gh run list --branch <branche>` reste vide après ~30-45s, ne pas
  attendre indéfiniment — dispatcher manuellement plutôt que supposer que
  le code est en cause.

## Ce qui reste (backlog OpsLog)

- #162 Télémétrie d'usage anonyme (opt-out) — pas commencé
- #163 MySQL partagé / profils multiples — pas commencé, chantier
  architectural de grande ampleur (~663 références à `shared_log`/
  `save_log_to_disk`/`add_qso_to_log`/`load_log_from_disk` dans 58
  fichiers) — nécessitera probablement une couche d'abstraction de
  stockage avant de brancher un backend MySQL, à concevoir avant d'attaquer
  le code.
- #168 ACOM — laissé explicitement EN ATTENTE sur demande de F4GLD (pas
  écarté comme Antenna Genius, malgré l'absence totale de documentation
  exploitable — décision consciente de garder la porte ouverte).
