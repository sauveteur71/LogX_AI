# Directives de design — LogX AI

Direction graphique verrouillée le 2026-08-03 (échange avec F4GLD), appliquée
à TOUTES les pages HTML de `concours/` (pilote sur `logx_configuration.html`/
`logx_logbook.html`, généralisée aux 13 autres le même jour). Reste à faire :
la conversion emoji → icônes monochromes (chantier distinct, plus gros).

## Ce qu'on ne fait PAS

- Pas de fond blanc/dégradé violet/police Inter — LogX AI a déjà une identité
  distincte (Share Tech Mono + Exo 2, HUD sombre) et ne part pas du problème
  générique IA habituel. Le travail consiste à RAFFINER cette identité, pas à
  la remplacer.

## Palette : graphite & cuivre

Un seul accent (cuivre), plus de duo cyan/orange-red. Deux luminosités par
variable pour rester lisible dans les deux thèmes :

```css
:root {                    /* NUIT */
  --bg:#17181A; --bg2:#1D1F22; --bg3:#25272B; --border:#34363A;
  --accent:#E8964A; --accent2:#E8964A; --accent-rgb:232,150,74;
}
body.day-mode {             /* JOUR — thème prioritaire */
  --bg:#EDEAE0; --bg2:#F8F6EF; --bg3:#E3DED0; --border:#D6D0BE;
  --accent:#8B4F1F; --accent2:#8B4F1F; --accent-rgb:139,79,31;
}
```

- `--accent`/`--accent2` pointent sur LA MÊME valeur (accent unique). Les deux
  variables sont conservées séparément dans le code pour ne pas casser les
  usages existants, mais ne doivent jamais être réglées sur des teintes
  différentes.
- `--accent-rgb` sert aux `rgba(var(--accent-rgb),X)` (fonds/glows translucides).
- `--green`/`--red`/`--yellow`/`--purple` restent des couleurs SÉMANTIQUES
  (succès, erreur, CW, digi…) — non concernées par le passage au cuivre.
