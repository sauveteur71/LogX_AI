# LogX AI — Ressources techniques fiables pour faire avancer le projet

**Date :** 21 juillet 2026
**Cible :** développement du logiciel de logbook / contest radioamateur LogX AI (F6KQJ)
**Méthode :** ressources sélectionnées et vérifiées, classées par chantier réel du projet (callbook cascade, ADIF/EDI, clusters/RBN, CAT/Hamlib, propagation, interop réseau, cloud sync, activations).

> Chaque section indique **la source de référence (spec ou dépôt)**, **ce que ça t'apporte concrètement**, et **le point d'accroche dans ton code** (`logx_*.py`) quand il existe.

---

## 1. Formats & standards — le socle non négociable

### 1.1 ADIF (Amateur Data Interchange Format) — version courante 3.1.7
C'est LA référence pour l'import/export et l'interopérabilité. La 3.1.7 est datée du 22 mars 2026.

- **Spec 3.1.7 (lecture) :** https://www.adif.org/317/ADIF_317.htm
- **Spec annotée (voir ce qui a changé) :** https://www.adif.org/317/ADIF_317_annotated.htm
- **Ressources machine-readable (LE truc à récupérer) :** https://adif.org.uk/317/ADIF_317_resources.htm
  → un ZIP fournit **tous les champs, types de données et énumérations** en **XML / TSV / CSV / JSON / XLSX / ODS**. Les fichiers `enumerations_*.tsv` et `fields.tsv` te permettent de **générer automatiquement** ta table de champs et tes validations au lieu de les coder à la main. Recommandation officielle : le **TSV** est le plus simple à parser (split sur tabulation).
- **Accroche projet :** `logx_import.py`, `logx_export.py`, `logx_validate.py`, `logx_validator.py`. Faire pointer ta validation sur les énumérations ADIF 3.1.7 officielles te garantit un import « je viens d'un autre logiciel » sans surprise.

### 1.2 Cabrillo — format de soumission contest (HF)
Standard maintenu par la **WWROF** (World Wide Radio Operators Foundation).

- **Spec Cabrillo v3 (entête + notes) :** https://wwrof.org/cabrillo/ et https://wwrof.org/cabrillo/cabrillo-specification-notes/
- **Entête détaillé :** https://wwrof.org/cabrillo/cabrillo-v3-header/
- **Noms Cabrillo (identifiants de concours normalisés) :** https://www.contestcalendar.com/cabnames.php
- **Limites connues du format (à anticiper) :** https://geek.jasonhancock.com/2020/11/23/shortcomings-of-cabrillo-format-ham-radio-contest-logs/
- **Accroche projet :** tu exportes déjà du Cabrillo (mentionné dans le plan de bataille). La page « cabnames » sert à mapper proprement l'ID interne d'un concours vers le `CONTEST:` attendu par le robot de dépouillement.

### 1.3 EDI / REG1TEST — format de soumission contest THF (VHF/UHF/SHF, IARU R1 / REF)
C'est ton format critique côté français/THF, celui des concours REF et IARU R1.

- **Description du format EDI (REG1TEST) par l'UKSMG (claire, champ par champ) :** https://uksmg.org/contest/edi-file-format.php
- **Règles IARU R1 VHF & up (PDF officiel, définit ce que le log doit contenir) :** https://www.iaru-r1.org/wp-content/uploads/2024/02/Rules-IARU-R1-VHF-up-Contests.pdf
- **Génération EDI expliquée (Win-Test Wiki, bon pour comprendre les cas limites) :** https://docs.win-test.com/wiki/Creating
- **Accroche projet :** tu as des champs EDI dynamiques (`ediClub`, `ediRName`…). La spec UKSMG te sert de checklist de conformité pour l'entête `[REG1TEST;1]` et les lignes QSO.

### 1.4 Fichiers pays / DXCC (cty.dat)
Indispensable pour résoudre indicatif → entité DXCC / zone CQ / zone ITU (multiplicateurs contest).

- **Amateur Radio Country Files (AD1C, la référence, mise à jour régulière) :** https://www.country-files.com/
- **Club Log — requête DXCC (API/prefix) :** https://clublog.freshdesk.com/support/solutions/articles/54904-how-to-query-club-log-for-dxcc-info
- **Discussion API/CSV des entités DXCC Club Log :** https://groups.google.com/g/clublog/c/9SjQ9G_huko
- **Accroche projet :** tu as déjà `cty.dat` + `logx_dxcc.py` + `logx_countries.py`. Penser à un **rafraîchissement automatique** du cty.dat depuis country-files.com (comme tu rafraîchis les règlements).

---

## 2. Callbook multi-source (chantier §3.1 de ta roadmap : cascade + repli gratuit)

