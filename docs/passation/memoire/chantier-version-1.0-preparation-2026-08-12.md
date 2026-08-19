---
name: chantier-version-1-0-preparation-2026-08-12
description: "Passage de 0.9-beta27 à la version 1.0 stable (PR #44) — changelog nettoyé des concurrents, i18n MODE NUMÉRIQUE/RTTY/FT8 découvert à 0% et corrigé, site de présentation rafraîchi"
metadata: 
  node_type: memory
  type: project
  originSessionId: 98b0707f-1a89-40bf-8422-4ab7b88ba78a
  modified: 2026-08-12T11:37:56.535Z
---

Demande F4GLD : « pousse une nouvelle beta et ensuite audit sous un angle
différent » interrompu, corrigé en « non pas une beta mais la version 1 » —
première sortie STABLE (pas juste un bump beta), déclenchée juste après la
clôture complète du 2e passage d'audit ([[chantier-triage-et-fixnow-mineur-2026-08-12]]).
Puis 2 instructions ajoutées en cours de route (mi-tour, pas de nouveaux
tours de conversation) : « pense a la mise a jour des langues, mise a jour
de readme et de la presentation web » et « dans le journal des
modification supprime toute allusion aux programme concurent! ».

## PR #44 (mergée, taguée, release publiée — chantier CLOS)

