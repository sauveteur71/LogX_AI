# Dossier InVideo AI — LogX AI

Tout ce qu'il faut pour lancer la production d'une vidéo de **10 à 15 min** sur
**InVideo AI** et obtenir un premier jet de qualité, sans perdre de temps.

## Contenu du dossier

| Fichier | À quoi ça sert |
|---|---|
| `01_prompt_invideo.md` | Le **prompt de workflow** à coller dans InVideo (3 variantes : 10 min, 13 min, teaser) + les réglages à cocher |
| `02_script_narration.md` | Le **script de narration pur** (texte dit à voix haute), prêt à coller en *Script to video*. Sections : Introduction · Le Problème · La Solution · Démonstration · Conclusion |
| `03_plan_visuel_captures.md` | La **liste des captures d'écran** à faire (écran, état, nom de fichier) mappée au script, + les assets déjà dispo (logos, présentations web) |
| `04_voix_off.md` | Les **deux options de voix** (IA d'InVideo ou ta voix) + la direction de jeu |
| `captures/` | *(à créer)* — range ici tes captures d'écran nommées comme dans le fichier 03 |

## Marche à suivre (dans l'ordre)

1. **Les captures sont déjà faites** — 19 visuels réels dans `captures/` (station
   TM6KJS, ~10 000 QSO), mappés au script dans `03_plan_visuel_captures.md`. Deux
   visuels optionnels restent à décider (bannière de score concours en direct ;
   plan de session généré) — voir la fin de `03_…`.
2. **Ouvre InVideo AI**, mode **Script to video**, langue **Français**.
3. **Colle le prompt** de `01_prompt_invideo.md` (variante A recommandée).
4. **Colle le script** de `02_script_narration.md` (tout, à partir de `## INTRODUCTION`).
5. **Génère** le premier jet.
6. **Remplace les visuels de banque** par tes captures (fichier 03).
7. **Voix off** : suis `04_voix_off.md` (option B = ta voix = plus crédible).
8. **Sous-titres FR**, format **16:9**, musique discrète, puis export.

## Checklist avant de cliquer « Generate »

- [x] Script narration prêt (`02_…`) — polyvalence en fil rouge, prêt à coller
- [ ] Prompt de workflow choisi (`01_…`) — durée, ton, langue, format
- [x] Captures d'écran faites (19 dans `captures/`, mappées dans `03_…`)
- [ ] Logo prêt pour intro/outro (`docs/logoXAI.png`)
- [ ] Décision voix off prise (IA InVideo **ou** ma voix)
- [ ] Sous-titres = FR · Format = 16:9 · Musique = discrète

## Rappel — ne rien inventer

La vidéo ne doit présenter **que ce que LogX AI fait réellement**. Bornes
factuelles : `../logx_decks_claude_design.md` § « Rappels de contenu factuel »
et le script minuté d'origine `../logx_video_script_13min.md`.
