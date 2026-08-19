---
name: chantier-voicekeyer-synthese-multivoix-2026-08
description: "Keyer vocal — synthèse MULTI-VOIX (un moteur/une voix par segment de langue) pour corriger l'accent sur les segments internationaux, merge ef00549 (04/08/2026)"
metadata: 
  node_type: memory
  type: project
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-08-04T09:37:33.071Z
---

Suite directe de [[chantier-voicekeyer-multilangue-2026-08]], même journée
(04/08/2026), branche `feat/voicekeyer-multi-voix-segments`.

## Le piège "nine /naɪn/" n'était pas juste documenté — il était réel

Le lot précédent documentait la limite dans le docstring sans la corriger
("pas de correctif possible sans SSML par mot"). F4GLD a testé en vrai et
confirmé le symptôme concret : *« en français cela donne ... fifty-nine
[prononcé à la française] et je voudrais ... fɪfti naɪn »*. Le texte généré
était déjà correct (voir lot précédent) — c'est la PRONONCIATION audible qui
était fausse, parce qu'une seule voix SAPI/Piper lisait tout le message d'un
bloc, y compris les segments toujours-anglais (alphabet OACI, RST, "stroke")
avec l'accent de la voix locale choisie pour {DE}/{TNX}.

## Solution : découper le message en segments de langue, une synthèse par segment

`expand_voice_segments(template, ctx)` (nouveau, `logx_voicekeyer.py`) rend
`[(texte, langue), ...]` au lieu d'une chaîne unique — même table de
placeholders que `expand_voice_text()`, mais chaque valeur porte sa langue :
- `{CALL}`/`{MYCALL}`/`{RST_SENT}`/`{RST_RCVD}`/`{NR}` → toujours `'en'`.
- `{DE}`/`{TNX}`/`{73}` → la langue dérivée de l'indicatif.
- **Le texte littéral du template (hors placeholders) est toujours `'en'`**
  — décision délibérée, pas un oubli : la ponctuation/les mots collés au
  jargon international restent avec lui. Piège de test découvert en écrivant
  les tests : un ESPACE littéral entre deux placeholders `'fr'` casse la
  fusion de segments adjacents (`{TNX} {73}` → 3 segments, pas 1) parce que
  cet espace est lui-même un segment `'en'` intercalé — seul un template SANS
  aucun caractère entre deux placeholders de même langue fusionne
  (`{DE}{TNX}` → 1 segment).

`_voice_matches_lang(engine, voice_id, lang)` (nouveau) : détermine si la
voix SAPI fixée en CONFIG correspond réellement à la langue demandée pour CE
segment (recherche dans `engine.getProperty('voices')`, comparaison via
`_LANG_VOICE_HINTS` déjà existant). `synthesize_to_wav()` préfère maintenant
une voix qui MATCHE la langue du segment à la voix CONFIG si elles diffèrent
— avec repli sur la voix CONFIG si aucune voix locale de la langue demandée
n'est installée (mieux vaut une voix mal assortie qu'un silence).

`emettre_wav_multi()` (nouveau, généralise `emettre_wav()` qui devient une
fine couche de délégation à 1 seul fichier) : joue plusieurs WAV en séquence
sous UNE SEULE prise de PTT (pas un PTT par segment — un seul hold/release
pour tout le message). `send_voice_message()` reçoit un paramètre optionnel
`segments=None` : si fourni, synthétise chaque `(texte, langue)` séparément
puis délègue à `emettre_wav_multi()` ; si omis, comportement STRICTEMENT
identique à avant (rétrocompatibilité totale, aucun appelant existant à
migrer).

## Piège de test attrapé APRÈS le premier passage pytest

`test_rig_voice_http.py` avait deux `fake_send()` avec la signature FIGÉE
`(cfg, text, lang='', skip_ptt=False)` — sans le nouveau paramètre
`segments`. `/rig/voice` (logx_http.py) appelle désormais toujours
`send_voice_message(..., segments=...)`, donc ces fakes levaient
`TypeError: unexpected keyword argument 'segments'` → 500 réel côté serveur,
détecté seulement en lançant la suite COMPLÈTE (`pytest` sans filtre), pas
juste `test_voicekeyer.py`. Un rappel direct de [[piege-artefacts-perimes-verification]] :
une suite ciblée verte ne garantit rien sur le reste du repo — toujours
lancer la suite complète avant de committer un changement de signature
partagée entre plusieurs fichiers de test.

## Vérification réelle (pas juste unitaire)

Serveur isolé (copie scratch, port 8199, `.server_config.json` avec
`voicekeyer_enabled: true` — PAS `config.json`, qui est un fichier
d'exemple différent) : `/rig/voice` avec `skip_ptt: true` a rejoué EXACTEMENT
les deux cas du rapport de bug de F4GLD (indicatif DL, puis F4GLD/MM↔F4GLD/P)
et renvoyé `ok:true` avec le texte attendu, confirmant que le pipeline de
segmentation s'exécute de bout en bout sur la vraie machine (vrai moteur
SAPI local) sans lever d'exception — la synthèse audio par segment tourne
réellement, la prononciation par voix distincte ne peut plus être vérifiée
à l'oreille depuis ce siège, mais le code path est prouvé fonctionnel.
