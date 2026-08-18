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
      var localStorage = {
        getItem: function(){ return __niveau; },
        setItem: function(k, v){ __niveau = v; },
      };
      var document = { getElementById: function(id){
        if(id === 'txText') return __txText;
        if(id === 'txStatus') return __status;
        return null;   // seqEtat/seqStopBtn absents : majPanneauSeq doit tenir
      }};
      function envoyerMessage(){ __envois.push(__txText.value); }
      function offrirLogQso(call){ __logs.push(call); }
      var window = {};
    """ % (MOI, GRILLE, 'true' if arme else 'false', niveau))
    src_js = src
    for nom in ('niveauSeq', 'seqArreter', 'majPanneauSeq', 'seqDemarrer',
                'seqExaminerCreneau', 'seqLoguer'):
        ctx.eval(_fonction(src_js, nom))
    ctx.eval(re.search(r'const NIVEAUX_SEQ = \[[^\]]*\];', src_js).group(0)
             .replace('const', 'var', 1))
    ctx.eval(re.search(r'const SEQ_MAX_RELANCES = \d+;', src_js).group(0)
             .replace('const', 'var', 1))
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

    _creneau(ctx, ['%s %s R-12' % (MOI, CIBLE)])          # il accuse notre report
    assert _etat(ctx)['envois'][-1] == 'YT2DZB F4GLD RRR'

    _creneau(ctx, ['%s %s RR73' % (MOI, CIBLE)])          # il conclut
    e = _etat(ctx)
    assert e['envois'][-1] == 'YT2DZB F4GLD 73'
    assert e['logs'] == [CIBLE], 'le QSO doit être loggué automatiquement'


def test_un_73_recu_termine_et_loggue_sans_reemettre():
    """Quand c'est LUI qui dit 73, le QSO est complet : il ne reste rien à
    émettre. Réémettre serait polluer la fréquence pour rien."""
    ctx = _ctx()
    ctx.eval("seqDemarrer('%s', 'X');" % CIBLE)
    avant = len(_etat(ctx)['envois'])
    _creneau(ctx, ['%s %s 73' % (MOI, CIBLE)])
    e = _etat(ctx)
    assert e['logs'] == [CIBLE]
    assert e['actif'] is False, 'la séquence doit être terminée'
    assert len(e['envois']) == avant, 'aucune émission supplémentaire'


# ─── LES ARRÊTS — le cœur du sujet ──────────────────────────────────────────

def test_il_abandonne_apres_le_nombre_de_relances_prevu():
    """Sans réponse, il relance — mais PAS indéfiniment. Une station qui
    appelle dans le vide pendant que l'opérateur est parti faire un café,
    c'est exactement ce qu'on veut empêcher."""
    ctx = _ctx()
    ctx.eval("seqDemarrer('%s', 'APPEL');" % CIBLE)
    maxi = ctx.eval('SEQ_MAX_RELANCES')
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
    assert e['logs'] == [CIBLE], 'le QSO doit être loggué'


def test_le_chemin_manuel_a_le_meme_ordre_de_decision():
    """Les deux arbres doivent rester alignés : un QSO mené à la main et un QSO
    séquencé produisent les mêmes messages. C'est aussi ce qui garantit que le
    correctif RR73 a bien été appliqué DES DEUX CÔTÉS."""
    corps = _fonction(_lire(), 'proposerReponse')
    i_jeton = corps.index("extra === 'RRR'")
    i_locator = corps.index('[A-R]{2}[0-9]{2}')
    assert i_jeton < i_locator, \
        'les jetons de protocole doivent être testés AVANT la regex de locator'
