# ✅ FAIT — LIVRÉ DANS MAIN (annoté le 2026-09-05)

> **Ce design est PÉRIMÉ (livré).** Refonte cockpit — Lot A (version discrète) + B1
> (blocs bandeau réseau) mergée — **PR #377** (`9339537`) ; spec mergée via **PR #368**.
> Conservé pour mémoire de conception.

---

# Refonte de la barre de statut « cockpit » — spec de conception

**Date** : 2026-08-27
**Auteur** : F4GLD (diagnostic + proposition) + mise en forme assistée
**Statut** : EN ATTENTE DE REVUE F4GLD (aucune ligne de code avant feu vert)

## 1. Problème (mot pour mot F4GLD, 27/08/2026)

> « L'accumulation de sous-barres et de bandeaux d'information commence à faire
> "bruit de fond" et dilue la visibilité des éléments vraiment critiques (état
> de la station, météo du pylône, version). »

Trois natures d'information sont aujourd'hui **mélangées** dans la barre de
statut (`#rcStatusBar`, `logx_statusbar.js`) et, sur LOGBOOK, dans un **second
bandeau** (connexion / météo / WSJT-X / postes) :

1. **Actions / outils** (Disposition, Affichage, Expert, Guide, Signaler) —
   noyés au milieu des statuts alors que ce sont des commandes.
2. **Redondance de version** (`v1.2-beta1` apparaît en HAUT *et* au milieu de la
   sous-barre).
3. **Télémétrie & états** (Disque, SFI/K, Météo/Rafales pylône, WSJT-X, Postes)
   qui s'étirent horizontalement sans hiérarchie.

## 2. Principe directeur — la règle qui tranche tout

**État *consultable* ≠ *flux*.** Un opérateur lit l'état de sa station *en un
coup d'œil, en permanence*. Le faire défiler (ticker) l'obligerait à *attendre*
que l'info repasse — inacceptable pour de l'état critique.

→ **Deux mécanismes, deux natures d'information, jamais mélangés :**

