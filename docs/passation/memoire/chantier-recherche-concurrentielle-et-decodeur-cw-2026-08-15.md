---
name: chantier-recherche-concurrentielle-et-decodeur-cw-2026-08-15
description: "Décodeur CW cassé sur IC-7300 réel diagnostiqué+corrigé (AGC réel) ; 5 évolutions concurrentielles, 3/5 livrées ce chantier, 5/5 réellement — WinKeyer existait déjà"
metadata: 
  node_type: memory
  type: project
  originSessionId: 98b0707f-1a89-40bf-8422-4ab7b88ba78a
  modified: 2026-08-16T10:23:15.099Z
---

Le 15/08/2026, F4GLD a signalé le décodeur CW « catastrophique » (rien
décodé) en test réel sur son IC-7300, et demandé une comparaison avec fldigi
(référence open source) + une veille concurrentielle (SmartLogger, DXAtlas,
OmniRig, F6GQK dxfile, SwissLog).

**Diagnostic confirmé (agent + tests empiriques)** : le seuil de détection
de `logx_cwdecoder.js` était en ÉCHELLE ABSOLUE (`noiseFloor*2.8+0.003`),
calibré sur des tons de test synthétiques à amplitude maximale — un signal
radio réel, plus faible, ne dépassait jamais ce plancher. Corrigé par un
AGC réel (pic de signal suivi, seuil relatif) + rejet des impulsions de
bruit courtes + test de périphérique automatique à l'ouverture du panneau.
Piège trouvé PENDANT l'implémentation (pas prévu par le diagnostic initial) :
un bootstrap `agcPeak`/`noiseFloor` à 0.01 (au lieu d'une valeur très basse,
0.001) laissait passer le même symptôme pendant plusieurs secondes après
l'ouverture — la décroissance du pic de signal est volontairement très
lente (~0,1%/bloc, pour ne pas l'oublier entre deux marques d'un même
message), donc un bootstrap trop haut met du temps à se résorber. Trouvé
uniquement parce que `CwAudioDecoder`/`_onBlock()` n'avait JAMAIS eu de test
propre avant ce chantier — seuls `MorseTimingDecoder`/`goertzelMagnitude`
l'étaient séparément.

**5 évolutions concurrentielles approuvées par F4GLD (« on fait tout »)** —
voir aussi [[feedback-jamais-citer-concurrents-sauf-open-source]] pour la
contrainte de présentation (aucun nom de concurrent, sauf open source ; plus
soigné visuellement) qui s'applique aux 5. Statut au 16/08/2026 : **4/5
livrées**, dans l'ordre de priorité prévu, une branche/PR par chantier.

