# LogX AI — 3 decks prêts pour Claude Design

> **Comment s'en servir :** ouvre Claude Design (claude.ai), et pour chaque deck colle
> le bloc « PROMPT » ci-dessous. Il structurera les diapositives (texte + design), que
> tu pourras ensuite éditer et exporter en PPTX/PDF.

## Direction artistique commune (à rappeler à Claude Design)

- **Identité** : reprendre celle du logiciel LogX AI — HUD sombre « graphite & cuivre ».
- **Palette** : fond graphite très sombre `#131417` / panneaux `#1B1D21` / bordures `#34363A`,
  **accent cuivre `#E8964A`**, texte `#EAEDF5`, gris `#A6ADC2`, succès `#35D6A0`, alerte `#FFD166`, danger `#FF6B6B`.
  (Variante claire possible : fond `#ECEAE1`, accent `#8B4F1F`.)
- **Typo** : titres en **serif éditoriale** (type Fraunces/Iowan/Palatino) ; données & étiquettes en
  **monospace** (type Cascadia/JetBrains Mono) en MAJUSCULES espacées ; corps en sans-serif propre.
- **Style** : sobre, technique, « salle de contrôle ». Pastilles de couleur pour l'état. Éviter le
  cliché IA (dégradé violet, police Inter, tout centré, emojis en tête de section).
- **Message central, répété** : « **L'IA prépare. L'opérateur déclenche.** »

---

## DECK 1 — Public : RADIOAMATEURS (démo produit)

PROMPT :
« Crée un pitch deck de 9 diapositives pour *LogX AI*, un logiciel de log et de concours pour
radioamateurs, avec l'identité graphite & cuivre décrite. Ton concret, vocabulaire du hobby, zéro jargon
marketing. Diapositives : »

1. **Titre** — LogX AI · Le copilote de station qui comprend ton objectif — et te laisse la main.
   Sous-titre : log, concours, FT8/CW/SSB, pilotage radio + une IA discrète. *Visuel : spectre/waterfall.*
2. **Le principe** — L'IA prépare, l'opérateur déclenche. Schéma en 3 nœuds : *Décodage/spot → Proposition → Ton geste (tu émets)*. Note : aucune émission automatique.
3. **« Ce que l'IA remarque »** — un fil unique dans le LOGBOOK : opportunités, QSO à vérifier, gains du dernier QSO, indicatif à corriger. 3 couches : **FAIT / CALCUL / PROPOSITION**.
4. **Opportunités en direct** — les meilleures stations à travailler maintenant (nouveau pays, bande, carré, confirmation LoTW), classées par intérêt.
5. **Copilote FT8 / CW / SSB** — l'IA prépare le message suivant dans une barre de consentement ; tu confirmes, alors seulement ça part.
6. **Validation vivante + après-QSO** — doublons/erreurs repérés en continu ; après chaque contact, ce qu'il t'a apporté (nouveau pays/bande, à confirmer).
7. **Sécurité d'émission** — consentement unique (30 s), relu contre la radio réelle, Stop TX qui verrouille, journal d'audit. L'IA ne peut pas émettre à ta place.
8. **Autonomie & carnet** — marche sans internet (zone blanche) ; carnet unique toutes bandes/modes ; DXCC/WAZ/WAS, POTA/SOTA/IOTA, multi-poste radioclub.
9. **Clôture** — Un vrai copilote. Ta station reste la tienne.

---

## DECK 2 — Public : GRAND PUBLIC / INSTITUTIONNEL

PROMPT :
« Crée un deck de 8 diapositives présentant *LogX AI* à un public non spécialiste (club, partenaires,
presse, institutionnels), identité graphite & cuivre. Langage simple, pédagogique, mettre en avant
l'innovation IA responsable et l'accessibilité. Diapositives : »

