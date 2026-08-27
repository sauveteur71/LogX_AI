# Refonte de la hiérarchie de la barre de navigation — spec de conception

**Date** : 2026-08-27
**Statut** : APPROCHE **A** ACTÉE (F4GLD, 27/08/2026). Voir §8 pour la décision
et le plan d'exécution. La nav est chemin critique — CONFIG↔LOGBOOK jamais
cachables, intangible.
**Spec sœur** : `2026-08-27-refonte-barre-statut-cockpit-design.md` (barre de
statut). Celle-ci ne traite QUE la barre de navigation principale (`.app-nav`).

## 1. Inventaire réel (11 entrées, `<nav class="app-nav">`)

| Entrée | Page | Nature |
|---|---|---|
| CONFIG | logx_configuration.html | Réglages (plomberie station) |
| LOGBOOK | logx_logbook.html | **Activité — carnet (chemin critique)** |
| CHASSE | logx_chasse.html | Trafic — qui contacter (spots, POTA/SOTA) |
| MODE NUMÉRIQUE | logx_modes_numeriques.html | Trafic — FT8/RTTY/SSTV |
| PROPAG | logx_propagation.html | Trafic — conditions de bande |
| CARTE IA | logx_carte.html | Trafic — tableau de bord temps réel + IA |
| ZONES TRAVAILLÉES | logx_departements.html | Diplômes — suivi REF/DXCC |
| PANADAPTER | (panadapter) | Station — matériel/SDR |
| CALENDRIER | logx_calendrier.html | Diplômes/réf — concours, règlements |
| WEBSDR | logx_websdr.html | Station — écoute SDR distante |
| ÉCOLE CW | logx_cw.html | Apprendre — entraînement morse |

## 2. Problème

Une barre **plate de 11 entrées** met sur le même plan des natures très
différentes (carnet, trafic, diplômes, matériel, apprentissage, réglages).
Conséquences :
- Pas de **hiérarchie** : le débutant ne voit pas ce qui est central (carnet,
  chasse) vs annexe (panadapter, école CW).
- La nav **ne s'adapte pas à l'activité** — elle contredit la doctrine
  « l'axe principal est l'activité » (CLAUDE.md, F4GLD 19/08) : « les outils CW
  apparaissent quand on choisit une activité CW, pas parce qu'on a coché une
  case ». Aujourd'hui ÉCOLE CW, PANADAPTER, MODE NUMÉRIQUE sont toujours là,
  quelle que soit l'activité.

## 3. Contraintes intangibles (CLAUDE.md)

- **Chemin critique JAMAIS cachable** : indicatif/bande/mode/RST/enregistrer +
  **navigation CONFIG↔LOGBOOK**. CONFIG et LOGBOOK restent donc TOUJOURS
  visibles au premier niveau, quelle que soit l'approche.
- **Masquer ≠ bloquer** : masquage CSS pur, endpoints et pages intacts ; un
  outil « rangé » reste accessible en un geste, jamais désactivé.
- **Intuitivité** : un débutant comprend en un coup d'œil quoi faire ensuite ;
  la richesse reste disponible, jamais imposée.
- **Ne pas rallonger le chemin quotidien** : ranger un outil ne doit pas coûter
  un geste de plus à l'habitué qui s'en sert tous les jours.
- **Composant partagé** (10+ pages via `.app-nav`, icônes SVG déjà mutualisées)
  → un seul point de modification ; **vérif navigateur 2 thèmes** obligatoire.

## 4. Trois approches (à trancher par F4GLD)

### Approche A — Cœur + « Outils ▾ » (minimale, faible risque)
Garder un **cœur toujours visible** (CONFIG · LOGBOOK · CHASSE · PROPAG — le
trajet quotidien) ; ranger le reste (MODE NUMÉRIQUE, CARTE IA, ZONES,
PANADAPTER, CALENDRIER, WEBSDR, ÉCOLE CW) dans **un seul menu « Outils ▾ »**.
- ➕ Désencombrement immédiat, risque faible, réversible, ne présuppose pas le
  modèle d'activité.
- ➖ N'ADAPTE pas encore la nav à l'activité (juste un rangement) ; un niveau
  de profondeur en plus pour les outils rangés.

### Approche B — Groupée par nature (sections étiquetées)
Réordonner en groupes visuels : **JOURNAL** (LOGBOOK) · **TRAFIC** (CHASSE,
MODE NUMÉRIQUE, PROPAG, CARTE IA) · **STATION** (PANADAPTER, WEBSDR) ·
**DIPLÔMES** (ZONES, CALENDRIER) · **APPRENDRE** (ÉCOLE CW) · **RÉGLAGES**
(CONFIG).
- ➕ Modèle mental clair, tout reste visible (pas de menu à ouvrir).
- ➖ Plus de complexité visuelle sur une barre déjà pleine ; groupes STATIQUES,
  toujours affichés, donc n'honore pas encore « l'axe est l'activité ».