Ton objectif : QRZ en primaire, mais **repli gratuit** quand pas d'abonnement. Voici les sources fiables, gratuites d'abord.

- **HamQTH — page développeurs (session XML, gratuit) :** https://www.hamqth.com/developers.php
  - Lookup XML : `https://www.hamqth.com/xml.php` (on demande d'abord un **session ID valable 1 h**, puis on requête l'indicatif).
  - DXCC sans authentification : `https://www.hamqth.com/dxcc_json.php?callsign=XX` (JSON) ou `dxcc.php` (XML).
  - **Bonus déjà utile pour d'autres modules :** spots cluster CSV `dxc_csv.php`, données RBN `rbn_data.php` (JSON/XML), upload log ADIF `prg_log_upload.php`, QSO temps réel `qso_realtime.php`.
- **HamDB — totalement gratuit, sans clé :** https://hamdb.org/api → `https://api.hamdb.org/{callsign}/json/{appname}` (US surtout).
- **Callook.info — US, gratuit, sans clé :** https://callook.info/api_reference.php (JSON, données FCC).
- **QRZ XML (payant, primaire) :** rappel — session key puis lookup ; à garder comme source primaire configurable.
- **Bibliothèque Python multi-callbook (à étudier / réutiliser la logique) :** https://github.com/miaowware/callsignlookuptools (QRZ, HamQTH, callook, HamDB en une interface) — PyPI : https://pypi.org/project/callsignlookuptools/
- **Accroche projet :** `logx_callbook.py` / `logx_qrz.py` / `logx_callhistory.py`. La lib `callsignlookuptools` est un excellent modèle d'architecture « cascade + merge » que tu peux transposer sans copier (licences à vérifier).

---

## 3. Spots temps réel : clusters, RBN, PSK Reporter, activations

### 3.1 DX Cluster (telnet DX Spider) et répertoire de serveurs
- **Répertoire officiel des clusters REF :** https://web.r-e-f.org/clusters/
- **Cluster F5LEN (VHF/THF France, ta source déjà intégrée) :** https://f5len.org/blog/tag/dx-cluster/
- **Accroche projet :** `logx_clusters.py`. Pour le chantier « répertoire éditable + toggles par source », la liste REF ci-dessus est une bonne base de serveurs telnet publics à proposer par défaut.

### 3.2 Reverse Beacon Network (RBN)
- **RBN — site principal + flux :** https://www.reversebeacon.net/main.php
- **Flux FT8 séparé (nouveauté à supporter) :** https://www.reversebeacon.net/pages/FT8+Announcement+40
- **RBN via HamQTH (JSON/XML tout prêt, pas de telnet à gérer) :** `https://www.hamqth.com/rbn_data.php`
- **Guide technique CW Skimmer + RBN (N6TV, PDF) :** https://www.kkn.net/~n6tv/N6TV_Dayton_2015_CW_Skimmer.pdf
- **Accroche projet :** `logx_rbn.py`. Le repli JSON HamQTH évite de maintenir une connexion telnet RBN fragile.

### 3.3 PSK Reporter (spots de réception numériques mondiaux)
- **Fil de référence sur l'API / accès aux données :** https://stationproject.blog/2013/02/08/reverse-beacon-networks-psk-reporter-and-wspr/
- Query XML/JSON via `retrieve.pskreporter.info` (paramètres `senderCallsign`, `flowStartSeconds`…). Attention aux **limites de fréquence** de requête (ne pas spammer, ~5 min entre requêtes).
- **Accroche projet :** `logx_psk.py`.

### 3.4 POTA (Parks On The Air) — API réelle
Base : `https://api.pota.app` (community-documented, utilisée par de nombreux outils).

- Spots activateurs : `https://api.pota.app/spot/activator`
- Commentaires d'un spot : `https://api.pota.app/spot/comments/{activator}/{park}`
- Détail parc : `https://api.pota.app/park/{ref}`
- Parcs d'une zone : `https://api.pota.app/location/parks/{location}`
- Poster un spot : `POST https://api.pota.app/spot/`
- **Doc POTA (générale) :** https://docs.pota.app/
- **Code de référence propre à étudier (hunterlog) :** https://github.com/cwhelchel/hunterlog

### 3.5 SOTA (Summits On The Air) & ParksNPeaks
- **API SOTA (v2, discussions officielles avec endpoints) :** https://reflector.sota.org.uk/t/sotadata-api/23731 et https://reflector.sota.org.uk/t/api-for-chased-summits/36548
- **ParksNPeaks (agrégateur multi-programmes AU, API JSON) :** https://parksnpeaks.org/api/
- **Accroche projet :** `logx_activation.py`. Pour étendre à ARLHS (phares) / WCA (châteaux) comme prévu, ParksNPeaks montre un modèle d'API multi-programmes.

