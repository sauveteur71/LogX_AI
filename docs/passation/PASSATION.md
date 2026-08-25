# Passation — reprendre LogX AI sur un nouveau compte

Écrit le 19/08/2026, à la demande de F4GLD dont le compte Claude arrivait à
échéance. Ce document est dans le DÉPÔT, pas dans une session : c'est lui qui
survit au changement de compte.

**Mise à jour le 22/08/2026** (nouveau changement de compte) : section 1
revérifiée et corrigée (version publiée, PR fusionnées depuis le 19/08,
nouvel item en attente d'essai sur l'air), mémoire condensée recopiée dans le
dépôt (§4). Le reste du document (méthode, conventions) n'a pas eu besoin de
changer.

**Mise à jour le 24/08/2026** : chantier **AFFICHAGE** (rendre configurable ce
que montre chaque page) mené étapes 1→4 et FUSIONNÉ — voir la sous-section
dédiée dans la section 1. Un piège de rebase y est consigné (une PR branchée
avant sa précédente aurait effacé le travail de celle-ci).

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
| #178 | **Page d'accueil par activité** (`logx_accueil.html`) : remplace le mode simple/expert comme axe premier de l'UI, décision F4GLD du 19/08. Seule LOG V/UHF filtre réellement à ce stade (doctrine : valider sur une activité avant les 18 autres). Inclut aussi le lien profond PROPAG depuis LOGBOOK. |
| #179 | **FT8 : mode Automatique** (CQ + QSO en totale autonomie, 22/08) + panneau QSO en cours séparé de l'activité de bande. Voir « En attente d'un essai sur l'air » ci-dessous — **c'est le nouvel item le plus important de cette section**. |
| #234 | **AFFICHAGE étape 1** : panneaux du LOGBOOK togglables (base + aménageable). |
| #235 | **AFFICHAGE étape 2** : presets d'affichage PAR ACTIVITÉ (`ACTIVITY_DISPLAY_PRESETS` dans `logx_statusbar.js`) — débutant minimal, expert = tout. |
| #236 | **AFFICHAGE étape 3** : profils d'affichage NOMMÉS + export/import JSON (partage entre postes/club, sans serveur). Noms utilisateur échappés (anti-injection). |
| #237 | **AFFICHAGE étape 4** : une DISPOSITION capture aussi l'affichage in-page (bascules AFFICHAGE), pas seulement les fenêtres détachées → « espace de travail » complet. Rétro-compat : une ancienne disposition sans champ `display` ne touche pas l'affichage courant. |

#### Chantier AFFICHAGE (étapes 1→4) — FAIT et FUSIONNÉ le 24/08/2026

