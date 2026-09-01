# Section EME opératoire — Tranche 1 : cockpit + suivi lunaire du rotor

**Date :** 2026-09-01 · **Auteur :** F4GLD + Claude · **Branche :** `feat/eme-cockpit`

> Chantier « gros » demandé par F4GLD : construire une section EME
> (Earth-Moon-Earth) opératoire et intégrée. Ce document ne couvre que la
> **Tranche 1** (validée le 2026-09-01). Les tranches suivantes ont leur propre
> spec le moment venu.

## 0. Découverte structurante — ~70 % existe déjà

Une cartographie du dépôt (fichier:ligne à l'appui) a montré que l'essentiel de
la plomberie EME est **déjà présent**. La conséquence directe : le brief initial
(Skyfield, arbre `eme/` complet, rotor Hamlib neuf, décodeur Q65 natif)
**réinventerait** l'existant. On réutilise, on n'ajoute que le manquant.

| Brique | État réel | Fichier |
|---|---|---|
| Position Lune, Doppler EME aller-retour, path-loss, fenêtre commune 2 QTH | ✅ existe (via `ephem`, déjà bundlé) | `concours/logx_eme.py` |
| Rotor **az/EL** (rotctld + GS-232), catalogue marques EME/sat | ✅ existe | `concours/logx_rotor.py` |
| Boucle de suivi az/el continue (bande morte, LOS, échecs bornés, auto-guérison) | ✅ existe (satellite) | `concours/logx_sat_track.py` |
| CAT freq/mode/PTT/puissance (natif + rigctld + Flex/OmniRig/TCI) | ✅ existe | `concours/logx_cat.py`, `logx_rig.py`… |
| Pont WSJT-X/JTDX/MSHV UDP 2237, **mode-agnostique** | ✅ existe | `concours/logx_wsjtx.py` |
| Endpoints `/data/eme_moon`, `/data/eme_doppler`, `/data/eme_window` | ✅ existent | `concours/logx_http.py` |

**Décisions actées d'emblée :**

1. **Pas de Skyfield.** `ephem` fait déjà lune + Doppler + satellites et est
   bundlé PyInstaller. Ajouter Skyfield = ~30 Mo d'éphémérides en doublon.
2. **Q65/JT65 : relais quasi gratuit.** `logx_wsjtx.parse_message` (type 2
   Decode, l.247-262) lit le champ `mode` tel quel ; `recent_decodes()` (l.668)
   rend `call/message/snr/freq_mhz/mode`. La page EME **filtre `mode ∈ {Q65,
   JT65}`**. Aucun décodeur neuf.
3. **Aucune table SQL neuve.** Un QSO EME **reste un QSO** : il se logge déjà via
   le pont (type 5 « QSO Logged », mode préservé) dans le **carnet unique
   chronologique**. La règle verrouillée « jamais un carnet par activité,
   l'activité est une VUE » (`CLAUDE.md`) l'exige. Les métadonnées EME (az/el et
   Doppler à l'instant du QSO) iront dans la colonne `extra` (JSON) — enrichissement
   de tranche suivante, pas de la tranche 1.

## 1. Périmètre de la Tranche 1

**DANS :**
- Page cockpit EME dédiée (`logx_eme.html`) + entrée nav.
- Suivi lunaire **automatique du rotor** (pointage réel, comme le suivi satellite).
- Relais live des décodages Q65/JT65 depuis WSJT-X.
- Doppler + fréquence d'activité **par bande, 144 MHz → 47 GHz**.

**HORS (tranches ultérieures) :** décodeur Q65 natif, machine d'état QSO EME
automatisée, echo test lunaire, split/VFO-B CAT, QMAP large bande, polarisation
automatique, enrichissement `extra` des QSO EME.

## 2. Composants

### 2.1 `concours/logx_moon_track.py` (NEUF)

Boucle de suivi Lune → rotor, **calquée sur `logx_sat_track.py`** et réutilisant
ses sécurités éprouvées. Différences (la Lune est un cas plus simple) :

- `logx_eme.moon_position(lat, lon, alt_m, when)` remplace `sp.position()`.
- **Pas de TLE, pas de pré-pointage AOS, pas de course au TCA** : la Lune bouge
  ~0,5°/min. La bande morte de 4° est atteinte en ~8 min → cadence lente
  (`CADENCE_S = 10`, à ajuster) au lieu de 2 s.
- Refus synchrone si la Lune est **sous l'horizon** au démarrage, avec l'heure du
  prochain lever (`logx_eme.moon_rise_set`).
- Arrêt quand la Lune passe sous l'horizon (équivalent LOS).
- `DUREE_MAX_S` dimensionnée par le **coucher de Lune** (session EME = plusieurs
  heures), plafonnée.
- Résolution rotor : `logx_station.rotor_defaut(cfg, prefer_bandes=['144','432','1296'])`
  (même résolution que `/rotor/point`).

**Sécurités reprises telles quelles de `sat_track` :** Event PAR suivi (jamais
partagé), auto-guérison de l'orphelin, bande morte, détection passage au nord
(`note`), relecture périodique de la VRAIE position rotor, 3 échecs consécutifs
bornés, corps enveloppé de bout en bout (état terminal garanti), aucun appel
réseau dans le handler HTTP.

**API interne :** `demarrer_suivi_lune(cfg) -> (ok, message)`,
`arreter_suivi_lune() -> (ok, message)`, `etat_suivi_lune() -> dict` (JSON-safe :
`actif, phase, cible_az/el, rotor_az/el, envois, visible, note, message`).

### 2.2 Endpoints (NEUFS)

- `POST /moon/track/start` → `demarrer_suivi_lune(cfg)`.
- `POST /moon/track/stop` → `arreter_suivi_lune()`.
- `GET /moon/track/state` → `etat_suivi_lune()`.
- `GET /eme/cockpit` → **agrégateur, sans logique métier neuve.** Compose :
  `logx_eme.moon_position` + `doppler_shift_hz` (sur la **fréquence RF** de la
  bande choisie, cf. §2.4) + `moon_rise_set` + fenêtre commune (si locator DX
  fourni) + état rig (`/hardware/state` réutilisé) + décodages filtrés
  `mode ∈ {Q65,JT65}` + `etat_suivi_lune()`. **Un seul appel de polling** (motif
  `/hardware/state`). Query : `band`, `dx_locator` (optionnel).

### 2.3 `concours/logx_eme.html` (NEUF)

Cockpit. Gabarit standard : `logx_theme.css`, `logx_theme_guard.js`,
`logx_statusbar.js`, `logx_i18n.js`, `<nav class="app-nav">`. Panneaux (densité :
pas d'espace mort, `align-items:flex-start` sur les conteneurs scrollables) :

- **LUNE** : az/el, distance, phase, lever/coucher, **Doppler live** (bande
  choisie), fenêtre commune (champ locator DX).
- **RIG (CAT)** : fréquence/mode/état RX-TX (depuis l'agrégat).
- **DÉCODAGES Q65 / JT65** : liste live `call · message · SNR · fréquence · âge`,
  filtrée par mode. Repli explicite si WSJT-X non connecté (marche à suivre :
  serveur UDP → ce PC:2237, mode Q65/JT65).
- **SUIVI LUNE (rotor)** : boutons start/stop, cible az/el vs rotor réel az/el,
  phase/`note`/message — miroir du widget de suivi satellite.
- **Sélecteur de bande** (144…47088) pilotant Doppler + fréquence d'activité.

Intuitivité : un débutant doit comprendre en un coup d'œil « où est la Lune, qui
j'entends, comment pointer ». Vocabulaire **portable/expédition** (jamais
« activation/activateur »).

### 2.4 Fréquences d'activité EME — VALEURS À SOURCER (IARU R1)

Le Doppler dépend de la **fréquence RF réelle**, pas du dial CAT. Au-dessus de
432 MHz, l'usage passe presque toujours par **transverter** : le dial CAT est
alors une **FI**, pas la RF. Le cockpit doit donc :

- porter une table de **centres d'activité EME par bande**, **configurables** et
  **sourcés du plan de bandes IARU R1** (VHF/UHF/micro-ondes) — jamais codés en
  dur ni devinés. À renseigner à l'implémentation avec la source citée ; d'ici
  là : `VALEUR À SOURCER`. Repères non confirmés fournis par F4GLD à re-vérifier :
  50.190 / 144.100–144.150 / 432.065 / 1296.065 / 2320.065 MHz.
- calculer le Doppler sur cette RF, **signaler visiblement** quand la bande est
  en transverter (dial CAT = FI ≠ RF).

## 3. Flux de données

```
WSJT-X (Q65/JT65) ─UDP 2237→ logx_wsjtx (cache) ─recent_decodes(mode∈Q65,JT65)─┐
ephem ─ logx_eme.moon_position / doppler_shift_hz(RF) / moon_rise_set ─────────┤→ /eme/cockpit ─poll→ navigateur
CAT ─ /hardware/state (freq/mode/PTT) ─────────────────────────────────────────┤   (2–5 s)
logx_moon_track (thread) ─ pointe le rotor ─ etat_suivi_lune() ────────────────┘
navigateur ─POST→ /moon/track/start | /moon/track/stop
```

## 4. Gestion d'erreurs

| Cas | Comportement |
|---|---|
| Lune sous l'horizon au démarrage du suivi | Refus **synchrone** + heure du prochain lever |
| Rotor injoignable | 3 échecs consécutifs bornés → arrêt nommé (repris de `sat_track`) |
| `ephem` absent (`HAS_EPHEM=False`) | Cockpit dégradé proprement (pas de crash), message clair |
| WSJT-X non connecté | Panneau décodages : marche à suivre (UDP 2237, Q65/JT65) |
| rotctld renvoie `nan` | Ne publier que du fini (repris de `sat_track`) |
| Bande > 432 en transverter | Doppler sur RF configurée ; bandeau « dial = FI » |

## 5. Tests — et l'honnêteté sur le non-testable

**Vérifiable côté agent (témoin vert → mutation → restauration → md5) :**
- Logique du suivi lunaire : bande morte, écart azimut (réutilise `ecart_azimut`
  déjà testé), refus horizon, arrêt au coucher, orphelin auto-guéri — **le rotor
  réel est simulé** (banc qui remplace `logx_rotor.set_position/get_position`).
- Filtrage des décodages par mode (Q65/JT65 gardés, FT8/FT4 exclus).
- Forme de l'agrégat `/eme/cockpit` (clés présentes, JSON-safe).
- `i18n` : pas de chaîne brute non passée par `Tf(...)` (test existant).

**NON testable côté agent — validation OBLIGATOIRE côté station, jamais annoncée
« traitée » sans mesure :**
- Pointage rotor réel, pilotage radio réel, décodage de vrais échos EME.
- Cohérence Lune/Doppler : **comparer az/el/Doppler du cockpit à WSJT-X**
  (tolérances du brief : az/el ±0,2°, Doppler ±1 Hz VHF/UHF). C'est la mesure de
  référence, elle se fait en station.

## 6. Ce que la Tranche 1 NE fait volontairement pas

Émission automatique, machine d'état QSO EME, echo test, split/VFO-B, QMAP,
polarisation auto, tables SQL EME. Chacun est une tranche ultérieure avec sa
propre validation. Le principe directeur : **une tranche verticale qui marche et
se vérifie**, plutôt qu'un MVP large à moitié éprouvable.

## 7. Travail « concours EME » parqué (distinct)

À ne pas confondre : 7 définitions du **European EME Contest** (scoring
`prefix_multiplier`) sont commitées en WIP sur `feat/concours-eme`
(schéma + dates 2026 vérifiés ; catalogue/mutation/PR à finir). C'est le
**concours**, pas la **section opératoire** de cette spec. Les deux se
rejoindront plus tard (un QSO EME de concours = un QSO EME loggé).
