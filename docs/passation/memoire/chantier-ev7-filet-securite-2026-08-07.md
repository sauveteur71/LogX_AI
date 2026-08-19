---
name: chantier-ev7-filet-securite-2026-08-07
description: "Filet de sécurité EV-7 livré et étendu — 6 scénarios HTTP (config→QSO→export, édition, mode simple, import ADIF, multi-op), première étape obligatoire avant tout refactor frontend"
metadata: 
  node_type: memory
  type: project
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-08-07T17:14:13.387Z
---

Chantier livré et fusionné sur `main` le 07/08/2026 (commit `05cf4d7`, merge
de `feat/ev7-filet-securite-parcours-critique`, commit de contenu `f9f0c1f`).

## Contexte de la décision

Après "[[chantier-doc-api-locale-2026-08-07]]", j'ai proposé 4 options pour
« la suite » (EV-7 refactor complet, EV-5 layouts, diffuser le contenu prêt,
s'arrêter). F4GLD a répondu juste « continuité » — un mot ambigu entre les 3
options actives. **J'ai choisi de poser une question de clarification** avant
d'agir (une des rares fois cette session, la plupart des « la suite »
précédents ayant été traités en autonomie totale) : le fichier
`concours/logx_configuration.html` fait maintenant 8982 lignes et
`logx_logbook.js` 9193 (le PRD estimait EV-7 sur des fichiers de 1000-4000
lignes, écrit avant l'essentiel du travail de cette session) — le vrai scope
d'EV-7 est 2-3x plus gros qu'anticipé, un fait matériel qui justifiait de ne
pas lancer silencieusement un refactor complet sur la seule foi d'un mot
ambigu. F4GLD a choisi **« Filet de sécurité d'abord »** (option recommandée).

## Ce qui a été livré

`concours/tests/test_ev7_filet_securite_parcours_critique.py` (2 tests) :
rejoue le parcours `/config/save` → `/log/add` (doublon puis `force=true`) →
`/log/list` → `/log/export/cabrillo` → `/log/export/adif` → `/log/delete`
par les VRAIES routes HTTP (`ThreadingHTTPServer` + `httpmod.Handler`, même
harnais que `test_log_delta_sync.py`) — jamais un appel direct à une
fonction JS/Python interne, pour qu'un futur refactor du frontend (qui ne
changerait QUE le JS, pas le contrat HTTP) ne fasse jamais échouer ce test
sans raison. `contest_id` volontairement synthétique
(`GOLDEN_PATH_TEST`, absent de `CONTEST_DEFINITIONS`) : le test ne dépend
d'aucun règlement réel qui pourrait changer.

## Vérification adversariale (le test a-t-il vraiment des dents ?)

Deux régressions injectées séparément puis restaurées (`git checkout --` sur
le fichier concerné) :
1. Garde-fou doublon désactivé (`if dup and not force:` → `if False:`) —
   **n'a PAS fait échouer le test** au premier essai : découverte qu'il y a
   DEUX points de contrôle redondants (défense en profondeur contre une
   race TOCTOU, `_find_dup()` rappelé sous verrou juste avant l'insertion) —
   casser un seul des deux ne suffit pas. Pas un défaut du test, juste une
   méthode de cassage insuffisante — reflex à avoir pour toute vérification
   adversariale future sur ce fichier : `add_qso_to_log` a un contrôle
   dupliqué intentionnel, il faut casser les DEUX pour simuler une vraie
   régression de ce garde-fou.
2. Fin de fichier Cabrillo supprimée (`lines.append('END-OF-LOG:')` → `pass`)
   — a bien fait échouer les 2 tests. Restauré, suite repassée verte.

## Bug réel trouvé PENDANT la vérification (pas dans le code visé — dans mon propre test)

`logx_storage.deleted_qsos` est un état module-level global, jamais remis à
zéro entre tests sauf si un test le monkeypatch explicitement (pattern déjà
suivi par `test_add_qso_bump_et_stamp_sont_atomiques_avec_le_verrou` dans
`test_log_delta_sync.py`, que je n'avais pas reproduit). Mon étape `/log/delete`
appelait `mark_qso_deleted()` qui mutait ce VRAI global en place — polluant
`test_log_delta_sync.py::test_log_list_since_valide_ne_renvoie_que_le_delta`
(exécuté plus tard dans le même processus pytest), qui échouait **une fois
sur deux selon l'ordre de collecte**, jamais en isolation. Détecté en
lançant la suite complète (pas juste mon fichier) après l'écriture initiale.
Corrigé en isolant aussi `deleted_qsos`/`log_version`/`hard_reset_version`
dans la fixture `server`. **2 passes complètes consécutives vertes** après
correctif (confirmation explicite demandée avant de committer).

## Extension de couverture (07/08/2026, merge f205856)

F4GLD a choisi "étend la couverture" comme suite immédiate. 4 scénarios
ajoutés au même fichier : correction de QSO (`/log/update`, y compris le 404
explicite si un autre poste l'a supprimé entre-temps), `usage_mode='simple'`
qui désactive la règle doublon, import ADIF (`/log/import_adif/preview` puis
`/commit`), catégorie `MULTI-OP` du Cabrillo quand 2 QSO ont un `operator`
distinct. 6 tests au total désormais. Vérification adversariale sur 2 des 4
(représentatif, méthode déjà validée par le premier lot) : les deux cassées
séparément ont bien fait échouer le test dédié.

Bug de test trouvé en écrivant le scénario import ADIF (pas dans le code
visé) : les QSO importés ne portent pas de `contest`, donc filtrés hors de
`/log/list` sous une portée concours active (même mécanisme de portée que
d'habitude — comportement réel et voulu, pas un bug serveur). Réécrit en
`usage_mode='simple'`, plus représentatif du vrai cas d'usage "importer un
log déjà commencé ailleurs". 2 passes complètes consécutives vertes avant
fusion, comme pour le lot précédent.

## Reliquat

Le VRAI refactor EV-7 (extraction de la logique métier des 2 gros fichiers
vers des modules JS réutilisables) n'a toujours pas commencé — ce chantier
n'est que son prérequis, maintenant un peu plus large (6 scénarios plutôt
que 2). Reste à décider avec F4GLD : lancer le refactor complet (scope 2-3x
plus gros que le PRD ne l'anticipait), étendre encore la couverture
(scoring/`/log/check`, assistant IA de règlement, wizard CONFIG multi-étapes
côté JS), ou continuer sur EV-5/diffusion à la place.
