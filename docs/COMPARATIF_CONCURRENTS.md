# LogX AI face aux grands loggers de contest — comparatif honnête

Document de positionnement, pas une brochure : les points forts établis des
trois grands loggers de concours (N1MM Logger+, Win-Test, DXLog.net) et du
logbook généraliste Log4OM sont reconnus tels quels, avec des décennies
d'usage réel derrière eux. L'objectif n'est pas de prétendre les remplacer
du jour au lendemain, mais de montrer où LogX AI apporte quelque chose que
ces logiciels n'ont pas — et où il leur manque encore de la maturité.

*Sources : documentation publique de chaque projet (n1mmwp.hamdocs.com,
win-test.com, dxlog.net/docs, log4om.com), août 2026. Vérifié avant
publication plutôt que reconstruit de mémoire — un fait erroné sur un
logiciel nommé se retournerait immédiatement contre ce document dans une
communauté aussi technique.*

## Tableau de synthèse

| | **N1MM Logger+** | **Win-Test** | **DXLog.net** | **Log4OM V2** | **LogX AI** |
|---|---|---|---|---|---|
| Prix | Gratuit | Gratuit (don) | Gratuit | Gratuit | Gratuit |
| Code source | Fermé | Fermé | Fermé | Fermé | **Ouvert (GPLv3)** |
| Plateforme | Windows natif | Windows natif | Windows natif | Windows natif (Wine/émulation ailleurs, non officiel) | **Serveur local, n'importe quel navigateur** (Windows/macOS/Linux/tablette/téléphone) |
| Multi-poste | Réseau LAN natif, très mature | Réseau LAN natif, très mature | Réseau LAN + UDP, très mature | Non (logbook mono-poste) | Réseau WiFi (aucune install sur les postes secondaires) + MySQL partagé |
| SO2R / SO2V | Oui, natif et éprouvé | Oui, natif et éprouvé | Oui, très poussé (double clavier) | Non | Non (pas encore) |
| Concours suivis | Très large (des dizaines) | Très large, fort en Europe | 500+ | Non spécialisé concours | 41 nommés + calendrier mondial WA7BNM + **IA lit un règlement inconnu** |
| Copilote IA / auto-config | Non | Non | Non | Non | **Oui** (need list par valeur réelle, coach rythme RUN/S&P, extraction de règlement) |
| Propagation intégrée | Non (outils tiers) | Non (outils tiers) | Estimations basiques | Non | Solaire/MUF/tropo/Es/EME complet, sans quitter le logiciel |
| POTA/SOTA/WWFF/IOTA | Non natif | Non natif | Non natif | Award tracking générique | Bases complètes en local (415 000+ références), spots, park-to-park |
| Interface | Dense, utilitaire, courbe d'apprentissage réelle | Dense, utilitaire | Moderne parmi les trois | Moderne | Web, thème jour/nuit, 8 langues |
| Ancienneté / communauté | Très large, référence US/mondiale | Référence historique en Europe/France | Référence DXpédition/multi-op sérieux | Populaire logbook généraliste | Récent (2026) |

## Ce que LogX AI n'a pas encore et où ces logiciels sont plus matures

Honnêteté d'abord — un contester sérieux le vérifiera en dix minutes :

- **SO2R/SO2V** : N1MM+, Win-Test et surtout DXLog.net (double clavier,
  scénarios d'interlock) ont des années d'affinage sur le pilotage à deux
  radios. LogX AI n'a pas encore cette brique.
- **Décennies de règles de concours affinées** : chaque cas limite d'un
  concours régional obscur, chaque feuille de dupe adaptée à un barème
  inhabituel — ce niveau de détail se construit avec le temps et des
  milliers d'utilisateurs qui remontent les écarts. LogX AI progresse vite
  (41 concours + IA pour le reste) mais n'a pas ce recul.
- **Vitesse clavier pur** : ces trois loggers sont conçus depuis toujours
  pour un pilotage 100% clavier en concours intensif, réglé par des
  contesters de très haut niveau pendant des années. L'ergonomie web de
  LogX AI est rapide, mais différente — à confirmer en usage réel intensif.

## Ce que LogX AI apporte que ces logiciels n'ont pas

- **Zéro installation sur les postes secondaires.** N1MM+/Win-Test/DXLog
  sont Windows-natifs : chaque poste du réseau installe le même logiciel.
  LogX AI est un serveur local ; les autres postes (Mac, Linux, tablette,
  téléphone) rejoignent le même log en ouvrant une adresse WiFi dans un
  navigateur — rien à installer.
- **Copilote IA.** Aucun des quatre n'a d'assistant qui classe les cibles
  par valeur réelle en points, conseille RUN vs Search & Pounce selon le
  rythme, ou lit le règlement PDF d'un concours inconnu pour proposer sa
  configuration (toujours avec relecture humaine avant activation).
- **Propagation et activation intégrées.** Solaire, MUF réelle, tropo,
  Sporadique-E, EME complet, et les bases POTA/SOTA/WWFF/IOTA/châteaux en
  local (415 000+ références) — ces logiciels renvoient vers des sites tiers
  ou ne couvrent pas ce terrain, LogX AI l'a nativement.
- **Code source ouvert (GPLv3).** Les quatre concurrents sont gratuits mais
  fermés — personne ne peut l'auditer ni y contribuer. LogX AI est
  entièrement ouvert.
- **Import facile depuis ces logiciels.** L'import ADIF de LogX AI
  reconnaît les conventions des exports N1MM+/Win-Test/DXLog/Log4OM (dont le
  mode "PH" et les tags propriétaires `APP_*` préservés) — changer de
  logiciel ne fait pas perdre l'historique.

## Où se recouvrent-ils (comparable, pas un avantage net d'un côté)

- Bandmap, cluster DX, RBN, PSK Reporter, CAT — les quatre concurrents
  couvrent ce terrain depuis longtemps ; LogX AI aussi, avec une intégration
  plus large de marques (OmniRig, FlexRadio SmartSDR natif, Icom réseau,
  PowerGenius XL en plus du CAT générique Hamlib/TCI).
- Export Cabrillo/ADIF, upload eQSL/ClubLog/LoTW : fonctionnalité standard
  des cinq.

## Conclusion honnête

Pour un contester intensif en SO2R sur les grands concours mondiaux,
N1MM+/Win-Test/DXLog restent aujourd'hui la référence — LogX AI ne prétend
pas encore rivaliser sur ce terrain précis. Pour un radioamateur qui veut
UN SEUL logiciel couvrant le trafic courant, les concours nommés, le
portable POTA/SOTA, la propagation et un radio-club multi-poste sans rien
installer ailleurs — avec en prime un copilote IA qu'aucun concurrent
n'a — LogX AI comble un vrai vide.
