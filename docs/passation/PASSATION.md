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

### En attente d'un essai sur l'air

**PR #116 — le séquenceur FT8 automatique.** Un double-clic sur une station
déroule le QSO seul (appel, report, accusé, 73) puis logue.

> 🔴 **Elle EST fusionnée** — le 19/08/2026 à 09:19 UTC, commit `ff5991e`.
> Une version antérieure de cette page affirmait le contraire (« jamais
> fusionnée, volontairement ») : c'était vrai à l'écriture, faux depuis, et
> personne ne l'avait mise à jour. Vérifié en relisant `main`, pas en croyant
> le document : `seqDemarrer` / `seqArreter` / `seqEtat` sont présents dans
> `concours/logx_ft8.html`. **La fonction la plus intrusive du logiciel est
> donc dans le code que F4GLD fait tourner.**

Ce qui reste vrai, et qui est le vrai sujet : un séquenceur **émet sans
surveillance**, et c'est la station de F4GLD qui est sur l'air. Trois revues
adversariales successives, 69 constats confirmés et corrigés, banc à 146 cas —
mais **toujours aucun essai sur l'air**. Aucun banc ne peut le remplacer.

C'est donc la première chose à faire en reprenant : un essai réel, sur une
station surveillée, avant que quiconque d'autre s'en serve. Même remarque pour
le décalage de VFO à l'émission (PR #125) : il commande le poste pendant
l'émission et n'a jamais été vérifié sur l'air ni contrôlé sur un WebSDR.

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

### 🔴 L'incident du 19/08/2026 — le carnet perdu

À lire avant tout ce qui touche à la persistance.

**Ce qui s'est passé.** En redémarrant après une série de modifications, F4GLD
a retrouvé son carnet **vide**. 9 871 QSO, de 2011 à 2026. Ils ont été
récupérés : d'abord par *carving* de la base SQLite (lecture des pages
libérées, ~9 859 fiches reconstituées à partir des ancres `{"` remontées à
l'envers — les tableaux de pointeurs de cellules des pages libérées sont
périmés, une première tentative appuyée dessus rendait 0), puis complétés en
réimportant l'ADIF d'origine qui traînait encore. Décompte actuel vérifié
auprès du serveur en direct (`/log/status`) : **9 871**.

**La cause racine n'a JAMAIS été identifiée.** C'est le point important, et il
ne faut pas laisser croire l'inverse. Ont été éliminés **par la mesure**, pas
par raisonnement : la remise à zéro, le vidage par archivage, les quatre
chemins de synchronisation, et la suite de tests. Sur ce dernier point, un
agent avait désigné la suite de tests comme « candidat principal » ; je l'ai
**réfuté moi-même en mesurant** — les bases des worktrees contiennent bien
F1TEST/F2AAA/F2BBB/F3CCC, la base de production en contient zéro, parce que le
répertoire de travail est calculé depuis `__file__`. Ne pas rouvrir cette piste
sans mesure nouvelle.

**Ce qui a été fait à la place — fermer le goulot, pas une porte** (PR #127,
fusionnée). Toute destruction massive passe par `concours/logx_storage.py` :
c'est là que les trois garde-fous ont été posés, plutôt que sur le chemin
soupçonné du jour.

1. **Refus d'écriture destructrice.** `_ecrire_tout()` compare ce qu'il y a sur
   disque à ce qu'on s'apprête à écrire ; au-delà de `_SEUIL_PERTE_MASSIVE = 25`
   fiches perdues, il lève `ReecritureDestructrice` et la base reste intacte.
   Les effacements **voulus** passent par `effacement_autorise=True` et
   continuent de marcher.
2. **Journal d'appoint append-only.** Quand l'écriture est bloquée, les QSO
   suivants partent dans `logx_journal_secours.jsonl` (`flush` + `os.fsync`),
   rejoué puis renommé au démarrage — sans quoi le gel serait un second
   désastre. ⚠️ Défaut trouvé en cours de route : le journal n'était rejoué que
   si la base existait. Corrigé.
3. **Verrou du DOSSIER de données** (`logx_singleton.py`, `msvcrt.locking` sous
   Windows, `fcntl.flock` ailleurs). Deux LogX AI dans le même dossier
   finissaient par s'effacer mutuellement. Un `.pid` ne convenait pas : il se
   libère à la mort du processus, et `os.kill(pid, 0)` **tue** sous Windows.

