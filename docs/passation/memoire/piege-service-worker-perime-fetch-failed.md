---
name: piege-service-worker-perime-fetch-failed
description: "Réutiliser un port de test déjà servi ressuscite un Service Worker qui intercepte tout et casse fetch() avec \"Failed to fetch\" — pas un bug du code testé"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 98b0707f-1a89-40bf-8422-4ab7b88ba78a
  modified: 2026-08-16T07:49:50.538Z
---

Quand une vérification navigateur sur un serveur de test isolé (port
8095-8099 etc., pattern habituel de ce projet) échoue avec des `fetch()`
qui lèvent `TypeError: Failed to fetch` / `net::ERR_FAILED` alors que `curl`
sur le MÊME endpoint réussit parfaitement (200, JSON correct) — ce n'est pas
un bug du serveur ni du code Python : c'est un **Service Worker enregistré
lors d'une session de test PRÉCÉDENTE sur ce même port**, toujours actif
dans le profil du Browser pane, qui intercepte les requêtes de la nouvelle
page et échoue au lieu de les laisser passer au nouveau serveur.

**Why:** Trouvé le 16/08/2026 en vérifiant le bouton d'upload LoTW
(chantier upload LoTW automatique) : `/qsl/status` et 3 autres endpoints
échouaient systématiquement en `fetch()` navigateur (page LOGBOOK) alors
que `qsl.qsl_status({})` en Python direct ET `curl` sur le port 8098
répondaient correctement tous les deux — diagnostic confirmé par
`navigator.serviceWorker.getRegistrations()`, qui listait un SW `activated`
sur `http://127.0.0.1:8098/` provenant d'un chantier antérieur de la MÊME
session ayant utilisé ce même port. Un Service Worker survit à la fermeture
du serveur qui l'a enregistré — il reste actif tant que le PROFIL navigateur
n'est pas nettoyé, indépendamment de quel process écoute ensuite sur ce port.

**How to apply:** Avant de conclure à un bug depuis un test navigateur qui
échoue en réseau (pas une erreur JS, pas un mauvais rendu — un vrai
`Failed to fetch`) :
1. Vérifier `curl`/appel Python direct sur le MÊME endpoint — si ÇA marche,
   le serveur est innocent.
2. Vérifier `navigator.serviceWorker.getRegistrations()` dans la page.
3. Si un SW est présent, le désinscrire (`.unregister()`) + vider les caches
   (`caches.keys()`/`caches.delete()`) + `navigate` à nouveau vers la page
   AVANT de continuer le diagnostic.
Pour éviter la récurrence : préférer un port de test JAMAIS réutilisé dans
la session (numéro incrémenté à chaque nouveau chantier, déjà l'habitude
implicite de ce projet — 8095, 8096, 8097, 8098, 8099...) plutôt que de
recycler un port déjà servi, si le logiciel enregistre un Service Worker
(support hors-ligne du LOGBOOK).
