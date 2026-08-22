---
name: decisions-et-references
description: "Décisions produit tranchées (à ne pas rouvrir seul) + matériel de référence technique (protocoles CAT propriétaires, contraintes matérielles, veille) pour LogX AI — fusion de 8 fiches, 21/08/2026"
metadata: 
  node_type: memory
  type: reference
  originSessionId: e5854853-072f-4b5f-895a-57c4ab0111d2
  modified: 2026-08-21T12:16:09.768Z
---

Consolidation du 21/08/2026. Fiches d'origine conservées dans `docs/passation/memoire/` du dépôt.

## Décisions produit tranchées

- **OCR carnet papier : abandonné définitivement** (13/08/2026, décision explicite F4GLD — « on va oublier l'histoire de la reconnaissance OCR »). Pas buildable en un lot raisonnable : aucune dépendance OCR dans le projet, et le vrai obstacle est l'écriture manuscrite non standardisée. Ne pas la reproposer proactivement, même dans une réflexion Expédition (saisie hors-ligne) — si le sujet revient, c'est F4GLD qui le rouvrira.
- **Migration de dépôt GitHub : FAITE** (vérifiée le 21/08/2026, la fiche d'origine disait « planifiée » — périmée, corrigée ici). Un seul dépôt reste sous le compte : `sauveteur71/LogX_AI` (date de création 15/07/2026 = celle du dépôt de CODE d'origine, confirmant un renommage et pas une recréation — historique/PR/issues préservés). L'ancien nom `radioaamateur-program-Contest` redirige (HTTP 200) vers `LogX_AI`. `GITHUB_REPO` dans `logx_update.py` pointe déjà vers `sauveteur71/LogX_AI`. Le wiki existe et a du contenu. Le site vitrine est intégré via une branche `gh-pages` (Pages GitHub construite et live, `https://sauveteur71.github.io/LogX_AI/`). Rien à refaire sur ce point — si un audit futur le re-signale comme « à faire », vérifier par `gh api user/repos` avant de le croire.
- **Affichage par `usage_mode`** (simple/contest/expedition/radioclub) : axe séparé du MODE RADIO courant (SSB/CW/FT8...) — à ne jamais confondre dans le code. Principe retenu : masquer ≠ bloquer l'accès, un élément secondaire dans un mode donné reste accessible en discret, jamais supprimé.
- **Vocabulaire, concurrents, workflow git** : voir `regles-produit-permanentes.md`.

## Contraintes matérielles/produit à garder en tête

- **Expédition = jusqu'à 15 jours d'affilée, 24h/24 (360h).** Toute fuite de ressource même infime devient fatale à cette échelle, au pire moment (le log est irremplaçable, personne ne peut réparer sur place). Pour toute modification touchant le serveur/le réseau/une boucle de fond : mesurer les ressources (fils, mémoire) sur plusieurs MILLIERS de cycles, jamais un test court. Piège de méthode : une extrapolation LINÉAIRE depuis un seul point de mesure trompe — vérifier la FORME de la courbe (plusieurs paliers) avant de conclure à une fuite ; le bruit de démarrage de l'allocateur peut ressembler à une fuite grave sur un seul point.
- **Diffusion publique à des inconnus** : jamais de blocage pour IP figée, antivirus, ou absence de connexion (terrain /P en zone blanche = cas central, pas limite). Tout appel réseau externe doit passer par le patron établi (thread jetable + timeout dur), voir `pieges-techniques.md` section H pour le détail config.

## Référence — protocoles CAT/ampli propriétaires (recherche du 06/08/2026)

Avant toute extension CAT/ampli au-delà de l'existant (`logx_cat.py`, `logx_amp.py` avec `TcpAmpPort`/`UdpAmpPort`/`KpaAmp`/`IcomAmp`/`SpeAmp`) :

| Protocole | Doc officielle | Ports | Prêt à coder |
|---|---|---|---|
| OmniRig (VE3NEA) | oui — http://www.dxatlas.com/omnirig/inistru.txt | — (COM local) | oui |
| FlexRadio SmartSDR | oui, exhaustive — github.com/flexradio/smartsdr-api-docs/wiki | TCP 4992 (contrôle) / UDP 4991 (streaming VITA-49) | oui |
| PowerGenius XL (4O3A) | oui, mais mal indexée (dans le wiki SmartSDR, pas le dépôt officiel 4o3a) | TCP+UDP 9008 | oui |
| Icom CI-V série | oui — manuel générique 1993 | — (série, trame `FE FE <dest> <ctrl> <cmd> ... FD`) | oui |
| Icom réseau/RS-BA1 (IC-705/7610/905...) | NON, entièrement reverse-engineered (wfview GPLv3 = référence, kappanhang Go) | UDP 50001/50002/50003 | via code source wfview/kappanhang uniquement |
| ACOM | AUCUNE source, ni officielle ni communautaire | inconnu | non, sans reverse engineering matériel |

Ordre d'implémentation recommandé : FlexRadio et PowerGenius XL en premier (doc complète, style proche de l'existant), Icom réseau ensuite si besoin remote, OmniRig si besoin de multiplexer un port CAT, ACOM en dernier (nécessite un sniffer série pendant qu'un logiciel tiers pilote l'ampli).

## Référence — API réelles déjà branchées vs délibérément écartées

- **POTA** : `logx_pota.py`, `GET api.pota.app/spot/activator` (public, sans clé), panneau propagation, cache 90s. Poster son propre spot (`POST /spot/`) volontairement PAS fait — pas de format d'authentification vérifié.
- **SOTA** : `logx_sota.py` (spots + base ~230k sommets) + `logx_sota_spot.py` (auto-spot OAuth SSO PKCE, gate explicite `sota_ai_approval_ack` car les CGU SOTA interdisent tout logiciel généré par IA sans accord préalable).
- **RBN** : telnet direct (`reversebeacon.net:7000`) uniquement. Un repli JSON a été DÉLIBÉRÉMENT écarté après recherche — l'endpoint interne du site n'est pas documenté et change de hash à chaque déploiement, sans filtre serveur par indicatif. Ne pas relancer cette piste sans nouvelle info.
- **ADIF** : validation stricte via `logx_adif_enums.py` (bandes/modes ADIF 3.1.7 officiel, recopié depuis adif.org, offline-first).
- **GridTracker** : intégration mise de côté (21/08/2026) — F4GLD ne l'utilise pas, réflexion possible « dans plusieurs mois ». Un audit avait affirmé « GridTracker émet du ADIF brut en UDP », caractérisation qui ne correspond PAS à son comportement documenté réel : GridTracker REÇOIT de l'ADIF (ex. depuis fldigi), il n'en émet pas nativement ainsi. Il a par contre une retransmission UDP configurable en mode compatible N1MM — et LogX AI a déjà un écouteur pour ce protocole précis (`logx_adifnet.py`, port 12060). Donc si le sujet revient : commencer par vérifier si un simple réglage côté GridTracker (pointer sa retransmission N1MM vers le port 12060) suffit, avant d'envisager du code nouveau — ne pas repartir sur la caractérisation « ADIF brut » de l'audit d'origine, déjà invalidée.
