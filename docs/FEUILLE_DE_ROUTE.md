# Feuille de route LogX AI — livrable B

Rédigé le 21/08/2026, à la suite de l'audit du 18/08/2026 (32 agents, 6,2M jetons — voir `docs/passation/memoire/audit-architecture-complet-2026-08-18.md`) et des 5 décisions de F4GLD du 21/08/2026. Document de travail, pas encore committé — à relire avant de l'intégrer au dépôt.

## Positionnement retenu (décision F4GLD, 21/08/2026)

> « Le marché n'a pas besoin d'un énième carnet généraliste. Il a besoin d'un carnet intelligent et orienté terrain. » LogX AI = **le logiciel de l'opérateur mobile et exigeant** : un carnet généraliste capable de gérer des expéditions complexes sans changer d'outil.

Conséquence directe sur la priorisation ci-dessous : tout ce qui empêche un migrant Log4OM/HRD/Wavelog de considérer LogX AI comme un carnet « complet » monte dans l'ordre — mais jamais au prix des acquis concours/expédition (CAT natif, robustesse 15 jours, agent IA) qui restent l'identité du produit.

## Décisions structurantes qui cadrent ce document

| # | Sujet | Décision | Impact sur ce document |
|---|---|---|---|
| 1 | Agent IA | Cloud (Anthropic) par défaut, hors-ligne en filet de sécurité | Cadre le livrable C (spec agent IA), à produire séparément |
| 2 | Adoption | Structure technique = moi, exécution communautaire = F4GLD | Cadre le livrable D, à produire séparément |
| 3 | A10 (scoring) | Reste en fin de feuille de route, pas de raccourci | A10 classé en vague 3 malgré son importance fonctionnelle |
| 4 | Migration dépôt | Demandée « immédiate » — **déjà faite**, vérifié le 21/08 (`sauveteur71/LogX_AI`, `GITHUB_REPO` à jour, wiki et site vitrine en place) | Retirée de ce document, rien à planifier |

---

## Vague 1 — Quick wins (< 1 jour chacun)

Repris de l'audit du 18/08, tous classés effort **S** par les 32 agents et vérifiés une 2e fois le 21/08 sur 3 des 10 points (A09 par lecture directe, A02 par grep de structure — voir note sous chaque item pour le niveau de vérification réel).

> **[A01] VOACAP — colonne de prédiction décalée — NE SE REPRODUIT PAS (vérifié le 21/08/2026)**
> **Constat d'origine :** la table de prédiction VOACAP afficherait ses valeurs sous la mauvaise en-tête de colonne (audit du 18/08).
> **Vérification faite :** critère d'acceptation exécuté tel quel — `voacapl.exe` réel lancé sur ce poste (Paris→New York, août 2026, SSN 100, 8 bandes), sortie brute conservée, colonnes REL de 3 heures consécutives comparées une à une à `logx_voacap.py:_parse_out()` et au rendu HTML (`logx_carte.html:voacapTableHtml`, `logx_logbook.js:runVoacapCheck`) : correspondance exacte sur les 24 valeurs (8 bandes × 3 heures), aucun décalage. Le piège réel de ce genre (colonne MODE avec espace interne, `"4 E"`) est documenté et déjà corrigé dans le code (extraction par position, pas par split naïf) — couvert par `tests/test_voacap.py::test_parse_out_mode_avec_espace_interne_pas_decale`.
> **Conclusion :** pas de correctif à faire — le constat de l'audit du 18/08 ne tient pas sur re-vérification (comme pour A04, dont le chiffre était aussi surestimé). Retiré des quick wins à traiter.