1. **FAIT (16/08, PR #99)** — Upload LoTW automatique, `tqsl` en mode
   silencieux (`logx_qsl.py` : `upload_lotw()`, exit codes ARRL documentés,
   `_find_tqsl_binary()` PATH-only).
2. **FAIT (16/08, PR #100)** — Bandmap multi-bandes : `logx_bande.html`
   (déjà multi-instance par conception) complété d'un marqueur VFO ;
   le bandmap LOGBOOK intégré (qui avait déjà le VFO mais reste
   mono-instance, `currentBand` sert aussi à la saisie QSO) n'a PAS été
   refactoré — jugé trop risqué pour le même bénéfice utilisateur.
3. **FAIT, scope adapté (16/08, PR #101)** — POTA : **pas d'upload
   automatique**. Recherche préalable a montré que POTA n'a AUCUNE API
   publique documentée pour ça (contrairement à LoTW/tqsl) — seule voie
   non officielle = mot de passe du compte POTA via Cognito (bibliothèque
   tierce v0.1.0, très jeune), et vérifié que même les concurrents ne le
   font pas (ils préparent un ADIF pour dépôt manuel, comme nous).
   Implémenté à la place : `logx_activation.activation_qsos()` (factorisé
   hors de `activation_state()`) + `logx_pota.export_filename()` (nom
   EXACT `callsign@parcRef-date.adi` attendu par l'auto-uploader du site)
   + `GET /pota/export_adif` + bouton LOGBOOK qui télécharge puis ouvre la
   page de dépôt pota.app. **Si un futur chantier reprend "upload POTA",
   ce choix (export assisté, zéro identifiant stocké) a déjà été validé par
   F4GLD après cette recherche — ne pas re-proposer l'upload silencieux par
   mot de passe sans nouvelle raison de le faire.**
4. **FAIT (16/08, PR #102)** — Mini-grille de progression bande×mode LoTW à
   la frappe d'un indicatif : `logx_awards.lotw_grid()` réutilise le même
   moteur que `besoin_lotw()` (`_creneaux_confirmes_lotw`) + `CHALLENGE_BANDS`
   (déjà utilisé par le DXCC Challenge) — ajoutée au champ `lotw_grid` du
   endpoint `/call/history` DÉJÀ interrogé à chaque frappe (zéro requête
   réseau de plus). Widget `#lotwGrid` dans `logx_callbook.js`, à côté de
   l'alerte texte existante `#prevQsos` (laissée intacte). Couleurs =
   uniquement des variables CSS déjà définies (--green/--accent2/--border),
   jour/nuit corrects sans y avoir pensé.
5. **DÉJÀ FAIT AVANT CE CHANTIER — le rapport concurrentiel du 15/08 avait
   tort** : en s'apprêtant à démarrer ce 5e point (16/08), grep de
   contrôle avant toute écriture (réflexe "vérifier avant de recommander
   depuis la mémoire") → `logx_winkeyer.py` existe déjà, COMPLET (protocole
   K1EL octet par octet, 1200 bauds/2 stop bits, `envoyer()`/`arreter()`/
   `tester()`), `tests/test_winkeyer.py` (31 tests, verts), section CONFIG
   dédiée déjà `expert-only` avec icône SVG mono, priorité WinKeyer >
   CAT natif déjà câblée côté serveur (`logx_http.py`). Seule réserve —
   dans le docstring du module lui-même : « aucun WinKeyer n'a été
   branché [...] le premier essai sur un boîtier réel reste à faire » —
   validation matérielle que seul F4GLD peut faire, pas un chantier de
   code. Le rapport concurrentiel initial du 15/08 ne l'avait
   apparemment pas croisé avec le code existant avant de le lister comme
   manquant — ne pas refaire cette erreur : TOUJOURS grep le nom de la
   fonctionnalité dans le dépôt avant de la mettre en file d'attente,
   pas seulement avant de l'implémenter.

Les 5 points de la liste sont donc désormais tous couverts côté code — le
seul reliquat concret est la validation WinKeyer sur un boîtier réel
(action F4GLD, pas un chantier).

**Revue de code demandée par F4GLD malgré les tests déjà verts (16/08/2026,
avant tout essai matériel)** : chaque octet de protocole de
`logx_winkeyer.py` vérifié contre la fiche technique OFFICIELLE K1EL
WinKeyer3.1 (Rev 1.3, `k1elsystems.com/files/WK3_Datasheet_v1.3.pdf`) —
ADMIN=0x00/RESET=0x01/HOST_OPEN=0x02/HOST_CLOSE=0x03, SET_WPM=0x02 (plage
5-99 confirmée identique), PTT_LEAD_TAIL=0x04 (pas de 10 ms confirmé),
CLEAR_BUFFER=0x0A, SET_MODE=0x0E, ET le point le plus à risque — trame série
« eight data bits, 2 stop bits, with no parity » à 1200 bauds — confirmés
MOT POUR MOT (page 18 de la fiche). Masque de détection d'octet d'état
`0xC0` reproduit exactement le pseudo-code officiel du fabricant (page 3).
Câblage serveur revu aussi : WinKeyer consulté AVANT tout backend CAT
(`logx_http.py`), verrou SO2R correctement dissocié (un seul WinKeyer
physique sert les deux radios via son propre mode SO2R matériel — confirmé
par la fiche technique elle-même, pas une lacune LogX AI), CONFIG câblé aux
3 endroits requis (aide, sauvegarde, restauration). **Aucun bug trouvé** —
review complète, pas seulement une relecture des tests.

**How to apply:** Ne PAS relancer de chantier WinKeyer sauf si F4GLD
signale un problème après un essai réel — dans ce cas, c'est un bug à
corriger sur `logx_winkeyer.py`, pas une fonctionnalité à construire. Le rapport
complet de recherche concurrentielle initial (citations de code exactes,
statut vérifié d'OmniRig déjà intégré) n'est pas dans cette mémoire — relire
la conversation du 15/08/2026 si le détail est nécessaire à nouveau ; cette
mémoire ne garde que la synthèse actionnable. Voir aussi
[[piege-vocabulaire-identifiants-js-pas-seulement-texte-visible]] (trouvé
pendant POTA, applicable à toute future page touchant la barre d'activation
POTA/SOTA/IOTA/WWFF) et [[piege-setupmodal-bloque-clics-serveur-test-frais]]
(trouvé pendant la mini-grille, applicable à toute vérification navigateur
du formulaire QSO LOGBOOK sur un serveur de test frais).
