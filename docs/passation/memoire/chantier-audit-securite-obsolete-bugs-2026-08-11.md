---
name: chantier-audit-securite-obsolete-bugs-2026-08-11
description: "Audit complet sécurité/code obsolète/bugs (workflow multi-agents, 20 agents) + correctifs en 2 PR (#35 critique/majeur, #36 mineurs), 11/08/2026"
metadata: 
  node_type: memory
  type: project
  originSessionId: 98b0707f-1a89-40bf-8422-4ab7b88ba78a
  modified: 2026-08-11T15:00:50.306Z
---

Suite à une demande terse de F4GLD ("verification complete code securité
code obsolete bug...") avec Ultracode actif, lancement d'un Workflow d'audit
(6 agents de recherche : sécurité backend/frontend, code obsolète
backend/frontend, bugs backend/frontend, chacun plafonné à 6 constats) puis
vérification adversariale individuelle de chaque constat (pipeline, pas de
barrière) — 20 agents au total, 14 constats trouvés, **14/14 confirmés, 0
rejeté**. Tous corrigés en 2 PR séparées (critique/majeur d'abord, mineurs
ensuite), chacune avec son propre cycle branche/tests/vérification
navigateur/CI/merge/sync live.

## Constat le plus grave : RCE via `autostart_programs`

Chaîne complète (voir détail dans PR #35) : le serveur écoutait sur
`0.0.0.0` par défaut → `/config/save` distribue automatiquement un jeton
`rc_token` à tout GET tant qu'aucun mot de passe d'accès n'est configuré
(réglage par défaut, documenté comme voulu dans CONFIG > SÉCURITÉ D'ACCÈS
pour l'usage "LAN de confiance") → ce jeton autorise un POST /config/save
avec `autostart_programs` arbitraire → `logx_autostart.lancer()` exécutait
n'importe quel chemin (y compris UNC réseau) sans validation, au prochain
redémarrage du serveur.

**Décision produit prise avec F4GLD (AskUserQuestion)** : « Les deux » —
1) `logx_autostart.py` exige désormais qu'un chemin d'autostart désigne un
   fichier DÉJÀ présent localement (`os.path.isfile`), chemins UNC toujours
   refusés même si `exists_fn` répond vrai.
2) Bind réseau : `127.0.0.1` par défaut (poste local uniquement), `0.0.0.0`
   (LAN/multi-poste/radioclub) devient un réglage EXPLICITE
   (`lan_access`, nouveau toggle CONFIG > SÉCURITÉ D'ACCÈS > ACCÈS RÉSEAU
   (LAN)), effectif au PROCHAIN redémarrage (bind_host décidé une fois au
   démarrage, pas dynamique en cours de route).

**Impact pour les utilisateurs existants (dont F4GLD)** : quiconque
utilisait le mode multi-poste/radioclub avant ce correctif doit RÉ-ACTIVER
`lan_access` dans CONFIG puis redémarrer LogX AI — sinon les autres postes
du réseau ne verront plus le serveur après mise à jour. C'est un changement
de comportement PB défaut intentionnel et approuvé, pas une régression —
mais à rappeler si quelqu'un signale "le multi-poste ne marche plus" après
cette mise à jour.

## Autres constats critiques/majeurs (PR #35)

- XSS stockée sur l'écran mural (`logx_wall.html`, per_band/per_mode/per_op
  sans `esc()`) et le panneau STATS (`logx_rate_panel.js`, `q.band` sans
  `escHtml()`) — même famille d'oubli, deux fichiers différents qui
  échappent systématiquement ailleurs.
- `parseScores()` (`logx_carte.html`) s'appliquait aussi au texte TAPÉ par
  l'opérateur dans le chat IA (pas seulement aux réponses de l'IA) : taper
  "il y a un DX à 850 km" écrasait MEILLEUR DX. Fix : `if(role==='agent')
  parseScores(text)`.
- `logx_update.py` : docstring de `_fetch_release_by_tag()` affirmait un
  appelant (chemin passerelle) qui n'existe pas réellement — le vrai chemin
  est `resolve_relay_asset()`. Docstring corrigée plutôt que suppression
  (fonction gardée comme primitive de bas niveau potentiellement utile).
- `logx_propagation.html` : le `catch` de `focusCharger()` (onglet BANDE
  ACTUELLE) écrasait la dernière liste de spots réelle en prétendant la
  "conserver" à chaque coupure réseau transitoire — piège trouvé car
  `#spots` a TOUJOURS un enfant DOM (placeholder "Chargement…" initial),
  donc un test naïf sur `children.length` ne suffit pas : il faut un
  booléen `focusChargeReussie` dédié.

## Constats mineurs (PR #36)

6 morceaux de code mort supprimés (zéro appelant, grep exhaustif code+tests
avant chaque suppression) : `ampli_par_id()` (logx_station.py),
`station_country()` (logx_wwa.py), `list_websdr()` (logx_websdr.py),
`TciClient.set_power()`/`enable_rx_sensors()` (logx_tci.py),
`getActiveSources()` (logx_configuration.js), 6 exports `window.rc*`
(logx_statusbar.js — les fonctions internes restent, seuls les alias morts
retirés). Plus 2 bugs réels dans `logx_edit_qso.js` : fuite de listener sur
`#editLocator` (nouvel `addEventListener` anonyme à CHAQUE ouverture de la
modale, jamais retiré — corrigé par fonction nommée stable +
`removeEventListener` avant `addEventListener`) et XSS mineure (band/mode
non échappés dans les `<option>`, exploitabilité réduite par le contexte
`<select>`).

## Pièges rencontrés pendant les correctifs

1. **`probe()` de `logx_singleton.py` dépend de `BIND_HOST` en interne** :
   changer le bind réel du serveur exige d'ajouter un paramètre `bind_host`
   à `probe()` (défaut = `BIND_HOST`, rétrocompatible) plutôt que de
   modifier la constante globale — sinon la détection "instance déjà
   lancée" testerait une adresse différente de celle du vrai bind.
2. **`/config` (GET) est une whitelist stricte de 13 champs publics** (pas
   un miroir de `current_config`) et **`/config.json` lit un fichier
   STATIQUE différent** (format imbriqué station/contest, fallback legacy
   pour la page mobile) — aucun des deux n'est le bon endpoint pour vérifier
   qu'un champ CONFIG fraîchement sauvegardé a persisté. Le vrai stockage
   navigateur est `localStorage['logx_config']` (source de vérité pour
   `applyFullConfigToForm()`) ; côté serveur, `current_config` n'est jamais
   exposé en lecture complète (contient potentiellement des secrets) — la
   seule vérification fiable du bind est de REDÉMARRER le serveur et lire
   `netstat`/la bannière console.
3. **Tester un `updateEditDistInfo()` compté sans compter l'appel DIRECT**
   dans `editQSO()` lui-même (`updateEditDistInfo(q.locator)`, une fois par
   ouverture, indépendant du listener) — piège de méthodologie de test, pas
   de bug produit : patcher le mock APRÈS les N ouvertures, juste avant la
   frappe unique à mesurer.
4. Process serveur background tué de façon inattendue (probablement lié à
   une reconnexion MCP en cours de session) — toujours revérifier
   `netstat` avant de supposer qu'un serveur lancé en tâche de fond plus tôt
   tourne encore, surtout après un événement de reconnexion d'outil.

Voir aussi [[chantier-reorg-nav-fusion-propag-focus-2026-08-11]] (PR #33+#34,
chantier précédent le même jour, sans rapport fonctionnel mais meme
session).
