# -*- coding: utf-8 -*-
"""FOCUS BANDE : classement des bandes + assemblage par bande (logx_focus.py).

DEMANDE UTILISATEUR : une seconde page qui rassemble tout ce que le programme
sait d'une bande choisie (cluster, carrés manquants, propagation, concours
actifs sur cette bande ET ce mode, suggestions, band map) — plus le module
complémentaire proposé en réponse : un classement de TOUTES les bandes par
opportunité, pour savoir non pas « qu'y a-t-il sur 20 m » mais « où devrais-je
être maintenant ».

CE QUI EST TESTÉ ICI : les décisions, pas l'affichage. Un classement qui met la
bande vide devant la bande à multiplicateurs est faux même si la page est
jolie ; et un filtre de mode qui fait disparaître les concours phonie parce que
le règlement écrit « PHONE » et l'opérateur « SSB » rend la page inutilisable
un jour de contest.
"""
import datetime
import os
import sys

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CONCOURS not in sys.path:
    sys.path.insert(0, CONCOURS)

import logx_focus as F   # noqa: E402

MAINTENANT = datetime.datetime(2026, 7, 31, 14, 0)


def _spot(band, mult=False, done=False, call='DL1ABC'):
    return {'call': call, 'band': band, 'new_mult': mult, 'already_done': done}


def _region(nom, best_band, best_score, open_bands):
    return {'region': nom[:2].upper(), 'region_name': nom,
            'best_band': best_band, 'best_score': best_score,
            'open_bands': open_bands}


def _qso(band, minutes_avant):
    d = MAINTENANT - datetime.timedelta(minutes=minutes_avant)
    return {'band': band, 'date': d.strftime('%Y%m%d'), 'time': d.strftime('%H:%M')}


# ─── Normalisation des bandes ────────────────────────────────────────────────

@pytest.mark.parametrize('brut,attendu', [
    ('14', '14'), ('14.0', '14'), (14, '14'), ('10.1', '10.1'),
    (' 7 ', '7'), ('', ''), (None, ''), ('20m', '20m'),
])
def test_la_bande_est_normalisee(brut, attendu):
    """« 14 » et « 14.0 » doivent désigner la MÊME bande : les spots, le log et
    le calendrier ne l'écrivent pas tous pareil, et deux graphies feraient deux
    lignes de classement pour une seule bande réelle."""
    assert F._bande(brut) == attendu


# ─── Le classement : ce qui doit primer ──────────────────────────────────────

def test_UNE_BANDE_A_MULTIPLICATEURS_PASSE_DEVANT_UNE_BANDE_VIDE_OUVERTE():
    """Le cœur du classement. Une bande grande ouverte mais sans rien dessus ne
    rapporte aucun point ; une bande moyennement ouverte avec deux
    multiplicateurs neufs, si. C'est ce qu'un opérateur fait spontanément, et
    c'est ce que le classement doit reproduire.

    La comparaison porte sur le SCORE et sur le marqueur `recommandee`, PAS sur
    la position : depuis que l'utilisateur a signale le desordre, la liste sort
    dans l'ordre des frequences et ne se reordonne plus sous le doigt."""
    classement = F.classer_bandes(
        ['14', '21'],
        spots=[_spot('21', mult=True), _spot('21', mult=True)],
        regions=[_region('Europe', '14', 95, ['14']),
                 _region('Asie', '21', 40, ['21'])],
        now=MAINTENANT)
    par_bande = {x['band']: x for x in classement}
    assert par_bande['21']['score'] > par_bande['14']['score'], classement
    assert par_bande['21']['recommandee'] is True
    assert par_bande['14']['recommandee'] is False


def test_une_bande_sans_rien_finit_derriere():
    classement = F.classer_bandes(
        ['14', '28'],
        spots=[_spot('14')],
        regions=[_region('Europe', '14', 60, ['14'])],
        now=MAINTENANT)
    par_bande = {x['band']: x for x in classement}
    assert par_bande['28']['score'] == 0
    assert par_bande['28']['recommandee'] is False


