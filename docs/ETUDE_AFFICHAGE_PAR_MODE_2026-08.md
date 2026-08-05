# Étude : quoi afficher par défaut, dans quel mode d'utilisation

Demande F4GLD (05/08/2026) : étudier logiquement, pour chacun des 4 modes
d'utilisation (SIMPLE, RADIOCLUB, EXPÉDITION, CONCOURS), quelles fonctions
sont réellement utiles à AFFICHER PAR DÉFAUT — par opposition à
« théoriquement inutile, mais je dois pouvoir y accéder en cas
d'exception ». Deux exemples donnés en modèle : CHASSE en mode expédition
(je n'y chasse pas, je m'y fais chasser) et le décodeur CW quand CW n'est
pas dans mes modes activés (exceptionnellement utile, pas par défaut).

## Principe — à ne jamais violer

**Masquer par défaut ≠ bloquer l'accès.** Aucune fonctionnalité ne doit
devenir injoignable pour une exception légitime. La distinction porte sur
ce qui prend de la place à l'écran EN PERMANENCE contre ce qui reste à
un clic — jamais sur ce qui est *possible*. C'est déjà la logique du
bouton **?** (aide en usage/expert) : un principe existant, pas une
invention pour cette étude.

## Les 4 modes, rappel (source : `logx_mode.py`, déjà écrit pour le
copilote IA/coach — cette étude l'étend à l'AFFICHAGE, qui ne le suivait
pas encore partout)

| Mode | Ce qui compte | Ce qu'il ignore |
|---|---|---|
| **SIMPLE** | pays/carrés jamais travaillés (diplômes à vie), propagation, confirmation QSL | règlement/score/multiplicateurs, horaire d'épreuve, soumission de log |
| **CONCOURS** | règlement, barème, multiplicateurs manquants, rythme QSO/h, fenêtres horaires | diplômes à vie |
| **EXPÉDITION / PORTABLE** | pile-up, régions pas encore servies, autonomie (batterie/météo/antenne), coordination multi-poste | le score d'un concours (sauf épreuve en cours) |
| **RADIOCLUB** | roulement opérateurs/postes, cohérence du log partagé, pédagogie | — |

## État des lieux — ce qui est DÉJÀ conditionnel aujourd'hui

Bonne surprise en creusant le code : une bonne partie de ce que cette
étude demande existe déjà, construite au fil des chantiers précédents.
Point de départ pour ne pas refaire ce qui marche :

- **Score/band-recap/hour-chart/filtres 144-432** : déjà masqués en
  SIMPLE **et** EXPÉDITION (`bandeauxRythmeMasques()`,
  `logx_logbook.js:201-207`) — pile la logique demandée : le rythme
  QSO/h d'un concours n'a pas de sens sans concours actif.
- **Recherche/horaire concours** : déjà masqués en SIMPLE.
- **Export Cabrillo/EDI/vérifier/archiver/scoreboard** : déjà masqués
  tant qu'aucun concours n'est réellement sélectionné (`contestActif()`),
  quel que soit le mode déclaré — cohérent.
- **QTC WAE** : déjà masqué hors concours WAEDC — granularité PLUS fine
  que le mode (dépend du règlement précis), très bien comme ça.
- **Barre d'activation POTA/SOTA + auto-spot** : déjà masquée tant
  qu'aucun programme d'activation n'est configuré.
- **Multi-opérateur (sélecteur OP, stats, chat)** : déjà masqué en
  SIMPLE, et en RADIOCLUB strictement lié au nombre d'opérateurs déclarés.
- **`.expert-only`** : bascule DÉBUTANT/EXPERT séparée du mode d'usage
  (`rc_ui_mode`), qui masque déjà macros CW / Wait&Pounce / enregistreur
  QSO / keyer vocal en mode débutant — une deuxième dimension de tri,
  orthogonale à SIMPLE/CONCOURS/EXPÉDITION/RADIOCLUB, à garder telle
  quelle (ne pas la confondre avec le sujet de cette étude).
