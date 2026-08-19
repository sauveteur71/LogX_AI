# Passation — reprendre LogX AI sur un nouveau compte

Écrit le 19/08/2026, à la demande de F4GLD dont le compte Claude arrivait à
échéance. Ce document est dans le DÉPÔT, pas dans une session : c'est lui qui
survit au changement de compte.

**Première chose à savoir : rien n'est perdu.** Tout le code est sur GitHub
(`sauveteur71/LogX_AI`). Ce qui disparaît avec le compte, c'est la mémoire de
travail et la méthode — les deux sont archivées ici.

---

## 1. Où en est le travail

### Fusionné et en production

| PR | Ce que ça fait |
|---|---|
| #115 | **Sûreté d'émission** : STOP et Échap annulent réellement une émission déjà programmée. Avant, jusqu'à 12,9 s d'émission continuaient APRÈS l'ordre d'arrêt, écran affichant « Émission coupée ». |
| #117 | **Décimation audio 48 → 12 kHz** avant décodage FT8. Blocage du thread principal divisé par 4 (10 319 → 2 576 ms par créneau, mesuré en vrai Chrome). |

La branche d'intégration locale est `local/live-8080-combined` — c'est celle
que sert le serveur sur le port 8080. Elle est à jour.

> ⚠️ **Le serveur doit être redémarré** pour prendre les correctifs Python.
> Les fichiers `.html`/`.js` sont relus à chaque requête, pas les `.py`.

### En attente de la décision de F4GLD

**PR #116 — le séquenceur FT8 automatique.** Un double-clic sur une station
déroule le QSO seul (appel, report, accusé, 73) puis logue.

Elle n'a **jamais été fusionnée, volontairement** : un séquenceur émet sans
surveillance, c'est la fonction la plus intrusive du logiciel, et c'est la
station de F4GLD qui est sur l'air. Trois revues adversariales successives, 69
constats confirmés et corrigés, banc à 146 cas — mais **aucun essai sur l'air**.
C'est ce qui manque, et aucun banc ne peut le remplacer.

PR #114 est l'ancêtre abandonné du séquenceur, laissée en brouillon. Ne pas la
rouvrir.

**PR #129 — le guide utilisateur.** Ouverte, jamais fusionnée faute de temps.
Elle ne porte **aucune coche de CI**, et c'est normal, pas un échec :
`check.yml` ne se déclenche que sur `concours/**` et deux chemins `.github/`,
or cette PR ne touche que `docs/`. Ne pas lire « aucune vérification » comme
« vérification en attente » — c'est le filtre de chemins, vérifié dans le
workflow. Elle ajoute au `docs/GUIDE_UTILISATEUR.md` les deux choses que
l'incident du 19/08 a rendues urgentes : l'avertissement du chapitre 2 disant
que **la sauvegarde automatique ne tourne pas tant qu'aucun dossier n'est
renseigné** (le guide la décrivait au §14.4 comme si elle tournait), et la
réécriture du §8.6 en « Modes numériques natifs : FT8, RTTY, SSTV » — le FT8
natif n'apparaissait nulle part dans les 1458 lignes du guide, alors que c'est
l'argument principal du produit. Rien de risqué dedans : c'est de la
documentation. À fusionner telle quelle.

### Ce qui reste ouvert

1. **Web Worker pour le décodage FT8** — c'est LE correctif du gel de cascade.
   La décimation a divisé le blocage par 4, mais il reste **2 576 ms mesurés
   contre un seuil de resynchronisation à 400 ms** : le compteur « N resynchro.
   audio » continuera de monter. Sortir `ft8DecodeAudioAll` du thread principal
   est le seul changement qui rende le trou nul. L'entrée est un `Float32Array`
   transférable, la sortie un petit tableau d'objets ; l'émission n'est pas
   concernée. **Aucun Worker n'existe aujourd'hui dans `concours/`.**

2. **Sans CAT configuré, la page ne peut RIEN émettre** — `envoyerMessage` sort
   avant la synthèse de la forme d'onde — alors que son message conseille de
   passer en VOX. Le conseil est donc impossible à suivre. Question ouverte
   pour F4GLD : faut-il faire réellement marcher le VOX en jouant la forme
   d'onde sans commander de PTT ? C'est un changement du chemin d'émission.

