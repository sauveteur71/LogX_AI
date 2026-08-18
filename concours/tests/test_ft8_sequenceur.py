# -*- coding: utf-8 -*-
"""BANC D'ESSAI À HORLOGE VIRTUELLE du séquenceur FT8 — écrit AVANT la machine.

═══════════════════════════════════════════════════════════════════════════════
POURQUOI CE FICHIER EXISTE, ET POURQUOI IL EST ÉCRIT EN PREMIER
═══════════════════════════════════════════════════════════════════════════════

Un séquenceur FT8 a été écrit DEUX fois dans logx_ft8.html, et retiré deux fois.
Deux revues adversariales ont confirmé 24 puis 20 défauts (13 puis 10
CRITIQUES), et la 2e passe a montré que les correctifs de la 1re avaient
introduit de NOUVEAUX critiques.

La cause racine n'était pas « du code mal écrit » : LE MODÈLE TEMPOREL ÉTAIT
FAUX. Le code jugeait un créneau PASSÉ sur un état PRÉSENT. Le défaut
emblématique : le verrou « suis-je en train d'émettre ? » était consulté au
moment d'examiner un créneau DÉJÀ TERMINÉ. Or l'examen d'un créneau tombe
700 ms APRÈS le début du créneau suivant : si ce créneau suivant est le nôtre,
TOUT ce qui a été entendu pendant le créneau examiné était jeté. Le QSO ne
pouvait pas aboutir, et le seul garde-fou automatique restant (abandonner si la
cible répond à un tiers) devenait INATTEIGNABLE.

Ce défaut a survécu à deux implémentations ET à deux revues de code parce que
le harnais de test était STRUCTURELLEMENT AVEUGLE : il résolvait l'émission
instantanément. Dans un monde où émettre ne prend pas de temps, la chronologie
fautive n'existe pas — le test ne pouvait pas la voir, quelle que soit sa
qualité par ailleurs.

D'où l'inversion volontaire de l'ordre de travail : le banc d'abord, la machine
ensuite. Tant que la machine n'existe pas, les tests de comportement ÉCHOUENT —
c'est le résultat attendu de l'étape 1, pas un défaut du banc. Les trois tests
de FIDÉLITÉ (§1), eux, passent dès aujourd'hui : ils vérifient le banc et le
fichier existant, pas la machine à venir.

═══════════════════════════════════════════════════════════════════════════════
PRINCIPE DU BANC : TOUT EST INDEXÉ PAR NUMÉRO DE CRÉNEAU
═══════════════════════════════════════════════════════════════════════════════

Un créneau vaut Math.floor(t/15000)*15000. Le banc ne demande JAMAIS « où en
est-on maintenant » : il fournit à la machine le NUMÉRO du créneau examiné, et
la machine doit raisonner sur ce numéro. L'horloge virtuelle avance événement
par événement, chaque événement dans son PROPRE appel à ctx.eval() — voir
_Banc.avancer() pour le pourquoi (microtâches).

Deuxième principe, appris en écrivant ce banc : AUCUN test ne fige la CADENCE
du séquenceur (« il doit répondre au créneau N+1 »). La cadence est une
conséquence du calendrier de la page (voir § « Conséquence dérangeante »
ci-dessous), pas une décision du séquenceur. Les scénarios utilisent donc un
CORRESPONDANT RÉACTIF — une station simulée qui répond à ce qu'elle entend,
comme une vraie — plutôt qu'une liste de messages à des instants figés. Un
scénario figé aurait cadenassé une cadence particulière et serait devenu faux
au premier réglage de timing.

═══════════════════════════════════════════════════════════════════════════════
FIDÉLITÉ AU CALENDRIER RÉEL — les seuls chiffres qui comptent
═══════════════════════════════════════════════════════════════════════════════

Tout est RELU dans le source par test_calendrier_du_banc_fidele_au_source() :
si quelqu'un modifie le calendrier réel dans logx_ft8.html sans toucher au banc,
ce test tombe. C'est le garde-fou contre un banc qui dériverait en silence de la
page qu'il prétend tester — exactement le mode d'échec des deux tentatives.

1. PROGRAMMATION D'UNE ÉMISSION — logx_ft8.html lignes 1585-1590
   (window.envoyerMessage, déclarée ligne 1569) :

       const now = Date.now();
       let prochain = Math.ceil(now/15000)*15000;
       if(prochain - now < 1000) prochain += 15000;   // marge PTT+lecture
       await new Promise(resolve => setTimeout(resolve, prochain - Date.now()));

   Demander une émission à t=45700 la programme donc pour le créneau 60000 ; la
   demander à t=44500 la programme pour 60000 aussi (44500 → 45000, marge de
   500 ms < 1000, on saute un créneau).

2. DURÉE D'UNE TRAME ÉMISE — 79 symboles à 0,160 s = 12,64 s.
   SOURCE : Franke K9AN, Somerville G4WJS & Taylor K1JT, « The FT4 and FT8
   Communication Protocols », QEX juillet/août 2020. Les deux constantes sont
   dans le dépôt et relues par test_duree_trame_conforme_au_codec_du_depot :
   concours/logx_ft8_codec.js ligne 20 (FT8_SYMBOL_PERIOD = 0.160) et ligne 24
   (FT8_NN = 79). Le même chiffre est cité en clair dans logx_ft8.html
   lignes 1464-1467 (commentaire du chien de garde PTT).

3. INSTANT D'EXAMEN D'UN CRÉNEAU — logx_ft8.html lignes 1154-1192
   (verifierCycle), cadencée par setInterval(..., 250) ligne 1314 :

       const slotCourant = Math.floor(now/15000)*15000;
       const slotTermine = slotCourant - 15000;
       if(slotTermine > lastProcessedSlot && (now - slotCourant) >= 700){ ... }

   Le contenu d'un créneau n'est donc connu qu'à frontière+700 ms au plus tôt.
   Le timer tournant à 250 ms sans alignement sur la grille UTC, l'instant réel
   tombe dans [frontière+700, frontière+950[. Le banc joue +700 par défaut, et
   test_conclusion_identique_quelle_que_soit_la_phase_d_examen rejoue le QSO
   nominal à +700, +825 et +949 : aucune conclusion ne doit dépendre de la
   phase du timer.

4. LA CHRONOLOGIE FAUTIVE, EN CHIFFRES

   Notre trame occupe [S, S+12640[ dans le créneau S. L'examen du créneau X a
   lieu à X+15700. Ces deux intervalles se recouvrent quand S = X+15000, et
   SEULEMENT dans ce cas :

       X+15000 ≤ X+15700 < X+15000+12640

   Autrement dit : l'examen du créneau qui PRÉCÈDE une de nos émissions tombe
   toujours 700 ms après le début de cette émission. L'ancien code y testait
   « suis-je en train d'émettre MAINTENANT » — vrai — et jetait le contenu du
   créneau X, qui était pourtant un créneau d'ÉCOUTE. Le bon test est
   « slotExamine === seq.slotEmis ? », c'est-à-dire « ai-je émis PENDANT LE
   CRÉNEAU EXAMINÉ ? » — faux ici (X ≠ X+15000), donc le contenu doit être VU.

   test_reponse_pendant_que_nous_emettions_au_creneau_precedent construit ce
   cas en DEUX PASSES : une 1re passe découvre les créneaux que la machine
   choisit réellement d'occuper, la 2e y place la réponse de la cible au
   créneau Y-15000. Le test ne présuppose donc aucune cadence.

5. CONSÉQUENCE DÉRANGEANTE, CONSTATÉE EN SIMULANT (à remonter à F4GLD)

   Le contenu du créneau X n'est connu qu'à X+15700, et envoyerMessage ne peut
   alors viser que X+30000 (le créneau X+15000 a déjà 700 ms de retard, et la
   marge de 1000 ms l'exclut de toute façon). Une réponse ne peut donc JAMAIS
   partir au créneau suivant celui qu'on vient d'entendre — alors que c'est la
   cadence normale du FT8 (15 s par échange). En respectant en plus la parité
   d'émission (voir test_parite_des_creneaux_d_emission_preservee), un échange
   coûte 4 créneaux, soit 60 s au lieu de 15 s.

   Ce n'est PAS un défaut du séquenceur : c'est une conséquence directe du
   pipeline de décodage existant, qui attend la fenêtre de 15 s COMPLÈTE puis
   700 ms de plus. WSJT-X n'a pas ce problème parce qu'une trame FT8 ne dure
   que 12,64 s des 15 s : le décodage peut commencer 2,36 s AVANT la frontière
   suivante. Rendre au séquenceur la cadence normale suppose de décoder plus
   tôt (côté extraireFenetre/verifierCycle), pas de modifier la machine à
   états. Décision produit, hors périmètre de l'étape 2 — mais à trancher
   avant de promettre un « séquenceur FT8 » à l'utilisateur.

═══════════════════════════════════════════════════════════════════════════════
SÉQUENCE FT8 STANDARD ATTENDUE DE LA MACHINE
═══════════════════════════════════════════════════════════════════════════════

  Tx1  <cible> <moi> <grille>
  Tx2  <cible> <moi> <report>     quand on reçoit sa GRILLE
  Tx3  <cible> <moi> R<report>    quand on reçoit son report NU
  Tx4  <cible> <moi> RRR          quand on reçoit son R<report>
  Tx5  <cible> <moi> 73           quand on reçoit RRR ou RR73
  Réception d'un 73 : QSO terminé, ne rien réémettre.

SOURCE : WSJT-X User Guide (Taylor K1JT, Franke K9AN, Somerville G4WJS),
chapitre « Basic Operating Tutorial », exemple de QSO standard entre K1ABC et
W9XYZ ; le même enchaînement figure dans l'article QEX 2020 cité plus haut.
VALEUR À SOURCER : le numéro de section exact varie d'une version à l'autre du
manuel — ne figer aucun numéro de section dans un commentaire.

Les deux rôles sont couverts : quand NOUS appelons (réponse à un CQ), la
séquence réellement jouée est Tx1 → (son report) → Tx3 → (son RRR) → Tx5 ;
Tx2 ne sert que dans l'autre rôle, quand c'est ELLE qui nous appelle en
annonçant sa grille (test_role_appele_repond_par_un_report_a_une_grille).

Format des reports : entier signé sur deux chiffres, « -07 », « -13 », « +03 »
— la forme utilisée par WSJT-X dans les messages standards.

PIÈGE DÉJÀ RENCONTRÉ, VÉRIFIÉ ICI : « RR73 » est AUSSI un locator Maidenhead
syntaxiquement valide (RR = champ, 73 = carré) — /^[A-R]{2}[0-9]{2}$/ l'accepte,
et c'est exactement la regex de locator de la page (RE_GRID, logx_ft8.html:479).
Les jetons de PROTOCOLE doivent donc être testés AVANT toute regex de locator.
Le banc lui-même respecte cette règle dans son correspondant simulé — sans quoi
il aurait reproduit le bug qu'il est censé interdire.

═══════════════════════════════════════════════════════════════════════════════
CONTRAT ATTENDU DE L'ÉTAPE 2
═══════════════════════════════════════════════════════════════════════════════

La machine doit être écrite dans logx_ft8.html à l'intérieur d'une région
délimitée par deux sentinelles EXACTES, chacune seule sur sa ligne :

    // ═══ SEQ:DEBUT ═══
    ...
    // ═══ SEQ:FIN ═══

Pourquoi une région et pas une extraction fonction par fonction : le séquenceur
est un ENSEMBLE (état + décision + construction de message + arrêts) dont les
morceaux se lisent les uns les autres. Extraire les fonctions une à une (motif
de test_ft8_surete_emission.py) obligerait le banc à connaître leur liste
exacte, donc à casser au moindre découpage interne — alors que ce qu'il faut
figer, c'est le COMPORTEMENT, pas le découpage.

La région doit définir, à son niveau supérieur :

  seqNiveau                       'manuel' (DÉFAUT) | 'assiste' | 'sequenceur'
  seq                             null, ou l'état de séquence :
                                    {cible, etape, relances, maxRelances,
                                     debutMs, slotEmis, grille, rstRecu,
                                     rstEnvoye, jeton}
  seqDemarrer(cible, infos)       infos : {grille, snr, maxRelances}
  seqExaminerCreneau(msgs, slot)  msgs : [{text, snr, freqHz}, ...]
  seqArreter(raison)
  seqCibleDepuisDecodage(text)    '' si ce message n'est pas appelable
  estIndicatif(jeton)

DEUX CONTRAINTES DE CONCEPTION TROUVÉES EN VALIDANT CE BANC contre une machine
de référence — elles ne sautent pas aux yeux à la lecture du brief :

  1. `slotEmis` EN SCALAIRE NE SUFFIT PAS. L'émission suivante est programmée à
     X+15700 (examen du créneau X), alors que le créneau X+15000 que nous
     occupons ne sera examiné qu'à X+30700 : à cet instant, un scalaire unique
     a déjà été écrasé par le créneau suivant, et le créneau que nous occupions
     est compté comme un silence de la cible. Garder l'ENSEMBLE des créneaux
     occupés récemment (trois ou quatre suffisent, purgés au fil de l'eau).

     RECTIFICATION (revue adversariale du 18/08/2026). Cet en-tête affirmait
     que test_creneau_occupe_par_notre_emission_ne_compte_pas_de_relance tombe
     si on l'oublie. C'EST FAUX à la cadence actuelle, et vérifié par mutation :
     remplacer l'ensemble par le scalaire (`seq.slotEmis === slotExamine`)
     laisse les tests verts. La raison est que l'écrasement du scalaire arrive
     TOUJOURS après l'examen du créneau qu'il désignait, tant qu'un échange
     coûte 4 créneaux.
     L'ensemble reste donc une MARGE DE SÛRETÉ en prévision d'un décodage plus
     précoce (voir le § « conséquence dérangeante »), pas une propriété testée
     aujourd'hui. Le jour où l'on décodera plus tôt, le scalaire redeviendra
     faux — et il n'y aura toujours aucun test pour le dire. Une affirmation
     vérifiable et fausse dans la documentation d'un banc est exactement le
     mode d'échec des deux tentatives précédentes : on la corrige plutôt que
     de la laisser rassurer.

  2. PROGRAMMER AU PLUS TARD, ET REVÉRIFIER JUSTE AVANT. Appeler envoyerMessage
     dès la décision met la trame en attente 14 s à l'avance, sous la seule
     garde du jeton. Décocher « Activer l'émission », arrêter l'écoute ou
     revenir en manuel pendant cette attente ne coupe alors rien : la trame
     part, et le séquenceur ne s'en aperçoit qu'au créneau suivant — 700 ms de
     FT8 tronqué sont déjà passés sur l'air. Déclencher l'appel ~2 s avant le
     créneau visé, précédé d'une revérification complète des conditions, ferme
     la quasi-totalité de la fenêtre ; la revérification de txArmed APRÈS
     l'attente, dans envoyerMessage lui-même, ferme le reste.

Le banc installe autour d'elle une version instrumentée de ce que la page
fournit déjà (voir _JS_SOCLE) :
  myCall, myGrid, txArmed, rxActif,
  envoyerMessage(texte), annulerEmissionsProgrammees(), generationTx,
  offrirLogQso(call, infos), confirmerLogQso(),
  gridVersLatLon(), distanceKm(), extraireStation()  ← EXTRAITES DU VRAI FICHIER
  document.getElementById(...)

TROIS ÉCARTS ENTRE LE BRIEF ET LE FICHIER RÉEL, constatés en LISANT le source
(ce ne sont pas des hypothèses — grep à l'appui) :

  a) annulerEmissionsProgrammees() et le jeton generationTx N'EXISTENT PAS
     dans logx_ft8.html aujourd'hui : zéro occurrence. Ils sont partis avec le
     séquenceur retiré. envoyerMessage() attend son créneau (ligne 1590) puis
     enchaîne DIRECTEMENT sur le PTT, sans aucune revérification : à ce jour
     rien ne peut annuler une émission déjà programmée — ni Échap, ni STOP.
     Le banc code la sémantique attendue ;
     test_jeton_de_generation_existe_dans_envoyer_message échoue tant que la
     page ne l'a pas, pour que les tests d'arrêt ne passent pas sur une fiction.

  b) envoyerMessage() ne prend AUCUN argument : il lit
     document.getElementById('txText').value (ligne 1571). Or le séquenceur ne
     doit JAMAIS émettre le contenu du champ de saisie — c'est par là qu'un
     clic simple pendant une séquence faisait partir n'importe quoi, et qu'un
     double-clic sur un message entre TIERS l'émettait VERBATIM, signé de
     l'indicatif d'autrui. Contrat retenu : envoyerMessage(texte) accepte un
     texte EXPLICITE et retombe sur le champ quand l'argument est absent (le
     chemin manuel ne change pas d'un iota).

  c) offrirLogQso(call) ne prend que l'indicatif (ligne 1657), et
     confirmerLogQso() (ligne 1666) écrit rst_sent:'', rst_rcvd:'', locator:'',
     dist:0 — des champs VIDES. Le « log automatique et COMPLET » exigé suppose
     offrirLogQso(call, infos) avec les reports réellement échangés, la grille
     et la distance.

═══════════════════════════════════════════════════════════════════════════════
CE QUE CE BANC NE PEUT PAS COUVRIR — à lire avant de s'y fier
═══════════════════════════════════════════════════════════════════════════════

  - Rien de RADIO : ni PTT réel, ni audio, ni encodage FT8. envoyerMessage() est
    SIMULÉ ici. La vraie chaîne PTT/audio est couverte, elle, par
    concours/tests/test_ft8_surete_emission.py, qui exécute le code réel.
  - Rien de DÉCODAGE : les messages entrants viennent du scénario. Un séquenceur
    parfait sur un décodeur défaillant reste muet, et ce banc ne le verra pas.
  - Rien de VISUEL : le DOM est un mannequin. Un bouton STOP SÉQUENCE
    correctement câblé côté machine mais invisible ou inatteignable à l'écran
    passerait tous ces tests. Vérification navigateur obligatoire en plus.
  - L'horloge est PARFAITE : ni dérive du PC, ni gigue du timer 250 ms au-delà
    des trois phases rejouées, ni onglet mis en veille par le navigateur, ni
    resynchronisation du tampon audio (derivesCumulees).
  - Le test du bloc <script> entier détecte une zone morte temporelle (TDZ) et
    une erreur de syntaxe. Il ne détecte PAS une faute de logique, ni une erreur
    qui ne survient que sur une interaction utilisateur.
  - La concurrence réelle du navigateur (rAF, ScriptProcessorNode, réseau) est
    absente : le banc sérialise tout. Une course entre le pipeline audio et le
    séquenceur ne serait pas vue ici.
  - Aucune vérification que le séquenceur est ATTEIGNABLE et compréhensible
    dans l'interface (choix du niveau, plafond de relances, bouton d'arrêt) —
    ce qui reste, sur ce logiciel, le critère numéro un.
"""
import json
import os
import re

