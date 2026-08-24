# Refonte de la saisie du LOGBOOK (sous-chantier A) — design

Écrit le 24/08/2026. Validé en brainstorming avec F4GLD (mise en page « bandeau
fixe + onglets », tags multi-activité et références multiples intégrés à A).

Ce document est la **spec** de A. Il ne couvre PAS B (unification/complétude de
l'export ADIF) ni C (familles FT8/contest, couverture d'activités absentes) —
mais il pose les clés de données pour que B n'ait qu'à les mapper.

---

## 1. Objectif

Rendre la fenêtre de saisie du carnet **complète** (couverture des champs utiles,
saisissables) et **propre** (rangée, non noyée) **tout en restant simple** : le
trafic quotidien ne doit pas être ralenti, et un débutant doit comprendre l'écran
en un coup d'œil.

Deux capacités nouvelles demandées explicitement :
- **Tags multi-activité cumulés** sur un même QSO (ex. FT8 + SOTA + QRP + DX +
  PORTABLE), cherchables — aujourd'hui le modèle est mono-slot (`contest`).
- **Références multiples simultanées** : une même activation peut être SOTA *et*
  POTA *et* WWFF (« two-fer ») — aujourd'hui `my_sig`/`my_sig_info` est unique.

## 2. État de départ (mesuré, audit du 24/08)

- **Stockage à schéma OUVERT** : `logx_storage.py` (table `qso` = 10 colonnes
  `_CORE` + blob `extra` JSON ; `_row_from_qso()` sérialise tout champ hors
  `_CORE` dans `extra` sans migration). → **tout nouveau champ persiste
  automatiquement** ; l'écart n'est PAS au stockage.
- **Saisie** = un seul formulaire déroulant, **pas d'onglets**, pas de
  divulgation progressive structurée (seulement `expert-only` CSS + quelques
  groupes `display:none` contextuels). Champs présents : indicatif, RST env/reçu
  (défaut `59`), N° env/reçu, bande/mode/opérateur (bouton+popup), fréquence,
  locator, commentaire, réf. correspondant (activation). **Non saisissables** :
  nom, QTH, pays, état (annuaire seul) ; **puissance absente de bout en bout**.
- Références d'activation : `logx_activation.py` `PROGRAM_SPECS` (POTA, SOTA,
  IOTA, WWFF, WCA, ARLHS) → un seul `my_sig`/`my_sig_info` à la fois.
- Prop_mode : seul `SAT` est tagué (auto, `logx_satellites.py`). ES/TROPO/EME/MS
  sont surveillés mais jamais consignés sur un QSO.
- Lieu d'exploitation : aucun champ ; seulement profils d'assistant + détection
  de suffixe `/P` `/MM`.
- Tags multi-activité : **absents** ; `contest` est mono-slot.
- Listes de domaine déjà présentes à réutiliser (NE PAS réinventer) :
  `logx_adif_enums.py` (`ADIF_MODES`), `logx_activation.py` (`PROGRAM_SPECS`),
  `logx_cat.py` (`MODES_NUMERIQUES`/`MODES_PHONIE`).

## 3. Contraintes (non négociables)

1. **Chemin critique jamais cachable** (CLAUDE.md) : indicatif, RST, échange,
   bande/mode, bouton d'enregistrement, navigation CONFIG↔LOGBOOK. → il reste
   dans un **bandeau permanent**, jamais derrière un onglet.
2. **Identité graphite & cuivre** (pas de clone web générique) ; vérif **jour ET
   nuit** obligatoire.
3. **Aucune valeur de domaine inventée** : listes (modes, prop_mode, programmes,
   lieux) issues des tables existantes + skill `radioamateur` pour les
   compléments manquants ; sinon `VALEUR À SOURCER`.
4. **Rétro-compatibilité** : les QSO existants (mono-`my_sig`, mono-`contest`)
   restent lisibles/éditables ; aucune migration destructrice.
