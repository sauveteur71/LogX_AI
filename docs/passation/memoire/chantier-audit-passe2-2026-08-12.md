---
name: chantier-audit-passe2-2026-08-12
description: "2e passage d'audit exhaustif (loop-until-dry, 617 agents) — 322 constats trouvés, 20 critiques corrigés (PR #37), ~302 restants pour un futur chantier"
metadata: 
  node_type: memory
  type: project
  originSessionId: 98b0707f-1a89-40bf-8422-4ab7b88ba78a
  modified: 2026-08-12T03:17:07.685Z
---

Suite à "go second passage" + "fait les correction je m'absente" (F4GLD,
11-12/08/2026 dans la nuit), lancement d'un 2e Workflow d'audit bien plus
profond que le premier (voir [[chantier-audit-securite-obsolete-bugs-2026-08-11]]) :
8 dimensions plus fines (endpoints/auth, SSRF/subprocess, secrets/crypto,
balayage XSS complet, obsolète backend/frontend suite, bugs backend/frontend
suite), en boucle **loop-until-dry** (2 tours consécutifs sans rien de neuf
pour s'arrêter).

## Échelle réelle — bien au-delà du prévu

**617 agents, ~10h15 d'exécution, 78M tokens, 35 tours de boucle avant
convergence.** La clé de déduplication (`fichier:ligne`) était trop fragile
pour un vrai loop-until-dry sur un dépôt de cette taille : le MÊME bug réel
(ex. `post_url_json`/`post_url_form` sans validation de schéma dans
`logx_utils.py`) était re-découvert à des lignes légèrement différentes par
des agents différents à travers les tours, empêchant la convergence — le
loop ne s'est terminé qu'après que des erreurs réseau (ECONNRESET, rounds
34-35) aient fait tomber des chercheurs, créant un faux "rien de neuf" par
effet de bord plutôt qu'une vraie exhaustion.

**Résultat brut : 322 constats confirmés sur 337 examinés (95,6% de taux de
confirmation)** — 28 critique, 132 majeur, 162 mineur. Ce taux est
suspicieusement élevé comparé au 1er passage (14/14 = 100% mais sur un
volume 20x plus petit, donc plus fiable) : signe probable d'une dérive de
qualité de la vérification adversariale à cette échelle (un seul
vérificateur sceptique par constat, pas de vote à 3, sur un volume que
personne n'a pu relire un par un avant application).

**Leçon pour la prochaine fois** : sur un dépôt de cette taille, soit (a)
plafonner le nombre de tours de boucle explicitement (ex. max 5-6) plutôt
que de compter uniquement sur "2 tours à sec", soit (b) utiliser une clé de
dédup sémantique plus robuste que `fichier:ligne` brut, soit (c) accepter
qu'un tel passage produira un GROS volume nécessitant un TRIAGE manuel
avant correction — ne jamais supposer qu'on peut "juste corriger" 300+
constats en une nuit sans un tri de priorité et de confiance.

## Ce qui a été fait cette nuit : les 28 critique, triés à la main

Sur les 28 constats de sévérité **critique**, 20 corrigés (PR
[#37](https://github.com/sauveteur71/radioaamateur-program-Contest/pull/37),
mergée), 1 documenté et volontairement laissé (voir plus bas), les 7
restants (cluster localStorage/serveur en CONFIG/LOGBOOK) jugés trop
systémiques/risqués pour une correction de nuit sans validation humaine —
voir section dédiée plus bas.

### Le plus grave : LOGBOOK cassé en production

`setupDone()` (logx_logbook.js:1568) plantait sur
`document.getElementById('currentOp').textContent = ...` — élément retiré
du HTML lors d'un refactor antérieur (probablement pendant la campagne
EV-7), jamais mis à jour ici alors que `_setCurrentOpLabel()` juste avant
avait déjà le même garde (`if(cur) cur.textContent = ...`) pour le MÊME id.
Un throw synchrone à cette ligne coupait TOUT ce qui suit dans la fonction :
`startRefresh()`, `startON4KSTReminder()`, `startChat()`, `fetchLog()` ne
s'exécutaient JAMAIS. **Confirmé actif sur le serveur live avant
correctif** (console : `TypeError: Cannot set properties of null`, en
boucle ; `qsoLog` vide, `isSetupDone` resté `false`). Ce bug pré-datait
cette session — probablement présent depuis le refactor qui a retiré
`#currentOp` du HTML, jamais remarqué car les tests V8 ne chargent pas de
vrai navigateur et un humain qui a déjà un indicatif configuré ne repasse
pas souvent par l'écran de setup.

### Piège découvert en corrigeant le CSRF (voir aussi [[piege-echo-exit-masque-code-sortie-reel]] pour la méthode de vérification)

Fix CSRF (`do_POST` exige désormais `Content-Type: application/json`,
matière SameSite=Strict qui n'empêche PAS un tiers colocalisé sur la même
IP mais un port différent de rejouer une route protégée — la notion de
« site » de SameSite ignore le port) a cassé **9 appels `fetch()` POST
légitimes du frontend qui n'envoyaient jamais ce header** (boutons sans
corps : `satTrackStop`, raccourci bureau, MAJ logicielle, suppression de
shift...). Détecté par la suite pytest (1 test HTTP a échoué avec 415),
PAS par une relecture manuelle — la vérification initiale (grep sur
`JSON.stringify` uniquement) avait un angle mort total sur les appels POST
à corps VIDE. Tous les 9 corrigés (header ajouté), plus le test lui-même.
**Réflexe pour toute future garde de ce genre : chercher TOUT
`fetch(...,{method:'POST'...})` sans le header requis, pas seulement ceux
qui ont un `body:`.**

### Constat #8 volontairement NON corrigé (assumé)

`/autostart/launch` exécute le chemin+arguments envoyés dans le corps sans
vérifier qu'ils correspondent à une entrée déjà sauvegardée dans
`autostart_programs` — MAIS c'est intentionnel : le bouton ▶ par ligne du
panneau CONFIG sert explicitement à « vérifier le chemin/les arguments sans
attendre de relancer LogX » (commentaire JS `testAutostartRow()`), donc à
tester une entrée MODIFIÉE MAIS PAS ENCORE SAUVEGARDÉE. Exiger une
correspondance avec la config sauvegardée casserait cette fonctionnalité
voulue. Déjà protégé par `_require_auth()` (jeton) + le
`_chemin_local_valide()` du 1er passage (fichier local déjà présent, jamais
UNC). Un durcissement supplémentaire est un vrai compromis produit
(sécurité vs utilité du bouton de test) — laissé à trancher avec F4GLD,
pas un choix unilatéral à 3h du matin.

### Les 7 constats du cluster localStorage/serveur (CONFIG/LOGBOOK), NON traités

Root cause partagée dans `logx_configuration.js` : `saveConfig()` écrit
`localStorage['logx_config']` et affiche succès AVANT/SANS vérifier que
`POST /config/save` a réellement abouti ; `init()`/`loadSavedConfig()` ne
consulte le serveur QUE si localStorage est vide (jamais après, même au
rechargement) ; `launchApp()` navigue vers LOGBOOK sans attendre la
réponse du save. Plus large : `syncOfflineQueue()` (logx_logbook.js +
logx_mobile.html, 2 sites) peut perdre un QSO hors-ligne ou le dupliquer en
cas d'exécution parallèle. Root cause architecturale, pas un simple oubli
de garde comme le reste — nécessite de repenser le flux
save→verify→navigate proprement, avec un vrai retour utilisateur en cas
d'échec réseau. **À traiter dans un futur chantier dédié, avec discussion
UX au préalable (que montrer à l'opérateur si la sauvegarde échoue en
silence aujourd'hui ?).**

## Corrections notables (détail technique, pour qui reprend ce chantier)

- `logx_scoring.py::build_ranked_spots()` et `/log/check` (logx_http.py) :
  MÊME bug root-cause (ignorent la portée concours active en parcourant
  `shared_log` sans filtre), trouvés comme 2 constats indépendants par 2
  chercheurs différents — un seul correctif a suffi (preuve concrète du
  problème de dédup mentionné plus haut).
- `active_scope_id()` (logx_storage.py) : le repli sur l'année UTC courante
  est désormais figé au 1er appel du process (`_FALLBACK_YEAR`, module-
  level), plus recalculé à chaque appel — sinon les QSO de décembre
  disparaissaient du LOGBOOK filtré pile au passage à la nouvelle année UTC
  pour tout concours sans `contest_start_date` renseigné.
- `logx_scoreboard.py::build_score_snapshot()` : utilise désormais
  `logx_scoring.contest_geo_mode()` (déjà existant, gère briques ET type
  legacy) au lieu de ne lire QUE le `type` legacy — tout concours moderne à
  multiplicateur DXCC/zone/préfixe (bricks) publiait un comptage de
  locators VHF totalement faux au tableau de bord externe.
- `logx_clusters.py::publish_self_spot()` : réutilise
  `logx_rules_ai._is_safe_host()` (SSRF, déjà écrit pour un autre besoin)
  plutôt que d'en réinventer un — patron à généraliser si un futur constat
  touche encore un socket/URL client-controlé.

## Pipeline suivi (identique aux chantiers précédents)

Branche dédiée (`fix/audit-passe2-critiques`) → 20 corrections → pytest
complet (2 itérations, la 1ère a révélé le piège CSRF/Content-Type
ci-dessus) → ruff → vérification navigateur réelle (le bug LOGBOOK
confirmé résolu : `isSetupDone` passe à `true`, `/log/list?since=`
périodique visible, 0 erreur console ; CSRF confirmé : requête légitime
200, simulation CSRF 415) → commit/push/PR
[#37](https://github.com/sauveteur71/radioaamateur-program-Contest/pull/37)/CI/merge
→ sync branche live → pytest complet sur live → redémarrage serveur 8080.

## Reste à faire (futur chantier, ne pas tout attaquer d'un coup)

- 132 constats **majeur** + 162 **mineur** du 2e passage (probablement
  beaucoup de doublons du même type que #4/#23 ci-dessus — dédupliquer
  sémantiquement avant de corriger, pas fichier:ligne brut).
- Le cluster localStorage/serveur (7 constats, voir plus haut) — discussion
  UX avec F4GLD recommandée avant de coder.
- Constat #8 (`/autostart/launch`) — décision produit à prendre avec F4GLD.
