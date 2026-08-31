# Vérification : le log POTA est-il parfaitement géré ? (31/08/2026)

Confronté à l'architecture de référence fournie par F4GLD. **Vérifié contre le
code réel** (fichiers cités), pas sur supposition.

## Verdict

**LogX AI couvre l'intégralité des exigences OPÉRATIONNELLES POTA de ta spec**,
souvent avec des sources officielles déjà vérifiées dans le code. Une seule
**divergence d'architecture assumée** (log unifié vs table `activations`
séparée) et un seul **petit correctif technique** valent d'être signalés.

## Point par point

| Ta spec | LogX AI | Verdict |
|---|---|---|
| **§2 Modèle QSO** : `my_sig`/`my_sig_info` (parc activé), `sig`/`sig_info` (P2P) | Champs **identiques** (`logx_logbook.js` submitQSO, `logx_export.py`) | ✅ conforme |
| **§5 Validation** : CALL, QSO_DATE, TIME_ON, MODE, BAND obligatoires | `isValidQSO` exige call/mode/time/date/rst ; `logx_controles.controle_activation_ref` valide le **format de réf** ; `activation_qsos` suit le min. QSO | ✅ (voir note validation) |
| **§6 Bande depuis fréquence** | `ADIF_BAND` + `_band_from_freq` (`logx_scoring`) | ✅ conforme |
| **§7 Export ADIF** (MY_SIG/MY_SIG_INFO/SIG/SIG_INFO, header ADIF_VER/PROGRAMID) | `logx_export.build_adif` émet tous ces tags | ✅ conforme |
| **§8 Nom de fichier** `callsign@parkRef-date.adi` | `logx_pota.export_filename` produit **exactement** ce format — vérifié contre `docs.pota.app/.../submitting_logs.html` (ex. `KA8H@US-1515-20201127.adi`) | ✅ conforme, sourcé |
| **§9 Park-to-Park** (SIG/SIG_INFO du parc distant) | Champ « réf. correspondant » (programme POTA) → `sig`/`sig_info` sur le QSO | ✅ conforme |
| **§12 Upload** : PAS d'API privée, ouvrir « My Log Uploads » | `exportPotaAdif()` télécharge l'ADIF **et ouvre `pota.app/#/user/logs`** dans un onglet. Politique documentée `logx_pota.py:148` (décision F4GLD 16/08 : pas d'auth non-officielle) | ✅ conforme — **identique à ta reco** |
| **§13 Doublons signalés localement** | `isDup` (saisie) + `validate_log` constat `doublon` | ✅ conforme |
| **§14 Base des parcs** (cache, réf/nom, GPS proximité) | `logx_pota.parks_db` (`all_parks_ext.csv`, ~50 000 parcs, cache disque) : `search`/`get`/`nearby`/`status` | ✅ conforme |
| **§15 IA advisory only** (jamais modifier en silence réf/heure/indicatif/ADIF) | Politique du dépôt (skills `tx-human-consent`, contrôles déterministes) | ✅ conforme |
| **§4 Activation = objet métier** (parc, min QSO, états) | `logx_activation.PROGRAM_SPECS` : POTA `ref_re` + `min_qso=10` ; `activation_qsos()` ; état d'avancement (X/min) | ⚠️ **divergence assumée** (ci-dessous) |
| **§11 Import WSJT-X** enrichi (my_sig=POTA auto) | Import ADIF **préserve** MY_SIG/SIG s'ils existent ; le **FT8 natif** de LogX pose déjà my_sig à l'enregistrement pendant l'activation | ⚠️ enrichissement à l'import externe : voir note |

## Les deux seuls points à discuter

### 1. Divergence d'ARCHITECTURE — VOULUE, pas un manque
Ta spec propose une **table `activations` séparée** + `activation_id` en clé
étrangère sur chaque QSO. **LogX fait délibérément l'inverse** : un **carnet
UNIQUE et chronologique**, toutes activités confondues ; l'activation est une
**VUE/filtre** (`activation_qsos` filtre par `my_sig_info` + jour UTC), pas une
table. C'est une décision produit **explicite** (`CLAUDE.md` : « jamais un
carnet par activité ») renforcée par l'**incident de perte de carnet du
19/08** — multiplier les carnets/tables multiplierait ce risque. Résultat POTA
identique (l'export filtre le bon parc + jour), sans le risque. **À garder tel
quel**, à mon sens.

### 2. Petit correctif technique réel — longueur ADIF en octets
`_adif_field` calcule `<NAME:len>` avec `len(value)` = **nombre de
caractères**. Pour un champ non-ASCII (COMMENT/NAME/QTH avec accents é/è —
fréquent en FR), la longueur devrait être en **OCTETS UTF-8** pour les parseurs
stricts. **Sans impact sur POTA** (call/réf/bande/mode/date sont ASCII), mais
un commentaire accentué pourrait faire mal parser le record ailleurs.
*(Note : ta propre spec §7 fait `len(text)` dans son exemple, tout en
recommandant les octets dans la prose — vraie subtilité ADIF.)* Correctif
sûr et ciblé si tu veux : `len(value.encode('utf-8'))` dans `_adif_field` **et
son jumeau** `logx_export_adif.js` (encoder pareil côté JS), + test round-trip
sur un accent. Je ne l'ai pas fait seul (ça touche TOUT l'export ADIF, pas que
POTA — mérite ton feu vert).

### Note enrichissement import
Le **FT8 natif** de LogX tague déjà `my_sig`/`my_sig_info` à l'enregistrement
pendant une activation. En revanche, importer un **`wsjtx_log.adi` externe**
ne re-tague pas automatiquement les QSO avec le parc actif (ils arrivent sans
MY_SIG). Amélioration possible : à l'import, proposer d'appliquer le parc de
l'activation active aux QSO importés. À décider (petit chantier).

## Conclusion
Le log POTA est **nativement et complètement géré** par LogX — modèle,
validation, export ADIF au bon format et bon nom, P2P, base des parcs, upload
manuel guidé. Rien de bloquant. Deux items optionnels seulement : (1) ne rien
changer à l'archi unifiée (c'est un atout), (2) longueur ADIF en octets si tu
veux durcir l'export pour les accents.
