---
name: feedback-vocabulaire-radioamateur
description: "Interdiction d'« activation »/« activateur » dans les textes FRANÇAIS visibles de LogX AI — vocabulaire radioamateur exigé (30/07/2026)"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-07-30T15:16:55.345Z
---

Le 30/07/2026 l'utilisateur a exigé, mot pour mot : « supprime ce language cibiste avec ACTIVATION ACTIVATEUR etc on est radioamateur ! ». Appliqué commit `e295710`.

**Why :** F4GLD juge ces mots indignes du vocabulaire radioamateur. J'ai signalé — et il a maintenu — que ce sont les termes OFFICIELS de POTA/SOTA/WWFF, employés par leurs règlements et leurs API (`api.pota.app` renvoie littéralement « activator »). Sa décision prime : c'est son logiciel et sa langue.

**How to apply :**
- Vocabulaire retenu : `STATIONS X EN DIRECT` (pas « activateurs »), `Aucun trafic X signalé`, `N stations`, `EXPÉDITION / PORTABLE`, `TRAFIC EN PORTABLE (POTA/SOTA/…)`, `MA RÉFÉRENCE`, « Tu **opères depuis** une référence ». Les trois formulations proposées (stations / trafic / expédition) ont été validées : choisir la mieux adaptée au contexte.
- **Seulement le FRANÇAIS VISIBLE.** L'anglais et l'allemand gardent « activation »/« Aktivierung » (termes officiels dans ces langues). Les identifiants de code (`activation_program`, `my_activation_ref`, `logx_activation.py`, `applyActivationMode`) restent : jamais vus, et les renommer imposerait de migrer config et sauvegardes déjà sur disque.
- **Deux homonymes à ne JAMAIS remplacer** : « activation (SCOREBOARD EN DIRECT) » = mise en marche d'une fonction ; « désactivation volontaire » (logx_logbook.js) = arrêt d'un enregistreur. Un sed global les avale.
- Garde-fou en place : `concours/tests/test_vocabulaire_portable.py`.

**PIÈGE STRUCTUREL, valable pour tout renommage de texte dans ce projet :** les clés de `logx_i18n.js` **sont** les phrases françaises. Changer un libellé sans changer sa clé ne casse rien de visible en français mais fait décrocher les **7 traductions** en silence. Toujours déplacer les deux ensemble, puis vérifier que chaque phrase de page est encore une clé. Voir aussi [[piege-faux-dom-stub-et-passes-paires]] pour les autres pannes i18n invisibles.