1. **Titre** — LogX AI · Quand une IA aide le radioamateur — sans jamais décider à sa place.
2. **C'est quoi ?** — La radio d'amateur : des passionnés qui communiquent par ondes partout dans le monde, parfois là où plus rien ne marche. LogX AI modernise leur outil.
3. **Avant / Avec** — Avant : noter à la main, jongler entre outils. Avec : un copilote qui relie tout et vérifie.
4. **L'innovation : une IA copilote** — 3 étapes : *Elle observe → Elle propose → L'humain décide*. La bonne façon d'utiliser l'IA.
5. **Sécurité & confiance** — L'IA ne peut pas émettre à la place de l'humain : autorisation unique, vérifiée, annulable. La responsabilité reste à l'opérateur.
6. **Accessible** — On ne se perd pas : l'écran s'adapte à ce qu'on fait ; la richesse est disponible, jamais imposée.
7. **Autonome & collectif** — fonctionne sans internet ; radioclubs et expéditions partagent un carnet en temps réel.
8. **Clôture** — La technologie au service de l'humain, pas l'inverse. Une vision de l'IA transparente et respectueuse.

---

## DECK 3 — Public : TECHNIQUE / DÉVELOPPEURS

PROMPT :
« Crée un deck technique de 9 diapositives sur l'architecture de *LogX AI*, identité graphite & cuivre,
ton d'ingénierie précis. Inclure un schéma d'architecture, un tableau d'invariants et un extrait de
pseudo-code. Diapositives : »

1. **Titre** — LogX AI · Déterministe d'abord. LLM en appoint. Émission = geste humain.
2. **Le principe fondateur** — séparation stricte : ce qui *calcule* (100 % local, sans LLM) vs ce que le LLM *ajoute* (prose + propositions). Aucun chemin IA n'écrit un QSO ni n'émet.
3. **Schéma d'architecture** — 2 couloirs. **Déterministe/hors-ligne** : validation, scoring, priorité chasse, DXCC, distances, coach. **LLM/propose-only** : chat, stratégie pile-up, audit, analyse de règlement, plan de session, actions (tool-use). Pont : intention structurée → validée serveur → proposition cliquée.
4. **Consentement d'émission (fail-closed)** — pseudo-code `authorize_transmission` : jeton unique/30 s, CAT relu, PTT-lock, freq/mode/puissance comparés, usage unique, audit UTC. Empreinte SHA-256 du message.
5. **Invariants verrouillés par test** — tableau : I1 *0 émission sans consentement*, I2 *0 écriture QSO par le LLM*, I3 *0 faux crédit*, I4 *0 action aberrante*, I5 *jeton jamais journalisé* — tous ✓ testés, non-vacants (contre-épreuve de mutation).
6. **BYOK multi-fournisseur** — Anthropic/OpenAI/Gemini/Mistral/xAI/DeepSeek, clé fournie par l'opérateur, modèle imposé par la config, sorties structurées (JSON forcé).
7. **Mode local & autonomie** — interrupteur qui coupe le réseau IA (zéro crédit) ; dégradation gracieuse vers réponses déterministes ; anti-injection sur sources externes, garde SSRF.
8. **Méthode** — TDD + contre-épreuve par mutation (« un test vert du premier coup ne prouve rien ») + revues adversariales.
9. **Clôture** — Une IA utile parce qu'elle est bornée : explicable, sourcée, rejouable, testable, révocable.

---

### Rappels de contenu factuel (ne rien inventer au-delà)

- Fonctions IA réelles : chat expert (contexte station/concours), copilote FT8 (grammaire déterministe,
  propose-only), copilote CW/SSB, validation du log (déterministe) + audit IA optionnel (JSON forcé),
  enrichissement/saisie assistée (cty.dat + callbook), diplômes/DXCC, stratégie pile-up FT8 (consultatif),
  analyse de règlement (avec relecture humaine obligatoire), plan de session (consultatif), keyer vocal.
- Sécurité : consentement unique 30 s, Stop TX + verrou, journal d'audit UTC, empreinte message, plafond
  puissance optionnel. **L'IA n'émet jamais seule.**
- Nouveautés (nuit + jour) : HUD Opportunités, fil « Ce que l'IA remarque », après-QSO, écran Santé,
  planificateur de session, suivi tokens IA, cockpit d'accueil, mode local.
