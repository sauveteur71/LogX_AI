# Audit `logx_configuration.html` + Trame de refonte du menu

**Date** : 21 juillet 2026
**Portée** : revue comportementale de `concours/logx_configuration.html` (5 dimensions, vérification adversariale à 3 votes) + benchmark UX (Ham Radio Deluxe, WinREF-THF, N1MM Logger+) + proposition d'architecture de remplacement.

---

## 1. Audit — 22 constats confirmés

Chaque constat a été vérifié indépendamment par 3 relecteurs adversariaux avant d'être retenu (22 confirmés / 22 soumis, 0 rejeté).

### 🔴 Critiques (2)

#### C1 — Perte de données silencieuse : Transceiver, Pays, URL et délai de soumission jamais restaurés
**Fichier** : `logx_configuration.html:3429` (et 2171/2181/3711/3829)

Le fichier contient **deux déclarations** de `loadSavedConfig()` (lignes 2171 et 3711) et **deux** de `loadFromServerConfig()` (lignes 2181 et 3829), dans le même `<script>`. En JavaScript, la seconde écrase silencieusement la première : c'est toujours la version de la ligne 3711/3829 qui s'exécute. Cette version active ne restaure **jamais** `radio`, `country`, `submit_url`, `submit_deadline` — alors que `saveConfig()` les envoie bien. Seule `applyConfigToForm()` (lignes 2093-2169) restaure ces 4 champs, mais elle n'est appelée que par la version *morte* de `loadSavedConfig` et par `loadProfile()`.

**Scénario concret** : remplir Transceiver/Pays/URL/délai → Sauvegarder (OK) → recharger la page (F5) → les 4 champs reviennent **vides** → si l'utilisateur re-sauvegarde à ce stade, les valeurs précédentes sont **écrasées définitivement par des chaînes vides**, en local et sur le serveur.

#### C2 — Mode Hamlib rigctld totalement inopérant
**Fichier** : `logx_configuration.html:3477`

`saveConfig()` envoie `rig_enabled: !!document.getElementById('rig_enabled')?.value`. **Aucun élément `id="rig_enabled"` n'existe dans la page** (remplacé depuis par `cat_enabled`/`cat_mode`) : l'appel retourne toujours `null` → `undefined` → `false`. Côté serveur, `logx_rig.py` et `logx_http.py` (`/rig/qsy`, `/rig/cw`, `/rig/stop`) conditionnent tout le mode rigctld sur ce booléen. Résultat : **quelle que soit la configuration affichée à l'écran**, le serveur répond systématiquement *« Radio CAT désactivée — active-la dans CONFIG »*.

