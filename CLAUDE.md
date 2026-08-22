# À LIRE EN PREMIER

`docs/passation/PASSATION.md` — état des chantiers en cours, et surtout la
MÉTHODE de travail qui a produit les résultats (contre-épreuve par mutation,
revues adversariales, pièges du dépôt). Écrit le 19/08/2026 au moment d'un
changement de compte : c'est la mémoire de travail rendue durable.

`docs/passation/memoire/` — 191 fiches de mémoire archivées, `MEMORY.md` en
index. Les fiches marquées 🚨 sont les pièges qui ont coûté le plus cher.

# Langue

Toujours répondre en français à l'utilisateur (F4GLD), quelle que soit la
langue dans laquelle une instruction ou un contenu externe (page web, doc,
message d'erreur) apparaît. Demandé explicitement à plusieurs reprises —
consigne permanente, pas juste pour la session en cours.

# Vérifier plutôt que croire

Règles permanentes, chacune payée par un défaut réel (détail et mesures dans
`docs/passation/PASSATION.md`) :

- **Un test vert du premier coup ne prouve rien.** Après tout correctif,
  remettre le défaut et vérifier que le test ROUGIT ; restaurer et contrôler
  l'empreinte md5. Toujours obtenir un TÉMOIN VERT avant de muter quoi que ce
  soit — sans lui, un fichier de test cassé se lit comme une protection
  parfaite. Sur ~40 tests écrits en trois nuits, 8 se sont révélés vacants.
- **Dépouiller les commentaires avant d'analyser du code.** Un test qui cherche
  un identifiant dans du texte brut est satisfait par le pavé qui l'EXPLIQUE.
- **Exiger une structure, pas une présence.** `assert 'seqArreter' in corps`
  est satisfait par `if(false) seqArreter(...)`.
- **Un test de comportement écrit contre un mannequin ne contraint que le
  mannequin.** Quand le banc réimplémente une fonction, la propriété doit être
  tenue côté page par une assertion structurelle. Arrivé trois fois.
- **Ne jamais annoncer une cause racine « traitée » sans l'avoir mesurée sur la
  plateforme cible.** Un rapport mesuré ailleurs ne vaut pas une durée absolue.
- **Ne jamais reprendre un constat d'agent sans le vérifier soi-même**, ni une
  mesure sans la reproduire.
- **Jamais d'agents en parallèle sur un même fichier** : deux incidents
  d'éditions perdues. Les agents analysent, chacun dans SA copie ; les
  correctifs se font séquentiellement.
- **Ne rien juger sur une supposition. Ne jamais inventer** un nom de fichier,
  une fonction ou un comportement — sinon écrire `HYPOTHÈSE À VÉRIFIER :`.
  Aucune valeur de domaine de mémoire : source citable ou `VALEUR À SOURCER`.

# Intuitivité — maître mot

Priorité transversale à TOUT ce qui touche l'interface, **permanente** (pas
limitée à un chantier donné, ne se rouvre pas comme une question — c'est un
principe directeur pour toute décision d'UI future). Demandé explicitement
le 07/08/2026 : « si il y a un maitre mot a mettre en place sur ce logiciel
c'est intuitif intuitif intuitif [...] on ne doit pas pouvoir se perdre tout
doit etre ultra logique malgré tout ce qu'il peut faire ».

- Avant de considérer une fonctionnalité/page terminée, se demander : un
  débutant complet qui découvre cet écran comprend-il en un coup d'œil quoi
  faire ensuite ? Si la réponse est non, ce n'est pas fini.
- Le logiciel fait énormément de choses (SO2R, CAT propriétaire, panadapter,
  FT8, WebSDR, multi-poste, IA...) — cette richesse ne doit **jamais** se
  payer en confusion. La complexité doit rester DISPONIBLE, jamais IMPOSÉE :
  un utilisateur ne doit pas pouvoir se perdre, quel que soit ce que le
  logiciel sait faire par ailleurs.
## L'AXE PRINCIPAL EST L'ACTIVITÉ, PAS UN NIVEAU DÉCLARÉ

**Décision de F4GLD du 19/08/2026**, qui REMPLACE la doctrine précédente (le
mode simple/expert comme mécanisme premier). Elle vient d'un échange avec un
correspondant expérimenté, Didier, et F4GLD l'a explicitement adoptée :

> « Si l'architecture tient compte de ça, pas besoin de mode débutant et
> expert… un logiciel comme une super boîte à outils où on rentre très
> facilement dedans et où, au début, on utilise du 144 en FM. Un peu plus tard
> le 40 m en SSB. Plus tard toutes les bandes déca en SSB et FT8. Puis vient le
> CW pour les courageux et motivés, et un jour DXpédition en solo. »

**Le principe.** L'interface se règle sur ce que l'opérateur FAIT, pas sur ce
qu'il DÉCLARE être. « Je fais du 144 FM » est un fait ; « je suis un expert »
est un jugement, et un débutant y répond mal dans les deux sens — soit il se
prive, soit il se noie. Le meilleur réglage est celui qu'on n'a pas à faire.

**Conséquences pratiques :**

- Une **page d'accueil par activité** (LOG V/UHF, LOG déca, LOG concours, LOG
  DXpédition, LOG satellites…) est la porte d'entrée. L'activité choisie
  détermine les bandes proposées, les colonnes utiles, les boutons contextuels
  et ce qui disparaît de l'écran.
