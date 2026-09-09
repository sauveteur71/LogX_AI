# Propositions de fonctionnalités & intuitivité — septembre 2026

Menu de propositions établi le 09/09/2026 à la demande de F4GLD (« sois force de
proposition »). Tout est aligné sur ce que le programme fait **déjà** et sur la
doctrine directrice du projet :

- **L'axe principal est l'ACTIVITÉ, pas un niveau déclaré** (décision du
  19/08/2026 — voir `CLAUDE.md`). L'accueil par activité est la porte d'entrée ;
  l'activité choisie détermine bandes, colonnes, boutons, et ce qui disparaît.
- **Intuitivité — maître mot.** Un débutant complet comprend chaque écran en un
  coup d'œil ; la complexité reste **disponible, jamais imposée** ; on ne doit
  jamais pouvoir se perdre.
- **Carnet UNIQUE et chronologique** : une activité est une VUE, jamais un
  carnet séparé.

> Statut : idéation. Chaque item retenu passe par un brainstorming (intention,
> écrans, contraintes) **avant** toute ligne de code.

---

## A. Dérouler l'axe « activité » — cœur stratégique

Le pilote **LOG V/UHF** valide le modèle. La suite déroule les activités dans
l'ordre de la progression naturelle d'un opérateur :

| # | Activité | Socle déjà présent | Ce qu'elle pré-câble |
|---|----------|--------------------|----------------------|
| A1 | **LOG déca SSB** | moteur de log, callbook, DXCC | bandes HF, colonnes sans locator imposé, zéro jargon concours |
| A2 | **LOG FT8 / numérique** | FT8 natif, Wait&Pounce (4 niveaux), décodeurs | waterfall, séquenceur, masque le non-numérique |
| **A3** | **LOG activation portable (POTA/SOTA/XOTA)** | 415 000+ réfs, DFCF/WWBOTA/GMA/ARLHS, carte de sortie PNG, spots, park-to-park | réf du jour, spots multi-programmes, carte partageable, chasse↔activation |
| A4 | **LOG concours** | 56 concours au barème, moteur générique, Cabrillo/EDI/ADIF | échange/barème du concours choisi, scoreboard |
| A5 | **LOG EME** | cockpit EME, Q65 natif, suivi lunaire | fenêtre commune, Doppler, bilan de liaison |
| A6 | **LOG satellites / DXpédition** | (à préciser) | trackers, passes, split |

**Intuitivité transverse à l'axe** : l'accueil retient la dernière activité et
reprend en un geste ; progression par découverte (les outils CW/EME
apparaissent quand on choisit l'activité, pas via une case à cocher).

**→ Priorité retenue avec F4GLD : A3 (activation portable)** — c'est l'avantage
différenciant le plus sous-exploité côté UX (le socle XOTA complet existe déjà).

---

## B. Corbeille de QSO récupérable — sûreté = intuitivité

**Origine** : le 09/09/2026, purge de 248 QSO test faite par API, irréversible
côté UI (sauvegarde manuelle heureusement prise avant). Le mécanisme de
**tombstone existe déjà** (`mark_qso_deleted`).

**Proposition** : une corbeille montrant les QSO récemment supprimés + bouton
**Restaurer** (fenêtre de N jours) ; **sélection multiple filtrée** (« tous les
incomplets », « tous les indicatifs test ») avec **aperçu + confirmation** avant
purge. Un débutant ne peut plus perdre son log par erreur, et l'opération de
masse faite à la main devient un geste UI sûr.

Risque faible, socle technique présent.

---

## C. Extensions naturelles des sous-systèmes existants

- **C1 — Requêtes en langage naturel sur le log** (copilote IA) : « montre mes
  QSO POTA en CW ce mois », « combien de new one 6 m cette année ». Le copilote
  connaît déjà le log ; pont évident, effet « waouh ».
- **C2 — Débrief post-activation** : symétrique du débrief post-concours
  existant ; résumé + carte de sortie prêts à publier après une sortie.
- **C3 — FT8 copilote N3/N4** : déjà livré mais **OFF, gaté sur un essai on-air
  non fait**. À débloquer sur décision F4GLD (charger `tx-human-consent` avant
  d'y toucher).

---

## D. Intuitivité transverse (maître mot)

- **D1 — Palette de commandes / recherche unique** (Ctrl+K) : indicatif,
  référence, concours, action — un seul point d'entrée.
- **D2 — États vides parlants** : chaque écran vide dit quoi faire ensuite.
- **D3 — Assistant de 1ʳᵉ mise en route par activité** : « je fais du 144 FM »
  → tout se règle, sans toucher au mode expert (résidu, pas l'axe premier).

---

## Recommandation (top 3, valeur × alignement)

1. **A3 — activation portable** — socle déjà là, UX à révéler. *(retenu, en cours)*
2. **B — corbeille de QSO** — sûreté + intuitivité, risque faible.
3. **C1 — requêtes langage naturel** — fort effet, coût modéré.

## Ce qu'on ne fait PAS (garde-fous doctrine)

- Pas de carnet par activité (vue, pas silo).
- Pas de ré-élévation du mode simple/expert comme axe premier.
- Aucune émission sans consentement humain explicite (`tx-human-consent`).
- Masquer ≠ bloquer : tout reste retrouvable en changeant d'activité.
