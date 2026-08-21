# Storyboard vidéo — LogX AI

Script de tournage : une capture d'écran par page, narration à lire pendant
que vous filmez/cliquez. Chaque bloc = [ce que montre l'écran] + [ce que dit
la voix off]. Les durées sont indicatives (~11-13 min au total en suivant
tout, ~6-7 min si vous coupez les sections marquées « optionnel »).

Conseils tournage :
- Enregistrez en 1080p minimum, navigateur en plein écran, thème NUIT (plus
  photogénique en vidéo que le thème jour).
- Une page = un clip séparé, montage ensuite — évite de tout refaire si un
  seul passage rate.
- Zoomez/surlignez au clic (curseur agrandi ou un outil de mise en évidence)
  pour que les éléments cités dans la narration soient visibles à l'écran.
- Préparez le log AVANT de filmer : quelques QSO déjà saisis, un concours
  sélectionné, la config remplie — un écran vide ne vend rien.

---

## 0. Accroche (0:00 – 0:25)

**Écran** : montage rapide (3-4 plans d'1-2s) — LOGBOOK en plein trafic, la
carte IA qui tourne, un spot qui devient un QSO au clic, le score qui monte.
Pas de narration détaillée ici, juste le ton.

**Voix off** :
« Un logiciel pour le log de tous les jours. Un autre pour les concours. Un
site pour la propagation. Un tableur pour vos sorties portables. Et une
pile d'onglets ouverts pour le cluster, les cartes, les QSL. LogX AI réunit
tout ça dans une seule application — qui tourne chez vous, gratuitement,
sans compte, sans abonnement. »

**Titre à l'écran** : LogX AI — le compagnon de trafic nouvelle génération.

---

## 1. CONFIGURATION (1:00 environ)

**Écran** : `logx_configuration.html`. Montrer le hub de catégories (grille
de cartes), puis ouvrir 2-3 popups en cliquant.

**Narration** :
« Tout commence ici, dans CONFIG. Un hub de catégories plutôt qu'un long
formulaire : identité de la station, opérateurs, sélection du concours,
radio, propagation... chaque carte ouvre un popup dédié, avec de l'aide
contextuelle sur chaque champ, accessible via le petit point
d'interrogation à côté de chaque réglage. »

*(Ouvrir la popup 3 — Sélection concours)*
« 41 concours intégrés — REF, IARU, CQ WW, CQ WPX, ARRL DX, WAE... — plus
le calendrier mondial WA7BNM au complet, prêts en un clic. Et si un
concours n'y est pas ? L'IA lit le règlement, PDF ou page web, français ou
anglais, et propose bandes, dates, échange et barème — toujours soumis à
votre relecture avant d'être activé. »

*(Ouvrir la popup 6 — Radio CAT)*
« Le pilotage radio : CAT natif Icom, Yaesu, Kenwood, Elecraft, Xiegu par
câble série, TCI pour les SDR, rigctld pour le reste. Auto-détection au
branchement — plug-and-play, pas de configuration manuelle du port. »

---

## 2. LOGBOOK — la page centrale (2:30 environ)

**Écran** : `logx_logbook.html`. C'est la page qui mérite le plus de temps —
montrer chaque zone dans l'ordre : saisie (gauche), band map (milieu),
tableau du log (droite), bandeau du bas.

### 2a. Saisie QSO (colonne gauche)

« La saisie, pensée pour aller vite. Bande et mode en un clic — un bouton,
un menu, plutôt qu'une rangée de dix-sept boutons illisible. On tape
l'indicatif... »

*(Taper un indicatif dans le champ)*

« ...et la fiche du correspondant apparaît toute seule : pays, drapeau,
historique de vos contacts avec lui, alerte dorée si c'est un nouveau pays
à vie. Distance, cap et points se calculent dès que le locator est saisi.
Et le mode ESM — la touche Entrée enchaîne CQ, échange, puis
enregistrement du QSO, sans jamais lâcher le clavier. »

### 2b. Band map (colonne du milieu)

« Au centre, le band map : les spots du cluster, RBN et PSK Reporter placés
par fréquence. Un clic dessus règle la radio ET pré-remplit l'indicatif —
zéro ressaisie. Rouge : jamais travaillé. Le filtre permet de ne garder que
les nouveaux pays ou les stations LoTW. »

*(Cliquer l'icône panadapter dans le toolbar du band map)*

« Et depuis peu, un panadapter intégré : spectre et chute d'eau depuis
l'audio de réception, le scope natif des Icom récents, ou le flux IQ d'un
serveur TCI — sans matériel supplémentaire pour la version audio. »

### 2c. Tableau du log (colonne droite)

« À droite, le log en direct — recherche, filtres par bande, export en un
clic. Le bouton CARTE bascule sur une carte de tous vos QSO de la session. »

*(Optionnel : cliquer la loupe dans la barre de navigation, taper un mot-clé)*

« Et si vous ne savez plus où se trouve un réglage précis — un simple mot
tapé dans la recherche de la nav retrouve la bonne page et le bon passage,
sans devoir connaître le logiciel par cœur. »

### 2d. Bandeau du bas — keyer

*(Basculer en mode CW si possible, sinon montrer le keyer vocal en SSB)*

« En bas, le keyer — vocal en phonie, macros F1 à F8 en CW, avec un
décodeur CW intégré qui écoute l'audio de réception et affiche le morse
décodé. Le keyer vocal épelle indicatif et report à la volée en alphabet
OACI, et prend automatiquement l'émission le temps du message. »

### 2e. Barre du haut (score, propagation, alertes) — optionnel

« En permanence sous les yeux : le score en direct, le temps restant du
concours, les indices solaires, une alerte s'il y a de l'orage sur le
QTH — sans jamais quitter la page de saisie. »

---

## 3. CARTE IA (0:45)

**Écran** : `logx_carte.html`.

« La carte IA : tous les spots en direct, positionnés dans le monde, avec
le classement des meilleures cibles par valeur RÉELLE en points — pas une
estimation, le vrai barème du concours actif. Le copilote explique
pourquoi telle station vaut plus qu'une autre : nouveau pays, nouveau
multiplicateur, distance. »

---

## 4. PROPAGATION (0:45)

**Écran** : `logx_propagation.html`.

« La propagation sans quitter le logiciel : indices solaires, MUF réelle
mesurée par ionosondes, ouvertures par région du monde, sporadique-E,
balises NCDXF. Et un panneau EME complet — position de la Lune, fenêtre
commune avec le correspondant, Doppler et bilan de liaison, à partir de
deux simples locators. »

---

## 5. CHASSE (0:45)

**Écran** : `logx_chasse.html`.

« Pour les activateurs et chasseurs POTA, SOTA, WWFF, IOTA et châteaux
WCA : plus de 415 000 références en local, spots en direct, validation
automatique, et suivi de votre propre activation en temps réel — avec
détection park-to-park. »

---

## 6. Cartes / Départements (0:30) — optionnel

**Écran** : `logx_departements.html`.

« Pour la chasse aux départements français : la carte se colore au fur et
à mesure de votre progression, département par département. »

---

## 7. CALENDRIER (0:30)

**Écran** : `logx_calendrier.html`.

« Le calendrier mondial des concours — près de 360 épreuves pour l'année,
préparables en un clic depuis cette page directement. »

---

## 8. WEBSDR (0:30) — optionnel

**Écran** : `logx_websdr.html`.

« Un annuaire de récepteurs WebSDR dans le monde — pour s'écouter
soi-même avant un appel, ou écouter un DX depuis un récepteur proche de
lui. »

---

## 9. FOCUS BANDE (0:30) — optionnel

**Écran** : `logx_focus.html`.

« La page FOCUS BANDE : tout ce que le logiciel sait d'une bande sur un
seul écran — cluster filtré bande et mode, ouvertures, concours actifs,
et le classement de toutes les bandes avec la raison écrite en clair. »

---

## 10. École CW (0:30) — optionnel

**Écran** : `logx_cw.html`.

« Pour s'entraîner : dix minutes de CW généré à partir de VOTRE index —
votre log, vos archives — avec l'échange de votre prochain concours. Rien
ne part sur l'air, tout reste dans le casque. »

---

## 11. Multi-poste & écran mural (0:45)

**Écran** : idéalement deux fenêtres/appareils côte à côte, ou
`logx_wall.html` seul si un seul poste disponible.

« Plusieurs postes du shack — PC, tablette, téléphone — rejoignent le même
log en ouvrant une simple adresse WiFi, sans rien installer. Jusqu'à
quarante opérateurs en mode radioclub. Pour un radio-club avec ses propres
serveurs, la synchronisation peut aussi passer par une base MySQL partagée,
quasi temps réel. Et un écran mural à projeter : le flux des QSO en direct,
visible depuis la salle pendant que les copains regardent. »

---

## 12. Après le contact — QSL & diplômes (0:30)

**Écran** : popup Diplômes/QSL de CONFIG ou du LOGBOOK.

« Après le contact : diplômes à vie, Worked Matrix bande par mode, et cinq
services QSL synchronisés en un clic — eQSL, LoTW sans installer TQSL,
ClubLog, QRZCQ, HRDLog. »

---

## 13. Clôture / appel à l'action (0:35)

**Écran** : le site de présentation (sauveteur71.github.io/LogX_AI).

« Un seul fichier à télécharger, aucune installation, aucun compte. Vos
données restent chez vous. LogX AI est gratuit, sous licence libre GPLv3 —
le code reste ouvert et le restera. Vous venez de N1MM+, Win-Test, DXLog ou
Log4OM ? Votre historique s'importe en un clic, sans rien ressaisir. C'est
un radioamateur qui l'a développé, avec l'aide d'un copilote IA pour
l'assistance au code — mais c'est vous, sur le terrain, qui savez ce qui
manque encore. Alors testez-le, et aidez-moi à l'améliorer. »

**Texte à l'écran (fin)** :
- Téléchargement : lien GitHub / dernière release
- Wiki / guide utilisateur : lien
- Groupe d'entraide : groups.io/g/LogXAI
- Logiciel libre — GPLv3
- 73 !

---

## Récapitulatif des chiffres à afficher en incrustation (facultatif)

Repris de `docs/LogX_AI_Promotion.md` — à mettre à jour si les chiffres ont
changé depuis :

| | |
|---|---|
| Références embarquées | 415 000+ (SOTA, POTA, WWFF, IOTA, châteaux WCA) |
| Concours suivis avec scoring exact | 41 + calendrier mondial + analyse IA |
| Bandes | 17, de 1,8 MHz à 47 GHz |
| Langues de l'interface | 8 |
| Abonnement / compte / cloud obligatoire | 0 |
| Licence | GPLv3 — code source ouvert |

---

## Notes pour le montage

- Section 0 (accroche) et section 13 (clôture) sont les deux seules à ne
  PAS suivre le principe « une capture = une page » — prévoir un montage un
  peu plus travaillé pour ces deux-là (musique, texte à l'écran).
- Les sections marquées « optionnel » peuvent être coupées pour une version
  courte (~6-7 min) centrée sur CONFIG → LOGBOOK → CARTE IA → PROPAGATION →
  CHASSE → clôture.
- Si un élément cité dans la narration n'est pas visible à l'écran au bon
  moment (ex. aucun spot sur le band map au moment du tournage), soit
  préparer les données à l'avance (log avec quelques QSO, concours actif
  avec du trafic simulé), soit ajuster la narration sur ce qui est
  réellement visible plutôt que de décrire un écran vide.