def test_un_spot_DEJA_TRAVAILLE_ne_fait_pas_monter_la_bande():
    """Sinon une bande pleine de doublons paraîtrait la plus attractive — c'est
    exactement l'inverse."""
    c = F.classer_bandes(['14'], spots=[_spot('14', done=True)] * 5, now=MAINTENANT)
    assert c[0]['score'] == 0
    assert c[0]['spots'] == 5 and c[0]['spots_exploitables'] == 0


def test_le_run_en_cours_compte():
    """On ne quitte pas une bande où l'on enchaîne les QSO pour un spot isolé
    ailleurs."""
    log = [_qso('14', m) for m in range(0, 50, 5)]   # 10 QSO dans l'heure
    c = F.classer_bandes(['14', '21'], log=log, now=MAINTENANT)
    q = {x['band']: x for x in c}['14']
    assert q['recommandee'] is True
    assert q['qso_derniere_heure'] == 10
    assert 'run en cours' in q['pourquoi']


def test_un_QSO_trop_ancien_ne_fait_pas_un_run():
    log = [_qso('14', 120)] * 10
    c = F.classer_bandes(['14'], log=log, now=MAINTENANT)
    assert c[0]['qso_derniere_heure'] == 0


def test_le_score_est_BORNE_quel_que_soit_le_nombre_de_multiplicateurs():
    """Au-delà de quelques multiplicateurs, la bande est de toute façon « à
    faire » : laisser le score enfler ferait disparaître toutes les autres du
    classement pendant des heures.

    On n'exige PAS l'égalité stricte entre 4 et 40 — un multiplicateur est
    aussi un spot exploitable, et ce second plafond se remplit un peu plus
    tard. Ce qui compte est que 40 multiplicateurs ne valent pas dix fois 4 :
    le score reste sous un maximum connu d'avance, et l'écart est marginal."""
    peu = F.classer_bandes(['14'], spots=[_spot('14', mult=True)] * 4,
                           now=MAINTENANT)[0]['score']
    beaucoup = F.classer_bandes(['14'], spots=[_spot('14', mult=True)] * 40,
                                now=MAINTENANT)[0]['score']
    plafond = F.POIDS_MULT * F.PLAFOND_MULTS + F.POIDS_SPOT * F.PLAFOND_SPOTS
    assert beaucoup <= plafond
    assert beaucoup < peu * 1.2, (peu, beaucoup)
    # ...et surtout : sans plafond, 40 multiplicateurs vaudraient 480 points.
    assert beaucoup < 0.25 * F.POIDS_MULT * 40


def test_CHAQUE_BANDE_DIT_POURQUOI():
    """Un classement qu'on ne peut pas justifier ne sera pas suivi : chaque
    ligne porte le détail de ce qui l'a fait monter."""
    c = F.classer_bandes(
        ['14'], spots=[_spot('14', mult=True), _spot('14')],
        regions=[_region('Europe', '14', 78, ['14'])], now=MAINTENANT)
    p = c[0]['pourquoi']
    assert 'mult' in p and 'ouverture 78' in p and 'spot' in p, p


def test_une_bande_sans_rien_le_dit_aussi():
    c = F.classer_bandes(['28'], now=MAINTENANT)
    assert c[0]['pourquoi'] == 'rien de signalé'


def test_l_ordre_est_stable_a_egalite():
    """Deux bandes à égalité ne doivent pas permuter d'un rafraîchissement à
    l'autre : un classement qui danse est illisible sur un écran mural."""
    a = F.classer_bandes(['28', '14', '21'], now=MAINTENANT)
    b = F.classer_bandes(['21', '28', '14'], now=MAINTENANT)
    assert [x['band'] for x in a] == [x['band'] for x in b] == ['14', '21', '28']


# ─── Ouvertures : la bande ouverte SANS être la meilleure ────────────────────