### Approche C — Nav pilotée par l'activité (idéal doctrinal) ⟵ *nord*
La nav se règle sur l'**activité choisie** (LOG V/UHF, LOG déca, LOG concours,
LOG DXpédition, LOG satellites…) : **cœur persistant** (CONFIG · LOGBOOK ·
CHASSE) + **extras contextuels** (ex. PANADAPTER/MODE NUMÉRIQUE en activité déca
numérique ; ÉCOLE CW en activité CW ; rien de tout ça en LOG V/UHF FM débutant).
- ➕ Honore pleinement la doctrine ; nav minimale pour le débutant, riche pour
  l'expert — sans réglage à faire.
- ➖ Plus gros changement ; **couplé au chantier « accueil par activité »**
  (première activité LOG V/UHF encore en construction, CLAUDE.md 19/08) — le
  bâtir AVANT le modèle d'activité serait prématuré.

## 5. Recommandation (direction design)

**Phasage A → C.** Faire **A maintenant** (désencombrement immédiat, sûr,
réversible) comme marche vers **C**, la vraie cible doctrinale, à mesure que le
modèle d'activité mûrit. **Ne pas construire C en avance** du chantier
« accueil par activité » — sinon on code une adaptation à un modèle qui n'existe
pas encore. B est un intermédiaire possible si tu veux tout garder visible sans
menu, mais il fige des groupes que C rendra dynamiques.

## 6. Décisions qui t'appartiennent

1. **Approche** : A (phasage, reco) / B / C direct / autre.
2. **Cœur toujours visible** : CONFIG · LOGBOOK sont imposés (chemin critique).
   J'ajoute CHASSE et PROPAG au cœur ? Ou seulement CHASSE ?
3. **WEBSDR / ÉCOLE CW** (tu les avais pointés) : rangés dans « Outils ▾ »
   (approche A) — confirmes-tu ? Ou l'un des deux reste au premier niveau ?
4. **Couplage activité** : on relie explicitement la refonte nav au chantier
   « accueil par activité » (C), ou on avance A indépendamment d'abord ?

## 7. Après ton choix

Spec détaillée de l'approche retenue → plan TDD en lots (structure nav testable
en V8 : cœur présent, items rangés accessibles, chemin critique jamais masqué),
chaque lot vérifié navigateur 2 thèmes avec toi. Le mécanisme `expert-only`
existant (masquage CSS `!important`) et les icônes SVG mutualisées sont réutilisés.

## 8. DÉCISION ACTÉE (F4GLD, 27/08/2026) + plan

**Approche A** — cœur + « Outils ▾ ».
- **Cœur (toujours visible, 1er niveau)** : CONFIG · LOGBOOK · CHASSE · PROPAG.
- **Menu « Outils ▾ »** : MODE NUMÉRIQUE · CARTE IA · ZONES TRAVAILLÉES ·
  PANADAPTER · CALENDRIER · WEBSDR · ÉCOLE CW.
- **Indépendant** du chantier « accueil par activité » (on n'attend pas C).
- Rappel intangible : CONFIG et LOGBOOK ne sont JAMAIS dans un menu (chemin
  critique) — ils restent au 1er niveau quoi qu'il arrive.

### Contrainte de mise en œuvre — la nav est DUPLIQUÉE
La `.app-nav` est recopiée à l'identique dans ~10 pages HTML (pas de composant
partagé ; historiquement éditée par script Python — CLAUDE.md, chantier icônes).
Le dropdown « Outils ▾ » a besoin de HTML + CSS + JS (toggle, clic-extérieur,
clavier). Donc : composant JS/CSS mutualisé + une passe scriptée sur les pages.

### Plan d'exécution en lots (TDD ; chaque lot vérif navigateur 2 thèmes)
1. **Composant « Outils ▾ »** (CSS + JS mutualisés) : dropdown accessible
   (clic + clavier + clic-extérieur + `expert-only` respecté), rendu XSS-safe,
   tokens `logx_theme.css`. Testable en V8 (ouverture/fermeture, focus).
2. **Pilote sur UNE page** (LOGBOOK) : cœur = 4 liens directs + « Outils ▾ »
   contenant les 7 autres. Valider le modèle end-to-end (doctrine : piloter
   avant de dérouler) — test de structure (cœur présent, 7 items joignables,
   CONFIG/LOGBOOK hors menu).
3. **Déroulé scripté sur les ~9 autres pages** (substitution exacte du bloc nav,
   comme la passe icônes) — un test vérifie que TOUTES les pages ont la même
   nav (cœur + Outils) et qu'aucune n'a perdu une destination.
4. **Responsive / débordement** : la nav + menu restent lisibles en largeur
   réduite, aucun débordement horizontal de page (`overflow` maîtrisé).

Convergence future vers **C** (nav pilotée par activité) quand le chantier
« accueil par activité » mûrit — A est la marche, pas l'arrivée.
