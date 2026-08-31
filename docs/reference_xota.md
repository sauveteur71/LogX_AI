# Section XOTA — programmes « X On The Air » dans LogX AI

Référence de travail (31/08/2026), demandée par F4GLD. Confronte l'architecture
XOTA de référence au **code réel** de LogX et compile les **sources web**, en
distinguant ce qui est **vérifié** de ce qui reste **à confirmer** (règle du
dépôt : aucune valeur de domaine sans source citable).

> **Principe directeur** (repris de la spec, et déjà appliqué par LogX) : **ne
> pas traiter tous les programmes comme POTA.** Chaque programme a ses
> références, seuils, règles de distance, format de log et procédure de
> soumission propres. LogX modélise ça dans un moteur générique — pas des `if`
> éparpillés.

---

## 1. Ce que LogX gère DÉJÀ — le moteur `PROGRAM_SPECS`

`concours/logx_activation.py` porte un **moteur XOTA générique** (`PROGRAM_SPECS`).
Chaque programme y déclare : nom, `sig`, **regex de référence** (`ref_re`),
**QSO minimum** (`min_qso`), libellé P2P, exemple, et — point crucial —
**`adif_tag`** : le **champ ADIF DÉDIÉ** quand la norme ADIF 3.1.5 en définit un,
sinon rien (mécanisme générique `SIG`/`SIG_INFO`).

| Programme | Réf. (regex) | Min QSO | Champ ADIF | Statut LogX |
|---|---|---|---|---|
| **POTA** | `[A-Z0-9]{1,4}-\d{3,5}` (ex. FR-0123) | 10 | `POTA_REF` | ✅ géré |
| **SOTA** | `[A-Z0-9]{1,3}/[A-Z]{2}-\d{3}` (F/AB-001) | 4 | `SOTA_REF` | ✅ géré |
| **IOTA** | `(AF\|AN\|AS\|EU\|NA\|OC\|SA)-\d{3}` (EU-064) | 1 | `IOTA` | ✅ géré |
| **WWFF** | `[A-Z0-9]{1,3}FF-\d{4}` (FFF-0123) | 44 | `WWFF_REF` | ✅ géré |
| **ARLHS** (phares) | `[A-Z]{2,3}-\d{3,4}[A-Z]?` (FRA-113) | 2 | — (SIG) | ✅ géré |
| **WCA** (châteaux) | `[A-Z0-9]{1,4}-\d{4,5}` (DL-00001) | 50 | — (SIG) | ✅ géré |
| **WWBOTA** (bunkers) | `B/[A-Z0-9]{1,3}-\d{4}` (B/G-0001) | 25 | — (SIG) | ✅ géré |
| **ILLW** (phares, événement) | `[A-Z]{2}-\d{4}` (IT-0005) | 1 | — (SIG) | ✅ géré |
| **GMA** (sommets) | `[A-Z0-9]{1,3}/[A-Z]{2}-\d{3}` (DL/BE-055) | 4 | — (SIG) | ✅ géré |

**Ce que ça règle déjà, de ta spec :**
- ✅ Moteur générique (pas de code monolithique par-programme).
- ✅ **Champ ADIF standard** quand il existe (`POTA_REF`/`SOTA_REF`/`WWFF_REF`/
  `IOTA`), **jamais** `MY_SIG_INFO` avec une syntaxe arbitraire pour les autres —
  exactement ta mise en garde. Les programmes sans champ ADIF dédié (ARLHS/WCA/
  WWBOTA) passent par `SIG`/`SIG_INFO` générique.
