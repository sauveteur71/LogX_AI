# Plan d'adoption — livrable D

Rédigé le 21/08/2026. Cadré par la décision de F4GLD du même jour : structure technique + templates fournis par moi, exécution communautaire (forums, groups.io, recrutement bêta-testeurs) par F4GLD.

## Raisonnement

### 1. Inventaire — ce qui existe déjà (vérifié le 21/08, pas supposé)

Avant d'écrire quoi que ce soit de nouveau, inventaire réel du dépôt : **la quasi-totalité du matériel de communication demandé par ce livrable existe déjà**, à des degrés de fraîcheur variables. Ne pas le redécouvrir en double serait un vrai gâchis.

| Document | État constaté |
|---|---|
| `README.md` | Complet, publié sur `main` — mais **`Version courante : 1.1-beta4`** affiché alors qu'on vient de publier la **1.1-beta6** ; lien HelloAsso encore au placeholder `LIEN_HELLOASSO_A_COMPLETER` ; compteur de tests (10 004) proche de la réalité mesurée aujourd'hui (**10 144**, recompté par `pytest --collect-only`), à rafraîchir quand même. |
| `docs/LogX_AI_Promotion.md` | Page de présentation complète et bien écrite — mais son tableau de chiffres est **fortement périmé** (« 470 tests automatiques » contre 10 144 réels aujourd'hui, un facteur 20). À corriger avant toute diffusion : un chiffre faux dans un document qui vante la rigueur du projet se retournerait contre lui. |
| `docs/COMPARATIF_CONCURRENTS.md` | Comparatif honnête et sourcé face à N1MM+/Win-Test/DXLog.net/Log4OM, méthodologie déjà rigoureuse (sources citées, vérifié avant publication). Document de positionnement INTERNE — pas à publier tel quel (voir note plus bas). |
| `docs/GROUPSIO_LOGX_AI.md` | Contenu **prêt à copier-coller** (paramètres de création, description, message d'accueil, post d'introduction) — seule la création du compte reste à faire par F4GLD (email + CGU, ~5 min). **Statut de création non vérifiable par moi** — à confirmer. |
| `docs/STORYBOARD_VIDEO_PROMO.md` + `_EN.md` | Storyboard complet en FR et EN (556 lignes à eux deux). Pas de moyen de savoir si la vidéo a été tournée — à confirmer. |
| `docs/helloasso_texte_campagne.md` | Texte de campagne prêt (24 lignes) — mais la campagne HelloAsso elle-même n'est manifestement pas créée (lien placeholder dans le README). |
| `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `.github/ISSUE_TEMPLATE/{bug,feature,config}.yml` | Présents, structurés — base saine pour accueillir des contributeurs externes. |
| `docs/GUIDE_UTILISATEUR.md` | 1537 lignes — onboarding déjà couvert en profondeur. |
| **Programme de bêta-test structuré** (recrutement / retours / cadence) | **Absent.** Aucun document dédié trouvé (grep sur « bêta-test »/« recrutement » dans `docs/` : seules des mentions incidentes dans le CHANGELOG). C'est le vrai trou de ce livrable. |

### 2. Diagnostic

Le travail de RÉDACTION est fait à 90 %. Ce qui manque n'est pas du contenu — c'est (a) la synchronisation de ce contenu avec l'état réel du projet (version, chiffres), (b) la **publication effective** de ce qui est prêt (groups.io, vidéo, HelloAsso — trois actions que je ne peux pas faire à la place de F4GLD, cohérent avec la répartition des rôles décidée), et (c) un vrai programme de bêta-test structuré, qui n'existe nulle part encore.

### 3. Décision

Ne pas réécrire ce qui existe déjà et fonctionne. Ce document se concentre sur les 3 manques réels : synchronisation, checklist de publication, programme de bêta-test — plus une recommandation d'ingénierie pour que le problème de désynchronisation (README à `beta4` alors qu'on est en `beta6`) ne se reproduise pas.

---

## A. Correctifs de synchronisation (quick wins, à traiter avant toute diffusion)

1. **`README.md`** : `Version courante : 1.1-beta4` → `1.1-beta6` ; recompter/rafraîchir « 10 004 tests automatiques » (10 144 aujourd'hui, chiffre qui bouge à chaque version — envisager de le formuler en ordre de grandeur plutôt qu'en nombre exact pour éviter de le re-perimer à chaque release, ex. « plus de 10 000 »).
2. **`docs/LogX_AI_Promotion.md`** : corriger le tableau « LogX AI en chiffres » — le nombre de tests (470 → réel), vérifier aussi le nombre de concours (« 36 » ici vs « 43 » dans le README — écart à trancher, une seule vérité doit sortir).
3. **Lien HelloAsso** : soit F4GLD crée la campagne (texte déjà prêt dans `docs/helloasso_texte_campagne.md`) et me donne l'URL pour que je remplace le placeholder, soit le lien reste absent tant que la campagne n'existe pas — **ne jamais publier un placeholder visible en production**, ça ressemble à un bouton cassé pour un visiteur.

## B. Checklist de publication (actions qui n'appartiennent qu'à F4GLD)

Rien ci-dessous ne peut être fait à ma place — création de comptes, décisions de calendrier public, présence humaine sur les forums. Mon rôle s'arrête à préparer le contenu, déjà fait pour l'essentiel.

- [ ] Créer le groupe groups.io (contenu prêt dans `docs/GROUPSIO_LOGX_AI.md`, ~5 minutes)
- [ ] Enregistrer et publier la vidéo courte (storyboard prêt en FR/EN)
- [ ] Créer la campagne HelloAsso (texte prêt), me transmettre l'URL pour le README
- [ ] Publier une présentation honnête sur le réflecteur CQ-Contest et eHam.net (déjà recommandé dans `docs/GROUPSIO_LOGX_AI.md` section 6) — **ne jamais y publier `docs/COMPARATIF_CONCURRENTS.md` tel quel** : c'est un document de travail interne, pas une brochure ; un post public doit rester dans le ton "je partage un projet, curieux d'avoir vos retours", pas un tableau comparatif chiffré face à des logiciels établis dans leur propre communauté — mauvais accueil quasi garanti.
- [ ] Poster l'annonce sur les canaux déjà identifiés dans les études existantes (`docs/ETUDE_COMPARATIVE_2026-07.md`) si applicable — à relire, pas dans le périmètre de vérification de cette session.

## C. Programme de bêta-test structuré (le vrai manque de ce livrable)

### Recrutement

- **Cible naturelle en premier** : les lecteurs du groupe groups.io et les visiteurs venus de CQ-Contest/eHam — pas de recrutement actif nécessaire au lancement, juste une porte d'entrée claire (déjà prévue : lien vers le dépôt + wiki dans chaque canal).
- **Cible qualifiée en second temps** (une fois le groupe actif) : radio-clubs (le profil « club » de LogX AI a des besoins spécifiques — multi-opérateur, log partagé — qui bénéficient d'un retour collectif plutôt qu'individuel), activateurs SOTA/POTA réguliers (déjà repérables via les spots que LogX AI suit lui-même — pas une cible abstraite).
- **Gabarit de message de recrutement** (à publier sur groups.io une fois créé, ou à adapter pour un forum) :

> Je cherche 5-10 bêta-testeurs pour la prochaine version de LogX AI, en particulier [préciser le chantier du moment — ex. le séquenceur FT8 automatique, ou le multi-poste radioclub]. Ce qui est utile : un usage réel en conditions (concours, activation, trafic courant), pas un test en laboratoire. Un retour "ça marche" est aussi utile qu'un bug — ça confirme qu'on peut avancer. Contact : [à définir — réponse sur ce fil, ou e-mail].

### Cadence de versions et de retours

- **Une bêta = une PR de release, comme aujourd'hui** (`v1.1-betaN`, déjà en place, `docs/CHANGELOG.md` tenu à jour à chaque tag). Rien à changer côté mécanique — le sujet est de la RENDRE VISIBLE à un groupe de testeurs, pas de la refaire.
- **Boucle de retour recommandée** : un message d'annonce sur groups.io à chaque tag publié (gabarit ci-dessous), pointant vers l'entrée du CHANGELOG correspondante — pas vers un résumé réécrit, la source déjà tenue à jour suffit.
- **Gabarit d'annonce de version** :

> **LogX AI v1.1-betaN publiée.**
> Points marquants : [1-3 lignes, copier depuis `docs/CHANGELOG.md`]
> Téléchargement : https://github.com/sauveteur71/LogX_AI/releases/latest
> Un souci après mise à jour ? Un message ici ou une issue GitHub — le plus utile est toujours le message d'erreur exact + ce qui était fait juste avant.

### Ce que je peux faire à chaque nouvelle version, sans intervention de F4GLD sur la partie communautaire

Ajouter à la checklist de release déjà suivie (voir `docs/CHANGELOG.md`) : synchroniser `README.md` (version, chiffres) au moment du bump de version plutôt qu'après coup — c'est exactement le genre d'oubli mécanique qui a laissé le README à `beta4` alors qu'on est en `beta6`. Proposition concrète : ajouter cette vérification à la même PR que le bump `APP_VERSION`/`CHANGELOG.md` désormais systématique pour chaque release (déjà fait pour la beta6, à reproduire).

---

## Ce qui n'entre pas dans ce document

- La rédaction de contenu supplémentaire — il y en a déjà assez, le travail restant est humain (publication, présence sur les forums) et non délégable.
- Une refonte de `docs/COMPARATIF_CONCURRENTS.md` — le document est bon, juste à ne pas diffuser tel quel publiquement (voir section B).