def test_une_bande_ouverte_mais_pas_la_meilleure_ne_vaut_pas_zero():
    """/data/openings ne chiffre que la MEILLEURE bande de chaque région ; les
    autres bandes ouvertes n'ont pas de score propre. Les compter à zéro ferait
    disparaître du classement une bande ouverte vers toutes les régions."""
    ouv = F.ouverture_par_bande([_region('Europe', '14', 80, ['14', '7', '3.5'])])
    assert ouv['14'][0] == 80
    assert 0 < ouv['7'][0] < 80


def test_le_meilleur_score_l_emporte_entre_regions():
    ouv = F.ouverture_par_bande([_region('Europe', '14', 40, ['14']),
                                 _region('Asie', '14', 90, ['14'])])
    assert ouv['14'][0] == 90


def test_les_regions_ouvertes_sont_nommees():
    c = F.classer_bandes(['14'], regions=[_region('Europe', '14', 80, ['14']),
                                          _region('Japon', '14', 60, ['14'])],
                         now=MAINTENANT)
    assert set(c[0]['regions_ouvertes']) == {'Europe', 'Japon'}


# ─── Concours actifs sur CETTE bande et CE mode ──────────────────────────────

def _contest(nom, h_avant_debut, duree=6, bands=None, modes=None):
    d = MAINTENANT - datetime.timedelta(hours=h_avant_debut)
    return {'id': nom, 'name': nom, 'date': d.strftime('%Y%m%d'),
            'start_utc': d.strftime('%H%M'), 'duration_h': duree,
            'bands': bands if bands is not None else [],
            'modes': modes if modes is not None else []}


def test_seuls_les_concours_EN_COURS_sortent():
    cal = [_contest('en cours', 2, 6), _contest('fini', 20, 6),
           _contest('pas commence', -5, 6)]
    noms = [c['name'] for c in F.concours_actifs(cal, now=MAINTENANT)]
    assert noms == ['en cours']


def test_le_filtre_de_bande_s_applique():
    cal = [_contest('THF', 1, 6, bands=['144', '432']),
           _contest('HF', 1, 6, bands=['14', '21'])]
    noms = [c['name'] for c in F.concours_actifs(cal, bande='14', now=MAINTENANT)]
    assert noms == ['HF']


def test_UNE_LISTE_DE_BANDES_VIDE_VEUT_DIRE_TOUTES():
    """Convention du calendrier. La traiter comme « aucune bande » ferait
    disparaître les concours les plus ouverts — précisément ceux qui
    intéressent."""
    cal = [_contest('toutes bandes', 1, 6, bands=[])]
    assert len(F.concours_actifs(cal, bande='14', now=MAINTENANT)) == 1


@pytest.mark.parametrize('mode_op,modes_reglement', [
    ('SSB', ['PHONE']), ('PHONE', ['SSB']), ('USB', ['SSB']),
    ('FT8', ['DIGI']), ('RTTY', ['DIGITAL']), ('CW', ['CW']),
])
def test_SSB_ET_PHONE_SONT_LE_MEME_MODE(mode_op, modes_reglement):
    """Les règlements écrivent tantôt « SSB » tantôt « PHONE ». Sans cette
    équivalence, choisir SSB dans la page ferait disparaître la moitié des
    concours phonie un jour de contest."""
    cal = [_contest('phonie', 1, 6, modes=modes_reglement)]
    assert len(F.concours_actifs(cal, mode=mode_op, now=MAINTENANT)) == 1


def test_un_mode_incompatible_exclut_bien():
    cal = [_contest('CW seulement', 1, 6, modes=['CW'])]
    assert F.concours_actifs(cal, mode='SSB', now=MAINTENANT) == []


def test_les_concours_sont_tries_par_fin_la_plus_proche():
    """Celui qui se termine dans une heure est plus urgent que celui qui dure
    encore deux jours."""
    cal = [_contest('long', 1, 48), _contest('court', 1, 2)]
    noms = [c['name'] for c in F.concours_actifs(cal, now=MAINTENANT)]
    assert noms == ['court', 'long']


def test_un_concours_sans_duree_ne_leve_pas():
    for d in (0, None, '', 'abc'):
        cal = [{'id': 'x', 'name': 'x', 'date': '20260731', 'start_utc': '1200',
                'duration_h': d}]
        assert F.concours_actifs(cal, now=MAINTENANT) == []