import pytest

py_mini_racer = pytest.importorskip('py_mini_racer')

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FT8_HTML = os.path.join(CONCOURS, 'logx_ft8.html')
FT8_CODEC = os.path.join(CONCOURS, 'logx_ft8_codec.js')

SLOT_MS = 15000
# 79 symboles × 0,160 s. Chiffre RECALCULÉ depuis le codec du dépôt par
# test_duree_trame_conforme_au_codec_du_depot — pas une constante « connue ».
DUREE_TRAME_MS = 12640

SENTINELLE_DEBUT = '// ═══ SEQ:DEBUT ═══'
SENTINELLE_FIN = '// ═══ SEQ:FIN ═══'

MOI = 'F4GLD'
MA_GRILLE = 'JN15'
CIBLE = 'F4ABC'
GRILLE_CIBLE = 'JN18'
TIERS = 'DL1XYZ'
QUATRIEME = 'SP9QQQ'

# Reports du scénario nominal, choisis DIFFÉRENTS l'un de l'autre : un log qui
# recopierait le même report des deux côtés passerait inaperçu s'ils étaient
# égaux.
SNR_ELLE_CHEZ_NOUS = -13      # ce que NOUS lui envoyons  -> rst_sent '-13'
SNR_NOUS_CHEZ_ELLE = -7       # ce qu'ELLE nous envoie    -> rst_rcvd '-07'


def _lire(chemin):
    with open(chemin, encoding='utf-8') as f:
        return f.read()


def _sans_commentaires(js):
    """Retire les commentaires JS AVANT toute analyse du code.

    Défaut confirmé par la revue adversariale du 18/08/2026, et reproduit :
    test_jeton_de_generation_existe_dans_envoyer_message cherchait
    « generationTx » dans le texte BRUT de la fonction. Le pavé de commentaire
    qui EXPLIQUE la revérification cite les deux identifiants et se trouve, lui
    aussi, après l'attente du créneau. On pouvait donc remplacer la seule ligne
    de contrôle réelle — celle qui empêche une trame annulée de partir — par
    « if(false) » sans qu'aucun des 47 tests ne bouge.

    Un test dont la mission est d'interdire une fiction ne doit jamais pouvoir
    être satisfait par de la prose.

    Le `(?<!:)` évite d'amputer « https:// » à l'intérieur d'une chaîne.
    """
    js = re.sub(r'/\*[\s\S]*?\*/', '', js)
    return re.sub(r'(?<!:)//[^\n]*', '', js)


def _extraire_region_sequenceur(src):
    """Région délimitée par les sentinelles. Message d'échec explicite : tant
    que l'étape 2 n'a pas écrit la machine, tous les tests de comportement
    doivent tomber ICI avec la marche à suivre — pas sur une erreur JS obscure
    trente lignes plus loin."""
    i = src.find(SENTINELLE_DEBUT)
    j = src.find(SENTINELLE_FIN)
    if i < 0 or j < 0 or j <= i:
        raise AssertionError(
            "ÉTAPE 2 NON FAITE — région du séquenceur absente de logx_ft8.html.\n"
            "Encadrer la machine à états par ces deux lignes EXACTES :\n"
            f'    {SENTINELLE_DEBUT}\n    ...\n    {SENTINELLE_FIN}\n'
            "Contrat attendu : voir l'en-tête de ce fichier.")
    return src[i + len(SENTINELLE_DEBUT):j]


def _extraire_fonction(src, nom):
    """Extraction par comptage d'accolades — même motif que
    test_ft8_surete_emission.py. Sert ici à réutiliser le VRAI code de géodésie
    et d'extraction de station plutôt que d'en recopier une version dans le
    banc : une copie divergerait, et le banc validerait alors une logique que
    la page n'exécute pas."""
    debut = -1
    for motif in ('function ' + nom, 'window.' + nom + ' ='):
        debut = src.find(motif)
        if debut >= 0:
            break
    assert debut >= 0, f'fonction {nom} introuvable dans logx_ft8.html'
    debut = src.rfind('\n', 0, debut) + 1
    prof, i = 0, src.index('{', debut)
    while True:
        if src[i] == '{':
            prof += 1
        elif src[i] == '}':
            prof -= 1
            if prof == 0:
                return src[debut:i + 1]
        i += 1


# ═══════════════════════════════════════════════════════════════════════════
# SOCLE JAVASCRIPT DU BANC
#
# Horloge virtuelle + ordonnanceur à événements + simulation FIDÈLE de
# envoyerMessage() + correspondant réactif. Aucune dépendance au temps réel :
# Date.now() rend NOW, et NOW n'avance QUE quand l'ordonnanceur tire un
# événement.
# ═══════════════════════════════════════════════════════════════════════════
_JS_SOCLE = r"""
var NOW = 0;
Date.now = function(){ return NOW; };

// ─── File d'événements (tâches macro, au sens du navigateur) ───────────────
// `ord` départage deux événements dus au même instant : premier programmé,
// premier servi. Sans lui, un scénario dépendrait de l'ordre de tri, donc ne
// serait pas reproductible.
var __evts = [], __idSeq = 1, __ordre = 0;
function setTimeout(fn, ms){
  var id = __idSeq++;
  __evts.push({due: NOW + (ms || 0), ord: __ordre++, fn: fn, id: id});
  return id;
}
function clearTimeout(id){
  for(var i = 0; i < __evts.length; i++){
    if(__evts[i].id === id){ __evts.splice(i, 1); return; }
  }
}
var setInterval = setTimeout;          // le banc n'utilise pas d'intervalle
function clearInterval(id){ clearTimeout(id); }

// Tire AU PLUS UN événement, et seulement s'il est dû avant `limite`.
// Appelé une fois par ctx.eval() côté Python : voir _Banc.avancer().
function __tirerUn(limite){
  if(!__evts.length) return false;
  __evts.sort(function(a, b){ return (a.due - b.due) || (a.ord - b.ord); });
  if(__evts[0].due > limite) return false;
  var e = __evts.shift();
  NOW = e.due;
  e.fn();
  return true;
}

// ─── DOM mannequin ────────────────────────────────────────────────────────
function __El(id){
  this.id = id; this.textContent = ''; this.innerHTML = ''; this.value = '';
  this.checked = false; this.disabled = false; this.className = '';
  this.title = ''; this.dataset = {}; this.style = {};
  this.children = []; this.firstChild = null;
  var s = {};
  this.classList = {
    add: function(c){ s[c] = true; },
    remove: function(c){ delete s[c]; },
    toggle: function(c, v){ if(v === undefined) v = !s[c]; if(v) s[c] = true; else delete s[c]; },
    contains: function(c){ return !!s[c]; }
  };
}
__El.prototype.appendChild = function(n){ this.children.push(n); return n; };
__El.prototype.insertBefore = function(n){ this.children.unshift(n); return n; };
__El.prototype.removeChild = function(n){ return n; };
__El.prototype.append = function(){ return this; };
__El.prototype.querySelectorAll = function(){ return []; };
__El.prototype.addEventListener = function(){};
__El.prototype.getBoundingClientRect = function(){ return {width: 300, height: 200}; };

var __els = {};
var document = {
  getElementById: function(id){ if(!__els[id]) __els[id] = new __El(id); return __els[id]; },
  createElement: function(t){ return new __El('<' + t + '>'); },
  addEventListener: function(){},
  querySelectorAll: function(){ return []; },
  body: new __El('body')
};
var window = {addEventListener: function(){}};

// ─── Identité station et armements ────────────────────────────────────────
var myCall = '__MOI__';
var myGrid = '__MA_GRILLE__';
var txArmed = true;      // case « Activer l'émission » — logx_ft8.html:1350
var rxActif = true;      // écoute en cours            — logx_ft8.html:659

// Format de report FT8 : entier signé sur deux chiffres (-07, -13, +03).
function __fmtRst(snr){
  var n = Math.round(Number(snr) || 0);
  var s = Math.abs(n) < 10 ? '0' + Math.abs(n) : String(Math.abs(n));
  return (n < 0 ? '-' : '+') + s;
}

// ─── Émission simulée — calendrier COPIÉ de logx_ft8.html:1585-1590 ───────
//
// Ce n'est pas « une émission instantanée avec un délai décoratif » : la trame
// occupe RÉELLEMENT [prochain, prochain+12640[ dans le temps virtuel, et c'est
// ce recouvrement qui rend visible le défaut que deux implémentations
// successives n'ont pas vu.
//
// generationTx : jeton d'annulation, capturé AVANT l'attente du créneau et
// revérifié APRÈS. Il EXISTE désormais dans logx_ft8.html — il en a été
// extrait et fusionné seul (correctif de sûreté d'émission), puis remonté
// ici. L'écart (a) de l'en-tête est donc résorbé : le banc ne code plus une
// sémantique à venir, il reproduit celle du fichier.
var generationTx = 0;
var __emissions = [];    // TOUTES les demandes, annulées comprises
var __enVol = null;

// Dernier motif de refus du PTT. Vit HORS de la région SEQ dans le fichier
// réel (c'est de l'état d'émission, pas de la machine à états), donc le socle
// doit le fournir : le séquenceur le lit pour choisir entre la raison générique
// 'emission-refusee' et la raison dédiée 'pas-de-pilotage-radio'. Sans lui,
// la région levait une ReferenceError et n'arrêtait plus rien.
var dernierRefusPtt = '';

function annulerEmissionsProgrammees(){
  generationTx++;
  if(__enVol){ __enVol.annulee = true; __enVol.finMs = NOW; __enVol = null; }
}

// REND `true` si une trame est RÉELLEMENT partie, `false` sinon — contrat de
// la vraie fonction depuis la correction du constat « une émission jamais
// partie était comptée comme émise ». Le banc DOIT rendre la même chose : un
// socle qui rend toujours undefined ferait croire au séquenceur que rien ne
// part jamais, et ce banc validerait alors une machine qui s'arrête tout le
// temps.
function envoyerMessage(texte){
  // logx_ft8.html — rien ne part tant que l'émission n'est pas armée.
  if(!txArmed) return Promise.resolve(false);
  // Une seule source d'émission à la fois : pendant une séquence, une demande
  // SANS texte explicite vient d'un geste manuel et doublerait l'émission.
  if(seq && texte === undefined) return Promise.resolve(false);
  // Contrat étape 2 (écart (b)) : texte EXPLICITE si fourni, repli sur le
  // champ de saisie pour le chemin MANUEL seulement.
  var brut = (texte !== undefined && texte !== null)
           ? texte : document.getElementById('txText').value;
  var text = String(brut).trim().toUpperCase();
  if(!text) return Promise.resolve(false);

  var maGeneration = generationTx;
  var now = Date.now();
  var prochain = Math.ceil(now / 15000) * 15000;
  if(prochain - now < 1000) prochain += 15000;

  var em = {texte: text, slot: prochain, programmeMs: now,
            debutMs: null, finMs: null, annulee: false};
  __emissions.push(em);

  return new Promise(function(res){
    setTimeout(function(){
      // LES DEUX revérifications après attente. Sans elles, un STOP ou un
      // décochage de « Activer l'émission » demandé pendant l'attente du
      // créneau laisse partir la trame quand même — constaté en validant ce
      // banc : 700 ms de FT8 tronqué sont bel et bien passés sur l'air avant
      // que le séquenceur ne s'en aperçoive au créneau suivant.
      if(maGeneration !== generationTx || !txArmed){ em.annulee = true; return res(false); }
      em.debutMs = NOW;
      __enVol = em;
      setTimeout(function(){
        if(em.annulee) return res(false);
        em.finMs = NOW; __enVol = null;
        // ─── QUEUE DE LA VRAIE FONCTION ─────────────────────────────────
        // Elle manquait au socle, et c'est ce trou qui a rendu TROIS
        // constats invisibles : la vraie envoyerMessage ouvre le bandeau
        // « QSO complété — l'ajouter au log ? » dès qu'un message se termine
        // par 73/RRR/RR73, SANS report. Sur le chemin du séquenceur, cela
        // proposait une fiche VIDE en plein QSO, et une fiche validée par
        // erreur faisait ensuite rejeter le log complet en 409.
        // La condition reproduite ici est celle du fichier : chemin MANUEL
        // seulement (texte non fourni, aucune séquence en cours).
        if(texte === undefined && !seq){
          var parts = text.split(' ');
          if(parts[2] === '73' || parts[2] === 'RRR' || parts[2] === 'RR73'){
            offrirLogQso(parts[0]);
          }
        }
        res(true);
      }, __DUREE_TRAME_MS__);
    }, prochain - Date.now());
  });
}

// ─── Neutralisation du couple champ + bouton pendant une séquence ─────────
// Vit HORS de la région SEQ dans le fichier réel (c'est du câblage d'écran,
// pas de la machine à états), donc le socle doit le fournir. On MÉMORISE ce
// qu'il décide, pour que le banc puisse vérifier qu'un clic manuel ne peut pas
// doubler l'émission du séquenceur — le bouton restait cliquable pendant toute
// la séquence, et deux formes d'onde FT8 partaient alors sur la même
// fréquence, dans le même créneau.
// Reproduit la SEULE décision de onArmChange qui concerne la séquence — la
// fonction elle-même vit hors de la région SEQ. Le test structurel
// test_decocher_l_armement_arrete_et_nomme_la_case tient l'autre bout : il
// vérifie que la page fait bien ce geste-là, pour que ce mannequin ne puisse
// pas valider une sémantique que le produit n'a pas.
function onArmChangeSimule(){
  if(!txArmed){ seqArreter('emission-desarmee'); annulerEmissionsProgrammees(); }
  majBoutonEnvoyer();
}

function majBoutonEnvoyer(){
  var b = document.getElementById('sendBtn');
  b.disabled = !txArmed || !!seq;
  var champ = document.getElementById('txText');
  champ.readOnly = !!seq;
}

// ─── Log — offrirLogQso(call, infos) puis confirmerLogQso() ───────────────
// Signature ÉLARGIE par rapport au fichier réel (écart (c) de l'en-tête) : le
// log « complet » exige les reports échangés, la grille et la distance.
var __offreEnAttente = null;
var __journal = [];
function offrirLogQso(call, infos){
  __offreEnAttente = {call: call, infos: infos || null, tMs: NOW};
}
function confirmerLogQso(){
  if(!__offreEnAttente) return Promise.resolve();
  __journal.push(__offreEnAttente);
  __offreEnAttente = null;
  return Promise.resolve();
}
function annulerLogQso(){ __offreEnAttente = null; }

// ─── CORRESPONDANT RÉACTIF ────────────────────────────────────────────────
//
// Une station simulée qui répond à ce qu'elle ENTEND, comme une vraie. C'est
// ce qui permet aux tests de ne figer AUCUNE cadence : quelle que soit la
// vitesse à laquelle le séquenceur répond, elle répond au créneau suivant le
// nôtre, et le QSO doit aboutir.
//
// __corr = {call, grille, snrChezNous, final, muette}
//   snrChezNous : SNR auquel NOUS l'entendons -> c'est le report que NOUS
//                 devons lui envoyer. Le report qu'ELLE nous envoie est
//                 __corr.sonReport.
var __corr = null;

function __messageCorrespondant(slot){
  if(!__corr || __corr.muette) return null;
  // PARITÉ. Une station FT8 émet toujours sur la même moitié du cycle de 30 s
  // (case « Tx even/1st » de WSJT-X) : c'est ce qui garantit qu'elle ÉCOUTE
  // pendant que son correspondant émet.
  //
  // Le correspondant du banc répondait au créneau suivant le nôtre QUEL QUE
  // SOIT ce créneau — une station qui écoute et parle en même temps. C'est ce
  // qui a rendu invisible le défaut le plus grave du séquenceur : émettre
  // dans les créneaux de la station appelée, une fois sur deux, au hasard de
  // l'instant du double-clic. Avec `parite` renseignée, elle n'émet QUE dans
  // ses créneaux ; si nous émettons dans les mêmes, elle ne nous entend
  // jamais et nous ne l'entendons jamais — et le QSO n'a simplement pas lieu.
  if(__corr.parite === 0 || __corr.parite === 1){
    if((Math.floor(slot / 15000) % 2) !== __corr.parite) return null;
  }
  // Qu'avons-nous émis dans le créneau précédent ? Elle ne peut répondre
  // qu'à ça — elle n'entend rien pendant qu'elle émet, exactement comme nous.
  var precedent = null;
  for(var i = 0; i < __emissions.length; i++){
    var e = __emissions[i];
    if(e.slot === slot - 15000 && e.debutMs !== null && !e.annulee) precedent = e;
  }
  if(!precedent) return null;                       // rien entendu : silence
  var p = precedent.texte.split(' ');
  if(p[0] !== __corr.call) return null;             // ce n'était pas pour elle
  var extra = p.slice(2).join(' ');
  var tete = myCall + ' ' + __corr.call + ' ';

  // JETONS DE PROTOCOLE D'ABORD — « RR73 » satisfait la regex de locator. Le
  // banc s'applique à lui-même la règle qu'il impose au séquenceur.
  if(extra === 'RRR') return tete + '73';
  if(extra === 'RR73' || extra === '73') return null;     // QSO fini de son côté
  if(/^R[+-]\d{1,2}$/.test(extra)) return tete + (__corr.final || 'RRR');
  if(/^[+-]\d{1,2}$/.test(extra)) return tete + 'R' + __fmtRst(__corr.snrChezNous);
  if(/^[A-R]{2}[0-9]{2}$/.test(extra)) return tete + __fmtRst(__corr.sonReport);
  return null;
}

// ─── Ordonnanceur d'examens : reproduit verifierCycle (1154-1192) ─────────
// Un examen par créneau, à frontière+phase, avec le NUMÉRO du créneau TERMINÉ.
var __scenario = {};     // {numeroDeCreneau: [messages]}  — cas adversariaux
var __phaseExamen = 700;
var __examens = [];
var __erreursExamen = [];
var __dernierPlanifie = -1;

function __planifierExamens(jusqua){
  var t = (__dernierPlanifie < 0)
        ? Math.floor(NOW / 15000) * 15000 + 15000 + __phaseExamen
        : __dernierPlanifie + 15000;
  for(; t <= jusqua; t += 15000){
    if(t <= NOW) continue;
    __dernierPlanifie = t;
    (function(instant){
      setTimeout(function(){
        // FIDÉLITÉ : verifierCycle() commence par `if(!rxActif) return;`, et
        // arreterRx() supprime en plus le timer. Sans cette ligne, le banc
        // appelait seqExaminerCreneau même écoute coupée — donc il validait
        // la garde `if(!rxActif) seqArreter(...)` qui s'y trouve, ALORS QUE
        // LA PAGE NE PEUT JAMAIS L'ATTEINDRE. Un banc qui teste du code mort
        // donne une assurance strictement négative.
        if(!rxActif) return;
        var slotTermine = Math.floor(NOW / 15000) * 15000 - 15000;
        var bruts = (__scenario[slotTermine] || []).slice();
        var duCorr = __messageCorrespondant(slotTermine);
        if(duCorr) bruts.push({text: duCorr, snr: __corr.snrChezNous});
        var msgs = bruts.map(function(m){
          return (typeof m === 'string') ? {text: m} : m;
        });
        __examens.push({slot: slotTermine, tMs: NOW, msgs: msgs.map(function(m){ return m.text; })});
        try{
          seqExaminerCreneau(msgs, slotTermine);
        }catch(err){
          __erreursExamen.push('slot ' + slotTermine + ' : ' + String((err && err.message) || err));
        }
      }, instant - NOW);
    })(t);
  }
}

// ─── Lecture d'état : TOUJOURS relue depuis V8 ────────────────────────────
// Piège documenté en mémoire (16/08/2026) : un miroir Python de l'état JS
// diverge dès la première mutation côté V8. Rien ne franchit la frontière
// autrement que par JSON.stringify.
function __etat(){
  return {
    now: NOW,
    seq: (typeof seq === 'undefined') ? null : seq,
    niveau: (typeof seqNiveau === 'undefined') ? null : seqNiveau,
    generationTx: generationTx,
    txArmed: txArmed, rxActif: rxActif,
    emissions: __emissions,
    demarrees: __emissions.filter(function(e){ return e.debutMs !== null; }),
    parties: __emissions.filter(function(e){ return e.debutMs !== null && !e.annulee; }),
    journal: __journal,
    offreEnAttente: __offreEnAttente,
    // LE MESSAGE RÉELLEMENT AFFICHÉ. Sans lui, aucun test ne pouvait vérifier
    // POURQUOI une séquence s'arrête : les six gestes d'arrêt étaient
    // interchangeables aux yeux du banc, et les trois raisons distinctes
    // ajoutées pour nommer la cause n'étaient contraintes par rien.
    seqEtat: document.getElementById('seqEtat').textContent,
    envoyerDesactive: !!document.getElementById('sendBtn').disabled,
    champVerrouille: !!document.getElementById('txText').readOnly,
    examens: __examens,
    erreurs: __erreursExamen,
    champTx: document.getElementById('txText').value
  };
}
"""