Et un bandeau rouge permanent sur les 15 pages (`logx_statusbar.js`, via
`/log/status`) : un blocage de persistance ne doit pas être silencieux.

> 🚨 **Piège payé deux fois pendant ce correctif** : un `except Exception:
> return True` avalait un `NameError` (`os` non importé dans
> `logx_singleton.py`) et faisait annoncer un verrou jamais pris. Trouvé
> seulement en lançant **deux vrais processus**. J'ai refait exactement la même
> erreur ensuite dans `logx_serveur.py` — rattrapée par `ruff` (F821). Ne pas
> écrire de repli muet sur ce chemin.

**Ce qui reste à faire ici** : la sauvegarde automatique est toujours
**inactive tant qu'aucun dossier n'est renseigné**, et le champ est vide à
l'installation. C'est ce qui a rendu l'incident irréversible. Le guide le dit
maintenant (chapitre 2 et §14.4), mais **le logiciel, lui, ne le réclame
toujours pas** au premier lancement. Une invite au démarrage tant que le
dossier est vide serait le vrai correctif, et elle n'existe pas.

### 🔴 Rien de tout cela n'est publié

`concours/logx_version.py` annonce `1.1-beta4`, et le dernier tag publié est
`v1.1-beta4`. Or **32 commits sont sur `main` depuis ce tag** (vérifié par
`git rev-list --count v1.1-beta4..main`), dont la PR #127 ci-dessus.

Autrement dit : **les garde-fous qui protègent le carnet ne sont dans aucun
binaire téléchargeable.** Quiconque installe LogX AI aujourd'hui prend la
version d'avant l'incident. La publication d'une `v1.1-beta5` a été commencée
puis suspendue, et jamais reprise.

Avant de pousser le tag : **vérifier le build PyInstaller en local d'abord**.
Un build de release est resté cassé deux jours sans que personne le sache
(`Tree()` vs `Analysis()`), et seul un vrai build local l'avait révélé.

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

4. ✅ **FAIT — 25 concours proposés dans l'interface rendaient zéro bande.**
   Corrigé le 19/08/2026 par l'accesseur `bandes_du_concours()` décrit plus
   bas, branché sur les onze sites qui lisaient `bands` à plat. 15 concours
   retrouvent leurs bandes, les 10 ambigus restent volontairement vides et
   leur liste est désormais **verrouillée par un test** — elle ne peut que
   rétrécir. Ce qui suit est conservé parce que le raisonnement, lui, reste
   utile : il explique pourquoi on n'a PAS fabriqué de définitions, et ce
   qu'il resterait à faire pour les 10 derniers.

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

   ⛔ **La recette écrite ici le matin du 19/08 était INAPPLICABLE — ne pas
   la suivre.** Elle proposait de fabriquer une définition minimale
   (`name`/`bands`/`modes`) marquée `'derive_du_bareme': True` et de l'insérer
   dans `CONTEST_DEFINITIONS`. C'est impossible, pour trois raisons vérifiées
   dans `concours/contest_schema.json` :

   - le schéma exige **huit** champs : `name`, `organizer`, `date_rule`,
     `bands`, `modes`, `exchange`, `scoring`, `log_format` ;
   - il porte `"additionalProperties": false` — la clé `derive_du_bareme`
     ferait donc échouer la validation à elle seule ;
   - `date_rule` est contraint par une expression régulière stricte
     (`first_saturday_july`, `last_full_weekend_october`…), interprétée par
     `calc_contest_date`.

   Et ce n'est pas théorique : la CI (`check.yml`) lance
   `python logx_validate.py` de façon **bloquante** contre ce schéma. Une
   entrée dérivée serait rejetée ; compléter `date_rule`, `exchange` ou
   `log_format` de tête reviendrait à inventer des valeurs de domaine, ce que
   le dépôt interdit sans source citable.

   **Recette correcte : un ACCESSEUR, pas une entrée fabriquée.** Le défaut à
   corriger est le symptôme — `…get('bands', [])` rend `[]`. Introduire dans
   `logx_definitions.py` une fonction du genre `bandes_du_concours(cid)` qui
   lit d'abord `CONTEST_DEFINITIONS[cid]['bands']`, et à défaut analyse la
   chaîne de `CONTEST_SCORING[cid]['bands']` (rendre `[]` dès qu'un `-` ou un
   mot apparaît, ce qui écarte les 10 ambigus tout seul, sans liste noire).
   Puis remplacer les consommateurs par cet accesseur — ils sont listés
   ci-dessus. `CONTEST_DEFINITIONS` n'est pas touché, le contrat public n'est
   pas modifié, rien n'est inventé, et `logx_validate.py` reste vert.

   Si un jour on veut de vraies définitions pour ces concours, c'est un
   travail de SOURCES (lire les règlements REF pour en tirer date, échange,
   format de log), pas un travail de conversion. Ne pas confondre les deux.

   **Ce qui reste ouvert ici**, et c'est le seul reliquat : les 10 concours
   dont le barème est une plage ou un mot — `CUSTOM`, `F9NL`,
   `UFT_RENCONTRES`, les quatre TVA, `REF_CHALLENGE_THF`, `REF_F8TD`,
   `REF_IARU_UHF`. Ils rendent toujours `[]`, volontairement. Pour en sortir
   un, il faut lire son règlement et lui écrire une vraie définition conforme
   au schéma, puis le retirer de `AMBIGUS_CONNUS` dans
   `tests/test_concours_sans_definition.py`. Le test refusera qu'on élargisse
   cette liste sans le vouloir, et refusera aussi qu'on y laisse un concours
   résolu.

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

