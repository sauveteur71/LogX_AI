---
name: chantier-ev7-cw-panel2-audio-2026-08-09
description: "EV-7 30e incrément : extraction DÉCODEUR CW #2 (audio) vers logx_cw_panel2_audio.js (09/08, merge edd6dcc) — dépendance top-level async analysée en profondeur, branche RTTY vérifiée en navigateur réel, 1 constat mineur (commentaire obsolète) corrigé"
metadata: 
  node_type: memory
  type: project
  modified: 2026-08-09T05:59:59.343Z
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
---

30e incrément de la campagne, candidat MOYEN du 3e inventaire
([[inventaire-ev7-3e-2026-08-09]]). Extraction de 118 lignes de
`concours/logx_logbook.js` (3963-4080) vers `concours/logx_cw_panel2_audio.js`
(nouveau) : `_cwPanelInstances`/`_cwPanel(suffix)` (instanciation paresseuse
de `CwPanel`), les wrappers globaux `toggleCwPanel()`/`toggleCwPanel2()`/
`toggleCwDecoder()`/`toggleCwDecoder2()`/`clearCwOutput()`/
`clearCwOutput2()`/`setCwFreq()`/`setCwFreq2()`, les accesseurs de
compatibilité `_cwOutText`/`_cwOutText2`, et `loadAudioInputDevices()`/
`loadAudioOutputDevices()` (génériques, réutilisées par l'enregistreur audio
par QSO ET le panneau RTTY, tous deux restés dans le cœur).

**Dépendance croisée la plus délicate de ce chantier** : `startAudioRecorder()`
(cœur) appelle `loadAudioInputDevices('qsoRecDevice', true)`, via la chaîne
`initAudioRecorderPanel()` — appelée de façon TOP-LEVEL non gardée en bas de
`logx_logbook.js` (`initAudioRecorderPanel();`, sans DOMContentLoaded).
Analysée en profondeur (pas seulement "ça a l'air ok") : `initAudioRecorderPanel()`
est `async`, son premier `await` porte sur IndexedDB (toujours asynchrone
par spec navigateur) — la suite de la fonction (dont l'appel réel à
`loadAudioInputDevices`) ne s'exécute donc JAMAIS de façon synchrone au
chargement du script, elle est reportée après la fin du chargement de TOUS
les `<script>` classiques de la page, donc après que `logx_cw_panel2_audio.js`
(chargé avant `logx_logbook.js`) ait fini de définir la fonction — sûr par
construction, pas par chance. Confirmé indépendamment par le 2e dimension de
la revue adversariale (dependency-integrity), qui a reconstruit la séquence
d'exécution exacte et n'a trouvé aucun chemin de rupture.

Seconde dépendance (déjà un motif connu) : `updateKeyerPanels()` (cœur)
appelle les deux fonctions uniquement sous garde `if(rtty){}` — motif déjà
accepté pour `renderRttyMacroBtns()` (RTTY, extrait précédemment).

3 fichiers de test mis à jour : `test_cw_panel_consolidation.py` (nouveau
`CW_PANEL2_AUDIO_JS_PATH`, inséré dans `_make_ctx()`/`_ctx_avec_ecouteurs()`
juste avant `JS_PATH`, et le comptage de `toggleCwDecoder` élargi aux deux
fichiers), `test_audio_recorder_client.py` (idem dans `_real_source()`, et
le marqueur `loadAudioInputDevices` cherché séparément dans le nouveau
fichier), `test_logbook_menu_debut_fin.py` (`JS_EXTRAITS_EV7`). Suite pytest
complète (8792 tests) verte deux fois de suite (première mesure faussée par
une double mise en arrière-plan accidentelle — `run_in_background:true` +
`&` interne au script — corrigée en relançant proprement).

Vérification navigateur réelle sur le serveur de production (jamais
redémarré) : **piège retrouvé** — naviguer vers `/concours/logx_logbook.html`
sert un contenu périmé/vide sur ce serveur ; la bonne URL est la racine
`/logx_logbook.html`. Une fois sur la bonne URL : toutes les fonctions
exportées opérationnelles, `toggleCwPanel()`/`toggleCwPanel2()` instancient
réellement des objets `CwPanel`, `clearCwOutput()`/`clearCwOutput2()`
réinitialisent bien `_cwOutText`/`_cwOutText2`. **Branche RTTY testée
spécifiquement** (seule jamais exercée par pytest) : `rigState.mode='RTTY'`
+ appel réel de `updateKeyerPanels()` → `loadAudioInputDevices('rttyDevice')`
et `loadAudioOutputDevices('rttyOutDevice', true)` bien appelées (vérifié
par espionnage des deux fonctions).

Revue adversariale (extraction-fidelity + dependency-integrity, 7 agents,
chaque constat re-vérifié indépendamment) : 5 constats bruts, 1 seul
confirmé (rapporté en double par les 2 dimensions) — commentaire obsolète
dans `logx_cw_panel.js` citant encore `logx_logbook.js` comme définissant
`loadAudioInputDevices()` ; corrigé dans le même commit, sans impact
fonctionnel (l'appel ne se produit que sur interaction utilisateur).

`logx_logbook.js` : ~4364 → ~4246 lignes.

Suite : dernier candidat MOYEN restant du 3e inventaire — BANDSCOPE+WATERFALL
(31e incrément), puis MACROS F1-F8 (32e), puis FILTRE SPOTS+refreshBandMap
(33e), avant de lancer un 4e inventaire Workflow.
