---
name: chantier-cat-adresse-civ-manuelle-2026-08
description: "Champ CONFIG « adresse CI-V (avancé) » pour la radio principale (logx_cat.py/logx_configuration.html) — follow-up flagué du chantier CAT plug-and-play, terminé"
metadata: 
  node_type: memory
  type: project
  modified: 2026-08-03T18:35:54.166Z
  originSessionId: dbfaf083-272e-4900-aba6-1be8881c46fe
---

Suite de [[chantier-cat-plug-and-play-2026-08]] : ce chantier avait flagué
« Permettre de configurer l'adresse CI-V de la radio PRINCIPALE dans CONFIG
(seul l'ampli a ce champ aujourd'hui) — pré-existant, indépendant de ce
chantier ». Fait le 03/08/2026, sur exactement le périmètre demandé (radio
principale, `logx_cat.py`/`logx_configuration.html`).

**Implémenté**, en calquant le pattern déjà existant pour l'ampli
(`amp_civ_addr`, `logx_amp.py`) :
- `logx_cat.py` : `_parse_civ_addr()` (texte hexa -> int ou None, jamais
  d'exception), `cat_settings()` renvoie désormais `civ_addr` = adresse
  manuelle (`cat_civ_addr`) si présente et valide, sinon repli sur
  `CIV_ADDRESSES.get(model, 0x94)`. `_ensure_connected()` et
  `test_connection()` (nouveau param `civ_addr=None`) utilisent cette
  adresse au lieu de relire `CIV_ADDRESSES` eux-mêmes.
- `logx_http.py` : `/rig/connect_test` transmet `payload.get('civ_addr')`
  à `cat.test_connection()`.
- `logx_configuration.html` : nouveau champ `#cat_civ_addr` dans la popup
  RADIO (section native), visible seulement pour Icom/Xiegu (même bascule
  que `#ampCivAddrField`), câblé dans le test de connexion, la sauvegarde
  et la restauration de config, + entrée `CONFIG_HELP`.
- `tests/test_cat.py` : cat_settings (repli modèle/manuel/invalide/vide),
  `_ensure_connected`/`get_state` avec une fausse radio qui ne répond QU'À
  l'adresse manuelle (preuve que l'adresse est réellement utilisée sur le
  fil, pas juste acceptée), reconnexion déclenchée par un changement de
  civ_addr SEUL, `test_connection()` avec/sans adresse manuelle.

🚨 **Piège trouvé en écrivant les tests** : `_ensure_connected()` construit
son tuple `key` (utilisé pour décider si la connexion persistante doit être
rouverte) en lisant `settings['civ_addr']` **avant** tout early-return (port
vide, modèle non pilotable...) — cohérent avec le style existant
(`settings['brand']`/`['model']` déjà lus pareil), mais ça veut dire que
TOUT dict passé directement à `_ensure_connected()` doit désormais contenir
la clé `civ_addr`, sinon `KeyError` immédiat. Cassé 3 tests qui appelaient
`_ensure_connected()` avec un dict à la main sans passer par
`cat_settings()` (`tests/test_cat.py::test_ensure_connected_port_manquant`,
`tests/test_cat_yaesu_famille.py` x2) — corrigés en ajoutant `'civ_addr':
0x94` à ces dicts. Réflexe pour toute future extension de `cat_settings()`/
`amp_settings()` : grep tous les appels DIRECTS de `_ensure_connected()`
dans les tests (pas seulement via `cat_settings()`/`get_state()`/
`set_freq()`), ils contournent le constructeur et n'ont pas la nouvelle clé.

**Vérifié en navigateur** (`concours/logx_configuration.html` via
preview_start) : bascule de visibilité par marque (Icom/Xiegu -> visible,
Yaesu -> masqué), texte d'aide (`CONFIG_HELP['cat_civ_addr']`) résolu,
valeur round-trip sauvegarde -> `localStorage['logx_config']` -> rechargement
de page -> champ pré-rempli + visible. `screenshot`/`computer` de
Claude_Browser étaient indisponibles dans cette session (pane non affiché) —
vérifié uniquement via `javascript_tool` (lecture directe du DOM/
localStorage), suffisant ici mais à garder à l'esprit si un test visuel
(couleurs, layout) est un jour nécessaire sur ce même environnement.

**Hors scope, assumé** : la 2e radio SO2R a le même trou — `logx_so2r.py`
(`config_radio_active()`) anticipe déjà une clé `cat2_civ_addr` dans sa
liste de correspondance cat2_* -> cat_*, mais AUCUN champ `#cat2_civ_addr`
n'existe dans `logx_configuration.html` (contrairement à `cat2_brand`/
`cat2_port`/`cat2_baudrate`, qui eux existent). Le radio focus 2 ne peut
donc jamais bénéficier d'une adresse CI-V manuelle. Pas traité ici car hors
du périmètre demandé (« radio principale » uniquement) — à faire si
quelqu'un utilise réellement SO2R avec une 2e radio Icom reconfigurée.
