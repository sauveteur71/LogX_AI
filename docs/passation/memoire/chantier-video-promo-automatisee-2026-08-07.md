---
name: chantier-video-promo-automatisee-2026-08-07
description: "Vidéo promo LogX AI (FR+EN) générée de bout en bout par l'assistant — ElevenLabs (voix) + Playwright (captures réelles) + ffmpeg (montage), sans intervention manuelle de F4GLD sur le tournage"
metadata: 
  node_type: memory
  type: project
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-08-07T08:39:16.838Z
---

Demande F4GLD (07/08/2026) : transformer `docs/STORYBOARD_VIDEO_PROMO.md`
en vraie vidéo sans qu'il ait à filmer/monter lui-même. Livré : 2 fichiers
MP4 (~6:33 chacun, FR et EN) envoyés directement en pièce jointe — pas
commités dans le dépôt (fichiers binaires volumineux, générés à la
demande, pas du code).

**Outils installés sur ce poste pour ce chantier** (pas des dépendances du
projet LogX AI, juste des outils locaux) :
- `ffmpeg` via `winget install --id Gyan.FFmpeg -e --source winget`
  (le `--source winget` explicite est nécessaire — sans lui, winget tente
  d'abord `msstore` et échoue sur ce poste avec une erreur de certificat).
- `playwright` (`pip install playwright` + `playwright install chromium`)
  — **piège rencontré** : ce poste a plusieurs interpréteurs Python
  installés (`python3` de la Windows Store résout vers Python 3.14 sans
  playwright, `python` résout vers Python 3.13 où pip avait bien installé
  le paquet) — toujours vérifier `python --version` correspond à celui où
  `pip install` a été fait avant de lancer un script.

**Pourquoi Playwright plutôt que les outils de capture d'écran du poste
(Browser pane / claude-in-chrome)** : `mcp__Claude_Browser__computer`
(screenshot) ne fournit l'image que DANS le contexte de conversation, pas
de fichier PNG accessible sur disque. `mcp__claude-in-chrome__computer`
a bien un paramètre `save_to_disk`, mais le fichier résultant reste
introuvable par `find`/`Glob` depuis l'outil Bash — chemin de sauvegarde
opaque, hors de portée. Playwright headless, lancé via Bash, écrit
directement où on lui dit (contrôle total du chemin), donc seule
approche fiable pour alimenter ffmpeg ensuite.

**Voix ElevenLabs** : clé API fournie par F4GLD dans le chat (jamais
écrite dans un fichier du dépôt), restreinte à la SEULE permission
Text to Speech (bonne pratique confirmée en pratique : les appels
`/v1/user/subscription` et `/v2/voices` ont échoué avec
`missing_permissions`, sans bloquer la synthèse elle-même — donc
restreindre une clé à un seul usage n'empêche pas ce pour quoi elle a été
créée). Voix "Adam" (`pNInz6obpgDQGcFmaJgB`), modèle
`eleven_multilingual_v2` — même voix pour les deux langues, l'accent
s'adapte automatiquement.

**Piège trouvé en écoutant l'audio généré** (retour F4GLD) : le texte
`**?**` (markdown gras autour d'un point d'interrogation isolé) envoyé
tel quel à la synthèse vocale se prononçait mal — présent identiquement
dans les DEUX storyboards (FR et EN), même passage sur le petit bouton
d'aide de CONFIG. Corrigé en reformulant la phrase (jamais un symbole nu
lu à voix haute) ET en ajoutant un nettoyage défensif du markdown
(`**gras**`, `*italique*`, `` `code` ``) dans le script d'extraction, pour
que ça ne se reproduise pas sur un futur bloc de narration édité avec du
formatage.

**Captures d'écran** : sur le VRAI serveur de production (port 8080,
lecture seule — aucun clic sur ENREGISTRER/SAUVEGARDER, uniquement
navigation + ouverture de popups + saisie non validée dans le champ
indicatif). Thème et langue forcés via
`localStorage.setItem('rc_theme'|'rc_lang', ...)` dans
`context.add_init_script()` AVANT le premier chargement de page — évite
un flash de mauvais thème/langue à la capture. **Thème JOUR retenu**
(`rc_theme='day'`) — le storyboard recommandait initialement la nuit
("plus photogénique"), mais F4GLD a explicitement demandé le jour après
le premier envoi ; recapturé + revidéo en quelques minutes puisque
`build_video.py` réutilise l'audio déjà généré, seules les images
changent. 23 écrans capturés par langue (46 au total), mappés 1:1 avec
les 23 blocs de narration du storyboard (même ordre de section, donc
même index).

**Corrections après premier envoi** (retour F4GLD, 5 problèmes réels) :
1. **Trop de haut de page LOGBOOK visible** — `body{overflow:hidden}` sur
   cette page (mise en page "app" fixe, voir CLAUDE.md) : `window.scrollTo`
   ne fait RIEN, ce n'est pas une page qui défile. Corrigé en capturant
   avec un viewport plus HAUT que la sortie (1600×1300 au lieu de
   1600×900) puis `page.screenshot(clip=...)` pour ne garder qu'une
   fenêtre de 900px décalée (`y:400`) — cadre sur SAISIE/tableau/keyer,
   pas sur la grille de stats. Deux fenêtres de clip selon le bloc :
   `CLIP_TOP` (y:0, pour l'accroche et la barre de score/propagation,
   qui PARLENT justement de cette zone) et `CLIP_CONTENT` (y:400).
2. **Panadapter vide** (pas de flux audio réel en capture automatisée) —
   page retirée de la capture ; ce bloc de narration réutilise
   l'image du band map (`06_logbook_bandmap`) dans `build_video.py`.
3. **Carte IA sans station** — le panneau COACH est fermé par défaut
   (`#coachPanel{display:none}`), à activer via `coachAdvice()` (bouton
   `.qbtn-coach`) avant la capture pour voir de vraies recommandations
   ("NOUVEAU PAYS jamais travaillé : ... spotté, appelle-le !").
4. **Cluster/band map vide** — pas un bug de capture : la bande par
   défaut du formulaire était 160m (souvent silencieuse en journée). Basculé
   sur 20m/14MHz via `pickBand('14')` (fonction JS du logbook) avant la
   capture — bande DX quasi toujours active, spots réels garantis.
5. **Écran de clôture** — remplacé le dépôt de code brut
   (`github.com/.../radioaamateur-program-Contest`) par le vrai site de
   présentation, `https://sauveteur71.github.io/LogX_AI/` (GitHub Pages
   actif sur ce dépôt séparé, voir [[piege-deux-depots-github-distincts-logx-ai]])
   — bascule FR/EN via son propre bouton (`button.lang-btn:not(.active)`,
   PAS `text=EN` qui matchait le mauvais élément et scrollait ailleurs
   sur la page sans traduire le contenu).
6. **Fin trop abrupte** — narration de clôture (FR+EN) réécrite : ajoute
   la mention de l'assistance par copilote IA (absente jusque-là de la
   vidéo, présente seulement dans le README) et se termine sur une
   invitation explicite ("testez-le, aidez-moi à l'améliorer" /
   "give it a try, help me make it better") plutôt que de s'arrêter sur
   une liste de liens.

**Montage** : un clip par bloc (image fixe + léger zoom Ken Burns
`zoompan` + la piste audio du bloc, durée = durée audio + 0.4s de marge),
concaténés par langue. Scripts et fichiers intermédiaires dans le
scratchpad de session (non committés) — à relancer entièrement si l'appli
change visuellement, les scripts (`generate_tts.py`, `capture_shots.py`,
`build_video.py`) restent dans le scratchpad de CETTE session seulement.