class _Banc:
    """Un banc = un contexte V8 + une horloge virtuelle + un scénario."""

    def __init__(self, niveau='sequenceur', phase=700, scenario=None,
                 correspondant=None):
        src = _lire(FT8_HTML)
        self.ctx = py_mini_racer.MiniRacer()

        socle = (_JS_SOCLE
                 .replace('__MOI__', MOI)
                 .replace('__MA_GRILLE__', MA_GRILLE)
                 .replace('__DUREE_TRAME_MS__', str(DUREE_TRAME_MS)))
        self.ctx.eval(socle)

        # Vrai code du dépôt, pas une copie : géodésie (distance du log) et
        # extraction de station. Si l'un des trois change dans la page, le banc
        # change avec — c'est voulu.
        for nom in ('gridVersLatLon', 'distanceKm', 'extraireStation'):
            self.ctx.eval(_extraire_fonction(src, nom))

        # La machine à états. Lève une AssertionError parlante si absente.
        self.ctx.eval(_extraire_region_sequenceur(src))

        self.ctx.eval('__phaseExamen = %d;' % phase)
        self.ctx.eval('seqNiveau = %s;' % json.dumps(niveau))
        if scenario:
            self.charger_scenario(scenario)
        if correspondant:
            self.ctx.eval('__corr = %s;' % json.dumps(correspondant))

    # ── scénario ───────────────────────────────────────────────────────────
    def charger_scenario(self, scenario):
        """{numéro de créneau (str) -> liste de messages}. Un message est une
        chaîne ou {text, snr, freqHz}. Réservé aux cas adversariaux ; pour un
        QSO, utiliser un correspondant réactif."""
        self.ctx.eval('__scenario = %s;' % json.dumps(scenario))

    def js(self, code):
        return self.ctx.eval(code)

    def etat(self):
        return json.loads(self.ctx.eval('JSON.stringify(__etat())'))

    def demarrer(self, cible=CIBLE, **infos):
        infos.setdefault('grille', GRILLE_CIBLE)
        infos.setdefault('snr', SNR_ELLE_CHEZ_NOUS)
        return self.ctx.eval('seqDemarrer(%s, %s)'
                             % (json.dumps(cible), json.dumps(infos)))

    # ── horloge ────────────────────────────────────────────────────────────
    def avancer(self, jusqua_ms):
        """Avance le temps virtuel jusqu'à `jusqua_ms`, UN ÉVÉNEMENT PAR APPEL
        À ctx.eval().

        Ce détail n'est pas cosmétique. Dans le V8 de py_mini_racer, la file de
        MICROtâches (continuations de `await`) n'est vidée qu'à la FIN d'un
        eval — vérifié en séance. Dérouler toute la boucle dans un seul eval
        exécuterait donc toutes les tâches macro AVANT la moindre continuation
        asynchrone : l'inverse du navigateur, et exactement le genre d'écart de
        modèle temporel qui a tué les deux versions précédentes. Un événement
        par eval rétablit l'alternance tâche → microtâches."""
        self.ctx.eval('__planifierExamens(%d);' % jusqua_ms)
        garde = 0
        while self.ctx.eval('__tirerUn(%d)' % jusqua_ms):
            garde += 1
            assert garde < 20000, "boucle d'événements emballée (banc ou machine)"
        self.ctx.eval('NOW = Math.max(NOW, %d);' % jusqua_ms)

    # ── raccourcis de lecture ──────────────────────────────────────────────
    def emissions_parties(self):
        return [e['texte'] for e in self.etat()['parties']]

    def creneaux_emis(self):
        return [e['slot'] for e in self.etat()['parties']]

    def suffixes_emis(self):
        """Ce qui suit « <cible> <moi> » dans chaque message émis."""
        out = []
        for t in self.emissions_parties():
            p = t.split(' ')
            out.append(' '.join(p[2:]) if len(p) > 2 else '')
        return out


def _correspondant(final='RRR', muette=False):
    return {'call': CIBLE, 'grille': GRILLE_CIBLE,
            'snrChezNous': SNR_ELLE_CHEZ_NOUS,
            'sonReport': SNR_NOUS_CHEZ_ELLE,
            'final': final, 'muette': muette}


@pytest.fixture
def banc():
    return _Banc


# ═══════════════════════════════════════════════════════════════════════════
# §1. FIDÉLITÉ — ces trois tests protègent le banc lui-même, et passent déjà
# ═══════════════════════════════════════════════════════════════════════════

def test_calendrier_du_banc_fidele_au_source():
    """Le banc recopie trois règles de calendrier de logx_ft8.html. Si l'une
    change dans la page sans changer ici, le banc devient un mensonge : il
    validerait une chronologie que la page n'exécute pas. C'est précisément
    ainsi qu'un harnais devient structurellement aveugle."""
    src = _lire(FT8_HTML)
    envoyer = _extraire_fonction(src, 'envoyerMessage')

    assert re.search(r'Math\.ceil\(\s*now\s*/\s*15000\s*\)\s*\*\s*15000', envoyer), \
        'logx_ft8.html:1586 — la programmation sur le prochain multiple de 15 s a changé'
    assert re.search(r'prochain\s*-\s*now\s*<\s*1000', envoyer), \
        'logx_ft8.html:1587 — la marge de 1000 ms qui décale au créneau suivant a changé'
    assert re.search(r'setTimeout\(\s*resolve\s*,\s*prochain\s*-\s*Date\.now\(\)\s*\)', envoyer), \
        "logx_ft8.html:1590 — l'attente jusqu'au créneau a changé de forme"

    cycle = _extraire_fonction(src, 'verifierCycle')
    assert re.search(r'Math\.floor\(\s*now\s*/\s*15000\s*\)\s*\*\s*15000', cycle), \
        'logx_ft8.html:1157 — le calcul du créneau courant a changé'
    assert 'slotCourant - 15000' in cycle, \
        "logx_ft8.html:1158 — slotTermine n'est plus le créneau précédent"
    assert re.search(r'\(\s*now\s*-\s*slotCourant\s*\)\s*>=\s*700', cycle), (
        "logx_ft8.html:1159 — le seuil de 700 ms avant examen a changé ; si c'est "
        "volontaire (voir le § « conséquence dérangeante » de l'en-tête), mettre "
        'le banc à jour AVANT de relire le moindre résultat')
    assert 'setInterval(verifierCycle, 250)' in src, \
        "logx_ft8.html:1314 — la cadence de 250 ms du timer d'examen a changé"


def test_duree_trame_conforme_au_codec_du_depot():
    """12,64 s n'est pas une constante « connue » : elle est RECALCULÉE depuis
    les deux constantes du codec du dépôt (79 symboles × 0,160 s), elles-mêmes
    sourcées Franke/Somerville/Taylor, QEX juillet-août 2020."""
    codec = _lire(FT8_CODEC)
    m_per = re.search(r'FT8_SYMBOL_PERIOD\s*=\s*([0-9.]+)', codec)
    m_nn = re.search(r'FT8_NN\s*=\s*(\d+)', codec)
    assert m_per and m_nn, 'constantes FT8_SYMBOL_PERIOD / FT8_NN introuvables'
    assert float(m_per.group(1)) == 0.160
    assert int(m_nn.group(1)) == 79
    assert round(float(m_per.group(1)) * int(m_nn.group(1)) * 1000) == DUREE_TRAME_MS
    # Et la trame doit tenir dans le créneau : sans quoi tout le raisonnement
    # de recouvrement de l'en-tête (§4) s'effondre.
    assert DUREE_TRAME_MS < SLOT_MS


def test_bloc_script_entier_s_evalue_jusqu_au_bout():
    """Évalue le BLOC <script> ENTIER de logx_ft8.html, pas des fonctions
    isolées.

    Raison d'être : une zone morte temporelle (TDZ) a déjà tué toute la page
    sans qu'aucun test ne la voie. Une TDZ — un `let`/`const` lu avant sa ligne
    de déclaration — est syntaxiquement PARFAITE ; elle ne se manifeste qu'à
    l'exécution, et elle interrompt le script à cet endroit, donc tout ce qui
    suit n'est jamais défini et la page entière est morte. Extraire les
    fonctions une par une ne peut structurellement pas la révéler, puisque
    chaque extrait est alors évalué dans un ordre que la page n'utilise pas.

    On installe un mannequin de navigateur, on évalue le bloc, puis on vérifie
    que l'exécution a atteint la DERNIÈRE ligne (sentinelle __FIN_BLOC). Toute
    exception en route — TDZ comprise — laisse la sentinelle à false.

    Contre-épreuve faite en écrivant le test : en injectant une vraie TDZ
    (lecture d'un `let` déclaré plus bas depuis le code d'initialisation), la
    sentinelle retombe à false et l'erreur remontée est bien
    « Cannot access ... before initialization ». Le test n'est donc pas vacant."""
    src = _lire(FT8_HTML)
    i = src.index('<script>', src.index('logx_ft8_dsp.js'))
    j = src.index('</script>', i)
    bloc = src[i + len('<script>'):j]

    ctx = py_mini_racer.MiniRacer()
    ctx.eval(_JS_MANNEQUIN_NAVIGATEUR)
    erreur = None
    try:
        ctx.eval(bloc + '\n;globalThis.__FIN_BLOC = true;\n')
    except Exception as e:          # noqa: BLE001 — on veut le message brut
        erreur = str(e).splitlines()[0]

    fin = ctx.eval('!!globalThis.__FIN_BLOC')
    assert erreur is None and fin, (
        "le bloc <script> de logx_ft8.html n'a pas pu être exécuté de bout en "
        "bout dans un navigateur mannequin.\n"
        "Cause la plus probable et la plus grave : une ZONE MORTE TEMPORELLE "
        "(let/const utilisé avant sa déclaration) — elle tue la page entière en "
        "production, sans erreur visible pour l'utilisateur.\n"
        "Autre cause possible : le bloc utilise une API navigateur que le "
        "mannequin ne fournit pas encore — dans ce cas, compléter "
        "_JS_MANNEQUIN_NAVIGATEUR, jamais désactiver ce test.\n"
        "Erreur remontée : %s" % (erreur or 'aucune (exécution interrompue)'))


