# -*- coding: utf-8 -*-
"""Séquenceur FT8 : il enchaîne le QSO, et surtout il SAIT S'ARRÊTER.

Demandé par F4GLD le 18/08/2026 : « pourquoi les appels ne se relancent pas
automatiquement jusqu'à obtention d'une réponse de la station que j'ai décidé
de contacter, et validation automatique du contact ? ».

C'est la fonction la plus dangereuse du logiciel : elle fait émettre la station
SANS que personne ne touche à rien. Ces tests portent donc en priorité sur les
conditions d'ARRÊT, pas sur le déroulé nominal — un séquenceur qui enchaîne mal
fait rater un QSO, un séquenceur qui ne s'arrête pas fait émettre une station
dans le vide pendant que l'opérateur est parti.

La machine à états est EXTRAITE de logx_ft8.html et exécutée telle quelle.
"""
import json
import os
import re

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FT8_HTML = os.path.join(CONCOURS, 'logx_ft8.html')

py_mini_racer = pytest.importorskip('py_mini_racer')

MOI = 'F4GLD'
GRILLE = 'JN15'
CIBLE = 'YT2DZB'


def _lire():
    with open(FT8_HTML, encoding='utf-8') as f:
        return f.read()


def _fonction(src, nom):
    for motif in ('function ' + nom, 'window.' + nom + ' ='):
        d = src.find(motif)
        if d >= 0:
            break
    assert d >= 0, f'{nom} introuvable'
    d = src.rfind('\n', 0, d) + 1
    prof, i = 0, src.index('{', d)
    while True:
        if src[i] == '{':
            prof += 1
        elif src[i] == '}':
            prof -= 1
            if prof == 0:
                return src[d:i + 1]
        i += 1


def _ctx(niveau='sequenceur', arme=True):
    src = _lire()
    ctx = py_mini_racer.MiniRacer()
    ctx.eval("""
      var __envois = [];        // chaque appel à envoyerMessage()
      var __logs = [];          // chaque QSO loggué
      var __txText = {value: ''};
      var __status = {textContent: '', className: ''};
      var myCall = '%s', myGrid = '%s';
      var txArmed = %s;
      var __niveau = '%s';
      var __relances = '0';   // 0 = jusqu'à confirmation, le défaut
      var localStorage = {
        getItem: function(k){
          return k === 'logx_ft8_relances' ? __relances : __niveau;
        },
        setItem: function(k, v){
          if(k === 'logx_ft8_relances') __relances = v; else __niveau = v;
        },
      };
      var document = { getElementById: function(id){
        if(id === 'txText') return __txText;
        if(id === 'txStatus') return __status;
        return null;   // seqEtat/seqStopBtn absents : majPanneauSeq doit tenir
      }};
      // envoyerMessage rend une PROMESSE dans le vrai code (il attend le
      // créneau). Le bouchon la résout tout de suite, mais garde la forme :
      // seqEmettre s'appuie dessus pour libérer le verrou `enVol`.
      function envoyerMessage(){ __envois.push(__txText.value); return Promise.resolve(); }
      var generationTx = 0;
      function annulerEmissionsProgrammees(){ generationTx++; }
      function setInterval(){ return 0; }
      function clearInterval(){}
      function offrirLogQso(call, infos){ __logs.push({call: call, infos: infos || {}}); }
      function gridVersLatLon(g){ return g ? {lat: 45, lon: 5} : null; }
      function distanceKm(){ return 1350; }
      var window = {};
    """ % (MOI, GRILLE, 'true' if arme else 'false', niveau))
    src_js = src
    for nom in ('niveauSeq', 'seqArreter', 'majPanneauSeq', 'seqEmettre',
                'seqArreterApresEmission', 'seqDemarrer',
                'seqExaminerCreneau', 'seqLoguer', 'estIndicatif',
                'cibleDepuisMessage'):
        ctx.eval(_fonction(src_js, nom))
    ctx.eval(re.search(r'const NIVEAUX_SEQ = \[[^\]]*\];', src_js).group(0)
             .replace('const', 'var', 1))
    ctx.eval(re.search(r'const SEQ_RELANCES_DEFAUT = \d+;', src_js).group(0)
             .replace('const', 'var', 1))
    ctx.eval(_fonction(src_js, 'relancesMax'))
    ctx.eval(re.search(r'const RE_INDICATIF = [^;]+;', src_js).group(0)
             .replace('const', 'var', 1))
    ctx.eval(re.search(r'const JETONS_NON_INDICATIF = new Set\(\[.*?\]\);',
                       src_js, re.S).group(0).replace('const', 'var', 1))
    ctx.eval('var seq = null;')
    return ctx


