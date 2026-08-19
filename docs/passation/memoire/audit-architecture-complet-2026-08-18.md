---
name: audit-architecture-complet-2026-08-18
description: "AUDIT ARCHITECTURE COMPLET (18/08/2026, 32 agents, 6.2M jetons) : cartographie + top 10 valeur/effort. Tranche les 2 points ouverts de F4GLD : règle K>=5 déjà supprimée du code, indice A calculé mais JAMAIS servi à l'IA malgré 2 commentaires qui l'affirment"
metadata: 
  node_type: memory
  type: project
  originSessionId: 98b0707f-1a89-40bf-8422-4ab7b88ba78a
  modified: 2026-08-18T08:46:02.011Z
---

Demande F4GLD 18/08/2026 : audit + refonte + promotion de LogX AI, par un
prompt très cadré (rôle architecte + radioamateur, zéro invention, zéro valeur
de domaine non sourcée, raisonnement étape par étape). Première action limitée
à 3 livrables : cartographie, 5 questions, top 10. **Livrables B/C/D (feuille
de route complète, spec agent IA, plan d'adoption) NON produits — F4GLD a
explicitement demandé de ne pas enchaîner sans validation, on avance section
par section.**

Méthode : Workflow 32 agents (10 cartographie par sous-système, 3 couverture
fonctionnelle, 3 concurrence, 1 diagnostic, 14 vérificateurs adversariaux,
1 synthèse). 155 constats bruts → 14 faiblesses candidates → **13 confirmées,
1 réfutée**. Chaque constat porte une preuve fichier:ligne relue.

## Les 2 points ouverts de F4GLD, tranchés

**(a) Règle « K>=5 ne dégrade que les bandes hautes » : DÉJÀ SUPPRIMÉE.**
Le point était périmé — `logx_paths.py:182-185` porte déjà un commentaire qui
la réfute (échelle G du NOAA définie sur Kp, libellé HF *latitudinal*, jamais
« bandes hautes »). Deux précisions sourcées manquaient et sont à ajouter :
le NOAA ne mentionne AUCUN effet HF à G1 (Kp=5), le 1er libellé HF est à G2
(Kp=6) ; et l'absorption d'orage varie en f^-1,5 (modèle D-RAP du SWPC), donc
frappe plus fort les bandes BASSES — l'exact inverse de la règle. Le bon
seuil Kp>=6 est déjà utilisé par `logx_coach.py:498`.

**(b) Indice A : le code se ment à lui-même.** F4GLD pensait qu'il n'était pas
exploité. Réalité : il EST calculé, stocké et affiché (PROPAG, panel), et
`logx_paths.py:112-114` + `247-249` affirment DEUX FOIS qu'il est « SERVI au
client et à l'IA ». Vérifié par grep : il n'atteint JAMAIS le contexte de
l'agent IA — ni `logx_http.py:1405-1411` (n'utilise que k_index+summary), ni
`paths.context_block()` (`logx_paths.py:409-417`). Correctif : une ligne.
Réflexe général confirmé : **un commentaire qui affirme un comportement n'est
pas une preuve, greper le chemin réel.**

## Verdict de maturité (résumé)

Solide : persistance/intégrité (le meilleur du dépôt — écriture atomique,
`synchronous=FULL`, drapeau `load_failed` qui gèle plutôt qu'écraser), instance
unique, services externes (déontologie exemplaire), diplômes, IA (séparation
déterministe/LLM réellement tenue, l'agent n'écrit jamais dans le log).
Faible : exports de dépôt (14/28 concours Cabrillo sans `cabrillo_name`, EDI
émet `CScor=` hors spec), score × multiplicateurs appliqué sur AUCUN des 3
chemins qui font autorité, front/i18n le plus inégal.

## Top 10 livré (ordre = ratio valeur/effort)

A01 VOACAP décalé d'une colonne · A02 `/log/add` ne renvoie pas l'id attribué
(→ « annuler le dernier QSO » efface un QSO historique) · A03 `handle_error`
non surchargé (pannes invisibles) · A04 exports Cabrillo/EDI non conformes ·
A05 miroir JS des barèmes ment quand il ignore un prédicat · A06 clavier du
run CW (dont : impossible de couper une émission WinKeyer sans CAT) ·
A07 `extra_fields` absents de l'export ADIF serveur · A08 cases CONFIG mortes ·
A09 `/log/list` non authentifié + CDN sans SRI · A10 score × multiplicateurs
(seul chantier M, fonctionnellement le plus important mais classé dernier par
ratio — assumé et expliqué).

## Le constat RÉFUTÉ (ne pas le ressortir)

« Aucune porte d'entrée pour l'écosystème (GridTracker/JTAlert/Wavelog) » :
FAUX sur ses 3 affirmations. `X-RC-Token` est une vraie clé d'API persistante
(`logx_http.py:577-605`), `POST /log/import_adif/commit` accepte une chaîne
ADIF brute, `GET /call/history` fait déjà le « worked before » en plus riche
que JTAlert, et `docs/API.md` (2027 lignes, 222 routes) existe. Le vrai
reliquat est étroit : compatibilité de FORME d'URL avec Cloudlog/Wavelog, et
l'écouteur ADIF-net ne parse que du XML `<contactinfo>` alors que GridTracker
émet de l'ADIF brut en UDP. ~15 lignes chacun.

## Question ouverte qui bloque la suite

Q1 (positionnement concours+expédition VS carnet généraliste) décide si
« champs de carnet + QSL papier » entre en position 3 du top 10 ou reste
dehors. C'est l'écart n°1 pour qui vient de Log4OM/HRD/Wavelog. Ne pas
trancher à sa place.

Voir [[feedback-jamais-citer-concurrents-sauf-open-source]] : le comparatif
concurrentiel est un outil d'analyse INTERNE, ne jamais le reverser tel quel
dans la communication produit.