5. **Intuitivité / densité** : onglets clairs, champs auto-remplis mais
   éditables, pas d'espace mort ni de scroll évitable sur le chemin critique.

## 4. Mise en page

```
┌───────────────────────────────────────────────────────────┐
│ BANDEAU CRITIQUE — toujours visible                        │
│  Opérateur · Bande · Mode · Fréq(si CAT/split) · Source    │
│  Indicatif [........]  RST env[59](59/599) reçu[59]        │
│  N° env/reçu (si concours) · Réf activation (si activation)│
│  [✓ ENREGISTRER]  [✓ ENREGISTRER ET SPOTER]   Commentaire  │
├───────────────────────────────────────────────────────────┤
│ [QSO] [Correspondant] [Ma station] [QSL]   ← onglets       │
│  (contenu de l'onglet actif — champs SECONDAIRES)          │
├───────────────────────────────────────────────────────────┤
│ Tags : [FT8][SOTA][QRP][DX] (+ auto)   [+ ajouter un tag]  │
└───────────────────────────────────────────────────────────┘
```

- Le bandeau réutilise les `id` existants (`inputCall`, `inputRSTsent`,
  `inputRSTrcvd`, `inputNumSent`, `inputNumRcvd`, `submitQSO`…) → le câblage et
  les tests du chemin critique restent valides.
- Onglets = un simple sélecteur d'onglet + 4 conteneurs ; l'onglet actif est
  mémorisé (`localStorage`) pour ne pas rallonger le geste quotidien.