# ─── Carrés ──────────────────────────────────────────────────────────────────
# Les trois tests qui vivaient ici ont été SUPPRIMÉS, pas corrigés : ils
# validaient une forme de données que j'avais SUPPOSÉE (`square`, `worked`,
# `band`) et que /awards/carres n'a jamais eue. Des tests verts sur une
# hypothèse fausse sont pires que pas de tests : ils donnent confiance dans une
# carte qui restait vide en permanence. Les remplaçants, plus bas, travaillent
# sur la forme réelle ({'g','n','conf','bands'}) et sont accompagnés d'un
# garde-fou qui tombera si cette forme change.


# ─── Robustesse : ces fonctions tournent dans un handler HTTP ────────────────

@pytest.mark.parametrize('fn,args', [
    (F.classer_bandes, ([],)),
    (F.ouverture_par_bande, (None,)),
    (F.spots_par_bande, (None,)),
    (F.qso_recents_par_bande, (None,)),
    (F.concours_actifs, (None,)),
    (F.carres_a_faire_sur_la_bande, (None,)),
    (F.filtrer_par_mode, (None, 'CW')),
    (F.bande_depuis_freq, (None, [])),
])
def test_aucune_entree_vide_ne_leve(fn, args):
    fn(*args)


def test_des_entrees_ABIMEES_ne_levent_pas():
    """Le cluster, le calendrier et le log viennent de l'extérieur : une entrée
    malformée ne doit pas faire tomber la page entière."""
    pourries = [None, 'texte', 42, {}, {'band': None}, {'band': {}}]
    F.classer_bandes(['14'], spots=pourries, regions=pourries, log=pourries,
                     now=MAINTENANT)
    F.concours_actifs(pourries, now=MAINTENANT)
    F.carres_a_faire_sur_la_bande(pourries)
    F.filtrer_par_mode(pourries, 'CW')


# ─── QUATRE DEFAUTS TROUVES A L'ECRAN, pas par un test ───────────────────────
# L'utilisateur a ouvert la page et a dit : « si je change le mode CW ou SSB le
# cluster ne change pas, et les autres cases restent vides ». Les trois causes
# etaient dans MON code, et toutes venaient de la meme faute de methode :
# j'avais suppose la forme des donnees au lieu de la lire.

def test_LE_MODE_FILTRE_VRAIMENT_LE_CLUSTER():
    """Le cluster n'annonce pas le mode : sans deduction depuis la frequence,
    changer CW/SSB ne changeait STRICTEMENT rien a la liste affichee."""
    spots = [{'call': 'A', 'freq': 14030.0},    # segment CW
             {'call': 'B', 'freq': 14250.0},    # segment phonie
             {'call': 'C', 'freq': 14074.0}]    # segment numerique
    cw = [s['call'] for s in F.filtrer_par_mode(spots, 'CW')]
    ssb = [s['call'] for s in F.filtrer_par_mode(spots, 'SSB')]
    assert cw == ['A'], cw
    assert ssb == ['B'], ssb


def test_un_mode_annonce_par_le_spot_prime_sur_la_frequence():
    """Rien n'interdit un QSO CW dans un segment phonie : si la source annonce
    le mode, on la croit."""
    spots = [{'call': 'A', 'freq': 14250.0, 'mode': 'CW'}]
    assert [s['call'] for s in F.filtrer_par_mode(spots, 'CW')] == ['A']


def test_un_spot_AU_MODE_INDEDUCTIBLE_est_CONSERVE():
    """Mieux vaut une ligne de trop qu'une station manquee parce que sa
    frequence sort des creneaux habituels."""
    spots = [{'call': 'X', 'freq': 0}]
    assert len(F.filtrer_par_mode(spots, 'CW')) == 1


def test_sans_mode_demande_rien_n_est_filtre():
    spots = [{'call': 'A', 'freq': 14030.0}, {'call': 'B', 'freq': 14250.0}]
    assert len(F.filtrer_par_mode(spots, '')) == 2


