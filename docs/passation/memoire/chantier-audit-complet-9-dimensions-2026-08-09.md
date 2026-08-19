---
name: chantier-audit-complet-9-dimensions-2026-08-09
description: "Passe de vérification complète LogX AI (9 dimensions Workflow) : 8 constats confirmés et corrigés, 5 dimensions propres, 1 flake réseau identifié (09/08, fusionné 09bc07c)"
metadata:
  type: project
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-08-09T16:30:34.117Z
---

Demande spontanée de F4GLD (« fait une passe de verifictation complete »)
après confirmation que le backlog #1-#339 était entièrement `[completed]`
(fin du chantier ACOM #168 + campagne EV-7). Deux Workflow distincts, tous
deux fusionnés sur main : découverte (`wf_2e50e7cd`, 9 dimensions, 17 agents,
1,76M tokens) puis correctifs+revue (`wf_b9a20c36`, 5 dimensions, 5 agents,
426k tokens, 0 constat sur les correctifs).

## Méthode (réutilisable telle quelle pour un futur audit)

9 dimensions couvrant l'appli entière plutôt qu'un balayage fichier par
fichier : sécurité réseau, chemin critique QSO, modules CAT/ampli, intégrité
des modules JS extraits par EV-7, structure `logx_configuration.html`,
cohérence doc/code, conformité « Intuitivité » (CLAUDE.md), santé de la
suite de tests, cohérence design graphite & cuivre. Chaque chercheur limité
à 5 constats max (les plus sérieux), chaque constat brut vérifié
indépendamment par un agent-sceptique dédié (`real=false` par défaut).
**5 dimensions sur 9 étaient entièrement propres** (sécurité réseau,
intégrité JS EV-7, structure config.html, conformité intuitivité) — la
richesse applicative (SO2R, CAT propriétaire, panadapter, FT8, WebSDR...)
documentée dans CLAUDE.md n'a pas dégradé ces axes malgré ~36 incréments
EV-7 et une trentaine de chantiers menés tambour battant début août.

## Les 8 constats confirmés (tous corrigés, voir commit 3d7b40b)

1. **Concurrence réelle, risque matériel** — `concours/logx_acom.py`
   `AcomPort.close()` écrivait `CMD_DISABLE_TELEMETRY` sans tenir
   `self._lock`, contrairement à `send_command()`/`read_one_frame()` — un
   thread en plein `set_operate('operate')` et un thread qui ferme la
   connexion (changement de port en CONFIG) pouvaient entrelacer leurs
   octets sur le fil RS-232 d'un ampli réel. Trouvé par la MÊME revue
   adversariale qui avait déjà mérité l'entrée [[chantier-acom-doc-communautaire-2026-08-09]]
   deux heures plus tôt — corrigé une 2e fois car la 1re revue n'avait
   inspecté que le contenu de `close()`, pas sa synchronisation avec les
   AUTRES méthodes. **How to apply** : une revue « le code fait-il ce que le
   commentaire dit » ne suffit pas — il faut aussi vérifier « ce code
   partage-t-il un état avec d'autres méthodes de la même classe, et ce
   partage est-il protégé de façon cohérente PARTOUT ». Test de régression
   ajouté avec 2 vrais threads + écriture volontairement lente (aurait
   échoué avant le correctif).

2. **Bug fonctionnel réel** — `concours/logx_http.py` `_find_dup()`
   ignorait la date, donc un concours à `dupe_reset='daily'` (WWA,
   règlement §7 : 1 QSO/jour/bande/mode, `scope_id` = contest+ANNÉE
   seulement) refusait à tort un recontact légitime un autre jour du même
   mois. Le popup client ne montrait que l'heure du 1er contact, pas la
   date — aggravant la confusion pour l'opérateur. Corrigé en lisant
   `bricks.get('dupe_reset')` via `resolve_scoring_bricks()` (déjà utilisée
   côté classement des spots, jamais côté `add_qso_to_log()`) + affichage de
   la date dans le popup (`fmtDate()`, déjà globale via `logx_callbook.js`).
   3 nouveaux tests dans `test_contest_scope.py` (bloque même jour, autorise
   jour différent, garde-fou non-régression sur un concours SANS ce trait).

3-4. **Documentation périmée** (2 constats) — `docs/API.md` manquait
   `/callhistory/update_scp` et `/autostart/launch` (2 routes actives non
   documentées, malgré l'auto-description "222 routes... toutes actives").
   `docs/GUIDE_UTILISATEUR.md` affirmait à tort que le KPA1500 n'a pas de
   support réseau (le TCP/UDP existe et fonctionne, `logx_amp.py`).

5. **Documentation périmée mineure (rejetée par la revue mais corrigée quand
   même)** — le paragraphe EDI/Cabrillo décrivait un bug déjà corrigé
   (WAE/UBA/ARRL 10m/160m routaient déjà correctement vers Cabrillo). La
   revue a classé `real=false` car le SCÉNARIO D'ÉCHEC allégué (utilisateur
   forcé de passer par ARCHIVER) ne se produit plus — mais le TEXTE restait
   factuellement faux, donc corrigé par cohérence documentaire malgré le
   verdict `PLAUSIBLE`.

6-7. **Trous de couverture de test** (2 constats) — `logx_cwdecoder.js`
   (décodeur CW temporel, déjà source d'un bug réel documenté en commentaire
   — dérive de l'unité de temps) et `logx_search.js` (recherche plein-texte
   navigateur, `findMatch`/`highlightFromQuery`) n'avaient AUCUN test malgré
   une logique non triviale. 20 nouveaux tests py_mini_racer au total.
   **`logx_search.js` est une IIFE qui ne fuit rien vers le global scope** —
   contrairement aux fichiers EV-7 habituels (classes/fonctions top-level,
   testables directement). Un export CommonJS conditionnel a dû être ajouté
   (`if (typeof module !== 'undefined') module.exports = {...}`, tout à la
   fin, à l'intérieur de l'IIFE) — no-op en navigateur réel (`module`
   n'existe jamais), mais premier cas de ce chantier où « ajouter un test »
   a nécessité un (micro-)changement de code de production. **How to
   apply** : avant d'écrire des tests pour un fichier JS, vérifier s'il
   expose ses symboles en top-level (comme `logx_cwdecoder.js`) ou les
   enferme dans une IIFE (comme `logx_search.js`) — dans le 2e cas, soit
   ajouter ce même export conditionnel, soit construire un DOM/environnement
   assez complet pour exercer le fichier via ses SEULS effets de bord
   observables (le 2e est plus fidèle mais bien plus coûteux à écrire).

8. **Cohérence design (mineur)** — `mapLocCompare()` dans
   `logx_configuration.html` peignait le marqueur/trait Leaflet de la carte
   locator avec `#E8964A` codé en dur (valeur --accent2 du thème NUIT),
   cassant le contraste en thème jour. Corrigé en passant la CHAÎNE littérale
   `'var(--accent2)'` à Leaflet (`color`/`fillColor`) — vérifié en navigateur
   réel que ça fonctionne : `getComputedStyle().stroke` bascule correctement
   de `rgb(139,79,31)` (jour) à `rgb(232,150,74)` (nuit) au toggle de
   `body.day-mode`, SANS même redessiner le marqueur (résolution CSS live via
   l'attribut de présentation SVG). **How to apply** : pour un futur hex codé
   en dur dans du SVG/Canvas généré en JS (Leaflet ou autre lib), la
   correction n'est pas nécessairement de calculer la valeur résolue en JS —
   passer directement la chaîne `'var(--accent2)'` à l'API graphique
   fonctionne souvent aussi bien, et reste réactif au changement de thème
   sans code de mise à jour supplémentaire.

## Piège reconfirmé pendant ce chantier

Suite pytest complète relancée 2 fois pendant les correctifs : 1 échec
(`test_update_integrity.py::test_peer_annoncant_le_bon_asset_toujours_accepte`,
mécanisme pair-à-pair de mise à jour, sans rapport avec les 8 correctifs)
apparu au 1er run, absent au 2e, et passe 3/3 en isolement AUSSI BIEN sur
main que sur la branche — flake sous charge déjà documenté
([[suite-tests-flakes-sous-charge]]), pas une régression. Confirmé
empiriquement par `git stash`/`stash pop` (le test passe sur l'état stashé
ET sur l'état restauré) plutôt que supposé depuis le fait qu'aucun fichier
touché ne concerne ce mécanisme — **toujours vérifier empiriquement même
quand la logique semble déjà trancher**.

## Voir aussi

[[chantier-acom-doc-communautaire-2026-08-09]] (chantier précédent le même
jour, revue adversariale ayant trouvé le 1er des 2 bugs `logx_acom.py`
avant celui-ci).
