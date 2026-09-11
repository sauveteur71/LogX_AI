# C1 — Requêtes en langage naturel sur le carnet : spec de cadrage

**Date :** 2026-09-11. **Statut : à relire par F4GLD avant tout code.**
Item du roadmap C1 (« requêtes langage naturel du copilote »), reconnu comme
un vrai chantier neuf le 11/09/2026 (voir `docs/passation/PASSATION.md`,
section fusion CHASSE→activité) : « construire une surface de chat qui
laisse un LLM interroger le carnet touche directement les invariants de
sûreté IA du dépôt (0 écriture QSO par le LLM, 0 action aberrante) et mérite
un cadrage AVEC F4GLD avant tout code, pas une improvisation nocturne. »
F4GLD a demandé de reprendre ce chantier le 11/09/2026 (« C1 PUIS ssdv »).

## 1. Ce qui existe déjà — reconnaissance factuelle avant toute proposition

Trois systèmes voisins existent, **aucun ne couvre le besoin** (vérifié en
lisant le code, pas supposé) :

- **`/agent/act`** (`logx_http.py:8678`) : message libre → `call_llm_actions`
  (tool-use Anthropic, `ACTION_TOOLS`) → au plus **une action physique
  proposée** (`pointer_rotor`, `qsy_radio`, `filtrer_spots`,
  `changer_bande_mode`, `pointer_vers`), jamais exécutée par le serveur —
  validée/normalisée par `pending_action_from_tool()` (rejette azimut hors
  0-360, fréquence non positive, etc. — implémente l'invariant I4), renvoyée
  au client comme carte de confirmation. **Aucun de ces outils ne touche le
  carnet** (lecture ou écriture) — tous pilotent la station.
- **Carte IA** (`logx_carte.html`) : questions libres à deux paliers —
  « 🔌 Basique » (0 jeton, réponse déterministe, pour les questions
  courantes score/spots/propagation) et un palier IA complet, avec dictée
  vocale et enrichissement multi-tour pour les « questions à vie »
  (DXCC/WAZ/WAC/départements). Porte sur la **propagation/le concours en
  cours**, pas sur l'historique du carnet.
- **`logx_fil_ia.js`** : flux de notifications passif, **lecture seule**,
  non-modal — rien à interroger, l'IA y pousse, l'opérateur ne lui répond
  jamais.
- **`logx_search.py`** : recherche plein-texte **statique** dans le HTML des
  pages (« où est SSTV dans le logiciel ») — pas une requête sur les
  données du carnet.

**Le vrai gap** : aucun chemin n'existant ne permet aujourd'hui de poser une
question en langage naturel sur SES PROPRES QSO (« combien de QSO en 20 m ce
mois-ci ? », « j'ai déjà travaillé F4ABC en CW ? », « quel est mon meilleur
DX en SSB cette année ? »).

## 2. Portée proposée pour C1

**Lecture seule, texte seul — aucun nouvel outil de tool-use.** C'est la
différence structurelle qui simplifie tout le reste : `/agent/act` doit
gérer des actions physiques (d'où tool-use + validation + confirmation
client) ; une question sur le carnet n'a besoin que d'une **réponse texte**.
Proposition : réutiliser `call_llm` (déjà utilisé ailleurs pour du texte
pur, PAS `call_llm_actions`) — élimine structurellement tout risque
d'action proposée sur ce chemin, donc l'essentiel du risque I4 n'existe
même pas à construire.

- **I2 (0 écriture QSO par le LLM)** : reste garanti par construction —
  aucun appel à `add_qso_to_log` (ou équivalent) n'est jamais atteignable
  depuis ce chemin, car le chemin ne fait QUE lire et renvoyer du texte.
  À COUVRIR PAR UN TEST DÉDIÉ dans `test_invariants_securite.py` dès le
  premier incrément (même patron que les 4 invariants existants), pas
  supposé acquis.
- **Contexte injecté** : jamais le carnet brut entier. Reprendre le patron
  déjà établi (`sanitize_external_text`, `logx_prompts.py`) pour tout champ
  libre (commentaire de QSO, note) injecté dans le prompt — même risque
  d'injection qu'un spot cluster ou un message ON4KST, jamais neutralisé
  nulle part pour le contenu du carnet à ce jour (vérifié : aucun appel à
  `sanitize_external_text` ni équivalent sur les champs libres du carnet
  dans le code actuel — à construire, pas déjà couvert).
- **Palier « basique » réutilisé** : les questions calculables directement
  en Python (comptage par bande/mode/DXCC, dernier contact avec un
  indicatif, meilleur DX) répondent en 0 jeton, sans appel LLM — même
  raisonnement coût/latence que Carte IA. Le palier IA ne s'active que pour
  une question qui dépasse un agrégat direct.

## 3. Ce que ce chantier n'est PAS

- **Pas un pilotage de station** : `/agent/act` existe déjà pour ça, hors
  scope ici, aucune fusion des deux chemins proposée dans ce cadrage.
- **Pas un remplacement de `logx_search.py`** : recherche UI statique
  (« où est ce bouton dans le logiciel »), nature différente, aucun rapport
  avec les données du carnet.
- **Pas une réécriture de Carte IA** : le patron basique/IA est repris
  comme RÉFÉRENCE d'architecture, pas fusionné dans le même fichier/la
  même page — où ça vit est une question ouverte (§4).

## 4. Questions ouvertes pour F4GLD

1. **Où ça vit** : nouvelle entrée de menu/page dédiée, ou intégré dans
   LOGBOOK (zone de question libre en bas du carnet) ? Le carnet est déjà
   la page la plus dense (voir directive Densité, CLAUDE.md) — à trancher
   avant la première ligne de code.
2. **Périmètre des questions couvertes en premier incrément** : uniquement
   des agrégats/comptages (palier basique, 0 jeton, zéro risque) pour
   commencer, IA complète en incrément suivant — ou les deux d'un coup ?
3. **Historique multi-tour** : Carte IA en a un pour les « questions à
   vie ». Utile ici aussi (« et en SSB ? » après « combien de QSO en CW »),
   mais ajoute de la complexité au premier incrément — à cadrer séparément
   ou inclus d'emblée ?
4. Aucun blocage de licence/dépendance externe ici (contrairement à SSDV) —
   uniquement une question d'architecture et d'ergonomie. Le seul vrai
   prérequis avant code est ta validation du périmètre ci-dessus.