def _etat(ctx):
    return json.loads(ctx.eval(
        'JSON.stringify({envois: __envois, logs: __logs, '
        'actif: !!seq, etape: seq ? seq.etape : null, '
        'relances: seq ? seq.relances : 0, statut: __status.textContent})'))


def _creneau(ctx, messages):
    ctx.eval('seqExaminerCreneau(%s);' % json.dumps(messages))


# ─── Déroulé nominal ────────────────────────────────────────────────────────

def test_le_qso_s_enchaine_et_se_loggue_tout_seul():
    """La demande, de bout en bout : on appelle, il répond avec sa grille, on
    envoie le report, il accuse, on accuse, il dit 73 — et le QSO part au
    carnet sans qu'on ait rien touché."""
    ctx = _ctx()
    ctx.eval("seqDemarrer('%s', '%s %s %s');" % (CIBLE, CIBLE, MOI, GRILLE))
    assert _etat(ctx)['envois'] == ['YT2DZB F4GLD JN15']

    _creneau(ctx, ['%s %s KN04' % (MOI, CIBLE)])          # il répond, grille
    assert _etat(ctx)['envois'][-1] == 'YT2DZB F4GLD -10'

    # « R-10 » et non « RRR » : la séquence FT8 standard accuse ET renvoie le
    # report. Répondre RRR sautait l'étape Tx3, si bien qu'aucun report n'était
    # jamais émis — alors que le carnet enregistrait rst_sent = « -10 ».
    _creneau(ctx, ['%s %s R-12' % (MOI, CIBLE)])          # il accuse notre report
    assert _etat(ctx)['envois'][-1] == 'YT2DZB F4GLD R-10'

    _creneau(ctx, ['%s %s RR73' % (MOI, CIBLE)])          # il conclut
    e = _etat(ctx)
    assert e['envois'][-1] == 'YT2DZB F4GLD 73'
    assert [x['call'] for x in e['logs']] == [CIBLE], 'le QSO doit être loggué automatiquement'


def test_un_73_recu_termine_et_loggue_sans_reemettre():
    """Quand c'est LUI qui dit 73, le QSO est complet : il ne reste rien à
    émettre. Réémettre serait polluer la fréquence pour rien."""
    ctx = _ctx()
    ctx.eval("seqDemarrer('%s', 'X');" % CIBLE)
    avant = len(_etat(ctx)['envois'])
    _creneau(ctx, ['%s %s 73' % (MOI, CIBLE)])
    e = _etat(ctx)
    assert [x['call'] for x in e['logs']] == [CIBLE]
    assert e['actif'] is False, 'la séquence doit être terminée'
    assert len(e['envois']) == avant, 'aucune émission supplémentaire'


# ─── LES ARRÊTS — le cœur du sujet ──────────────────────────────────────────

def test_il_abandonne_apres_le_nombre_de_relances_prevu():
    """Sans réponse, il relance — mais PAS indéfiniment. Une station qui
    appelle dans le vide pendant que l'opérateur est parti faire un café,
    c'est exactement ce qu'on veut empêcher."""
    ctx = _ctx()
    ctx.eval("__relances = '3';")   # plafond explicitement demandé
    ctx.eval("seqDemarrer('%s', 'APPEL');" % CIBLE)
    maxi = 3
    for _ in range(maxi + 1):
        _creneau(ctx, ['CQ SV5BYP KM46'])   # du trafic, mais rien pour nous
    e = _etat(ctx)
    assert e['actif'] is False, f'doit abandonner après {maxi} relances'
    assert 'relance' in e['statut'].lower() or 'réponse' in e['statut'].lower(), e['statut']
    # 1 appel initial + au plus maxi relances, jamais plus.
    assert len(e['envois']) <= maxi + 1


