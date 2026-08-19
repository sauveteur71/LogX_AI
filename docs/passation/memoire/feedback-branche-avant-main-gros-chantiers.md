---
name: feedback-branche-avant-main-gros-chantiers
description: "Les gros chantiers passent par une branche + CI verte avant de rejoindre main, jamais un push direct"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-07-26T05:51:29.525Z
---

Décidé avec l'utilisateur le 26/07/2026 : **tout gros chantier passe désormais par une branche dédiée, poussée séparément, dont la CI doit être VERTE avant la fusion dans `main`.** Les corrections d'une ligne peuvent continuer d'aller directement sur `main`.

**Why :** le 25 et le 26/07/2026, deux pushes directs sur `main` ont mis la CI au rouge (chemin `Z:\...` non portable dans les tests Cloud Sync, puis sémantiques de sockets Windows supposées universelles dans les tests d'instance unique). Dans les deux cas le logiciel était correct et seuls les tests étaient en cause — mais entre le push et le correctif, `main` était cassé. Or `main` est la branche que les bêta-testeurs téléchargent et celle sur laquelle se base une release : si un exécutable avait été construit pendant ce laps de temps, il partait avec une CI rouge. Rien n'a cassé par chance, pas par méthode.

Cause racine de ces deux incidents : je valide sur la machine Windows de l'utilisateur et j'annonce « tout est vert », alors que **la CI est la seule autorité pour Linux et macOS** — plateformes pour lesquelles des exécutables sont pourtant distribués.

**How to apply :**
- Gros chantier → `git checkout -b <nom-parlant>`, commits, `git push origin <branche>`, attendre la CI sur CETTE branche, puis fusionner dans `main`. Une PR (`gh pr create`) est un plus pour garder une trace lisible du pourquoi, mais l'essentiel est la CI verte AVANT la fusion.
- Ne jamais annoncer « c'est bon » sur la foi de la seule suite locale : attendre le verdict de la CI. Voir [[contrainte-expedition-15-jours-continu]] pour l'autre écueil de méthode (extrapolation depuis un seul point de mesure).
- Écrire les tests avec les DEUX plateformes en tête dès le départ (chemins de fichiers, sémantiques socket), plutôt que de réparer après coup.

Option non retenue pour l'instant, à proposer si les incidents se répètent : activer la protection de branche sur `main` côté GitHub (interdit le push direct). Écarté pour ne pas bloquer les correctifs rapides d'un développeur solo.