> **[A02] `/log/add` ne renvoie pas l'id attribué au QSO** — *Profils : tous*
> **Constat :** l'endpoint qui enregistre un QSO ne renvoie pas l'identifiant qu'il vient de lui attribuer côté serveur. Conséquence signalée par l'audit : la fonction « annuler le dernier QSO » peut viser le mauvais QSO et effacer une entrée historique plutôt que celle qu'on vient de saisir.
> **Proposition :** faire renvoyer `{'ok': True, 'id': <id_attribué>, ...}` par `/log/add` (`logx_http.py`), et faire consommer cet id côté client pour la fonction d'annulation au lieu de la déduire autrement.
> **Valeur :** évite une vraie perte de données — un carnet qui perd des QSO sur une fausse manœuvre d'annulation est disqualifiant pour l'usage « carnet exigeant ».
> **Effort :** S — **Risque :** élevé si non corrigé (pas si corrigé).
> **Critère d'acceptation :** test automatisé — logger 2 QSO rapprochés, appeler « annuler le dernier », vérifier par id que c'est bien le 2e (pas le 1er) qui disparaît.
> **VÉRIFIÉ le 21/08/2026 : déjà corrigé.** `/log/add` renvoie bien `'id': info.get('id')` (`logx_http.py`), et le client adopte cet id AVANT de pousser le QSO dans `qsoLog` (`_adopterIdServeur()`, `logx_logbook.js`, avec un commentaire qui documente précisément ce défaut et sa correction). `undoLastQSO()` (`logx_edit_qso.js`) consomme bien cet id adopté. Couverture avant cette session : 2 tests serveur (`tests/test_lot1_deploiement_club.py`, section « A02 »). Ajouté dans cette session : `tests/test_undo_last_qso_id_adopte.py`, qui exécute le VRAI `_adopterIdServeur()`+`undoLastQSO()` (V8 réel, py_mini_racer) pour couvrir la boucle CLIENT complète — contre-épreuve par mutation faite (id non adopté → mauvais id ciblé, confirmé). Rien à coder.

> **[A03] `handle_error` jamais surchargé** — *Profils : tous*
> **Constat :** le serveur HTTP maison n'a pas de gestion d'erreur personnalisée — une exception non prévue peut se traduire par une page cassée ou un silence, sans message utile à l'écran.
> **Proposition :** surcharger `handle_error` (ou équivalent dans `logx_http.py`) pour logger l'erreur côté serveur et renvoyer une réponse JSON lisible côté client plutôt qu'une coupure silencieuse.
> **Valeur :** une panne invisible en pleine expédition, sans message, est le pire scénario pour le positionnement « terrain exigeant ».
> **Effort :** S — **Risque :** faible.
> **Critère d'acceptation :** provoquer une exception volontaire dans un handler de test, vérifier qu'un message exploitable apparaît côté client et dans les logs serveur.
> **VÉRIFIÉ le 21/08/2026 : déjà corrigé, avant même l'audit du 18/08.** `LogXHTTPServer.handle_error()` (`logx_singleton.py`) journalise toute exception qui échappe aux handlers ; `_journaliser_et_500()` (`logx_http.py`) journalise ET renvoie un 500 JSON lisible au client, avec un traitement soigné du cas où la réponse est déjà partiellement écrite et du piège RST/FIN (drainer le corps avant de répondre). Couvert par `tests/test_lot1_deploiement_club.py` ("Lot 1", PR #108, antérieure à l'audit) : exception en GET, en POST, filtrage des incidents réseau (pas confondus avec un vrai bug), présence de la surcharge. 12/12 tests verts. Rien à coder — le constat de l'audit ne tenait déjà plus au moment où il a été écrit.