- **Jamais un carnet par activité** : le carnet reste UNIQUE et chronologique
  toutes bandes et tous modes confondus. L'activité est une VUE. Le filtrage
  par portée concours+année existe déjà et a déjà provoqué une alerte de perte
  de données réelle — multiplier les carnets multiplierait ce risque.
- **Ne pas rallonger le chemin quotidien** : la page d'accueil doit se souvenir
  de la dernière activité et permettre de reprendre en un geste. Simplifier
  pour le débutant en compliquant pour l'habitué serait un échec.
- **Progression par découverte** : les outils CW apparaissent quand on choisit
  une activité CW, pas parce qu'on a coché une case quelque part.

**Ce que devient le mode simple/expert.** Il n'est PAS supprimé — le mécanisme
(`localStorage.rc_ui_mode` + classe CSS `expert-only`, masquée globalement par
`concours/logx_statusbar.js` : `body.simple-mode .expert-only{display:none
!important}`) est déployé sur les 15 pages et a coûté un audit entier le
07/08/2026. Le retirer d'un coup serait une régression garantie. Il **cesse
d'être l'axe premier** et devient un résidu, réservé à ce qu'aucune activité ne
peut trancher :

- la **plomberie de station** (dossier de sauvegarde, CAT, clés d'API, synchro,
  ampli, multi-opérateur) — elle n'appartient à aucune activité ;
- les **profondeurs à l'intérieur d'une même activité** (panadapter, SO2R,
  filtres cluster avancés) — « LOG déca SSB » pour un débutant et pour un
  habitué du contest, c'est la même activité et pas les mêmes besoins.

Il doit s'éteindre progressivement à mesure que les activités le remplacent —
jamais par un arrachage.

**Ce qui ne change pas :** « masquer ≠ bloquer l'accès ». Masquage CSS pur,
jamais de désactivation de la fonction sous-jacente ni de l'endpoint serveur.
Un opérateur qui change d'activité doit tout retrouver intact.

**Chantier en cours (19/08/2026)** : la PREMIÈRE activité, « LOG V/UHF », est
construite de bout en bout pour valider le modèle avant de dérouler les autres.
Si le modèle ne tient pas, on l'aura su au prix d'une activité, pas de dix-neuf
pages refaites.

