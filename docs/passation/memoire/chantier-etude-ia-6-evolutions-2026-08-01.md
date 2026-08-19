---
name: chantier-etude-ia-6-evolutions-2026-08-01
description: "Fin de l'étude IA : 6 évolutions livrées (audit log, nudges, voix, agent qui agit, stratégie FT8, niveau) — fusion f27e3c4 (01/08/2026)"
metadata:
  node_type: memory
  type: project
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-08-01T20:17:45.284Z
---

Suite de [[chantier-etude-ia-3-evolutions-2026-08-01]] : F4GLD a fait dérouler
TOUT le classement du jury (« continue », « continu N », « pousser »). Après le
top-3 (streaming/hors-ligne/garde-fou zone, fusionné `5c17e23`), les six
restantes fusionnées `f27e3c4`, CI verte. **Suite 3287 → 3348 tests (+61 sur la
session entière).** L'étude est INTÉGRALEMENT réalisée ; les propositions
« écartées » l'ont été à raison (dictée STT cloud = morte hors-ligne, etc.).

**#2 AUDIT IA DU LOG** (`logx_validator.build_audit_input`/`normalize_audit_findings`,
`/log/audit` job de fond) : l'IA relit le log scopé et rend des constats au
FORMAT de validate_log ({level,msg,id}), fusionnés SOUS le VÉRIFIER déterministe
avec ses boutons Corriger/Supprimer. **Piège central : chaque constat DOIT porter
un qso_id du lot envoyé, sinon les boutons n'ont pas de cible** — filtrage strict.

**#5 NUDGES ÉVÉNEMENTIELS** (`logx_coach.coach_nudge`, `/coach/state?nudges=1`) :
UNE phrase d'action en toast dans la barre d'état (déjà pollée, zéro boucle en
plus) quand un événement paie — entité rare spottée (le spot PROUVE la bande
ouverte) › rythme effondré › silence. Débounce dur ≥5 min + dédup par signature ;
calculé SEULEMENT si `?nudges=1` (station sans l'option ne paie rien).

**#6 LECTURE VOCALE HORS-LIGNE** (`window.rcSpeak` dans logx_statusbar.js) : voix
SAPI **localService** (100 % hors-ligne, jamais la radio), 1re phrase seulement,
`voiceschanged` géré, regex SIMPLES (pas de lookbehind/`\p{}`/flag u — piège
py_mini_racer sans ICU). **Défaut trouvé en banc : affecter u.voice dans un try
À PART, sinon un setter capricieux tue TOUTE la lecture.**

**#7 L'AGENT QUI AGIT** (`call_llm_actions` tool-use single-shot, `/agent/act`) :
outils `pointer_rotor`/`qsy_radio` — le serveur n'exécute JAMAIS, il renvoie une
`pending_action` (validée : azimut 0-360, freq>0) affichée en CARTE de
confirmation ; le CLIC appelle l'endpoint EXISTANT (/rotor/point, /rig/qsy),
anti-double-clic. Non-Anthropic → texte seul. **Le piège maladie « câbler
vraiment la carte » traité de front (composant réel, testé navigateur).**

**#8 STRATÉGIE PILE-UP FT8** (`logx_wsjtx._decode_series`/`decode_history`,
`/wsjtx/strategy`) : **le piège mémoire — `_decodes` n'a qu'un last_seen PLAT,
donc AJOUT d'un ring buffer par indicatif, borné DEUX FOIS (deque maxlen + purge
synchronisée) pour tenir 360 h.** L'IA lit la série des décodes d'une DX et
conseille où/quand appeler ; purement consultatif, jamais d'émission ; la modale
montre les décodes bruts (anti-hallucination).

**#21 NIVEAU débutant/confirmé/expert** (`window.rcSkillDirective`) : directive
calquée sur `rcLangDirective`, `rcAiDirectives()` combine langue+niveau aux 2
points d'injection du prompt (chat + chasse assistée ; coach/débrief héritent via
send()). Confirmé = défaut = aucune directive.

**PATRONS RÉUTILISÉS toute la session** : le job de fond asynchrone (thread daemon
+ `/…/state` polling, jamais de LLM dans le thread HTTP) sert #2/#7/#8 ; le
streaming SSE (#1) sert le chat/coach/débrief. **6 défauts réels au total
débusqués UNIQUEMENT en navigateur** (banc isolé qui rejoue le contrat serveur +
vraies fonctions client copiées, sans toucher au serveur 8080 de l'utilisateur) —
voir [[piege-verifier-sur-donnees-reelles]]. Technique de banc éprouvée :
`.blur()` ne déclenche `onblur` que si l'élément a eu le focus ; les objets voix
simulés cassent le setter natif ; un mock qui ne décode pas `%3A` fausse une
signature — appeler les fonctions directement plutôt que simuler les événements.
