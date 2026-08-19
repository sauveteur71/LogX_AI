---
name: piege-liste-identifiants-ecrite-a-la-main
description: "Une liste d'identifiants de concours codée en dur diverge DANS LES DEUX SENS — 17 concours sans fichier de dépôt, 5 identifiants fantômes (01/08/2026)"
metadata: 
  node_type: memory
  type: project
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-08-01T08:29:24.148Z
---

Deux listes d'identifiants de concours écrites à la main dans `logx_logbook.js`
avaient silencieusement divergé de `CONTEST_DEFINITIONS`. Mesuré, pas supposé :

- **`HF_CONTESTS`** (12 identifiants) pilotait le routage de l'export alors que
  **26** définitions déclarent `log_format: 'CABRILLO'`. **17 concours
  tombaient dans la branche EDI et ne produisaient AUCUN fichier** — « Aucun
  QSO VHF/UHF à exporter » — au moment du dépôt, veille de date limite. WAEDC
  CW/SSB/RTTY, ARRL 10 m et 160 m, Russian DX, EU HF Champ, All Asian, Stew
  Perry, UBA, SP, HA, REF 160 m, les 2 UFT Challenge.
- **`VHF_CONTESTS`** (9 identifiants) : **5 n'existaient pas**, et 7 concours
  THF réels manquaient — dont `REF_CDF_THF` (Championnat de France THF) et
  `IARU_MARCONI`. Statistiques HF affichées pendant toute l'épreuve.
- **8 identifiants fantômes au total** (`IARU_HF`, `WAE_CW`, `WAE_SSB`,
  `DARC_VHF`, `REF_CCD`, `EU_VHF`, `OARC_VHF`, `REF_VHF_UHF_FR`).

**Pourquoi c'est un piège durable :** une liste tenue à la main diverge dans
les DEUX sens à la fois — elle oublie des entrées réelles ET en garde
d'inexistantes. Aucun test ne tombe : les deux listes étaient « cohérentes »
avec elles-mêmes.

**How to apply :** avant d'écrire une liste d'identifiants de concours dans le
client, chercher le CHAMP qui porte l'information dans `CONTEST_DEFINITIONS`
(`log_format`, `bands`, `exchange`…). Il voyage souvent déjà jusqu'au client
via `/data/calendar` sans y être conservé. À défaut de champ, déduire des
DONNÉES (les bandes réellement présentes dans le log) — elles ne périment pas.
Vérifier par un script de comptage, pas à l'œil : `set(definitions) ^
set(liste)` dans les deux sens.

Même famille que [[piege-table-domaine-ecrite-de-memoire]] (table de domaine
écrite au jugé) et [[piege-verifier-sur-donnees-reelles]].