def test_il_abandonne_si_la_station_repond_a_quelqu_un_d_autre():
    """Elle nous a doublés. Continuer à l'appeler brouillerait un QSO en
    cours — c'est une question de savoir-vivre autant que de technique."""
    ctx = _ctx()
    ctx.eval("seqDemarrer('%s', 'APPEL');" % CIBLE)
    avant = len(_etat(ctx)['envois'])
    _creneau(ctx, ['ON4FHM %s -05' % CIBLE])
    e = _etat(ctx)
    assert e['actif'] is False
    assert 'autre' in e['statut'].lower(), e['statut']
    assert len(e['envois']) == avant, 'aucune émission après avoir été doublé'


def test_desarmer_l_emission_arrete_la_sequence():
    """Décocher « Activer l'émission » est un ordre d'arrêt aussi net que le
    bouton STOP."""
    ctx = _ctx()
    ctx.eval("seqDemarrer('%s', 'APPEL');" % CIBLE)
    ctx.eval('txArmed = false;')
    avant = len(_etat(ctx)['envois'])
    _creneau(ctx, ['%s %s KN04' % (MOI, CIBLE)])
    e = _etat(ctx)
    assert e['actif'] is False
    assert len(e['envois']) == avant


def test_changer_de_niveau_arrete_la_sequence():
    ctx = _ctx()
    ctx.eval("seqDemarrer('%s', 'APPEL');" % CIBLE)
    ctx.eval("__niveau = 'manuel';")
    avant = len(_etat(ctx)['envois'])
    _creneau(ctx, ['%s %s KN04' % (MOI, CIBLE)])
    e = _etat(ctx)
    assert e['actif'] is False
    assert len(e['envois']) == avant


# ─── Conditions de DÉMARRAGE ────────────────────────────────────────────────

def test_il_ne_demarre_pas_sans_emission_armee_et_le_dit():
    """La case « Activer l'émission » reste LE geste explicite qui autorise
    l'émission. Et le refus doit être expliqué : un séquenceur qui ne démarre
    pas en silence est pire qu'un séquenceur absent."""
    ctx = _ctx(arme=False)
    ok = ctx.eval("seqDemarrer('%s', 'APPEL');" % CIBLE)
    e = _etat(ctx)
    assert ok is False
    assert e['actif'] is False
    assert e['envois'] == []
    assert 'mission' in e['statut'], e['statut']


def test_il_ne_demarre_pas_au_niveau_manuel():
    """Niveau par défaut : rien ne change pour qui n'a rien demandé."""
    ctx = _ctx(niveau='manuel')
    assert ctx.eval("seqDemarrer('%s', 'APPEL');" % CIBLE) is False
    assert _etat(ctx)['envois'] == []


def test_il_ne_demarre_pas_au_niveau_assiste():
    """« Assisté » prépare la réponse mais n'émet JAMAIS de lui-même — c'est
    tout ce qui le distingue du niveau automatique."""
    ctx = _ctx(niveau='assiste')
    assert ctx.eval("seqDemarrer('%s', 'APPEL');" % CIBLE) is False
    assert _etat(ctx)['envois'] == []


def test_il_ne_demarre_pas_sans_indicatif():
    ctx = _ctx()
    ctx.eval("myCall = '';")
    assert ctx.eval("seqDemarrer('%s', 'APPEL');" % CIBLE) is False
    assert 'CONFIG' in _etat(ctx)['statut']


# ─── Ce qu'il doit IGNORER ──────────────────────────────────────────────────

def test_il_ignore_les_appels_d_autres_stations_vers_nous():
    """On ne mène qu'UN QSO à la fois, comme un opérateur. Un appel d'une
    troisième station ne doit ni détourner la séquence, ni compter comme une
    réponse de la cible."""
    ctx = _ctx()
    ctx.eval("seqDemarrer('%s', 'APPEL');" % CIBLE)
    _creneau(ctx, ['%s I80HQ JN33' % MOI])   # quelqu'un d'autre nous appelle
    e = _etat(ctx)
    assert e['actif'] is True, 'la séquence continue vers sa cible'
    assert e['relances'] == 1, 'ce créneau compte comme sans réponse'
    assert all(CIBLE in env or env == 'APPEL' for env in e['envois'])


def test_il_ignore_le_trafic_qui_ne_le_concerne_pas():
    ctx = _ctx()
    ctx.eval("seqDemarrer('%s', 'APPEL');" % CIBLE)
    _creneau(ctx, ['CQ SV5BYP KM46', 'TA3KJ SP6FME JO90', 'M7GDQ 9A1CCB R-21'])
    assert _etat(ctx)['actif'] is True


