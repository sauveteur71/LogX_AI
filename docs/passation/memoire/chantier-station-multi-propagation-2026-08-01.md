---
name: chantier-station-multi-propagation-2026-08-01
description: "Station à plusieurs antennes/rotors/amplis + propagation bornée par le BAS (couche D) + FT8 JTDX/MSHV (01/08/2026, 192d038)"
metadata: 
  node_type: memory
  type: project
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-08-01T14:04:41.250Z
---

Quatre demandes de F4GLD dans la même session. Fusionné en `192d038`, CI verte,
suite passée de 3223 à **3269 tests**.

**1. « Le 160 m ne peut pas être ouvert à cette heure-ci » — il avait raison.**
La page testait `fréquence <= MUF` : la MUF est la borne HAUTE, il n'y avait
AUCUNE borne basse. À 09h41 UTC un 1er août, soleil à 52,6° sur JN15WD, tout ce
qui est sous 23,7 MHz passait pour ouvert. **Cause profonde** : `_band_score`
(logx_paths.py) faisait la MOYENNE du jour/nuit entre les deux bouts, donc une
extrémité nocturne rachetait une extrémité en plein midi (« 160 m ouvert vers
le Japon »). L'absorption de la couche D **ne se moyenne pas**, elle se subit à
CHAQUE bout → c'est le bout le plus éclairé qui commande. Nouvel état
« régional » pour 160/80/40 m de jour. Verdict calculé en Python
(`etat_bandes_hf`), plus dans le JS de la page.

**2. « La propagation est donnée pour N0NBH » — non, mais le CRÉDIT l'était.**
Vérifié : locator JN15WD bien utilisé ; Dourbes est RÉELLEMENT l'ionosonde
fraîche la plus proche (554 km, mesuré contre les 25 fraîches du monde). Seules
les lignes ☀️/🌙 du bas viennent de hamqsl — le panneau les étiquette désormais
« tendance mondiale N0NBH (pas ta position) ».

**3. Réglage CAT perdu** → voir [[piege-valeur-posee-sur-element-pas-pret]].

**4. Plusieurs antennes / rotors / amplis** (`logx_station.py`). Modèle CHOISI
PAR L'OPÉRATEUR via AskUserQuestion : une liste d'antennes, chacune désignant
SON rotor et SON ampli ; un clic sur un spot ne fait tourner QUE le rotor de la
bande active (multi-opérateur). `/station[?bande=]`, `/rotor/point` accepte
`bande` ou `rotor_id`, décalage mécanique du pylône appliqué à UN SEUL endroit.
**Migration** : les 4 champs texte deviennent des antennes, l'ancien rotor
unique est rattaché à toutes (sinon perte du pointage) ; une config déjà migrée
n'est JAMAIS réécrasée par les vieux champs.

**5. FT8 JTDX/MSHV : rien à faire côté protocole.** Prouvé en rejouant des
datagrammes `JTDX`, `MSHV`, `MSHV_Ver2.71` — tous acceptés, le parseur ne
filtre que sur le nombre magique. Le manque était que l'écran affichait
« WSJT-X » quoi qu'il arrive. **Reste à vérifier avec le vrai logiciel** :
l'identifiant exact de MSHV et s'il honore les messages « Reply » du
Wait-and-Pounce. lz2hv.org a un certificat invalide (ne couvre pas son domaine).

**3e occurrence du piège `nan`** dans ce dépôt (après les positions de suivi
satellite et les fréquences WebSDR) : `float('nan')` ne lève pas, `nan % 360`
vaut nan, l'azimut serait parti tel quel au rotor. Attrapé par mon propre test.

**Reste à faire** : si deux antennes couvrent la même bande, la première de la
liste sert par défaut — il faudrait un sélecteur d'antenne dans le logbook.

---

**SUITE — revue adversariale (fusion `9617388`, CI verte, 3269 → 3287 tests).**
Après « verification de l'ensemble avant de pousser », une revue qui EXÉCUTE ses
scénarios a trouvé 8 défauts. Le motif dominant est humiliant : **j'avais
reproduit, DANS MON PROPRE travail rotor du jour, exactement le piège que je
corrigeais toute la journée ailleurs** — un backend correct et testé sans AUCUN
appelant côté interface (voir [[piege-verifier-sur-donnees-reelles]]). Le
nouvel éditeur de parc écrivait la liste `rotors`, mais `logx_rotor.rotor_settings`
ne lisait QUE les vieux champs `rotor_host/enabled` → une station configurée par
le seul nouvel éditeur avait : bouton « pointer » masqué (`/rotor/state`
enabled:false), `/rotor/point` retombé sur le repli legacy (décalage mécanique
JAMAIS appliqué), et suivi satellite impossible. **3 symptômes, une racine.**
Correctif : résolution UNIQUE `logx_station.rotor_defaut(cfg, prefer_bandes)`
partagée par state/point/sat. Les appelants UI transmettent la BANDE (sans elle,
tout retombe sur le rotor par défaut et le multi-pylône reste injoignable).

Autres défauts de la même revue : gate grey-line `my_el > 0` écrasait en
'regional' la fenêtre du lever (meilleur DX 160/80) — porté à `> 6°` (le verdict
contredisait le bonus grey-line `abs(el)<6` du score) ; `'rotor'+(length+1)`
reforgeait un id déjà pris après suppression → antenne reliée au mauvais pylône
en silence (`_idLibre` prend le 1er libre) ; `derive_horloge` itérait le deque DT
sans verrou → « deque mutated during iteration » sous FT8 chargé (`_dt_lock`) ;
et **le 6 m (50 MHz) manquait de `VHF_UHF_SHF_BANDS`/`BANDES_THF`** → tout log
6 m donnait « Aucun QSO VHF/UHF à exporter » et des stats HF (bug préexistant).

**LEÇON : corriger un piège ailleurs ne m'immunise pas contre lui ici même.**
Aucun test unitaire ne tombait — chaque couche était cohérente avec elle-même ;
seule une revue qui EXÉCUTE un aller-retour réel (station parc-only → bouton →
tournage du bon pylône) l'a exposé. Non-régression : `test_revue_jour_correctifs.py`.
