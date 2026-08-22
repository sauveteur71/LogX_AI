---
name: regles-produit-permanentes
description: "Règles permanentes de comportement et de positionnement produit pour LogX AI (fusion de 7 fiches feedback, 21/08/2026) — langue, vocabulaire, concurrents, workflow git, exceptions UI actées"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: e5854853-072f-4b5f-895a-57c4ab0111d2
  modified: 2026-08-21T03:32:51.012Z
---

Consolidation du 21/08/2026 des fiches `feedback-*.md` individuelles (conservées telles quelles dans `docs/passation/memoire/` du dépôt). Ce sont des règles TRANCHÉES — ne pas les rouvrir sans qu'F4GLD ne le fasse lui-même.

## Langue et vocabulaire

- **Toujours répondre en français**, quelle que soit la langue du contenu observé. Demandé au moins deux fois avant d'être fixé dans `CLAUDE.md` (chargé automatiquement à chaque session) — si `CLAUDE.md` semble avoir perdu cette consigne, la restaurer immédiatement plutôt que de compter sur la seule mémoire.
- **Jamais « activation »/« activateur » dans le français VISIBLE** (« supprime ce language cibiste, on est radioamateur ! », 30/07/2026) — même si ce sont les termes officiels POTA/SOTA/WWFF dans leurs propres API. Vocabulaire retenu : « STATIONS X EN DIRECT », « TRAFIC EN PORTABLE », « MA RÉFÉRENCE », « tu opères depuis ». L'anglais et l'allemand gardent « activation »/« Aktivierung » (termes officiels dans ces langues). Les identifiants de CODE existants restent (`activation_program`, `logx_activation.py`…) — jamais renommés, ça casserait la config déjà sur disque. Deux homonymes à ne jamais toucher : « activation (SCOREBOARD EN DIRECT) » = mise en marche d'une fonction, « désactivation volontaire » = arrêt d'un enregistreur.
- **Piège structurel pour tout renommage de texte** : les clés de `logx_i18n.js` SONT les phrases françaises — changer un libellé sans changer sa clé casse les 7 traductions en silence. Toujours déplacer les deux ensemble.

## Positionnement concurrentiel

- **Ne jamais citer un concurrent nommément** (code, UI, commits, docs) dont on s'inspire, sauf s'il est réellement open source (ex. OmniRig). Viser systématiquement plus soigné visuellement que l'inspiration. Reformuler en termes génériques du domaine (« bandmap multi-bandes »), jamais en référence à l'implémentation d'un tiers (« comme SwissLog »). Avant de committer une fonctionnalité née d'une veille concurrentielle : grep le nom du produit source dans tout le diff et le retirer.
- **« QSO Director » : interdiction absolue et permanente** dans tout fichier sous `concours/` (code, UI, JS, JSON, commentaires, noms de fichiers), y compris en comparaison. La mémoire de travail elle-même peut continuer à le nommer pour le suivi interne — seule l'application livrée est concernée. Grep insensible à la casse avant tout commit touchant `concours/`.

## Workflow git

- **Tout gros chantier passe par une branche dédiée, CI verte AVANT fusion dans `main`.** Les corrections d'une ligne peuvent continuer d'aller directement sur `main`. Cause : deux push directs ont mis `main` au rouge (chemins non portables Windows/Linux, sémantiques socket supposées universelles) — la CI est la seule autorité pour Linux/macOS, une validation locale Windows ne suffit jamais à annoncer « c'est bon ». Ne jamais construire d'exécutable pendant que `main` est potentiellement rouge.
- **Ne pas reconstruire l'exécutable (PyInstaller) à chaque commit** — uniquement en fin de chantier ou sur demande explicite. Un `git commit` est un commit de code source, point.

## Exceptions UI actées (ne pas les re-signaler comme un manquement)

- **Le bouton ⇱ DÉTACHER de CARTE IA reste visible dans TOUS les modes** (Simple ET Expert), jamais `expert-only` — confirmé explicitement deux fois par F4GLD (une revue automatique l'avait suggéré en `expert-only` au nom de la règle générale d'intuitivité ; rejeté).
- Rappel du principe général qui encadre ces exceptions (voir `CLAUDE.md`) : masquer ≠ bloquer l'accès, jamais de désactivation de la fonction sous-jacente — seulement du CSS.