def test_une_reponse_remet_le_compteur_de_relances_a_zero():
    """Un QSO qui progresse ne doit pas être coupé par un compteur hérité des
    tentatives d'appel initiales."""
    ctx = _ctx()
    ctx.eval("seqDemarrer('%s', 'APPEL');" % CIBLE)
    _creneau(ctx, ['CQ SV5BYP KM46'])
    assert _etat(ctx)['relances'] == 1
    _creneau(ctx, ['%s %s KN04' % (MOI, CIBLE)])
    assert _etat(ctx)['relances'] == 0


# ─── Câblage dans la page ───────────────────────────────────────────────────

def test_le_stop_emission_coupe_aussi_le_sequenceur():
    """Sinon le bouton n'aurait coupé que le message en cours, et le
    séquenceur aurait replanifié une émission au créneau suivant. « Arrêter »
    doit vouloir dire arrêter."""
    corps = _fonction(_lire(), 'stopEmission')
    assert 'seqArreter' in corps
    assert corps.index('seqArreter') < corps.index('relacherPtt'), \
        'le séquenceur doit être coupé AVANT le relâchement du PTT'


def test_arreter_l_ecoute_coupe_le_sequenceur():
    """Sans décodage il ne verrait plus ni les réponses ni le moment
    d'abandonner : il émettrait à l'aveugle."""
    assert 'seqArreter' in _fonction(_lire(), 'arreterRx')


def test_desarmer_coupe_le_sequenceur_dans_le_gestionnaire():
    assert 'seqArreter' in _fonction(_lire(), 'onArmChange')


def test_le_sequenceur_est_branche_sur_le_cycle_de_decodage():
    src = _lire()
    assert 'seqExaminerCreneau(results.map' in src


def test_la_commande_est_sur_la_page_et_jamais_expert_only():
    """Celui qui a activé une émission automatique doit pouvoir l'arrêter sans
    changer de page ni chercher un réglage."""
    src = _lire()
    i = src.index('id="seqNiveau"')
    bloc = src[i - 400:i + 800]
    # On teste les vraies CLASSES, pas la présence du mot : le commentaire qui
    # justifie ce choix contient lui-même « expert-only » et faisait échouer
    # une première version de ce test.
    for m in re.finditer(r'class="([^"]*)"', bloc):
        assert 'expert-only' not in m.group(1), m.group(0)
    assert 'seqStopBtn' in src
    assert 'Manuel' in bloc and 'Automatique' in bloc


def test_le_niveau_par_defaut_est_manuel():
    """Personne ne doit se retrouver avec une émission automatique sans
    l'avoir demandée — y compris après une mise à jour."""
    corps = _fonction(_lire(), 'niveauSeq')
    assert "return 'manuel'" in corps
    assert corps.count("'manuel'") >= 2, 'manuel doit être le repli ET le défaut'


def test_aucune_sequence_ne_reprend_au_rechargement():
    """Le NIVEAU survit au rechargement (sinon l'opérateur ne comprendrait pas
    pourquoi plus rien ne s'enchaîne), mais aucune séquence en cours ne
    redémarre : recharger la page arrête toute émission automatique."""
    src = _lire()
    assert 'sel.value = niveauSeq()' in src
    assert 'seqDemarrer' not in src[src.index('chargerIdentite();'):
                                    src.index('chargerIdentite();') + 600]


# ─── Le piège RR73, trouvé par ces tests ────────────────────────────────────

def test_rr73_est_traite_comme_un_message_pas_comme_un_locator():
    """« RR73 » est à la fois un jeton de protocole FT8 ET un locator
    Maidenhead parfaitement valide : R et R sont dans [A-R], 7 et 3 sont des
    chiffres. La regex de locator étant testée en premier, une station qui
    concluait par RR73 se voyait répondre « -10 », le QSO n'était jamais
    loggué, et on la relançait dans le vide.

    Défaut PRÉEXISTANT — il était déjà dans proposerReponse(), donc dans le
    chemin manuel, avant que le séquenceur n'existe. Trouvé par ce test, pas
    par lecture."""
    ctx = _ctx()
    ctx.eval("seqDemarrer('%s', 'APPEL');" % CIBLE)
    _creneau(ctx, ['%s %s RR73' % (MOI, CIBLE)])
    e = _etat(ctx)
    assert e['envois'][-1] == 'YT2DZB F4GLD 73', e['envois']
    assert [x['call'] for x in e['logs']] == [CIBLE], 'le QSO doit être loggué'