| Nature | Mécanisme | Support |
|---|---|---|
| **État station** (disque, SFI/K, météo pylône, WSJT-X, postes, backup) | **Blocs compacts FIXES**, glançables, toujours visibles | `logx_statusbar.js` (barre existante, réorganisée) |
| **Flux** (DX spots, expéditions, POTA/SOTA, news) | **Tickers défilants** | `logx_bandeaux.js` (framework EXISTANT, déjà déployé sur l'accueil) |

Décision F4GLD (27/08) : état station = **blocs compacts fixes** (façon status
bar de cockpit / IDE). Pas de défilement pour l'état.

## 3. Cible — barre de statut cockpit, 3 blocs

Une seule barre compacte, 3 blocs séparés visuellement (séparateurs discrets) :

- **Bloc 1 — Station & Réseau** : `🟢 Connecté · Postes 2 · WSJT-X 🟢`
  (état serveur, nb de postes connectés même WiFi, lien WSJT-X port 2237).
- **Bloc 2 — Propagation & Environnement** : `☀️ SFI 131·K0 · 🌡 19° · 💨 28/46 km/h`
  (indices solaires, balise, météo/vent).
- **Bloc 3 — Maintenance & Système** : `💾 Disque OK · 📄 Règlements`
  (dernière sauvegarde disque, dernier check règlements).

### 3.1 L'alerte pylône est de la SÉCURITÉ, pas de la télémétrie

Exigence de conception **de premier ordre** (pas un détail de couleur) : quand
« Rafales – surveille le pylône » s'active, l'alerte doit **s'extraire du bloc
compact et s'imposer** — couleur (`--red`/`--yellow` sémantiques, jamais
l'accent cuivre), clignotement, priorité visuelle — puis **retomber** dans le
bloc au retour au calme. C'est la seule ligne qui protège le matériel et les
personnes. État « calme » discret ; état « alerte » impossible à manquer.

### 3.2 Ce qu'on nettoie

- **Version en double** : retirer `v1.2-beta1` du milieu de la sous-barre. UNE
  seule indication de version, discrète (bas de page ou écran CONFIG).
- **Actions déplacées** : Disposition + Affichage migrent dans un menu
  **« ⚙ Vue »** (Affichage EST déjà un menu déroulant `#rcsbDisplayItem` — on y
  regroupe Disposition). Guide / Signaler / Expert restent des commandes,
  ancrées proprement (pas des badges texte noyés dans les statuts).

## 4. Réutilisation — rien à réinventer (vérifié)

- `logx_statusbar.js` : la barre `#rcStatusBar` et son système AFFICHAGE
  (masquage par item, classe `!important`, profils) — on RÉORGANISE, on ne
  reconstruit pas. Le chrono d'épreuve est déjà masqué hors concours (PR #367).
- `logx_bandeaux.js` + `logx_bandeaux_defs.js` : framework de tickers déjà en
  place (accueil) — reste dédié au FLUX (DX/expéditions), pas à l'état station.
- `logx_theme.css` : tokens partagés (`--bg`, `--accent`, `--muted`, `--green`,
  `--red`, `--yellow`, `--border`, `--font-mono`) — la refonte n'introduit AUCUNE
  couleur codée en dur ; couleurs sémantiques pour succès/alerte.

## 5. Contraintes permanentes (CLAUDE.md)

- **Intuitivité** : un débutant comprend l'état en un coup d'œil ; la richesse
  reste disponible, jamais imposée.
- **Masquer ≠ bloquer** : le système AFFICHAGE (choix utilisateur des items
  visibles) doit être PRÉSERVÉ ; masquage CSS pur, endpoints intacts.
- **Chemin critique jamais cachable** (indicatif, bande/mode/RST, enregistrer,
  nav CONFIG↔LOGBOOK).
- **Densité sans espace mort**, hiérarchie visuelle respectée.
- **Vérif navigateur OBLIGATOIRE des DEUX thèmes** (jour ET nuit) sur instance
  isolée — barre partagée par 20 pages : chaque lot validé avant le suivant.
- **Composant partagé** : toute règle de couleur `background:var(--accent2?)`
  + `color:#hex` sombre sans override jour = piège connu à éviter.

## 5bis. Accessibilité (règles mgifford/aria-live-regions + keyboard)

Sources : skills `aria-live-regions` et `keyboard` (WCAG 2.2 AA) dans
`.claude/skills/`. **Contrainte de conception du Lot 4 (alerte pylône) surtout.**

- **Alerte pylône = `role="alert"`** (assertive, condition importante et
  temporelle) — mais sur un **nœud STABLE exposé AVANT la mise à jour** :
  ```html
  <span id="rcsbStormAlert" role="alert"></span>   <!-- présent en permanence, vide au calme -->
  ```
  On **remplit** son texte quand les rafales dépassent le seuil, on le **vide**
  au calme. **INTERDIT** : créer le nœud + le message dans la même opération, ou
  vider/réinsérer après un délai fixe (50/100 ms) — patterns non fiables (skill).
- **`role="alert"` réservé à l'alerte**, PAS à la télémétrie routinière : SFI/K,
  vent, disque restent **visibles non annoncés** (les annoncer en assertif à
  chaque tick = « Serious »). Ne pas annoncer les ticks d'horloge/polling.
- **Pas d'`alertdialog`** : l'alerte pylône est informationnelle (« surveille le
  pylône »), elle ne requiert pas de réponse modale — un `role="alert"` visible
  suffit ; un alertdialog volerait le focus à tort.
- **Visible d'abord** (l'alerte l'est déjà) ; **ne pas dupliquer** un message
  visible ET une région cachée (double annonce).
- **Clignotement** : respecter **`prefers-reduced-motion`** — repli sur une
  bordure/couleur statique forte (pas de clignotement) quand l'utilisateur l'a
  demandé.
- **Contraste** : la couleur d'alerte (`--red`/`--yellow` sémantiques) doit
  tenir **≥ 3:1** (Non-text Contrast, 1.4.11) sur les 2 thèmes.
- **Menus « ⚙ Vue »** (lot 2) : mêmes règles disclosure que la nav — bouton
  natif + `aria-expanded`, `Échap` ferme + focus rendu, `hidden` (pas
  `aria-hidden`), focus visible sur les 2 thèmes.
- **WCAG** visés : 4.1.3 (status messages — Critique si l'alerte n'est pas
  annoncée), 4.1.2 (name/role/value), 2.3.3 (motion, AAA — via reduced-motion),
  1.4.11 (non-text contrast).
- **Tests V8 (Lot 4)** : nœud `role="alert"` présent dès le boot (stable) ;
  se remplit quand `storm/rafales` actif, se vide au calme ; la télémétrie
  routinière n'a PAS de `role="alert"`.

## 6. Découpage pressenti en lots (pour le futur plan TDD)

1. **Dédup version + item version discret** (petit, isolé, faible risque).
2. **Regrouper Disposition dans le menu ⚙ Vue** (Affichage déjà un menu).
3. **Regroupement visuel en 3 blocs** de la barre de statut (séparateurs,
   ordre, densité) — sans changer les sources de données.
4. **Escalade de l'alerte sécurité pylône** (état calme/alerte, clignotement,
   extraction) — le lot le plus sensible, tests comportementaux V8.
5. **Absorption du 2e bandeau LOGBOOK** (connexion/météo/WSJT/postes) dans la
   barre unifiée — supprime la ligne supplémentaire.

Chaque lot : TDD + contre-épreuve par mutation + vérif navigateur 2 thèmes.

## 7. Décisions actées (F4GLD, 27/08/2026)

- État station = **blocs compacts fixes** (pas de ticker pour l'état).
- Barre de NAVIGATION : F4GLD veut une **refonte de hiérarchie complète** →
  traitée dans une **spec SÉPARÉE** (voir §8), pas dans ce chantier.

## 8. Hors scope (spec séparée à venir)

**Refonte de la hiérarchie de la barre de navigation principale** (11 entrées,
réorganisation par activité/contexte, sort éventuel de WEBSDR/ÉCOLE CW vers un
menu Outils). Plus gros, mérite sa propre exploration/brainstorm et sa spec.
NE PAS l'entamer dans ce chantier — risque de cacher des destinations d'activité
utiles (doctrine « l'axe est l'activité »).

## 9. À valider en navigateur avec F4GLD

- Séparateurs entre blocs (barre verticale discrète vs espacement seul).
- Emplacement final de l'indication de version discrète.
- Seuils exacts de l'alerte pylône (déjà côté serveur météo) et intensité du
  clignotement (respecter `prefers-reduced-motion`).
- Comportement responsive : la barre 3 blocs doit rester lisible en largeur
  réduite (scroll interne du bloc, jamais de débordement horizontal de page).
