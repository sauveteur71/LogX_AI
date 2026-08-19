---
name: chantier-wait-and-pounce-4-niveaux
description: "Wait-and-Pounce livré en 4 commits (30/07/2026) — F4GLD a explicitement voulu l'émission SANS SURVEILLANCE ; + le piège Qt double précision de l'UDP WSJT-X"
metadata: 
  node_type: memory
  type: project
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-07-30T17:53:26.521Z
---

Wait-and-Pounce livré le 30/07/2026 en quatre commits séparés à dessein : `f9b30d7` (sens sortant UDP), `c82a75d` (niveau 2, armer au clic), `ea3d73b` (moteur de décision, inerte), `abbd179` (câblage — c'est là que le logiciel se met à émettre seul), `5e617c7` (écran).

**LA DÉCISION DE L'UTILISATEUR, à ne pas rouvrir.** J'ai signalé que le niveau 4 fait émettre la station sans personne devant elle et que c'est une question de responsabilité d'opérateur, pas de faisabilité. Réponse : « je voudrais que les 4 options soit possible mais je voudrais pouvoir choisir de les activer ou pas, tout automatique veux dire personne devant la radio ». C'est **construit et assumé**. Ne pas re-poser la question ; les garde-fous sont la réponse d'ingénieur, pas un refus déguisé.

Note factuelle utile : « Wait and Pounce » est un utilitaire précis de **F5UKW** pour FT8 (appelle seul via UDP WSJT-X/JTDX, exclusions, règles « worked before »), à ne pas confondre avec **Search & Pounce**, la technique de trafic — que LogX faisait déjà (band map, `bandmapNoter`, `bandmapSaut`).

**PIÈGE DE PROTOCOLE, silencieux :** Qt sérialise en **double précision**. Un champ déclaré `float` côté WSJT-X occupe **8 octets** sur le fil, pas 4. En écrire 4 décale tout ce qui suit et WSJT-X **jette le datagramme sans erreur** — on croit que « ça ne marche pas ». Méthode retenue : écrire avec `_Writer` puis relire avec le parseur **déjà en production** (`parse_message`) ; s'ils divergent d'un octet, un test tombe. Le parseur JETAIT `time_ms`, `snr`, `dt` et l'`id` d'instance — or un `Reply` doit les renvoyer À L'IDENTIQUE, c'était le vrai verrou.

**Architecture, et pourquoi :** `logx_pounce.py` est **pur** (ni socket, ni HTTP, ni logx_wsjtx — deux tests le verrouillent sur l'**AST**, pas sur le texte, parce que la source mentionne `logx_wsjtx` dans le commentaire expliquant qu'elle ne l'importe pas). La décision tourne dans le **thread UDP**, jamais dans un handler HTTP : « personne devant la radio » veut dire personne pour ouvrir un navigateur.

**Garde-fous** (chacun contre une façon de mal finir) : durée max avec désarmement automatique ; un seul appel en vol ; 3 appels max par station ; plafond 30 appels/quart d'heure qui **désarme** ; journal de tout ce qui part ; session **jamais persistée** (un redémarrage ne doit pas relancer l'émission). Règle générale : **un réglage illisible retombe au niveau 1 SIGNALER** — le doute ne profite jamais à l'émission, exactement l'inverse de [[piege-verifier-sur-donnees-reelles]] côté filtres de spots où le doute profite à l'affichage.

**RESTE À FAIRE, et moi seul ne peux pas :** aucun échange avec un **vrai WSJT-X** n'a été exercé (pas de WSJT-X sur ce poste). L'essai qui tranche : WSJT-X → Réglages → Rapports → serveur UDP sur le PC LogX, puis clic sur un indicatif dans CARRÉS ENTENDUS. S'il apparaît dans WSJT-X, toute la chaîne tient — les niveaux 3 et 4 reposent sur le même message `Reply`.