- **Décodeurs CW/RTTY/SSTV, macros CW, keyer vocal** : déjà conditionnés
  sur le MODE RADIO courant (`updateKeyerPanels()`), pas sur le mode
  d'usage — exactement l'exemple donné en modèle : le décodeur CW
  n'apparaît QUE quand la bande/mode de saisie est réglée sur CW.

## Les vrais écarts trouvés

### 1. CHASSE (POTA/SOTA/WWFF/WCA/DXpeditions) — aucune priorité par mode

**Constat** : le lien CHASSE dans la barre de nav et les 5 panneaux de la
page ont exactement le même poids visuel dans les 4 modes. Aucun
conditionnel `usage_mode` nulle part dans `logx_chasse.html`.

**Analyse par mode** (reprend l'exemple donné) :
- **SIMPLE** : très pertinent — la chasse DX/POTA/SOTA occasionnelle EST
  l'usage simple par excellence. Rien à changer.
- **CONCOURS** : pertinent différemment — les DXpeditions actives sont
  souvent des multiplicateurs recherchés pendant une épreuve. Rien à
  changer.
- **EXPÉDITION** : c'est l'exemple donné — en activant SA PROPRE
  référence (POTA/SOTA/WWFF/château), on ne chasse pas simultanément
  celles des autres. Utile pour le park-to-park occasionnellement, mais
  jamais un usage central de la session. **Candidat à dé-priorisation.**
- **RADIOCLUB** : dépend du poste — un radioclub peut très bien organiser
  une sortie chasse collective. Neutre, pas de raison de masquer.

**Recommandation** : ne PAS masquer CHASSE en expédition (contredirait le
principe « jamais bloquer l'accès », et le park-to-park reste réel) —
mais lui retirer sa place de premier plan. Option la plus simple et la
moins intrusive : le lien de nav reste identique partout (cohérence de la
barre, déjà un principe établi sur ce projet), et c'est le contenu de la
page CHASSE elle-même qui pourrait afficher un bandeau discret en mode
expédition du type « vous activez actuellement [référence] — la chasse
aux autres stations est secondaire pendant une activation », sans rien
cacher.

**✅ IMPLÉMENTÉ (05/08/2026, `72ef73d`)** — bandeau discret retenu (option
proposée ci-dessus), sans toucher au lien de nav. `verifierBandeauExpedition()`
dans `logx_chasse.html` : affiché uniquement si `usage_mode==='expedition'`
ET une activation est configurée (`activation_program`+`my_activation_ref`),
avec le texte exact proposé plus haut. Se met aussi à jour si CONFIG est
modifiée dans un autre onglet (event `storage`).

### 2. Décodeur CW/RTTY/SSTV — déjà bien fait, un point à vérifier

**Constat** : déjà conditionné sur le mode RADIO courant, PAS sur le mode
d'usage — exactement ce qui était demandé. Le seul point à vérifier :
est-ce que les boutons de sélection de MODE (dans la saisie) sont
eux-mêmes restreints aux modes activés en CONFIG, ou tous toujours
proposés ? Si un opérateur qui n'a QUE SSB/FT8 d'activés ne peut de toute
façon pas basculer sa saisie sur CW, le décodeur reste en pratique
inatteignable pour le cas « exceptionnellement, je veux décoder du CW »
que vous citiez — il faudrait alors un accès indépendant du mode de
saisie (ex. depuis le menu DÉBUT/FIN, ou un raccourci dédié), plutôt que
de dépendre d'un changement de mode de saisie.

**✅ CONFIRMÉ ET CORRIGÉ (05/08/2026, `72ef73d`)** — vérification faite :
`renderModeButtons()` ne propose bien QUE les modes cochés dans CONFIG >
MODES, donc le décodeur CW était réellement injoignable sans CW activé.
Fix : bouton dédié `#cwForceBtn` dans la barre d'outils du band map
(`toggleCwPanelForce()`, `logx_logbook.js`), qui force l'ouverture du
panneau `#cwPanel` indépendamment du mode de saisie courant, sans toucher
aux macros CW ni au keyer vocal (qui restent liés au vrai mode radio).

### 3. CONFIG — hub toujours identique quel que soit le mode

**Constat** : les 15 cartes du hub CONFIG (identité, opérateurs, concours,
radio, ampli, rotor, réseau, sauvegarde, propagation, alertes, QSL,
scoreboard, expédition, IA) sont TOUTES rendues sans condition — seule la
couleur du badge de statut change. Un carnettiste SIMPLE voit donc les
mêmes 15 cartes qu'un concourrant, y compris « SCOREBOARD & SOUMISSION »
ou « SÉLECTION CONCOURS », qui ne servent à rien pour lui.

**Analyse** : contrairement aux panneaux du LOGBOOK (transitoires, gênent
la place pendant le trafic), CONFIG n'est visité qu'AVANT la session — le
coût d'une carte "en trop" y est bien plus faible (pas de concurrence
d'espace avec la saisie). Masquer des cartes entières risquerait aussi de
surprendre un opérateur qui change de mode en cours de route et ne
retrouve plus un réglage déjà fait. **Recommandation : ne pas masquer de
cartes CONFIG — le sujet ne s'y pose pas dans les mêmes termes que pour
le LOGBOOK.** Mentionné ici pour être exhaustif, pas comme un gap à
corriger.

### 4. Écran mural, multi-poste — déjà bien géré

Rien trouvé à corriger : déjà strictement lié au nombre d'opérateurs
déclarés + mode RADIOCLUB pour la carte CONFIG dédiée (section « POSTES
RADIO »).

## Tableau récapitulatif

Légende : ✅ affiché par défaut · 🔸 accessible mais secondaire (pas mis en
avant) · ➖ déjà masqué par défaut (mécanisme existant) · — non concerné.

| Fonction | SIMPLE | CONCOURS | EXPÉDITION | RADIOCLUB | État actuel |
|---|---|---|---|---|---|
| Band map / spots cluster | ✅ | ✅ | ✅ | ✅ | conforme |
| CHASSE (POTA/SOTA/WWFF/DXped.) | ✅ | ✅ | 🔸 *(bandeau)* | ✅ | **§1 corrigé** |
| Décodeur CW/RTTY/SSTV | dépend du mode radio, pas du mode d'usage — accès forcé possible via `#cwForceBtn` | | | | **§2 corrigé** |
| Macros CW / Keyer vocal | dépend du mode radio + bascule débutant/expert | | | | conforme |
| Wait & Pounce (FT8/FT4) | dépend de WSJT-X connecté | | | | conforme |
| QTC WAE | dépend du règlement (WAEDC) | | | | conforme |
| Score/band-recap/hour-chart | ➖ | ✅ | ➖ | ✅ | conforme |
| Export Cabrillo/EDI/scoreboard | ➖ *(sans concours)* | ✅ | dépend | ✅ | conforme |
| Barre d'activation + self-spot | ➖ *(sans réf.)* | dépend | ✅ | dépend | conforme |
| Multi-op (OP, stats, chat) | ➖ | dépend du nb. d'opérateurs | dépend | ✅ *(si >1)* | conforme |
| CONFIG (15 cartes du hub) | ✅ | ✅ | ✅ | ✅ | volontairement non filtré, §3 |
| PANADAPTER, WEBSDR, FOCUS, CALENDRIER, CARTE IA, PROPAG | ✅ | ✅ | ✅ | ✅ | pages annexes, jamais gênantes en continu — pas de raison de filtrer |
| École CW | ✅ | ✅ | ✅ | ✅ | entraînement, hors session — pas concerné |

## Statut

Les 2 écarts trouvés (§1 et §2) sont implémentés et fusionnés sur `main`
le 05/08/2026 (commit `72ef73d`, suite à la réponse F4GLD « oui les
deux »). Détails d'implémentation et pièges rencontrés (CSS `display`
dupliqué, test à regex exacte cassé par un changement légitime) :
mémoire `chantier-cw-hors-mode-bandeau-expedition-2026-08`. Les points §3
(CONFIG) et §4 (écran mural/multi-poste) restent volontairement non
modifiés, comme recommandé plus haut.