Rendre configurable ce que chaque page affiche, dans l'esprit « l'axe est
l'activité, pas un niveau déclaré » (cf. `CLAUDE.md`). Tout se joue dans
`concours/logx_statusbar.js` (le menu ⚙ AFFICHAGE, partagé sur les 15 pages) et
dans `localStorage` — **aucun endpoint serveur, aucun `.py`**. Les quatre
incréments (#234→#237) coexistent sur `main`, vérifié : presets #235, profils
#236 et capture-affichage #237 présents ensemble, sans régression.

Vérifications faites (méthode du dépôt, section 2) : témoin vert + contre-épreuve
par mutation avec contrôle md5 sur #236 et #237, `ruff` propre, et **rendu réel
capturé en Chrome headless dans les DEUX thèmes** (jour ET nuit) pour #236 — le
nom de profil `SOTA <portable>` s'affiche littéralement, ce qui prouve
visuellement l'échappement anti-injection.

> 🚨 **Piège de rebase, à retenir.** #237 avait été branché depuis l'étape 1
> (#234), AVANT que l'étape 2 (#235) soit fusionnée. Son diff CONTRE `main`
> « supprimait » donc tout le bloc des presets d'activité de #235 — **pur
> artefact de base périmée**, pas une intention. Le fusionner tel quel aurait
> effacé #235 (régression réelle et silencieuse). Diagnostic : comparer le
> commit à SON PROPRE parent (`git diff 3f51d18~1 3f51d18`) montrait que le
> vrai changement n'était que 2 hunks (saveLayout/loadLayout). Correctif :
> rebase sur `origin/main` → conflit nul (les 2 hunks ne touchent pas les zones
> de #235/#236), diff net réduit aux 2 vrais hunks, presets #235 et
> `expert-only` intacts. **Toujours lire le diff d'une PR contre son parent
> réel, pas seulement contre `main`, avant de juger ce qu'elle change.**

⚠️ **Après le resync de la branche live du 24/08** : le merge `origin/main` a
tiré bien plus que ces 4 PR (≈38 commits : tropo, validate, winkeyer, parsers
SOTA/WWFF, etc.), dont **11 `.py` de production** — donc le serveur 8080 DOIT
être redémarré pour les prendre (les `.py` ne sont pas relus à chaud). Les 4 PR
AFFICHAGE seules n'auraient pas exigé de redémarrage (JS/HTML uniquement).

La branche d'intégration locale est `local/live-8080-combined` — c'est celle
que sert le serveur sur le port 8080. Elle est à jour (diff vide avec
`origin/main`, resynchronisée et vérifiée le 24/08/2026 — mais voir
l'avertissement « 11 `.py` » ci-dessus : redémarrage du serveur requis).

⚠️ `.claude/launch.json` (config `logx-serveur` pour l'aperçu navigateur)
pointait vers un chemin périmé (`RADIOAMATEUR/Programme pour contest`,
l'ancien emplacement du dépôt avant réorganisation) au lieu du dépôt actuel —
corrigé le 22/08/2026, mais ce fichier est dans `.gitignore` (config locale
par machine) : si le nouveau compte tourne sur une AUTRE machine, il faudra
recréer ce fichier localement, pas s'attendre à retrouver le correctif via
git. Une seconde config morte (`pttrts-statique`, worktree disparu) a été
supprimée du même fichier.

> ⚠️ **Le serveur doit être redémarré** pour prendre les correctifs Python.
> Les fichiers `.html`/`.js` sont relus à chaque requête, pas les `.py`.

#### Nuit du 24→25/08/2026 — sous-projets ADIF/IA + couverture concours/activités

Session autonome (F4GLD absent, consigne « ne t'arrête pas »). Tout en
TDD + contre-épreuve par mutation (md5) + `ruff`, chaque lot revu en
adversarial avant fusion, suite complète verte re-vérifiée sur `main`
après chaque batch (leçon #242 : jamais fusionner sur CI rouge, toujours
relancer la suite ENTIÈRE après un merge). PR fusionnées :

| PR | Ce que ça fait |
|---|---|
| #244 | **Sous-projet B — cohérence export/import ADIF** : clés de saisie, réfs multiples, confirmations à anti-dup dynamique, symétrie import, régressions round-trip. INVARIANT posé : tout tag émis dans `_ADIF_STD_TAGS` doit avoir un mapping d'import, sinon perte silencieuse au round-trip (classe de bug trouvée en revue B). |
| #245 | **IA-1 — validation déterministe du log** (`logx_controles.py`) : contrôles purs freq↔bande, date future, heure de fin, RST↔mode (sous-modes via `_mode_effectif`), réf d'activation ; `resume_controle`. Bug corrigé en revue : `MAX_FINDINGS` ne doit jamais faire tomber une `erreur`. |
| #246 | **Fix ADIF sous-modes MFSK** : FT4/JS8/Q65/FST4 exportés `MODE=MFSK`+`SUBMODE=X` (jamais `MODE=FT4`), via `_SUBMODE_PARENT`. Jumeaux Python/JS synchronisés. |
| #247 | **IA-2 — enrichissement déterministe** (`logx_enrichissement.py`) : dérive pays DXCC/continent/zones CQ+ITU/distance/azimut + champs `my_*`, injecté à l'export sous `completer=` (uploads restent légers). Bug corrigé en revue : ne pas court-circuiter les 3 sources si l'indicatif est inconnu. |
| #248 | **Activations WWBOTA (bunkers) + ILLW (phares)** dans `PROGRAM_SPECS`. |
| #249 | **Export CSV serveur** (`build_csv`, jumeau du CSV client) + archive `.csv`. |
| #250 | **Agent `ham-radio-expert` + skills** (`tx-human-consent`, `adif-validation`) dans `.claude/`. |
| #251 | **Sûreté TX — backend « émission unique »** (`logx_tx_consent.py`) : jeton `TxConsent` (uuid4, expire 30 s, usage unique, invalidé au changement radio), `authorize_transmission` relit le CAT réel avant PTT, journal d'audit UTC, Stop TX global. Datetimes aware-UTC, `now` injectable. **Backend seul — non câblé au PTT réel** (endpoints/UI/Stop TX = chantier suivant, demande un avis design F4GLD). Applique la contrainte verbatim : « l'IA peut préparer une action TX, jamais la déclencher d'elle-même ». |
| #252 | **Bande 60m = clé unique `'5'`** (5 MHz), pas des canaux — décision F4GLD. Jumeaux scoring `_band_from_freq` + wsjtx `_mhz_to_band` + `ADIF_BAND['5']='60m'` + toggle contest. Le band-plan IARU R1 (`bandplan_iaru_r1.json`) contenait déjà 60m (5.3515–5.3665) : `en_bande_amateur` le reconnaît, rien à ajouter là. |
| #253 | **Concours RTTY** (en cours de fusion) : CQ WW RTTY + ARRL RTTY Roundup, valeurs sourcées (cqwwrtty.com / arrl.org). Presets `zone_country_per_band_rtty` (1/2/3) et `rtty_roundup` (1 pt). |

**Item scopé, non fait (demande un arbitrage F4GLD)** : les multiplicateurs
états/provinces W/VE des deux concours RTTY (CQ WW RTTY §IV.C.3 combiné
zone+DXCC+état par bande ; RTTY Roundup mult all-band états+provinces+DXCC).
Ils touchent le moteur PARTAGÉ de classement de spots (`build_ranked_spots`
/ `MULT_EVALUATORS`, cf. `logx_scoring.py`) que TOUS les concours utilisent —
chirurgie non spéculative écartée en l'absence de F4GLD (les QSO se comptent
déjà correctement zone+DXCC ; il ne manque qu'un multiplicateur secondaire).

#### Journée du 25/08/2026 — items 1 & 2 (« attaque 1 et 2 ») + barre d'émission

F4GLD présent par intermittence, demande « attaque 1 et 2 » puis « lance ».
Même méthode (TDD + mutation md5 + revue adversariale + CI verte avant merge).
PR fusionnées :

| PR | Ce que ça fait |
|---|---|
| #254 | **Item 1 — multiplicateurs RTTY (score AUTORITAIRE)**. Valeurs SOURCÉES : CQ WW RTTY (cqwwrtty.com §IV.C) = zones CQ + DXCC + états US(48)/DC/aires canadiennes(14) des W/VE, PAR BANDE (AK 'KL'/HI 'KH6' = pays seulement) ; ARRL RTTY Roundup (PDF officiel §5.3) = 1 pt × (états + provinces + DXCC hors US/Canada), UNE FOIS ALL-BAND. Nouveaux kinds `zone_dxcc_state` (per-band) + `rtty_ru` (is_global) dans `calc_total_score`/`_mult_entries`. Discriminant état = `country_key in {'K','VE'}`, code depuis `num_rcvd`. **Le client affiche déjà le score autoritaire serveur** (A10) → correction remonte automatiquement, pas de twin JS à faire. Régression rattrapée par la CI : mon propre test #253 figeait l'ancien `multiplier is None`. |
| #255 | **Item 2 — câblage backend + PTT du consentement TX** (F4GLD : « backend + déclenchement PTT complet »). Étend `logx_tx_consent` : verrou TX serveur (`lock_tx`/`unlock_tx`/`is_tx_locked`, posé par `stop_tx`), `radio_state_from_cat()` (mappe `cat.get_state` freq_hz/mode/ok/enabled → contrôle ; **power_w reporté du jeton car le CAT ne lit pas la puissance** — décision documentée ; ptt_locked = verrou serveur), journal d'audit en mémoire UTC (façon `logx_cw_journal`). Endpoints minces `logx_http` : `POST /tx/prepare|authorize|stop|rearm`, `GET /tx/audit`. `/tx/authorize` : garde-fou mode/bande (read-only) → `authorize_transmission` (consomme le jeton) → PTT RÉEL borné via le chemin existant (verrou SO2R + chien de garde voicekeyer). Durée bornée obligatoire. |
| #256 | **Barre d'émission du LOGBOOK** (`logx_tx_bar.js`) — surface client, **maquette validée par F4GLD (« magnifique »), emplacement barre en pied de page**. Identité graphite & cuivre (tokens de la page, thèmes auto). `LogxTxBar.proposer({...})`→`/tx/prepare`, bouton ÉMETTRE→`/tx/authorize`, STOP TX→`/tx/stop`. Compte à rebours du jeton, ligne d'état. Logique pure testée en V8 (7 tests, mutation). Maquette de référence : `docs/maquettes/tx_barre_emission.html`. |

**Le test SUR L'AIR reste le geste de F4GLD** (écrire ≠ émettre). Vérif
navigateur de la barre = déclencher `LogxTxBar.proposer(...)` sur l'instance live.

**Piège récurrent noté** : la suite complète LOCALE se bloque par intermittence
sur un test réseau (~65 %, jamais identifié précisément) ; la CI (« harnais
mock », env propre) fait foi pour le vert de la suite complète, comme depuis #251.

#### Après-midi du 25/08/2026 — chaîne d'émission complète + concours/activations

Suite de « enchaîne ». Toujours TDD + mutation md5 + ruff + CI verte avant merge.

| PR | Ce que ça fait |
|---|---|
| #256 | **Barre d'émission du LOGBOOK** (`logx_tx_bar.js`) — surface client validée par F4GLD (« magnifique »). Barre en pied de page, identité graphite & cuivre. `LogxTxBar.proposer()`→prepare, ÉMETTRE→authorize, STOP TX→stop. Logique pure testée V8. Maquette : `docs/maquettes/tx_barre_emission.html`. |
| #257 | **`/tx/authorize` émet le CONTENU par mode** : CW → `wk.envoyer` (keyer), phonie → `vk.envoyer_message` (slot WAV). Dispatcher pur `emettre_message`. Verrou SO2R par famille. |
| #258 | **Choix voix WAV/TTS (offline-first)** + sélecteur dans la barre. `voice_source` ('wav'/'tts'/'auto') + `voice_source_effectif`. La cascade IA cloud→Piper local→voix système est DÉJÀ dans `logx_voicekeyer.synthesize_to_wav` — on ne branche que le choix. « Marche sans accès, profite d'internet/IA si présents » (principe zone blanche). |
| #259 | **Concours FT Roundup** (FT4/FT8) — SOURCE rttycontesting.com. Même barème que l'ARRL RTTY Roundup (kind `rtty_ru`). DISCONTINUÉ (logs historiques). Corrige la note ARRL (mult automatisé depuis #254). |
| #260 | **Activation GMA** (Global Mountain Activity) — sommets hiérarchiques, 4 QSO min, réf format SOTA (SOURCE cqgma.org). *(en attente CI au moment d'écrire)* |
| #261 | **Concours FT Challenge** (successeur ACTIF du FT Roundup) — barème DIFFÉRENT : points 1+1/3000 km, mult champ de grille 2 car par bande. 2 briques neuves (`per_grid_3000`, kind `grid_field`). *(en attente CI)* |

**La chaîne « émission unique » est complète de bout en bout** : l'IA prépare
(`proposer`) → la barre affiche (avec choix voix) → l'humain valide (ÉMETTRE) →
contrôle CAT réel + garde-fou → PTT + émission du CONTENU (CW texte / WAV /
TTS selon accès) → journal d'audit. **Stop TX** coupe tout. Le **test sur l'air
reste le geste de F4GLD**.

**Reste de la roadmap copilote IA** : le **déclencheur IA réel** — FAIT
ci-dessous (copilote FT8). Autres : câblage endpoints TX au PTT réel déjà fait
(#255/#257) ; UI de confirmation faite (#256) ; FT Challenge/FT Roundup/GMA
faits ci-dessus.

#### Soir du 25/08/2026 — copilote FT8 (déclencheur IA, 1re brique)

Cadré avec F4GLD (spec `docs/superpowers/specs/2026-08-25-ft8-copilote-declencheur-design.md`).
Décisions : répondre à un appel FT8 ; **l'IA propose, l'humain confirme CHAQUE
émission (jamais d'auto-émission)** ; approche **X** (pilotée par les décodes,
n'utilise PAS la boucle temporisée du séquenceur). Boucle complète :

| PR | Ce que ça fait |
|---|---|
| #262 | **Copilote FT8 — répondre à un appel**. Sur un décode « pour moi » au niveau `copilote`, l'IA calcule la réponse standard (`reponseFt8` : grille→report, report→R+report, R+report→RR73, RRR/RR73/73→fin — table protocole SOURCÉE F4GLD) et la PROPOSE dans la barre #256 ; ÉMETTRE → `envoyerMessage()` au prochain créneau. Barre étendue `proposer(em, onConfirm)` (chemin client, FT8 = mode data hors serveur voix/CW). |
| #263 | **Copilote FT8 — répondre à un CQ** (double-clic → propose l'appel initial `appelInitial`). *(mergé)* |
| #264 | **Copilote FT8 — journaliser le QSO à la clôture** (l'approche X décode-driven contourne la boucle du séquenceur ; suivi d'état + `offrirLogQso` à RR73/73). *(mergé)* |
| #265 | **Copilote FT8 — file d'attente pile-up** (10 max, à la suite). `ajouterFile`/`retirerFile`/`prochainFile` ; priorité : station cliquée (copain) > nouveau DXCC (`/dxcc/besoin`) > FIFO. UI file + ★ nouveau DXCC. *(mergé)* |
| #266 | **Copilote FT8 — niveau 2 `copilote_auto`** (« délai fixe puis émet sauf annulation », F4GLD). `delaiAutoMs(niveau, defaut)` (>0 seulement à `copilote_auto`) ; barre `proposer(em, onConfirm, autoMs)` : `_autoAt` armé, `_tick` auto-émet UNE fois via **le même callback** que le niveau 1 (propriété propose-only intacte), STOP TX/ÉMETTRE annulent. Décompte visible (`autoSecondsLeft`). Délai **réglable** 3/5/8/12 s (`delaiValideMs`, borné [2,30] s, persistant `rc_ft8_copilote_delai_s`). Option + texte d'état dédiés. **Traçabilité (arbitrage F4GLD 25/08)** : le FT8 émet côté client (hors `/tx/authorize`) → la barre POSTe `/tx/trace` au déclenchement (ÉMETTRE **ou** délai écoulé) ; `journal_copilote_emission` grave l'émission dans le MÊME journal d'audit serveur (`event:TX_COPILOTE_EMISSION`, `declencheur` copilote/copilote_auto), consultable via `/tx/audit` — même si le navigateur est fermé ensuite. Fire-and-forget (une trace ratée ne défait jamais une émission). **Fiabilisation pile-up (choix F4GLD « fiabiliser »)** : (a) **péremption** — `epurerFile(file, vu, now, maxAge)` retire une station qui ne rappelle plus (non réentendue > ~6 cycles = 90 s, `_copiloteFileVu` suit le dernier appel, purge à chaque décodage) ; (b) **lien trace↔QSO loggé** — à l'écriture RÉELLE d'un QSO copilote (confirmation humaine, non-doublon) la page POSTe `/tx/trace kind:'qso'` → `journal_copilote_qso` grave `TX_COPILOTE_QSO_LOGGED` (même indicatif que les `TX_COPILOTE_EMISSION` → boucle consentement→émission→QSO tracée de bout en bout). Le log reste un geste humain. **Afficheur d'audit (demande F4GLD « faut le faire aussi »)** : `LogxTxBar.formatAuditLigne(entry)` (pur, testé) rend chaque entrée `/tx/audit` en une ligne FR ; panneau repliable « Journal d'émission » sur la page FT8 (sous la file copilote), lecture seule, `textContent` (jamais innerHTML), tokens de charte (jour/nuit). Rend enfin CONSULTABLE la traçabilité gravée. *(mergé)* |

🚨 **SÛRETÉ verrouillée par tests structurels + mutation sur les DEUX chemins** :
au niveau `copilote`, le seul `envoyerMessage` est DANS le callback ÉMETTRE →
**aucune auto-émission possible**. Séquenceur existant (manuel/assisté/
séquenceur/auto) **inchangé** (non-régression verte). Nouveau niveau `copilote`
dans le `<select>` de `logx_ft8.html`. Déterministe, zéro réseau (zone blanche).

**Piège rebase (rappel #237, revécu)** : #263 empilé sur #262 squash-mergé →
`git rebase` rejouait les commits déjà squashés (conflit). Correctif :
`git rebase --onto origin/main <dernier-commit-262>` pour ne rejouer QUE le
commit propre de #263.

**VÉRIF NAVIGATEUR = geste F4GLD** (avant usage on-air) : page FT8 → niveau
Copilote → décode simulé « pour moi » → la barre s'affiche → ÉMETTRE → FT8 part
au prochain créneau ; thèmes jour/nuit. **Niveau 2 (#266)** : choisir « Copilote
auto », vérifier le sélecteur DÉLAI (3/5/8/12 s), qu'un décode « pour moi »
propose PUIS émet seul après le délai affiché, et que **STOP TX** annule dans la
fenêtre — puis re-tester en jour/nuit.

**Suite copilote (demande direction produit F4GLD)** : niveau 2 (`copilote_auto`,
semi-auto temporisé) **FAIT** (#266) ; pile-up **FAIT** (#265). Restent :
niveaux 3-4 (fenêtre de confiance élargie / TX encadrée) ; copilote CW/SSB ;
journaliser le lien consentement→QSO ; (noté, non demandé) péremption d'une
station en file (stale-timeout).

#### Nuit du 25→26/08/2026 — copilote CW/SSB + aides « départements » LOGBOOK

Suite directe du fil FT8, tout **mergé sur main**, chaque PR TDD +
contre-épreuve par mutation + ruff + CI verte. Ordre chronologique :

| PR | Ce que ça fait |
|---|---|
| #267 | **Copilote CW/SSB — préparer l'échange à l'indicatif résolu** (choix F4GLD : déclencheur = lookup de l'indicatif, pas un décode). `logx_cwssb_copilote.js` : `familleMode(mode)`→`cw`/`phonie`/`null`, `doitProposer(actif,call,mode)`, `messagePropose(...)`, `cle(call,txMsg)`. **Propose-only** (jamais d'émission spontanée) — cohérent avec le garde-fou TX unifié. |
| #268 | **LOGBOOK — auto-remplir le PRÉNOM du correspondant** (capture WinREF F4GLD : prénom + drapeau + locator dès la saisie de l'indicatif, corrigeable). `merge_calldb_entry(entry, locator, dept, name)` (pur) ; endpoints `/calldb/update` (stocke le nom), `/calldb/lookup` (le rend) ; champ `#inputName` éditable, le prénom saisi **prime** sur l'annuaire. Base interne d'abord, puis repli réseau (QRZ). |
| #269 | **LOGBOOK — amorcer la base interne des prénoms depuis le journal** (backfill). `enrich_calldb_from_log(shared_log, calls)` (pur) + `POST /calldb/enrich_from_log` : les prénoms déjà présents dans les QSO passés peuplent l'annuaire local sans réseau. |
| #270 | **LOGBOOK — grille départements 00–99** (clic direct) pour l'échange-département, + **override dept**. `logx_dept_grid.js` : `codesMetro()` (01-95 + 2A/2B), `doitAfficher(labelR)`, `champCible(labelR, estVhf)`, rendu + surlignage travaillés. Champ `#inputDept` saisi **prime** sur le locator dans `dept_for_qso` (« grand OUI » VHF/UHF F4GLD). Carte `logx_departements.html` : départements NON faits en rouge « à faire » (#E5544B), légende verte/rouge. |
| #271 | **fix — `department_targets()` aveugle aux indicatifs jamais loggés** (bug bloquant, priorité #1 F4GLD). Résolution du dept d'un spot unifiée : historique → `dept_from_locator` local (indicatif FR) → repli réseau `_resolve_spotted_live`. Le panneau n'est plus structurellement incomplet quand un chasseur jamais loggué apparaît sur un département manquant. |
| #272 | **Panneau « départements À FAIRE » — tri fréquence (défaut) + bascule rareté** (décisions F4GLD). `logx_dept_todo.js` : `trier(targets, mode, freqMhz)` **pure** — mode `freq` : le dept dont le donneur spotté est le plus proche de la fréquence courante en tête (**minimise le QSY**), donneurs triés par proximité ; mode `rarete` : moins de stations connues d'abord. Bouton bascule `#deptTodoTri`, mode persisté (`rc_dept_todo_tri`), re-rend sans refetch. Le clic (QSY + QSO pré-rempli) et la source (spots cluster) préexistaient. |
| #273 | **LOGBOOK — heure de fin (`time_off`) AUTOMATIQUE** (demande F4GLD « l'heure doit être entrée automatiquement à l'enregistrement »). Champ manuel « HEURE DE FIN (UTC) » supprimé ; à l'enregistrement `qso.time_off = qso.time.replace(':','')` (fin = début, chiffres nus, même format que TIME_ON à l'export et que `controle_heure_fin`). `time_off` **reste une clé interne** (symétrie import/export ADIF + contrôle inchangés) ; seule la frappe disparaît. Édition d'un QSO importé préserve son `time_off` distinct (chemin `logx_edit_qso.js` séparé). |

**Vérif d'intégration** : les 8 PR (#266→#273) ensemble sur `main`, tranche
pertinente **522 tests verts**, `node --check` OK sur les 3 JS clés. Worktrees
des 8 branches nettoyés.

**VÉRIF NAVIGATEUR restante (geste F4GLD)** : #272 (bouton ≈fréq/★rareté, tri
qui bouge selon la fréquence du poste) et #273 (plus de champ heure de fin,
heure gravée à l'enregistrement) non encore vérifiés en navigateur dans les
deux thèmes — à faire avant de considérer clos côté UI.

#### 26/08/2026 — autonomie zone blanche + outillage vidéo

| PR | Ce que ça fait |
|---|---|
| #274 | **Repli CDN local** (demande F4GLD, lève le verrou de la fiche « ne pas corriger sans demande »). Leaflet 1.9.4 + Chart.js 4.5.1 **vendorisés** dans `concours/vendor/` (leaflet.min.js/css + images/, chart.umd.min.js), stockés verbatim (`.gitattributes : concours/vendor/** binary`). 5 pages (carte, départements, logbook, wall, websdr) repointées local (`/vendor/…`, sans SRI — même origine) → **zéro CDN externe .js/.css** (une station /P en zone blanche charge la carte + les stats au lieu de mourir sur `L`/`Chart` undefined). `logx_sw.js` précache les 3 libs (SHELL, CACHE v1→v2). **Vérifié ≠ cru** : la « regex cassée sw.js:29 » de la fiche était FAUSSE pour le code actuel (`logx_sw.js`, regex ancrée `(\/|$)`, déjà corrigée) → non touchée. `test_sri_cdn_externe` repurposé : contre-épreuve « ≥5 CDN » → invariant PLUS FORT « zéro CDN externe ». Hors scope assumé : Google Fonts `@import`. |
| #275 | **Skill projet `radio-video-analysis`** (`.claude/skills/`, git-tracké, même convention que `adif-validation`/`tx-human-consent`). Complément métier du plugin `watch` (`bradautomates/claude-video`, `/watch` = téléchargement + frames horodatées + transcription) : `watch` fait VOIR/ENTENDRE la vidéo, ce skill dit QUOI extraire (radio/firmware/logiciel/CAT/série/CI-V/mode/PTT/split/audio/FT8/câblage/menus/erreurs + timestamps) et COMMENT le restituer. Garde-fous : CONFIRMÉ/PROBABLE/INCONNU, jamais une commande CAT universelle, comparer au manuel officiel, JAMAIS de PTT/RF, jamais de secret copié. `disable-model-invocation: true` → `/radio-video-analysis` seulement. |

**Outillage `watch` (hors dépôt, poste F4GLD)** : dépendances préparées —
`ffmpeg` déjà présent (winget v9.0, PATH), `yt-dlp` installé (pip 2026.08.19)
et son dossier ajouté au **PATH utilisateur** (winget bloqué par une erreur de
certificat = interception réseau locale, même artefact que le reset des grosses
réponses localhost). **Reste à la main de F4GLD** (commandes TUI `/plugin`
qu'un agent ne peut pas taper) : `/plugin marketplace add bradautomates/
claude-video` puis `/plugin install watch@claude-video`, puis **redémarrer la
session** pour que `watch` ET `radio-video-analysis` soient découverts.

### En attente d'un essai sur l'air

✅ **PR #179 — mode Automatique FT8 : ESSAI SUR L'AIR SUPERVISÉ FAIT
(24/08/2026, confirmé par F4GLD).** Le blocage de publication est LEVÉ, et le
mode Automatique est inclus dans le tag `v1.1-beta8` publié le 24/08/2026 (cf.
« publication » plus bas). Le contexte d'origine est conservé ci-dessous —
mais l'item n'est plus « en attente ».

🔴 (historique, résolu) **PR #179 (22/08/2026) — le mode Automatique FT8, LE PLUS PRIORITAIRE des
deux items de cette section.** Appelle CQ, décode qui répond, enchaîne
l'échange complet (grille/report/RRR/73), logue, relance CQ — SANS aucune
confirmation humaine à chaque étape, en boucle. C'est une dérogation
EXPLICITE et VOULUE par F4GLD (22/08/2026, activation TM6KJS) à la règle de
sécurité par défaut du séquenceur (« aucune émission automatique sans
confirmation humaine ») — dérogation qui ne s'applique qu'à ce 4e mode
optionnel, à double geste (menu + bouton dédié `▶ DÉMARRER APPEL CQ`), jamais
aux 3 modes existants. 111 tests, chaque garde de sécurité vérifiée par
contre-épreuve de mutation, vérification navigateur faite (visibilité
conditionnelle, thèmes jour/nuit) — mais **aucun test ne peut remplacer un
QSO réel sur l'air**, et ce mode est structurellement le plus exposé de tous
ceux du dépôt (émission en boucle, sans supervision). **Premier essai à
faire en SUPERVISÉ, jamais laissé tourner seul avant ça.**

**PR #116 — le séquenceur FT8 automatique (manuel : double-clic).** Un
double-clic sur une station déroule le QSO seul (appel, report, accusé, 73)
puis logue.

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

✅ **PR #129 — le guide utilisateur — FUSIONNÉE** (vérifié le 22/08/2026 via
`gh pr view 129`, l'affirmation précédente « ouverte, jamais fusionnée » était
périmée). Elle ajoutait à `docs/GUIDE_UTILISATEUR.md` les deux choses que
l'incident du 19/08 avait rendues urgentes : l'avertissement disant que **la
sauvegarde automatique ne tourne pas tant qu'aucun dossier n'est renseigné**,
et la réécriture du §8.6 en « Modes numériques natifs : FT8, RTTY, SSTV ». Le
guide n'a en revanche pas encore de section sur le mode Automatique FT8
(PR #179, ci-dessus) — à ajouter une fois l'essai sur l'air fait.

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

### ✅ RÉSOLU — publication à jour (`v1.1-beta8`, 24/08/2026)

Le paragraphe original (19/08) alertait sur un décalage de 32 commits entre
`main` et le dernier tag (`v1.1-beta4`), dont les garde-fous anti-perte de
carnet (PR #127) absents de tout binaire publié. **Rattrapé depuis** :
`concours/logx_version.py` annonce `1.1-beta7`, tag `v1.1-beta7` publié —
vérifié le 22/08/2026 (`git describe --tags`). Les garde-fous du carnet sont
dans cette version publiée.

✅ **Publication `v1.1-beta8` — le 24/08/2026.** `concours/logx_version.py`
passe à `1.1-beta8`, tag `v1.1-beta8` poussé, binaires Windows/macOS/Linux
construits par `build-release.yml`. Cette bêta inclut le chantier AFFICHAGE
(#234→#237), les correctifs sécurité/robustesse de la campagne du 24/08, ET le
mode Automatique FT8 (#179) — publié **après** que son essai sur l'air
supervisé a été confirmé fait par F4GLD (le blocage rouge précédent est donc
levé, cf. « En attente d'un essai sur l'air » plus haut). Le build PyInstaller
a été **vérifié en local d'abord** (EXIT 0, `LogXAI.exe` produit) avant de
pousser le tag, comme l'exige la consigne ci-dessous.

> ⚠️ **Consigne permanente pour tout futur tag** : `APP_VERSION` doit être
> bumpé AVANT le tag (sinon l'appli se croit en retard sur elle-même), et
> **vérifier le build PyInstaller en local d'abord** — un build de release est
> resté cassé deux jours sans que personne le sache (`Tree()` vs `Analysis()`),
> et seul un vrai build local l'avait révélé. Le spec `concours/logx.spec`
> gère le cas Tree()/Analysis() (TOC combiné à `a.datas` APRÈS Analysis).

### Ce qui reste ouvert

1. ✅ **FAIT ET FUSIONNÉ — Web Worker pour le décodage FT8** (PR #138,
   `b784b6c` sur `main`, fusionnée le 19/08/2026). Premier Web Worker du
   dépôt. Il reste à l'ÉPROUVER sur l'air réel (voir la fin du point) — mais
   le code, lui, n'attend plus rien.

   MESURÉ en navigateur réel sur la page elle-même, même fenêtre de 16,5 s à
   48 kHz et mêmes 3 stations, synthétisées puis décodées :

   | | Synchrone | Worker |
   |---|---|---|
   | blocage max du fil principal | 1 942 ms | **12 ms** |
   | durée du décodage | 2 023 ms | 2 021 ms |
   | tics de minuteur observés | 51 | 244 |
   | messages décodés | 3/3 | **3/3, textes identiques** |

   12 ms est SOUS les 400 ms de `DERIVE_MAX_MS` : le trou n'est pas réduit, il
   est **supprimé**. Le calcul dure toujours autant — mais il ne vole plus
   l'audio pendant qu'il travaille, donc il cesse de se saboter lui-même.

   ⚠️ **La note qui précédait disait « l'entrée est un Float32Array
   transférable ». NE PAS LE TRANSFÉRER** : `fenetre.samples` est relu juste
   après par `surveillerSilenceAnormal`, et `ft8Decimer` rend l'entrée
   ELLE-MÊME quand le facteur vaut 1. Un transfert viderait le tableau côté
   page et la surveillance du silence mesurerait « silence » à chaque créneau.
   Copie par clone structuré, ~3,2 Mo par créneau — négligeable devant les
   2,5 s économisées.

   ⚠️ **« L'émission n'est pas concernée » était FAUX**, et c'est le piège le
   plus coûteux du chantier : `hashTable` est lue par le décodage ET par
   `ft8EncodeMessage`, donc par les messages ÉMIS. Un Worker qui accumulerait
   ses hachages priverait la page de ceux nécessaires aux indicatifs composés
   — panne d'émission SILENCIEUSE, visible seulement d'en face. La page envoie
   sa table, le Worker rend les entrées apparues, la page FUSIONNE.

   Reste à faire, et F4GLD seul peut le faire : **l'essai sur de l'AIR RÉEL**.
   Ici le signal est synthétisé par la page, donc parfait.

2. ✅ **FAIT (20/08/2026, branche `fix/lot4-vox-echap-voacap`)** — sans CAT
   configuré, la page ne fabriquait AUCUNE forme d'onde : `envoyerMessage`
   sortait avant la synthèse, alors que son message conseillait de passer en
   VOX. Le conseil était impossible à suivre.

   **Ce que le correctif a dû faire, et qui ne saute pas aux yeux.** La
   décision VOX est prise AVANT le bloc de sortie anticipée : laissée dedans,
   le `return false` final s'y serait appliqué aussi et le correctif aurait été
   mort-né sans que rien ne le signale. Et deux propriétés anodines avant
   deviennent critiques, l'ancien code faisant l'inverse des deux :
   `pttDemande` passe à VRAI (c'est lui qui rend le bouton STOP visible — il
   était mis à FALSE, la radio aurait émis avec l'arrêt caché), et le chien de
   garde reste ARMÉ (il était désarmé).

   **La coupure n'a PAS eu à être écrite** : `jouerForme()` inscrivait déjà sa
   source dans `sourcesTxVivantes` et `couperAudioTx()` l'arrête. C'est ce
   chemin qui fait retomber le VOX faute de signal — vérifié avant de s'y fier.

   **Reste à faire, et F4GLD seul peut le faire** : l'essai sur l'AIR. Qu'un
   VOX réel se déclenche dépend du seuil du poste et du niveau de la carte
   son ; aucun test ne peut le dire.

   Décision d'origine, conservée pour le contexte :

   ✅ **TRANCHÉ PAR F4GLD LE 20/08/2026 : le VOX doit marcher réellement.** La
   page doit jouer la forme d'onde dans la carte son sans commander de PTT ;
   c'est le VOX du poste qui déclenche l'émission. Usage courant en FT8, et
   c'est déjà ce que le message promet.

   **Ce que cela engage, et qui doit être traité DANS le même lot** : la radio
   peut alors passer en émission sans qu'aucune commande CAT ne soit envoyée,
   donc **le logiciel ne peut plus la faire taire par CAT**. Les garde-fous
   restants sont le bouton STOP et les cinq façons d'arrêter le séquenceur —
   ils deviennent la SEULE barrière, et doivent être vérifiés comme tels (le
   bouton STOP a déjà été trouvé « tenu par rien » une fois, PR #136). Le
   point d'arrêt du son lui-même compte aussi : `logx_ft8.html` documente déjà
   qu'une onde résiduelle « remet le poste en émission » sur une station en
   VOX (voir les commentaires autour de la coupure de l'oscillateur), et que
   « laisser le son partir n'arrête rien sur une station en VOX ». Couper le
   PTT ne suffira plus : il faudra couper le SON, et le prouver.

   **Où ça se passe, repéré le 20/08/2026** (pour ne pas refaire la fouille) :
   dans `logx_ft8.html`, `pttOn(true)` est attendu puis, si le serveur répond
   `non_engage` (aucun pilotage radio), la fonction sort — c'est là que le
   chemin d'émission s'arrête, avant toute synthèse. Le message affiché juste
   après est celui qui conseille le VOX.

   Deux points à ne PAS manquer dans ce lot, parce qu'ils ne sautent pas aux
   yeux : la visibilité du bouton STOP est pilotée par `pttDemande` via
   `majBoutonStop()`, et la branche `non_engage` remet justement `pttDemande`
   à `false` — en mode VOX il faudra qu'il passe à VRAI, sinon la radio émet
   pendant que le bouton d'arrêt est caché. Et le chien de garde
   (`armerChienDeGarde` / `desarmerChienDeGarde`) est désarmé sur cette même
   branche : il devra rester armé.

   Chantier non encore ouvert au 20/08/2026.

3. ✅ **TRAITÉ — deux stations distantes de moins de 50 Hz : la seconde
   n'était jamais décodée.** `logx_ft8_dsp.js`, `minFreqSeparationHz`
   valait `8 × 6,25 Hz`. La limite passe de 50 Hz à ~19 Hz.

   **Le piège de ce chantier, et il aurait coûté cher** : la première mesure
   (2 stations proches) donnait « sans la règle, 6/6 au lieu de 3/6 » et
   invitait donc à la SUPPRIMER. C'était faux. La règle n'écarte pas des
   stations, elle effondre la JUPE d'un même signal — le balayage grossier
   avance par pas de 3,125 Hz, donc un signal fort produit plusieurs pics
   voisins qui mangent les places de `maxCandidates`. Mesuré sur bande
   chargée, avec des amplitudes inégales (c'est cette inégalité qui révèle
   le défaut ; à amplitudes égales les deux configurations se valent et la
   mesure ne discrimine pas) :

   | stations | règle 50 Hz | sans règle |
   |---|---|---|
   | 16 | 16/16 | 12/16 |
   | 22 | 22/22 | 15/22 |
   | 28 | 28/28 | **14/28** |

   Le mécanisme est donc bon, seule sa LARGEUR était en cause. Balayage du
   seuil sur les deux scénarios opposés :

   | seuil | 2 stations à 18 Hz | à 31 Hz | 16 stations |
   |---|---|---|---|
   | 0 à 12,5 Hz | 6/6 | 6/6 | 12/16 |
   | **18,75 Hz** | **6/6** | **6/6** | **16/16** |
   | 25 à 31,25 Hz | 3/6 | 6/6 | 16/16 |
   | 50 Hz (ancien) | 3/6 | 3/6 | 16/16 |

   18,75 Hz = 3 × l'espacement des tons est la SEULE valeur qui tienne les
   deux bouts. Mais à ce seuil un signal prend 2 à 3 places au lieu d'une, et
   la bande à 28 stations retombait à 21/28 — d'où `maxCandidates` porté de
   30 à 60 (mesuré : 21/28 à 30 places, 23/28 à 45, **28/28 à 60**, et rien
   de plus à 90 ou 120 pour 1 à 2 s de temps en plus). Le surcoût est faible
   parce que c'est la recherche de synchro grossière qui domine le décodage,
   pas les décodages LDPC.

   **MESURÉ SUR LA PLATEFORME CIBLE**, pas seulement sous le moteur des tests —
   navigateur réel, décodage dans un Worker, signal à 12 kHz (ce que voit
   `ft8DecodeAudioAll` après `ft8Decimer`) :

   | stations | budget | durée | décodées |
   |---|---|---|---|
   | 16 | 30 | 3 458 ms | 16/16 |
   | 16 | 60 | 4 697 ms | 16/16 |
   | 28 | 30 | 3 490 ms | 21/28 |
   | 28 | **60** | **4 057 ms** | **28/28** |

   Sur bande très chargée : **+7 stations pour +567 ms**. Quatre secondes dans
   un créneau qui en dure quinze, et depuis la PR #138 ce calcul est dans un
   Worker — il ne bloque donc pas l'écran (12 ms mesurés).

   ⚠️ **Piège du banc lui-même, à ne pas refaire** : la première version
   synthétisait le signal à 48 kHz puis décimait. Elle ne rendait JAMAIS la
   main — le noyau gaussien de `ft8SynthesizeGfsk` grandit avec la cadence,
   donc la fabrication du signal coûtait seize fois plus cher que le décodage
   qu'on cherchait à mesurer, et gelait le moteur de rendu au point de rendre
   l'onglet injoignable. Synthétiser directement à 12 kHz est FIDÈLE (c'est
   exactement ce que le décodeur reçoit) et mesure la bonne chose.

   **Vérifié aussi** : l'estimateur de report (`ft8EstimerSnr`) justifie
   explicitement l'emploi d'une MÉDIANE pour le plancher de bruit par le fait
   que « la séparation minimale est de 50 Hz ». Abaisser le seuil change
   cette prémisse, donc on l'a mesuré au lieu de le supposer — reports
   strictement identiques avant/après (24,6 puis 22,3 dB avec une voisine à
   18 Hz ; 17,4 / 16,6 dB sur signal faible). La médiane encaisse.

   **Ce qui reste vrai** : sous ~19 Hz d'écart la seconde station est encore
   perdue. La limite est DÉPLACÉE, pas supprimée. La lever demanderait la
   soustraction de signal et un décodage multi-passes, chantier d'un autre
   ordre.

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

6. 📋 **CHANTIER À VENIR, pas commencé — scinder les gros fichiers HTML
   monolithiques.** Demandé par F4GLD le 22/08/2026, pendant le chantier du
   mode Automatique, à propos de `logx_ft8.html` — puis élargi le même jour
   après mesure des autres pages du dépôt.

   **Pas un problème de vitesse, sur aucune de ces pages.** Quelques centaines
   de Ko se parsent en quelques ms, et servi en local il n'y a même pas de
   coût réseau — mesuré nulle part comme un point noir. Scinder en plusieurs
   `<script src>` ne changerait rien à la rapidité (voire ajouterait des
   requêtes HTTP sans bénéfice en local). L'intérêt est uniquement la
   maintenance : navigation plus facile, moins de risque de perdre un
   correctif en éditant une zone déjà touchée par ailleurs (le dépôt a déjà eu
   deux incidents d'éditions perdues avec des agents en parallèle sur un même
   fichier — un fichier plus petit réduit la probabilité de collision, il ne
   l'élimine pas).

   **Mesure faite le 22/08/2026 sur toutes les pages de `concours/`, PUIS
   CORRIGÉE le même jour** — le premier passage comptait les lignes/Ko du
   `.html` sans vérifier s'il contenait vraiment du `<script>` inline, ce qui
   a fait cataloguer `logx_configuration.html` comme candidat alors qu'il ne
   l'est plus. 🚨 **Piège attrapé en se relisant, pas trouvé du premier
   coup** : la seule mesure fiable est `grep -n "<script"` sur le `.html` —
   un fichier peut peser 260 Ko de HTML/CSS légitimes sans une ligne de JS
   inline. Compter les lignes/Ko seul aurait refait exactement l'erreur que
   ce chantier veut corriger ailleurs.

   | Fichier | `<script>` inline ? | Où est vraiment le monolithe |
   |---|---|---|
   | `logx_ft8.html` | **oui** — JS inline massif, région `SEQ:DEBUT`/`SEQ:FIN` repérable | le `.html` lui-même : 4896 lignes / 276 Ko |
   | `logx_carte.html` | **oui**, ligne 545 (`<script>` sans `src`) — confirmé, 142 fonctions inline | le `.html` lui-même : 3480 lignes / 204 Ko, **rien de spécifique à la carte** n'a jamais été extrait |
   | `logx_configuration.html` | **non** — 0 `<script>` sans `src`, extraction faite le 10/08/2026 (avant même `logx_contest_rules.js` du 19/08) | **`logx_configuration.js`** : 6930 lignes / 416 Ko / 259 fonctions — c'est LUI le monolithe, pas le `.html` |
   | `logx_logbook.html` | non, 50 modules externes déjà chargés | aucun — modèle déjà atteint, pas un chantier |

   **Découpage le plus naturel pour chacun des trois vrais candidats :**
   - `logx_ft8.html` : isoler le bloc du séquenceur, déjà délimité par les
     sentinelles `SEQ:DEBUT`/`SEQ:FIN` que `test_ft8_sequenceur.py` utilise
     pour l'extraire — un fichier `logx_ft8_sequenceur.js`. **Ne rien
     commencer ici avant que le mode Automatique (ci-dessus) soit fusionné
     et éprouvé sur l'air.**
   - `logx_configuration.js` : analysé le 22/08/2026 (agent en lecture
     seule, résultats revérifiés indépendamment — `wc -l`/`du -h`/`grep -c
     "function "` confirment 6930/416K/259). Trois blocs candidats, du plus
     sûr au moins sûr :
     1. **Cloud Sync + MySQL** (~96 lignes) — `cloudsyncNow`,
        `_mysqlFieldsFromForm`, `testMysqlConnection`, `mysqlSyncNow`.
        ✅ **FAIT le 23/08/2026 (PR #219)** — extrait dans
        `logx_configuration_cloudsync.js`, chargé APRÈS configuration.js.
        Déplacement pur (-96 l, 0 ajout), équivalence byte-à-byte,
        contre-épreuve mutation, `test_config_cloudsync_extrait.py`.
     2. **ACOM (série RS-232)** (~76 lignes) — `refreshAcomPorts`,
        `testAcomConnection`, `acomSetOperate`.
        ✅ **FAIT le 23/08/2026 (PR #220)** — extrait dans
        `logx_configuration_acom.js`, chargé APRÈS configuration.js.
        Déplacement pur (-76 l, 0 ajout), `test_config_acom_extrait.py`.
        Dépendance notée : `escC()` reste un global de configuration.js
        (disponible au moment de l'appel — les 3 fonctions ne sont
        appelées qu'au clic/focus, jamais au chargement).
     3. **Mot de passe d'accès optionnel** (~90 lignes) —
        `refreshAccessPasswordStatus`, `setAccessPassword`,
        `disableAccessPassword`.
        🚫 **ÉCARTÉ le 23/08/2026 après analyse (décision F4GLD) — NE PAS
        re-proposer.** L'analyse initiale sous-estimait le couplage. Deux
        obstacles vérifiés dans le vrai code : (a) `init()` est appelée
        **synchroniquement au chargement** (`const _initReady = init();`,
        fin de configuration.js) et appelle `refreshAccessPasswordStatus()`
        — un fichier extrait chargé APRÈS configuration.js casserait l'init
        (ReferenceError) ; (b) `disableAccessPassword` dépend en retour de
        `_confirmConfigBanner()`, global de configuration.js. Une extraction
        n'est possible qu'en chargeant le fichier AVANT configuration.js
        (ordre INVERSÉ vs les deux précédents) — fragilité subtile qu'un
        futur rangement casserait en silence, **sur du code d'auth**, pour
        ne gagner que ~90 lignes sur ~6760. Mauvais échange : on laisse ce
        bloc dans configuration.js.
     ⚠️ Les bannières `// ─── TITRE ───` du fichier ne délimitent PAS
     toujours un module cohérent : la section « AMPLIFICATEUR HF »
     mélange en réalité des fonctions ACOM/AMP avec du CAT/QRZ/backup sans
     rapport — vérifier au cas par cas, ne jamais se fier au titre seul.
     Garde-fou inscrit en test pour ACOM (le bloc ne doit pas déborder sur
     `AMP_DEFAULT_BAUD`/`updateEnabledFieldsVisibility`).

     **Bilan `logx_configuration.js` : 6939 → ~6767 lignes (-172), deux
     extractions propres. Plus de bloc franchement isolable sans entrer
     dans du code entrelacé — le reste du monolithe est cohérent. Le
     modèle « extraire vers un `<script src>` chargé après, test
     d'équivalence + contre-épreuve » est validé pour de futurs blocs.**
   - `logx_carte.html` : analysé le 23/08/2026 (lecture seule). 🚫 **NON
     découpable proprement — écarté, ne pas re-proposer.** Le `<script>`
     inline (545→3478, 257 fonctions) mêle les définitions à du code exécuté
     AU CHARGEMENT top-level (`L.map('map',...)`, `setInterval`/`setTimeout`
     épars : ~411, 581-582, 807, 2303-2304, 2333-2334…, appels directs
     `fetchCoach()`) partageant un état de MODULE (`leafletMap`, timers,
     caches) via closures. Extraire un sous-ensemble casserait cet état
     partagé — il faudrait passer les `let` en globaux, ce qui n'est PLUS un
     déplacement pur (même obstacle que le bloc Mot de passe, en pire).

   **Bilan du chantier découpage (23/08/2026) : SOLDÉ côté sûr.** Les seuls
   candidats à déplacement pur (Cloud Sync, ACOM) sont faits (#219/#220,
   -172 l sur configuration.js). Mot de passe et `logx_carte.html` écartés
   sur analyse (couplage/entrelacement). Restent hors périmètre autonome :
   `logx_ft8.html` (émission), `logx_logbook.js` (chemin critique, sur accord
   F4GLD uniquement). AUCUN autre gros fichier n'est un candidat propre.

   **Audit i18n (23/08/2026, lecture seule) : SAIN.** Extraction des 24
   dictionnaires `T`/`T_XXX` et calcul de parité : **2371 clés source, parité
   parfaite** sur les 7 langues (en/de/es/it/pt/nl/pl), 0 manquante — le
   travail des blocs `T_PARITY_FIX` tient. Les traductions identiques au
   français sont des noms propres légitimes (PowerGenius XL, Kenwood,
   définitions IOTA/POTA/SOTA…). Rien à corriger ; ne pas « traduire » (ce
   serait inventer du contenu).

   **Le coût réel, à ne pas sous-estimer.** Extraire un module bien plus
   petit et bien moins sensible que n'importe lequel des blocs ci-dessus
   (`logx_contest_rules.js`, une pure fonction de filtrage) a déjà demandé
   de mettre à jour une trentaine de fichiers de test. `logx_ft8.html` en
   particulier pilote de l'émission radio réelle (le séquenceur, et depuis
   le 22/08 le mode Automatique qui émet sans confirmation humaine) —
   chaque bloc doit être traité SEUL, avec la même discipline contre-épreuve
   par mutation que le reste du dépôt, jamais « en passant » à côté d'un
   autre correctif.

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

1. **La mémoire ACTIVE est dans `docs/passation/memoire_condensee/`** (6
   fichiers + `MEMORY.md` index) — à recopier tel quel dans
   `~/.claude/projects/<projet>/memory/` pour la réactiver. C'est la version
   déjà consolidée le 21/08/2026 (191 fiches → 6 fichiers, cf. `MEMORY.md`
   de ce dossier pour le détail), copiée dans le dépôt le 22/08/2026
   spécifiquement pour ce changement de compte — inutile de reconstruire
   quoi que ce soit à partir des fiches archivées.
2. `docs/passation/memoire/` (191 fiches d'origine, PR #118) reste
   **l'archive**, git-trackée pour ne rien perdre — ne pas la recopier, elle
   ne sert qu'en cas de besoin de retrouver le détail brut d'une fiche
   consolidée.
3. `CLAUDE.md` à la racine est lu automatiquement à chaque session : il porte
   déjà la langue, l'intuitivité, la charte graphique — et un renvoi vers ce
   document.
4. Le premier réflexe utile après avoir recopié la mémoire : relire la
   section 1 ci-dessus (« Où en est le travail »), à jour à la date indiquée
   en tête de ce document — c'est elle qui dit ce qui est fusionné, ce qui
   attend un essai sur l'air, et ce qui reste ouvert, pas la mémoire.

---

*Trois revues adversariales, 69 constats confirmés et corrigés, 146 cas au banc
d'essai. Et un séquenceur qui attend toujours son premier QSO réel — parce
qu'aucun banc ne remplace une antenne.*