**Effet de bord** : un utilisateur migré depuis une ancienne config (`rig_enabled: true` stocké avant l'ajout du natif/TCI) verra ce `true` écrasé par `false` dès le premier ré-enregistrement — une installation qui fonctionnait casse silencieusement.

---

### 🟠 Hautes (6)

#### H1 — Chargement de profil incomplet : ~50 réglages ne suivent pas
**Fichier** : `logx_configuration.html:2588`

`saveProfile()` capture la config complète (~90 champs). `loadProfile()` → `applyConfigToForm()` n'en réapplique qu'un sous-ensemble restreint (~40 champs). Ne sont **jamais** restaurés au chargement d'un profil : identifiants QRZ/eQSL/LoTW/ClubLog/QRZCQ/HRDLog, pilotage radio/ampli/rotor, WSJT-X, réseau ADIF, keyer vocal, scoreboard, backup, cloud sync, alertes personnalisées.

**Scénario** : Profil A = CAT natif IC-7300/COM3 + QRZ='F4GLD'. Profil B = rigctld + QRZ='F1XXX'. Charger le profil A depuis B : indicatif/locator basculent bien, mais **marque/port radio et identifiant QRZ restent ceux du profil B** — mélange incohérent invisible pour l'utilisateur.

#### H2 — Aucune validation avant de changer d'étape, sauvegarder ou lancer
**Fichier** : `logx_configuration.html:3013`

`goStep(n)` ne vérifie jamais que l'étape courante est complète. Les onglets d'étape permettent de sauter directement à RÉSUMÉ sans être passé par les précédentes. `saveConfig()`/`launchApp()` ne contrôlent aucun champ requis (indicatif, locator, concours). Le seul `confirm()` du fichier concerne la suppression de profil — ce garde-fou existe ailleurs dans le code, il est simplement absent de tout le parcours de l'assistant.

**Scénario** : ouvrir la page sans config → cliquer directement RÉSUMÉ → LOGGER : le logbook s'ouvre avec indicatif et locator vides, sans aucun avertissement.

#### H3 — Changer de concours écrase silencieusement les personnalisations
**Fichier** : `logx_configuration.html:2701`

`selectContest(id)` réinitialise systématiquement toutes les cases bande/mode puis ne réactive que celles du nouveau concours, et écrase les dates — sans vérifier si l'utilisateur avait déjà personnalisé ces champs. Le garde-fou existant (`_filtersAppliedFor`) protège seulement contre une ré-application au changement d'étape, pas contre un second clic sur une carte.

**Scénario** : personnaliser bandes/dates à l'étape 3 → revenir à l'étape 2 → recliquer une carte (même celle déjà sélectionnée) → toutes les personnalisations sont perdues sans avertissement.

#### H4 — Mode Expédition/Activation inaccessible en mode débutant
**Fichier** : `logx_configuration.html:3586`

Les champs `expedition_mode`, `activation_program`, `my_activation_ref`, `clublog_live` vivent dans le panneau de l'étape 4, masqué en mode UI « débutant » (le défaut pour tout nouvel utilisateur). Le sélecteur MODE D'UTILISATION propose pourtant toujours « EXPÉDITION/ACTIVATION » et son aide dit littéralement d'aller « dans la section ci-dessous » — section **impossible à atteindre** sans deviner qu'il faut d'abord basculer en mode EXPERT.

#### H5 — Locator Maidenhead : aucune validation de format
**Fichier** : `logx_configuration.html` (champ `#locator`, pas de ligne unique)

Seuls `maxlength="6"` et une mise en majuscule sont appliqués. La regex de validité existe déjà dans le fichier (`/^[A-R]{2}[0-9]{2}([A-X]{2})?$/`, utilisée par `locatorToLatLon()`) mais n'est jamais utilisée pour valider la saisie. Un locator syntaxiquement invalide (`"999999"`, `"ZZ99ZZ"`) ou trop court (`"JN"`) est accepté et sauvegardé sans avertissement, alors que le bandeau affiche quand même « coordonnées calculées automatiquement ».

#### H6 — Test de connexion rigctld : aucune prise en charge, ni client ni serveur
**Fichier** : `logx_configuration.html:2406`

`testCatConnection()` ne distingue que `tci` d'un `else` qui traite `native` ET `rigctld` de façon identique (champs marque/modèle/port série). En mode rigctld, ces champs n'ont pas de sens (seuls `rig_host`/`rig_port` comptent, jamais lus). Confirmé côté serveur : `/rig/connect_test` n'a **aucune branche** testant une connexion rigctld.

**Scénario** : mode rigctld + port série jamais configuré → message trompeur « Choisis un port série d'abord ». Ou : port série natif déjà configuré avant de basculer en rigctld → le test interroge silencieusement ce port série au lieu du serveur rigctld visé, pouvant renvoyer un faux succès.

---

### 🟡 Moyennes (9)

| # | Titre | Ligne | Résumé |
|---|---|---|---|
| M1 | Extraction IA sans protection anti-concurrence | 3951 | Pendant les 30-90s d'analyse, rien n'empêche de changer de concours ou de naviguer ; la validation finale de la proposition IA écrase silencieusement une sélection manuelle faite entre-temps. |
| M2 | Dates concours non bornées l'une par rapport à l'autre | — | Rien n'empêche une date de fin antérieure à la date de début après modification manuelle. |
| M3 | Bornes numériques HTML purement cosmétiques | — | `min`/`max` posés en HTML jamais vérifiés en JS ; `altitude:"-500"` ou `alert_volume:-10` sont acceptés et persistés tels quels. |
| M4 | Sauvegarde possible avec zéro bande / zéro mode | — | Aucun contrôle qu'au moins une case reste active ; on peut lancer le logbook avec une configuration inexploitable. |
| M5 | Aucun grisage des champs dépendants d'un toggle Désactivé | 2280 | Ampli/rotor/Cloud Sync : les champs restent pleinement éditables même toggle sur Désactivé — aucune perte de valeur, mais aucun indice visuel. |
| M6 | « Synchroniser maintenant » utilise l'ancienne config serveur | 2828 | Contrairement aux boutons de test CAT/ampli, `cloudsyncNow()` n'envoie pas les valeurs actuellement affichées — juste la dernière config sauvegardée. |
| M7 | Distance/azimut : arrondi différent client/serveur | 3140 | Même formule (haversine, R=6371km) mais `Math.round()` (JS) vs `int()` = troncature (Python) — jusqu'à 1km/1° d'écart selon les cas. |
| M8 | Locator 4 caractères : accepté côté carte, rejeté côté serveur (certains appelants) | 3072 | `locator_to_latlon()` Python rejette tout locator <6 caractères ; plusieurs appelants compensent (`+'MM'`), d'autres non (`logx_psk.py`), cassant silencieusement le calcul pour des rapports PSK Reporter à 4 caractères. |
| M9 | Carte Leaflet : échec silencieux si les tuiles OSM sont bloquées | 3105 | L'échec du script JS est signalé, mais un blocage réseau spécifique aux tuiles (hôte différent du CDN) laisse une carte grise sans aucun message. |

---

### ⚪ Basses (5)

- **B1** — `rig_enabled` référence un id DOM mort (vestige du renommage vers `cat_enabled`), même cause que C2.
- **B2** — Club Log Live Stream activable sans qu'aucun identifiant ClubLog ne soit renseigné (juste un texte d'avertissement statique).
- **B3** — Mode TCI : contrairement au mode natif, aucune vérification de champ vide avant test (repli silencieux sur `127.0.0.1`, pas de message explicite).
- **B4** — `CONFIG_HELP` incomplet : 8 champs légitimes (Transceiver, Pays, Indicatif responsable, Code postal, 4 champs Antennes) n'ont jamais de bouton d'aide « ? », contrairement à leurs voisins immédiats du même formulaire.
- **B5** — Course d'initialisation : cliquer l'assistant IA immédiatement après un rechargement de page (avant la résolution du `fetch('/config')` asynchrone) peut donner « pas de clé API configurée » alors qu'une clé existe bien côté serveur.

