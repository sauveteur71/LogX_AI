# LogX AI

**Le premier logbook de contest radioamateur qui lit un règlement et s'adapte tout seul.**

Un copilote IA en temps réel recommande le prochain meilleur QSO, un moteur de score générique s'auto-configure sur n'importe quel concours, et tout tourne en local — sans cloud obligatoire, sans abonnement.

[💛 Soutenir le projet sur HelloAsso](LIEN_HELLOASSO_A_COMPLETER) · [📖 Guide utilisateur](docs/GUIDE_UTILISATEUR.md) · [📋 PRD / roadmap](docs/LogX_AI_PRD.md)

---

## Pourquoi LogX AI

La plupart des loggers de contest radioamateur imposent une liste figée de règlements codés en dur. LogX AI **lit le règlement** (PDF ou page web, en français ou en anglais), en extrait bandes/dates/échange/barème via une IA vérifiée par une passe adversariale, et reconfigure son moteur de score sans qu'une ligne de code ne soit écrite — la définition proposée reste **toujours soumise à relecture humaine** avant d'être activée.

- **Copilote IA en session** : recommandation RUN vs Search & Pounce, plan de bande selon l'heure et le barème, impact score de chaque spot.
- **Profondeur propagation** : solaire (N0NBH), MUF réelle (ionosondes KC2G), tropo, météores, grey-line, prévision Es/aurore.
- **Ancrage radioamateur français** : concours REF (RPH, THF, HF), départements REF, export EDI/REG1TEST natif — un créneau que les loggers anglophones couvrent mal.
- **Local-first** : serveur local (port 8080), données dans le profil utilisateur, fonctionne aussi hors connexion Internet — le terrain n'a pas toujours de réseau.
- **Multi-poste** : plusieurs opérateurs sur le même WiFi local, log partagé en temps réel.

## Fonctionnalités

- **36 concours intégrés** (REF, IARU R1, CQ WW/WPX, ARRL DX/FD, SOTA/POTA, WAE, UBA, Russian DX, All Asian, Stew Perry, ARRL 10/160m…) + **358 concours mondiaux** (calendrier WA7BNM) préparables en un clic.
- Radio CAT via Hamlib/rigctld, TCI, pont WSJT-X ; pilotage ampli et rotor.
- Clusters DX multi-sources, RBN, PSK Reporter, balises NCDXF/IBP.
- Callbook (QRZ/HamQTH/HamDB), historique d'indicatifs (Super Check Partial), DXCC/pays.
- Programmes d'activation POTA/SOTA/IOTA/WWFF, chasse aux départements français, diplômes.
- Export Cabrillo v3 / ADIF 3 / EDI, upload eQSL/ClubLog/LoTW, scoreboard en direct.
- Annuaire WebSDR (écoute déportée) + assistant de configuration guidé.
- Interface en 8 langues, mode débutant/expert.

## Démarrage rapide

1. Télécharger `LogXAI.exe` (Windows/macOS) ou lancer `python logx_serveur.py` depuis `concours/` (Python 3).
2. Ouvrir `http://127.0.0.1:8080/logx_configuration.html` — le navigateur s'ouvre automatiquement en version packagée.
3. Suivre l'assistant de configuration (station, concours, filtres, propagation) — 3 clics suffisent pour un concours déjà connu.

Guide complet, dépannage et FAQ : [docs/GUIDE_UTILISATEUR.md](docs/GUIDE_UTILISATEUR.md).

## Statut du projet

Phases 0 à 4 livrées, Phase 5 (validation terrain) en cours. Roadmap détaillée et exigences à venir dans [docs/LogX_AI_PRD.md](docs/LogX_AI_PRD.md).

## Soutenir le projet

LogX AI est développé bénévolement, avec l'aide d'un copilote IA (Claude, Anthropic) pour l'assistance au développement — un coût récurrent pour le mainteneur. Si le logiciel vous rend service, un don via **[HelloAsso](LIEN_HELLOASSO_A_COMPLETER)** (au profit du radioclub) aide à couvrir cet abonnement et à faire vivre le projet. Aucune contrepartie, aucune fonctionnalité fermée derrière un paywall — le logiciel reste et restera gratuit.

## Licence

À définir (discussion en cours — voir [docs/LogX_AI_PRD.md](docs/LogX_AI_PRD.md), §13).

## Contact

Équipe F6KQJ.
