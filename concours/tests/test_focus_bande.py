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
    c'est ce que le classement doit reproduire."""
    classement = F.classer_bandes(
        ['14', '21'],
        spots=[_spot('21', mult=True), _spot('21', mult=True)],
        regions=[_region('Europe', '14', 95, ['14']),
                 _region('Asie', '21', 40, ['21'])],
        now=MAINTENANT)
    assert classement[0]['band'] == '21', classement


def test_une_bande_sans_rien_finit_derriere():
    classement = F.classer_bandes(
        ['14', '28'],
        spots=[_spot('14')],
        regions=[_region('Europe', '14', 60, ['14'])],
        now=MAINTENANT)
    assert classement[-1]['band'] == '28'
    assert classement[-1]['score'] == 0


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
    assert c[0]['band'] == '14'
    assert c[0]['qso_derniere_heure'] == 10
    assert 'run en cours' in c[0]['pourquoi']


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


# ─── Carrés manquants ────────────────────────────────────────────────────────

def test_les_carres_deja_travailles_sont_ecartes():
    c = F.carres_manquants([{'square': 'JN18', 'worked': True},
                            {'square': 'JN19', 'worked': False}])
    assert [x['square'] for x in c] == ['JN19']


def test_UN_CARRE_SANS_BANDE_EST_CONSERVE():
    """Il manque partout : le masquer parce qu'on regarde le 20 m priverait
    l'opérateur d'une cible valable sur cette bande aussi."""
    c = F.carres_manquants([{'square': 'JN18'}], bande='14')
    assert [x['square'] for x in c] == ['JN18']


def test_un_carre_d_une_AUTRE_bande_est_ecarte():
    c = F.carres_manquants([{'square': 'JN18', 'band': '144'}], bande='14')
    assert c == []


# ─── Robustesse : ces fonctions tournent dans un handler HTTP ────────────────

@pytest.mark.parametrize('fn,args', [
    (F.classer_bandes, ([],)),
    (F.ouverture_par_bande, (None,)),
    (F.spots_par_bande, (None,)),
    (F.qso_recents_par_bande, (None,)),
    (F.concours_actifs, (None,)),
    (F.carres_manquants, (None,)),
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
    F.carres_manquants(pourries)
