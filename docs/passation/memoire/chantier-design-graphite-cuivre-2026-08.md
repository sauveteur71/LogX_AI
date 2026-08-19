---
name: chantier-design-graphite-cuivre-2026-08
description: "Nouvelle direction graphique LogX AI (graphite & cuivre) — TERMINÉ : palette+typo sur 15 pages, icônes emoji→SVG mono en 3 lots (nav, titres/boutons, CONFIG+LOGBOOK)"
metadata: 
  node_type: memory
  type: project
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-08-03T14:20:41.772Z
---

Suite à une demande de F4GLD ("pagination sobre luxueuse futuriste et high
tech"), direction verrouillée le 2026-08-03 après un aperçu itératif (Artifact
avec toggles jour/nuit + typographie + icônes, ajusté à chaque retour) :

- **Palette** : accent unique cuivre (remplace le duo cyan `#00D4FF` /
  orange-red `#FF5030`) — nuit `#E8964A`, jour `#8B4F1F`. Fond graphite (nuit)
  / bone-titane (jour). **Le mode jour est le mode PRIORITAIRE** (choix
  explicite de F4GLD, inhabituel pour ce genre de direction — ne pas
  redemander).
- **Typographie** : Fraunces (serif éditorial) sur les titres de section
  UNIQUEMENT, Share Tech Mono + Exo 2 inchangés partout ailleurs.
- **Icônes** : monochrome (SVG `currentColor`) choisi pour remplacer l'emoji
  actuel — décidé mais PAS ENCORE FAIT (chantier séparé, plus gros : des
  centaines d'emoji à recenser dans le code réel, contrairement au mockup qui
  n'en comportait qu'une poignée).
- **Effets** : glassmorphism + glow sur l'interactif, pas partout.

Tout est documenté dans `CLAUDE.md` (racine du dépôt) avec les valeurs
exactes de tokens et la marche à suivre pour toucher une nouvelle page.

**Fait — pilote** (commit `ea2183e`, fusionné `d5ebc8d`) : `logx_configuration.html`
+ `logx_logbook.html` — tokens, ~45 sites hardcodés convertis, Fraunces sur
les titres. Voir [[piege-couleur-data-vs-theme]] pour le piège rencontré.

**Fait — généralisation aux 13 autres pages** (commit `0c61232`, fusionné
`dde8498`, même jour) : bande/calendrier/carte/chasse/cw/departements/
focus/mobile/panel/propagation/scope/wall/websdr. **Fait via 13 agents en
parallèle (Agent tool), un par fichier**, chacun avec les instructions
précises + le piège data-vs-thème — patron qui a bien fonctionné pour un
lot de fichiers indépendants de taille modeste. Chaque agent a produit un
rapport détaillé (sites modifiés/laissés intacts + justification), vérifié
après coup par un audit centralisé plutôt que pris au mot.

**Audit centralisé après les 13 agents — a trouvé 3 classes de dérive que
les instructions individuelles n'avaient pas couvertes** :
1. Seul 1 agent sur 13 (focus.html) avait pensé à aligner `--text`/`--muted`
   du mode jour sur le pilote (encre chaude) — les 12 autres gardaient
   l'ancien bleu-marine froid, qui jurait sur le nouveau fond crème. Corrigé
   par script sur les 12 fichiers restants (une seule occurrence exacte par
   fichier, vérifiée avant sed).
2. Dégradés d'en-tête codés en dur (bleu-marine nuit / bleu-gris jour) —
   même chose, corrigé par script sur les fichiers concernés.
3. **Le plus important** : `background:var(--accent2)` combiné à un
   `color:#hex` FIXE et sombre, SANS override `body.day-mode` qui change ce
   texte — devient illisible en jour puisque l'accent jour est un cuivre
   encre sombre. Recherche structurée (parseur de règles CSS, pas juste un
   grep texte) sur les 15 fichiers → 6 occurrences trouvées, **dont 2 dans
   les pages PILOTES déjà fusionnées** (`.config-sidebar-item.active`,
   `.chat-input-row button` dans logbook) — des bugs de contraste latents
   qui existaient depuis la fusion du pilote, invisibles tant que personne
   n'avait cherché SPÉCIFIQUEMENT ce motif plutôt que les anciens hex
   `#00D4FF`/`#FF5030`. Tous corrigés avec la valeur fixe `#C9822E` déjà
   établie. Leçon : une recherche par ancien-hex ne suffit pas pour ce genre
   de régression de contraste — il faut aussi chercker le motif
   structurel (fond=accent + texte=hex fixe) indépendamment de la valeur.

