---
name: chantier-fix-op1-adif-station-callsign-2026-08-08
description: "3 bugs LOGBOOK/ADIF signalés par F4GLD corrigés (merge f55eadb) : OP1 affiché au lieu de l'indicatif réel, libellé « log partagé multi-opérateur » trompeur, STATION_CALLSIGN manquant en ADIF serveur — revue adversariale Workflow a trouvé 17 constats supplémentaires, tous corrigés sauf 1 accepté en l'état"
metadata:
  type: project
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-08-08T12:47:24.214Z
---

Correctif livré et fusionné sur `main` le 08/08/2026 (commit `f55eadb`,
merge de `fix/logbook-operator-callsign-adif`, commit de contenu `84cfa6e`).

## 3 signalements F4GLD à l'origine du chantier

1. « en logbook simple il y a que 1 operateur la je viens de faire 2
   contacts avec mon call f4gld et je lis OP1 ! » — LOGBOOK affichait l'ID de
   créneau brut (`operator: 'OP1'`) au lieu de l'indicatif réel partout :
   colonne du tableau, dernier QSO, stats par opérateur, export ADIF/CSV.
2. Screenshot d'une conversation avec le coach IA affirmant à tort être en
   « log partagé multi-opérateur » sur un profil solo — cf.
   [[chantier-fix-libelle-log-partage-2026-08-08]] (même chantier, root
   cause distincte, voir ci-dessous).
3. Implicite dans le signalement #1 : l'export ADIF doit distinguer
   STATION_CALLSIGN (la station) de OPERATOR (la personne), jamais exporter
   l'ID brut comme OPERATOR.

## Mécanisme central : résolution à l'affichage/export, jamais à la source

`_resolveOperatorCallsign(opIdOrCall)` (JS, `logx_logbook.js`) et
`resolve_operator_callsign(op_id, cfg, station_fallback=True)` (Python,
`logx_export.py`, miroir fonctionnel) : `/^OP(\d+)$/i` détecte un ID de
créneau brut, résolu via `cfg.operators[idx].call`, avec repli sur
`callsign_contest`/`callsign` de la station.

**Décision architecturale déterminante** : le champ `operator` stocké SUR le
QSO (`operator: myOp` à la création) reste TOUJOURS l'ID brut — jamais
réécrit. La résolution s'applique UNIQUEMENT aux points d'affichage/export
(`renderLog`, `updateLastQso`, `updateOpStats` — libellé seulement, pas la
clé de regroupement —, `buildAdifText`, `exportCSV`, message `confirm()` de
doublon). Nécessaire car `opColorAttr(q.operator)` (couleur par opérateur)
et le filtre "mine" (`q.operator!==myOp`) exigent l'ID brut pour fonctionner
— vérifié en traçant tous les usages de `myOp`/`.operator` dans le fichier
avant d'implémenter.

## Paramètre `station_fallback` : deux usages différents du même résolveur

Ajouté APRÈS coup (revue adversariale) : un champ qui doit toujours porter
UNE identité (ADIF `OPERATOR`, Cabrillo `OPERATORS:`) replie sur l'indicatif
de la STATION si le créneau n'est pas configuré (`station_fallback=True`,
défaut). Un usage de RÉPARTITION PAR OPÉRATEUR (écran mural `per_op`,
`active_ops`) doit `station_fallback=False` : sans ça, 2 créneaux non
configurés (`OP1`, `OP2`) retombent tous les deux sur le MÊME indicatif de
station et FUSIONNENT silencieusement leurs comptes dans le même bucket —
pire que d'afficher l'ID brut, qui reste au moins distinguable. Piège trouvé
en écrivant les tests : `test_cabrillo_structure` (fixture existante, pas de
`operators[]` configuré) s'est mis à échouer car `CATEGORY-OPERATOR`
(SINGLE-OP/MULTI-OP) était recalculé depuis la liste RÉSOLUE au lieu des
créneaux BRUTS distincts — corrigé en séparant `raw_ops` (comptage) de
`operators` (affichage humain `OPERATORS:`).

## Root cause distincte : libellé « log partagé multi-opérateur »

`logx_prompts.py::build_terrain_context()` étiquetait tout `shared_log` non
vide comme « LOG PARTAGÉ MULTI-OPÉRATEUR » dès qu'il contenait des QSO —
`shared_log` est une liste Python en mémoire, "partagée" entre les ONGLETS
d'un même serveur, PAS entre plusieurs stations réseau. Vérifié en lisant
`.server_config.json` en direct : `mysql_mode='off'`, `cloudsync_mode` vide,
aucune synchro réseau active — juste ~9800 QSO d'historique perso. Corrigé :
le libellé ne s'applique que si 2+ opérateurs RÉELLEMENT distincts sont
détectés (résolvés + normalisés en casse).

## Revue adversariale Workflow : 17 constats supplémentaires, tous traités

4 dimensions en parallèle (`resolver-correctness`, `call-sites-coverage`,
`label-fix-correctness`, `adif-fields-correctness`) + vérification
indépendante sceptique par constat. 17 constats bruts, **17 confirmés**
(aucun réfuté) — inhabituel pour ce projet, où une passe trouve d'ordinaire
un mélange confirmé/réfuté. Traités par catégorie :

