# Spécification de l'agent IA — livrable C

Rédigé le 21/08/2026. Cadré par la décision de F4GLD du même jour : *« Dépendance à une API Cloud (Anthropic) par défaut, avec un mode dégradé hors-ligne — le mode hors-ligne ne doit servir que de filet de sécurité en plein milieu de nulle part ou en cas de coupure réseau. »*

## Raisonnement

### 1. Inventaire — ce que le code fait déjà (vérifié le 21/08, pas supposé)

L'architecture existante est plus avancée que ce à quoi un audit de haut niveau laisse penser. Trois éléments vérifiés directement dans `logx_http.py`/`logx_coach.py`/`logx_carte.html` :

**a) Séparation déterministe/LLM réellement tenue.** `build_coach_state` (`logx_coach.py:815`) — l'horloge de concours, le rythme QSO/h, le plan de bande pondéré, les diagnostics RUN/S&P — ne contient **aucun appel LLM**. Le bouton conversationnel (🧠 COACH, `/proxy/ai`) est une couche PROSE ajoutée par-dessus des données déjà calculées, jamais l'inverse. Confirmé par grep : zéro occurrence de `call_llm`/`add_qso_to_log` dans le moteur du coach.

**b) Six fournisseurs déjà supportés, choix libre de l'opérateur (BYOK).** `logx_utils.py:75-90` : Anthropic, Gemini, OpenAI, Mistral, xAI, DeepSeek — chacun avec son modèle par défaut. Le logiciel ne force aucun fournisseur ; c'est une clé API que l'opérateur configure et paie lui-même (cohérent avec la contrainte « gratuit, autonome » — le LOGICIEL est gratuit, l'usage cloud optionnel a son propre coût, assumé par l'opérateur qui le choisit).

**c) Function calling DÉJÀ implémenté pour l'action physique — pattern « propose, n'exécute jamais ».** `logx_http.py:391-459` (`ACTION_TOOLS`, `call_llm_actions`) : l'agent peut proposer `pointer_rotor` ou `qsy_radio` via le tool-use natif Anthropic. Le serveur **n'exécute jamais l'action lui-même** — il renvoie la proposition, et c'est le clic de confirmation de l'opérateur côté client qui appelle l'endpoint réel (`/rotor/point`, `/rig/qsy`). Single-shot, pas de boucle agentique. Réservé à Anthropic ; les 5 autres fournisseurs retombent sur une réponse texte simple (`action: None`), le chat ne casse jamais.

**d) Dégradation gracieuse déjà câblée.** `logx_carte.html:1993-2018` : `_setAiOffline()` bascule l'UI sur un message « IA indisponible — réponses calculées localement » dès qu'un appel échoue OU que `navigator.onLine` passe à `false` (écouteurs `online`/`offline` natifs du navigateur) — donc déjà réactif à une vraie coupure réseau, pas seulement à une erreur de clé API.

**e) Endpoints existants pertinents pour ce livrable** : `/coach/state` (déterministe, poll 60s), `/coach/debrief` (analyse post-concours, `build_debrief`), `/agent/analyze` (analyse conversationnelle **asynchrone**, tourne dans un thread serveur et survit à un changement de page — `_agent_analyses` + polling `/agent/analyze/state`), `/proxy/ai` (chat direct).

### 2. Analyse comparative

Aucun concurrent étudié dans l'analyse du 10/08 (Wavelog, GridTracker2, AllMySat, SmartLogger, World Radio League, Log4OM) n'a d'assistant IA intégré — c'est déjà noté comme différenciateur confirmé, pas juste perçu. La question n'est donc pas de rattraper un concurrent sur ce point, mais de savoir si l'architecture ACTUELLE (context-stuffing pour la lecture, tool-use pour l'action physique seulement) suffit à tenir la promesse du positionnement du 21/08 (« carnet de l'opérateur mobile et exigeant »).

### 3. Diagnostic — deux écarts réels, pas dix