---

## 2. Benchmark UX — ce que font les logiciels existants

| Logiciel | Pattern observé | À retenir |
|---|---|---|
| **Ham Radio Deluxe** | Arbre de catégories à gauche + panneau de détail à droite, dans une seule fenêtre modale | Hiérarchie visible d'emblée, navigation instantanée sans ouvrir/fermer de fenêtres |
| **WinREF-THF** | Deux commandes séparées : *Configurer le concours* / *Configurer le programme*. La fenêtre concours est dense mais groupée en blocs titrés (Identification station / opérateur / Catégorie / Dates / Description par bande / Soapbox) | Séparer clairement « ce qui change à chaque concours » de « les préférences durables » ; grouper visuellement par blocs titrés quand une section a beaucoup de champs |
| **N1MM Logger+** | Menu Config = liste plate d'~25 entrées mélangeant réglages et cases à cocher, sans hiérarchie (réputé difficile à apprendre) — **mais** « Change Your Station Data... » ouvre une popup dédiée simple (Call/Grid/Zone/Power/Antenna...) | Contre-exemple à éviter pour la structure globale ; bon exemple pour une popup ciblée par thème |

---

## 3. Trame du nouveau menu

### Principes directeurs

1. **Hub de catégories cliquables**, pas d'assistant linéaire forcé — chaque catégorie est une carte avec un badge d'état (✅ configuré / ⚠️ à compléter / ○ non utilisé), consultable dans n'importe quel ordre.
2. **Une popup par catégorie**, contenu groupé en blocs titrés si la catégorie a beaucoup de champs (modèle WinREF).
3. **Validation à la fermeture de la popup**, pas seulement à la sauvegarde globale — un locator invalide, des dates incohérentes ou un champ numérique hors bornes sont signalés immédiatement, dans le contexte où l'erreur a été commise (règle H5, M2, M3, M4).
4. **Un seul état central** (`state.cfg`) lu/écrit par toutes les popups — plus de fonctions dupliquées, plus de divergence entre ce que sauvegarde une popup et ce qu'une autre restaure (règle C1, H1).
5. **Grisage systématique** des champs dépendants dès qu'un toggle est sur Désactivé (règle M5).
6. **Ordre des catégories = ordre d'usage réel**, du plus stable (identité station) au plus ponctuel (récapitulatif).