**Corrigés directement (même fichiers déjà en cours d'édition)** :
- `_OP_SLOT_RE` : `\d` Python matche tout chiffre Unicode par défaut (pas
  seulement ASCII comme en JS) → `re.ASCII` ajouté.
- `operators[]` mal typé (chaîne au lieu de liste) → `AttributeError` côté
  Python, dégradation silencieuse côté JS → `isinstance()` ajoutés des deux
  côtés de la boucle de résolution.
- STATION_CALLSIGN ignorait `q.my_call` par-QSO (repli uniquement sur
  `cfg`) → même pattern que MY_GRIDSQUARE déjà présent dans la même
  fonction, juste au-dessus, mais pas appliqué à STATION_CALLSIGN par oubli.
- Cabrillo `OPERATORS:` jamais résolu (seul ADIF l'était).
- `confirm()` de doublon (`logx_logbook.js:3705`) : `ex.operator` affiché
  brut dans la boîte de dialogue bloquante — site manqué par les 5 premiers
  points de correction.
- Faux positif du libellé multi-op par MÉLANGE DE FORMAT (pas seulement de
  casse) : un même opérateur physique peut écrire via LOGBOOK ('OP1') ET la
  page FT8 native/WSJT-X (indicatif réel 'F4GLD') dans le MÊME `shared_log`
  → `distinct_ops` comparait des chaînes brutes hétérogènes. Corrigé par
  résolution + `.upper()` avant comptage.

**Étendus à des sous-systèmes non touchés initialement (décision : le
faire quand même, cf. section suivante)** :
- `logx_wall.py`/`logx_wall.html` (écran mural PUBLIC, projecteur/TV en
  expédition) : `_active_operators()`, `per_op`, `recents[].op` affichaient
  l'ID brut — 3 sites, jamais reçu le correctif contrairement à
  LOGBOOK/export. Bonus : le lookup `operators_cfg.get(op.upper())` pour le
  badge SSB/CW/DIGI était cassé silencieusement (comparait un ID de créneau
  à un indicatif) — corrigé du même coup par la résolution en amont.
- `logx_adifnet.py::build_contactinfo_xml()` : diffusion UDP N1MM/DXLog vers
  un poste voisin transmettait `operator` brut.
- `logx_mqtt.py::publish_qso()` : trouvé par un balayage indépendant
  supplémentaire APRÈS la revue Workflow (agent Explore dédié) — publication
  MQTT vers un tableau de bord tiers (Node-RED, Home Assistant) transmettait
  aussi l'ID brut. Pas dans les 17 constats initiaux : preuve qu'un
  deuxième passage de balayage après coup trouve encore des choses.

**Accepté en l'état, non corrigé (documenté)** :
- Asymétrie mineure : le repli JS (`resolved || cfg.callsign_contest ||
  cfg.callsign || myCall || raw`) a une étape de plus que le Python
  (`myCall`, variable de session côté client) — aucun équivalent serveur
  n'existe (pas de "valeur actuellement tapée dans un onglet" côté Python).
  Édge case : config vidée pendant qu'un onglet LOGBOOK reste ouvert avec un
  `myCall` figé. Corriger aurait nécessité soit inventer un état côté
  serveur, soit modifier le comportement JS existant (risque de régression
  UX) pour un scénario narrow — jugement d'ingénieur : accepté, pas dans le
  scope de "avoir un miroir parfait bit-à-bit" mais "résoudre le bug
  utilisateur réel".

## Décision de périmètre : étendre au-delà des 3 signalements initiaux

L'utilisateur a explicitement autorisé 3h de travail autonome pendant une
sieste (« JE VAIS FAIRE UNE SIESTE TU AS 3 HEURES POUR TRAVAILLER TOUT SEUL
SANS T'ARRETER ») — décision prise de traiter aussi les constats initialement
étiquetés [DIFFÉRÉ] (`logx_wall.py`, `logx_adifnet.py`) sur la MÊME branche
plutôt que de les reporter, contrairement à la pratique habituelle de ce
projet ("reliquat séparé" documentée dans plusieurs mémoires précédentes,
ex. [[chantier-config-sidebar-nav-2026-08-08]]) — justifié ici par : (a) le
temps disponible, (b) chaque site restait un ajout de 3-5 lignes réutilisant
la MÊME fonction déjà écrite et testée (`resolve_operator_callsign`), pas une
nouvelle investigation, (c) tests dédiés ajoutés et suite complète 2x verte
avant fusion — le risque de régression restait donc faible malgré
l'élargissement de scope.

## Chiffres

12 fichiers modifiés, 377 insertions/25 suppressions. 10 tests ajoutés
(5 `test_export.py`, 1 `test_prompts_terrain_context_label.py` [nouveau
fichier, 5 tests au total], 4 `test_wall_roulement.py`, 1 `test_adifnet.py`,
1 `test_mqtt.py`). Suite complète : 8790 tests, 2 passes vertes.

## Vérification navigateur : piège localStorage retrouvé

Vérification DOM-only (jamais de vrai doublon réseau ni de vrai
`saveConfig()`) sur le serveur de production (port 8080, jamais
redémarré) : `_resolveOperatorCallsign` et le site `confirm()` testés via
`javascript_tool` en manipulant `localStorage.logx_config` directement.
**Piège retrouvé** : recharger la page (même avec `force:true`) NE
resynchronise PAS `localStorage.logx_config` depuis le serveur — la valeur
de test (`callsign: 'F6KQJ'`) est restée en cache après le reload, alors que
le vrai config serveur (`GET /config`) portait `F4GLD/P`. Halluciné un
"réhydratation automatique au chargement" qui n'existe pas. Corrigé en
refetchant `/config` et en réécrivant `localStorage` avec les vraies
valeurs avant de continuer — sinon cet onglet du navigateur intégré serait
resté dans un état trompeur pour la suite de la session.
