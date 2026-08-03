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
  pas de police d'icônes tierce) plutôt que l'emoji actuel — à appliquer lors
  de la généralisation aux autres pages. Pas encore fait sur les pages
  pilotes (chantier distinct, plus gros : des centaines d'emoji à recenser).

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