3. **Deux stations distantes de moins de 50 Hz : la seconde n'est jamais
   décodée.** `logx_ft8_dsp.js`, `minFreqSeparationHz = 8 × 6,25 Hz`. Mesuré
   (0/40 tirages pour une station à 18 Hz d'écart). Préexistant, chantier
   distinct.

4. **25 concours proposés dans l'interface n'ont AUCUNE définition serveur.**
   C'est le chantier que j'avais en cours au moment de la fermeture du compte :
   analyse terminée et chiffrée, correctif **non appliqué**. Tout ce qu'il faut
   pour le poser est ci-dessous.

   Mesuré le 19/08/2026 en exécutant le code, pas en le lisant :
   `CONTEST_DEFINITIONS` contient 43 entrées, `CONTEST_SCORING` 43 aussi, mais
   **25 identifiants de `CONTEST_SCORING` n'existent pas dans
   `CONTEST_DEFINITIONS`**. Le catalogue client (`concours/logx_configuration.js`,
   45 concours nommés) les propose pourtant tous à la sélection.

   Conséquence, vérifiée :
   `CONTEST_DEFINITIONS.get('REF_MARCONI', {}).get('bands', [])` rend `[]`. Les
   dix consommateurs passent **tous** par `.get(x, {})` — `logx_archive.py:67`,
   `logx_callhistory.py:110` et `:396`, `logx_coach.py:582` et `:825`,
   `logx_http.py:983`, `:1304`, `:2732`, `:2892`. La dégradation est donc
   **silencieuse partout** : pas d'exception, pas de trace au journal, juste des
   bandes vides. C'est pour ça que personne ne l'a vue.

   Presque tous les concernés sont des concours THF français — les douze CCD
   mensuels, Challenge THF, Trophée F8TD, Marconi, IARU VHF/UHF/50 MHz, DDFM 50,
   les quatre TVA. C'est **exactement la population visée par le chantier LOG
   V/UHF**, qui ne doit donc pas démarrer avant ce correctif : ce serait bâtir
   sur du sable.

   **La donnée existe déjà dans le dépôt**, mais dans une seconde structure
   faite pour l'affichage, pas pour le code : `CONTEST_SCORING` porte les bandes
   en texte (`'432 1296 2320MHz'`), et le catalogue client porte les libellés.
   Il n'y a donc rien à inventer — seulement à convertir. Recensement complet :

   - **15 convertibles**, liste de bandes explicite. `144MHz` :
     REF_CCD_AVR_CW, REF_CCD_DEC, REF_CCD_DEC_CW, REF_CCD_FEV2, REF_CCD_JAN2,
     REF_CCD_MAR, REF_CCD_NOV, REF_IARU_VHF, REF_MARCONI. `432 1296 2320MHz` :
     REF_CCD_FEV1, REF_CCD_JAN1, REF_CCD_MAI, REF_CCD_OCT. `50MHz` :
     REF_DDFM_50, REF_IARU_50.
   - **10 NON convertibles, et il ne faut pas les forcer** : `CUSTOM`
     (« Au choix »), `F9NL` et `UFT_RENCONTRES` (« HF »), les quatre TVA
     `REF_CDF_TVA` / `REF_IARU_TVA` / `REF_NAT_TVA` / `REF_NAT_TVA_DEC`
     (« 438MHz+ TVA »), `REF_CHALLENGE_THF` (« 144MHz-47GHz »), `REF_F8TD`
     (« 1296MHz-47GHz »), `REF_IARU_UHF` (« 432MHz-47GHz »). Développer une
     PLAGE ou un mot en liste de bandes, c'est **décider** quelles bandes en
     font partie — donc inventer une valeur de domaine, ce que ce dépôt
     interdit sans source citable. Il faut lire les règlements REF pour les
     trancher, ou demander à F4GLD. Ne pas deviner.

   Le format attendu est celui des entrées existantes : `bands` est une liste
   de chaînes en **MHz** (`['144','432']` pour REF_RPH), jamais `'2m'`/`'70cm'`.
   Vérifié sur les entrées réelles, c'est un piège classique du dépôt.

   **Recette prévue, non appliquée.** Une fonction de dérivation en fin de
   `logx_definitions.py` (après `CONTEST_SCORING`, sinon `NameError` à
   l'import) qui, pour chaque identifiant de `CONTEST_SCORING` absent de
   `CONTEST_DEFINITIONS`, analyse la chaîne de bandes et n'écrit une entrée
   **que** si elle est purement numérique. L'analyseur doit rendre `None` dès
   qu'il voit un `-` ou un mot : ainsi les 10 ambigus s'écartent tout seuls,
   sans liste noire à maintenir. L'entrée créée porte un marqueur explicite
   (`'derive_du_bareme': True`) pour qu'on ne la confonde jamais avec une
   définition relue à la main.

   Trois précautions, chacune correspondant à un piège déjà payé :
   - Les libellés viennent du catalogue client, extraits par la regex
     `id:'([A-Z0-9_]+)'\s*,\s*name:'((?:[^'\\]|\\.)*)'` sur
     `logx_configuration.js` (45 résultats, les 25 orphelins tous couverts).
     Si on fige ces libellés côté Python, il **faut** un test de
     synchronisation avec le `.js` — une liste d'identifiants recopiée à la
     main diverge, fiche `piege-liste-identifiants-ecrite-a-la-main`.
   - Un test doit **figer la liste des 10 restants** : elle ne peut que
     rétrécir, jamais grandir en silence. C'est précisément ce filet qui a
     manqué pendant tout ce temps, et sans lui le défaut se reformera.
   - Le test doit exiger une **structure** (bandes non vides, numériques), pas
     la présence d'une chaîne : `assert 'REF_MARCONI' in fichier` serait
     satisfait par le commentaire qui l'explique.

   Enfin : témoin vert d'abord, puis contre-épreuve par mutation (remettre le
   défaut, vérifier que ça rougit, restaurer, contrôler l'empreinte md5), puis
   suite complète et `ruff`. Le fichier passe en CRLF après une fusion git —
   construire les ancres multi-lignes avec `chr(10)`/`chr(13)`, sinon elles ne
   matchent plus (fiche `piege-contre-epreuve-ancres-crlf-apres-fusion-git`).

5. **Constats restants de la 3e revue** (modérés) : offre de log écrasée en
   silence par le QSO suivant après un échec d'écriture ; changement de MODE
   D'ENVOI qui tue le QSO sans le dire (`seqMajUI()` écrase le message dans le
   même tick) ; double-clic sur un 73 reçu qui repart en TX1 au lieu de
   logguer ; six raisons d'arrêt encore neutralisables sans test rouge ;
   « (sans plafond) » affiché alors qu'un plafond de 15 min court.

---

## 2. La méthode — ce qui a réellement produit les résultats

Cette section compte plus que la liste ci-dessus. Elle est le condensé de trois
nuits de travail, et chaque règle a été payée par un défaut réel.

### 2.1 La contre-épreuve par mutation, avec témoin vert

**Un test vert du premier coup ne prouve rien.** Il peut décrire le code au
lieu de le contraindre.

Après chaque correctif, remettre le défaut d'origine et vérifier que le test
rougit. Restaurer, puis contrôler l'empreinte md5 du fichier.

```
1. lancer la suite  →  TÉMOIN VERT obligatoire
2. muter une ligne
3. lancer le test visé  →  doit rougir
4. restaurer + vérifier md5
```

Le témoin n'est pas une formalité : une docstring mal fermée a un jour fait
échouer *toutes* les mutations, ce qui s'affichait « les 9 tests contraignent
le code ». Sans témoin, un fichier cassé se lit comme une protection parfaite.

**Bilan mesuré : sur ~40 tests écrits, 8 se sont révélés vacants à la
contre-épreuve.** Aucun n'aurait été détecté autrement.

### 2.2 Les cinq façons dont un test ne contraint rien

Toutes rencontrées, toutes corrigées :

1. **Satisfait par un commentaire.** `assert 'generationTx' in corps` est
   satisfait par le pavé qui *explique* `generationTx`. On pouvait supprimer la
   seule ligne réelle sans qu'un test bouge. → Dépouiller les commentaires
   avant toute analyse (`_sans_commentaires`).

2. **Présence au lieu de structure.** `assert 'seqArreter' in corps` est
   satisfait par `if(false) seqArreter(...)`. → Exiger l'appel en tête
   d'instruction, ou une structure (condition *suivie d'un* `return`).

