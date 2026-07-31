# LogX AI

**Le premier logbook de contest radioamateur qui lit un règlement et s'adapte tout seul.**

Un copilote IA en temps réel recommande le prochain meilleur QSO, un moteur de score générique s'auto-configure sur n'importe quel concours, et tout tourne en local — sans cloud obligatoire, sans abonnement.

[💛 Soutenir le projet sur HelloAsso](LIEN_HELLOASSO_A_COMPLETER) · [📖 Guide utilisateur](docs/GUIDE_UTILISATEUR.md) · [📋 PRD / roadmap](docs/LogX_AI_PRD.md) · [🗒️ Journal des modifications](docs/CHANGELOG.md)

---

## Pourquoi LogX AI

La plupart des loggers de contest radioamateur imposent une liste figée de règlements codés en dur. LogX AI **lit le règlement** (PDF ou page web, en français ou en anglais), en extrait bandes/dates/échange/barème via une IA vérifiée par une passe adversariale, et reconfigure son moteur de score sans qu'une ligne de code ne soit écrite — la définition proposée reste **toujours soumise à relecture humaine** avant d'être activée.

- **Copilote IA en session** : recommandation RUN vs Search & Pounce, plan de bande selon l'heure et le barème, impact score de chaque spot. Il sait **à quel usage il répond** — carnet de trafic courant, concours, expédition ou radioclub n'ont pas les mêmes besoins, et l'assistant ne parle pas stratégie de concours à quelqu'un qui chasse tranquillement le DX.
- **Profondeur propagation** : solaire (N0NBH), MUF réelle (ionosondes KC2G), tropo, météores, grey-line, prévision Es/aurore.
- **Ancrage radioamateur français** : concours REF (RPH, THF, HF), départements REF, export EDI/REG1TEST natif — un créneau que les loggers anglophones couvrent mal.
- **Local-first** : serveur local (port 8080), données dans le profil utilisateur, fonctionne aussi hors connexion Internet — le terrain n'a pas toujours de réseau.
- **Multi-poste** : plusieurs opérateurs sur le même WiFi local, log partagé en temps réel.
- **Pensé pour plusieurs écrans** : chaque panneau se détache dans sa propre fenêtre, y compris **autant de fenêtres par bande qu'on veut** — cinq bandes surveillées côte à côte sur un deuxième écran.

## Fonctionnalités

- **41 concours intégrés** (REF, IARU R1, CQ WW/WPX, ARRL DX/FD, SOTA/POTA, WAE, UBA, Russian DX, All Asian, Stew Perry, ARRL 10/160m…) + **le calendrier mondial WA7BNM au complet** (≈360 épreuves pour 2026), préparables en un clic.
- **Page FOCUS BANDE** : tout ce que le logiciel sait d'une bande sur un seul écran — cluster filtré bande **et** mode, carrés, ouvertures par région, concours actifs à cet instant, suggestions de l'IA, et le classement de toutes les bandes avec la raison écrite en clair. La bande se choisit à la main ou **suit la radio**.
- Radio CAT via Hamlib/rigctld, TCI, pont WSJT-X ; pilotage ampli et rotor.
- **Wait & Pounce** en FT8/FT4 : appel automatique sur ce que LogX sait déjà — entité jamais travaillée, entité non confirmée LoTW sur ce créneau bande × mode, carré neuf, nouveau multiplicateur. Quatre niveaux activables séparément, du simple signalement à l'appel sans personne devant la radio, avec durée maximale, plafonds et coupe-circuit.
- Band map, bandscope, chute d'eau, **décodeur CW** ; clusters DX multi-sources, RBN, PSK Reporter, balises NCDXF/IBP.
- Callbook (QRZ/HamQTH/HamDB), historique d'indicatifs (Super Check Partial, MASTER.SCP, Call History N1MM), DXCC/pays.
- Programmes portables POTA/SOTA/IOTA/WWFF/WCA, chasse aux départements français, diplômes, satellites (`PROP_MODE=SAT` à l'export).
- Export Cabrillo v3 / ADIF 3 / EDI, upload eQSL/ClubLog/LoTW, scoreboard en direct.
- Annuaire WebSDR (écoute déportée) ; page CONFIGURATION en hub de catégories, avec une aide contextuelle rédigée pour chaque réglage.
- **Mise à jour proposée automatiquement**, sans perte de données — et, sur le terrain, relayable par un poste voisin du réseau local quand un seul a Internet.
- Interface en 8 langues, mode débutant/expert, quatre modes d'utilisation (carnet simple, concours, expédition, radioclub).

## Démarrage rapide

1. Télécharger l'exécutable de la [dernière release](../../releases/latest) (`LogXAI-vX.Y.exe` pour Windows, `-macos`/`-linux` pour les autres OS) ou lancer `python logx_serveur.py` depuis `concours/` (Python 3).
2. **Première utilisation** : le navigateur s'ouvre sur `http://127.0.0.1:8080/logx_configuration.html`. Renseigner l'indicatif, puis les catégories utiles (station, concours, radio, propagation) — 3 clics suffisent pour un concours déjà connu.
3. **Ensuite** : le logiciel ouvre directement le carnet, `http://127.0.0.1:8080/logx_logbook.html`. La configuration reste accessible depuis la barre de statut, mais elle ne s'impose plus à chaque démarrage.

Guide complet, dépannage et FAQ : [docs/GUIDE_UTILISATEUR.md](docs/GUIDE_UTILISATEUR.md).

## Statut du projet

Version courante : **0.9-beta12** ([journal des modifications](docs/CHANGELOG.md)). Phases 0 à 4 livrées, Phase 5 (validation terrain) en cours. Roadmap détaillée et exigences à venir dans [docs/LogX_AI_PRD.md](docs/LogX_AI_PRD.md).

Le logiciel se met à jour tout seul : au lancement, il compare sa version à la dernière release et propose le téléchargement, dont il vérifie l'empreinte SHA-256 avant de remplacer quoi que ce soit.

## Soutenir le projet

LogX AI est développé bénévolement, avec l'aide d'un copilote IA (Claude, Anthropic) pour l'assistance au développement — un coût récurrent pour le mainteneur. Si le logiciel vous rend service, un don via **[HelloAsso](LIEN_HELLOASSO_A_COMPLETER)** (au profit du radioclub) aide à couvrir cet abonnement et à faire vivre le projet. Aucune contrepartie, aucune fonctionnalité fermée derrière un paywall — le logiciel reste et restera gratuit.

## Licence

À définir (discussion en cours — voir [docs/LogX_AI_PRD.md](docs/LogX_AI_PRD.md), §13).

## Contact

Équipe F6KQJ.
