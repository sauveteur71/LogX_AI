# LogX AI

**Le premier logbook de contest radioamateur qui lit un règlement et s'adapte tout seul.**

Un copilote IA en temps réel recommande le prochain meilleur QSO, un moteur de score générique s'auto-configure sur n'importe quel concours, et tout tourne en local — sans cloud obligatoire, sans abonnement.

[💛 Soutenir le projet sur HelloAsso](https://www.helloasso.com/associations/radioclub-du-velay/formulaires/2) · [📖 Guide utilisateur](docs/GUIDE_UTILISATEUR.md) · [📋 PRD / roadmap](docs/LogX_AI_PRD.md) · [🗒️ Journal des modifications](docs/CHANGELOG.md)

---

## Nouveau dans la série 1.2

- 🤖 **Copilote FT8 / CW / SSB** : l'IA prépare l'échange à l'indicatif résolu (CW/SSB) et, en FT8, propose la réponse puis **émet après un délai réglable sauf annulation** — jamais d'émission sans validation, chaque émission gravée dans un journal d'audit consultable.
- 🗺️ **Aides « départements » (concours REF THF/HF)** : grille 00-99 en un clic, panneau « départements à faire » trié par proximité de fréquence ou par rareté, et stations de départements manquants surlignées sur le band map — un clic **QSY sur leur fréquence + pré-remplit le QSO**.
- 📇 **Saisie assistée** : prénom, drapeau et locator du correspondant auto-remplis (base interne puis internet, corrigeables) ; heure de fin du QSO automatique.
- 📴 **Autonomie « zone blanche » renforcée** : cartes (Leaflet) et graphiques (Chart.js) désormais **embarqués localement** — plus aucune dépendance CDN, l'application charge et fonctionne sans Internet.
- 🖼️ **SSTV enrichie** : 9 modes supplémentaires (Martin M3/M4, Scottie S3/S4, Robot 8/12/24 N&B, Wraase SC2-120/180) portant à **23 le nombre de modes reçus et émis** dans le navigateur, avec détection automatique du mode (en-tête VIS).
- 🎚️ **FT8 plus simple à régler** : appairage automatique entrée/sortie audio du **même appareil**, écoute qui **démarre toute seule**, **vu-mètre de niveau RX** (repère WSJT-X, pour régler le volume d'entrée), et **SNR affiché** dans la liste des CQ pour choisir qui appeler.

### Déjà apporté par la série 1.1

- 📡 **VOACAP point-à-point** : vrai moteur de prévision de propagation entre votre station et n'importe quel point du globe, directement dans le carnet et sur la carte.
- 🎙️ **FT8 et RTTY natifs dans le navigateur** : décodage/émission sans WSJT-X/JTDX/MSHV ni logiciel tiers, chacun dans sa propre fenêtre détachable.
- 🖨️ **Designer de carte QSL imprimable**, export PNG/JPG en quelques clics.

## Pourquoi LogX AI

La plupart des loggers de contest radioamateur imposent une liste figée de règlements codés en dur. LogX AI **lit le règlement** (PDF ou page web, en français ou en anglais), en extrait bandes/dates/échange/barème via une IA vérifiée par une passe adversariale, et reconfigure son moteur de score sans qu'une ligne de code ne soit écrite — la définition proposée reste **toujours soumise à relecture humaine** avant d'être activée.

- **Copilote IA en session** : recommandation RUN vs Search & Pounce, plan de bande selon l'heure et le barème, impact score de chaque spot. Il sait **à quel usage il répond** — carnet de trafic courant, concours, expédition ou radioclub n'ont pas les mêmes besoins, et l'assistant ne parle pas stratégie de concours à quelqu'un qui chasse tranquillement le DX.
- **Profondeur propagation** : solaire (N0NBH), MUF réelle (ionosondes KC2G), tropo, météores, grey-line, prévision Es/aurore.
- **Ancrage radioamateur français** : concours REF (RPH, THF, HF), départements REF, export EDI/REG1TEST natif — un créneau que les loggers anglophones couvrent mal.
- **Local-first** : serveur local (port 8080), données dans le profil utilisateur, fonctionne aussi hors connexion Internet — le terrain n'a pas toujours de réseau.
- **Multi-poste** : plusieurs opérateurs sur le même WiFi local, log partagé en temps réel.
- **Pensé pour plusieurs écrans** : chaque panneau se détache dans sa propre fenêtre, y compris **autant de fenêtres par bande qu'on veut** — cinq bandes surveillées côte à côte sur un deuxième écran.

## Fonctionnalités

- **41 concours prêts à l’emploi** (REF, IARU R1, CQ WW/WPX, ARRL DX/FD, SOTA/POTA, WAE, UBA, Russian DX, All Asian, Stew Perry, ARRL 10/160m…) + **le calendrier mondial WA7BNM au complet** (≈360 épreuves pour 2026), préparables en un clic.
- **Page FOCUS BANDE** : tout ce que le logiciel sait d'une bande sur un seul écran — cluster filtré bande **et** mode, carrés, ouvertures par région, concours actifs à cet instant, suggestions de l'IA, et le classement de toutes les bandes avec la raison écrite en clair. La bande se choisit à la main ou **suit la radio**.
- Radio CAT via Hamlib/rigctld, TCI, pont WSJT-X ; pilotage ampli et rotor.
- **Wait & Pounce** en FT8/FT4 : appel automatique sur ce que LogX sait déjà — entité jamais travaillée, entité non confirmée LoTW sur ce créneau bande × mode, carré neuf, nouveau multiplicateur. Quatre niveaux activables séparément, du simple signalement à l'appel sans personne devant la radio, avec durée maximale, plafonds et coupe-circuit.
- Band map, bandscope, chute d'eau, **décodeur CW** ; clusters DX multi-sources, RBN, PSK Reporter, balises NCDXF/IBP.
- **FT8 et RTTY natifs dans le navigateur** : décodage/émission sans WSJT-X/JTDX/MSHV ni logiciel tiers, chacun dans sa propre fenêtre détachable — clic sur un indicatif décodé pour le renvoyer directement dans le carnet.
- **SSTV native dans le navigateur** : réception **et** émission d'images sans MMSSTV ni RX-SSTV, **23 modes** (Martin M1-M4, Scottie S1-S4/DX, Robot 36/72 couleur et 8/12/24 N&B, PD50-290, Wraase SC2-120/180), mode reconnu automatiquement à la réception (en-tête VIS).
- **Panadapter** : spectre + chute d'eau depuis l'audio de réception (universel, zéro matériel), le scope CI-V natif des Icom (IC-7300/7610/9700/705/7851, large bande), ou le flux IQ d'un serveur TCI (Flex/SunSDR).
- **VOACAP point-à-point** : vrai moteur de prévision de propagation (NTIA/ITS) entre votre station et n'importe quel point du globe, intégré au carnet et à la carte.
- Callbook (QRZ/HamQTH/HamDB), historique d'indicatifs (Super Check Partial, MASTER.SCP, fichiers d'historique par concours), DXCC/pays.
- Programmes portables POTA/SOTA/IOTA/WWFF/WCA, chasse aux départements français, diplômes, satellites (`PROP_MODE=SAT` à l'export).
- Export Cabrillo v3 / ADIF 3 / EDI, upload eQSL/ClubLog/LoTW, scoreboard en direct, **designer de carte QSL imprimable** (export PNG/JPG).
- Annuaire WebSDR vivant (~900 récepteurs, rafraîchi en ligne, carte cliquable, occupation et SNR en direct) : « s'écouter » depuis le band map, ou écouter un spot sur un récepteur proche du DX avant de l'appeler.
- Page CONFIGURATION en hub de catégories, avec une aide contextuelle rédigée pour chaque réglage.
- **Mise à jour proposée automatiquement**, sans perte de données — et, sur le terrain, relayable par un poste voisin du réseau local quand un seul a Internet.
- Interface en 8 langues, mode débutant/expert, quatre modes d'utilisation (carnet simple, concours, expédition, radioclub).

## Démarrage rapide

1. Télécharger l'exécutable de la [dernière release](../../releases/latest) (`LogXAI-vX.Y.exe` pour Windows, `-macos`/`-linux` pour les autres OS) ou lancer `python logx_serveur.py` depuis `concours/` (Python 3). *Windows peut afficher « Windows a protégé votre PC » au premier lancement (exécutable non signé, avertissement normal) : cliquer sur « Informations complémentaires » puis « Exécuter quand même ».*
2. **Première utilisation** : le navigateur s'ouvre sur `http://127.0.0.1:8080/logx_configuration.html`. Renseigner l'indicatif, puis les catégories utiles (station, concours, radio, propagation) — 3 clics suffisent pour un concours déjà connu.
3. **Ensuite** : le logiciel ouvre directement le carnet, `http://127.0.0.1:8080/logx_logbook.html`. La configuration reste accessible depuis la barre de statut, mais elle ne s'impose plus à chaque démarrage.

Guide complet, dépannage et FAQ : [docs/GUIDE_UTILISATEUR.md](docs/GUIDE_UTILISATEUR.md).

## Statut du projet

Version courante : **1.2-beta8** ([journal des modifications](docs/CHANGELOG.md)). La dernière version marquée stable est la **1.0**. La série 1.1 a apporté le FT8/RTTY natifs, VOACAP et la protection du carnet ; la série 1.2 ajoute le copilote FT8/CW/SSB, les aides « départements », l'autonomie hors-ligne complète, l'enrichissement SSTV (23 modes) et une page FT8 plus simple à régler. Utilisée quotidiennement en trafic réel, mais reste une bêta et le dit.

Couverture : **plus de 10 000 tests automatiques** rejoués à chaque modification par l'intégration continue. Roadmap détaillée dans [docs/LogX_AI_PRD.md](docs/LogX_AI_PRD.md).

Le logiciel se met à jour tout seul : au lancement, il compare sa version à la dernière release et propose le téléchargement, dont il vérifie l'empreinte SHA-256 avant de remplacer quoi que ce soit.

## Soutenir le projet

LogX AI est développé bénévolement, avec l'aide d'un copilote IA (Claude, Anthropic) pour l'assistance au développement — un coût récurrent pour le mainteneur. Si le logiciel vous rend service, un don via **[HelloAsso](https://www.helloasso.com/associations/radioclub-du-velay/formulaires/2)** (au profit du radioclub) aide à couvrir cet abonnement et à faire vivre le projet. Aucune contrepartie, aucune fonctionnalité fermée derrière un paywall — le logiciel reste et restera gratuit.

## Contribuer

Un bug, une idée ? Les [gabarits d'issue](.github/ISSUE_TEMPLATE/) guident le
signalement, aucune connaissance technique requise. Pour proposer du code,
voir [CONTRIBUTING.md](CONTRIBUTING.md) (installation, tests, conventions) —
toute contribution est soumise au [code de conduite](CODE_OF_CONDUCT.md) du
projet.

## Échanger avec d'autres utilisateurs

Le groupe [groups.io/g/LogXAI](https://groups.io/g/LogXAI) sert au support,
aux retours d'expérience en concours réel, aux demandes de fonctionnalités
et aux annonces de version — ouvert à tous, utilisateurs actuels comme
curieux.

## API locale

Le serveur local expose environ 220 endpoints HTTP (journal de trafic,
configuration, cluster DX, propagation, pilotage radio...) documentés dans
[docs/API.md](docs/API.md) — de quoi brancher un script ou un tableau de
bord tiers dessus.

## Licence

[GNU GPLv3](LICENSE) — cohérent avec l'écosystème radioamateur libre (Tucnak, qxsl). Le code reste et restera librement redistribuable et modifiable ; toute version dérivée diffusée doit rester elle aussi sous GPLv3.

## Contact

Équipe F6KQJ.
