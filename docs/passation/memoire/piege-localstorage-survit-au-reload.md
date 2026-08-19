---
name: piege-localstorage-survit-au-reload
description: "PIÈGE vérification navigateur : écrire dans localStorage.logx_config pour un test DOM-only laisse l'onglet dans un état trompeur — recharger la page (même force:true) ne resynchronise PAS depuis le serveur, il faut refetch /config et réécrire localStorage explicitement"
metadata:
  type: project
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-08-08T12:47:47.873Z
---

Trouvé le 08/08/2026 pendant [[chantier-fix-op1-adif-station-callsign-2026-08-08]].

## Le piège

Pour vérifier `_resolveOperatorCallsign()` sans déclencher de vrai
`saveConfig()` (interdit contre le serveur de production), j'ai écrit
directement dans `localStorage.setItem('logx_config', JSON.stringify({...
valeurs de test ...}))` sur un onglet du navigateur intégré pointant sur
`http://localhost:8080/logx_logbook.html` (serveur de production, jamais
redémarré). Une fois la vérification terminée, j'ai supposé qu'un simple
`navigate({url, force:true})` vers la même page suffirait à "remettre les
choses en ordre" en rechargeant le vrai config depuis le serveur.

**Faux** : `localStorage` est un cache CLIENT persistant par origine, pas
réhydraté automatiquement à chaque chargement de page tant que rien dans le
JS de la page ne le fait explicitement (et ce n'est pas garanti). Vérifié
via `fetch('/config')` (le vrai endpoint serveur, PAS `/config/load` qui
n'existe pas) : le serveur portait toujours `callsign_contest: 'F4GLD/P'`,
alors que `localStorage` de cet onglet affichait encore `'F6KQJ'` (ma
valeur de test) APRÈS le reload.

## Comment l'avoir détecté plus tôt

Après tout `localStorage.setItem()` de test sur une page qui lit sa config
depuis le serveur, ne JAMAIS supposer qu'un reload la purge — vérifier
explicitement en comparant `localStorage.getItem('logx_config')` à
`fetch('/config')` (ou l'endpoint réel équivalent) APRÈS le reload, pas
seulement juste après l'écriture de test.

## Correctif qui fonctionne à coup sûr

```js
fetch('/config').then(r=>r.json()).then(cfg => {
  localStorage.setItem('logx_config', JSON.stringify(cfg));
});
```
Refetch le vrai config serveur et réécrit `localStorage` explicitement avec
les valeurs réelles — ne pas se fier à un `navigate()` pour "nettoyer après
soi" un `localStorage` de test.

## Comment l'appliquer

Toute vérification navigateur future qui écrit dans `localStorage` (config,
état applicatif quelconque) sur une page servie par le serveur de
production doit se terminer par une restauration EXPLICITE depuis
l'endpoint serveur réel — pas juste un `navigate({force:true})`, qui ne
touche que le cache HTTP des sous-ressources (`<script src>`, voir
[[piege-cache-navigateur-masque-changement-js]], un piège voisin mais
distinct : celui-là concerne le code JS servi, celui-ci l'état applicatif
en localStorage), jamais le contenu de `localStorage` lui-même.
