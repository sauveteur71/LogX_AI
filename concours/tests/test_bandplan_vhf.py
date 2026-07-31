# -*- coding: utf-8 -*-
"""Plan de bandes IARU R1 au-dessus de 440 MHz + contraintes 23 cm.

CE FICHIER TESTE SURTOUT LES QUATRE PIÈGES DE MODÉLISATION signalés par
l'opérateur avec la source, parce que ce sont eux qui feraient rendre au
logiciel une réponse plausible et fausse — le motif de tous les défauts de la
journée. Les chiffres eux-mêmes se relisent ; la FORME de la table, non.

  (a) la largeur de bande doit être NULLABLE : au-dessus de 1,3 GHz, la plupart
      des lignes renvoient à la réglementation nationale ;
  (b) « Sub-Regional / national band planning » est un STATUT, pas un mode :
      le ranger dans l'énumération des modes créerait un mode fantôme ;
  (c) les segments à bande étroite alternatifs sont CONDITIONNELS AU PAYS —
      une table plate ne peut pas les représenter ;
  (d) la colonne « Usage » n'est PAS normative, sauf « exclusive » (balises) :
      les centres d'activité doivent être séparés des segments.

Et la réserve qui prime sur tout le reste : le 23 cm de l'édition 2017 est
ANTÉRIEUR à la CMR-23. La décision ECC/DEC/(25)01 (27 juin 2025) impose depuis
des limites de puissance que ce plan ignore.
"""
import os
import sys

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CONCOURS not in sys.path:
    sys.path.insert(0, CONCOURS)

import logx_bandplan_vhf as bp   # noqa: E402


# ─── Cohérence de la table ───────────────────────────────────────────────────

@pytest.mark.parametrize('bande', bp.BANDES)
def test_les_segments_ne_se_chevauchent_pas(bande):
    """Deux segments qui se recouvrent rendraient segment_a() dépendant de
    l'ordre de la liste — donc arbitraire."""
    seg = bp.segments(bande)
    for a, b in zip(seg, seg[1:]):
        assert a['hi_mhz'] <= b['lo_mhz'], (a, b)


@pytest.mark.parametrize('bande', bp.BANDES)
def test_chaque_segment_a_des_bornes_croissantes(bande):
    for s in bp.segments(bande):
        assert s['lo_mhz'] < s['hi_mhz'], s


def test_aucun_mode_hors_du_vocabulaire():
    for s in bp.SEGMENTS:
        assert s['mode'] in bp.MODES, s


def test_une_bande_inconnue_rend_une_liste_vide_pas_une_erreur():
    for v in ('', None, '14', 'xyz'):
        assert bp.segments(v) == []
        assert bp.bornes(v) is None


# ─── Piège (a) : la largeur de bande est NULLABLE ───────────────────────────

def test_la_largeur_de_bande_peut_etre_NULLE():
    """`None` veut dire « fixée au niveau national », PAS « illimitée ». Un
    schéma qui exigerait un entier obligerait à inventer une valeur."""
    nationales = [s for s in bp.SEGMENTS if s['bw_hz'] is None]
    assert nationales, 'aucun segment à largeur nationale : la table est suspecte'
    # Ce n'est pas un cas marginal : plus de la moitié des lignes.
    assert len(nationales) > len(bp.SEGMENTS) / 3


def test_les_largeurs_renseignees_sont_plausibles():
    for s in bp.SEGMENTS:
        if s['bw_hz'] is not None:
            assert 100 <= s['bw_hz'] <= 200000, s


# ─── Piège (b) : le statut n'est pas un mode ────────────────────────────────

def test_la_planification_nationale_est_un_STATUT_pas_un_mode():
    """« Sub-Regional / national band planning » décrit qui décide du
    découpage, pas ce qu'on y émet. Dans l'énumération des modes, il
    produirait un mode qu'aucun filtre ne saurait traiter."""
    assert bp.STATUT_NATIONAL not in bp.MODES
    nat = [s for s in bp.SEGMENTS if s['statut'] == bp.STATUT_NATIONAL]
    assert nat, 'le segment 2300-2320 devrait porter ce statut'
    for s in nat:
        assert s['mode'] in bp.MODES, s


def test_le_2300_2320_est_bien_en_planification_nationale():
    s = bp.segment_a('2320', 2310.0)
    assert s and s['statut'] == bp.STATUT_NATIONAL, s


# ─── Piège (c) : les alternatives NB dépendent du pays ──────────────────────

def test_les_segments_NB_alternatifs_sont_hors_de_la_table_plate():
    """Une bande peut avoir deux ou trois segments à bande étroite selon que le
    principal est attribué. Une table (bande, début, fin, mode) ne peut pas
    l'exprimer sans mentir sur l'un des deux cas."""
    a = bp.alternatives_nb('2320')
    assert a is not None
    assert a['principal'] == (2320.0, 2322.0)
    assert (2304.0, 2306.0) in a['alternatives']
    assert len(a['alternatives']) == 3
    assert 'attribué' in a['condition']


