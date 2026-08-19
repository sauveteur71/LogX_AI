---
name: chantier-etude-ia-3-evolutions-2026-08-01
description: "Étude IA reprise → 3 évolutions livrées (streaming SSE, chat hors-ligne, garde-fou zone CQ), fusion 5c17e23 (01/08/2026)"
metadata:
  node_type: memory
  type: project
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-08-01T16:39:15.215Z
---

F4GLD : « reprends l'étude IA et sers-t'en pour faire évoluer l'IA ». Un Workflow
(24 propositions → jury impact/faisabilité/nouveauté → classement) a produit un
top-3 net, livré un à un (« passe à la suite », « continu sur 3 », « pousser »).
Fusionné `5c17e23`, CI verte, suite 3287 → **3313 tests** (+26). Voir l'étude
initiale [[chantier-etude-ia-cinq-points-2026-08-01]].

**#1 STREAMING SSE — le verrou de voûte.** Tout l'IA (`call_llm`, `/proxy/ai`,
`call_ai_structured`) faisait `urlopen()+read()` COMPLET (timeout 120-180 s) : le
chat, le coach et le débrief étaient un mur figé, donc l'IA était inexploitable
EN TRAFIC. `call_llm_stream()` streame (Anthropic + 4 OpenAI-compat en natif,
Gemini en repli non-streamé) ; le thread de fond `/agent/analyze` remplit
`_agent_analyses[aid]['reply']` au fil de l'eau ; nouvel endpoint SSE
`/agent/analyze/stream` qui TAILE ce buffer (il ne TIENT pas la génération, qui
survit au changement d'onglet). **PIÈGE 360 h majeur : un thread OS par connexion
sur ThreadingHTTPServer — un flux SSE qui ne finit jamais = fuite garantie.**
Garde-fous : la boucle se termine TOUJOURS (fin d'analyse / client parti / deadline
dure 150 s), heartbeat `: ping` (socket timeout 30 s aussi en écriture via
`StreamRequestHandler.setup`), et `retry: 3600000` en tête = backstop
anti-reconnexion EventSource (le client ferme sur done/failed). Event nommé
`failed`, PAS `error` (collision avec `es.onerror`).

**#4 CHAT HORS-LIGNE — la raison d'être en expédition.** Sans internet, tout le
chat mourait sur « ❌ clé API » pile pendant les 15 jours. `/coach/answer`
réutilise `build_coach_state` (aucune logique de score recopiée) + `answer_text`
(ZÉRO LLM) : score, mults + répartition par bande, prop/openings, résumé.
« Spots » répond honnêtement qu'il faut le réseau. Les boutons rapides portent un
TOPIC EXPLICITE (pas de reniflage de chaîne) ; le repli est branché aux 3 sorties
(SSE `failed`, polling, catch POST). Clés i18n FR+EN (autres langues → FR par
contrat du module).

**#3 GARDE-FOU « MULT FANTÔME » — protéger le score À LA SAISIE.** En CQ WW une
zone bustée compte comme mult puis est retirée au checking = pénalité nette.
`logx_dxcc.verifier_zone_cq(call, valeur)` compare la zone saisie à cty.dat via
`lookup()` (dérogations `(zz)` + `=CALL` honorées — JAMAIS de table de zones en
dur). `match=None` sur inconnu/vide → on ne crie pas sur ce qu'on ne sait pas
vérifier. Endpoint déterministe `/exchange/check` ; l'IA ne tranche l'ambigu
(/P, /MM, pays à cheval : USA 3-5, Russie 16-23) qu'à la demande via `/proxy/ai`.
Conditionné à `currentExchange.check==='cq_zone'` (CQ_WW_SSB/CW seulement) : zéro
bruit ailleurs.

**LEÇON QUI SE RÉPÈTE — le navigateur trouve ce que la suite verte ne voit pas.**
Deux défauts réels attrapés SEULEMENT en test navigateur (bancs isolés, sans
toucher au serveur 8080 de l'utilisateur), pas par les 3313 tests :
1. la bulle d'ERREUR gardait la classe `streaming` → curseur ▌ clignotant sous un
   message d'échec (branches sans partiel ne passaient pas par `finalizeAgentReply`) ;
2. une espace fine insécable **U+202F** s'était glissée dans `'%s MHz'` (autocorrection ?)
   — invisible à l'œil, cassait l'assertion. Voir [[piege-verifier-sur-donnees-reelles]].
Technique de banc : un mini http.server qui rejoue EXACTEMENT le contrat serveur
(format SSE réel, /coach/answer, /exchange/check) + les VRAIES fonctions client
copiées verbatim → on teste la logib client dans un vrai navigateur sans la stack
complète. `.blur()` ne déclenche `onblur` que si l'élément a eu le focus (appeler
la fonction directement en test).