**Écart 1 : la lecture (log, plan de bandes, propagation, spots) n'est pas exposée en function calling, contrairement à ce que demande explicitement le cadrage de ce livrable.** Aujourd'hui `do_refresh`/`build_scoring_context` assemblent un GROS bloc de contexte injecté d'un coup dans le prompt système, à chaque appel — pas d'appel à la demande. Ce n'est pas un bug (ça marche, c'est simple, et ça évite une boucle agentique multi-tours plus complexe à sécuriser) mais ça a un coût réel : le contexte est envoyé en entier même quand la question ne porte que sur un point précis (ex. « tu me confirmes bien que F5ABC est un nouveau département ? » n'a pas besoin de tout le plan de bande).

**Écart 2 : « mode hors-ligne » aujourd'hui ne veut PAS dire « IA qui fonctionne sans réseau »** — ça veut dire « le logiciel ne casse pas, la partie déterministe continue, la partie conversationnelle s'éteint proprement avec un message clair ». C'est une dégradation gracieuse réelle et déjà bonne, mais ce n'est pas un filet de sécurité qui vaut d'appel LLM en pleine expédition sans réseau. La décision de F4GLD du 21/08 emploie littéralement « filet de sécurité » — il faut trancher ce que ce mot recouvre AVANT de coder quoi que ce soit (voir question ouverte, section Décision).

### 4. Options

**Pour l'écart 1 (lecture en function calling) :**
- *Option A — tout migrer vers du tool-use multi-tours.* Le plus proche de la demande littérale, mais gros chantier (boucle agentique, gestion des tours, coût par appel qui grimpe si mal borné) pour un projet porté par une seule personne.
- *Option B — function calling CIBLÉ sur 3-4 requêtes ponctuelles seulement* (ex. `lire_historique_station(call)`, `lire_propagation(bande)`), le contexte permanent (horloge, plan de bande courant) restant injecté comme aujourd'hui parce qu'il est presque toujours utile.
- *Option C — ne rien changer, garder le context-stuffing.* Simple, déjà fiable, mais ne satisfait pas la lettre du cahier des charges et coûte plus de jetons par appel qu'il ne faudrait.

**Pour l'écart 2 (mode hors-ligne réel) :**
- *Option A — modèle local embarqué* (type llama.cpp/gguf, quelques Go). Répond littéralement à « ça continue de répondre sans réseau », mais alourdit énormément le paquet PyInstaller (aujourd'hui ~57 Mo) et la maintenance (choix du modèle, mises à jour, qualité très inférieure au cloud pour un usage « pointu » comme demandé dans le prompt d'origine).
- *Option B — pas de génération de texte hors ligne, mais un filet de sécurité RICHE* : quand le réseau tombe, l'agent bascule sur des réponses **template + données déterministes** (ex. « Pas de réseau. D'après le plan de bande calculé localement : 20m ouvert vers l'Asie, silence radio depuis 12 min. » — pas de prose IA, mais une réponse utile construite sans appel réseau). C'est un renforcement de ce qui existe déjà (`_setAiOffline`), pas une nouvelle brique.

### 5. Décision

Écart 1 → **Option B** (function calling ciblé, pas une refonte complète) : cohérent avec « pas de sur-ingénierie » (règle 5 du cadrage), et le contexte permanent actuel a déjà fait ses preuves.

Écart 2 → **TRANCHÉ PAR F4GLD LE 21/08/2026 : Option B, sans hésitation.** Pas de modèle local embarqué — poids de paquet inutile, qualité forcément au rabais, CPU consommé pour rien au moment précis (expédition, coupure) où l'opérateur a besoin d'un carnet ultra-fiable et réactif, pas d'une IA dégradée. Le statu quo (`_setAiOffline` + écoute `online`/`offline`) est validé comme la bonne architecture — il reste à l'ENRICHIR (pas à le remplacer) : quand la prose IA s'éteint, basculer sur un **mode assistant textuel de base à messages d'état pré-formatés**, construits uniquement à partir des données déterministes déjà calculées localement (coach, plan de bande, propagation) — pas de génération de texte, des gabarits remplis. Voir la section Recommandations ci-dessous pour la mise en œuvre concrète.

### 6. Vérification (pour la mise en œuvre, une fois validée)

- Function calling ciblé : mesurer le volume de jetons envoyés avant/après sur un scénario réel (question ponctuelle sur un indicatif) — l'option B doit réduire le coût par appel, sinon elle n'apporte rien.
- Mode dégradé renforcé : couper le réseau volontairement (mode avion) pendant une session simulée, vérifier qu'une réponse utile (pas une erreur brute) sort toujours du chat.

---

## Cas d'usage par profil (ce que l'agent doit réellement faire, pas un gadget conversationnel)

| Cas d'usage | Profils | État aujourd'hui |
|---|---|---|
| Aide au trafic en direct (RUN/S&P/CHANGE) | Concours, DXeur | **Fait** — `run_sp_recommendation`, déterministe |
| Suggestion de bande/heure/direction | Tous | **Fait** — `band_plan` pondéré + `logx_paths.py` (ouvertures par région) |
| Décodage d'un log douteux | Tous | **Fait, déterministe** — `logx_validator.py`/VÉRIFIER ; pas de couche IA dessus aujourd'hui, pourrait en gagner une pour EXPLIQUER un constat en langage naturel (pas pour le calculer) |
| Préparation d'activation (POTA/SOTA) | Activateur | **Partiel** — spots temps réel déjà remontés (`logx_pota.py`, `logx_sota.py`), pas de préparation IA proactive avant le départ (ex. « voici les fenêtres de propagation probables pour ce sommet, cette date ») |
| Coaching du novice | Novice | **Partiel** — hints du coach existent, mais pas calibrés par niveau déclaré/déduit de l'opérateur |
| Analyse post-concours | Concours | **Fait** — `build_debrief` |

Le vrai trou n'est donc pas « il manque un agent IA » — l'essentiel existe — mais deux cas précis (préparation d'activation proactive, coaching calibré par niveau) qui pourraient entrer dans une future feuille de route, PAS ce document.

## Architecture (état + ce qui ne change pas)

- **Cloud par défaut (Anthropic), BYOK, 5 autres fournisseurs en repli au choix de l'opérateur** — déjà en place, décision du 21/08 confirme le statu quo plutôt que d'en changer.
- **Séparation stricte déterministe/LLM** — ne jamais l'affaiblir. Le coach, le scoring, la propagation restent 100 % calculables sans réseau ; le LLM n'ajoute QUE de la prose et des propositions d'action.
- **Tool-use pour l'action physique reste single-shot, propose-only** — ne jamais faire évoluer ça vers une exécution automatique sans confirmation humaine, quel que soit le gain de fluidité promis.

## Outils exposés à l'agent

- **Déjà exposés (action, propose-only) :** `pointer_rotor`, `qsy_radio`.
- **À exposer en lecture ciblée (option B ci-dessus, si validée) :** interrogation ponctuelle de l'historique d'un indicatif, de la propagation d'une bande précise, de l'état d'un spot — en complément du contexte permanent actuel, pas en remplacement.

## Garde-fous (existants à documenter, pas à réinventer)

1. **L'agent ne modifie jamais un QSO sans confirmation** — déjà vrai : aucun chemin LLM n'appelle `add_qso_to_log`. À VERROUILLER par un test de non-régression dédié (grep automatisé qui échoue si un futur commit introduit ce lien) plutôt que de compter sur la vigilance humaine.
2. **L'agent ne fabrique jamais une donnée réglementaire** — tenu par construction : les valeurs de plan de bandes/contraintes viennent de modules déterministes sourcés (`logx_bandplan_vhf.py`, `logx_paths.py`), jamais générées par le LLM lui-même. À vérifier : le prompt système interdit-il EXPLICITEMENT au LLM d'inventer une fréquence/un seuil s'il n'est pas dans le contexte fourni ? Point à contrôler dans `logx_prompts.py`, non fait dans cette session.
3. **L'agent indique ses sources** — partiellement tenu (le contexte injecté porte déjà des explications sourcées, ex. les hints du coach) ; pas de garantie que le LLM les cite systématiquement dans sa PROSE. À renforcer par une consigne explicite dans le prompt système si ce n'est pas déjà fait — à vérifier avant de considérer ce point acquis.
4. **Dégradation gracieuse** — déjà en place (`_setAiOffline`), à renforcer côté contenu (option B de l'écart 2) si F4GLD tranche dans ce sens.

## Recommandations concrètes (mode dégradé enrichi — décision du 21/08 validée)

Aucune de ces propositions n'a été codée dans cette session — à traiter comme un chantier « structurant » de la feuille de route (`docs/FEUILLE_DE_ROUTE.md`), pas en vague 1.

1. **Étendre `_setAiOffline()` (`logx_carte.html`) pour qu'il produise un message d'état construit, pas juste un texte fixe.** Aujourd'hui : une seule chaîne statique (« IA indisponible — réponses calculées localement »). Cible : appeler une petite fonction côté client qui lit l'état déjà présent dans le DOM (résultat du dernier `/coach/state`, band_plan, run_sp) et compose 1-2 phrases gabarit (« Pas de réseau. D'après le plan de bande local : {meilleure_bande} ouvert, rythme {qso_h} QSO/h, silence depuis {minutes} min. »).
2. **Aucun appel réseau supplémentaire pour ce mode** — tout doit venir de données déjà rafraîchies par le polling déterministe existant (`/coach/state`, toutes les 60 s), jamais une tentative de contacter l'IA en boucle pendant une coupure (gaspillage de batterie/CPU en terrain, contraire à l'esprit de la décision).
3. **Réutiliser le même patron sur `logx_mobile.html`** (page terrain) si elle a un chat IA équivalent — à vérifier avant de coder, ne pas supposer qu'elle partage le même code que `logx_carte.html`.
4. **Test de vérification** : couper le réseau (mode avion ou `navigator.onLine` forcé à `false` en test), confirmer qu'un message construit et utile apparaît — pas une chaîne fixe, pas une erreur brute, pas de tentative réseau en boucle observable dans l'onglet réseau du navigateur.