def test_le_chemin_manuel_a_le_meme_ordre_de_decision():
    """Les deux arbres doivent rester alignés : un QSO mené à la main et un QSO
    séquencé produisent les mêmes messages. C'est aussi ce qui garantit que le
    correctif RR73 a bien été appliqué DES DEUX CÔTÉS."""
    corps = _fonction(_lire(), 'proposerReponse')
    i_jeton = corps.index("extra === 'RRR'")
    i_locator = corps.index('[A-R]{2}[0-9]{2}')
    assert i_jeton < i_locator, \
        'les jetons de protocole doivent être testés AVANT la regex de locator'


# ─── Un log AUTOMATIQUE ne doit pas être un log APPAUVRI ────────────────────

def test_le_log_automatique_emporte_les_reports_et_la_grille():
    """F4GLD a tranché « log automatique ! ». Raison de plus pour que le QSO
    archivé soit COMPLET : personne ne relira une ligne enregistrée toute
    seule pour y remettre à la main ce que le logiciel avait sous les yeux.

    C'est la même faute que le lot 2 vient de corriger ailleurs (nom et QTH
    reçus de l'annuaire, affichés, puis jetés à l'enregistrement)."""
    ctx = _ctx()
    ctx.eval("seqDemarrer('%s', 'APPEL');" % CIBLE)
    _creneau(ctx, ['%s %s KN04' % (MOI, CIBLE)])      # sa grille
    _creneau(ctx, ['%s %s R-12' % (MOI, CIBLE)])      # son report
    _creneau(ctx, ['%s %s RR73' % (MOI, CIBLE)])      # il conclut
    infos = _etat(ctx)['logs'][-1]['infos']
    assert infos['locator'] == 'KN04', infos
    assert infos['rst_rcvd'] == '-12', infos
    assert infos['rst_sent'] == '-10', infos
    assert infos['dist'] > 0, 'la distance doit être calculée depuis les deux locators'


def test_le_R_du_report_recu_est_retire():
    """« R-12 » est un accusé de réception PLUS un report : le carnet attend le
    report seul, pas le préfixe de protocole."""
    ctx = _ctx()
    ctx.eval("seqDemarrer('%s', 'APPEL');" % CIBLE)
    _creneau(ctx, ['%s %s R-05' % (MOI, CIBLE)])
    _creneau(ctx, ['%s %s 73' % (MOI, CIBLE)])
    assert _etat(ctx)['logs'][-1]['infos']['rst_rcvd'] == '-05'


def test_le_chemin_manuel_loggue_toujours_sans_infos():
    """offrirLogQso() garde un second argument OPTIONNEL : le chemin manuel
    l'appelle sans, et ne doit pas casser pour autant."""
    src = _lire()
    assert 'function offrirLogQso(call, infos)' in src
    assert 'qsoInfos = infos || {}' in src
    corps = _fonction(src, 'proposerReponse')
    assert 'offrirLogQso(de)' in corps, 'appel à un seul argument conservé'


# ─── « Relance automatique jusqu'à confirmation du contact » ────────────────

def test_par_defaut_il_relance_sans_plafond():
    """Demandé explicitement par F4GLD le 18/08/2026, après que j'aie proposé
    un plafond à 3 : « relance automatique jusqu'à confirmation du contact ».
    C'est sa décision d'opérateur — il est le titulaire de la station.

    Ce test vérifie qu'aucun plafond caché ne subsiste : 25 créneaux sans
    réponse, et la séquence tient toujours."""
    ctx = _ctx()
    ctx.eval("seqDemarrer('%s', 'APPEL');" % CIBLE)
    for _ in range(25):
        _creneau(ctx, ['CQ SV5BYP KM46'])
    e = _etat(ctx)
    assert e['actif'] is True, 'aucun abandon ne doit survenir sans plafond'
    assert e['relances'] == 25