---

## 4. Contrôle radio (CAT) & interop réseau — protocoles à supporter

### 4.1 Hamlib / rigctld (tu l'utilises déjà — approche universelle, bon choix)
- **Contrôle réseau (protocole rigctld TCP) :** https://github.com/Hamlib/Hamlib/wiki/Network-Device-Control
- **Manuel rigctld :** https://hamlib.sourceforge.net/html/rigctl.1.html
- **Accroche projet :** `logx_rig.py`, `logx_cat.py`, `logx_rotor.py`, `logx_amp.py`. Rester sur Hamlib générique est la bonne décision (couvre ~tout le parc sans coder 10 pilotes propriétaires).

### 4.2 TCI (Transceiver Control Interface — Expert Electronics / SunSDR)
Le protocole moderne WebSocket qui monte, surtout côté SDR ; intéressant à supporter en plus de CAT.

- **Logiciels compatibles TCI (point d'entrée officiel Expert) :** https://eesdr.com/en/software-en/software-en
- **Accroche projet :** `logx_tci.py` existe déjà — tu es en avance ici. TCI transporte aussi l'audio/spectre, utile pour ton bandscope.

### 4.3 WSJT-X — protocole UDP (numérique FT8/FT4…)
- **Définition officielle des messages (fichier source C++) :** https://github.com/roelandjansen/wsjt-x/blob/master/NetworkMessage.hpp
- **Guide utilisateur WSJT-X (section UDP) :** https://wsjt.sourceforge.io/wsjtx-doc/wsjtx-main-2.7.0.pdf
- **Implémentation de référence bien documentée (Go, lisible) :** https://pkg.go.dev/github.com/k0swe/wsjtx-go/v4
- **Accroche projet :** `logx_wsjtx.py` (cité dans ta roadmap).

### 4.4 N1MM Logger+ — broadcast UDP (LE format à généraliser pour ton chantier §3.6 « réseau ADIF générique »)
Beaucoup d'outils de l'écosystème parlent ce protocole ; le supporter t'ouvre l'interop large.

- **Spec officielle External UDP Broadcasts :** https://n1mmwp.hamdocs.com/appendices/external-udp-broadcasts/
  - Messages XML UTF-8 : `AppInfo`, `RadioInfo` (toutes les 10 s), `ContactInfo`, `Contact Replace/Delete`, `Spot`, `Score`, `LookupInfo`.
  - Ports par défaut : **12060** (contacts/radio/app), 12040 (rotor). UDP unicast ou broadcast, `SO_REUSEADDR` pour partage de port.
  - Fréquences en unités de 10 Hz (pas de décimale).
- **Accroche projet :** `logx_adifnet.py` existe déjà → tu es déjà sur ce chantier. Supporter en réception les messages N1MM (+ ADIF-over-UDP) te branche à N1MM, DXLog, Log4OM… d'un coup.

---

## 5. Propagation & données solaires

- **HamQSL / N0NBH — le flux de référence (bannières + XML) :** https://www.hamqsl.com/solar.html
  → XML exploitable directement : SFI, A, K, sunspots, conditions HF jour/nuit par bande, aurora, etc. C'est la source la plus utilisée par les loggers.
- **VOACAP — modèle de prédiction HF (le standard) :** https://www.voacap.com/ et aide modèle : https://www.voacap.com/2023/itshfbc-help/voacap-general.html
  → pour des prédictions point-à-point/area, tu peux packager le moteur ITSHFBC ou t'inspirer de VOAProp (http://www.g4ilo.com/voaprop.html).
- **Comparatif d'outils de propagation 2026 (veille) :** https://dxradar.com/blog/best-propagation-apps-2026
- **Accroche projet :** `logx_propagation.html`, `logx_tropo.py`, `logx_meteors.py`, `logx_beacons.py`. Ta profondeur (tropo, météores, grey-line) est déjà au-dessus de la moyenne ; HamQSL XML couvre le solaire « officiel » sans le calculer toi-même.

---

## 6. Diplômes / QSL / upload (LoTW, eQSL, Club Log, HamQTH, QRZ)

- **LoTW — doc développeur ARRL (intégration loggers) :** https://lotw.arrl.org/lotw-help/developer-information/
  - Intro développeur (PDF) : https://www.arrl.org/files/file/LoTW_Developer/DeveloperIntro.pdf
  - Signature & upload en ligne de commande (TQSL) : https://lotw.arrl.org/lotw-help/cmdline/ et https://lotw.arrl.org/lotw-help/signing/
  - Soumettre des QSO par programme : https://lotw.arrl.org/lotw-help/developer-submit-qsos/
- **Club Log — API upload/DXCC :** https://clublog.freshdesk.com/support/solutions/articles/54904-how-to-query-club-log-for-dxcc-info
- **HamQTH — upload ADIF & temps réel :** `prg_log_upload.php` / `qso_realtime.php` (voir §2).
- **Accroche projet :** `logx_qsl.py`, `logx_awards.py`. TQSL en ligne de commande est la façon propre d'automatiser LoTW sans réimplémenter la crypto de signature.

---

## 7. Projets open-source de référence à étudier (architecture, pas copier-coller)

- **Cloudlog (PHP/MySQL, web, très complet, HF→micro-ondes) :** https://github.com/magicbug/Cloudlog — excellent pour voir un **schéma de base QSO mûr** et des intégrations (LoTW, eQSL, Club Log, CAT).
- **Wavelog (fork moderne de Cloudlog, très actif, Docker) :** https://github.com/wavelog/wavelog — doc : https://docs.wavelog.org/ — bon modèle d'**API REST** de logbook.
- **qxsl (Java) — décodeur ADIF + moteur de scoring contest en LISP :** https://github.com/autodyne/qxsl — très pertinent pour ton **moteur de score générique à briques** : approche « règles déclaratives » proche de ta Phase 2.
- **adif-multitool (Go) — valider/convertir/modifier de l'ADIF en CLI :** https://github.com/flwyd/adif-multitool — banc d'essai idéal pour tester la conformité de tes exports.
- **Tucnak (C) — contest VHF/THF, gère EDI/REG1TEST nativement :** https://tucnak.nagano.cz/wiki/Contest — la référence libre côté THF européen ; à étudier pour le dépouillement EDI et le scoring locators.
- **TaffyQSL — logbook libre récent avec signature QSO :** https://github.com/sophiel-meow/TaffyQSL
- **hunterlog (Python) — chasseur POTA/SOTA :** https://github.com/cwhelchel/hunterlog — code Python propre pour consommer les API POTA/SOTA.
- **Topics GitHub à suivre :** https://github.com/topics/hamradio-logbook et https://github.com/topics/adif

---

## 8. Communautés, forums & veille (FR + international)

- **REF (Réseau des Émetteurs Français) — clusters, règlements concours THF/HF :** https://web.r-e-f.org/
- **Radioamateurs France (actus, cluster, ressources) :** https://www.radioamateurs-france.fr/cluster/
- **ON4KST Chat (VHF/UHF/microwave, tu l'intègres déjà) :** https://www.on4kst.com/
- **SOTA Reflector (forum dev + API) :** https://reflector.sota.org.uk/
- **WSJTX groups.io (support protocole UDP) :** https://wsjtx.groups.io/g/main
- **N1MM Logger+ groups.io :** https://groups.io/g/N1MMLoggerPlus
- **linuxham groups.io (Hamlib, flrig, CQRLOG) :** https://groups.io/g/linuxham
- **DXZone — annuaire logiciels contest/logging (veille concurrentielle) :** https://www.dxzone.com/catalog/Software/Contesting/

---

## 9. Priorisation suggérée (mappée sur tes lots roadmap)

**Lot rapide, fort ROI :**
1. Brancher la **validation ADIF 3.1.7** sur les fichiers TSV officiels (§1.1) → fiabilise import/export d'un coup.
2. Ajouter **HamQTH + HamDB** en repli gratuit du callbook (§2) → couvre les users sans QRZ.
3. Ajouter le **repli RBN via HamQTH JSON** (§3.2) → supprime la fragilité telnet.

**Lot moyen :**
4. Généraliser l'interop réseau en **écoutant le protocole N1MM UDP + ADIF-over-UDP** (§4.4) → interop N1MM/DXLog/Log4OM.
5. Rafraîchissement auto de **cty.dat (AD1C)** (§1.4), comme les règlements.
6. Solaire officiel via **HamQSL XML** en complément de tes calculs (§5).

**Lot structurant / veille continue :**
7. Étudier **qxsl** pour consolider ton moteur de score à briques (§7).
8. Étudier **Cloudlog/Wavelog** pour ton schéma QSO et ton API cloud sync (§7, chantier §3.5).
9. Conformité **EDI/REG1TEST** vérifiée contre Tucnak et la spec UKSMG (§1.3, §7).

---

*Toutes les URL ci-dessus ont été collectées et vérifiées le 21 juillet 2026. Les API tierces (POTA, HamQTH, PSK Reporter…) peuvent changer : prévois une couche d'abstraction par source (tu l'as déjà en partie) pour absorber les évolutions.*