- ✅ Seuils **par programme** (`min_qso`), fenêtre d'activation par jour UTC.
- ✅ Export **prêt à téléverser** par programme (POTA : nom `callsign@ref-date.adi`).
- ✅ **Log UNIFIÉ** (l'activation est une VUE/filtre, pas une table séparée) —
  choix produit assumé (`CLAUDE.md`), voir la note d'archi ci-dessous.

## 2. Divergence d'architecture assumée (vs la spec)

La spec propose des tables séparées `xota_programs` / `xota_sites` /
`xota_activations` / `qso_xota` (multi-programmes par clés étrangères). **LogX
fait délibérément un carnet UNIQUE** : le multi-programme se porte déjà sur le
QSO via `my_refs`/`refs` (listes `[{program, ref}]`) exportées vers les bons
champs ADIF. C'est la même décision que pour POTA (cf. `docs/verification_log_pota.md`) :
l'activation reste une **vue**, jamais une table — renforcé par l'incident de
perte de carnet du 19/08. **À garder.**

## 3. Programmes À AJOUTER (plugins, ta décision)

Absents de `PROGRAM_SPECS` aujourd'hui. Chacun s'ajouterait comme une entrée du
moteur (regex + min_qso + éventuel champ ADIF), **avec sa source officielle et
sa VERSION de règles** — plusieurs ont des seuils qui ont bougé :

| Programme | Source officielle (vérifiée) | Réf. | Règles (⚠️ à figer par version) |
|---|---|---|---|
| **DFCF** (forts & châteaux FR) | [dfcf.fr](https://dfcf.fr/) · [REF](https://ftp.ref-union.org/index.php?Itemid=303&id=141&option=com_content&view=article) | ex. `DFCF01-001` | **⚠️ distance a évolué (500 m → 1000 m selon additif 2026)** ; 100 QSO HF (50 réactivation), 25 VHF / 15 UHF ; CW+SSB. **À confirmer sur le règlement courant.** |
| **DMF** (moulins FR) | [dmf.r-e-f.org](https://dmf.r-e-f.org/) | `DMF01.001` (dept.numéro) | 100 QSO HF (50 réactivation), 25 VHF ; une seule activité à la fois même si plusieurs moulins < 500 m ; réf. attribuée par le correspondant départemental. |
| **ROTA** (chemins de fer) | rota.barac.org.uk *(fourni, à vérifier)* | réf. ROTA | événement ; assurance requise (source secondaire). |
| **COTA** | ⚠️ **sigle AMBIGU** (COTA-DL, COTA-RU…) — identifier le gestionnaire avant tout code | selon organisme | ne PAS créer une base mondiale COTA unique. |
| **BOTA** (plages) | beachesontheair.com *(fourni, à vérifier)* | réf. BOTA | à confirmer sur le règlement courant. |
| **LOTA / IWI / WAB / WAI** | à identifier | — | plugins avec source configurable. |

## 4. Cas FRANCE 2026 — POTA ≠ PARC Community (à ne PAS confondre)

- **POTA international** : programme officiel sur [pota.app](https://pota.app/),
  règles [docs.pota.app/docs/rules.html](https://docs.pota.app/docs/rules.html).
  Durcissement 2026 des critères de qualification des parcs (propriété/gestion
  publique/limites documentées) — **fait confirmé côté règlement**.
- **PARC Community** (Protected Area Radio Community) : **entité DISTINCTE**,
  approche plus large des espaces FR (ZNIEFF, Natura 2000, réserves…).
  **⚠️ NON documentée techniquement** à ce jour (règlement final, format de réf,
  min QSO, champs ADIF, portail de soumission, API : inconnus). **Statut à
  réserver `experimental`/`unverified`** — ne jamais présenter une activation
  PARC comme officiellement validée, ni réutiliser `MY_SIG=POTA` avec une réf.
  PARC. Provider séparé le jour venu.
- Les chiffres de la controverse (« ~85 % des réf. FR retirées », démission
  F5PYI…) = **sources secondaires**, à ne pas coder comme des faits.

→ Trois programmes **indépendants** : `POTA`, `PARC`, `WWFF`. Références,
règles et exports jamais mélangés.

## 5. Sources web — base de références

Niveaux d'autorité : `official` (site/portail du programme) · `official_database`
(base des réf.) · `regulatory` (réglementation) · `secondary`/`historical`/
`unverified`. **✅ = confirmé cette session ; (fourni) = transcrit de la spec,
à vérifier avant usage en validation.**

### Général / normes
- **ADIF** — spécification du format d'échange : [adif.org.uk](https://adif.org.uk/)
  — ✅ **3.1.7** est la version courante (LogX cite 3.1.5 dans le code ; l'en-tête
  émet `ADIF_VER` 3.1.4 — bump cosmétique possible).
- **REF** (Réseau des Émetteurs Français) : [r-e-f.org](https://www.r-e-f.org/)
- ANFR / Légifrance : réglementation FR *(fourni)*.

### POTA — ✅ vérifié cette session
- Site : <https://pota.app/> · Docs : <https://docs.pota.app/> · Règles :
  <https://docs.pota.app/docs/rules.html> · Soumission des logs (My Log Uploads) :
  page `pota.app/#/user/logs` (LogX l'ouvre déjà). Réf. ADIF POTA : docs.pota.app.

### SOTA — ✅ vérifié cette session
- Site : <https://www.sota.org.uk/> · Règles générales :
  <https://www.sota.org.uk/Joining-In/General-Rules> · Base des sommets :
  <https://www.sotadata.org.uk/> · SOTAwatch/spots. (Accès API : groupe
  *API-consumers* du Reflector — cf. `docs/sota_demande_autorisation_api.md`.)

### WWFF — ✅ vérifié
- Site : <https://wwff.co/> · **Global Rules V5.10 (2025-09-03)** :
  <https://wwff.co/wwff_cont/uploads/2025/09/WWFF-Global-Rules-V_5.10.pdf> ·
  LogSearch / Directory (base des réf.).

### IOTA — ✅ vérifié
- Site : <https://www.iota-world.org/> · Règles :
  <https://www.iota-world.org/iota-directory/iota-programme-rules.html> ·
  Directory des groupes d'îles.

### DFCF — ✅ site officiel vérifié
- <https://dfcf.fr/> · REF/ARML. ⚠️ règlement versionné (distance 500/1000 m).

### DMF — ✅ site officiel vérifié
- <https://dmf.r-e-f.org/>

### WWBOTA / ILLW / GMA / ARLHS — ✅ sources déjà vérifiées dans le code
- WWBOTA : wwbota.net · ILLW : illw.net · GMA : cqgma.org / gma.rocks ·
  ARLHS : arlhs.com. (Cf. commentaires `PROGRAM_SPECS`.)

### WCA / ROTA / COTA / BOTA / LOTA / IWI / WAB / WAI — (fourni, à vérifier)
- Transcrits de ta liste ; plusieurs pages sont anciennes/ambiguës. À confirmer
  (afficher la date de consultation) avant d'en faire des règles bloquantes.

## 6. Reco d'implémentation (si tu ajoutes des programmes)

1. Ajouter l'entrée dans `PROGRAM_SPECS` (regex + min_qso + `adif_tag` **seulement**
   si un champ ADIF dédié existe réellement dans la norme — sinon SIG générique).
2. **Versionner la règle** utilisée (source_url + version + date) pour qu'un vieux
   log reste interprétable avec les règles de son époque — surtout DFCF/DMF/BOTA.
3. Export **séparé par programme** (déjà le cas côté POTA).
4. GPS = **assistant** (avertissement + position enregistrée), **jamais** une
   preuve automatique de validité — décision à l'opérateur.
5. PARC Community : provider séparé, statut `experimental`, **pas** d'export
   présenté comme officiel tant que le règlement/format n'est pas publié.

---

*Aucune modification de code dans ce document — il sert de référence pour décider
quels programmes ajouter et avec quelles sources. Les valeurs marquées ⚠️ ou
(fourni) doivent être confirmées sur la source officielle courante avant d'être
codées comme règles de validation.*
