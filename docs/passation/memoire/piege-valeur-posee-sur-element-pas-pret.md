---
name: piege-valeur-posee-sur-element-pas-pret
description: JS — poser .value sur un <select> sans ses <option> échoue SANS ERREUR ; reconstruire innerHTML le remet sur sa 1re option (01/08/2026)
metadata: 
  node_type: memory
  type: feedback
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-08-01T10:59:40.036Z
---

F4GLD : « je choisis une radio, je sauvegarde, je vais au logbook, je reviens
et ma radio n'est plus sélectionnée ». **DEUX bugs distincts** derrière ce seul
symptôme, tous deux silencieux :

1. **Reconstruire les options efface la sélection.** `init()` restaurait la
   config (marque + modèle posés correctement), puis rappelait
   `updateCatModelOptions()` quelques lignes plus bas. `sel.innerHTML = …` remet
   un `<select>` sur sa PREMIÈRE option → le FT-991 redevenait un FT-891.
2. **Poser `.value` sur un `<select>` encore vide échoue sans lever.** La liste
   des ports arrive du serveur APRÈS la restauration ; l'affectation est
   ignorée, `sel.value` reste vide, et le port sauvegardé cédait la place au
   premier détecté. Idem pour le port de l'ampli.

**Why :** aucune exception, aucun message, aucun test unitaire ne le voit — le
DOM accepte silencieusement une valeur qui ne correspond à aucune option.

**How to apply :** toute fonction qui (re)remplit un `<select>` doit relire la
valeur voulue APRÈS remplissage — soit `sel.value` capturé avant, soit la
config mémorisée (`window._cfgRestauree`, posée par `applyFullConfigToForm`).
Vérifier en NAVIGATEUR par un aller-retour réel : enregistrer, recharger,
relire — c'est le seul test qui l'attrape. Motif appliqué aussi aux `<select>`
rotor/ampli de l'éditeur d'antennes.

Même famille que [[piege-faux-dom-stub-et-passes-paires]] (du JS qui ne tourne
jamais en test) et [[piege-verifier-sur-donnees-reelles]].
