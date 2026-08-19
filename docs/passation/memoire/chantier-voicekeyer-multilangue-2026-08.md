---
name: chantier-voicekeyer-multilangue-2026-08
description: "Keyer vocal — connecteur {DE} localisé + système de nombres allemand complet, indicatif DL parle désormais en allemand (04/08/2026)"
metadata: 
  node_type: memory
  type: project
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-08-04T08:38:45.488Z
---

Suite directe de [[chantier-voicekeyer-piper-local-2026-08]], même journée
(04/08/2026), branche `fix/voicekeyer-connecteur-de-from-localise`.

## Deux bugs/demandes distincts, même session de test

1. **Bug "de" figé** : en testant le keyer vocal avec un indicatif anglais
   (W1AW), F4GLD a repéré que le mot **"de"** (connecteur entre {CALL} et
   {MYCALL}) restait toujours en français, même quand le reste du message
   passait en anglais — hardcodé en dur dans le template du bouton "Tester"
   de CONFIG (`'{CALL} de {MYCALL}, {RST_SENT}'`), jamais localisé comme le
   reste. Fix : nouveau placeholder `{DE}` dans `expand_voice_text()`.

2. **Demande d'extension** : *« si je tape un indicatif allemand DL... il
   faut passer le message en allemand [...] adapter le message en fonction
   de l'indicatif saisi »*. Avant ce lot, `lang_for_call()` ne connaissait
   que fr/en (binaire) — le mot de remerciement de clôture ({TNX}) était
   déjà multilingue (merci/arigato/danke/grazie/gracias/obrigado/dank u)
   mais les NOMBRES (RST, séries) restaient toujours en anglais pour tout
   sauf le français.

## Mise à jour (même jour) : "ajoute toute les langues"

F4GLD a confirmé vouloir TOUTES les langues, pas juste l'allemand — et a
noté un vrai piège en passant : *« attention nine se prononce
phonétiquement /naɪn/ »*. Complété dans la foulée (commit `f2f9aa0`) :
**it/es/pt/nl/ja** ont maintenant, comme fr/de, un système de nombres
0-9999 complet ET un connecteur {DE} localisé (da/de/de/van/kara). Les 7
langues de `_LANG_AND_THANKS_BY_COUNTRY` sont donc toutes couvertes de bout
en bout (nombres + connecteur + remerciement) ; 'en' reste le repli par
défaut pour tout pays non reconnu.

Chaque langue a son propre piège linguistique réel (pas de règle générique
qui aurait suffi à toutes) :
- **Italien** : élision devant 1/8 (ventuno/ventotto), accent sur les
  combinaisons en 3 (ventitré).
- **Espagnol** : deux régimes dans la même langue — 16-29 fusionnés
  (dieciséis), 30+ garde « y » + espaces (cincuenta y nueve). Centaines
  irrégulières (quinientos, novecientos).
- **Portugais** : le séparateur avec les milliers dépend de la VALEUR, pas
  seulement de la langue (mil e um, mais mil duzentos sans « e »).
- **Néerlandais** : tréma orthographique obligatoire sur « tweeën-»/
  « drieën- » (2 et 3 finissent par une voyelle) — bug attrapé et corrigé
  AVANT de committer, pas après (première version écrivait « tweeentwintig »
  sans tréma).
- **Japonais (rōmaji)** : changements euphoniques irréguliers aux
  centaines/milliers (san+hyaku -> sanbyaku, hachi+sen -> hassen) —
  encodés en table de correspondance, pas dérivés d'une règle générale.

## Deuxième revirement (même jour) : les rapports restent TOUJOURS en anglais

Après avoir vu le résultat, F4GLD a tranché dans l'autre sens pour les
RAPPORTS spécifiquement : *« pour les rapports 59 ou 58 ou 44 toujours
passer ces chiffres en anglais c'est mieux et plus simple »*. Décision
finale (commit `6d23ef3`) : `{RST_SENT}`/`{RST_RCVD}`/`{NR}` sont
désormais codés en dur sur `lang='en'`, quelle que soit la langue dérivée
de l'indicatif — l'ÉCHANGE (donnée de concours) reste simple et sans
ambiguïté. En revanche `{DE}` (connecteur) et `{TNX}`/`{73}` (clôture "73 +
remerciement") restent localisés : ce n'est pas une donnée d'échange, juste
une formule de politesse en fin de message, où le risque d'ambiguïté est
nul. Rien du travail des 7 systèmes de nombres (fr/de/it/es/pt/nl/ja) n'est
perdu : `number_to_words()`/`spell_number()` restent utilisés tels quels
par `{73}`/`{TNX}`.

Résultat final vérifié : `DL1AA <-> F4GLD, RST 59` -> *"... von Foxtrot
Four Golf Lima Delta, **fifty-nine** dreiundsiebzig danke"* — connecteur et
clôture allemands, rapport en anglais.

### Le piège "nine" : documenté, PAS "corrigé" (aucun correctif possible ici)

La remarque de F4GLD pointe une limite réelle et non résolue : le texte
envoyé au moteur TTS est un bloc UNIQUE, sans balisage SSML par mot. Si une
voix allemande/japonaise/etc. est choisie pour prononcer les nombres, les
mots anglais internationaux mélangés dans la MÊME phrase (alphabet OACI,
« Nine », « stroke ») risquent d'être lus avec les règles de prononciation
de cette langue plutôt que l'anglais correct. Ce n'est PAS un bug de ce
lot — c'est une limitation de pyttsx3/SAPI5/Piper en usage texte->audio
simple, qui existait déjà avant (même en français). Documentée en toutes
lettres dans le docstring du module plutôt que de prétendre l'avoir réglée
— un vrai correctif demanderait du SSML par mot (hors périmètre actuel).

## Piège évité en refactorisant

`thanks_word()` avait une politique DÉLIBÉRÉMENT plus prudente que
`lang_for_call()` : un pays NON identifié ne dit AUCUN mot de remerciement
improvisé (jamais "thanks" par défaut), alors que `lang_for_call()` doit
bien choisir UNE langue pour les nombres et retombe donc largement sur 'en'.
En fusionnant les deux tables sources (`_LANG_AND_THANKS_BY_COUNTRY`), il
fallait garder cette asymétrie : `lang_for_call()` a un `return 'en'` en
sortie de boucle, `thanks_word()` garde son `_ENGLISH_ENTITIES` explicite +
retourne `''` sinon — les fusionner naïvement en une seule fonction aurait
fait dire "thanks" à un pays inconnu, changeant un comportement testé et
voulu (`test_thanks_word_par_pays` : Mongolie -> '').