5. ✅ **SOLDÉ — les 5 « constats restants » de la 3e revue.** Vérifiés
   indépendamment le 19/08/2026, puis les confirmés soumis à réfutation.
   **Aucun des cinq n'était à corriger tel qu'énoncé.**

   | Constat consigné | Verdict |
   |---|---|
   | changement de MODE D'ENVOI qui tue le QSO | **déjà corrigé**, garde-fou structurel |
   | « (sans plafond) » menteur | **déjà corrigé** — la chaîne ne subsiste que dans DEUX COMMENTAIRES |
   | double-clic sur un 73 qui repart en TX1 | **déjà corrigé** |
   | offre de log écrasée | **réfuté** — le scénario exigeait 3 indicatifs et 2 échecs, et trois traces restent à l'écran |
   | six raisons d'arrêt non couvertes | **réfuté** — sur 8 sites, 6 sans conséquence sur l'air ; « 6 » venait d'un changement d'unité en cours de démonstration |

   **La leçon vaut plus que le résultat.** Cette liste était consignée comme
   du travail restant ; s'y fier aurait fait « corriger » deux défauts
   inexistants, et le cas du « (sans plafond) » est l'illustration exacte du
   piège maison : un test cherchant la chaîne l'aurait trouvée dans le
   commentaire qui EXPLIQUE l'ancien défaut. **Ne jamais reprendre un constat
   de revue — même le sien — sans le remesurer.**

   **Ce sont les RÉFUTATIONS qui ont trouvé les vrais trous**, tous deux
   corrigés depuis (PR #136) :

   - **« Ignorer » perdait la fiche.** `marquerNonEnregistre` n'avait qu'UN
     site d'appel (`offrirLogQso`, indicatif différent). Après un échec
     d'écriture le bandeau reste ouvert exprès, et le seul geste qui le
     referme — « Ignorer » — vidait la fiche sans rien poser. Un clic, un
     indicatif, plus rien. Un drapeau `qsoEchecEcriture` distingue désormais
     « je refuse ce QSO » de « je referme un bandeau ».
   - **Le bouton STOP n'était tenu par aucun test.** `window.seqStop` :
     0 occurrence dans les 16 fichiers de tests FT8. On pouvait le rendre
     inerte sans qu'un test ne rougisse, sur le bouton qui arrête une
     émission automatique.

   ⚠️ **Pour toute suite sur cette page** : un banc de COMPORTEMENT y est
   vacant. Les mannequins DOM (`__El`/`__El2` dans `test_ft8_sequenceur.py`)
   n'ont ni `querySelector` ni `remove`, et leur `innerHTML` n'est qu'une
   chaîne — poser `innerHTML=''` n'y vide pas `children`. Un test « la ligne
   rouge survit » passe au VERT avec le défaut en place. Assertions
   structurelles, ou banc étendu, ou vérification navigateur.

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
