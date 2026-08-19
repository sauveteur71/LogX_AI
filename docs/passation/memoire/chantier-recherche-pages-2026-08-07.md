---
name: chantier-recherche-pages-2026-08-07
description: "Module de recherche plein-texte dans les pages (logx_search.py/js) + fix d'un faux positif de l'assistant CONFIG trouvé en le construisant"
metadata: 
  node_type: memory
  type: project
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-08-07T05:48:51.308Z
---

Demande F4GLD (07/08/2026) : « je cherche sstv, je ne sais pas où c'est
dans le logiciel » — voulait une zone de recherche. Livré et fusionné sur
main (`3f36a3a`) :

- `concours/logx_search.py` : endpoint `GET /search?q=...`, indexe le texte
  visible (titres de section + corps) de 12 pages de contenu à CHAQUE
  requête (pas de cache — coût négligeable, évite toute invalidation).
  Découpage en sections par regex sur les classes de titre connues
  (`section-title`, `panel-title`, `cat-modal-title`...), extraction du
  texte par retrait de `<script>`/`<style>`/tags, PAS un vrai parseur DOM
  (aucune dépendance HTML tierce dans ce projet).
- `concours/logx_search.js` : widget partagé (icône loupe injectée dans
  `.app-nav`, un seul fichier inclus sur les 11 pages qui partagent la
  nav — même motif que `logx_statusbar.js`). Clic sur un résultat -> navigue
  vers `page.html?rcq=<terme>` ; CE MÊME script, sur la page cible, cherche
  le premier passage correspondant et le fait défiler/flasher.

**Piège trouvé en vérifiant en navigateur** : le premier essai (un seul
essai à `DOMContentLoaded`) ratait un résultat pourtant bien réel — le
panneau CALLBOT de `logx_logbook.html` n'est peuplé qu'APRÈS
`DOMContentLoaded` (contenu injecté par un script plus loin dans la page).
Corrigé par des réessais espacés (~2,4 s au total) plutôt qu'un essai
unique — pattern à réutiliser pour tout futur "trouve et surligne" sur
cette appli, beaucoup de panneaux sont peuplés en différé.

**Piège outil (pas produit)** : dans ce même environnement de vérification,
`computer.left_click`/clics par coordonnée ou par `ref` sur le bouton de
recherche atterrissaient systématiquement sur `<html>` (élément vide) au
lieu du bouton réel — vérifié en armant un listener de clic en phase de
capture. Contourné en pilotant l'interaction via `javascript_tool`
(`.click()`/`dispatchEvent`) pour la vérification fonctionnelle, un vrai
clic utilisateur n'est pas concerné par ce problème d'outil.

**Bug produit trouvé PENDANT la vérification, hors scope initial mais
corrigé dans la foulée** (capture d'écran F4GLD, « pourquoi l'assistant
répond à côté de la plaque ») : l'assistant CONFIGURATION
(`_searchLocalHelp` dans `logx_configuration.html`) matchait par
SOUS-CHAÎNE (`hay.includes(w)`) plutôt que par mot entier — "trouve"
matchait à l'intérieur de "retrouver" dans l'aide du champ indicatif,
faisant remonter cette entrée comme "réponse" à une question sur SSTV alors
qu'AUCUNE entrée de CONFIG_HELP n'en parle. Corrigé par un match `\b...\b`
(`_wholeWordIncludes`). Bon rappel que cet assistant est une recherche
ÉTROITE (uniquement les tooltips de champs CONFIG), différente de
`logx_search.py` (contenu réel de 12 pages) — les deux se complètent, ne
pas confondre en cas de future demande similaire.