def test_SSB_et_PHONE_restent_le_meme_mode_dans_le_filtre():
    """La table des creneaux repond « PHONE » ; l'operateur choisit « SSB »."""
    spots = [{'call': 'B', 'freq': 14250.0}]
    assert len(F.filtrer_par_mode(spots, 'SSB')) == 1


# ─── Carres : la VRAIE forme des donnees ─────────────────────────────────────

def _carre(g, bandes, conf=False):
    """Forme reelle de /awards/carres — que j'avais supposee autrement."""
    return {'g': g, 'n': 1, 'conf': conf, 'bands': bandes}


def test_UN_CARRE_DEJA_FAIT_SUR_CETTE_BANDE_N_EST_PLUS_UNE_CIBLE():
    c = F.carres_a_faire_sur_la_bande([_carre('JN18', ['14'])], bande='14')
    assert c == []


def test_un_carre_fait_AILLEURS_est_une_cible_sur_cette_bande():
    """La station existe et elle est a portee : c'est l'information utile."""
    c = F.carres_a_faire_sur_la_bande([_carre('JN18', ['144'])], bande='14')
    assert [x['square'] for x in c] == ['JN18']
    assert c[0]['bandes'] == ['144']


def test_les_carres_les_plus_actifs_d_abord():
    """Un carre fait sur cinq bandes se retrouvera plus facilement sur une
    sixieme qu'un carre vu une seule fois."""
    liste = [_carre('AA00', ['144']), _carre('BB11', ['144', '432', '1296'])]
    c = F.carres_a_faire_sur_la_bande(liste, bande='14')
    assert [x['square'] for x in c] == ['BB11', 'AA00']


def test_LA_FORME_REELLE_DES_CARRES_EST_BIEN_CELLE_ATTENDUE():
    """Garde-fou de la lecon : mon premier jet cherchait 'square'/'worked'/
    'band', qui n'existent pas — la carte restait vide en permanence, sans
    erreur. Si /awards/carres change de forme, ce test doit tomber."""
    import logx_awards as awards
    res = awards.carres_travailles([{'call': 'DL1ABC', 'band': '14',
                                     'locator': 'JN18AA', 'mode': 'SSB',
                                     'date': '20260101', 'time': '1200'}], '')
    sq = res.get('squares') or []
    assert sq, 'aucun carre produit : la forme a change'
    assert 'g' in sq[0] and 'bands' in sq[0], sq[0]


# ─── Bande deduite de la frequence ───────────────────────────────────────────

BANDES = ['1.8', '3.5', '7', '10.1', '14', '18', '21', '28', '50', '144', '432']


@pytest.mark.parametrize('freq,attendu', [
    (14074.0, '14'),      # kHz
    (14.074, '14'),       # MHz
    (7150.0, '7'),
    (10125.0, '10.1'),
    (430100.0, '432'),    # LE PIEGE : le nom de la bande n'est pas sa borne basse
    (144300.0, '144'),
])
def test_la_bande_se_deduit_de_la_frequence(freq, attendu):
    assert F.bande_depuis_freq(freq, BANDES) == attendu


@pytest.mark.parametrize('freq', [0, None, '', 'abc', 999999.0])
def test_une_frequence_inutilisable_ne_donne_aucune_bande(freq):
    assert F.bande_depuis_freq(freq, BANDES) == ''


# ─── Score d'ouverture par bande ─────────────────────────────────────────────

def test_la_meilleure_bande_d_une_region_garde_son_score_plein():
    r = _region('Europe', '14', 80, ['14', '7'])
    assert F.score_ouverture_region(r, '14') == 80


def test_une_AUTRE_bande_ouverte_a_un_score_REDUIT_mais_PAS_NUL():
    """Afficher « · » revenait a lister des regions ouvertes sans dire a quel
    point — l'information la plus utile de la carte manquait."""
    r = _region('Europe', '14', 80, ['14', '7'])
    s = F.score_ouverture_region(r, '7')
    assert 0 < s < 80


