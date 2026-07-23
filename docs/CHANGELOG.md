# Journal des modifications

Toutes les évolutions notables de LogX AI sont documentées dans ce fichier.

Le format suit [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/). LogX AI
n'a pas encore de politique de versionnage strictement [semver](https://semver.org/lang/fr/) —
tant que le logiciel est en bêta, les tags `vX.Y-betaN`/`vX.Y-rcN` servent surtout
à déclencher la construction des exécutables (voir
`.github/workflows/build-release.yml`) et à comparer la version installée à la
dernière disponible. La version affichée dans la barre de statut de
l'application correspond à la constante `APP_VERSION` de `logx_version.py`,
qui doit être incrémentée à chaque tag poussé.

## [Non publié]

### Ajouté
- World Wide Award (hamaward.cloud) : nouveau concours avec roster de stations spéciales et scoring dédié.
- Auto-spot SOTA sur le cluster + push temps réel vers QRZ Logbook.
- Auto-spot POTA (bouton « Se spotter », POST vers api.pota.app).
- IOTA : spots en direct extraits des commentaires du cluster DX existant.
- WCA : géocodage de la référence activée pour donner une position au château sur la carte.
- flrig comme 4e backend de pilotage CAT (XML-RPC), aux côtés du natif/TCI/rigctld.
- Bandmap waterfall (canvas), scans QSL papier et records DX dans le panneau Diplômes.
- Enregistreur audio par QSO (tampon glissant 2 min, clip 20 s attaché au log).
- QTC (WAE) : saisie détaillée émis/reçu + export Cabrillo.
- Multi-opérateur : compte à rebours de la règle des 10 minutes + vue Partner (saisie en direct).
- Extension du check partiel (SCP) : import MASTER.SCP, vérification N+1, import Call History N1MM par concours.
- Worked Matrix : panneau détachable, adapté à chaque concours.
- Mécanisme de mise à jour logicielle proposée automatiquement, sans perte de données.
- Mot de passe d'accès optionnel avant remise du jeton d'écriture (rc_token).
- Vraie page de saisie mobile (`logx_mobile.html`) + bannière sur petit écran.
- Build Linux + workflow GitHub Actions multi-plateforme (Windows/macOS/Linux, exécutables attachés à la release).
- Journal d'erreurs local (`sys.excepthook`/`threading.excepthook`) exposé au diagnostic.
- Affichage de la version installée + bouton « Signaler un problème » dans la barre de statut.
- Formulaire d'issue GitHub structuré (`.github/ISSUE_TEMPLATE/bug.yml`) pour les bêta-testeurs non techniques (que faisiez-vous / version / OS / description), issues « vierges » désactivées pour canaliser les retours dedans.
- Ce journal des modifications (`docs/CHANGELOG.md`), au format Keep a Changelog.

### Modifié
- WSJT-X : alerte DXCC/département manquant + publication MQTT optionnelle.
- Parité mobile : scoring calculé côté serveur, n° de série centralisé, file d'attente hors ligne.
- Compression gzip + synchronisation différentielle de `/log/list` (ne retransmet que les QSO modifiés).
- Le thème jour/nuit se partage désormais entre postes (lien multi-poste).
- Fenêtre de rendu limitée pour les gros logs dans le logbook (300 lignes + bouton « Afficher plus »).
- Les artefacts de release Windows/macOS/Linux embarquent désormais le tag de version dans leur nom (ex. `LogXAI-v0.9-beta2.exe`) au lieu d'un nom fixe, pour qu'un testeur avec plusieurs versions en local puisse les distinguer ; la mise à jour automatique (`logx_update.py`) a été adaptée pour retrouver ce nouveau nom.

### Corrigé
- Repli RPH périmé + alerte DX QO-100 basée sur une distance sans tenir compte du sens.
- RBN : repli HTTP si le telnet du port 7000 est bloqué (verdict « aucun » au lieu de rester bloqué).
- Pare-feu Windows qui bloquait l'accès multi-poste (réseau « Public » sans règle de pare-feu).

## [0.9-beta1] - 2026-07-22

Première bêta packagée (Windows/macOS/Linux). Résumé des grands chantiers menés
depuis le premier commit ; voir `git log` pour le détail commit par commit.