def test_meme_sans_plafond_il_abandonne_si_la_cible_repond_a_un_autre():
    """LE garde-fou qui reste, et le seul qui compte vraiment : insister sur
    une station déjà en QSO brouillerait ce QSO. Il est indépendant du
    plafond de relances."""
    ctx = _ctx()
    ctx.eval("seqDemarrer('%s', 'APPEL');" % CIBLE)
    for _ in range(8):
        _creneau(ctx, ['CQ SV5BYP KM46'])
    assert _etat(ctx)['actif'] is True
    _creneau(ctx, ['ON4FHM %s -05' % CIBLE])
    assert _etat(ctx)['actif'] is False


def test_meme_sans_plafond_tous_les_arrets_manuels_fonctionnent():
    """Sans plafond, les ordres d'arrêt deviennent le seul recours : ils
    doivent marcher après un grand nombre de relances comme au premier
    créneau."""
    ctx = _ctx()
    ctx.eval("seqDemarrer('%s', 'APPEL');" % CIBLE)
    for _ in range(30):
        _creneau(ctx, ['CQ SV5BYP KM46'])
    ctx.eval('txArmed = false;')
    avant = len(_etat(ctx)['envois'])
    _creneau(ctx, ['CQ SV5BYP KM46'])
    e = _etat(ctx)
    assert e['actif'] is False
    assert len(e['envois']) == avant


def test_le_plafond_reste_disponible_pour_qui_le_veut():
    """« Jusqu'à confirmation » est le défaut, pas une obligation : le réglage
    reste offert, et prend effet sur la séquence EN COURS."""
    src = _lire()
    assert 'id="seqRelances"' in src
    corps = _fonction(src, 'changerRelances')
    assert 'seq.maxRelances = relancesMax()' in corps,         'changer le réglage doit agir tout de suite, pas au QSO suivant'


def test_la_duree_de_la_sequence_est_affichee():
    """Sans plafond, l'affichage devient le garde-fou : une séquence qui
    s'éternise doit se voir au premier coup d'œil, pas se déduire en comptant
    les lignes du tableau."""
    corps = _fonction(_lire(), 'majPanneauSeq')
    assert 'debutMs' in corps and 'min' in corps


# ─── Constats de la revue adversariale du 18/08/2026 ────────────────────────

def test_un_cq_directionnel_ne_donne_jamais_le_modificateur_pour_cible():
    """« CQ DX YT2DZB KN04 » donnait la cible « DX » : la station appelait
    indéfiniment un correspondant qui n'existe pas, et AUCUNE condition
    d'arrêt ne pouvait se déclencher puisque « DX » ne répond jamais.
    Mesuré en navigateur par la revue."""
    ctx = _ctx()
    for msg, attendu in [('CQ DX YT2DZB KN04', 'YT2DZB'),
                         ('CQ POTA YT2DZB KN04', 'YT2DZB'),
                         ('CQ TEST YT2DZB KN04', 'YT2DZB'),
                         ('CQ YT2DZB KN04', 'YT2DZB')]:
        assert ctx.eval("cibleDepuisMessage(%r)" % msg) == attendu, msg


def test_un_message_entre_tiers_ne_donne_aucune_cible():
    """Un double-clic sur « ON4FHM SQ8LSB 73 » faisait émettre EN BOUCLE un
    message signé de l'indicatif de quelqu'un d'autre."""
    ctx = _ctx()
    assert ctx.eval("cibleDepuisMessage('ON4FHM SQ8LSB 73')") == ''
    assert ctx.eval("cibleDepuisMessage('TA3KJ SP6FME JO90')") == ''


def test_un_message_qui_nous_est_adresse_donne_l_emetteur():
    ctx = _ctx()
    assert ctx.eval("cibleDepuisMessage('%s %s KN04')" % (MOI, CIBLE)) == CIBLE


def test_les_indicatifs_portables_sont_acceptes():
    ctx = _ctx()
    for c in ('F/ON4ABC', 'ON4ABC/P', 'YT2DZB'):
        assert ctx.eval("estIndicatif(%r)" % c) is True, c
    for t in ('CQ', 'DX', 'TEST', 'POTA', 'QRZ', 'DE', 'RR73'):
        assert ctx.eval("estIndicatif(%r)" % t) is False, t


