---
name: chantier-so2r-phase0-1-2026-08-07
description: SO2R Phase 0 (verrou TX + focus fiabilisé sur 8 endpoints) + Phase 1 (MVP OmniRig radio 2) livrés — 4 bugs critiques trouvés et corrigés par revue adversariale avant fusion
metadata: 
  node_type: memory
  type: project
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-08-07T11:03:29.022Z
---

Chantier lancé après une découverte critique : `docs/COMPARATIF_CONCURRENTS.md`
et le contenu groups.io affirmaient à tort « SO2R : Non (pas encore) » pour
LogX AI, alors que `logx_so2r.py` (focus logiciel + protocole OTRSP) existait
déjà depuis `eb94008` (27/07/2026) — corrigé en même temps que ce chantier
(`eff9bfa`). Root cause : affirmation écrite de mémoire/impression générale
sans grepper le code avant publication. Une étude commandée par F4GLD
(« étude/plan d'abord ») a produit `docs/ETUDE_SO2R.md` (audit + plan 5
phases), dont les agents ont eux-mêmes trouvé le module existant — c'est ce
qui a révélé l'erreur.

**Décisions F4GLD (AskUserQuestion)** : Phase 0+1 directement (pas de
validation intermédiaire), avertissement texte seul dans la doc (pas de case
à cocher « je confirme avoir des filtres passe-bande »), pas de boîtier OTRSP
disponible pour l'instant (Phase 3 matérielle reste non testée terrain).

**Livré** (`1df1ad2`, merge sur main) :
- Phase 0 : `so2r.config_radio_active()` câblé sur 8 endpoints qui
  l'ignoraient encore (`/rig/state`, `/rig/scope_*`, `/rig/tci_spectrum_*`,
  `/hardware/state`, `/rig/voice`, `/voice/play`) — avant, basculer le focus
  (Ctrl+Espace) laissait ces endpoints afficher/piloter la radio 1.
- Verrou logiciel d'exclusivité TX (`verrouiller_tx`/`deverrouiller_tx`/
  `tx_actif`, timeout 120s) — équivalent du « First One Wins » de N1MM+.
- Phase 1 : remap `omnirig_rig_num`, UI `cat2_mode` (natif/OmniRig) remplace
  le `'native'` figé en dur, nouveau champ RIG OMNIRIG radio 2.

**Revue adversariale (workflow, 3 agents indépendants + vérif adversariale,
15 agents au total) AVANT fusion : 6 constats bruts, 4 bugs réels confirmés**
— tous corrigés avant le commit, jamais poussés sur main :
1. **Le verrou TX n'était JAMAIS relâché sur un échec `/rig/cw`** (ex. Icom
   natif sans WinKeyer, qui refuse toujours le CW) — seul `/rig/stop`
   explicite ou le timeout de 120s le levait. Comme le verrou se
   RÉARME/rafraîchit à chaque appel de la MÊME radio, un run CQ normal (macro
   répétée < 120s d'intervalle) bloquait l'AUTRE radio indéfiniment, sans
   qu'aucune émission réelle n'ait eu lieu. Corrigé par un helper `_reponse_cw()`
   qui relâche le verrou sur tout `res.get('ok') is False`, câblé sur les 6
   chemins d'échec de ce bloc (WinKeyer, natif, flrig, omnirig/flex/
   icomremote, TCI/rigctld, CAT désactivée).
2. **`/rig/stop` relâchait le verrou de la radio ayant le focus AU MOMENT du
   stop**, pas celle qui l'avait réellement armé — un Ctrl+Espace entre
   l'envoi CW (fire-and-forget) et le clic sur ■ STOP laissait le verrou
   d'origine orphelin. Corrigé : `deverrouiller_tx(so2r.tx_actif()['radio'])`
   (relâche qui détient VRAIMENT le verrou, pas qui a le focus courant).
3. **Fenêtre TOCTOU** : `cfg_snap` (config réellement pilotée) et
   `radio_active` (radio protégée par le verrou) venaient de deux lectures
   INDÉPENDANTES de `so2r.focus()` — un `/so2r/focus` concurrent entre les
   deux pouvait faire correspondre le verrou à une radio différente de celle
   réellement commandée. Corrigé : `radio_active` lu UNE SEULE FOIS par
   requête, `config_radio_active(cfg, radio=radio_active)` accepte
   maintenant un paramètre explicite au lieu de relire le focus en interne.
4. **`omnirig_enabled` (garde-fou interne de `logx_omnirig.py`, séparé de
   `cat_mode`) n'était PAS remappé pour la radio 2** — calculé côté JS
   UNIQUEMENT depuis `cat_enabled`/`cat_mode` de la radio 1. Résultat :
   radio 1 native + radio 2 OmniRig (**exactement la config que l'UI elle-même
   recommande** dans son texte d'aide) cassait silencieusement TOUT pilotage
   OmniRig de la radio 2 avec « Pilotage OmniRig désactivé (CONFIG) ». Corrigé
   en recalculant `omnirig_enabled` dans `config_radio_active()` à partir du
   `cat_mode`/`cat_enabled` déjà remappés.

**Piège de méthode, trouvé en écrivant les tests de vérification** : les 4
tests structurels existants (`test_rig_cw_verrouille_avant_denvoyer` etc.)
ne détectaient AUCUN de ces bugs — ils vérifiaient juste la PRÉSENCE de
`verrouiller_tx`/`deverrouiller_tx` quelque part dans le bloc source, jamais
qu'ils soient sur le MÊME chemin d'exécution. Remplacés par 5 vrais tests
HTTP de bout en bout (`ThreadingHTTPServer` + `urllib`, même harnais que
`tests/test_cat_proprietaire_dispatch.py`) qui reproduisent chacun des bugs
ci-dessus. **Piège trouvé dans mon PROPRE premier jet** : le test du bug #4
mockait `omnirig.set_ptt` directement (la fonction qui CONTIENT le garde-fou
`omnirig_enabled`) — un test qui aurait donc passé même SANS le correctif.
Détecté en désactivant temporairement le correctif et en confirmant que le
test échoue bien (`assert (400 == 200)`) avant de le restaurer — corrigé en
mockant `omnirig._com_call` (la couche COM en dessous) à la place, pour que
le VRAI garde-fou soit exercé. Réflexe pour toute suite : avant de considérer
un test de non-régression fiable, vérifier qu'il échoue réellement sans le
correctif — un mock trop haut dans la pile peut contourner exactement ce
qu'on croit tester.

Voir aussi [[chantier-cat-plug-and-play-2026-08]] (même piège de méthode :
« zéro bug trouvé par les tests » ne veut rien dire si les tests ne peuvent
techniquement pas voir le bug) et [[piege-couleur-data-vs-theme]] pour
d'autres cas où une vérification apparemment suffisante ratait le vrai
défaut.