# Mannequin de navigateur pour le test ci-dessus UNIQUEMENT. Volontairement
# séparé du socle du banc : ici on ne simule rien de temporel, on cherche
# seulement à faire tourner le bloc de bout en bout.
_JS_MANNEQUIN_NAVIGATEUR = r"""
function __El2(){
  this.textContent = ''; this.innerHTML = ''; this.value = ''; this.checked = false;
  this.disabled = false; this.className = ''; this.title = ''; this.dataset = {};
  this.style = {}; this.children = []; this.firstChild = null; this.lastChild = null;
  this.width = 300; this.height = 200;
  var s = {};
  this.classList = {
    add: function(c){ s[c] = true; }, remove: function(c){ delete s[c]; },
    toggle: function(c, v){ if(v === undefined) v = !s[c]; if(v) s[c] = true; else delete s[c]; },
    contains: function(c){ return !!s[c]; }
  };
}
__El2.prototype.appendChild = function(n){ this.children.push(n); this.lastChild = n; if(!this.firstChild) this.firstChild = n; return n; };
__El2.prototype.insertBefore = function(n){ this.children.unshift(n); this.firstChild = n; if(!this.lastChild) this.lastChild = n; return n; };
__El2.prototype.removeChild = function(n){ return n; };
__El2.prototype.append = function(){ return this; };
__El2.prototype.querySelectorAll = function(){ return []; };
__El2.prototype.addEventListener = function(){};
__El2.prototype.removeEventListener = function(){};
__El2.prototype.getBoundingClientRect = function(){ return {width: 300, height: 200, left: 0, top: 0}; };
__El2.prototype.getContext = function(){
  return {
    fillRect: function(){}, clearRect: function(){}, fillText: function(){},
    beginPath: function(){}, moveTo: function(){}, lineTo: function(){},
    stroke: function(){}, fill: function(){}, arc: function(){},
    drawImage: function(){}, putImageData: function(){}, save: function(){},
    restore: function(){}, translate: function(){}, setLineDash: function(){},
    createImageData: function(){ return {data: []}; },
    getImageData: function(){ return {data: []}; }
  };
};
__El2.prototype.focus = function(){};
__El2.prototype.play = function(){};
__El2.prototype.pause = function(){};
__El2.prototype.setSinkId = function(){ return Promise.resolve(); };

var __elements2 = {};
var document = {
  body: new __El2(),
  getElementById: function(id){ if(!__elements2[id]) __elements2[id] = new __El2(); return __elements2[id]; },
  createElement: function(){ return new __El2(); },
  querySelector: function(){ return new __El2(); },
  querySelectorAll: function(){ return []; },
  addEventListener: function(){}, removeEventListener: function(){}
};
var localStorage = {
  _d: {},
  getItem: function(k){ return (k in this._d) ? this._d[k] : null; },
  setItem: function(k, v){ this._d[k] = String(v); },
  removeItem: function(k){ delete this._d[k]; }
};
var location = {protocol: 'http:', href: 'http://127.0.0.1:8080/logx_ft8.html', search: ''};
function setTimeout(){ return 1; }
function clearTimeout(){}
function setInterval(){ return 1; }
function clearInterval(){}
function requestAnimationFrame(){ return 1; }
function cancelAnimationFrame(){}
function fetch(){ return Promise.resolve({ok: false, status: 0, json: function(){ return Promise.resolve({}); }}); }
function Audio(){ return new __El2(); }
var HTMLMediaElement = {prototype: {}};   // setSinkId absent : chemin « sortie par défaut »
var navigator = {
  mediaDevices: {
    getUserMedia: function(){ return Promise.reject(new Error('pas de micro dans le mannequin')); },
    enumerateDevices: function(){ return Promise.resolve([]); }
  },
  sendBeacon: function(){ return true; }
};
function AudioContext(){
  this.sampleRate = 12000; this.destination = {};
  this.createMediaStreamSource = function(){ return {connect: function(){}, disconnect: function(){}}; };
  this.createScriptProcessor = function(){ return {connect: function(){}, disconnect: function(){}}; };
  this.createGain = function(){ return {gain: {value: 0}, connect: function(){}, disconnect: function(){}}; };
  this.createAnalyser = function(){ return {fftSize: 0, frequencyBinCount: 1024, connect: function(){}, disconnect: function(){}, getByteFrequencyData: function(){}}; };
  this.createBuffer = function(){ return {copyToChannel: function(){}}; };
  this.createBufferSource = function(){ return {connect: function(){}, start: function(){}, stop: function(){}}; };
  this.createMediaStreamDestination = function(){ return {stream: {}}; };
  this.close = function(){};
}
var webkitAudioContext = AudioContext;
var window = {
  addEventListener: function(){}, removeEventListener: function(){},
  devicePixelRatio: 1, AudioContext: AudioContext, webkitAudioContext: AudioContext,
  rcT: null
};
// Bibliothèques chargées par <script src> AVANT le bloc testé : on ne rejoue
// pas leur contenu (elles ont leurs propres tests), on se contente d'exister —
// sinon l'appel de la ligne 651 tuerait le bloc pour une raison sans rapport
// avec ce qu'on cherche.
function ft8CreateHashTable(){ return {}; }
function ft8EncodeMessage(){ return null; }
function ft8SynthesizeGfsk(){ return new Float32Array(0); }
function ft8DecodeAudioAll(){ return []; }
function ft8FindSync(){ return null; }
"""


# ═══════════════════════════════════════════════════════════════════════════
# §2. CHRONOLOGIE — le défaut emblématique
# ═══════════════════════════════════════════════════════════════════════════

def test_reponse_pendant_que_nous_emettions_au_creneau_precedent(banc):
    """LE test de non-régression du défaut qui a tué les deux versions.

    Construit en DEUX PASSES pour ne présupposer aucune cadence :

      Passe 1 — correspondant MUET : on observe quels créneaux la machine
        choisit réellement d'occuper. Soit Y le deuxième d'entre eux.
      Passe 2 — la cible répond dans le créneau Y-15000. Son examen tombe donc
        à Y+700, c'est-à-dire 700 ms APRÈS le début de NOTRE trame du créneau Y
        (démonstration du §4 de l'en-tête). Le créneau examiné (Y-15000) n'est
        pourtant PAS celui que nous occupons (Y) : c'était un créneau
        d'ÉCOUTE, et son contenu doit être pris en compte.

    L'ancien code testait « suis-je en train d'émettre MAINTENANT », vrai à
    Y+700, et jetait la réponse. Résultat : le QSO ne pouvait pas aboutir."""
    # ── Passe 1 : découvrir la cadence réelle de la machine ────────────────
    b1 = banc(correspondant=_correspondant(muette=True))
    b1.js('NOW = 2000;')
    b1.demarrer()
    b1.avancer(400000)
    creneaux = b1.creneaux_emis()
    assert len(creneaux) >= 2, (
        'la machine n\'a pas relancé : impossible de construire le cas. '
        'Créneaux émis : %r' % (creneaux,))
    y = creneaux[1]
    slot_ecoute = y - SLOT_MS

    # ── Passe 2 : la réponse tombe précisément dans ce créneau-là ──────────
    # Elle nous envoie son report NU (-07) : la seule réponse correcte est
    # ensuite R<notre report> (Tx3), impossible à confondre avec une relance.
    b2 = banc(scenario={
        str(slot_ecoute): [{'text': f'{MOI} {CIBLE} -07', 'snr': SNR_ELLE_CHEZ_NOUS}],
    })
    b2.js('NOW = 2000;')
    b2.demarrer()
    b2.avancer(400000)

    et = b2.etat()
    assert not et['erreurs'], et['erreurs']
    examines = {e['slot'] for e in et['examens']}
    assert slot_ecoute in examines, (
        'le créneau %d n\'a même pas été examiné (bug du banc)' % slot_ecoute)

    suffixes = b2.suffixes_emis()
    assert any(s.startswith('R-') or s in ('RRR', 'RR73') for s in suffixes), (
        "la réponse reçue dans le créneau %d n'a pas été prise en compte : la "
        "machine a continué à relancer son appel initial.\n"
        "Ce créneau d'ÉCOUTE a été examiné à %d, soit 700 ms après le début de "
        "NOTRE trame du créneau %d — c'est EXACTEMENT le défaut des deux "
        "versions précédentes : juger un créneau passé sur l'état présent.\n"
        "Messages émis : %r" % (slot_ecoute, y + 700, y, b2.emissions_parties()))


def test_tout_message_emis_survit_a_l_aller_retour_du_codec(banc):
    """LE garde-fou qui aurait attrapé le défaut du locator à 6 caractères.

    Un message peut être « valide » au sens où il s'encode, tout en perdant en
    silence un champ que l'émetteur croit transmettre. Mesuré sur le codec du
    dépôt (logx_ft8_codec.js), aller-retour ft8EncodeMessage → ft8DecodeSymbols :

        « F4ABC F4GLD JN18CX »  ->  « F4ABC F4GLD »      grille PERDUE
        « F4ABC F4GLD JN18 »    ->  « F4ABC F4GLD JN18 » intacte

    Vérifier la longueur de la grille ne suffirait pas : n'importe quel futur
    champ ajouté à un message aurait le même problème sans que rien ne le dise.
    On fait donc passer CHAQUE message réellement émis par le codec réel, et on
    exige qu'il revienne à l'identique. Ce que l'écran affiche doit être ce que
    l'air porte."""
    b = banc(correspondant=dict(_correspondant(), parite=0))
    b.js("myGrid = 'JN18CX';")           # le cas NOMINAL de CONFIG (maxlength=6)
    b.js('NOW = 700;')
    b.demarrer(slotEntendu=0)
    b.avancer(400000)
    messages = b.emissions_parties()
    assert messages, 'aucune émission : le test ne prouverait rien'

    ctx = py_mini_racer.MiniRacer()
    ctx.eval(_lire(os.path.join(CONCOURS, 'logx_ft8_codec.js')))
    for msg in messages:
        rendu = ctx.eval('''(function(){
          var HT = ft8CreateHashTable();
          var e = ft8EncodeMessage(%s, HT);
          if(!e) return 'NON ENCODABLE';
          return ft8DecodeSymbols(e.symbols, HT);
        })()''' % json.dumps(msg))
        assert rendu == msg, (
            'ce que nous émettons n\'est pas ce qui arrive en face :\n'
            '  émis    : %r\n  reçu    : %r' % (msg, rendu))


def test_socle_fidele_au_contrat_de_envoyer_message():
    """Le socle RÉIMPLÉMENTE envoyerMessage. Chaque écart silencieux entre les
    deux rend un défaut structurellement invisible — c'est ainsi que TROIS
    constats de la revue du 18/08/2026 ont échappé à 47 tests verts : le socle
    ne reproduisait pas la queue de la vraie fonction, celle qui ouvre le
    bandeau de log manuel.

    Ce test amarre les points de contrat que le socle copie. Il ne compare pas
    les implémentations — il vérifie que les DÉCISIONS existent des deux
    côtés."""
    envoyer = _sans_commentaires(_extraire_fonction(_lire(FT8_HTML), 'envoyerMessage'))

    # 1. Elle REND ce qu'elle a fait. Sans valeur de retour, le séquenceur ne
    #    peut pas distinguer « émis » de « refusé » et relance dans le vide.
    assert re.search(r'return\s+false', envoyer), (
        'envoyerMessage doit rendre false sur ses sorties de refus')
    assert re.search(r'return\s+true', envoyer), (
        'envoyerMessage doit rendre true quand la trame est réellement partie')

    # 2. Une seule source d'émission à la fois.
    assert re.search(r'seq\s*&&\s*texte\s*===\s*undefined', envoyer), (
        "une demande manuelle pendant une séquence doit être refusée : c'est "
        'la garde côté machine contre deux ondes dans le même créneau')

    # 3. L'offre de log automatique appartient au chemin MANUEL.
    i_offre = envoyer.index('offrirLogQso')
    zone = envoyer[max(0, i_offre - 300):i_offre]
    assert 'texte === undefined' in zone and '!seq' in zone, (
        "l'offre de log doit être réservée au chemin manuel — le séquenceur "
        'logue lui-même, avec les reports réellement échangés')

    # 4. Le bouton d'envoi suit l'existence d'une séquence.
    maj = _sans_commentaires(_extraire_fonction(_lire(FT8_HTML), 'majBoutonEnvoyer'))
    assert re.search(r'!txArmed\s*\|\|\s*!!seq', maj), (
        'majBoutonEnvoyer doit neutraliser le bouton pendant une séquence')


def test_creneau_occupe_par_notre_emission_ne_compte_pas_de_relance(banc):
    """L'autre moitié du même raisonnement, et le seul cas où sauter l'examen
    est légitime : un créneau que NOTRE trame occupait n'a rien pu nous
    apprendre. Il ne doit donc ni déclencher de relance, ni faire avancer le
    compteur — sinon un plafond réglé à 3 serait atteint sans qu'aucune vraie
    tentative n'ait été perdue."""
    b = banc(correspondant=_correspondant(muette=True))
    b.js('NOW = 2000;')
    b.demarrer()
    b.avancer(300000)

    et = b.etat()
    assert et['seq'] is not None, \
        "la séquence a disparu alors qu'aucun plafond n'était réglé"
    occupes = {e['slot'] for e in et['parties']}
    ecoutes = [e['slot'] for e in et['examens'] if e['slot'] >= 0 and e['slot'] not in occupes]
    assert et['seq']['relances'] <= len(ecoutes), (
        'relances=%d alors que seuls %d créneaux d\'ÉCOUTE ont été examinés : '
        'un créneau que nous occupions a été compté comme un silence de la '
        'cible.\nCréneaux occupés : %r\nCréneaux examinés : %r'
        % (et['seq']['relances'], len(ecoutes), sorted(occupes),
           sorted(e['slot'] for e in et['examens'])))


@pytest.mark.parametrize('phase', [700, 825, 949])
def test_conclusion_identique_quelle_que_soit_la_phase_d_examen(banc, phase):
    """verifierCycle est cadencée par un setInterval de 250 ms non aligné sur
    la grille UTC : l'examen tombe n'importe où dans [+700, +950[. Aucune
    conclusion du séquenceur ne doit dépendre de cette phase. Un test à une
    seule phase donnerait une fausse assurance — et une phase est justement ce
    qu'un développeur règle « au feeling » pour faire passer un test."""
    b = banc(phase=phase, correspondant=_correspondant())
    b.js('NOW = 2000;')
    b.demarrer()
    b.avancer(500000)
    et = b.etat()
    assert not et['erreurs'], et['erreurs']
    assert len(et['journal']) == 1, (
        'phase %d ms : le QSO n\'a pas abouti (journal=%r). Une décision du '
        'séquenceur dépend de l\'instant d\'examen.' % (phase, et['journal']))