Séquence finale respectée à la lettre (leçon beta27, voir bas de page) :
build PyInstaller local réel AVANT le tag (`dist/LogXAI.exe`, 56,9 Mo,
sans erreur) -> tag `v1.0` poussé -> build multi-OS GitHub Actions
surveillé jusqu'au bout (pas supposé) -> confirmé via `gh release view
v1.0` : 3 assets présents (`LogXAI-v1.0.exe`, `-macos`, `-linux`) ->
branche live resynchronisée, serveur 8080 redémarré, `/network/info`
confirme `"app_version": "1.0"` en direct. Aucun repli/re-tag nécessaire
cette fois (contrairement à beta27).

- `logx_version.py` : `APP_VERSION = '1.0'` (convention établie : pas de
  suffixe patch style beta, juste `1.0`, cohérent avec `v0.9-betaN` sans
  patch non plus).
- `docs/CHANGELOG.md` : entrée `[1.0]` résumant TOUT depuis beta25 (beta25
  était la dernière entrée réellement à jour — beta26/beta27 n'avaient
  jamais eu d'entrée, rattrapé ici). Liste construite depuis `gh pr list
  --state merged` plutôt que de deviner.
- **Nettoyage concurrents (sur consigne explicite)** : 8 mentions
  nominatives (N1MM, Win-Test, DXLog, Log4OM, Tucnak, Wavelog, MMTTY/
  MMVARI/Fldigi) retirées du changelog ENTIER, pas seulement l'entrée
  1.0 — certaines dataient d'entrées historiques (beta1, beta7) déjà
  écrites avant cette session. Reformulé en gardant le sens technique
  (« export d'autres loggers de concours » au lieu de nommer chacun).
  Portée demandée = uniquement `docs/CHANGELOG.md` ; `README.md` cite
  encore Tucnak/qxsl dans la section Licence (contexte différent — valeurs
  logiciel libre partagées, pas une comparaison concurrentielle) : laissé
  tel quel faute d'instruction explicite sur ce fichier.

## Découverte majeure : i18n à 0% sur 3 pages livrées le 11/08

`logx_modes_numeriques.html` (hub), `logx_rtty.html`, `logx_ft8.html`
(créées 11/08, donc APRÈS les derniers gros audits d'intuitivité/
accessibilité) : **zéro** clé de traduction, confirmé par extraction
`TreeWalker` réelle en navigateur (pas une supposition) sur les 3 pages.
`logx_ft8.html` définissait même un helper `T = s => window.rcT ? ... : s`
jamais appelé nulle part dans son propre code.

**Méthode reproductible pour scoper un rattrapage i18n** (à réutiliser) :
1. Charger la page en navigateur réel, exécuter un script qui reproduit
   EXACTEMENT le `TreeWalker`/filtre de `logx_i18n.js` (SCRIPT/STYLE exclus,
   `.rc-i18n-live` exclu, `#rcLangSelect` exclu) + `[title],[placeholder],
   [alt],[aria-label]` — donne la liste EXACTE des fragments texte tels que
   le moteur les voit, fragments coupés par les balises inline (`<b>`, `<a>`)
   inclus. Deviner cette segmentation à l'œil sur le HTML source est trop
   risqué (vérifié : un paragraphe avec 2 `<b>` + 1 `<a>` se scinde en 7
   fragments distincts).
2. Dédupliquer et vérifier CHAQUE fragment contre le dictionnaire existant
   (recherche exacte de la clé, pas une recherche approximative) avant de
   traduire quoi que ce soit — sur 62 candidats, 11 étaient déjà couverts
   ailleurs par coïncidence de texte.
3. Structure établie du fichier (13 objets `T_XXX_FIX` nommés par
   fonctionnalité, PAS un seul gros dictionnaire) : créer un nouveau
   `const T_NOUVEAU_FIX = { en:{}, de:{}, es:{}, it:{}, pt:{}, nl:{}, pl:{} }`
   + boucle `for (const l of [...]) if (T[l]) Object.assign(T[l],
   T_NOUVEAU_FIX[l]);` juste avant `window.rcTranslate = ...` (fin du
   fichier). Contrairement à `T_PARITY_FIX` (n'a QUE 6 langues, EN sert de
   référence déjà traduite) — un rattrapage où même EN manque doit inclure
   les 7 langues.
4. Traduction : Workflow, 7 agents en parallèle (un par langue), même liste
   de chaînes source, consigne explicite de préserver la continuité
   grammaticale des fragments coupés (le fragment N+1 doit continuer la
   phrase du fragment N une fois concaténés) et de ne JAMAIS traduire le
   jargon universel (CQ/QSO/DX/RST/PTT/CAT/UTC/Hz/FT8/RTTY/WSJT-X/LOGBOOK/
   CONFIG). Assemblage fait par moi (pas par les agents directement dans le
   fichier partagé) via script Python, pour éviter tout risque d'édition
   concurrente sur `logx_i18n.js`.
5. **Vérification en navigateur réel obligatoire, pas seulement
   `test_i18n_parite_langues.py`** : ce test ne garantit QUE la parité
   inter-langues (si une clé existe quelque part, elle existe partout) —
   il ne détecte NI une clé absente de toutes les langues à la fois, NI une
   clé présente mais qui ne matche jamais le DOM réel. Les deux défauts
   suivants n'ont été trouvés qu'en rechargeant les pages traduites et en
   lisant le texte affiché :
   - **Piège espace insécable** : une phrase RTTY (« ...moins de 50&nbsp;Hz
     du signal... ») avait DÉJÀ une traduction existante dans le
     dictionnaire (ajoutée par un chantier antérieur, coïncidence de texte)
     — mais la clé du dictionnaire utilisait un espace NORMAL alors que le
     HTML source utilise `&nbsp;` (rendu en U+00A0 par le navigateur, pas
     U+0020). Byte différent, invisible à l'œil, `test_i18n_parite_langues.py`
     ne pouvait pas le voir (il compare les langues entre elles, jamais
     contre le DOM réel). Trouvé uniquement parce que la phrase restait en
     français après bascule de langue malgré une traduction censée exister.
     Corrigé dans les 7 langues (remplacement de l'espace par U+00A0 dans
     la clé, pas dans le HTML — modifier le HTML aurait pu casser le
     retour à la ligne voulu par l'auteur d'origine).
   - **Étiquette de nav jamais traduite** : « MODE NUMÉRIQUE » (majuscules,
     libellé du lien de navigation partagé sur 10 pages) est un texte
     DIFFÉRENT de « Modes numériques » (h1, casse normale) — deux clés
     distinctes pour le moteur texte-exact. Je n'avais traduit QUE le h1,
     oubliant l'étiquette de nav elle-même, qui restait donc en français
     sur les 10 pages qui partagent cette barre de navigation (pas
     seulement les 3 pages du chantier). Trouvé en relisant le texte de
     page après traduction, pas en relisant le code.

## Site de présentation (repo séparé `sauveteur71/LogX_AI`, GitHub Pages)

Découverte en creusant « présentation web » : un repo GitHub DISTINCT du
dépôt principal héberge le site vitrine (`sauveteur71.github.io/LogX_AI/`,
`index.html` unique de 827 Ko, contenu bilingue FR/EN dupliqué en dur —
pas de template, le FR est du HTML direct, l'EN est un tableau de chaînes
JS échappées). Figé à `v0.9-beta22` (créé le 05/08, jamais retouché depuis)
avec deux inexactitudes visibles publiquement : « licence à définir »
(GPLv3 adoptée depuis beta25, le 07/08) et « 194 fichiers de tests »
(234 fichiers / 9000+ tests aujourd'hui). Corrigé (version, licence,
compte de tests) en FR et EN, poussé directement sur `main` de CE repo
(pas de CI/tests sur un site statique, cohérent avec son historique de
3 commits tous en push direct). Contenu éditorial plus profond (mentions
de fonctionnalités) laissé tel quel — seules les inexactitudes factuelles
confirmées ont été corrigées, pas de refonte du texte marketing.

## Reste à faire après le merge de PR #44 (voir tâches #17-19 de la session)

Avant de pousser le tag `v1.0` : lancer un VRAI build PyInstoller local
(`python -m PyInstaller --noconfirm --clean logx.spec`) — leçon du 12/08
([[chantier-fix-release-cassee-et-repli-version-bugreport-2026-08-12]]) :
un tag `v0.9-beta27` avait cassé le build multi-OS 2 jours sans que
personne ne le sache, faute de cette vérification. Puis pousser le tag,
surveiller `build-release.yml` sur les 3 OS (ne pas supposer que ça
marche), puis synchroniser `local/live-8080-combined`.
