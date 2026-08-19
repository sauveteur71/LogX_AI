---
name: chantier-dialogues-non-bloquants-chantier2-suite-2026-08-10
description: "Suite du chantier accessibilité : élimine les ~43 alert()/confirm() natifs restants trouvés par exploration (15 fichiers) — bug critique z-index trouvé par revue adversariale, PR #17 ouverte non fusionnée"
metadata:
  node_type: memory
  type: project
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-08-11T04:59:21.897Z
---

Demandé par F4GLD le 10/08/2026 ("continue de travailler jusqu'à mon retour,
il faut que tous ces points soient traités" — en référence à une analyse
concurrentielle antérieure, tous déjà traités sauf VOACAP). En autonomie
pendant l'absence de l'utilisateur, un agent Explore a inventorié le dépôt
et trouvé que le [[chantier-accessibilite-1-2-2026-08-09]] (chantier 2,
09/08/2026) n'avait converti QUE 2 des ~45 sites `alert()`/`confirm()`
natifs bloquants réels du dépôt — les 2 autres cas explicitement différés
à l'époque (doublon QSO, validation CONFIG). Ce chantier traite le reliquat.

## Ce qui a été fait

- `_confirmDupBanner(message, yesLabel, noLabel)` (logx_logbook.js) : les
  deux nouveaux paramètres optionnels (défaut = comportement historique
  "Enregistrer quand même"/"Annuler") permettent de réutiliser LE MÊME
  bandeau partagé pour ~15 actions sans rapport avec le doublon QSO
  d'origine (suppression, publication, archivage...) sans afficher un
  bouton au libellé trompeur.
- Équivalent créé pour `logx_configuration.html` (script inline, pas de
  portée JS partagée avec logx_logbook.js) : `_confirmConfigBanner()` +
  `_configToast()`, même patron Promise<boolean>/toast auto-disparaissant.
- 3 pages autonomes (`logx_statusbar.js` chargé sur presque toutes les
  pages, `logx_mobile.html`, `logx_panadapter.html`) : toast/bandeau
  injectés dynamiquement au premier appel, aucune dépendance à un élément
  HTML pré-existant — même patron que les scripts injectant déjà leur
  propre DOM (statusbar construit toute la barre par JS).
- 12 fichiers loggés/chargés sur `logx_logbook.html` convertis en
  réutilisant `notify()`/`_confirmDupBanner()` déjà existants : dup_finder,
  edit_qso, qtc, verif_panel, net_control, export_adif, export_edi,
  bulk_resolve, popout_selfspot, hardware_cat, outils_autonomes,
  filter_builder.

## 🚨 Bug critique trouvé par la revue adversariale (Workflow, 14+14 agents)

`#dupConfirmBanner` était en FLUX NORMAL (aucun `position`/`z-index`) dans
son CSS d'origine — conçu pour un seul contexte (champ INDICATIF du
formulaire QSO principal, jamais recouvert). En le réutilisant depuis ~10
fichiers dont les actions se déclenchent DEPUIS UN POPUP PLEIN ÉCRAN
(`.shortcuts-overlay`, `position:fixed;z-index:500`), le bandeau se
retrouvait rendu SOUS le calque opaque à 92% du popup — invisible,
incliquable, la Promise ne se résolvant jamais tant que l'opérateur ne
fermait pas le popup par un autre biais. **Régression totale par rapport
au `confirm()` natif remplacé**, qui était toujours au premier plan.