**Fait — icônes monochromes, 1er lot** (commit `d5d67a6`, fusionné `0c4049d`,
même jour) : recensement réel = **954 occurrences d'emoji sur les 15 pages**
(jusqu'à 460 dans `logx_configuration.html` seul) — bien plus que le mockup
ne suggérait, conversion totale hors de portée en un seul passage. Scindé
par valeur/risque : converti UNIQUEMENT la barre `<nav class="app-nav">`
(identique sur 10 pages, 9-10 liens) en SVG monochromes — remplacement par
SCRIPT (substitution exacte de texte), pas par agent, puisque le contenu
nav est rigoureusement identique partout (contrairement à la généralisation
couleur où chaque fichier différait). Décision assumée : les drapeaux du
sélecteur de LANGUE restent en emoji (un drapeau identifie une langue,
une icône générique ne le peut pas) — ne pas les convertir même en
poussant le chantier plus loin.

**Fait — icônes monochromes, 2e lot** (commit `c627194`, fusionné `4ed1ad0`,
même jour) : titres de section/panneau + boutons/étiquettes AUTONOMES sur
les 13 pages hors CONFIG/LOGBOOK (13 agents en parallèle, un par fichier).
295 emoji restants → 202 après ce lot (le reste = exclusions volontaires
correctes : contenu `.textContent`, inline mi-phrase, options/attributs,
drapeaux). Piège central pour toute conversion emoji→icône en JS :
**vérifier `.innerHTML=` (SVG rendu OK) vs `.textContent=`/`.value=`
(afficherait le balisage en texte brut) avant de convertir** — plusieurs
agents ont correctement détecté et refusé de convertir des cas où le MÊME
libellé est réécrit par les deux chemins selon le contexte (un repli sans
donnée en textContent, un chemin avec donnée en innerHTML) pour éviter un
rendu incohérent selon l'état. Point coloré de statut (🟢🟡🔴⚪) → puce
`<span>` stylée via `var(--green/--yellow/--red/--muted)`, jamais une
icône monochrome plate (perdrait le sens couleur).

🚨 **Piège de test découvert par la suite pytest, pas par relecture** :
`tests/test_page_chasse_split.py` figeait le texte EXACT avec préfixe
emoji de 5 titres de panneau (`'🏞️ STATIONS POTA EN DIRECT'` etc.) pour
détecter une suppression silencieuse lors d'un refactor antérieur — la
conversion en icône a fait échouer ce test alors qu'aucune régression
réelle n'avait eu lieu (le panneau était toujours là, juste avec une
icône SVG au lieu de l'emoji). Corrigé en ne comparant que le TEXTE (sans
le préfixe décoratif). Réflexe à avoir désormais : après toute conversion
emoji→icône, greper `tests/` pour l'emoji touché AVANT de considérer un
lot fini — la suite complète l'a attrapé ici, mais ça aurait pu passer
inaperçu sur un poste qui ne lance pas systématiquement tous les tests.

**Fait — icônes monochromes, 3e lot / dernier** (commit `9889f39`, fusionné
`9a395ea`, même jour) : `logx_configuration.html` (7664 lignes, 448→216
emoji) et `logx_logbook.html` (1655 lignes, 88→38 emoji) — les deux plus
gros fichiers, seuls restants. `logx_configuration.html` trop gros pour un
agent unique : **scindé en 9 plages de lignes non-chevauchantes** (5 sur le
HTML des popups, 4 sur le bloc `<script>` découpées sur des frontières de
fonction pour équilibrer le nombre d'emoji par agent — voir le calcul par
comptage cumulatif aux frontières de `function` avant dispatch). Chaque
agent reçoit ses bornes exactes + consigne stricte de ne toucher QUE sa
plage. `logx_logbook.html` assez petit pour un seul agent sur tout le
fichier.