- **Cas particulier — remplissage plein + texte sombre dessus** (ex.
  `.toggle-btn.on`) : le cuivre "encre" du jour (#8B4F1F) est trop sombre pour
  porter du texte noir dessus. Utiliser une valeur FIXE et lumineuse
  (`#C9822E`), indépendante du thème — même raisonnement que l'ancien code
  qui fixait déjà `#FF5030` pour cette même raison. **Piège trouvé après coup
  (généralisation du 03/08/2026)** : ce cas ne se limite pas aux hex codés en
  dur — une règle `background:var(--accent2)` (ou `--accent`) combinée à un
  `color:` hex FIXE et sombre, SANS override `body.day-mode` qui change ce
  texte, casse en mode jour (texte sombre sur fond cuivre-encre sombre). 6
  occurrences de ce genre trouvées et corrigées APRÈS la première passe de
  généralisation (`.config-sidebar-item.active`, `.shortcut-offer-yes`,
  `.net-upd-gateway`, `.chat-input-row button`, `.act-yes`, `.sdr-open`) —
  dont 2 dans les pages PILOTES elles-mêmes, invisibles tant qu'aucun grep
  systématique n'avait été fait. Avant de considérer une page terminée,
  chercher TOUTE règle `background:\s*var\(--accent2?\)` combinée à un
  `color:#hex` dans le même bloc — pas seulement les anciens hex `#00D4FF`/
  `#FF5030`. (Deux cas similaires, `.op-btn.active`/`.bm-btn.active` dans
  `logx_logbook.html`, sont en réalité SAINS : ils ont un override
  `body.day-mode .xxx.active{color:#fff}` qui flip le texte pour le jour —
  vérifier l'absence d'un tel override avant de corriger.)
- **Piège vérifié en le faisant** : certains hex identiques à l'ancien accent
  (`#00D4FF`/`#FF5030`) sont en réalité des DONNÉES de catégorisation sans
  rapport avec le thème — code couleur par GROUPE de concours (`groupColors`
  dans `logx_configuration.html`), et code couleur par OPÉRATEUR (`.op-1`…
  `.op-5` dans `logx_logbook.html`) ou par BANDE (légende de carte). Ne
  jamais les modifier en même temps que l'accent — vérifier le contexte de
  CHAQUE occurrence avant de toucher un hex, un grep seul ne suffit pas.

## Typographie

- **Conserver** Share Tech Mono (données/mono) et Exo 2 (corps de texte) sur
  toutes les pages — déjà cohérents, aucun risque, aucune migration requise.
- **Ajouter** Fraunces (`family=Fraunces:opsz,wght@9..144,600;9..144,900`)
  UNIQUEMENT sur les titres de section/popup (`.section-title`,
  `.cat-modal-title`, `.panel-title`, `.edit-title` et équivalents) via
  `--font-display:'Fraunces',serif;`. Ne pas l'étendre au corps de texte ni
  aux étiquettes — le mélange "serif éditorial pour les titres + mono
  technique pour les données" est le rendu recherché, pas une generalisation
  à tout le texte.
- Titres en Fraunces : `font-weight:900`, `letter-spacing` réduit à ~0.2-0.3px
  (un tracking large comme sur le mono ne convient pas à une serif).

## Icônes

- Direction retenue : **monochrome** (tracés SVG `stroke="currentColor"`,
  pas de police d'icônes tierce) plutôt que l'emoji actuel.
- **Recensement fait le 03/08/2026** : ~954 occurrences d'emoji sur les 15
  pages (jusqu'à 460 dans `logx_configuration.html` seul) — bien plus que le
  mockup ne le suggérait. Conversion totale hors de portée raisonnable en un
  seul passage ; le chantier est scindé par ordre de valeur/risque :
  1. **FAIT** — barre de navigation principale (`<nav class="app-nav">`,
     identique sur les 10 pages qui la partagent) : les 9-10 liens
     (CONFIG/LOGBOOK/CARTE IA/PROPAG/CHASSE/Cartes/CALENDRIER/WEBSDR/FOCUS,
     + ÉCOLE CW sur `logx_cw.html`) sont passés à des SVG monochromes
     (`<span class="nav-ico"><svg>…</svg></span>`), taille fixée par
     `.app-nav a svg,.nav-ico svg{width:15px;height:15px;flex-shrink:0}`
     ajouté à chaque fichier. Le `display:flex;gap:7px` déjà présent sur
     `.app-nav a` aligne icône+texte sans CSS supplémentaire. Remplacement
     par script Python (substitution exacte `>{emoji} LABEL<` → icône+label),
     PAS par agent — le nav est identique partout, un seul passage suffit.
  2. **FAIT (03/08/2026, lot 2)** — titres de section/panneau et boutons/
     étiquettes AUTONOMES sur les 13 pages hors CONFIG/LOGBOOK (13 agents en
     parallèle, un par fichier, chacun avec le même corpus d'instructions +
     icônes réutilisables). Piège central à respecter pour toute suite :
     **avant de convertir un emoji généré en JS, vérifier s'il est assigné
     via `.innerHTML =` (SVG rendu, OK) ou `.textContent =`/`.value =`
     (le SVG s'afficherait en texte brut, un vrai bug visuel) — en cas de
     doute ou si le MÊME libellé est réécrit par les deux chemins selon le
     contexte (ex. un repli sans donnée en `textContent` et un chemin avec
     donnée en `innerHTML`), laisser l'emoji partout plutôt que de créer un
     rendu incohérent selon l'état.** Un point coloré de statut (🟢🟡🔴⚪,
     état en ligne/dégradé/hors-ligne) devient un `<span>` rond stylé via
     `var(--green)`/`var(--yellow)`/`var(--red)`/`var(--muted)`, PAS une
     icône monochrome plate (perte du sens couleur). **Piège de test trouvé
     après coup** : `tests/test_page_chasse_split.py` figeait le TITRE EXACT
     avec préfixe emoji de 5 panneaux (`'🏞️ STATIONS POTA EN DIRECT'` etc.)
     pour vérifier qu'ils n'avaient pas été supprimés en silence — la
     conversion en icône a fait échouer ce test bien qu'aucune régression
     réelle n'ait eu lieu. Corrigé en ne testant que le TEXTE (sans le
     préfixe décoratif, appelé à changer). Reflex à avoir : après toute
     conversion emoji→icône, greper les `tests/` pour l'emoji touché avant
     de considérer le lot fini.
  3. **PAS FAIT** — icônes de bouton/badge dans `logx_configuration.html` et
     `logx_logbook.html` (les deux plus gros fichiers, ~371 et ~90+ emoji
     restants estimés) + tout le contenu généré en JS qui n'a pas déjà été
     traité au fil du lot 2 (badges, tooltips, options de `<select>`) —
     chantiers séparés, à faire à la demande.
  4. **HORS SCOPE, décision assumée** : les drapeaux du sélecteur de LANGUE
     (🇫🇷🇬🇧🇩🇪…) restent en emoji — un drapeau identifie une langue
     instantanément, une icône monochrome générique ne le peut pas. Ne pas
     les convertir même en poussant le chantier plus loin.

## Effets

- Glassmorphism (fond semi-transparent + `backdrop-filter:blur()`) et glow
  sur les éléments interactifs (boutons, focus, ligne active) — pas en
  permanence sur tout, réservé à ce qui est actionnable ou qui vient de
  changer, pour renforcer la hiérarchie plutôt que la noyer.

## Avant de toucher une nouvelle page

1. Lire son bloc `:root`/`body.day-mode` existant — chaque page HTML de
   `concours/` duplique sa propre copie des tokens (pas de fichier CSS
   partagé).
2. Grep les hex `#00D4FF`/`#FF5030` (et `rgba(0,212,255,`/`rgba(255,80,48,`)
   AVANT de les toucher, et vérifier le contexte de chaque groupe de
   résultats — distinguer thème UI vs donnée de catégorisation (voir piège
   ci-dessus).
3. Vérifier en navigateur les DEUX thèmes (jour ET nuit) sur une instance
   isolée, pas seulement celui par défaut.