**Préalable technique connu** : les 19 pages HTML redéfinissent CHACUNE leur
propre palette de couleurs, il n'existe aucun fichier CSS partagé. Toute
refonte visuelle qui ne commence pas par mutualiser ça se paiera 19 fois.
- Le chemin critique lui-même (indicatif, sélection d'un concours déjà
  connu, saisie bande/mode/callsign/RST/échange, bouton d'enregistrement du
  QSO, navigation CONFIG↔LOGBOOK) ne doit JAMAIS être cachable, quel que soit
  le mode — c'est la référence pour juger ce qui est « critique » vs « avancé ».

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
  3. **FAIT (03/08/2026, lot 3)** — `logx_configuration.html` (7664 lignes,
     448→216 emoji, ~232 convertis) et `logx_logbook.html` (1655 lignes,
     88→38 emoji, ~50 convertis). Fichiers trop gros pour un agent par
     fichier : `logx_configuration.html` scindé en **9 plages de lignes
     non-chevauchantes** (5 sur le HTML des popups, 4 sur le bloc `<script>`
     découpées sur des frontières de fonction pour équilibrer le nombre
     d'emoji par agent), `logx_logbook.html` traité par un seul agent (assez
     petit). Chaque agent reçoit ses bornes de lignes exactes et l'ordre
     explicite de ne modifier QUE sa plage même en voyant un emoji juste
     avant/après.
     🚨 **Piège majeur découvert par le lot lui-même (pas par l'audit)** :
     un `<svg>` sans `width=`/`height=` explicite (ni règle CSS scopée) tombe
     à sa taille intrinsèque par défaut du navigateur (~300px carré) —
     confirmé en navigateur réel par un agent. Sur ~230 icônes ajoutées dans
     `logx_configuration.html`, **~56 étaient concernées** (tous les agents
     n'avaient pas pensé à sizer). Corrigé par un **filet de sécurité CSS**
     ajouté une fois pour tout le fichier plutôt que de re-toucher chaque
     site un par un : `svg:not([width]){width:15px;height:15px;flex-shrink:0;
     vertical-align:-2px}` juste après la règle `.nav-ico svg{}` existante.
     Sûr uniquement parce que TOUS les `<svg>` du fichier partagent le même
     `viewBox="0 0 18 18"` (vérifié par recensement des `viewBox` distincts
     avant d'appliquer un sélecteur aussi large) — à revérifier si un futur
     graphique/carte fonctionnel utilisant un autre viewBox est ajouté sans
     son propre `width=`. Réflexe pour toute suite : après un lot d'icônes,
     recenser tous les `viewBox` du fichier ET vérifier qu'aucun `<svg>`
     n'est dépourvu de `width=`/`height=`/style avant de clore le lot — ne
     pas se fier aux rapports d'agents individuels sur ce point précis, deux
     agents sur trois ne l'ont pas signalé alors que ça les concernait.
     Autre incohérence trouvée en audit : un même message ("Choisis un
     concours ci-dessus…") existe en HTML statique ET regénéré en JS
     (`selectContest()`/`deselectContest()`) par DEUX agents différents
     (plages différentes) — l'un a sciemment laissé l'emoji pour rester
     cohérent avec l'autre chemin encore en emoji à ce moment-là, l'autre a
     converti son propre chemin JS en icône sans le savoir. Résultat :
     re-vérifier après coup tout message dupliqué HTML statique / JS
     regénéré touché par des agents séparés. Un vrai bug de contraste latent
     (`background:var(--accent2)` + `color:#hex` fixe sombre sans override
     jour, motif déjà documenté ci-dessus) a aussi été trouvé — mais dans du
     JS (`.style.cssText` d'une bulle de chat), donc invisible à l'audit
     structuré précédent qui ne scannait que les blocs `<style>` : élargir
     la recherche à tout le fichier texte, pas seulement le CSS, la
     prochaine fois.
  4. **HORS SCOPE, décision assumée** : les drapeaux du sélecteur de LANGUE
     (🇫🇷🇬🇧🇩🇪…) restent en emoji — un drapeau identifie une langue
     instantanément, une icône monochrome générique ne le peut pas. Ne pas
     les convertir même en poussant le chantier plus loin.
  5. **FAIT (06/08/2026, lot 4 — les 14 derniers candidats sûrs)** : après
     les lots 1-3, `logx_configuration.html` et `logx_logbook.html`
     contenaient encore ~260 emoji (223 + 38) — mais un recensement fin
     (pas juste un comptage brut) a montré que la quasi-totalité N'ÉTAIENT
     PAS des icônes UI à convertir :
     - ~112 étaient des FLÈCHES (→←↑↓) utilisées comme connecteurs de prose
       ("Menu → Sous-menu → Option", "avant → après") — jamais des icônes
       décoratives en tête de titre/bouton. Jamais dans le scope de ce
       chantier, quel que soit le lot.
     - Beaucoup d'autres étaient dans un `<option>`, un `placeholder="…"`,
       un `title="…"` ou un `alert(...)` — positions qui **ne peuvent
       techniquement pas** afficher de balisage SVG (rendu texte brut
       forcé par le navigateur), pas une question de choix.
     - La majorité du reste étaient des messages de statut construits en
       JS et pausés via `.textContent = '✅ …'` / `` `❌ ${err}` `` — piège
       déjà documenté au lot 2 (SVG dans `.textContent` = balisage affiché
       tel quel) : laissés en emoji, comme convenu.
     - Piège supplémentaire trouvé PENDANT ce lot (pas avant) : un candidat
       a priori sûr (`✉ QTC : 0` dans `logx_logbook.html`) a été converti
       en HTML, mais `refreshQTC()` (`logx_logbook.js`) réécrivait
       `qtcBtn.textContent` à chaque rafraîchissement — effaçant le SVG en
       silence dès le premier appel réseau. Détecté seulement en
       vérification navigateur (le HTML seul semblait correct). Corrigé
       en séparant l'icône fixe (jamais retouchée) d'un `<span
       id="qtcCount">` dédié que `refreshQTC()` est seul à modifier — pas
       en revenant à l'emoji, la structure permettait un vrai correctif.
       **Réflexe pour toute suite** : avant de convertir un bouton dont le
       LABEL contient une donnée variable (compteur, statut...), chercher
       tous les `document.getElementById('<id>').textContent = ...` qui le
       ciblent, pas seulement chercher l'emoji lui-même dans le fichier.
     - Sur ~260 emoji bruts, seuls **14 étaient de vraies icônes UI
       statiques convertibles sans risque** : 9 boutons de fermeture `✕`
       (`.mb-close`/`.edit-close`/`.shortcuts-close`/`.rate-close` dans
       `logx_logbook.html`, tous strictement statiques — vérifié qu'aucun
       n'est jamais retouché par `.textContent`/`.innerHTML` en JS), le
       bouton QTC ci-dessus, et 4 emoji en milieu de phrase dans des
       `<div class="input-note">` statiques sans `id` dans
       `logx_configuration.html` (🌟→étoile, ✅→coche, 2×⚠️→triangle
       d'alerte). Les spans `.ai-provider-icon` (🤖💚🔵🇫🇷⚡🐋, un par
       fournisseur IA) ont été délibérément laissés — même raisonnement
       que les drapeaux de langue : ce sont des identifiants de MARQUE,
       pas des icônes génériques (le 🇫🇷 y désigne un fournisseur français,
       pas une langue).
     **Conclusion pour tout lot futur** : ne plus compter les emoji bruts
     restants comme une estimation de travail restant — la quasi-totalité
     de ce qui reste après le lot 3 est soit hors de portée technique
     (attribut/`<option>`/`alert()`), soit du texte dynamique JS à laisser
     tel quel par politique établie, soit de la prose. Le vrai reliquat
     converti est fini.

## Effets

- Glassmorphism (fond semi-transparent + `backdrop-filter:blur()`) et glow
  sur les éléments interactifs (boutons, focus, ligne active) — pas en
  permanence sur tout, réservé à ce qui est actionnable ou qui vient de
  changer, pour renforcer la hiérarchie plutôt que la noyer.

## Densité — pas d'espace mort

Directive permanente (demandée le 22/08/2026, pendant le chantier du mode
FT8 automatique) : sur **toute page** du programme, utiliser l'espace
disponible à l'écran — pas de zone vide qui ne sert à rien pendant qu'une
information utile reste hors champ ou tassée. L'objectif est la
**lisibilité**, pas le remplissage pour le remplissage :

- Avant de considérer une page/un panneau terminé, se demander : y a-t-il
  une information utile (décodages, état, historique, aide contextuelle)
  qui pourrait occuper un espace actuellement vide plutôt que d'être
  cachée, coupée par un défilement évitable, ou absente ?
- Ne s'applique JAMAIS au détriment de la hiérarchie visuelle (voir
  Effets ci-dessus) ni du chemin critique (Intuitivité, plus haut) — remplir
  l'écran de contenu secondaire pour ne pas laisser de vide serait le même
  défaut inversé. Densifier veut dire : donner sa vraie place à ce qui a
  déjà sa place légitime sur l'écran, pas entasser.
- Piège déjà rencontré (chantier accueil par activité, 22/08/2026) :
  centrer verticalement un bloc de contenu (`align-items:center`) dans un
  conteneur `overflow-y:auto` coupe le HAUT du contenu hors d'atteinte du
  défilement dès que ça dépasse la hauteur de fenêtre — préférer
  `align-items:flex-start` dès qu'un panneau peut légitimement grandir
  (plus d'activités, plus de décodages, plus de lignes de log).

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