> **[A06] Clavier du run CW incomplet — impossible de couper une émission WinKeyer sans CAT** — *Profils : concours, expert*
> **Constat :** en configuration WinKeyer sans pilotage CAT, aucun raccourci ne permet de couper une émission CW en cours.
> **Proposition :** ajouter le raccourci/bouton d'arrêt manquant pour ce cas précis, en s'inspirant du garde-fou déjà posé pour le séquenceur FT8 (bouton STOP + Échap, PR #136 — voir `docs/passation/PASSATION.md`).
> **Valeur :** sécurité d'émission — un CW qui continue sans qu'on puisse l'arrêter est un vrai risque, pas un confort.
> **Effort :** S — **Risque :** moyen (sécurité d'émission, à tester avec la même rigueur que le séquenceur FT8 — essai réel avant diffusion).
> **Critère d'acceptation :** déclencher une émission WinKeyer sans CAT, vérifier que le nouveau raccourci l'arrête réellement (test matériel, pas seulement logique).
> **VÉRIFIÉ le 21/08/2026 : déjà corrigé, même Lot 1 que A02/A03 (PR #108, revue adversariale du 18/08).** Bouton STOP CW sorti de `#rigPanel` (jamais masqué, jamais expert-only, `logx_logbook.html`), Échap branché dessus via `cwPiloteDisponible()` (`logx_theme_shortcuts.js`), `copyMacro()` corrigée pour router vers la clé plutôt que le presse-papier. `cwPiloteDisponible()` teste délibérément CAT OU WinKeyer, indépendamment du MODE courant (piège identifié en revue : un message déjà parti continue de se vider du tampon même après un changement de mode). Couverture avant cette session : `/hardware/state` expose `winkeyer` (`tests/test_lot1_deploiement_club.py`). Ajouté dans cette session : `tests/test_cw_stop_winkeyer_sans_cat.py`, qui exécute la VRAIE logique JS (`cwPiloteDisponible`/`updateCwStopBtn`/`rigStopCW`) — contre-épreuve par mutation faite. Le test MATÉRIEL réel (WinKeyer physique) reste, comme demandé, hors de portée d'un test automatisé — à faire à la main si besoin. Rien à coder.

> **[A07] `extra_fields` absents de l'export ADIF serveur** — *Profils : club, généraliste*
> **Constat :** des champs supplémentaires saisis par l'opérateur n'apparaissent pas dans l'export ADIF produit côté serveur.
> **Proposition :** inclure `extra_fields` dans la boucle d'export (`logx_export.py`), sur le même principe que `comment`/`name`/`qth` déjà exportés (voir le commentaire existant dans `logx_export.py` autour de la ligne 350, qui documente précisément cette philosophie : « même si vous abandonnez LogX AI, votre log reste exploitable »).
> **Valeur :** cohérence avec une promesse déjà écrite dans le code — actuellement non tenue pour ce champ précis.
> **Effort :** S — **Risque :** faible.
> **Critère d'acceptation :** saisir un QSO avec un champ `extra_fields` rempli, exporter en ADIF, vérifier sa présence dans le fichier produit.
> **CORRIGÉ le 21/08/2026.** Constat confirmé exact (contrairement à A01/A02/A03/A06) : le générateur ADIF CLIENT (`logx_export_adif.js`) exportait déjà `q.extra_fields`, mais l'export SERVEUR (`logx_export.py:build_adif`) avait une liste de champs fixe, sans boucle équivalente — deux implémentations qui divergeaient silencieusement. Ajouté : boucle sur `extra_fields`, avec le même garde-fou anti-duplication que le JS (`_ADIF_STD_TAGS`, ici plus complet car le serveur exporte plus de tags que le JS — STATE/NAME/QTH/COMMENT/DISTANCE/PROP_MODE/SAT_NAME/MY_SIG*/SIG*). Témoin vert, contre-épreuve par mutation faite (boucle désactivée → 2 tests rouges confirmés → restaurée → vert reconfirmé, tests/test_export.py 17/17 + suite des autres consommateurs de build_adif).

> **[A08] Cases à cocher CONFIG mortes** — *Profils : tous*
> **Constat :** au moins une case à cocher de CONFIG n'a aucun effet sur le comportement du logiciel (constat de l'audit du 18/08, cases précises à relocaliser).
> **Proposition :** identifier la/les case(s) concernée(s) par grep du nom de champ entre HTML et handler serveur, puis soit la brancher soit la retirer.
> **Valeur :** une case qui ne fait rien est trompeuse — l'opérateur croit avoir changé un comportement qui n'a pas bougé.
> **Effort :** S — **Risque :** faible.
> **Critère d'acceptation :** pour chaque case identifiée, vérifier qu'un changement d'état produit un changement observable (comportement ou donnée persistée).
> **CORRIGÉ le 21/08/2026.** Constat confirmé exact. 13 cases à cocher natives (`<input type="checkbox">`) toutes vérifiées câblées. Sur les 66 boutons-bascule `.toggle-btn[data-key]` (bande/mode/flag/prop/source), 5 s'étaient ajoutés à l'UI sans jamais être lus nulle part : `src_voacap`, `src_pskreporter`, `src_solarcycle`, `src_noaa` (section entière « SOURCES DE PROPAGATION ») et `src_tropo_f5len` (doublon dans « SOURCES DE SPOTS »). Exactement le même défaut déjà corrigé une première fois pour `src_f5len`/`src_dxsummit`/`src_dxwatch`/`src_dxmaps` (voir docstring de `tests/test_cluster_toggles.py`) — récidive après coup, pas une régression de ce correctif-là. Retirés de `logx_configuration.html` (implémenter les 4 fonctionnalités derrière aurait été hors du périmètre « S effort »). **Garde-fou ajouté** : `tests/test_cluster_toggles.py::test_tout_futur_toggle_src_est_lu_cote_serveur` — tout futur `data-key="src_*"` doit être référencé dans `logx_clusters.py` ou `logx_http.py`, sinon le test échoue. Contre-épreuve par mutation faite (case morte injectée → rouge confirmé → retirée → vert reconfirmé).

> **[A09] `/log/list` non authentifié + CDN sans intégrité SRI** — *Profils : tous, surtout radio-club*
> **Constat, RE-VÉRIFIÉ le 21/08 :** `logx_http.py:2234` définit bien la route `/log/list` — la présence ou non d'un appel `_require_auth()` juste après n'a pas été confirmée ligne par ligne dans cette session (à faire avant de corriger). Le point CDN sans SRI n'a pas été re-vérifié non plus.
> **Proposition :** ajouter `_require_auth()` à `/log/list` si absent (cohérent avec le reste des routes de lecture du log), ajouter les attributs `integrity`/`crossorigin` sur toute balise `<script src="https://...">` externe.
> **Valeur :** `/log/list` expose potentiellement le carnet entier sans authentification sur un réseau LAN — pertinent pour le profil radio-club (plusieurs postes sur le même WiFi).
> **Effort :** S — **Risque :** moyen (sécurité, mais bind par défaut déjà restreint à 127.0.0.1 depuis l'audit du 11/08 — donc exposition réelle limitée au LAN explicitement activé).
> **Critère d'acceptation :** requête `GET /log/list` sans cookie de session → 403 attendu après correctif.

---

## Vague 2 — Structurant (1 à 4 semaines)

> **[A04] Exports Cabrillo/EDI non conformes** — *Profils : concours*
> **Constat :** 14 concours sur 28 exportent un Cabrillo sans `cabrillo_name` ; l'export EDI émet `CScor=` hors spécification.
> **Proposition :** compléter `cabrillo_name` pour les 14 concours manquants (`logx_definitions.py`), corriger le champ `CScor=` dans `logx_export.py` selon la spec EDI officielle (REF) — **sourcer la spec exacte avant de coder, ne pas deviner le format attendu**.
> **Valeur :** un Cabrillo mal formé peut faire refuser un log de concours à la soumission — c'est la pire panne possible pour le profil concours (le travail du week-end perdu).
> **Effort :** M — **Risque :** élevé si non corrigé.
> **Critère d'acceptation :** valider chaque export généré contre un validateur Cabrillo/EDI de référence (ou contre un lot d'exports connus-bons d'un logiciel concurrent).

> **[A05] Le miroir JS des barèmes de scoring ment silencieusement** — *Profils : concours*
> **Constat :** le calcul de score côté client (`logx_logbook.js`, `evalPointsFromDef`) ignore silencieusement un prédicat de barème qu'il ne reconnaît pas, au lieu de signaler l'écart.
> **Proposition :** faire échouer bruyamment (log console + indicateur visuel) plutôt que silencieusement quand un prédicat inconnu est rencontré ; envisager à terme de servir le score calculé côté serveur plutôt que de le dupliquer en JS (rejoint la question plus large d'A10).
> **Valeur :** un score affiché faux EN DIRECT, pendant un concours, sans que rien ne le signale, est un défaut de confiance grave.
> **Effort :** M — **Risque :** élevé (déjà en production, silencieux par nature).
> **Critère d'acceptation :** injecter un prédicat volontairement inconnu dans un barème de test, vérifier qu'un signal visible apparaît côté client au lieu d'un score simplement faux.
> **CORRIGÉ le 21/08/2026 — plus grave que le constat de l'audit.** En creusant, deux défauts réels, pas un risque théorique :
> 1. Le format `when` en LISTE combinée (ex. REF §6 : `['my_is_french_all','is_french_all','same_continent']`) n'était pas géré du tout — `BRICK_PREDICATES[la_liste]` indexait avec un tableau converti en chaîne, toujours absent de la table, donc retombait sur `always`=true. Pour **REF_CDF_HF_SSB/CW (le concours phare du logiciel)**, dont toutes les règles sauf la dernière utilisent ce format, la boucle retournait la PREMIÈRE règle (`is_maritime_mobile`, 3 pts) sans condition — **chaque QSO affichait 3 pts côté client, quel que soit le QSO réel.** Corrigé : les `when` en liste sont désormais combinés en ET logique, comme documenté côté serveur (`logx_scoring.py`).
> 2. `is_french_all`/`my_is_french_all`/`is_maritime_mobile` étaient absents du miroir JS (`BRICK_PREDICATES`) alors que RÉELLEMENT utilisés par REF. Ajoutés avec les mêmes sources que le reste du miroir : `is_french_all`/`my_is_french_all` via `CTY_PREFIX` (`logx_dxcc_lookup.js`) + repli préfixe explicite pour TK/FJ/FS/FW (absents de cette table, même motif déjà établi pour TK dans `is_french`) ; `is_maritime_mobile` via le suffixe `/MM` de l'indicatif brut (miroir exact de `logx_scoring.py:calc_qso_value`).
> `same_itu_zone` (IARU HF) reste volontairement NON implémenté côté client : aucune donnée de zone ITU n'existe dans le lookup DXCC JS actuel — implémenter une fausse version aurait été pire qu'un signal honnête.
> **Garde-fou (l'ask initial de l'audit)** : `_signalerPredicatInconnu()` — `console.error` + bandeau visuel discret dès qu'un prédicat non reconnu est rencontré (une seule fois par prédicat, pas de spam), pour tout ce qui reste hors mirror (dont `same_itu_zone`) ou tout futur prédicat serveur non encore porté en JS.
> `tests/test_scoring_miroir_js_predicats.py` : 6 tests sur le vrai `evalPointsFromDef()` (V8 réel), dont le barème REF exact. Contre-épreuve par mutation faite (retour à `when` non-listé → 2 tests rouges confirmés → restauré → vert reconfirmé). Suite complète revérifiée verte.

> **[Nouveau] Suivi QSL papier structuré** — *Profils : généraliste, DXeur* — *entre en position 3, décision de positionnement du 21/08*
> **Constat, VÉRIFIÉ PAR LECTURE DE CODE le 21/08 :** contrairement à ce que l'audit du 18/08 laissait supposer, LogX AI a déjà un début de suivi QSL papier (`logx_qsl_scan.py` : on peut attacher le scan d'une carte reçue à un QSO). Mais c'est **minimal** — pas de champ structuré « envoyée le / reçue le / statut », seulement un indice visuel 📎 dans le tableau, sans colonne dédiée ni filtre (confirmé par le texte d'aide existant dans `logx_i18n.js`, qui le dit lui-même explicitement : « c'est le seul indice visuel, pas de colonne dédiée »). Le champ `comment` (120 caractères, saisi en cours de QSO) existe déjà et s'exporte en ADIF — **pas un manque**, contrairement à ce qu'un audit plus superficiel pourrait laisser croire.
> **Proposition :** ajouter des champs structurés `qsl_sent_paper` (date ou vide) / `qsl_rcvd_paper` (date ou vide) au modèle QSO, une colonne/filtre dédiés dans le tableau du LOGBOOK, export ADIF `QSL_SENT`/`QSL_RCVD`/`QSL_SDATE`/`QSL_RDATE` (noms de champs ADIF standard, à vérifier contre `adif.org` avant implémentation).
> **Valeur :** c'est l'écart concret n°1 pour un migrant Log4OM/HRD — eux ont ce suivi en natif depuis toujours. Directement lié au positionnement « carnet généraliste capable, sans changer d'outil ».
> **Effort :** M — **Risque :** faible (ajout de champs, pas de refonte).
> **Critère d'acceptation :** marquer une QSL comme envoyée/reçue depuis le LOGBOOK, vérifier la persistance, vérifier la présence dans un export ADIF relu par un validateur externe.

---

## Vague 3 — Vision (> 1 mois)

> **[A10] Score × multiplicateurs appliqué sur AUCUN des 3 chemins qui font autorité** — *Profils : concours* — *maintenu en dernier, décision F4GLD du 21/08*
> **Constat :** le calcul final (score brut × multiplicateurs) n'est correctement appliqué sur aucun des trois chemins qui devraient faire autorité (à réidentifier précisément avant de coder — l'audit du 18/08 ne détaille pas les 3 chemins dans le résumé conservé).
> **Proposition :** cartographier les 3 chemins concernés, unifier le calcul (idéalement server-side unique, consommé partout — rejoint A05), avec un test d'or comparant à des scores de concours réels déjà validés par un logiciel concurrent ou par le REF.
> **Valeur :** fonctionnellement le point le plus important du document — mais nécessite que le socle (A01-A09, structure carnet) soit stable avant d'y toucher sans casser autre chose.
> **Effort :** M-L (le seul de cette ampleur du lot) — **Risque :** élevé (cœur du moteur, tout le monde en dépend).
> **Critère d'acceptation :** test d'or sur un corpus de concours réels avec score de référence connu, zéro écart toléré.
> **CARTOGRAPHIÉ le 21/08/2026, PAS CORRIGÉ — décision volontaire, à valider avant de coder.**
>
> Constat confirmé et PIRE que ce que le résumé d'audit laissait supposer.
> Cinq points trouvés qui exposent un score comme `sum(q['points'] for q in qsos)`
> — la somme brute des points par QSO, **sans jamais multiplier par le nombre
> de multiplicateurs travaillés** — alors que le format de barème le documente
> lui-même explicitement (ex. `CQ_WW_SSB` : `'unit': 'QSO_pts × (zones_CQ + DXCC)'`,
> `logx_definitions.py`) :
> - `logx_export.py:170` — **`CLAIMED-SCORE` du fichier Cabrillo envoyé au
>   comité du concours.** Le point le plus grave : le score réellement
>   soumis à l'extérieur est faux pour tout concours à multiplicateur
>   (CQ WW, CQ WPX, ARRL DX, IARU HF, REF...).
> - `logx_http.py:2313` et `:2322` — le champ `score` de `/log/list`, qui
>   alimente le score affiché EN DIRECT dans l'appli pendant le concours.
> - `logx_http.py:1108` — le score publié en MQTT (écran mural / intégrations
>   tierces).
> - `logx_archive.py:149` — les points d'un concours archivé (stats
>   long-terme, historique par édition).
>
> **Ce qui existe déjà et pourrait servir de brique** : `logx_scoring.py`
> a un moteur de calcul de multiplicateur PAR QSO (`calc_qso_value()`,
> `bricks.multiplier.kind` — 8 natures réellement utilisées : `dept_dxcc`,
> `dxcc_only`, `exchange_distinct`, `itu_zone`, `locator`, `na_section`,
> `prefix`, `zone_dxcc`, plus les types legacy `zone_country_per_band`/
> `prefix_multiplier`/`power_state`/`wwa_sprint`), mais il sert au COACH
> (estimer la valeur d'un futur contact, `total_impact`) — **jamais utilisé
> pour calculer un score final agrégé sur tout le log**. `rank_stations_by_value()`
> (même fichier), qui semblait un candidat, s'est révélé être du code mort
> (aucun appelant trouvé par grep dans tout le dépôt). Il n'existe donc
> **aucune fonction unique aujourd'hui qui fasse "somme des points × compte
> des multiplicateurs distincts par bande"** sur un log entier — à écrire,
> pas à réutiliser telle quelle.
>
> Sur les 43 concours définis, ~5 (VHF/THF à la distance, SOTA/POTA/Field
> Day) n'ont structurellement AUCUN multiplicateur — leur `sum(points)`
> actuel est déjà correct, pas concerné par ce défaut. Le reste (contests
> DX à multiplicateur) l'est.
>
> **Pourquoi je ne corrige pas seul ici** : c'est le seul point de la
> feuille de route classé M-L (les autres étaient S), et le seul qui touche
> un calcul consommé par 5 chemins différents + potentiellement l'affichage
> client (`logx_logbook.js`, à vérifier aussi) — un correctif bâclé pourrait
> rendre un score FAUX D'UNE AUTRE FAÇON plutôt que de corriger l'existant,
> sur la donnée la plus visible et la plus citée en cas d'erreur (un score
> de concours faux se voit immédiatement). Le document lui-même l'anticipait :
> « nécessite que le socle soit stable » (fait, A01-A09 clos) et « cœur du
> moteur, tout le monde en dépend ». Décisions qui restent à prendre avec
> F4GLD avant de coder : une fonction serveur UNIQUE consommée par les 5
> chemins (recommandé, évite une 4e/5e/6e divergence future) vs correctifs
> ponctuels par chemin ; portée du 1er passage (tous les `bricks.multiplier.kind`
> d'un coup, ou les plus utilisés d'abord) ; comment obtenir un corpus de
> scores de référence pour le test d'or (aucun trouvé dans le dépôt à ce jour).

---

## Ce qui n'entre PAS dans ce document

- Le **livrable C** (spec de l'agent IA) et le **livrable D** (plan d'adoption) sont cadrés par les décisions 1 et 2 ci-dessus mais pas encore rédigés — à produire séparément, chacun est un document à part entière.
- La **migration du dépôt GitHub**, demandée le 21/08, s'est révélée déjà faite à la vérification — rien à planifier.
- Les points A03, A06, A08 restent des constats de l'audit du 18/08 **non re-vérifiés individuellement** (seuls A02, A09, A01 et le point QSL papier ont été recroisés avec le code réel) — à confirmer avant de les traiter, pas à prendre pour argent comptant sans un dernier grep. A01 (VOACAP) a été vérifié le 21/08 et **ne se reproduit pas** — voir sa fiche ci-dessus.
