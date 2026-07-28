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

- **Décodeur SSTV intégré au logbook** (panneau 🖼 en bas de l'écran, à droite
  du décodeur CW) : réception des images à balayage lent — activations,
  dimanches SSTV, transmissions de l'ISS en PD120 — **sans MMSSTV ni RX-SSTV
  à côté**, tout se passe dans le navigateur comme pour les décodeurs CW et
  RTTY. Détection automatique du mode par l'en-tête VIS (Martin M1/M2,
  Scottie S1/S2/DX, Robot 36/72, PD50 à PD290), image construite ligne par
  ligne pendant la réception, compensation continue de la dérive d'horloge
  entre cartes son (l'image « penchée » classique) sur les impulsions de
  synchro, export PNG horodaté. Pipeline DSP dans `logx_sstvdecoder.js`,
  couvert par des tests aller-retour encode → décode (fidélité mesurée au
  pixel près sur les 14 modes, dérive d'horloge, bruit, rejet des en-têtes
  VIS invalides).

### Corrigé

- **Le lanceur Windows pouvait rouvrir l'ANCIENNE version après une mise à
  jour, en affichant que tout allait bien.** `LANCER_RADIOCONTEST.bat` testait
  le port avec `curl http://localhost:8080/` : dès que quelque chose répondait,
  il affichait « [OK] Serveur deja en route » et ouvrait le navigateur **sans
  jamais exécuter `logx_serveur.py`**. Or c'est ce dernier qui porte la
  détection d'instance déjà lancée (`logx_singleton`). Un serveur laissé en
  route depuis la veille servait donc indéfiniment son ancienne version, et
  l'utilisateur concluait que la mise à jour avait échoué. Constaté sur poste
  réel : la 0.9-beta5 s'affichait alors que la 0.9-beta7 était installée.
  Le lanceur appelle désormais `logx_instance.py`, qui compare la version qui
  répond à celle du dossier ; à version différente il **n'ouvre aucune page**
  et explique quoi fermer.
- **Le message « LogX AI est déjà lancé » nomme maintenant les deux versions**
  côte à côte (celle qui répond, celle installée). Il décrivait le mécanisme
  — « c'est l'ANCIEN qui continuerait de répondre » — sans jamais donner les
  numéros, alors que c'est exactement ce que cherche quelqu'un qui vient de
  mettre à jour. Vaut aussi pour `LogXAI.exe`, qui ne passe pas par le `.bat`
  mais tombait dans le même piège.

- **Le lanceur n'ouvre plus le navigateur sans savoir si le serveur a
  démarré.** Il attendait `timeout /t 3` en aveugle, puis ouvrait les pages
  quoi qu'il arrive. Deux conséquences : la fenêtre du serveur étant lancée
  minimisée (`start /MIN`), un refus de démarrer — port pris entre la sonde et
  le bind, fichier manquant — s'affichait là où personne ne regarde pendant
  que le navigateur montrait « impossible de se connecter » sans la moindre
  explication ; et 3 secondes n'était qu'une devinette, donc sur un poste lent
  (ou avec un antivirus qui inspecte l'interpréteur) la page s'ouvrait trop tôt
  sur la même erreur alors que tout allait bien. Le lanceur attend désormais
  que le port **réponde** ; s'il ne répond pas, il n'ouvre rien, nomme la
  fenêtre minimisée où lire la cause, et affiche les dernières lignes du
  journal d'erreurs **si elles datent de ce démarrage** (un journal n'étant pas
  effacé entre deux lancements, l'afficher sans regarder sa date désignerait
  une panne ancienne comme cause du problème du jour).

### Interne

- `logx_i18n.js` n'emploie plus `\p{L}` : les échappements de propriété
  Unicode exigent un moteur JS compilé **avec ICU**, or le V8 embarqué par la
  suite de tests (`py_mini_racer`) est un build **sans ICU** et lève une
  `SyntaxError` dessus. Comme V8 ne compile une expression régulière littérale
  qu'à sa *première évaluation*, l'erreur restait invisible tant que la
  correspondance directe aboutissait : la règle du préfixe emoji était
  structurellement **intestable**. Remplacé par une recherche de première
  lettre écrite à la main, vérifiée sur un corpus de 1005 chaînes réelles
  (14 divergences, toutes multilignes, toutes sans effet).
- `logx_singleton.sonde_sans_bind()` : sonde qui se contente de se connecter,
  sans jamais ouvrir le port. `probe()` fait un vrai `bind` pour savoir si le
  port est libre ; l'employer en boucle pendant qu'un serveur démarre lui
  volerait le port à l'instant de son bind — sous Windows, où
  `allow_reuse_address` est volontairement désactivé, ce bind échouerait en
  `WinError 10048`. L'attente aurait provoqué la panne qu'elle surveille.
- `LANCER_RADIOCONTEST.bat` était listé dans `.gitignore` parmi les
  « documents personnels de préparation », entre deux PDF. C'est un fichier du
  programme (chemins relatifs, prévu pour un zip extrait n'importe où) : il est
  désormais suivi, et son câblage est vérifié par les tests.

## [0.9-beta7] - 2026-07-27

Version issue d'une **étude comparative** avec N1MM Logger+, DXLog.net, Tucnak,
Win-Test et Wavelog (voir `docs/ETUDE_COMPARATIVE_2026-07.md`). Huit écarts y
avaient été identifiés et vérifiés ; les huit sont traités ici. S'y ajoutent les
correctifs d'une passe d'audit, dont plusieurs pertes de données silencieuses.

**Réserve importante, à lire avant de compter dessus** : le WinKeyer, la
commande CW `KY`, les transverters, le keyer vocal et le boîtier SO2R ont été
développés **sans qu'aucun matériel soit branché**. Les trames sont conformes
aux spécifications des protocoles et vérifiées octet par octet, mais le premier
essai sur un poste réel reste à faire. Le décodeur RTTY, lui, est vérifié de
bout en bout par signal synthétique — sauf en pile-up réel.

### Ajouté
- **Les macros se déclenchent aux touches F1 à F8.** Les boutons affichaient « F1 »… « F8 » depuis toujours, mais seul le clic les déclenchait : en run, la main devait quitter le clavier pour viser un bouton. C'est la fonction que N1MM, Win-Test et DXLog mettent en avant en premier. Actif même pendant la saisie — on tape l'indicatif, on envoie l'échange, on continue.
- **Manipulation CW en mode Natif** (commande `KY`) pour **Kenwood et Elecraft**. Le mode que la configuration recommande par défaut refusait auparavant tout envoi CW : un opérateur CW n'avait donc aucune manipulation.
- **Manipulateur WinKeyer K1EL** sur son propre port série. Il prend la main sur l'envoi CW **quelle que soit la marque** — c'est la seule manipulation possible en Icom (le protocole CI-V ne publie aucune commande d'envoi de texte CW) et en Yaesu. Sa cadence ne dépend plus du trafic CAT.
- **Support des transverters.** Au-dessus de 1296 MHz la radio affiche sa fréquence intermédiaire : sans table de conversion, la bande déduite, le QSO enregistré, le filtre du band map, le QSY et le fichier EDI étaient **tous faux au même moment, sans le moindre message**. Concerne directement le Rallye des Points Hauts, le National THF et le Challenge THF.
- **Décodeur RTTY (Baudot/ITA2) dans le navigateur**, sans logiciel externe — N1MM s'appuie sur MMTTY, MMVARI ou Fldigi. Chaque indicatif décodé est **cliquable** et part dans la saisie : c'est ce geste qui fait la vitesse en RTTY.
- **Band map Search & Pounce** : les stations que vous entendez vous-même en balayant s'ajoutent à celles du cluster, avec un repère distinct. `Ctrl+Entrée` note la station en cours, `Ctrl+↑`/`Ctrl+↓` sautent de spot en spot (QSY et indicatif pré-remplis). Les notes vivent sur le serveur — partagées entre postes — et s'effacent au bout de 30 minutes, une station entendue il y a une heure ayant presque sûrement changé de fréquence.
- **SO2R** : deuxième radio déclarable, bascule d'émission par `Ctrl+Espace`, pilotage d'un boîtier OTRSP (microHAM, YCCC, EA4TX). Le QSY, les macros et le manipulateur visent la radio qui a l'émission. Le « dueling CQ » automatique et le second band map ne sont **pas** faits.

### Modifié
- **Le keyer vocal émet enfin par la radio.** Les messages enregistrés partaient vers la sortie par défaut du navigateur, sans PTT : le correspondant n'entendait rien. Ils empruntent désormais le chemin du callbot (PTT levé, lecture vers le périphérique choisi, PTT relâché avec vérification). Ils sont stockés **sur le serveur**, donc suivent l'opérateur d'un poste à l'autre et survivent au vidage du cache ; les enregistrements existants sont repris automatiquement.
- **Les points ne s'affichent que si un concours est sélectionné.** Sans concours, le barème retombait sur 1 pt/km et affichait des scores parfaitement calculés mais qu'aucun règlement ne compte. Distance, nombre de QSO, meilleur DX et pays restent affichés — eux sont vrais dans tous les cas.
- **PROPAGATION** : le tableau OUVERTURES PAR RÉGION passe en pleine largeur au-dessus des autres panneaux. Coincé dans une colonne, il se repliait derrière une barre de défilement horizontale qui masquait la colonne RÉGION — la seule qui identifie la ligne.

### Corrigé
- **Cabrillo enfin soumissible.** Deux générateurs coexistaient pour le même fichier, chacun avec ses défauts : l'en-tête portait l'identifiant interne (`REF_CDF_HF_SSB`) au lieu du nom officiel, le locator était ajouté à l'échange même en HF, et le générateur du navigateur écrivait l'échange **sans le compte-rendu** — un CQ WW partait avec `001` au lieu de `59 14`. Les robots de réception refusent ou déclassent en *checklog* pour moins que ça. Un seul générateur subsiste, et les lignes `CATEGORY-*` sont complètes.
- **Un seul QSO malformé gelait définitivement toute la sauvegarde sur disque**, en silence.
- **Les identifiants de QSO pouvaient entrer en collision** : l'import ADIF consommait plusieurs secondes d'identifiants futurs, si bien qu'un QSO saisi juste après en héritait. Supprimer un contact en effaçait alors un autre, sans erreur.
- **Chaque QSO réécrivait l'intégralité du carnet** — de l'ordre du téraoctet écrit sur une expédition de 15 jours.
- **La rotation des sauvegardes effaçait les fichiers Cloud Sync** et les marqueurs de suppression du poste.
- **Export EDI** : le numéro de série envoyé était régénéré depuis la position dans la liste ; le numéro réellement passé sur l'air était jeté.
- **Macro CW `{NR}`** : envoyait le nombre total de QSO + 1 au lieu du numéro de série de la bande — le numéro annoncé n'était pas celui du log.
- **Ouvrir la page CARTE écrasait la configuration partagée** du serveur : carnet vidé et numérotation remise à 001 sur tous les postes.
- **Export ADIF** : le champ `<BAND>` était invalide sur les 14 bandes.
- **Refus HTTP** : les réponses « trop de tentatives » et « non autorisé » pouvaient se perdre. Fermer une connexion dont le tampon contient encore des octets fait envoyer un RST qui détruit la réponse déjà émise — l'utilisateur recevait une erreur réseau au lieu du message lui disant quoi faire.
- **Le guide récité par l'assistant IA** décrivait une page de configuration en 5 étapes remplacée depuis par un ensemble de cartes : il envoyait les utilisateurs vers des écrans inexistants. Même correction pour un texte de la page CONFIG.
- **Suite de tests** : elle produisait environ un échec aléatoire par passe, sur un test différent à chaque fois. Deux causes corrigées ; deux passes complètes de 1691 tests sont désormais sans échec.

## [0.9-beta6] - 2026-07-26

Refonte de la page PROPAGATION, jugée « inutilisable » par un utilisateur :
18 panneaux répondant à 5 questions différentes y étaient empilés. Plus une
série de correctifs de fond sur le serveur.

### Ajouté
- **Page CHASSE** : les cibles de trafic (activateurs POTA, SOTA, WWFF, châteaux WCA, need list du cluster) quittent la propagation pour une page dédiée — chercher qui appeler et consulter les conditions sont deux gestes différents.
- **PROPAGATION en 3 onglets** : HF · VHF & EME · M'entend-on ? La page s'ouvre automatiquement sur l'onglet pertinent selon le concours actif (bandes VHF → onglet VHF). Aucun défilement, vérifié par mesure à 1366×768 comme à 1920×1080.
- **Alerte orage dans la barre de statut**, présente sur toutes les pages, à la place du panneau de carte permanent : on n'a pas besoin de voir la foudre en continu, mais d'être prévenu quand il faut débrancher les antennes.
- **Nombre d'opérateurs saisi directement**, au lieu d'un clic par opérateur — neuf clics pour une équipe de dix. Réduire l'effectif demande confirmation si les lignes supprimées contiennent déjà un indicatif.
- **Plafond d'opérateurs porté de 5 à 40** en concours et expédition. La limite de 5 était historique et sans justification technique (le mode radioclub tournait déjà à 40 avec le même export) : une DXpédition à 10 opérateurs, ou une équipe de 9 en contest IOTA, était purement et simplement bloquée.
- **Protection contre le double lancement** : relancer le logiciel alors qu'une instance tournait affichait un démarrage normal… mais c'est l'ANCIENNE qui continuait de répondre, et deux serveurs écrivaient dans le même journal de contacts. Message clair et ouverture de la fenêtre existante.
- **Réseau de balises NCDXF/IBP** rendu accessible depuis toutes les pages.

### Modifié
- **Connexions HTTP persistantes** : une page ouvrait autant de connexions réseau que de fichiers, et chaque sondage périodique en rouvrait une. Elles sont désormais réutilisées — moins de va-et-vient réseau, utile en multi-poste.
- Les rafraîchissements d'un onglet masqué sont **suspendus** : une page laissée ouverte en arrière-plan interrogeait le serveur en continu pour personne (mesuré : 27 requêtes en 68 s).

### Corrigé
- **Infobulles qui clignotaient** indéfiniment entre le français et la langue choisie, sur toutes les pages en langue étrangère.
- **Le champ de recherche de concours de la configuration restait en français** dans les 7 langues traduites — il n'avait de traduction dans aucune. Plus généralement, les infobulles et champs de saisie introduits par un pictogramme (🔍, ✅…) suivent désormais la même règle de traduction que le reste du texte : jusqu'ici seuls les libellés en bénéficiaient.
- Traduction du titre d'onglet qui, si elle échouait, interrompait **toute** la traduction de la page — celle-ci restait alors intégralement en français sans le moindre message.
- Plusieurs libellés illisibles à 1366×768 (mode et nom du parc dans les listes d'activateurs, explication de la need list).
- Mise à jour réseau : un fichier plus court qu'annoncé bloquait 30 s au lieu d'échouer immédiatement.

### Sécurité
- **Mot de passe d'accès réaffiché en clair.** Après 5 essais infructueux — exactement le cas pour lequel la protection anti-force-brute existe — la tentative suivante était refusée sans lire les données envoyées. Celles-ci se retrouvaient collées à la requête suivante du navigateur, produisant une page d'erreur qui contenait le mot de passe tapé. Défaut apparu avec les connexions persistantes de cette même version, jamais publié.
- Deux autres cas de désynchronisation de connexion (requête refusée dont les données n'étaient ni lues ni écartées) pouvant délivrer à un client la réponse destinée à une autre requête.

## [0.9-beta5] - 2026-07-25

Version issue d'un audit systématique du code (6 angles d'analyse, chaque
constat soumis à une vérification adversariale indépendante avant correction) :
17 défauts réels confirmés et corrigés. **Mise à jour recommandée à tous les
utilisateurs de la 0.9-beta4**, qui contient les deux défauts critiques
ci-dessous.

### Sécurité
- **Critique — fuite du jeton d'écriture et des identifiants** : la liste noire des fichiers jamais servis (`.auth_token`, `.server_config.json`, log complet…) filtrait l'URL demandée au lieu du fichier réellement atteint. Un simple slash final (`/.auth_token/`), un `%2F` ou un détour par `..` la contournaient et renvoyaient le contenu en clair. Ces routes étant servies avant toute authentification et le serveur écoutant sur le réseau local, n'importe quel appareil du LAN pouvait récupérer le jeton d'écriture partagé — et donc réinitialiser le log, modifier la configuration ou déclencher une mise à jour. La protection par mot de passe optionnelle ne couvrait pas ce chemin.
- **Injection de code sans authentification** : la version déclarée par un poste voisin (`/log/list?ver=`, route sans jeton) était réinjectée sans échappement dans la CHECKLIST d'avant-concours. Un appareil du réseau pouvait ainsi faire exécuter son propre JavaScript dans l'onglet d'un opérateur authentifié. Corrigé par un double verrou (échappement côté client + filtrage de la valeur avant stockage côté serveur).

### Corrigé
- **Critique — corruption silencieuse du carnet (Cloud Sync `full`)** : la fusion était purement additive. Un QSO supprimé réapparaissait au cycle de synchronisation suivant (suppression définitivement impossible), et corriger un QSO recréait son ancienne version en doublon. Corrigé par des marqueurs de suppression persistants, qui propagent la suppression au lieu de l'annuler.
- **Numéro de série faux en concours** : l'allocation ignorait la portée du concours actif et repartait du plus grand numéro de tout l'historique de la bande — le premier QSO d'un nouveau concours pouvait recevoir 801 au lieu de 001, échange erroné transmis sur l'air puis enregistré, sans recours possible.
- **Mise à jour Windows impossible dès qu'un accent figure dans le chemin** (`C:\Users\Frédéric\…`) : le script d'installation était écrit dans un encodage que `cmd` ne lit pas, l'application s'arrêtait sans jamais redémarrer ni signaler d'erreur, et reproposait indéfiniment la même mise à jour.
- **QSO importés invisibles pour les autres postes** : sur un import ADIF, le marquage de version se faisait hors du verrou du log ; un poste qui interrogeait le serveur au mauvais moment n'apprenait jamais l'existence de ces QSO.
- Blocage du serveur jusqu'à 21 s (mesuré) sur un dossier Cloud Sync injoignable, sondé toutes les 20 s par toutes les pages.
- Sauvegarde la plus récente supprimée immédiatement après un changement d'indicatif (tri des fichiers par nom au lieu de la date).
- Copie de la base de données sans verrou lors des sauvegardes (instantané potentiellement corrompu) et écritures de sauvegarde non atomiques.
- Assistant « Nouveau concours » invisible et deux boutons sans effet dans sa bannière (régression de la refonte de la page CONFIGURATION).
- Mise à jour réseau : un poste se découvrait lui-même comme passerelle, masquant les passerelles réelles ; un pair d'une autre plateforme était proposé puis rejeté après téléchargement complet ; la référence d'intégrité ne survivait pas à un redémarrage.
- Alerte « versions différentes » fantôme après le départ d'un poste, et synchronisation différentielle qui retransmettait presque tout le log après chaque redémarrage.

## [0.9-beta4] - 2026-07-25

### Ajouté
- Mise à jour réseau résiliente en DXpédition/multi-op : relais passerelle (un poste avec internet relaie l'authentique contenu GitHub) en priorité, relais pair-à-pair (un poste sert un exécutable déjà téléchargé et vérifié) en secours strict uniquement si aucune passerelle n'est disponible — vérification SHA-256 systématique contre une référence obtenue directement de GitHub, jamais du pair/de la passerelle.
- Affichage de la version logicielle de chaque poste connecté en réseau multi-op, avec alerte visuelle si un poste est resté sur une version différente.
- Indicateur de dégradation réseau (callbook, solaire, Cloud Sync) dans la barre de statut, au lieu d'une dégradation silencieuse visible seulement en console.
- CWops (CWT) et les 2 éditions UFT (été/hiver) ajoutés aux concours suivis.
- Réseau de balises NCDXF/IBP rendu découvrable depuis toutes les pages (il était déjà présent mais peu visible).

### Corrigé
- Dérive du schéma de définition des concours vis-à-vis de la réalité (CQ WW/CQ WPX, World Wide Award) qui faisait échouer silencieusement la validation en CI.
- CI GitHub Actions « Check LogX AI » cassée par un clone git superficiel incompatible avec les tests de non-régression qui rejouent un ancien commit.
- Flakes pytest intermittents (test HTTP sans fermeture explicite de serveur, chemin de dossier invalide non portable sous Linux).
- Alerte Cloud Sync fantôme qui pouvait rester affichée après correction du dossier.

### Sécurité
- 3 défauts trouvés en revue adversariale sur le nouveau mécanisme de mise à jour réseau, corrigés avant publication : verrou de vérification d'intégrité absent juste avant le remplacement de l'exécutable, SSRF possible via le champ IP fourni par le client (requêtes serveur sortantes forcées vers une cible arbitraire), priorité passerelle-avant-pair non appliquée côté serveur (seulement une convention d'interface).

## [0.9-beta3] - 2026-07-24

### Ajouté
- CONFIG : les bandes et modes proposés pour un concours sélectionné reflètent désormais le vrai règlement serveur (calendrier + définitions), plus un objet client dupliqué à la main qui pouvait dériver.
- DXHeat ajouté comme 6e source cluster HF+VHF/UHF, avec locator structuré (plus fiable qu'un regex sur commentaire).
- Carte MUF mondiale graphique en direct (hamqsl.com) sur la page Propagation et en vignette sur l'écran mural.
- Carte de foudre en direct (Blitzortung.org) intégrée à la page Propagation + lien depuis l'écran mural.
- Fuseaux horaires DX de référence sur l'écran mural, au-delà d'UTC et de l'heure locale.
- Sélecteur de dossier natif Windows pour la sauvegarde automatique (CONFIG).
- Raccourci bureau proposé au premier lancement de l'exécutable figé.

### Modifié
- Décodeur CW : suppression d'un panneau en double qui cassait silencieusement le bouton, et correction de l'affichage qui pouvait cacher l'enregistreur de QSO.
- Traductions complétées (dont le bouton « ENREGISTRER LE QSO », resté en français dans toutes les langues) et corrections structurelles du moteur i18n pour le texte généré dynamiquement.

### Corrigé
- 4 défauts de revue adversariale sur les filtres bandes/modes (les deux axes doivent être restreints indépendamment) et sur les spots DXHeat (priorité du locator structuré, doublons entre les lots HF et VHF/UHF).
- Cache de calendrier externe retiré du suivi git (régénéré automatiquement, n'avait jamais dû être versionné) + bouton « SANS DUPES » qui ne se traduisait jamais.

## [0.9-beta2] - 2026-07-24

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
