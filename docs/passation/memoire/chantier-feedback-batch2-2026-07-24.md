---
name: chantier-feedback-batch2-2026-07-24
description: "6 correctifs demandés par l'utilisateur (dossier sauvegarde natif, CW décodeur qui cachait la saisie, foudre en direct, i18n incomplet, raccourci bureau)"
metadata: 
  node_type: memory
  type: project
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-07-24T16:40:44.039Z
---

Commits 3093922, aeef05b, bd72b19, 04b690d, 3e8cd85, c804152 (24/07/2026), menés via Workflow en parallèle de [[chantier-bandes-modes-serveur-dxheat]] (même fichier `logx_configuration.html` touché par les deux — pas de collision car exécutés en config "jamais toucher ce fichier pendant que l'autre workflow tourne encore").

- **Sélecteur dossier natif Windows** : nouveau module réutilisable `logx_winshell.py` (PowerShell + `System.Windows.Forms.FolderBrowserDialog` en sous-processus, timeout 180s, ne lève jamais d'exception) — utilisé à la fois par `/backup/pick_folder` et par le raccourci bureau ci-dessous. `tkinter` reste exclu du build PyInstaller.
- **Décodeur CW qui cachait l'enregistreur de QSO** : bug racine = `toggleCwDecoder()` déclarée deux fois dans `logx_logbook.js` (la 2e écrasait silencieusement la 1re). PIÈGE CSS trouvé en vérifiant en navigateur réel : corriger juste la cible du padding (`.saisie-secondary` au lieu de `.saisie-panel`) ne suffisait pas — un `padding-bottom` plus grand que la boîte la force à grandir (une boîte ne peut jamais être plus petite que ses marges internes), ce qui faisait déborder `.saisie-secondary` de son parent. Solution finale : réduire `max-height` au lieu d'ajouter du padding.
- **Carte de foudre Blitzortung.org** : intégrée en iframe (pas juste un lien) après vérification live que la page n'a AUCUN header `X-Frame-Options`/CSP ni script anti-frame — embarquable. Iframe complète sur `logx_propagation.html`, simple lien compact sur l'écran mural.
- **i18n incomplet** (bouton "ENREGISTRER LE QSO" resté en français malgré changement de langue) : 2 bugs structurels trouvés en testant en navigateur réel, pas en relisant le code — (1) `el.textContent = msg` sur un nœud existant génère une mutation `childList` (remplacement de nœud texte), pas `characterData` comme on l'aurait cru ; l'ancien filtre n'acceptait que les nœuds ÉLÉMENT → corrigé pour accepter aussi les nœuds texte + observer `characterData` en plus, avec garde-fous anti-boucle (`LAST_OUT` WeakMap, classe `.rc-i18n-live` pour horloge/chrono/score). (2) La fonction `walk()` excluait les `<option>` du parcours de traduction (même liste que SCRIPT/STYLE) — oubli sans rapport avec `option.value`, corrigé.
- **Raccourci bureau au premier lancement** : gated sur `is_frozen()` (jamais proposé en dev), marker file anti-répétition. Utilise `SpecialFolders('Desktop')` (pas `%USERPROFILE%\Desktop` codé en dur) pour rester correct sous OneDrive avec redirection de dossiers connus.

Vérification indépendante (moi, hors auto-évaluation du workflow) : pytest relancé deux fois (1051 puis 1073 tests avec les commits suivants, 0 échec réel — un seul flake transitoire dû à une collision avec l'autre workflow tournant en parallèle, non reproductible), grep "QSO Director" propre, lecture directe de `logx_winshell.py` (gestion annulation/timeout/hors-Windows/échappement PowerShell correcte).