3. **Testé contre le mannequin, pas contre la page.** Le banc réimplémente
   `envoyerMessage`, `majBoutonEnvoyer`, `confirmerLogQso`. Un test de
   comportement écrit contre le socle ne contraint que le socle — arrivé
   **trois fois**. → La propriété doit alors être tenue côté page par une
   assertion structurelle.

4. **Mauvaise fenêtre temporelle.** Deux tests décrivaient le bon scénario mais
   frappaient à un instant où le défaut est inoffensif : une garde voisine
   arrêtait aussi, avec le même message. → Distinguer *laquelle* a agi.

5. **Relation qui dépend de la cadence.** « relances == émissions − 1 » est
   faux : la dernière relance reprogramme une émission qui tombe hors de la
   fenêtre observée. → Dériver la relation de l'observé, jamais l'écrire en dur.

### 2.3 Le banc doit pouvoir VOIR le défaut

Un scénario écrit en dur sur des numéros de créneau ne reproduit souvent rien :
à la cadence réelle (un échange toutes les 60 s), la machine relit toujours la
même phase du scénario. **Procéder en deux passes** : découvrir d'abord les
créneaux que la machine utilise réellement, puis injecter sur ceux-là.

Le correspondant simulé doit aussi être réaliste. Le premier répondait au
créneau suivant le nôtre *quel que soit* ce créneau — une station qui écoute et
parle en même temps. C'est ce qui a rendu invisible le défaut le plus grave du
séquenceur (la parité d'émission).

### 2.4 Les revues adversariales

Le motif qui a produit tous les résultats :

- **une copie isolée PAR LENTILLE** (un worktree détaché chacun). Quand les
  cinq lentilles partageaient une copie, elles se mutaient entre elles : un
  agent a vu ses mesures faussées par les `if(false)` d'un voisin, et deux
  mutations sont restées en place après coup ;
- **les correctifs précédents sont les suspects, pas le code d'origine.** La
  1re revue a trouvé 17 défauts ; la 2e en a trouvé 26 dont l'essentiel *dans
  les correctifs de la 1re* ; la 3e a trouvé 26 de plus, dont deux critiques
  sur des correctifs que je croyais appliqués ;
- **un sceptique par constat**, avec pour consigne de RÉFUTER par défaut et de
  refaire toute mesure citée. Deux constats ont été écartés parce que leur
  mesure ne se reproduisait pas.

**Ne jamais reprendre un constat d'agent sans le vérifier soi-même.** Un faux
positif a déjà été signalé à F4GLD, et un cas de test de la revue s'est révélé
faux (« RRR » n'est pas une alternance sans progrès : il *termine* le QSO).

### 2.5 Mesurer sur la plateforme cible

**L'erreur la plus instructive de ces trois nuits.** J'ai annoncé la cause
racine du gel de cascade « traitée », en mesurant un *rapport* sous le moteur
des tests. J'avais moi-même écrit « c'est le rapport qui compte, pas la valeur
absolue » — et le critère d'acceptation, lui, est une durée absolue (400 ms).
J'ai correctement refusé d'extrapoler, puis j'ai conclu sans mesurer.

La revue a mesuré dans un vrai Chrome : le rapport se transportait, **la valeur
absolue aussi**, et elle était six fois au-dessus du seuil.

> Ne jamais annoncer une cause racine traitée sans l'avoir mesurée là où le
> logiciel tourne.

### 2.6 Un test peut consacrer un bug

Ma contre-épreuve d'un lot affirmait qu'aucun relâchement de PTT ne devait
avoir lieu sans onde en cours — ce qui était précisément le défaut. Il a tenu
une nuit avant que la revue suivante ne le relève.

**La mutation vérifie qu'un test mord, pas qu'il mord sur la bonne propriété.**
Rien ne remplace la question : « qu'est-ce que ce test affirme, et est-ce vrai
dans le monde ? »

### 2.7 Jamais d'agents en parallèle sur un même fichier

Deux incidents d'éditions perdues sont en mémoire. Les correctifs sur
`logx_ft8.html` se font **séquentiellement**, par moi. Les agents parallèles ne
servent qu'à *analyser*, chacun dans sa copie.

---

## 3. Conventions du dépôt

### Cycle de travail

```bash
git fetch origin main -q
git worktree add ".claude/worktrees/<nom>" -b <branche> origin/main
# éditer, tester, ruff
python -m pytest concours/tests/ -q
python -m ruff check --select E9,F concours/
git commit   # message en français, explique le POURQUOI
git push -u origin <branche>
gh pr create
gh pr checks <N> --watch
gh pr merge <N> --squash --delete-branch
# puis resynchroniser la branche live :
git fetch origin main -q && git merge origin/main --no-edit
```

### Pièges connus du dépôt

- `tests/test_voacap.py::test_predict_reel_avec_le_vrai_binaire` **échoue dans
  tous les worktrees** et passe sur `main`. Connu, ne pas chercher.
- `test_review_3ab2986_http.py::test_awards_activity_days_enorme_est_borne`
  est un **flake sous charge** — vérifié 3/3 en isolation.
- Le port 8080 sert le **dépôt principal**, jamais un worktree.
- Utiliser `/logx_logbook.html` à la racine, pas `/concours/logx_logbook.html`
  (qui sert du vide).
- Écrire les scripts de correction avec l'outil d'écriture puis les exécuter :
  les heredocs mangent les échappements (`\b` est devenu un caractère de
  contrôle invisible dans un fichier source, une fois).
- Toujours `newline=''` à l'écriture Python, sinon CRLF invisible.

### Règles produit, non négociables

- **Gratuit, autonome, multiplateforme, respectueux de la vie privée.** Aucun
  service tiers OBLIGATOIRE.
- **Intuitivité** : maître mot permanent. Un débutant doit comprendre en un
  coup d'œil quoi faire ensuite. La complexité reste DISPONIBLE, jamais
  IMPOSÉE (mécanisme `expert-only` + `localStorage.rc_ui_mode`).
- **Toujours répondre en français** à F4GLD.
- **Jamais citer un concurrent** sauf s'il est open source.
- Jamais « activation »/« activateur » en français radioamateur.
- Le bouton ⇱ DÉTACHER carte et le STOP CW ne sont JAMAIS `expert-only`.

### Règles d'audit

- **Ne rien juger, critiquer ou proposer sur la base d'une supposition.**
- **Ne jamais inventer** un nom de fichier, une fonction, une API ou un
  comportement. Sinon préfixer `HYPOTHÈSE À VÉRIFIER :`.
- **Aucune valeur de domaine écrite de mémoire** : source citable, ou écrire
  `VALEUR À SOURCER`. Charger le skill radioamateur avant toute table de
  domaine.

---

## 4. Reprendre sur le nouveau compte

1. La mémoire de travail est dans `docs/passation/memoire/` (191 fiches).
   `MEMORY.md` en est l'index. La recopier dans
   `~/.claude/projects/<projet>/memory/` pour la réactiver.
2. `CLAUDE.md` à la racine est lu automatiquement à chaque session : il porte
   déjà la langue, l'intuitivité, la charte graphique — et désormais un renvoi
   vers ce document.
3. Le premier réflexe utile : lire `MEMORY.md`, puis les fiches marquées 🚨
   (ce sont les pièges qui ont coûté le plus cher).

---

*Trois revues adversariales, 69 constats confirmés et corrigés, 146 cas au banc
d'essai. Et un séquenceur qui attend toujours son premier QSO réel — parce
qu'aucun banc ne remplace une antenne.*