def test_il_n_emet_pas_par_dessus_sa_propre_emission():
    """Il relançait à CHAQUE créneau : 86 % de rapport cyclique, aucun créneau
    d'écoute, donc il ne pouvait PAS entendre sa cible — et sans plafond, la
    séquence ne pouvait jamais se terminer. En FT8 on émet un créneau sur deux."""
    ctx = _ctx()
    ctx.eval("seqDemarrer('%s', 'APPEL');" % CIBLE)
    ctx.eval('seq.enVol = true;')          # émission en cours
    avant = len(_etat(ctx)['envois'])
    _creneau(ctx, ['CQ SV5BYP KM46'])
    assert len(_etat(ctx)['envois']) == avant, 'aucune émission par-dessus la nôtre'


def test_la_sequence_s_arrete_apres_le_73_final():
    """Après RR73 reçu et QSO loggué, l'étape restait '73' et la relance
    réémettait « 73 » à chaque créneau, indéfiniment : « jusqu'à confirmation »
    devenait « pour toujours », alors que la confirmation venait d'arriver."""
    ctx = _ctx()
    ctx.eval("seqDemarrer('%s', 'APPEL');" % CIBLE)
    _creneau(ctx, ['%s %s RR73' % (MOI, CIBLE)])
    e = _etat(ctx)
    assert e['envois'][-1] == 'YT2DZB F4GLD 73'
    assert e['etape'] in ('73', 'fini'), e['etape']
    # Le créneau suivant ne doit plus rien produire.
    apres = len(e['envois'])
    ctx.eval('if(seq) seq.enVol = false;')
    _creneau(ctx, ['CQ SV5BYP KM46'])
    assert len(_etat(ctx)['envois']) == apres, 'plus aucune émission après le 73'


def test_l_intro_ne_nie_plus_l_existence_du_sequenceur():
    """Elle affirmait encore « il n'y a pas de séquenceur automatique : un
    message part par action, jamais de QSO déroulé tout seul ». Un texte
    d'interface qui ment sur la sûreté d'émission est pire que pas de texte."""
    src = _lire()
    intro = src[src.index('class="intro"'):src.index('</p>', src.index('class="intro"'))]
    assert 'pas de séquenceur automatique' not in intro
    assert 'SÉQUENCEUR' in intro


def test_le_jeton_d_annulation_existe_et_est_verifie_apres_l_attente():
    """LE constat critique : envoyerMessage ne testait txArmed qu'AVANT son
    attente de créneau. Mesuré en navigateur : PTT ON 10,7 s APRÈS l'ordre
    d'arrêt, écran affichant « Émission coupée »."""
    corps = _fonction(_lire(), 'envoyerMessage')
    assert 'const maGeneration = generationTx' in corps
    i_attente = corps.index('prochain - Date.now()')
    i_controle = corps.index('maGeneration !== generationTx')
    assert i_attente < i_controle, "le contrôle doit venir APRÈS l'attente"
    assert '!txArmed' in corps[i_controle:i_controle + 120]


def test_tous_les_arrets_annulent_les_emissions_programmees():
    src = _lire()
    for nom in ('seqArreter', 'stopEmission', 'onArmChange', 'arreterRx'):
        assert 'annulerEmissionsProgrammees' in _fonction(src, nom), nom


def test_echap_agit_aussi_pendant_l_attente_du_creneau():
    """Il était verrouillé sur pttDemande : inopérant pendant toute l'attente
    du créneau et entre deux relances, c'est-à-dire la majorité du temps."""
    src = _lire()
    i = src.index("e.key === 'Escape'")
    bloc = src[i:i + 200]
    assert 'emissionProgrammee' in bloc and 'seq' in bloc


def test_le_bouton_stop_est_visible_pendant_l_attente():
    """Pendant l'attente, pttDemande vaut false : le bouton disparaissait alors
    qu'il y avait justement quelque chose à annuler."""
    assert 'emissionProgrammee' in _fonction(_lire(), 'majBoutonStop')


def test_le_bandeau_de_log_ne_se_rouvre_pas_apres_un_log_automatique():
    """Il se rouvrait pour le MÊME QSO avec les reports et la grille vidés :
    un clic de l'opérateur écrasait la version complète par une version pauvre."""
    corps = _fonction(_lire(), 'envoyerMessage')
    i = corps.index("parts[2] === '73'")
    assert '!seq' in corps[i - 120:i], 'la réouverture doit être exclue en mode séquencé'
