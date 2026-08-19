---
name: chantier-statusbar-personnalisable-ecole-cw-2026-08-10
description: "Barre de statut personnalisable (survol, popup MAJ, menu AFFICHAGE à cocher) + feedback immédiat École CW — PR #15, demandes F4GLD en observant sa propre barre"
metadata: 
  node_type: memory
  type: project
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-08-10T11:38:12.950Z
---

Demandé le 10/08/2026 en observant sa propre barre de statut (screenshots) : la
dropdown DISPOSITION ne s'ouvrait qu'au clic, un badge de MAJ trop discret, des
indicateurs jugés « pas essentiels » (backup, balise NCDXF, version) sans façon
de les masquer/afficher soi-même. Ma proposition initiale (expert-only figé sur
ces 3 items) a été remplacée par l'idée de l'utilisateur, meilleure : **un menu
à cocher par item plutôt qu'un binaire simple/expert**. PR #15, mergée.
Implémenté via Workflow (2 agents d'implémentation — statusbar / École CW,
fichiers disjoints — + 3 agents de revue adversariale).

## Ce qui a été livré

- `concours/logx_statusbar.js` :
  - DISPOSITION et le nouveau menu **⚙ AFFICHAGE** s'ouvrent au survol (en plus
    du clic, jamais à sa place — clavier/tactile en dépendent).
  - Popup de mise à jour disponible **auto-ouverte** (réutilise tel quel le
    dropdown `#rcsbUpdateDD` déjà existant et fonctionnel, juste auto-affiché
    au lieu d'attendre un clic sur le badge).
  - Menu ⚙ AFFICHAGE à cocher : `STATUSBAR_TOGGLES` (registre unique, source de
    vérité), persistance `localStorage.rc_statusbar_prefs`. Items masquables :
    backup (défaut OFF), météo solaire (défaut ON), balise NCDXF (défaut OFF),
    QSO/h (défaut ON), vérif règlements (défaut ON), version (défaut OFF).
    Concours actif/temps restant restent TOUJOURS visibles (chemin critique,
    jamais dans la liste des cases à cocher).
- `concours/logx_cw.html` : feedback ✅/❌ immédiat + correction affichée à
  chaque Entrée dans l'exercice de série CW, sans casser le rythme (le
  feedback reste visible pendant que la station suivante joue).

## 5 constats de la revue adversariale, tous corrigés avant merge

1. **[Majeur]** AFFICHAGE ne s'ouvrait pas au survol contrairement à
   DISPOSITION juste à côté — deux menus visuellement jumeaux et adjacents,
   comportements différents. Exactement le genre de rupture que le principe
   « intuitivité » (CLAUDE.md) vise à éliminer. Corrigé en factorisant le
   mécanisme de survol dans une fabrique `_wireHoverDropdown(itemId, ddId,
   renderFn)` réutilisée pour les deux menus plutôt que de dupliquer le couple
   open/scheduleClose par item.
2. **[Majeur]** Contraste du bouton principal du popup de MAJ en mode NUIT :
   2,36:1 mesuré (sous le seuil AA 4,5:1) — `background:var(--accent)` +
   `color:#fff` fixe, texte blanc illisible sur le cuivre clair de nuit.
   **Nouvelle occurrence du piège déjà documenté dans CLAUDE.md** (remplissage
   plein + texte fixe sombre/clair sans override par thème), mais ici dans le
   sens inverse (texte clair sur fond qui devient trop clair la nuit, pas trop
   sombre le jour). Corrigé avec une valeur FIXE `#8B4F1F` (le cuivre jour,
   plus profond) au lieu de `var(--accent)` — 6,49:1 dans les deux thèmes.
   Seulement devenu un vrai problème visible PARCE QUE ce chantier a rendu le
   popup auto-ouvert (avant, il fallait cliquer le badge pour même le voir).
3. **[Moyen]** Le popup de MAJ se rouvrait tout seul à CHAQUE navigation de
   page (pas juste une fois) : le garde-fou anti-réouverture était un flag
   JS en mémoire (`let _updAutoOpened`), réinitialisé à chaque chargement de
   page — mon erreur de conception initiale dans la consigne du chantier
   (j'avais anticipé le piège du polling 30 min mais pas celui de la
   navigation entre pages). Corrigé avec `sessionStorage` (clé
   `rc_update_auto_shown`, valeur = version) : survit à une navigation dans
   le même onglet, se vide seul à la fermeture — comportement voulu.
4. **[Mineur]** Cases à cocher du menu AFFICHAGE sans `accent-color` →
   bleu système du navigateur au lieu du cuivre unique de la charte. Corrigé
   (`accent-color:var(--accent2)`, cohérent avec les checkboxes déjà stylées
   ailleurs dans l'appli, ex. `logx_carte.html`).
5. **[Mineur]** `#rcsbRateItem` (composition préférence ET concours actif,
   nouvelle logique de ce chantier) non recalculé sur l'événement `storage`
   (changement de config depuis un AUTRE onglet/poste) — jusqu'à 60s de
   retard avant le prochain tic de `refreshRate()`. Corrigé en ajoutant
   `updateRateItemVisibility()` au listener `storage` existant.

## Réutilisable pour tout futur ajout de dropdown à la barre de statut

- Patron d'ouverture au clic+survol : `_wireHoverDropdown(itemId, ddId,
  renderFn)` dans `logx_statusbar.js` — appeler une fois par nouveau menu,
  ne jamais recopier le couple open/scheduleClose à la main.
- Patron de préférence utilisateur par item (au lieu du binaire simple/
  expert) : `STATUSBAR_TOGGLES` + `applyStatusbarPrefs()` + localStorage —
  reproductible pour tout futur indicateur qui mériterait d'être optionnel
  plutôt que figé visible/masqué.
- Piège de composition à retenir : quand la visibilité d'un item dépend de
  DEUX conditions indépendantes (ici : préférence utilisateur ET état
  concours), centraliser le calcul dans UNE fonction partagée appelée par
  TOUS les points d'entrée qui peuvent faire changer l'une ou l'autre
  condition (poll périodique, changement de préférence, ET événements
  cross-onglet comme `storage`) — sinon un point d'entrée oublié laisse
  l'affichage désynchronisé silencieusement.