### Architecture proposée

```
┌─────────────────────────────────────────────────────────┐
│  LogX AI — Configuration                    [Résumé ▸]  │
├─────────────────────────────────────────────────────────┤
│  MA STATION                                              │
│  ┌──────────────┐  ┌──────────────┐                     │
│  │ 1. Identité   │  │ 2. Opérateurs│                     │
│  │    ✅          │  │    ○ (1 seul)│                     │
│  └──────────────┘  └──────────────┘                     │
│                                                           │
│  CONCOURS                                                │
│  ┌──────────────┐  ┌──────────────┐                     │
│  │ 3. Sélection  │  │ 4. Dates &   │                     │
│  │    ✅ REF THF │  │    bandes/mo │
│  │              │  │    ⚠️         │                     │
│  └──────────────┘  └──────────────┘                     │
│                                                           │
│  MATÉRIEL                                                │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐    │
│  │ 5. Radio (CAT)│ │ 6. Amplificat.│ │ 7. Rotor    │    │
│  │    ⚠️ incomplet│ │    ○          │ │    ○        │    │
│  └──────────────┘ └──────────────┘ └──────────────┘    │
│                                                           │
│  RÉSEAU & SAUVEGARDE                                     │
│  ┌──────────────┐  ┌──────────────┐                     │
│  │ 8. Multi-poste│  │ 9. Sauvegarde│                     │
│  │    & Cloud    │  │    auto      │                     │
│  └──────────────┘  └──────────────┘                     │
│                                                           │
│  PROPAGATION & ALERTES                                   │
│  ┌──────────────┐  ┌──────────────┐                     │
│  │10. Sources    │  │11. Alertes   │                     │
│  │   (cluster...)│  │   perso      │                     │
│  └──────────────┘  └──────────────┘                     │
│                                                           │
│  APRÈS LE CONCOURS                                       │
│  ┌──────────────┐  ┌──────────────┐                     │
│  │12. QSL &      │  │13. Scoreboard│                     │
│  │   diplômes    │  │   & soumission                     │
│  └──────────────┘  └──────────────┘                     │
│                                                           │
│  SPÉCIAL                                                 │
│  ┌──────────────┐  ┌──────────────┐                     │
│  │14. Expédition │  │15. Assistant │                     │
│  │   / activation│  │   IA         │                     │
│  └──────────────┘  └──────────────┘                     │
│                                                           │
│              [ 🚀 TOUT EST BON — LOGGER ]                │
└─────────────────────────────────────────────────────────┘
```

### Détail de chaque popup