Trouvé indépendamment par PLUSIEURS agents de vérification travaillant sur
des fichiers différents (dup_finder, net_control, bulk_resolve, verif_panel)
— chacun a identifié le MÊME défaut systémique dans le CSS partagé, pas
propre à son fichier. Confirmé par eux via `document.elementFromPoint()`
en navigateur réel (renvoie l'overlay, pas le bandeau).

**Corrigé AVANT tout commit** : `.dup-confirm-banner{position:fixed;
top:70px;left:50%;transform:translateX(-50%);z-index:9999;...}` (même
patron que `#configConfirmBanner`, déjà construit fixed dès le départ car
créé APRÈS avoir anticipé ce risque pour CONFIG). Un seul edit CSS a
suffi à corriger simultanément tous les ~10 sites concernés — la
mutualisation qui causait le bug initial a aussi permis un correctif en
un seul point.

**Effets de bord corrigés dans la foulée** (le bandeau devenant le
premier plan visuel, mais pas encore le premier plan clavier) :
- `_elementModaleOuverte()` (logx_theme_shortcuts.js) : le bandeau est
  désormais vérifié EN PREMIER (avant même `setupModal`), sinon le piège
  de focus Tab restait confiné à l'overlay du dessous — inatteignable au
  clavier bien que visible.
- `watchedIds` (auto-focus à l'ouverture) : `'dupConfirmBanner'` ajouté à
  la liste déjà existante, réutilisant le MutationObserver générique.
- Handler Échap : `_cancelPendingDupConfirm()` appelé en tout premier,
  avant tout le reste — un `confirm()` natif se fermait déjà sur Échap.

## Autres constats réels trouvés par la revue adversariale (corrigés)

- `archiveLog()` (logx_outils_autonomes.js) : SEUL des ~17 appelants du
  dépôt où `false` (refus) n'interrompt PAS l'action — les deux réponses
  archivent, seul le fait de vider le log actif diffère. Les libellés
  `'Archiver'`/`'Annuler'` masquaient cette nuance (« Annuler » archive
  quand même). Renommés `'Archiver et vider'`/`'Archiver sans effacer'` +
  texte du message aligné (ne mentionne plus un bouton "OK" disparu).
  **Risque documenté mais non corrigé en profondeur** (déprioritisé,
  contrainte de temps) : `_cancelPendingDupConfirm()` peut désormais
  résoudre `false` SANS interaction (ex. l'opérateur retape un indicatif
  ailleurs pendant que ce bandeau précis est ouvert) — dans ce cas
  précis, l'archivage part quand même sans consentement explicite. Pas
  de perte de données (le log actif n'est jamais vidé sans réponse
  explicite), juste un archivage non sollicité. Distinguer auto-annulation
  et refus explicite nécessiterait un signal tri-état sur la Promise
  partagée par les 17 appelants — hors scope de ce chantier.
- `resetLog()` : message mentionnait encore "Tape OK pour continuer" sans
  bouton "OK" — corrigé (texte retiré, le libellé du bouton suffit).
- Indentation de template littéral (`_statusbarToast`/`_paToast`) :
  `white-space:pre-line` posé sur le CONTENEUR plutôt que le `<span>`
  interne faisait apparaître les retours à la ligne STRUCTURELS du
  template (avant `<style>`, avant `<span>`) comme des lignes vides
  visibles au-dessus du message — corrigé en déplaçant la règle sur le
  `<span>` uniquement. Piège généralisable à tout futur toast auto-injecté
  par template literal indenté.
- `role="status" aria-live="polite"` manquant sur `#rcsbToastMsg`
  (contrairement aux toasts frères `#configToast`/`.macro-toast`) —
  ajouté, alignement accessibilité.

## Tests cassés par la conversion (6 fichiers, tous corrigés + vérifiés)

- `tests/test_export_edi_num_sent.py`, `tests/test_logbook_render_window_reset.py` :
  stubaient `confirm = function(){ return true; };` — mort désormais
  (plus jamais appelé). Ajouté `_confirmDupBanner = function(){ return
  Promise.resolve(true); };` en complément. **Découverte empirique
  importante** : appeler une fonction `async` qui `await` une Promise
  DÉJÀ résolue (`Promise.resolve(true)`) depuis `ctx.eval("maFonction();")`
  dans py_mini_racer (V8) n'a PAS nécessité de flush manuel de microtâches
  (contrairement au patron `_flush(ctx)` de `test_dup_confirm_banner.py`,
  qui lui gère une Promise `pending` résolue PLUS TARD par un event
  séparé) — un `ctx.eval()` séparé et SUBSÉQUENT suffit à observer l'état
  post-résolution, confirmé empiriquement (pas supposé) en lançant la
  suite réelle avant de chercher plus loin.
- `tests/test_config_category_switch.py`, `tests/test_assistant_banner_popup_js.py` :
  extraction de fonction par regex ANCRÉE `^function nom\(` — ne matche
  plus `async function nom\(`. Corrigé en `^(?:async\s+)?function nom\(`.
  Sans l'ancrage `^`, l'échec est différent et plus sournois (voir
  fichier suivant).
- `tests/test_operateurs_retrait_ligne.py` : extraction NON ancrée
  (`function\s+nom\s*\(`) — le match RÉUSSIT quand même sur
  `async function nom(` mais `m.start()` pointe APRÈS le mot "async", donc
  le snippet extrait `src[m.start():j+1]` commence par "function nom("
  mais son CORPS contient toujours `await` → `SyntaxError` JS silencieux
  seulement au moment du `ctx.eval()`, pas au moment du match regex.
  Piège plus difficile à diagnostiquer qu'un simple "fonction introuvable".
  Corrigé en incluant `(?:async\s+)?` DANS le groupe qui définit
  `m.start()`.
- `tests/test_operateurs_nombre.py` : `assert 'confirm(' in fn` — un test
  purement textuel (pas d'exécution JS) qui vérifiait la présence d'un
  confirm() par sous-chaîne littérale. `_confirmConfigBanner(` NE contient
  PAS la sous-chaîne `confirm(` (le `C` majuscule de Config suit
  immédiatement `confirm`, pas de `(`) — corrigé en cherchant
  `_confirmConfigBanner(` à la place.

## 🚨 Piège de process découvert pendant la vérification (pas dans le code)

Un agent de vérification (dup_finder.js) a fait "une vérification en
navigateur réel sur l'instance http://127.0.0.1:8080" — **le serveur DE
PRODUCTION de l'utilisateur**, pas une instance isolée, en violation de la
règle établie de session (toujours utiliser un port isolé pour ne jamais
perturber la session active de F4GLD, voir
[[piege-serveur-8080-sert-depot-principal-pas-worktree]]). Repéré après
coup en observant `tabs_context()` (un onglet `127.0.0.1:8080` inattendu)
plutôt que signalé par l'agent lui-même. **Aucune perte de données** :
vérifié directement dans `shared_log.json` (9872 QSO intacts) — le "0 QSO"
affiché à l'écran pour REF_MARCONI est un effet du filtrage par portée de
concours (feature existante, sans rapport), pas une suppression réelle.
Mais le risque était réel : le test exerçait justement `dupDeleteOne()`/
`dupDeleteMany()`. **Leçon pour tout futur Workflow avec des agents de
vérification en navigateur** : préciser EXPLICITEMENT dans le prompt
partagé de ne JAMAIS utiliser le port du serveur de développement standard
(8080) et de toujours lancer/utiliser une instance isolée — cette règle,
déjà appliquée par moi-même tout au long de la session, n'avait pas été
transmise aux agents du Workflow.

## État final

- Commit `492bfc1` sur `feat/dialogues-non-bloquants-chantier2-suite`,
  PR #17 (https://github.com/sauveteur71/radioaamateur-program-Contest/pull/17).
  Fusionnée sur main.
- Suite pytest complète verte après tous les correctifs.
- Vérifié en navigateur réel (serveur isolé port 8099, PAS 8080) :
  `elementFromPoint()` confirme le bandeau au premier plan et cliquable
  au-dessus d'un overlay ouvert, fermeture par bouton ET par Échap
  fonctionnelles.

## Reliquat volontairement non traité (documenté, pas oublié)

- Auto-annulation silencieuse d'`archiveLog()` (voir plus haut).
- `#configConfirmBanner` n'a pas de fermeture par Échap (contrairement à
  `#dupConfirmBanner` maintenant) — `logx_configuration.html` ne charge
  pas `logx_theme_shortcuts.js`, aurait nécessité son propre handler.
- Quelques appels `selectContest()`/`openCategoryPopup()` sans `await` ni
  `.catch()` (ex. `switchSection()`, `init()`) — rejets de promesse non
  gérés en cas d'exception future, fonctionnellement correct aujourd'hui.
- `prompt()` natifs bloquants trouvés en passant (resetLog() ligne
  suivante, 2 dans logx_statusbar.js) — hors périmètre de ce chantier
  (alert/confirm seulement), à traiter dans une suite dédiée si voulu.
