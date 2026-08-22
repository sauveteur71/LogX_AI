---
name: feedback-economie-tokens
description: "L'utilisateur paie ses crédits d'utilisation de sa poche (forfait Pro + solde de crédits prépayés) — travailler de façon économe en tokens"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: e5854853-072f-4b5f-895a-57c4ab0111d2
  modified: 2026-08-21T07:19:54.687Z
---

Adapter le style de travail pour réduire la consommation de tokens : réponses
plus courtes, éviter de reformuler ce qui est déjà visible dans les diffs ou
sorties d'outils, éviter de relire des fichiers volumineux déjà lus
récemment (préférer Grep ou des lectures ciblées avec offset/limit), limiter
les relances de suites de tests complètes quand un sous-ensemble ciblé suffit
à couvrir le changement, éviter de spawner des agents ou lancer des commandes
lourdes sans nécessité réelle.

**Why:** F4GLD a vu sa page de facturation Claude (forfait Pro + solde de
crédits d'utilisation prépayés à 77,83 €, rechargement automatique
désactivé) et a explicitement demandé de travailler en économisant les
tokens plutôt que d'attendre que le quota/solde s'épuise.

**How to apply:** Ne PAS relâcher la rigueur de vérification du projet
([[verifier-plutot-que-croire]] si cette fiche existe — témoin vert avant
mutation, contre-épreuve par mutation, sourçage strict des valeurs de
domaine) : l'économie porte sur la forme (longueur des réponses, citations
de code superflues, relectures redondantes, agents non nécessaires), jamais
sur le fond des contrôles qualité qui ont déjà coûté cher par le passé sur ce
projet.