#### 1. Identité de ma station
Indicatif, indicatif concours (si différent), locator Maidenhead (avec bouton carte + validation regex immédiate), ville, code postal, pays, altitude, puissance, antennes (HF/144/432/SHF).

#### 2. Opérateurs
Liste des opérateurs multi-poste (nom/indicatif/rôle), opérateur responsable (nom, adresse, téléphone, email — champs actuellement dispersés en étape 1).

#### 3. Sélection du concours
Grille de cartes + recherche instantanée + bouton « Analyser un règlement » (IA). **Si des personnalisations existent déjà** (bandes/dates modifiées à la main), un changement de concours demande confirmation au lieu d'écraser silencieusement (règle H3).

#### 4. Dates & bandes/modes
Dates début/fin (avec contrôle fin > début, règle M2), bandes actives, modes actifs (avec contrôle qu'au moins une case de chaque reste cochée, règle M4), filtre de préfixe.

#### 5. Radio (CAT)
Sélecteur natif/TCI/rigctld avec **les 3 sous-blocs de champs qui s'affichent UNIQUEMENT pour le mode choisi** (pas les 3 en même temps), test de connexion qui route vraiment vers rigctld quand ce mode est actif (règle C2, H6), toggle Activé/Désactivé qui grise réellement la section (règle M5).

#### 6. Amplificateur / 7. Rotor
Même traitement : toggle qui grise, test de connexion cohérent avec le mode choisi.

#### 8. Multi-poste & Cloud Sync
Mode Full/Push/Off, dossier partagé, intervalle. Bouton « Synchroniser maintenant » qui utilise les valeurs **actuellement affichées**, pas l'ancienne config serveur (règle M6) — ou qui sauvegarde automatiquement avant de synchroniser.

#### 9. Sauvegarde automatique
Dossier, intervalle.

#### 10. Sources de propagation
Toggles individuels cluster/RBN/PSK Reporter/balises (déjà existants, à regrouper visuellement ici plutôt que dispersés).

#### 11. Alertes personnalisées
Distance DX, fiabilité spotter, filtre de préfixe, règles d'alerte.

#### 12. QSL & diplômes
Identifiants QRZ/eQSL/LoTW/ClubLog/QRZCQ/HRDLog, **avec le toggle "Live Stream" grisé tant que les identifiants correspondants ne sont pas remplis** (règle B2).

#### 13. Scoreboard & soumission
URL de soumission du log, délai de soumission, réglages scoreboard en direct.

#### 14. Expédition / Activation
**Accessible sans condition de mode débutant/expert** (règle H4) — dès que « EXPÉDITION/ACTIVATION » est choisi en mode d'utilisation, cette popup devient directement accessible depuis le hub, sans dépendre d'un onglet masqué.

#### 15. Assistant IA
Fournisseur, modèle, clé API — la clé API se recharge de façon synchrone avant que le bouton assistant flottant ne devienne cliquable (règle B5).

### Ce que cette architecture règle par construction

- **C1, H1** : plus de duplication de fonctions save/load possible — un seul état central, une seule fonction pour le lire/l'écrire, testée une fois pour toutes les popups.
- **H2** : chaque popup valide ses propres champs à la fermeture ; le hub peut refuser le lancement si des catégories obligatoires (Identité, Concours) restent en ⚠️.
- **H3** : la popup Concours ne réinitialise plus les bandes/dates si l'utilisateur avait déjà ouvert la popup 4 et personnalisé — demande confirmation explicite.
- **H4** : plus de section masquée par le mode débutant/expert — chaque popup est indépendamment accessible.
- **M5** : le grisage devient une règle générique appliquée à toutes les popups avec toggle (un seul mécanisme, pas 4 implémentations partielles).

---

*Document de travail — à faire évoluer au fil de l'implémentation. Voir aussi `docs/LogX_AI_PRD.md` (EV-7, refactor frontend) pour le contexte plus large.*