def test_parite_des_creneaux_d_emission_preservee(banc):
    """Une station FT8 émet toujours sur la MÊME parité de créneau (case
    « Tx even/1st » de WSJT-X) : c'est ce qui garantit qu'elle écoute pendant
    que son correspondant émet. Un séquenceur qui change de parité en cours de
    QSO finit par émettre EN MÊME TEMPS que la station qu'il appelle — il se
    brouille lui-même, et rien à l'écran ne l'explique.

    SOURCE : WSJT-X User Guide, réglage « Tx even/1st » ; convention
    universelle du FT8 sur 15 s.

    Coût assumé de cette contrainte, à connaître avant de la lire comme un
    défaut : voir le § « conséquence dérangeante » de l'en-tête."""
    b = banc(correspondant=_correspondant())
    b.js('NOW = 2000;')
    b.demarrer()
    b.avancer(500000)
    creneaux = b.creneaux_emis()
    assert len(creneaux) >= 2, 'trop peu d\'émissions pour juger : %r' % (creneaux,)
    parites = {(c // SLOT_MS) % 2 for c in creneaux}
    assert len(parites) == 1, (
        'le séquenceur a changé de parité de créneau en cours de QSO : %r.\n'
        'Il émettra tôt ou tard par-dessus la station qu\'il appelle.' % (creneaux,))


# ═══════════════════════════════════════════════════════════════════════════
# §3. QSO NOMINAL ET LOG
# ═══════════════════════════════════════════════════════════════════════════

def test_qso_complet_nominal_aboutit_et_est_loggue(banc):
    """Le QSO doit ABOUTIR — premier critère, et aucune des deux versions
    précédentes n'y arrivait.

    Rôle joué : NOUS appelons (réponse à un CQ), donc Tx1 → (son report) →
    Tx3 → (son RRR) → Tx5. La cible est un correspondant RÉACTIF : elle répond
    à ce qu'elle entend, au créneau suivant le nôtre, quelle que soit notre
    cadence.

    Le log doit porter les reports RÉELLEMENT échangés : -13 envoyé (SNR auquel
    NOUS l'entendons) et -07 reçu (ce qu'ELLE annonce). Aujourd'hui
    confirmerLogQso() écrit des chaînes VIDES dans rst_sent/rst_rcvd
    (logx_ft8.html:1676) : un log FT8 sans reports est un log faux, et il
    part tel quel vers LoTW/eQSL."""
    b = banc(correspondant=_correspondant())
    b.js('NOW = 2000;')
    b.demarrer()
    b.avancer(500000)

    et = b.etat()
    assert not et['erreurs'], et['erreurs']
    parties = [e['texte'] for e in et['parties']]
    assert parties, 'la machine n\'a rien émis du tout'

    prefixe = f'{CIBLE} {MOI} '
    assert all(p.startswith(prefixe) for p in parties), \
        'un message émis n\'était pas adressé à la cible et signé de nous : %r' % (parties,)
    suffixes = [p[len(prefixe):] for p in parties]
    assert suffixes[0] == MA_GRILLE, 'Tx1 doit annoncer NOTRE grille : %r' % (suffixes,)
    assert 'R-13' in suffixes, \
        'Tx3 doit accuser son report en envoyant le nôtre (R-13) : %r' % (suffixes,)
    assert suffixes[-1] == '73', 'le QSO doit se terminer par 73 : %r' % (suffixes,)

    assert len(et['journal']) == 1, \
        'le QSO doit être loggué AUTOMATIQUEMENT, une fois et une seule : %r' % (et['journal'],)
    entree = et['journal'][0]
    infos = entree['infos'] or {}
    assert entree['call'] == CIBLE
    assert str(infos.get('rst_sent')) == '-13', \
        'rst_sent doit être le report que NOUS avons envoyé : %r' % (infos,)
    assert str(infos.get('rst_rcvd')) == '-07', \
        'rst_rcvd doit être le report qu\'ELLE a envoyé : %r' % (infos,)
    assert infos.get('locator') == GRILLE_CIBLE, \
        'la grille connue de la cible doit être loggée : %r' % (infos,)
    assert infos.get('dist'), \
        'la distance doit être calculée (les deux grilles sont connues) : %r' % (infos,)


def test_role_appele_repond_par_un_report_a_une_grille(banc):
    """Autre rôle : c'est ELLE qui nous appelle en annonçant sa grille. La
    réponse attendue est Tx2 — un report NU, pas R<report>, et surtout pas une
    répétition de notre propre grille."""
    b = banc(scenario={
        str(SLOT_MS): [{'text': f'{MOI} {CIBLE} {GRILLE_CIBLE}', 'snr': SNR_ELLE_CHEZ_NOUS}],
    })
    b.js('NOW = 16000;')                 # on démarre APRÈS ce créneau
    b.demarrer(grille=GRILLE_CIBLE)
    b.avancer(200000)

    suffixes = b.suffixes_emis()
    assert suffixes, 'aucune émission'
    assert '-13' in suffixes, \
        'à réception de sa GRILLE, la réponse est un report NU (Tx2) : %r' % (suffixes,)
    assert 'R-13' not in suffixes[:suffixes.index('-13') + 1], \
        'R<report> (Tx3) envoyé avant le report nu (Tx2) : %r' % (suffixes,)


def test_apres_73_recu_plus_aucune_emission(banc):
    """« Réception d'un 73 : QSO fini, ne rien réémettre. » Un 73 qui déclenche
    une réémission, c'est une station qui continue d'appeler quelqu'un ayant
    déjà tourné la page — et, avec un plafond illimité, sans fin."""
    b = banc(scenario={
        str(SLOT_MS * 2): [{'text': f'{MOI} {CIBLE} 73', 'snr': SNR_ELLE_CHEZ_NOUS}],
    })
    b.js('NOW = 2000;')
    b.demarrer()
    b.avancer(80000)
    demarrees = len(b.etat()['demarrees'])
    b.avancer(400000)

    et = b.etat()
    assert len(et['demarrees']) == demarrees, \
        'des émissions sont parties APRÈS la réception du 73 : %r' % (et['emissions'],)
    assert et['seq'] is None, 'la séquence doit être terminée après un 73 reçu'


def test_rr73_recu_envoie_73_puis_loggue_puis_arrete(banc):
    """RR73 vaut à la fois « bien reçu » et « 73 » : on répond 73, on loggue,
    puis on s'arrête. Il faut LAISSER PARTIR ce dernier message — un arrêt
    immédiat couperait le 73 en plein vol, laisserait le QSO incomplet en face
    et donnerait à l'opérateur d'en face l'impression d'un abandon."""
    b = banc(correspondant=_correspondant(final='RR73'))
    b.js('NOW = 2000;')
    b.demarrer()
    b.avancer(500000)

    et = b.etat()
    parties = et['parties']
    assert parties, 'aucune émission'
    assert parties[-1]['texte'] == f'{CIBLE} {MOI} 73', \
        'le dernier message émis doit être le 73 : %r' % ([e['texte'] for e in parties],)
    assert parties[-1]['finMs'] is not None, \
        "le 73 a été coupé en cours d'émission au lieu d'être laissé partir"
    assert len(et['journal']) == 1, 'RR73 doit déclencher le log : %r' % (et['journal'],)
    assert et['seq'] is None, 'la séquence doit être terminée après le 73 émis'


def test_r_report_recu_ne_declenche_pas_un_r_report_en_retour(banc):
    """Défaut confirmé par la revue : « R<report> » était renvoyé en réponse à
    un « R<report> ». Les deux stations se répondaient alors R-07 / R-13
    indéfiniment — blocage et émission sans fin, le pire résultat possible pour
    un automatisme sur l'air."""
    b = banc(scenario={
        str(SLOT_MS * 2): [{'text': f'{MOI} {CIBLE} R-07', 'snr': SNR_ELLE_CHEZ_NOUS}],
    })
    b.js('NOW = 2000;')
    b.demarrer()
    b.avancer(200000)

    suffixes = b.suffixes_emis()
    apres = [s for s in suffixes if s not in (MA_GRILLE,)]
    assert not any(re.fullmatch(r'R[+-]\d{1,2}', s) for s in apres), \
        'un R<report> a été renvoyé en réponse à un R<report> : %r' % (suffixes,)
    assert 'RRR' in suffixes or 'RR73' in suffixes, \
        'la réponse à un R<report> doit être RRR (Tx4) : %r' % (suffixes,)


# ═══════════════════════════════════════════════════════════════════════════
# §4. RELANCES ET ABANDONS
# ═══════════════════════════════════════════════════════════════════════════

def test_aucune_reponse_relance_sans_plafond_et_compteur_qui_avance(banc):
    """Décision d'opérateur titulaire, non discutable : la relance va JUSQU'À
    CONFIRMATION DU CONTACT, sans plafond par défaut. On vérifie les deux
    choses à la fois — que ça relance vraiment, et que le compteur avance : un
    compteur figé rendrait tout plafond réglé inopérant, sans rien montrer."""
    b = banc(correspondant=_correspondant(muette=True))
    b.js('NOW = 2000;')
    b.demarrer()
    b.avancer(900000)                    # 15 minutes de temps virtuel

    et = b.etat()
    assert et['seq'] is not None, \
        "la séquence s'est arrêtée toute seule alors qu'aucun plafond n'est réglé"
    assert et['seq']['relances'] >= 4, \
        'le compteur de relances n\'avance pas : %r' % (et['seq'],)
    parties = b.emissions_parties()
    assert len(parties) >= 4, 'trop peu de relances parties : %r' % (parties,)
    assert all(p == f'{CIBLE} {MOI} {MA_GRILLE}' for p in parties), \
        'une relance sans réponse doit répéter Tx1 à l\'identique : %r' % (parties,)


def test_plafond_regle_a_3_abandonne_apres_3_relances(banc):
    """ÉGALITÉ, pas inégalité (revue adversariale du 18/08/2026).

    Ce test disait « au plus 4 émissions ». Une machine qui SUR-COMPTE les
    relances — en comptant chaque créneau d'écoute intermédiaire, et pas
    seulement celui où la réponse était attendue — épuise un plafond de 3 après
    UNE seule vraie tentative : elle satisfait donc « au plus 4 » en n'émettant
    que 2 fois. Mutation vérifiée : supprimer la garde `slotExamine <
    seq.slotAttendu` laissait les tests verts.

    Exactement 4 : un appel, puis trois relances."""
    b = banc(correspondant=_correspondant(muette=True))
    b.js('NOW = 2000;')
    b.demarrer(slotEntendu=0, maxRelances=3)
    b.avancer(900000)

    et = b.etat()
    assert et['seq'] is None, "le plafond de 3 relances n'a pas arrêté la séquence"
    parties = b.emissions_parties()
    assert len(parties) == 4, (
        '%d émissions au lieu de 4 exactement (1 appel + 3 relances). Moins '
        'signifie que les relances sont SUR-COMPTÉES : un plafond réglé est '
        "alors atteint sans qu'aucune vraie tentative n'ait échoué. Plus "
        'signifie que le plafond ne borne rien. Émissions : %r'
        % (len(parties), parties))
    assert not et['journal'], 'aucun QSO ne doit être loggué après un abandon'


def test_cible_qui_repond_a_un_tiers_declenche_un_abandon(banc):
    """Garde-fou déjà présent dans les versions précédentes — et INATTEIGNABLE,
    parce que le message censé le déclencher tombait dans un créneau jeté à
    tort. Ici, le cas simple : elle répond à un tiers dans un créneau que nous
    n'occupons pas."""
    b = banc(scenario={
        str(SLOT_MS * 2): [{'text': f'{TIERS} {CIBLE} -05', 'snr': SNR_ELLE_CHEZ_NOUS}],
    })
    b.js('NOW = 2000;')
    b.demarrer()
    b.avancer(300000)

    et = b.etat()
    assert et['seq'] is None, \
        'la cible est en QSO avec un tiers : la séquence devait être abandonnée'
    assert not et['journal'], 'aucun QSO ne doit être loggué après un abandon'
    assert len(b.emissions_parties()) <= 2, \
        'on a continué à appeler une station déjà en QSO avec un tiers : %r' \
        % (b.emissions_parties(),)


def test_abandon_tiers_atteignable_meme_examine_pendant_notre_emission(banc):
    """Même deux passes que le test emblématique : le message entre la cible et
    un tiers est placé dans le créneau Y-15000, dont l'examen tombe 700 ms
    après le début de NOTRE trame du créneau Y. C'est le cas exact qui rendait
    ce garde-fou inatteignable — et donc le séquenceur incapable de lâcher une
    station qu'il ne pouvait plus contacter."""
    b1 = banc(correspondant=_correspondant(muette=True))
    b1.js('NOW = 2000;')
    b1.demarrer()
    b1.avancer(400000)
    creneaux = b1.creneaux_emis()
    assert len(creneaux) >= 2, 'pas assez de relances pour construire le cas'
    y = creneaux[1]

    b2 = banc(scenario={
        str(y - SLOT_MS): [{'text': f'{TIERS} {CIBLE} -05', 'snr': SNR_ELLE_CHEZ_NOUS}],
    })
    b2.js('NOW = 2000;')
    b2.demarrer()
    b2.avancer(400000)
    assert b2.etat()['seq'] is None, (
        "l'abandon « la cible répond à un tiers » est resté INATTEIGNABLE : le "
        "message tombait dans le créneau %d, examiné à %d, pendant notre trame "
        "du créneau %d." % (y - SLOT_MS, y + 700, y))


# ═══════════════════════════════════════════════════════════════════════════
# §4bis. LES CONSTATS DE LA REVUE ADVERSARIALE DU 18/08/2026
#
# Chacun de ces tests ROUGIT sur le code d'avant correction — vérifié un par
# un en remettant le défaut. Un test ajouté après coup qui passe du premier
# coup ne prouve rien : il décrit le code au lieu de le contraindre.
# ═══════════════════════════════════════════════════════════════════════════

# ── CRITIQUE — la parité d'émission n'était pas dérivée de la cible ────────

@pytest.mark.parametrize('depart', [700, 2000, 4000, 6000, 8000, 10000, 12000,
                                    14000, 15700, 17000, 19000, 21000, 23000,
                                    25000, 27000, 29000])
def test_notre_parite_est_toujours_l_inverse_de_celle_de_la_cible(banc, depart):
    """LE défaut le plus grave trouvé par la revue.

    En FT8 une station émet toujours sur la même moitié du cycle de 30 s. Deux
    stations sur la MÊME parité ne s'entendent jamais : chacune émet pendant
    que l'autre émet. La parité restait à null et se figeait sur le premier
    créneau libre venu — donc, selon l'instant du double-clic, une fois sur
    deux sur la parité de la station appelée. Aucun QSO n'était alors possible,
    et le plafond de relances valant 0 par défaut, la station répétait
    indéfiniment PAR-DESSUS celle qu'elle appelait.

    16 instants de départ répartis sur deux créneaux : AUCUN ne doit produire
    une émission dans les créneaux de la cible."""
    slot_entendu = 0                     # elle a été entendue dans le créneau 0
    parite_cible = (slot_entendu // SLOT_MS) % 2
    b = banc(correspondant=dict(_correspondant(muette=True), parite=parite_cible))
    b.js('NOW = %d;' % depart)
    b.demarrer(slotEntendu=slot_entendu)
    b.avancer(300000)

    notres = [(c // SLOT_MS) % 2 for c in b.creneaux_emis()]
    assert notres, 'aucune émission : le test ne prouverait rien'
    assert parite_cible not in notres, (
        'départ à %d : %d de nos %d émissions tombent dans les créneaux de la '
        'cible (parité %d). Elle ne peut pas nous entendre, nous ne pouvons pas '
        "l'entendre, et nous la brouillons."
        % (depart, notres.count(parite_cible), len(notres), parite_cible))


def test_le_qso_aboutit_avec_une_station_a_parite_fixe(banc):
    """Contre-épreuve du test précédent : sur la BONNE parité, le QSO doit
    aller au bout. Sans elle, « ne jamais émettre sur sa parité » serait
    satisfait en n'émettant jamais du tout."""
    b = banc(correspondant=dict(_correspondant(), parite=0))
    b.js('NOW = 700;')
    b.demarrer(slotEntendu=0)            # créneau 0 → parité 0 → la nôtre est 1
    b.avancer(400000)
    et = b.etat()
    assert et['journal'], 'aucun QSO loggué avec une station à parité fixe'
    assert et['journal'][0]['infos']['rst_sent']
    assert et['journal'][0]['infos']['rst_rcvd']


def test_sans_creneau_connu_la_parite_reste_decidee_a_la_premiere_emission(banc):
    """Repli assumé : un démarrage sans créneau d'écoute (appel programmatique)
    ne peut pas deviner la parité de la cible. On la fige alors sur notre
    première émission — imparfait, mais stable, et c'est le comportement
    d'avant. Ce test existe pour que ce repli reste un CHOIX documenté et non
    une régression silencieuse."""
    b = banc(correspondant=_correspondant(muette=True))
    b.js('NOW = 2000;')
    b.demarrer()                         # aucun slotEntendu
    b.avancer(120000)
    parites = {(c // SLOT_MS) % 2 for c in b.creneaux_emis()}
    assert len(parites) == 1, 'la parité doit rester STABLE une fois figée : %r' % parites


# ── CRITIQUE — « couper l'écoute » n'arrêtait pas la séquence ──────────────

def test_arreter_rx_appelle_bien_seqarreter():
    """Le seul endroit qui VOIE la coupure d'écoute.

    La garde équivalente de seqExaminerCreneau est du CODE MORT :
    seqExaminerCreneau n'est appelée que par verifierCycle, qui sort dès sa
    première ligne sur !rxActif, et arreterRx supprime jusqu'au timer qui
    l'aurait rappelée. Mesuré avant correction : la séquence survivait à
    « ■ Arrêter », l'écran affichait toujours « QSO avec F4ABC », et relancer
    l'écoute deux minutes plus tard remettait la station en émission sans un
    geste de l'opérateur.

    Commentaires dépouillés : le pavé qui EXPLIQUE ce câblage cite seqArreter,
    et sans dépouillement ce test serait satisfait par de la prose."""
    corps = _sans_commentaires(_extraire_fonction(_lire(FT8_HTML), 'arreterRx'))
    assert 'seqArreter' in corps, (
        "arreterRx() ne coupe pas la séquence. La garde de seqExaminerCreneau "
        "ne peut pas la remplacer : elle est inatteignable écoute coupée.")


def test_la_garde_de_seqexaminercreneau_ne_suffit_pas_seule(banc):
    """Contre-preuve, pour que le test précédent ne passe jamais pour de
    mauvaises raisons : si l'on se contente de baisser rxActif — c'est-à-dire
    si arreterRx ne faisait QUE cela — la séquence reste vivante. C'est
    exactement ce que faisait la page, et ce que le banc ne pouvait pas voir
    tant que son ordonnanceur ignorait rxActif."""
    b = banc(correspondant=_correspondant(muette=True))
    b.js('NOW = 2000;')
    b.demarrer(slotEntendu=0)
    b.avancer(20000)
    b.js('rxActif = false;')             # SANS seqArreter : le défaut d'origine
    b.avancer(200000)
    assert b.etat()['seq'] is not None, (
        'Si ce test tombe, la garde de seqExaminerCreneau est devenue '
        "atteignable — et alors test_arreter_rx_appelle_bien_seqarreter n'est "
        'plus le seul filet. Revoir les deux ensemble.')


def test_reprendre_l_ecoute_ne_relance_aucune_emission(banc):
    """Après un arrêt d'écoute correct, relancer l'écoute ne doit RIEN
    réémettre. Avant correction, demarrerRx remettait lastProcessedSlot à 0 et
    le premier examen relançait : la station se remettait à émettre toute
    seule, plusieurs minutes après que l'opérateur avait tout coupé."""
    b = banc(correspondant=_correspondant(muette=True))
    b.js('NOW = 2000;')
    b.demarrer(slotEntendu=0)
    b.avancer(20000)
    b.js("seqArreter('ecoute-arretee'); annulerEmissionsProgrammees(); rxActif = false;")
    b.avancer(140000)
    avant = len(b.etat()['parties'])
    b.js('rxActif = true;')
    b.avancer(300000)
    assert len(b.etat()['parties']) == avant, (
        "reprendre l'écoute a relancé des émissions : %r"
        % b.emissions_parties()[avant:])


# ── CRITIQUE — le bouton « Envoyer » restait actif pendant la séquence ─────

def test_le_bouton_envoyer_est_neutralise_pendant_la_sequence(banc):
    """Deux formes d'onde FT8 simultanées, sur la même fréquence, dans le même
    créneau : un brouillage causé par sa propre station et invisible depuis
    celle-ci. Le bouton restait cliquable parce que sa seule condition était
    !txArmed, et qu'aucune fonction du séquenceur n'y touchait."""
    b = banc(correspondant=_correspondant())
    b.js('NOW = 2000;')
    assert b.etat()['envoyerDesactive'] is False, 'au repos, le bouton doit servir'
    b.demarrer(slotEntendu=0)
    et = b.etat()
    assert et['envoyerDesactive'] is True, 'le bouton reste cliquable pendant la séquence'
    assert et['champVerrouille'] is True, 'le champ reste modifiable pendant la séquence'
    b.js("seqArreter('bouton');")
    assert b.etat()['envoyerDesactive'] is False, 'le bouton doit revenir après STOP'


def test_un_envoi_manuel_pendant_la_sequence_ne_double_pas_l_emission(banc):
    """Ceinture côté MACHINE : même si le bouton réapparaissait, une demande
    d'émission SANS texte explicite (le seul geste manuel possible) ne doit
    rien produire pendant une séquence."""
    b = banc(correspondant=_correspondant(muette=True))
    b.js('NOW = 2000;')
    b.demarrer(slotEntendu=0)
    b.avancer(5000)
    b.js('document.getElementById("txText").value = "POUBELLE";')
    b.js('envoyerMessage();')            # clic « Envoyer » — sans argument
    b.avancer(120000)
    creneaux = b.creneaux_emis()
    assert len(creneaux) == len(set(creneaux)), (
        'deux émissions dans le même créneau : %r' % creneaux)
    assert 'POUBELLE' not in ' '.join(b.emissions_parties())


# ── CRITIQUE — message sans grille : émission sans fin, plafond inopérant ──

def test_une_reponse_sans_grille_fait_avancer_le_qso(banc):
    """« F4GLD F4ABC » — message standard SANS grille — est une forme
    parfaitement valide du protocole, et c'est même ce que LogX AI émettait
    lui-même dès que le locator de CONFIG dépassait 4 caractères : deux postes
    LogX AI se bloquaient donc mutuellement. seqSuite ne le reconnaissait pas
    et répétait le Tx1 indéfiniment. Protocolairement, c'est une RÉPONSE À
    NOTRE APPEL : on enchaîne sur le report."""
    x = 30000
    b = banc(correspondant=_correspondant(muette=True),
             scenario={str(x): ['%s %s' % (MOI, CIBLE)]})
    b.js('NOW = 2000;')
    b.demarrer(slotEntendu=0)
    b.avancer(200000)
    suffixes = b.suffixes_emis()
    assert any(re.match(r'^[+-]\d{2}$', s) for s in suffixes), (
        'le QSO n\'a pas avancé jusqu\'au report : %r' % suffixes)


def test_un_correspondant_qui_repete_sans_faire_avancer_finit_par_etre_abandonne(banc):
    """Le plafond réglé par l'opérateur doit TOUJOURS finir par s'appliquer.

    Il était remis à zéro dès qu'un message nous était adressé, AVANT même de
    savoir s'il faisait progresser le QSO : une station qui répète un message
    inexploitable remettait le compteur à zéro à chaque créneau, et l'émission
    ne s'arrêtait jamais. Mesuré avant correction : 19 émissions en 10 minutes
    avec un plafond réglé à 3."""
    scenario = {}
    for k in range(2, 40):
        scenario[str(k * SLOT_MS)] = ['%s %s RUBBISH' % (MOI, CIBLE)]
    b = banc(correspondant=_correspondant(muette=True), scenario=scenario)
    b.js('NOW = 2000;')
    b.demarrer(slotEntendu=0, maxRelances=3)
    b.avancer(600000)
    assert b.etat()['seq'] is None, (
        'la séquence tourne encore après 10 minutes malgré un plafond de 3 : '
        '%d émissions' % len(b.etat()['parties']))


# ── MAJEUR — une émission jamais partie était comptée comme émise ──────────

def test_une_emission_refusee_arrete_la_sequence_au_lieu_de_relancer(banc):
    """envoyerMessage sort sans rien émettre dans quatre cas réels : message
    non encodable, annulation pendant l'attente, verrou SO2R, aucun pilotage
    radio. Elle ne rendait rien : le séquenceur croyait avoir émis, sautait
    l'examen du créneau, comptait une relance et reprogrammait. Mesuré avant
    correction : 0 émission réelle en 400 s, « relances 6 » à l'écran, et rien
    nulle part pour dire que la radio n'avait jamais émis."""
    b = banc(correspondant=_correspondant(muette=True))
    b.js('NOW = 2000;')
    # Refus permanent, fidèle à la sortie « verrou SO2R / non_engage ».
    b.js('envoyerMessage = function(){ return Promise.resolve(false); };')
    b.demarrer(slotEntendu=0)
    b.avancer(400000)
    assert b.etat()['seq'] is None, (
        'la séquence relance dans le vide alors que rien ne part sur l\'air')


def test_une_emission_qui_leve_arrete_aussi_la_sequence(banc):
    """Une promesse REJETÉE ne doit pas être confondue avec un envoi réussi :
    la continuation d'erreur recevait le motif du rejet, jamais `false`."""
    b = banc(correspondant=_correspondant(muette=True))
    b.js('NOW = 2000;')
    b.js('envoyerMessage = function(){ return Promise.reject(new Error("radio")); };')
    b.demarrer(slotEntendu=0)
    b.avancer(400000)
    assert b.etat()['seq'] is None


# ── MAJEUR — la queue de envoyerMessage rouvrait le log manuel sans report ──

def test_un_qso_sequence_ne_produit_qu_une_offre_de_log_avec_ses_reports(banc):
    """Le séquenceur passe par envoyerMessage comme le chemin manuel. Sa queue
    ouvrait « QSO complété — l'ajouter au log ? » dès le RRR, EN PLEIN QSO,
    avec des reports VIDES. Un opérateur qui validait écrivait une fiche sans
    report ; le log complet du séquenceur arrivait ensuite et se faisait
    rejeter en 409 « déjà loggué ». La mauvaise fiche restait, la bonne était
    perdue — l'exact contraire de « log automatique et COMPLET ». Une
    troisième offre partait même APRÈS l'arrêt de la séquence et restait
    affichée indéfiniment."""
    b = banc(correspondant=dict(_correspondant(), parite=0))
    b.js('NOW = 700;')
    b.demarrer(slotEntendu=0)
    b.avancer(400000)
    et = b.etat()
    assert len(et['journal']) == 1, (
        '%d entrées au journal pour UN QSO : %r' % (len(et['journal']), et['journal']))
    infos = et['journal'][0]['infos'] or {}
    assert infos.get('rst_sent') and infos.get('rst_rcvd'), (
        'fiche loggée SANS report échangé : %r' % infos)
    assert et['offreEnAttente'] is None, (
        'une offre de log est restée affichée après la fin de la séquence : %r'
        % (et['offreEnAttente'],))


# ── MAJEUR — locator 6 caractères : la grille partait vide, en silence ─────

def test_le_tx1_ne_porte_que_le_carre_a_quatre_caracteres(banc):
    """Le champ locator de CONFIG est maxlength=6 avec le placeholder
    « JN15XC » : 6 caractères est le cas NOMINAL, pas un cas tordu. Le message
    FT8 standard ne transporte que le carré à 4 caractères ; passer 6
    caractères faisait partir le message SANS grille, en silence, alors que le
    champ d'émission affichait pourtant la grille complète.

    Conséquence en chaîne : notre carré n'arrivait jamais chez le
    correspondant, et le message émis était précisément celui qui met un autre
    poste LogX AI en boucle infinie (constat de la réponse sans grille)."""
    b = banc(correspondant=_correspondant(muette=True))
    b.js("myGrid = 'JN18CX';")
    b.js('NOW = 2000;')
    b.demarrer(slotEntendu=0)
    b.avancer(60000)
    suffixes = b.suffixes_emis()
    assert suffixes and suffixes[0] == 'JN18', (
        'le Tx1 doit porter JN18, il porte %r' % (suffixes[0] if suffixes else None))


# ── MODÉRÉ — démarrage sans « Activer l'émission » ────────────────────────

def test_sans_armement_le_sequenceur_refuse_et_nomme_la_case(banc):
    """L'écran annonçait « QSO avec F4ABC » — l'opérateur croyait son QSO
    lancé — puis, 12 s plus tard, mourait sur « conditions plus réunies », une
    phrase qui ne nomme ni la case, ni où la trouver. Le chemin manuel traite
    ce cas depuis toujours en nommant la case ET en la faisant clignoter."""
    b = banc(correspondant=_correspondant())
    b.js('NOW = 2000;')
    b.js('txArmed = false;')
    assert b.demarrer(slotEntendu=0) is None, 'aucune séquence ne doit être créée'
    assert b.etat()['seq'] is None
    b.avancer(120000)
    assert not b.etat()['parties'], 'rien ne doit partir sans armement'


# ── MODÉRÉ — le filtre de source n'était tenu par aucun test ──────────────

def test_un_tiers_qui_nous_appelle_ne_fait_pas_avancer_le_qso(banc):
    """En FT8 il est courant que plusieurs stations nous appellent pendant un
    QSO. La ligne qui écarte les messages dont la source n'est pas la cible
    est la SEULE chose qui empêche de prendre l'appel de DL1XYZ pour la
    réponse de F4ABC — et de loguer F4ABC avec la grille et le report d'une
    autre station. Elle pouvait disparaître sans qu'un seul test rougisse
    (vérifié : mutation en `if(false)`, 47 tests verts).

    ÉCRIT EN DEUX TEMPS, après contre-épreuve. Une première version vérifiait
    qu'aucun message ne partait vers DL1XYZ et que le journal ne portait pas sa
    grille : elle restait VERTE avec le filtre muté en `if(false)`. Elle ne
    prouvait rien — la cible du séquenceur ne change pas, donc aucun message ne
    part jamais vers le tiers, et un QSO qui n'aboutit pas ne logue rien. Le
    dégât réel est ailleurs : l'ÉTAPE AVANCE sur le message d'un tiers, et
    c'est la grille du tiers qui finit dans notre fiche.
    """
    scenario = {}
    for k in range(2, 20):
        scenario[str(k * SLOT_MS)] = ['%s DL1XYZ JO31' % MOI,
                                      '%s DL1XYZ -05' % MOI]

    # 1. Cible MUETTE : nous devons rester au Tx1 (notre grille) quoi que les
    #    tiers racontent. Si le filtre saute, « JO31 » est lu comme sa réponse
    #    et nous passons au report — visible dans le suffixe émis.
    b = banc(correspondant=_correspondant(muette=True), scenario=scenario)
    b.js('NOW = 2000;')
    b.demarrer(slotEntendu=0)
    b.avancer(300000)
    suffixes = b.suffixes_emis()
    assert suffixes, 'aucune émission : le test ne prouverait rien'
    assert set(suffixes) == {MA_GRILLE}, (
        "l'étape a avancé sur le message d'un TIERS : suffixes émis %r" % suffixes)
    for texte in b.emissions_parties():
        assert 'DL1XYZ' not in texte, 'message émis vers un tiers : %r' % texte

    # 2. Cible qui RÉPOND : le QSO aboutit, et la fiche doit porter SA grille,
    #    jamais celle du tiers.
    b2 = banc(correspondant=dict(_correspondant(), parite=0), scenario=scenario)
    b2.js('NOW = 700;')
    b2.demarrer(slotEntendu=0)
    b2.avancer(400000)
    journal = b2.etat()['journal']
    assert journal, 'le QSO avec la cible aurait dû aboutir'
    assert journal[0]['call'] == CIBLE
    assert journal[0]['infos']['locator'] != 'JO31', (
        'la grille du TIERS a été loggée à la place de celle de la cible')


# ═══════════════════════════════════════════════════════════════════════════
# §4ter. DEUXIÈME REVUE ADVERSARIALE (19/08/2026)
#
# La revue a attaqué les correctifs de la première, et en a trouvé plusieurs
# qui déplaçaient le défaut au lieu de le fermer. Ces tests-là comptent double :
# ils protègent une correction DE correction.
# ═══════════════════════════════════════════════════════════════════════════

# ── Le plafond de relances, défait par une station qui ALTERNE ─────────────

@pytest.mark.parametrize('alternance', [
    ('JN18', 'R-12'),      # sa grille, puis un R-report  (TX2 <-> TX4)
    ('JN18', '-12'),       # sa grille, puis un report nu (TX2 <-> TX3)
    ('R-12', 'JN18'),      # l'ordre inverse : on commence par régresser
])
def test_un_correspondant_qui_alterne_deux_messages_n_echappe_pas_au_plafond(
        banc, alternance):
    """Une station qui ALTERNE deux messages fait réellement AVANCER le QSO une
    fois sur deux. Deux formulations plus simples du « progrès » ont donc été
    essayées et MESURÉES insuffisantes avant d'arriver à celle-ci :

      « l'étape CHANGE »          — une régression est un changement : le
                                    compteur repartait de zéro à chaque recul.
      « l'étape AVANCE depuis la
        dernière fois »           — l'alternance avance une fois sur deux, donc
                                    remet le compteur à zéro une fois sur deux.
                                    Mesuré : 10 trames en 10 min avec un
                                    plafond de 3, séquence toujours vivante.

    Ce qui ferme le cas, c'est de comparer à l'étape la PLUS AVANCÉE jamais
    atteinte : re-atteindre un point déjà visité n'est pas un progrès, c'est un
    cycle. Mesuré après correction : 5 à 6 trames, puis abandon.

    LE SCÉNARIO EST DÉCOUVERT, PAS ÉCRIT EN DUR. Première version de ce test :
    j'alternais un message tous les 15 s. Ça ne reproduisait RIEN — à la cadence
    réelle (un échange toutes les 60 s) la machine relit toujours la même phase
    du scénario et se retrouve à voir un message RÉPÉTÉ, pas alterné. Le test
    passait donc avec ET sans correctif. On découvre d'abord les créneaux où la
    machine attend une réponse, puis on alterne SUR CEUX-LÀ."""
    a, b = alternance
    # 1re passe : où la machine attend-elle réellement une réponse ?
    reco = banc(correspondant=_correspondant(muette=True))
    reco.js('NOW = 2000;')
    reco.demarrer(slotEntendu=0)
    reco.avancer(600000)
    attendus = [c + SLOT_MS for c in reco.creneaux_emis()]
    assert len(attendus) >= 4, 'pas assez de créneaux pour alterner'

    # 2e passe : alterner sur ces créneaux-là.
    scenario = {str(sl): ['%s %s %s' % (MOI, CIBLE, a if i % 2 else b)]
                for i, sl in enumerate(attendus)}
    bc = banc(correspondant=_correspondant(muette=True), scenario=scenario)
    bc.js('NOW = 2000;')
    bc.demarrer(slotEntendu=0, maxRelances=3)
    # 10 minutes SEULEMENT : franchement sous le plafond de DURÉE (15 min),
    # sans quoi ce test passerait grâce à lui et non grâce au plafond de
    # relances qu'il prétend vérifier.
    bc.avancer(600000)
    et = bc.etat()
    assert et['seq'] is None, (
        'plafond réglé à 3, et la séquence tourne encore après 10 minutes : '
        '%d trames émises, écran = %r' % (len(et['parties']), et['seqEtat']))
    assert len(et['parties']) <= 8, (
        'plafond réglé à 3 et %d trames parties : %r'
        % (len(et['parties']), bc.emissions_parties()))
    assert 'avance pas' in et['seqEtat'], (
        "l'arrêt doit dire que le QSO n'avance pas : %r" % et['seqEtat'])


def test_un_qso_qui_avance_normalement_remet_bien_le_compteur_a_zero(banc):
    """Contre-épreuve du test précédent. Exiger « le compteur ne repart jamais
    à zéro » serait satisfait en ne le remettant JAMAIS à zéro — et un QSO
    normal, mais lent, serait alors abandonné à tort. Le QSO nominal doit
    aboutir avec un plafond serré."""
    b = banc(correspondant=dict(_correspondant(), parite=0))
    b.js('NOW = 700;')
    b.demarrer(slotEntendu=0, maxRelances=2)
    b.avancer(400000)
    assert b.etat()['journal'], (
        "un QSO nominal a été abandonné alors qu'il avançait : %r"
        % (b.etat()['seqEtat'],))


# ── Le plafond de DURÉE, seul garde-fou du réglage LIVRÉ ───────────────────

def test_le_reglage_livre_sans_limite_a_quand_meme_un_plafond_de_duree(banc):
    """« Sans limite (jusqu'au contact) » est le réglage PAR DÉFAUT, et 0 est
    falsy : toutes les gardes écrites « seq.maxRelances && … » étaient donc
    mortes pour l'immense majorité des opérateurs, qui ne changent pas ce
    réglage. Mesuré avant correction : 479 trames automatiques en 4 h, séquence
    toujours vivante, étape figée sur TX1.

    « Jusqu'au contact » veut dire que l'opérateur accepte d'ATTENDRE, pas
    d'émettre indéfiniment dans le vide."""
    b = banc(correspondant=_correspondant(muette=True))
    b.js('NOW = 2000;')
    b.demarrer(slotEntendu=0)            # AUCUN maxRelances : le réglage livré
    assert b.etat()['seq']['maxRelances'] == 0, 'le test doit jouer le défaut livré'
    b.avancer(4 * 3600 * 1000)           # 4 heures de temps virtuel
    et = b.etat()
    assert et['seq'] is None, (
        'séquence toujours vivante après 4 h avec le réglage livré : %d trames'
        % len(et['parties']))
    assert 'minutes' in et['seqEtat'] or 'longue' in et['seqEtat'], (
        "l'arrêt doit dire que c'est le plafond de DURÉE : %r" % et['seqEtat'])


def test_le_plafond_de_duree_ne_coupe_pas_un_qso_normal(banc):
    """Contre-épreuve : un QSO nominal dure quelques minutes à la cadence de
    cette page. Le plafond ne doit jamais le rattraper."""
    b = banc(correspondant=dict(_correspondant(), parite=0))
    b.js('NOW = 700;')
    b.demarrer(slotEntendu=0)
    b.avancer(400000)
    assert b.etat()['journal'], 'le plafond de durée a coupé un QSO normal'


# ── Décocher « Activer l'émission » ne doit pas laisser une séquence vivante ─

def test_double_clic_sur_une_autre_station_abandonne_toujours_l_ancienne(banc):
    """RÉGRESSION INTRODUITE par le correctif « refuser sans armement » : placé
    AVANT la garde de remplacement, il faisait sortir seqDemarrer sans arrêter
    la séquence en cours.

    Conséquence mesurée : l'opérateur décoche la case, double-clique une AUTRE
    station, l'écran affirme « rien ne peut partir » — puis recocher la case
    relance l'émission vers la station qu'il venait d'abandonner, dont
    l'indicatif n'a jamais été affiché. 3 trames vers l'ancienne cible."""
    b = banc(correspondant=_correspondant(muette=True))
    b.js('NOW = 2000;')
    b.demarrer(slotEntendu=0)                       # séquence vers F4ABC
    b.avancer(5000)
    # txArmed baissé SANS passer par onArmChange : on teste ici le contrat
    # propre de seqDemarrer — « aucun refus ne doit laisser une séquence
    # orpheline » — et non le câblage du décochage, qui a son propre test.
    #
    # Piège trouvé en contre-épreuve : la première version passait par
    # onArmChangeSimule(), qui arrête déjà la séquence. Le test était donc vert
    # même en neutralisant la garde de remplacement qu'il visait : il vérifiait
    # le correctif du voisin.
    b.js('txArmed = false;')
    b.demarrer(cible='DL1XYZ', slotEntendu=0)       # double-clic sur une autre
    assert b.etat()['seq'] is None, (
        'la séquence vers %s a survécu au double-clic sur une autre station'
        % CIBLE)
    b.js('txArmed = true;')
    b.avancer(400000)
    vers_ancienne = [t for t in b.emissions_parties() if t.startswith(CIBLE + ' ')]
    assert not vers_ancienne, (
        'des trames sont parties vers la station ABANDONNÉE après recochage : %r'
        % vers_ancienne)


def test_aucun_refus_de_demarrage_ne_precede_la_garde_de_remplacement():
    """La garde « une seule séquence à la fois » doit passer AVANT tout refus.

    Placée après le contrôle de « Activer l'émission », elle était
    court-circuitée : seqDemarrer sortait sans avoir arrêté la séquence en
    cours, qui restait vivante et invisible. C'est une propriété d'ORDRE, donc
    on la teste comme telle — un test de comportement ne peut plus l'atteindre
    depuis que le décochage arrête lui-même la séquence, et un test qui ne peut
    plus échouer ne protège rien.

    Commentaires dépouillés : les pavés d'explication citent les deux."""
    corps = _sans_commentaires(_extraire_fonction(_lire(FT8_HTML), 'seqDemarrer'))
    i_garde = corps.index("seqArreter('remplacement')")
    for refus in ('if(!txArmed)', 'return null'):
        i = corps.index(refus)
        if refus == 'return null' and i < corps.index('estIndicatif'):
            continue
    # Tous les refus qui rendent null APRÈS la validation d'entrée doivent être
    # postérieurs à la garde. Les deux refus d'entrée légitimes (indicatif
    # invalide, mode manuel) précèdent volontairement : ils n'ont pas encore
    # regardé `seq`, et refuser un appel malformé ne doit rien casser.
    i_txarmed = corps.index('if(!txArmed)')
    assert i_garde < i_txarmed, (
        "le refus « Activer l'émission » précède la garde de remplacement : "
        'un double-clic sur une autre station laisserait la séquence courante '
        'vivante et invisible')


def test_decocher_l_armement_arrete_et_nomme_la_case():
    """Le décochage doit être un ordre d'arrêt IMMÉDIAT, pas une condition que
    le prochain examen de créneau finira par remarquer.

    Sans cela, dans les 2 secondes du préavis — c'est-à-dire au moment où un
    opérateur décoche le plus souvent, juste avant que ça parte — c'était
    envoyerMessage qui rendait false, et l'arrêt passait par la raison
    générique « la trame n'est pas partie, voir le message ci-dessus », qui ne
    nomme ni la case ni où la retrouver. Le message dédié, ajouté la veille
    précisément pour la nommer, ne s'affichait donc pas.

    Commentaires dépouillés : le pavé qui explique ce câblage cite seqArreter."""
    corps = _sans_commentaires(_extraire_fonction(_lire(FT8_HTML), 'onArmChange'))
    assert 'seqArreter' in corps, (
        'onArmChange doit arrêter la séquence, pas seulement faire vieillir le '
        'jeton et attendre que quelqu\'un remarque')


# ── Une raison d'arrêt qui envoie dans un mur ──────────────────────────────

def test_sans_pilotage_radio_la_raison_ne_renvoie_pas_a_un_conseil_impossible(banc):
    """Sans CAT configuré, envoyerMessage sort AVANT la synthèse de la forme
    d'onde : rien n'est jamais joué dans la carte son. Le message d'émission
    conseille pourtant « passe en émission au micro ou en VOX » — un conseil
    que le code ne permet pas de suivre.

    Le séquenceur s'arrêtait sur « la trame n'est pas partie — voir le message
    d'émission ci-dessus », c'est-à-dire en renvoyant vers ce conseil. On tourne
    en rond. La raison doit nommer la vraie cause et la page où la corriger.

    (La question de fond — faut-il faire réellement fonctionner le VOX ? — est
    un changement du chemin d'ÉMISSION, laissé à la décision de F4GLD.)"""
    b = banc(correspondant=_correspondant(muette=True))
    b.js('NOW = 2000;')
    b.js("dernierRefusPtt = 'non_engage';"
         'envoyerMessage = function(){ return Promise.resolve(false); };')
    b.demarrer(slotEntendu=0)
    b.avancer(120000)
    et = b.etat()
    assert et['seq'] is None
    assert 'CONFIG' in et['seqEtat'], (
        "la raison doit dire OÙ corriger : %r" % et['seqEtat'])
    assert 'ci-dessus' not in et['seqEtat'], (
        'la raison renvoie encore vers le message qui conseille l\'impossible : '
        '%r' % et['seqEtat'])


# ── La table des raisons ne doit contenir que des raisons vivantes ─────────

def test_aucune_raison_declaree_n_est_morte():
    """Une raison déclarée mais jamais appelée laisse croire qu'un chemin
    d'arrêt existe encore. Un futur lecteur peut réintroduire l'appel en
    croyant compléter la table — et défaire le correctif qui l'avait
    précisément scindée en trois raisons distinctes.

    Le ternaire `seqArreter(complet ? 'a' : 'b')` est pris en compte : la
    regex cherche toute chaîne quotée dans un appel à seqArreter."""
    src = _sans_commentaires(_lire(FT8_HTML))
    i = src.index('const SEQ_RAISONS')
    bloc = src[i:src.index('\n  };', i)]
    declarees = set(re.findall(r"^\s*'([a-z0-9-]+)':", bloc, re.M))
    appelees = set(re.findall(r"seqArreter\(\s*'([a-z0-9-]+)'", src))
    appelees |= set(re.findall(r"\?\s*'([a-z0-9-]+)'\s*:\s*'([a-z0-9-]+)'", src)
                    and [x for pair in re.findall(
                        r"\?\s*'([a-z0-9-]+)'\s*:\s*'([a-z0-9-]+)'", src)
                        for x in pair])
    mortes = declarees - appelees
    assert not mortes, 'raisons déclarées et jamais appelées : %r' % sorted(mortes)
    inconnues = appelees - declarees - {'test'}
    assert not inconnues, (
        'raisons appelées mais absentes de la table (l\'écran n\'affichera '
        'rien) : %r' % sorted(inconnues))


# ═══════════════════════════════════════════════════════════════════════════
# §5. ARRÊTS — chacun doit VRAIMENT couper
# ═══════════════════════════════════════════════════════════════════════════

_GESTES_D_ARRET = [
    ('bouton STOP SÉQUENCE', "seqArreter('bouton');"),
    ("décochage de l'armement", 'txArmed = false;'),
    # Le geste reproduit ce que fait arreterRx() dans la page — et l'ORDRE
    # compte : seqArreter AVANT de baisser rxActif. Poser `rxActif = false`
    # tout seul laissait la séquence VIVANTE, parce que la garde équivalente
    # de seqExaminerCreneau est inatteignable une fois l'écoute coupée
    # (verifierCycle sort dessus, et le timer est supprimé). Ce test le
    # démontrait dès que le banc a cessé d'ignorer rxActif ; c'est
    # test_arreter_rx_appelle_bien_seqarreter qui tient l'autre bout, en
    # vérifiant que la page fait bien ces deux gestes-là.
    ("arrêt de l'écoute",
     "seqArreter('ecoute-arretee'); annulerEmissionsProgrammees(); rxActif = false;"),
    ('retour au niveau manuel', "seqNiveau = 'manuel';"),
    ('passage en niveau assisté', "seqNiveau = 'assiste';"),
    # Échap et STOP ÉMISSION passent par la chaîne de sûreté existante
    # (logx_ft8.html:1503 stopEmission, 1519 Échap). Le séquenceur doit s'y
    # raccrocher : couper l'émission SANS arrêter la séquence relancerait une
    # trame au créneau suivant, ce qui revient à ignorer l'ordre de l'opérateur.
    ('Échap / STOP ÉMISSION', "annulerEmissionsProgrammees(); seqArreter('stop-emission');"),
]


@pytest.mark.parametrize('nom,geste', _GESTES_D_ARRET)
@pytest.mark.parametrize('instant,situation', [
    (5000, "pendant l'ATTENTE du créneau (trame programmée, pas commencée)"),
    (20000, 'pendant la TRAME (émission déjà en cours)'),
])
def test_chaque_chemin_d_arret_coupe_vraiment(banc, nom, geste, instant, situation):
    """Chaque arrêt est testé DEUX FOIS : pendant l'attente du créneau, et
    pendant la trame elle-même.

    L'attente du créneau est la fenêtre où une version naïve laisse la trame
    partir quand même : l'attente est déjà engagée dans un setTimeout que plus
    rien ne surveille (c'est exactement l'état du fichier aujourd'hui, écart (a)
    de l'en-tête). Ne tester que « pendant la trame » donnerait une fausse
    assurance sur le cas le plus fréquent — l'opérateur appuie sur STOP entre
    deux émissions, pas au milieu."""
    b = banc(correspondant=_correspondant(muette=True))
    b.js('NOW = 2000;')
    b.demarrer()
    b.avancer(instant)
    t_ordre = b.etat()['now']
    b.js(geste)
    b.avancer(600000)

    et = b.etat()
    tardives = [e for e in et['demarrees'] if e['debutMs'] > t_ordre]
    assert not tardives, (
        '%s (%s) : %d émission(s) ont DÉMARRÉ après l\'ordre d\'arrêt (t=%d).\n'
        'Émissions tardives : %r' % (nom, situation, len(tardives), t_ordre, tardives))
    assert et['seq'] is None, '%s (%s) : la séquence est restée active' % (nom, situation)


def test_arret_annule_l_emission_programmee_pas_seulement_la_suivante(banc):
    """L'arrêt doit passer par annulerEmissionsProgrammees() : incrémenter le
    jeton est le SEUL moyen d'empêcher une trame déjà en attente de son créneau
    de partir. « Plus d'émission après » ne le prouve pas (la machine a pu
    simplement ne rien reprogrammer) : on vérifie donc explicitement que le
    jeton a bougé."""
    b = banc(correspondant=_correspondant(muette=True))
    b.js('NOW = 2000;')
    b.demarrer()
    b.avancer(5000)                      # trame du créneau 15000 programmée, pas partie
    avant = b.etat()['generationTx']
    b.js("seqArreter('test');")
    apres = b.etat()['generationTx']
    assert apres > avant, (
        "seqArreter() n'a pas appelé annulerEmissionsProgrammees() : la trame "
        "déjà programmée partira quand même à son créneau, alors que "
        "l'opérateur a demandé l'arrêt.")


def test_temporisation_d_arret_ne_tue_pas_la_sequence_suivante(banc):
    """Défaut confirmé par la revue : une temporisation d'arrêt suivait la
    variable GLOBALE de séquence et pouvait tuer la séquence SUIVANTE. On
    arrête une séquence, on en démarre aussitôt une autre, et on vérifie que la
    seconde survit ET émet."""
    b = banc(correspondant=_correspondant(muette=True))
    b.js('NOW = 2000;')
    b.demarrer()
    b.avancer(5000)
    b.js("seqArreter('premiere');")
    b.demarrer(TIERS, grille='JO31')
    jeton2 = b.etat()['seq']['jeton']
    b.avancer(300000)

    et = b.etat()
    assert et['seq'] is not None, \
        'la seconde séquence a été tuée par une temporisation de la première'
    assert et['seq']['jeton'] == jeton2, 'le jeton de la seconde séquence a changé'
    assert any(e['texte'].startswith(TIERS + ' ') for e in et['parties']), \
        'la seconde séquence n\'a jamais émis : %r' % ([e['texte'] for e in et['parties']],)


# ═══════════════════════════════════════════════════════════════════════════
# §6. RÉ-ENTRANCE — une seule émission en vol
# ═══════════════════════════════════════════════════════════════════════════

def test_double_clic_ne_produit_jamais_deux_emissions_dans_un_creneau(banc):
    """Défaut confirmé : sans garde de ré-entrance, un double-clic pendant une
    séquence produisait DEUX formes d'onde simultanées — deux signaux FT8
    superposés dans le même créneau, sur la même fréquence. Sur l'air, c'est un
    brouillage causé par sa propre station, et invisible pour celui qui le
    provoque."""
    b = banc(correspondant=_correspondant())
    b.js('NOW = 2000;')
    b.demarrer()
    b.demarrer()                          # le 2e clic du double-clic
    b.avancer(400000)

    creneaux = b.creneaux_emis()
    assert len(creneaux) == len(set(creneaux)), \
        'deux formes d\'onde dans le même créneau : %r' % (b.etat()['parties'],)


def test_double_clic_sur_une_autre_station_ne_laisse_qu_une_sequence(banc):
    """seqDemarrer() doit refuser, ou arrêter proprement l'ancienne. Les deux
    comportements sont acceptables ; ce qui ne l'est pas, c'est deux séquences
    qui émettent en parallèle vers deux stations différentes."""
    b = banc(correspondant=_correspondant(muette=True))
    b.js('NOW = 2000;')
    b.demarrer()
    b.demarrer(TIERS, grille='JO31')
    b.avancer(300000)

    et = b.etat()
    cibles = {e['texte'].split(' ')[0] for e in et['parties']}
    assert len(cibles) <= 1, \
        'deux séquences ont émis en parallèle : %r' % ([e['texte'] for e in et['parties']],)
    creneaux = [e['slot'] for e in et['parties']]
    assert len(creneaux) == len(set(creneaux))


def test_une_continuation_tardive_n_agit_pas_sur_la_sequence_suivante(banc):
    """« Toute continuation asynchrone doit vérifier que le jeton est toujours
    celui de sa séquence. » On mémorise le jeton de la 1re séquence, on la
    remplace, et on vérifie que le jeton a changé — sans quoi rien ne distingue
    une continuation de la 1re d'une continuation de la 2e, et un `.then()`
    oublié en vol peut loguer ou arrêter la mauvaise séquence."""
    b = banc(correspondant=_correspondant(muette=True))
    b.js('NOW = 2000;')
    b.demarrer()
    j1 = b.etat()['seq']['jeton']
    b.js("seqArreter('remplacement');")
    b.demarrer(TIERS, grille='JO31')
    j2 = b.etat()['seq']['jeton']
    assert j1 != j2, (
        'deux séquences successives portent le même jeton (%r) : une '
        'continuation tardive de la première agira sur la seconde.' % (j1,))


# ═══════════════════════════════════════════════════════════════════════════
# §7. LE MESSAGE ÉMIS EST CONSTRUIT, JAMAIS REPRIS
# ═══════════════════════════════════════════════════════════════════════════

def test_message_emis_jamais_repris_verbatim_d_un_decodage(banc):
    """Défaut confirmé, et le plus grave sur l'air : le message émis venait de
    proposerReponse() (chemin MANUEL), si bien qu'un double-clic sur un message
    entre TIERS l'émettait VERBATIM — signé de l'indicatif d'autrui. On place
    ici le même piège à la fois dans le champ de saisie ET dans le décodage."""
    poubelle = f'{TIERS} {QUATRIEME} RR73'
    b = banc(scenario={
        str(SLOT_MS * 2): [{'text': poubelle, 'snr': SNR_ELLE_CHEZ_NOUS}],
    })
    b.js('NOW = 2000;')
    b.js('document.getElementById("txText").value = %s;' % json.dumps(poubelle))
    b.demarrer()
    b.avancer(300000)

    parties = b.emissions_parties()
    assert parties, 'aucune émission : le scénario n\'a pas démarré'
    for p in parties:
        assert p != poubelle.upper(), 'un décodage a été émis VERBATIM : %r' % (p,)
        jetons = p.split(' ')
        assert jetons[0] == CIBLE, \
            'le 1er jeton doit être la cible, pas autre chose : %r' % (p,)
        assert jetons[1] == MOI, \
            "le message doit être signé de NOTRE indicatif, jamais de celui " \
            "d'un tiers : %r" % (p,)


def test_champ_de_saisie_reecrit_ne_change_pas_ce_qui_part(banc):
    """Défaut confirmé : un clic simple pendant une séquence réécrivait le champ
    de message, et la relance émettait ce contenu. Le champ est un AFFICHAGE
    d'information ; la source de vérité est l'état de séquence.

    RÉÉCRIT après la revue adversariale du 18/08/2026. La réécriture était
    faite à t=35000, un instant où seqProgrammer réécrit le champ de toute
    façon avant le départ : un séquenceur qui relirait le champ AU MOMENT
    D'ÉMETTRE — c'est-à-dire le défaut historique lui-même — passait le test.
    Reproduit : en remplaçant envoyerMessage(texte) par
    envoyerMessage(document.getElementById('txText').value), les 47 tests
    restaient verts.

    La fenêtre dangereuse est APRÈS le préavis et AVANT le départ. On ne la
    fige pas en dur : on DÉCOUVRE d'abord les créneaux réellement occupés, puis
    on réécrit à (créneau visé − 500 ms). Un instant écrit en dur redeviendrait
    faux à la première modification de cadence — c'est précisément ce qui est
    arrivé."""
    # 1re passe : à quels créneaux la machine émet-elle réellement ?
    reco = banc(correspondant=_correspondant(muette=True))
    reco.js('NOW = 2000;')
    reco.demarrer()
    reco.avancer(200000)
    creneaux = reco.creneaux_emis()
    assert len(creneaux) >= 3, 'pas assez d\'émissions pour viser une fenêtre'
    vise = creneaux[2]

    # 2e passe : on réécrit le champ 500 ms AVANT le départ de cette trame,
    # donc après le préavis qui l'a programmée. Aucune réécriture légitime du
    # champ ne peut plus effacer notre poubelle avant l'émission.
    b = banc(correspondant=_correspondant(muette=True))
    b.js('NOW = 2000;')
    b.demarrer()
    b.avancer(vise - 500)
    b.js('document.getElementById("txText").value = "N\'IMPORTE QUOI";')
    b.avancer(300000)

    parties = b.emissions_parties()
    assert "N'IMPORTE QUOI" not in parties, \
        'le contenu réécrit du champ de saisie est parti sur l\'air : %r' % (parties,)
    assert all(p.startswith(f'{CIBLE} {MOI} ') for p in parties), parties


def test_le_sequenceur_passe_son_texte_explicitement(banc):
    """L'autre bout du test précédent, en STRUCTURE : la région du séquenceur
    doit appeler envoyerMessage avec un argument. C'est ce qui rend le champ de
    saisie incapable d'influencer ce qui part."""
    region = _sans_commentaires(_extraire_region_sequenceur(_lire(FT8_HTML)))
    assert re.search(r'envoyerMessage\(\s*texte\s*\)', region), (
        "seqProgrammer doit passer son texte EXPLICITEMENT à envoyerMessage ; "
        'relire le champ de saisie au moment d\'émettre est le défaut '
        'historique de ce séquenceur')
    assert not re.search(r"envoyerMessage\(\s*document\.", region), (
        'le séquenceur relit le champ de saisie au moment d\'émettre')


def test_cq_dx_la_cible_est_l_indicatif_jamais_le_mot_dx(banc):
    """« CQ DX F4ABC JN15 » : sur ce message, la version précédente émettait
    littéralement « DX F4GLD JN15 » — un appel adressé à une station nommée
    « DX », qui n'existe pas. Le même piège vaut pour CQ TEST, CQ POTA, CQ EU."""
    b = banc()
    for entete in ('CQ DX', 'CQ TEST', 'CQ POTA', 'CQ EU', 'CQ'):
        texte = f'{entete} {CIBLE} {GRILLE_CIBLE}'
        cible = b.js('seqCibleDepuisDecodage(%s)' % json.dumps(texte))
        assert cible == CIBLE, \
            '%r → cible extraite %r au lieu de %r' % (texte, cible, CIBLE)


def test_message_entre_tiers_ne_demarre_aucune_sequence(banc):
    """Un message qui ne nous est pas adressé et qui n'est pas un CQ ne doit
    donner AUCUNE cible : répondre à « DL1XYZ SP9QQQ -05 » revient à s'inviter
    dans le QSO de deux autres stations."""
    b = banc()
    for texte in (f'{TIERS} {QUATRIEME} -05', f'{TIERS} {QUATRIEME} RR73',
                  f'{TIERS} {QUATRIEME} 73', f'{TIERS} {QUATRIEME} JN18'):
        assert b.js('seqCibleDepuisDecodage(%s)' % json.dumps(texte)) == '', \
            'un message entre tiers a fourni une cible : %r' % (texte,)


def test_message_qui_nous_est_adresse_donne_bien_la_cible(banc):
    """Contre-épreuve du test précédent : à force de tout refuser on obtiendrait
    un séquenceur qui ne démarre jamais, et les deux tests passeraient."""
    b = banc()
    for texte in (f'{MOI} {CIBLE} {GRILLE_CIBLE}', f'{MOI} {CIBLE} -07',
                  f'{MOI} {CIBLE} R-07', f'{MOI} {CIBLE} RRR'):
        assert b.js('seqCibleDepuisDecodage(%s)' % json.dumps(texte)) == CIBLE, \
            '%r n\'a pas donné la cible %r' % (texte, CIBLE)


# ═══════════════════════════════════════════════════════════════════════════
# §8. ANALYSE LEXICALE — RR73 n'est ni un locator ni un indicatif
# ═══════════════════════════════════════════════════════════════════════════

def test_rr73_n_est_ni_un_indicatif_ni_un_locator(banc):
    """« RR73 » satisfait /^[A-R]{2}[0-9]{2}$/ — la regex de locator de la page
    (RE_GRID, logx_ft8.html:479). Les jetons de PROTOCOLE doivent donc être
    reconnus AVANT toute regex de locator : sinon un RR73 devient une grille, et
    le QSO se poursuit puis se loggue sur une donnée fausse."""
    b = banc()
    for protocole in ('RRR', 'RR73', '73', 'R-07', 'R+03', '-07', '+03', 'CQ'):
        assert b.js('estIndicatif(%s)' % json.dumps(protocole)) is False, \
            '%r pris pour un indicatif' % (protocole,)


def test_est_indicatif_refuse_les_locators(banc):
    """Défaut confirmé : estIndicatif() acceptait les locators Maidenhead (JN15,
    KN04). Conséquence directe : une grille reçue devenait une cible, et la
    station appelait un correspondant inexistant."""
    b = banc()
    for locator in ('JN15', 'KN04', 'IO91', 'AA00', 'RR99'):
        assert b.js('estIndicatif(%s)' % json.dumps(locator)) is False, \
            '%r (locator Maidenhead) pris pour un indicatif' % (locator,)


def test_est_indicatif_accepte_les_vrais_indicatifs(banc):
    """Contre-épreuve indispensable : un estIndicatif() qui rend toujours false
    ferait passer les deux tests ci-dessus. Les formes à barre (F/DL1XYZ,
    F4ABC/P) sont incluses — ce sont des indicatifs non standards, gérés en FT8
    par la table de hachage (logx_ft8.html:651)."""
    b = banc()
    for call in (MOI, CIBLE, TIERS, QUATRIEME, 'W1AW', 'VK9XY', '9A1A',
                 'F/DL1XYZ', 'F4ABC/P'):
        assert b.js('estIndicatif(%s)' % json.dumps(call)) is True, \
            '%r refusé alors que c\'est un indicatif valide' % (call,)


# ═══════════════════════════════════════════════════════════════════════════
# §9. NIVEAUX — manuel et assisté n'émettent JAMAIS seuls
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize('niveau', ['manuel', 'assiste'])
def test_niveaux_manuel_et_assiste_n_emettent_jamais_seuls(banc, niveau):
    """Trois niveaux, décision non négociable : manuel (défaut, rien ne change),
    assisté (prépare, N'ÉMET JAMAIS SEUL), séquenceur (enchaîne et loggue). Le
    niveau assisté est le plus exposé : il fait tout SAUF émettre, donc une
    seule ligne oubliée le transforme en automate — et l'opérateur, lui, croit
    encore contrôler chaque départ."""
    b = banc(niveau=niveau, correspondant=_correspondant())
    b.js('NOW = 2000;')
    b.demarrer()
    b.avancer(300000)
    et = b.etat()
    assert not et['demarrees'], \
        'niveau « %s » : une émission est partie toute seule : %r' % (niveau, et['emissions'])
    assert not et['journal'], \
        'niveau « %s » : un QSO a été loggué automatiquement' % niveau


def test_niveau_par_defaut_est_manuel():
    """« manuel (défaut, rien ne change) » : la page ne doit pas se retrouver en
    séquenceur parce qu'une variable a été mal initialisée. On lit la valeur
    dans le source, pas dans le banc — le banc, lui, force le niveau."""
    region = _extraire_region_sequenceur(_lire(FT8_HTML))
    assert re.search(r"seqNiveau\s*=[^;\n]*'manuel'", region), \
        "seqNiveau n'est pas initialisé à 'manuel' dans la région du séquenceur"
    assert not re.search(r"seqNiveau\s*=\s*'sequenceur'\s*;", region), \
        "seqNiveau est initialisé directement sur 'sequenceur'"


# ═══════════════════════════════════════════════════════════════════════════
# §10. LE JETON D'ANNULATION DOIT EXISTER DANS LE VRAI envoyerMessage()
# ═══════════════════════════════════════════════════════════════════════════

def test_jeton_de_generation_existe_dans_envoyer_message():
    """Le banc simule la sémantique d'annulation ; ce test-ci vérifie qu'elle
    existe AUSSI dans la page. Sans lui, tous les tests d'arrêt du §5
    passeraient sur une fiction — le harnais validerait une sûreté que le
    produit n'a pas.

    RÉÉCRIT après la revue adversariale du 18/08/2026. Il cherchait
    « generationTx » et « txArmed » dans le texte BRUT de la fonction. Or le
    pavé de commentaire qui EXPLIQUE la revérification cite littéralement les
    deux noms, et il se trouve lui aussi après l'attente du créneau. On pouvait
    donc remplacer la seule ligne de contrôle réelle par « if(false) » sans
    qu'aucun des 47 tests ne bouge — reproduit, mesuré, confirmé. Le test qui
    avait pour mission d'interdire une fiction était satisfait par de la prose.

    Deux corrections : on DÉPOUILLE les commentaires, et on exige la STRUCTURE
    (une comparaison suivie d'un return) au lieu d'une simple présence de
    chaîne."""
    src = _lire(FT8_HTML)
    assert 'function annulerEmissionsProgrammees' in src, \
        'annulerEmissionsProgrammees() absente de logx_ft8.html'
    envoyer = _sans_commentaires(_extraire_fonction(src, 'envoyerMessage'))
    assert re.search(r'maGeneration\s*!==\s*generationTx', envoyer), (
        "la comparaison du jeton capturé avec le jeton courant a disparu — "
        "c'est ELLE qui empêche une trame annulée de partir, pas le commentaire "
        'qui la décrit')
    assert 'generationTx' in envoyer, \
        "envoyerMessage() n'utilise aucun jeton d'annulation"
    # Le jeton doit être capturé AVANT l'attente et comparé APRÈS : un jeton
    # seulement lu avant ne sert à rien.
    i_attente = envoyer.index('prochain - Date.now()')
    assert 'generationTx' in envoyer[:i_attente], \
        "le jeton doit être capturé AVANT l'attente du créneau"
    assert 'generationTx' in envoyer[i_attente:], \
        "le jeton doit être REVÉRIFIÉ APRÈS l'attente du créneau — c'est la " \
        "seule ligne qui empêche une trame annulée de partir"
    # Et l'armement doit être revérifié au même endroit. Trouvé en VALIDANT ce
    # banc contre une machine de référence : décocher « Activer l'émission »
    # pendant l'attente laissait partir la trame, que le séquenceur ne coupait
    # qu'au créneau suivant — 700 ms de FT8 tronqué déjà sur l'air. Le seul
    # instant où l'armement est encore d'actualité, c'est juste avant le PTT.
    assert re.search(r'txArmed', envoyer[i_attente:]), (
        "txArmed doit être REVÉRIFIÉ APRÈS l'attente du créneau : le contrôle "
        "de la première ligne date du moment où le message a été DEMANDÉ, pas "
        "du moment où il part.")
    # Et la comparaison doit RENONCER, pas seulement exister : un test qui
    # trouve la condition sans exiger le `return` laisserait passer une
    # branche vide.
    apres = envoyer[i_attente:]
    i_cond = apres.index('maGeneration')
    assert 'return' in apres[i_cond:i_cond + 400], (
        'le contrôle du jeton doit être suivi d\'un return : une condition '
        'sans effet ne protège rien')