def test_une_bande_sans_alternative_rend_None():
    assert bp.alternatives_nb('3400') is None
    assert bp.alternatives_nb(None) is None


def test_les_alternatives_ne_sont_PAS_declarees_comme_bande_etroite():
    """Elles ne doivent pas figurer dans la table plate AVEC un mode bande
    étroite : ce serait affirmer qu'elles valent dans tous les pays.

    PREMIER JET DE CE TEST FAUX : j'exigeais qu'elles tombent hors de tout
    segment. C'est le contraire — 2304-2306 et 2308-2310 tombent dans
    2300-2320, précisément le segment marqué « planification nationale », et
    c'est cohérent : c'est le pays qui décide d'y mettre ou non son segment
    étroit. La table dit donc « ici, c'est le pays qui tranche », ce qui est
    exactement l'information juste."""
    for lo, hi in bp.ALTERNATIVES_NB['2320']['alternatives']:
        s = bp.segment_a('2320', (lo + hi) / 2)
        if s is None:
            continue
        assert s['statut'] == bp.STATUT_NATIONAL or s['mode'] == 'SAT', (lo, s)
        assert s['bw_hz'] != 500, (
            'un segment bande étroite déclaré ici vaudrait pour tous les pays')


# ─── Piège (d) : « Usage » n'est pas normatif ───────────────────────────────

def test_les_centres_d_activite_sont_SEPARES_des_segments():
    """Le document est explicite : aucun droit à une fréquence réservée n'en
    découle. Les mêler aux segments les ferait passer pour des règles."""
    centres = bp.centres_activite()
    assert centres
    for c in centres:
        assert set(c) == {'bande', 'mhz', 'quoi'}, c
        assert 'exclusif' not in c


def test_seules_les_balises_sont_exclusives():
    """« exclusive » est le SEUL cas normatif de la colonne Usage."""
    exclusifs = [s for s in bp.SEGMENTS if s['exclusif']]
    assert exclusifs
    for s in exclusifs:
        assert 'balise' in s['note'] or s['mode'] == 'CW', s


def test_les_centres_se_filtrent_par_bande():
    assert all(c['bande'] == '10368' for c in bp.centres_activite('10368'))
    assert bp.centres_activite('bande-qui-n-existe-pas') == []


def test_un_centre_d_activite_tombe_DANS_sa_bande():
    """Contrôle croisé : un centre hors des bornes de sa bande serait une
    faute de saisie."""
    for c in bp.centres_activite():
        lo, hi = bp.bornes(c['bande'])
        assert lo <= c['mhz'] <= hi, c


# ─── Interrogation ───────────────────────────────────────────────────────────

def test_on_retrouve_le_segment_d_une_frequence():
    s = bp.segment_a('1296', 1296.100)
    assert s['mode'] == 'CW/MGM' and s['bw_hz'] == 500
    assert 'EME' in s['note']


def test_le_segment_balises_du_23cm_est_exclusif():
    s = bp.segment_a('1296', 1296.900)
    assert s['exclusif'] is True


def test_une_frequence_hors_bande_ne_rend_rien():
    assert bp.segment_a('1296', 1500.0) is None
    assert bp.segment_a('1296', 'abc') is None


# ─── 23 cm : la couche normative qui prime sur le plan de 2017 ──────────────

def test_le_23cm_a_des_limites_de_PUISSANCE_depuis_la_CMR_23():
    """Le plan IARU 2017 les ignore : il est antérieur."""
    c = bp.contraintes_puissance(1296.100)
    assert c is not None
    assert c['max_dbw'] == 17.0
    assert c['grandeur'] == 'puissance_emetteur'


@pytest.mark.parametrize('mhz,attendu_dbw,grandeur', [
    (1260.0, -17.0, 'eirp'),
    (1290.0, -17.0, 'eirp'),
    (1296.5, 17.0, 'puissance_emetteur'),
    (1299.0, 22.0, 'puissance_emetteur'),
])
def test_les_paliers_de_puissance_du_23cm(mhz, attendu_dbw, grandeur):
    c = bp.contraintes_puissance(mhz)
    assert c['max_dbw'] == attendu_dbw and c['grandeur'] == grandeur


def test_EIRP_ET_PUISSANCE_EMETTEUR_NE_SE_CONFONDENT_PAS():
    """Deux grandeurs différentes : sans le gain d'antenne elles ne se
    comparent pas. Les mélanger donnerait un chiffre faux de plusieurs
    dizaines de dB — d'où le champ `grandeur`, obligatoire."""
    for f in (1260.0, 1296.5, 1299.0):
        assert bp.contraintes_puissance(f)['grandeur'] in (
            'eirp', 'puissance_emetteur')


def test_la_large_bande_a_sa_propre_limite():
    """> 150 kHz, ATV comprise : la limite est en dBW PAR MÉGAHERTZ.

    DÉFAUT QUE CE TEST A ATTRAPÉ : la fonction écrasait la note propre du
    palier par la note générale sur la période transitoire. On perdait la
    seule information qui dit à quoi le palier s'applique."""
    c = bp.contraintes_puissance(1280.0, large_bande=True)
    assert c['max_dbw_par_mhz'] == -17.0
    assert 'ATV' in c['note'], c
    assert 'transitoire' in c['note_generale'], c