🚨 **Piège majeur découvert par un agent lui-même (pas par l'audit), à
généraliser à tout futur lot d'icônes** : un `<svg>` sans `width=`/`height=`
explicite (ni règle CSS scopée) tombe à sa taille intrinsèque par défaut du
navigateur (~300px carré) — confirmé en navigateur réel par l'agent traitant
`logx_configuration.html` lignes 1-780. Sur ~230 icônes ajoutées dans ce
fichier, **~56 étaient concernées** (2 des 9 agents seulement avaient pensé
à sizer systématiquement). Corrigé après coup par un **filet de sécurité
CSS** ajouté une fois pour tout le fichier plutôt que de retoucher chaque
site un par un : `svg:not([width]){width:15px;height:15px;flex-shrink:0;
vertical-align:-2px}` juste après la règle `.nav-ico svg{}` existante — sûr
uniquement parce que TOUS les `<svg>` du fichier partagent le même
`viewBox="0 0 18 18"` (vérifié par recensement des `viewBox` distincts
avant d'appliquer un sélecteur aussi large ; `logx_logbook.html` a en plus
un vrai graphique fonctionnel `#bandscope` à un autre viewBox, protégé par
sa propre règle plus spécifique déclarée APRÈS le filet générique). Réflexe
pour toute suite : après un lot d'icônes, recenser tous les `viewBox` du
fichier ET vérifier qu'aucun `<svg>` n'est dépourvu de `width=`/`height=`/
style avant de clore le lot — ne pas se fier aux rapports d'agents
individuels sur ce point précis.

Deux autres constats de l'audit centralisé, tous deux impossibles à
détecter par un agent scopé à une seule plage :
- Un même message ("Choisis un concours ci-dessus…") existe en HTML
  statique (plage d'un agent) ET regénéré en JS par `selectContest()`/
  `deselectContest()` (plage d'un AUTRE agent) — l'agent HTML a sciemment
  laissé l'emoji pour rester cohérent avec le JS encore en emoji à ce
  moment-là, mais l'agent JS a converti son propre chemin en icône sans le
  savoir. Résultat : incohérence (icône après interaction, emoji au
  premier chargement) invisible tant qu'on ne recroise pas les rapports des
  deux agents sur le MÊME texte. Corrigé en alignant le HTML statique sur
  l'icône déjà utilisée côté JS.
- Un vrai bug de contraste latent (motif déjà documenté : `background:
  var(--accent2)` + `color:#hex` fixe sombre, sans override jour) trouvé
  dans la bulle de chat de l'assistant IA — mais posé en JS
  (`div.style.cssText = '...background:var(--accent2);color:#04222b...'`),
  donc invisible à l'audit structuré du lot précédent qui ne scannait que
  les blocs `<style>`. Élargir la recherche à tout le texte du fichier (y
  compris les chaînes JS), pas seulement le CSS, la prochaine fois.

**Chantier icônes terminé** : nav (lot 1) + titres/boutons des 13 pages
(lot 2) + CONFIG/LOGBOOK (lot 3) = tous les emoji structurels convertis.
Restent volontairement en emoji : drapeaux de langue, `.textContent`/
`.value`, attributs (`title`/`alt`/`placeholder`/`<option>`), `alert`/
`confirm`/`prompt`, emoji mi-phrase, points de statut colorés (déjà des
`<span>` teintés). Version poussée juste après : `v0.9-beta18`.

🚨 **Bug signalé par F4GLD juste après (screenshot)** : le bandeau `<header>`
de `logx_configuration.html` restait BLEU (nuit ET jour). Cause : le pilote
initial (tout premier commit du chantier, avant même la généralisation aux
13 pages) avait converti tous les hex de couleur SAUF le dégradé
`header{background:linear-gradient(...)}` — resté sur les anciennes
valeurs bleu-marine (`#0A0B18,#131530,#0A0B18` nuit) et bleu-lavande
(`#DDE0EE,#EAEDF8,#DDE0EE` jour). La leçon "dégradés d'en-tête codés en
dur" de l'audit du 2e passage (généralisation aux 13 pages) avait bien été
appliquée à `logx_logbook.html` et aux 13 autres pages, mais PAS à
`logx_configuration.html` lui-même — probablement parce que ce fichier,
étant le pilote, était présumé déjà à jour et exclu du grep de vérification
d'alors. Corrigé (`ce419f5`→fusionné `873df80`, `v0.9-beta19`) en alignant
sur `var(--bg),var(--bg2),var(--bg)` (nuit) / `var(--bg3),var(--bg2),
var(--bg3)` (jour), identique aux autres fichiers. Réflexe pour toute
future vérification "tous les fichiers sont à jour" : ne jamais présumer
qu'un fichier PILOTE est forcément conforme aux règles découvertes plus
tard sur les fichiers généralisés — le re-vérifier explicitement lui aussi.