def test_une_bande_fermee_vaut_zero():
    r = _region('Europe', '14', 80, ['14'])
    assert F.score_ouverture_region(r, '28') == 0


# ─── Ordre et completude du bandeau ──────────────────────────────────────────
# DEUX REPROCHES DE L'UTILISATEUR, tous deux fondes : « pourquoi les bandes
# sont dans le desordre » et « pourquoi il manque plusieurs bandes ».

def test_LES_BANDES_SONT_DANS_L_ORDRE_DES_FREQUENCES():
    """Le bandeau etait trie par SCORE. Il se relit toutes les 15 s : les
    bandes changeaient de place sous le doigt, et retrouver « le 20 m »
    demandait de relire les huit etiquettes a chaque fois."""
    b = F.bandes_a_proposer([], [])
    valeurs = [float(x) for x in b]
    assert valeurs == sorted(valeurs), b


def test_le_CLASSEMENT_aussi_sort_dans_l_ordre_des_frequences():
    c = F.classer_bandes(['28', '14', '3.5'],
                         spots=[_spot('28', mult=True)] * 3, now=MAINTENANT)
    assert [x['band'] for x in c] == ['3.5', '14', '28']


def test_la_bande_recommandee_est_SIGNALEE_sans_changer_de_place():
    """L'information du classement ne disparait pas : elle passe de la POSITION
    a un marqueur, qui ne bouge pas quand les scores evoluent."""
    c = F.classer_bandes(['28', '14'], spots=[_spot('28', mult=True)] * 3,
                         now=MAINTENANT)
    reco = [x['band'] for x in c if x.get('recommandee')]
    assert reco == ['28'], c


def test_aucune_bande_recommandee_quand_rien_ne_se_passe():
    """Mettre en avant une bande au hasard serait un mauvais conseil."""
    c = F.classer_bandes(['14', '28'], now=MAINTENANT)
    assert not any(x.get('recommandee') for x in c)


def test_TOUT_LE_PLAN_DE_BANDES_EST_PROPOSE_meme_hors_concours():
    """La liste venait des seules bandes du concours : hors concours, ou sur un
    concours a deux bandes, la page devenait borgne."""
    b = F.bandes_a_proposer([], [])
    for attendue in ('1.8', '3.5', '7', '10.1', '14', '18', '21', '24', '28',
                     '50', '144', '432'):
        assert attendue in b, (attendue, b)


def test_les_bandes_WARC_sont_la():
    """30, 17 et 12 m manquaient dans les captures de l'utilisateur."""
    b = F.bandes_a_proposer(['14'], [])
    assert '10.1' in b and '18' in b and '24' in b


def test_une_bande_HORS_TABLE_apparait_si_un_spot_y_tombe():
    """Les hyperfrequences ne sont pas dans le plan de bandes decoupe en
    segments ; elles doivent quand meme etre atteignables quand il s'y passe
    quelque chose."""
    b = F.bandes_a_proposer([], [{'band': '1296'}])
    assert '1296' in b


def test_une_bande_du_concours_hors_table_apparait_aussi():
    b = F.bandes_a_proposer(['2320'], [])
    assert '2320' in b


def test_la_bande_DEMANDEE_apparait_meme_si_rien_ne_la_signale():
    b = F.bandes_a_proposer([], [], bande_demandee='5760')
    assert '5760' in b


def test_les_bandes_du_concours_sont_MARQUEES_sans_etre_privilegiees():
    """On doit pouvoir regarder ailleurs : le marqueur informe, il ne filtre
    pas."""
    c = F.classer_bandes(['14', '28'], now=MAINTENANT, bandes_concours=['14'])
    par_bande = {x['band']: x for x in c}
    assert par_bande['14']['dans_concours'] is True
    assert par_bande['28']['dans_concours'] is False
    assert len(c) == 2, 'la bande hors concours ne doit pas disparaitre'


def test_aucun_doublon_dans_la_liste():
    b = F.bandes_a_proposer(['14', '14.0', '144'], [{'band': '14'}], '14')
    assert len(b) == len(set(b)), b
