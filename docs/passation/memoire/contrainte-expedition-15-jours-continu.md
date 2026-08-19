---
name: contrainte-expedition-15-jours-continu
description: "En DXpédition, les postes tournent jusqu'à 15 jours d'affilée 24h/24 — toute fuite de ressource, même infime, devient fatale"
metadata: 
  node_type: memory
  type: project
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-07-26T05:12:09.244Z
---

Information donnée par l'utilisateur le 26/07/2026 : **en expédition, les postes tournent jusqu'à 15 jours sans interruption, 24h sur 24** (soit 360 h).

**Pourquoi ça change les décisions techniques** : une fuite invisible sur un test de quelques secondes devient une panne certaine à cette échelle. Un fil d'exécution ou quelques kilo-octets non libérés par connexion, multipliés par des dizaines de milliers de cycles, finissent par immobiliser le serveur — au milieu d'une expédition, à l'endroit précis où personne ne peut rien réparer et où le log est irremplaçable.

**Conséquence pour toute modification touchant le serveur, le réseau ou une boucle de fond** : ne jamais se contenter d'un test court. Mesurer les ressources (fils, mémoire) sur plusieurs milliers de cycles.

**PIÈGE de méthode, rencontré immédiatement** : une extrapolation LINÉAIRE à partir d'un seul point de mesure est trompeuse. Premier test du passage HTTP/1.1 → +0,43 Mo sur 500 cycles → extrapolait à +368 Mo sur 15 jours, alarmant. En mesurant la FORME de la courbe (8 paliers de 500 cycles), la croissance s'aplatit : +0,07 Mo sur 4000 cycles, soit ~7 Mo sur 15 jours. Le premier chiffre n'était que du bruit de démarrage de l'allocateur. **Toujours vérifier si la courbe plafonne ou croît linéairement avant de conclure à une fuite** — et faire une phase de chauffe avant la mesure de référence.

Scripts de mesure réutilisables (session du 26/07/2026, à recréer au besoin) : ouvrir N connexions en cycles, mesurer `threading.active_count()` et `psutil.Process().memory_info().rss` à plusieurs paliers, comparer la croissance du premier tiers à celle du dernier. Exercer les DEUX chemins de fermeture : fermeture par le client, et expiration par délai d'inactivité côté serveur (chemin introduit par HTTP/1.1, le plus emprunté sur la durée).

Voir [[chantier-http11-keepalive]] pour le contexte du changement qui a motivé cette mesure.