### Ajouté
- Moteur de concours générique (barèmes/bandes/dates/échange pilotés par une définition JSON), lu automatiquement à partir d'un règlement PDF ou web via extraction IA vérifiée par une passe adversariale.
- 36 concours intégrés (REF, IARU R1, CQ WW/WPX, ARRL DX/FD, WAE, UBA, Russian DX, All Asian, Stew Perry, ARRL 10/160 m…) + 358 concours mondiaux préparables depuis le calendrier WA7BNM.
- Coach stratégique IA par concours (Run vs Search & Pounce, plan de bande, ouvertures par région) + agent et coach multilingues (8 langues).
- Carnet de log partagé multi-poste (SQLite), dédup des QSO, exports Cabrillo v3 / ADIF 3 / EDI-REG1TEST.
- Carnet permanent : déjà-contacté, diplômes/QSL, band map (inspiré Log4OM/HRD), tableau de chasse départements avec carte de France qui se colore.
- Callbook en cascade QRZ → HamQTH → HamDB, fiche du correspondant à la saisie, historique d'indicatifs Super Check Partial.
- Base DXCC hors ligne (cty.dat), mise à jour automatique si elle a plus de 30 jours.
- Page PROPAGATION : MUF réelle (ionosondes KC2G), indices solaires, grey-line, tropo/météores/avion, RBN, balises NCDXF/IBP, PSK Reporter, prévision Es/aurore VHF, carte de propagation mondiale 24 h.
- Pilotage radio CAT natif (pyserial), Hamlib rigctld, TCI (SDR type SunSDR/ExpertSDR3), rotor d'antenne (rotctld), amplificateurs HF (Elecraft KPA500/1500, Icom PW-1/PW2, SPE Expert).
- Programmes d'activation POTA / SOTA / IOTA / WWFF, puis ARLHS (phares) et WCA (châteaux), EME (rebond lunaire), moteur générique partagé entre tous ces programmes.
- Bandscope (activité de bande sans matériel SDR) + décodeur CW temps réel (Morse → texte, 100 % navigateur).
- Application mobile installable (PWA), page mobile généralisée multi-concours, utilisable en mobilité ou à domicile.
- Second écran / fenêtres détachables (multi-moniteur), panneaux détachables généralisés avec dispositions nommées, mode expédition (écran mural + Club Log Live).
- Auto-spot (self-spot) sur cluster DX avec la fréquence courante.
- Keyer vocal automatique (callbot) : indicatif et report dits/reçus par la radio.
- Chasse aux DXpeditions (flux RSS public NG3K ADXO) + onglet Calendrier dédié.
- Chasse aux départements français : lookup callbook en direct pour les indicatifs spottés jamais croisés ; coach avec suggestions proactives de pays/départements jamais travaillés.
- Constructeur de règles d'alerte personnalisées ; Cloud Sync multi-poste via dossier synchronisé.
- Réseau ADIF générique (interopérabilité UDP `<contactinfo>` avec N1MM/DXLog) ; QSO Upload unifié (QRZCQ, HRDLog, ClubLog, eQSL, LoTW).
- Modes d'utilisation (logbook simple / concours / expédition) + mode Radioclub (postes partagés, jusqu'à 40 opérateurs).
- Carte multi-échelle (France / Europe / continent / monde), horloge UTC + heure locale partout.
- Assistant de configuration guidé + annuaire de WebSDR distants.
- Packaging en exécutable autonome Windows/macOS/Linux (PyInstaller), aucune installation de Python requise.
- Guide utilisateur complet et document de promotion (`docs/GUIDE_UTILISATEUR.md`, `docs/LogX_AI_Promotion.md`).
- CI locale (`check.bat`) et GitHub Actions (`check.yml`) : tests pytest + validation des définitions de concours.

### Modifié
- Renommage complet du produit en LogX AI (fichiers, marque, logo, charte de couleur) — auparavant nommé RadioContest AI.
- Refonte de la page CONFIGURATION en hub de catégories + popups, à la place de l'ancien assistant pas-à-pas.
- Refonte lisibilité (tailles de caractères, contraste) et zéro scroll de page sur l'ensemble des écrans.
- Nettoyage du dépôt : seuls le code (`concours/`) et la CI sont suivis par git, purge des fichiers hérités du tout premier commit.

### Corrigé
- Fix critique : perte de données possible en page CONFIGURATION + pilotage rigctld inopérant.
- Fix logbook simple : bandes/modes fiables, doublons hors concours non traités comme erreurs, concours fantôme après expiration.
- Fix lenteur majeure de `/log/list` (verrou du log gardé pendant tout l'envoi réseau).
- Fix mode CONCOURS qui affichait le log de base au lieu du log filtré par portée concours + année.
- Fix HTTPS bloqué par Avast sous Python 3.13 + fiabilisation de l'extraction IA du règlement.
- Corrections issues de plusieurs revues adversariales dédiées (propagation, audit CONFIG H1-H6/M1-M9/B2-B5, sécurité/robustesse/perf).

### Sécurité
- Traversée de répertoire bloquée dans `Handler._resolve()` + liste noire des fichiers sensibles (clé API…) jamais servis.
- Authentification par jeton partagé sur les écritures et l'IA, CORS restreint au réseau local.
- Endpoints `/debug/*` désactivés par défaut ; écritures JSON atomiques et thread-safe.
- Robustesse réseau pour une diffusion publique : plus aucun appel réseau bloquant dans le thread HTTP (QRZ, callbook, cluster, RBN, PSK Reporter, solaire, HRDLog, LoTW, Cloud Sync).