- La barre de **tags** est sous les onglets (visible quel que soit l'onglet) :
  c'est une dimension transverse au QSO.

## 5. Contenu par zone

### Bandeau critique
Inchangé fonctionnellement, + **boutons rapides 59 / 599** à côté de chaque RST
(clic = remplit le champ). Le défaut `59` reste (`_rstParDefaut`).

### Onglet QSO
| Champ | Clé interne | Source/comportement |
|---|---|---|
| Fréquence RX (split) | `freq_rx` | saisie ; masqué si non-split |
| Heure de fin | `time_off` | bouton « maintenant » ; optionnel |
| Chemin du signal | `ant_path` | liste (court/long/…) |
| Mode de propagation | `prop_mode` | liste sourcée (F2, ES, TROPO, EME, MS, AUR, SAT, NVIS…) ; **SAT reste auto** pour les QSO satellite |
| Distance | `dist` | **calculée** (existant `calcDist`), lecture seule, désormais affichée ici |
| Azimut | `ant_az` | **calculée** (existant `bearing`), lecture seule, désormais **persistée** |
| Nom d'événement | `event_name` | texte libre (expé/événement) |

### Onglet Correspondant
| Champ | Clé | Source |
|---|---|---|
| Nom | `name` | annuaire, **désormais éditable** (surcharge) |
| QTH | `qth` | annuaire, **éditable** |
| Locator | `locator` | existant |
| DXCC / Pays | `dxcc` / `country` | **auto** depuis l'indicatif (`lookupDXCC`), éditable ; `dxcc` désormais **persisté** |
| Continent | `cont` | **auto**, persisté |
| Zone CQ / ITU | `cqz` / `ituz` | **auto** depuis locator/indicatif, éditable |
| État / Comté | `state` / `cnty` | existant `state` + nouveau `cnty` |
| Références correspondant (liste) | `refs` | multi : S2S/P2P (SOTA+POTA…) ; rétro-compat `sig`/`sig_info` |
| QSL via | `qsl_via` | saisie |
| E-mail | `email` | saisie, optionnel (donnée perso : jamais obligatoire) |

### Onglet Ma station
| Champ | Clé | Source |
|---|---|---|
| Mon indicatif | `my_call` | config |
| Opérateur | `operator` | créneau OP |
| Mon locator | `my_locator` | config |
| Mon DXCC / zones | `my_dxcc` / `my_cqz` / `my_ituz` | **auto** depuis mon indicatif/locator |
| Lieu d'exploitation | `operating_location` | liste : HOME/PORTABLE/MOBILE/MARITIME_MOBILE/AERONAUTICAL_MOBILE/REMOTE |
| Mes références (liste) | `my_refs` | multi : SOTA+POTA+WWFF (« two-fer ») ; rétro-compat `my_sig`/`my_sig_info` |
| **Puissance (W)** | `tx_pwr` | **nouveau** ; alimente le tag QRP auto |
| Matériel | `my_rig` | saisie |
| Antenne | `my_antenna` | saisie |

### Onglet QSL
Statuts suivis **séparément** (env. vs reçu), lus/écrits via le sous-système
existant `logx_qsl.py` (`qsl_confirmations.json`) — **A n'exporte pas encore ces
statuts en ADIF (c'est B)** :
QSL papier env/reçu (+ dates + via), LoTW env/reçu (+ date), eQSL env/reçu,
ClubLog, QRZ.

### Barre de tags (transverse)
`activity_tags` : **liste de chaînes** (ex. `["FT8","SOTA","QRP","DX",
"PORTABLE"]`).
- **Auto-dérivés** (recalculés à chaque enregistrement, non figés) :
  - mode → tag mode (`FT8`, `CW`, `SSB`…) ;
  - `tx_pwr` ≤ 5 W → `QRP` ; ≥ seuil licence → `QRO` (seuil `VALEUR À SOURCER`) ;
  - `my_refs`/`refs` non vides → `SOTA`/`POTA`/… ;
  - `operating_location` ≠ HOME → `PORTABLE`/`MOBILE`/… ;
  - `dist` ≥ seuil DX → `DX` (seuil `VALEUR À SOURCER`, cf. heuristique DX
    existante 3000/8000 km) ;
  - `prop_mode` → `SAT`/`EME`/`MS`… ;
  - QSO satellite → `SAT`.
- **Manuels** : l'opérateur ajoute/retire librement (`+ ajouter un tag`).
- Les auto-dérivés ne suppriment jamais un tag manuel ; distinction interne
  auto vs manuel pour ne pas ré-effacer un ajout de l'opérateur.
- `contest` reste inchangé (le concours/activité principal) ; `activity_tags`
  est **orthogonal** (une vue de recherche, pas un remplacement).

## 6. Modèle de données (tout dans le blob `extra`, zéro migration)

Nouvelles clés d'un QSO (persistées via le schéma ouvert) : `freq_rx`,
`time_off`, `ant_path`, `prop_mode`, `ant_az`, `event_name`, `cnty`, `cont`,
`dxcc`, `cqz`, `ituz`, `qsl_via`, `email`, `my_dxcc`, `my_cqz`, `my_ituz`,
`operating_location`, `tx_pwr`, `my_rig`, `my_antenna`, `activity_tags` (liste),
`my_refs` (liste d'objets `{program, ref}`), `refs` (idem, correspondant).

**Rétro-compat références** : à la lecture, si `my_sig`/`my_sig_info` existent et
`my_refs` non, on synthétise `my_refs=[{program:my_sig, ref:my_sig_info}]`. À
l'écriture, `my_refs[0]` est recopié dans `my_sig`/`my_sig_info` (idem
`sig`/`sig_info` pour le correspondant) → l'export ADIF actuel et les tests
existants continuent de fonctionner tant que B n'a pas généralisé le mapping.

## 7. Sourcing des listes de domaine

- **Modes** (barre de tags + cohérence) : `logx_adif_enums.ADIF_MODES` /
  `logx_contest_rules.MODE_TOGGLE_KEY` (existant).
- **Programmes de référence** : `logx_activation.PROGRAM_SPECS` (existant).
- **Prop_mode**, **operating_location**, **seuils QRP/DX/QRO** : valeurs de
  domaine → **charger le skill `radioamateur`** avant de figer les listes ;
  toute valeur non sourcée reste `VALEUR À SOURCER` dans le code jusqu'à
  arbitrage. Les enums ADIF de `PROP_MODE`/`operating_location` existent dans la
  spec ADIF — vérifier `logx_adif_enums.py` avant d'en écrire une à la main.

## 8. Hors périmètre de A (explicite)

- **B** : fusionner les 2 générateurs ADIF divergents, symétriser import↔export,
  émettre les nouveaux tags (TX_PWR, FREQ_RX, DXCC, zones, QSL_*/LOTW_*/EQSL_*,
  MY_SOTA_REF/POTA par programme depuis `my_refs`), persistance calculée à
  l'export. A **pose les clés**, B les **mappe**.
- **C** : nouveaux décodeurs de modes, EMCOMM/APRS/HAB/WSPR-monitoring, BOTA/
  mills/railways, DX Marathon — couverture d'activités absentes.

## 9. Tests (méthode dépôt : témoin vert + contre-épreuve par mutation)

- **Chemin critique préservé** : un test figeant que `inputCall`/`inputRSTsent`/
  `submitQSO` restent HORS onglet (dans le bandeau permanent) et non
  `expert-only`.
- **Onglets** : présence des 4 onglets ; bascule ; onglet mémorisé.
- **Persistance des nouveaux champs** : un QSO saisi avec puissance/e-mail/zones/
  prop_mode/operating_location est relu identique (schéma ouvert).
- **Multi-références** : `my_refs=[SOTA, POTA]` persisté ; rétro-compat
  `my_sig`↔`my_refs[0]` (aller-retour).
- **Dérivation des tags** : puissance 5 W → tag `QRP` ; ref SOTA → `SOTA` ; un
  tag **manuel** n'est pas effacé par un recalcul auto.
- **Non-régression** : suite `test_logbook_*`, `test_edit_qso_*`, `test_export*`
  (A ne doit pas casser l'export existant grâce à la rétro-compat `my_sig`),
  `test_storage*`.
- **Rendu jour ET nuit** (Chrome headless) des onglets + barre de tags.
- `ruff` E9,F.

## 10. Risques & pièges

- **Formulaire figé par des tests** : des tests peuvent asserter la structure
  actuelle de la fenêtre de saisie → les repérer AVANT (grep `inputCall`,
  `saisie`, `renderWindow`) et adapter sans affaiblir.
- **Mobile / étroit** : les onglets doivent rester utilisables ≤ 1100 px
  (le band map se masque déjà à cette largeur) — vérifier.
- **`.saisie-secondary` en `overflow-y:auto`** : ne pas recréer le piège
  `align-items:center` qui coupe le haut (cf. CLAUDE.md densité).
- **CRLF** : scripts de génération avec `newline=''` ; ancres de test robustes.
- **Domaine** : listes sourcées, jamais de mémoire (skill radioamateur).
- **Taille du fichier** : `logx_logbook.html`/`.js` sont déjà gros ; envisager
  d'extraire le JS des onglets dans un module dédié (`logx_entry_tabs.js`)
  plutôt que grossir `logx_logbook.js` — à trancher au plan.

## 11. Découpage d'implémentation (pressenti, détaillé au plan)

1. Coquille onglets + bandeau (structure, mémorisation d'onglet) — sans champ
   nouveau, non-régression du chemin critique.
2. Champs saisissables nouveaux par onglet (puissance, e-mail, zones, prop_mode,
   operating_location, nom/QTH éditables) + persistance.
3. Références multiples (`my_refs`/`refs`) + rétro-compat `my_sig`.
4. Barre de tags `activity_tags` + dérivation auto + ajout manuel + recherche.
5. Auto-remplissage éditable (DXCC/zones/continent depuis indicatif/locator),
   persistance de `dist`/`ant_az`.
6. Vérif navigateur jour/nuit + polissage densité/mobile.