def test_la_note_propre_du_palier_survit_toujours():
    """Garde-fou général : aucun palier ne doit perdre sa note."""
    for f, large in ((1280.0, True), (1296.5, False)):
        c = bp.contraintes_puissance(f, large_bande=large)
        assert 'note_generale' in c
        origine = ([x for x in (bp.CONTRAINTES_23CM['large_bande'] if large
                                else bp.CONTRAINTES_23CM['bande_etroite'])
                    if x['lo'] <= f < x['hi']] or [{}])[0]
        if 'note' in origine:
            assert c['note'] == origine['note']


def test_la_derogation_EME_est_CONDITIONNELLE():
    """27 dBW seulement avec une antenne à gain ≥ 30 dBi pointée ≥ 15° au-dessus
    de l'horizontale. Sans ces conditions, la limite ordinaire s'applique — la
    servir sans sa condition ferait dépasser en toute bonne foi."""
    eme = bp.CONTRAINTES_23CM['eme']
    assert eme['max_dbw'] == 27.0
    assert '30 dBi' in eme['conditions']
    assert '15' in eme['conditions']
    # Elle n'est PAS dans la table ordinaire : contraintes_puissance() rend la
    # limite de droit commun, pas la dérogation.
    assert bp.contraintes_puissance(1299.0)['max_dbw'] == 22.0


def test_la_montee_satellite_depend_de_l_ELEVATION():
    """1260-1262 MHz : trois paliers selon l'angle de site de l'antenne."""
    sat = bp.CONTRAINTES_23CM['satellite_montee'][0]
    paliers = sat['par_elevation']
    assert len(paliers) == 3
    assert paliers[0]['max_dbw'] == -3.0
    assert paliers[-1]['max_dbw'] == 26.8
    # Les paliers doivent couvrir 0-90° sans trou.
    assert paliers[0]['el_min'] == 0 and paliers[-1]['el_max'] == 90
    for a, b in zip(paliers, paliers[1:]):
        assert a['el_max'] == b['el_min'], (a, b)


def test_aucune_contrainte_hors_du_23cm():
    """Les autres bandes n'en ont pas — pour l'instant."""
    for f in (2320.0, 5760.0, 10368.0, 144.0):
        assert bp.contraintes_puissance(f) is None


@pytest.mark.parametrize('v', [None, '', 'abc'])
def test_une_frequence_illisible_ne_leve_pas(v):
    assert bp.contraintes_puissance(v) is None


# ─── Provenance ──────────────────────────────────────────────────────────────

def test_la_provenance_dit_2017_LANDSHUT_pas_2021():
    """LE NOM DU FICHIER MENT : il annonce 2021, l'en-tête interne et le pied
    de page disent 2017 / Landshut. Se fier au nom de fichier daterait la
    table de quatre ans de trop."""
    p = bp.provenance('iaru_r1_2017')
    assert p['edition'] == '2017'
    assert 'Landshut' in p['conference']
    assert '2021' in p['reserve'], "la réserve doit expliquer le piège du nom"


def test_la_provenance_dit_que_ce_N_EST_PAS_la_source_primaire():
    p = bp.provenance('iaru_r1_2017')
    assert p['normatif'] is False
    assert 'iaru-r1.org' in p['reserve']
    assert 'GÉNÉRIQUES' in p['reserve'] or 'générique' in p['reserve'].lower()


def test_la_decision_ECC_est_datee_et_NORMATIVE():
    p = bp.provenance('ecc_dec_25_01')
    assert p['approuve_le'] == '2025-06-27'
    assert p['normatif'] is True
    assert 'transitoire' in p['reserve']


def test_chaque_segment_porte_sa_source():
    for s in bp.SEGMENTS:
        assert bp.provenance(s['source']) is not None, s


def test_une_source_inconnue_rend_None():
    assert bp.provenance('inexistante') is None


# ─── Passerelle vers l'affichage ─────────────────────────────────────────────

def test_ATV_et_SATELLITE_n_ont_PAS_de_categorie_d_affichage():
    """Les ranger de force dans « phonie » ferait dessiner une réglette qui
    ment. Mieux vaut ne rien colorer que colorer faux."""
    assert bp.categorie_affichage('ATV/DATV') is None
    assert bp.categorie_affichage('SAT') is None


@pytest.mark.parametrize('mode,attendu', [
    ('CW', 'CW'), ('CW/MGM', 'CW'), ('MGM', 'DIGITAL'),
    ('FM/DV', 'PHONE'), ('ALL', 'PHONE'),
])
def test_la_correspondance_d_affichage(mode, attendu):
    assert bp.categorie_affichage(mode) == attendu


def test_tout_mode_du_vocabulaire_est_traite():
    """Un mode oublié rendrait None sans qu'on sache si c'est voulu."""
    for m in bp.MODES:
        assert m in bp._VERS_AFFICHAGE, m
