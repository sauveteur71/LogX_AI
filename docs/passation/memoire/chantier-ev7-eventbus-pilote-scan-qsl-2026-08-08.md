---
name: chantier-ev7-eventbus-pilote-scan-qsl-2026-08-08
description: "EV-7 phase 2 livrée — premier pilote du bus d'événements DOM (SCAN QSL PAPIER via editQSO()), autorisé explicitement par F4GLD comme chantier non urgent ('ce sera fait pour plus tard') ; motif différent des 9 incréments d'extraction pure qui précédaient"
metadata:
  type: project
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-08-08T04:31:13.094Z
---

Chantier livré et fusionné sur `main` le 08/08/2026 (commit `37d4327`, merge
de `feat/ev7-eventbus-pilote-scan-qsl`, commits de contenu `ffd8788` +
`dd6fed1`).

## Contexte

Après 9 incréments EV-7 de pure extraction (copié-collé verbatim d'un bloc
autonome — voir [[chantier-ev7-outils-autonomes-2026-08-08]]), 2 audits
Explore successifs avaient conclu que le stock de blocs contigus sans
dépendance cœur était épuisé. F4GLD a explicitement demandé « ok est ce
interrresant necessaire de faire ce chantier en sachant que le logiciel va
continuer a grossir » (question exploratoire, réponse concise donnée sans
lancer d'implémentation), puis a autorisé explicitement : « ok lance le
chantier ce sera fait pour plus tard » — chantier cadré comme NON URGENT,
à mener incrément par incrément comme la campagne EV-7 classique, pas en
big-bang.

## Pivot de périmètre pendant le chantier (important pour la suite)

Le candidat initialement envisagé (RADIO CAT/AMPLI/ROTOR/WSJT-X via
`refreshHardware()`) s'est avéré, à l'investigation réelle du code (pas au
résumé d'un agent antérieur), bien plus entremêlé que prévu :
`applyWsjtxState()` appelle DIRECTEMENT `refreshPounce()` (WAIT-AND-POUNCE)
ET `appliquerSuiviCarres()` (LOCATOR TRACKER) — 3 sous-systèmes emboîtés,
pas un simple dispatcher unique. CLOCK+COUNTDOWN écarté aussi : appelé
depuis `setupDone()` (fonction cœur de fin de config) et son UI est
TOUJOURS visible — pas vraiment « optionnel ». Les deux ont été abandonnés
SANS écrire de code (juste du temps de cadrage perdu, pas d'édition à
défaire) avant de choisir SCAN QSL PAPIER comme premier pilote réellement
sûr.

## Le motif « bus d'événements » (nouveau, différent des 9 incréments précédents)

`editQSO()` (cœur, `logx_logbook.js`) émettait un appel direct à
`_renderEditQslScan()` — la dépendance cœur→optionnel interdite depuis le
2e incrément ([[chantier-ev7-outils-maintenance-logbook-2026-08-07]], leçon
du moteur de filtre). Au lieu d'extraire tel quel en gardant l'appel dur,
`editQSO()` émet maintenant :
```js
document.dispatchEvent(new CustomEvent('logx:qso-editing-opened', {detail: {qso: q}}));
```
`logx_scan_qsl.js` (nouveau fichier) s'y abonne :
```js
document.addEventListener('logx:qso-editing-opened', e => {
  _renderEditQslScan(e.detail.qso.qsl_scan);
});
```
Le cœur ne sait plus que ce module existe. Sens du flux : UNIQUEMENT
cœur→module (fire-and-forget), jamais l'inverse.

## Pourquoi SCAN QSL était sûr et CHAMPS ADIF ne l'était pas

Candidat voisin physiquement adjacent dans `editQSO()`/`saveEdit()` :
CHAMPS ADIF PERSONNALISÉS (`editExtraFields`). Délibérément EXCLU :
`saveEdit()` (cœur) LIT `editExtraFields` en retour pour construire le
payload de sauvegarde — dépendance BIDIRECTIONNELLE qui demanderait un
mécanisme d'échange à deux sens (pas le simple fire-and-forget utilisé
ici). SCAN QSL est sûr précisément parce que `saveEdit()` ne lit jamais
`qsl_scan` en retour — `uploadQslScan()` persiste directement au serveur
(`POST /qsl_scan/upload`) et met à jour `qsoLog` localement, indépendamment
du flux d'enregistrement du formulaire d'édition.

**Généralisation pour la suite de la phase 2** : avant d'extraire un bloc
via bus d'événements, toujours vérifier qu'aucune fonction cœur voisine
(souvent la fonction de sauvegarde/validation qui suit juste après) ne LIT
l'état du module optionnel en retour — c'est le nouveau piège spécifique à
ce motif, distinct du piège « dépendance cœur→optionnel directe » des
incréments 1-9.

## Piège de test proactivement anticipé (pas découvert réactivement)

`new CustomEvent(...)`/`document.dispatchEvent(...)` appelé depuis une
fonction cœur est un motif JAMAIS utilisé avant dans `logx_logbook.js`.
Tout test py_mini_racer (V8 nu, sans navigateur réel) qui charge ce fichier
ET appelle une fonction qui dispatche désormais un événement a besoin d'un
stub `document.dispatchEvent` + constructeur global `CustomEvent`, sinon
`ReferenceError`. Convention réutilisée (déjà existante dans
`tests/test_pastille_orage_cache_froid.py`) :
```js
dispatchEvent:function(){ return true; },
// top-level :
function CustomEvent(n, o){ this.type = n; this.detail = (o||{}).detail; }
```
Appliqué à `tests/test_edit_qso_mode_hors_concours.py` (seul fichier
appelant `editQSO()` dans un moteur JS nu — confirmé par la revue
adversariale, 45 fichiers chargent `logx_logbook.js` mais un seul appelle
`editQSO()`) **avant** de lancer les tests, pas après un échec — 4e
application consécutive de la leçon des incréments 4/5/9 (grep par nom de
fonction ET flux d'exécution, pas seulement les chaînes de message).

## Constat de la revue adversariale (corrigé avant fusion)

`JS_EXTRAITS_EV7` dans `tests/test_logbook_menu_debut_fin.py` n'avait pas
été étendu à `logx_scan_qsl.js` (rupture de la convention établie aux
incréments 6-9, voir [[chantier-ev7-qtc-2026-08-07]]). Sans impact
fonctionnel réel (aucune fonction de ce fichier n'apparaît dans
`itemsMenuLogbook()`), mais corrigé quand même par cohérence — commit
séparé `dd6fed1` avant fusion.

## Vérification

2 passes pytest complètes vertes (8756 tests). Vérification navigateur
réelle contre données de production (QSO id `1785765238844`) : événement
émis avec le bon `detail`, listener exécuté, modale édition ouverte/fermée
proprement, aucune nouvelle erreur console. Revue adversariale Workflow (3
agents en parallèle) : équivalence stricte du code déplacé confirmée par
diff byte-à-byte, dépendance cœur→optionnel confirmée strictement à sens
unique, couverture de tests confirmée complète (un seul fichier concerné,
déjà corrigé).

`logx_logbook.js` : 7328 → 7328 lignes de code réel avant/après ce commit
précis (le déplacement retire ~50 lignes de fonctions mais le point d'appel
en ajoute quelques-unes ; net proche de zéro sur ce pilote — la valeur
n'est pas la réduction de lignes ici mais la suppression de la dépendance
directe cœur→optionnel).

## Reliquat pour la suite de la phase 2 (NON lancé, cadré uniquement)

Toujours en attente, chacun nécessitant son propre cadrage cas par cas (pas
un motif mécanique répétable comme les incréments 1-9) : RTTY/SSTV
(`updateKeyerPanels()`), RADIO CAT/AMPLI/ROTOR/WSJT-X (`refreshHardware()`
— confirmé complexe, 3 sous-systèmes entremêlés, PAS un premier bon
candidat), MACROS F1-F8+SO2R+band-map (handler clavier global),
busted-pastille+ESM (`submitQSO()`), CHAMPS ADIF PERSONNALISÉS
(nécessiterait un motif bidirectionnel, pas encore conçu). Aucune cible
suivante choisie ni autorisée à ce stade — « ce sera fait pour plus tard »
signifie non urgent, pas planifié dans l'immédiat.
