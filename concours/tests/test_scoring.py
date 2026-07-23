# -*- coding: utf-8 -*-
"""Tests du moteur de scoring (calc_qso_value) — barèmes vérifiés à la main
contre les règlements officiels des concours concernés."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from logx_scoring import calc_qso_value, extract_dx_locator, score_new_qso


def score(contest, dx, band, dist_km=0, dx_loc='', done_calls=None,
          done_dxcc=None, done_zones=None, my_call='F6KQJ', my_loc='JN15XC'):
    """Appel simplifié : état de log vide par défaut.
    done_calls : {indicatif: {bandes}} — structure du moteur.
    done_dxcc : clés pays cty.dat ('K', 'DL'...) ; done_zones : zones CQ (str)."""
    return calc_qso_value(contest, dx, dx_loc, my_call, my_loc,
                          done_calls or {}, set(), set(), done_zones or set(),
                          done_dxcc or set(), 0, band=band, dist_km=dist_km)


# ─── REF Rallye des Points Hauts : 1 pt/km, sans multiplicateur ──────────────

def test_rph_un_point_par_km():
    r = score('REF_RPH', 'F1ABC', '144', dist_km=387)
    assert r['direct_pts'] == 387
    assert r['total_impact'] == 387
    assert not r['new_mult']


def test_rph_doublon_meme_bande():
    r = score('REF_RPH', 'F1ABC', '144', dist_km=387,
              done_calls={'F1ABC': {'144'}})
    assert r['already_done']


def test_rph_rebond_autre_bande_autorise():
    """Le même indicatif sur une AUTRE bande est un QSO valable."""
    r = score('REF_RPH', 'F1ABC', '432', dist_km=387,
              done_calls={'F1ABC': {'144'}})
    assert not r['already_done']
    assert r['direct_pts'] == 387


# ─── European HF Championship : 1 pt/QSO, Europe uniquement ──────────────────

def test_euhfc_qso_europeen_vaut_un_point():
    r = score('EU_HF_CHAMP', 'DL1ABC', '14')
    assert r['direct_pts'] == 1
    assert r['already_done'] is False


def test_euhfc_hors_europe_invalide():
    """Règlement §1 : « Only continental Europe contacts count »."""
    r = score('EU_HF_CHAMP', 'W1AW', '14')
    assert r['direct_pts'] == 0
    assert 'hors Europe' in r['explanation']


def test_euhfc_russie_asiatique_invalide():
    """UA0 = Russie asiatique (cty.dat) — piège classique."""
    r = score('EU_HF_CHAMP', 'UA0ABC', '14')
    assert r['direct_pts'] == 0


def test_euhfc_komi_ua9x_valide():
    """Subtilité cty.dat : UA9X (Komi) est en Russie EUROPÉENNE — l'ancienne
    table à 2 caractères classait tout UA9 en Asie et jetait des QSO valides."""
    r = score('EU_HF_CHAMP', 'UA9XYZ', '14')
    assert r['direct_pts'] == 1


# ─── WAE DX Contest : EU↔DX uniquement, mults pondérés par bande ─────────────

def test_wae_eu_vers_eu_invalide():
    r = score('WAEDC_SSB', 'DL1ABC', '14')
    assert r['direct_pts'] == 0
    assert 'WAE' in r['explanation']


def test_wae_dx_vaut_un_point():
    r = score('WAEDC_SSB', 'W1AW', '14')
    assert r['direct_pts'] == 1


def test_wae_mult_pondere_par_bande():
    """Nouveau pays : ×4 sur 3.5 MHz, ×2 sur 14 MHz (règlement WAE §6)."""
    r80 = score('WAEDC_SSB', 'W1AW', '3.5')
    r20 = score('WAEDC_SSB', 'W1AW', '14')
    assert r80['new_mult'] and r20['new_mult']
    assert 'x4' in r80['explanation'].replace('×', 'x')
    assert 'x2' in r20['explanation'].replace('×', 'x')
    # Un nouveau mult doit relever nettement la priorité (1-2 sur 6)
    assert r80['priority'] <= 2


def test_wae_pays_deja_travaille_pas_de_mult():
    # Clé pays cty.dat : W1AW → 'K' (USA), zone CQ 5
    r = score('WAEDC_SSB', 'W1AW', '14', done_dxcc={'K'}, done_zones={'5'})
    assert not r['new_mult']


def test_zone_dxcc_pas_de_faux_nouveau_mult():
    """Régression du bug historique : l'indicatif était comparé au set des
    ZONES (toujours absent) → toute station passait pour un nouveau mult."""
    r1 = score('WAEDC_SSB', 'W1AW', '14')
    assert r1['new_mult']                       # 1er USA : vrai nouveau mult
    r2 = score('WAEDC_SSB', 'W2XYZ', '14', done_dxcc={'K'}, done_zones={'5'})
    assert not r2['new_mult']                   # USA + zone 5 déjà travaillés


def test_zone_cq_reelle_detectee():
    """Porto Rico (KP4, zone 8) après un QSO USA (K, zone 5) : nouveau pays
    ET nouvelle zone — détectable uniquement avec la base cty.dat."""
    r = score('WAEDC_SSB', 'KP4XX', '14', done_dxcc={'K'}, done_zones={'5'})
    assert r['new_mult']


# ─── Cohérence générale du moteur ────────────────────────────────────────────

def test_priorite_entre_1_et_6():
    for contest, dx, band in [('EU_HF_CHAMP', 'DL1ABC', '14'),
                              ('WAEDC_SSB', 'JA1XYZ', '7'),
                              ('REF_RPH', 'F8XYZ', '432')]:
        r = score(contest, dx, band, dist_km=100)
        assert 1 <= r['priority'] <= 6


def test_total_impact_jamais_negatif():
    r = score('EU_HF_CHAMP', 'W1AW', '14')   # QSO invalide
    assert r['total_impact'] >= 0


# ─── Locator du DX vs grille du spotteur (bug carte : station OK → France) ───

def test_locator_grille_spotteur_rejetee():
    """OK1SC spotte F5ZSW en mettant SA grille JO70OB : ne jamais placer la
    station française à Prague."""
    assert extract_dx_locator('F5ZSW', 'JO70OB 539 QSB', 'OK1SC') == ''


def test_locator_bon_candidat_choisi():
    """Deux grilles dans le commentaire : celle du pays du DX gagne."""
    assert extract_dx_locator('F5ZSW', 'JO70OB JN23 539', 'OK1SC') == 'JN23MM'


def test_locator_du_dx_conserve():
    assert extract_dx_locator('OK1ABC', 'JO70OB', 'F5XYZ') == 'JO70OB'
    assert extract_dx_locator('F1ABC', 'JN25XC tropo', 'F5XYZ') == 'JN25XC'


def test_locator_incoherent_avec_le_pays_rejete():
    """Grille européenne pour un indicatif US : trop loin du centroïde."""
    assert extract_dx_locator('W1AW', 'JO70OB', 'OK1SC') == ''


# ─── score_new_qso : recalcul serveur des points à l'INSERTION d'un QSO ──────
# (logx_http.add_qso_to_log, quelle que soit l'origine : PC, mobile, WSJT-X,
# ADIF réseau, Cloud Sync — voir logx_http.py)

def test_score_new_qso_km_recalcule_la_distance_depuis_les_locators():
    """Barème 1 pt/km (REF_RPH) : la distance vient des locators, jamais d'un
    champ 'dist'/'points' envoyé par le client (potentiellement faux ou
    trafiqué) — même locator des deux côtés = 0 km = 0 pt, quoi qu'envoie
    le client."""
    qso = {'contest': 'REF_RPH', 'call': 'F1ABC', 'locator': 'JN15XC',
           'my_call': 'F6KQJ', 'my_locator': 'JN15XC', 'band': '144',
           'mode': 'SSB', 'dist': 999999, 'points': 999999}
    assert score_new_qso(qso) == 0


def test_score_new_qso_ignore_le_champ_points_du_client():
    """La page mobile envoyait 'points' = distance MÊME hors barème
    kilométrique (ex. concours européen à points fixes) — score_new_qso doit
    toujours recalculer selon le VRAI barème du concours actif."""
    qso = {'contest': 'EU_HF_CHAMP', 'call': 'DL1ABC', 'locator': '',
           'my_call': 'F6KQJ', 'my_locator': 'JN15XC', 'band': '14',
           'mode': 'SSB', 'points': 12345}
    assert score_new_qso(qso) == 1   # EU_HF_CHAMP : 1 pt/QSO européen


def test_score_new_qso_hors_perimetre_zero_point():
    qso = {'contest': 'EU_HF_CHAMP', 'call': 'W1AW', 'locator': '',
           'my_call': 'F6KQJ', 'my_locator': 'JN15XC', 'band': '14',
           'mode': 'SSB', 'points': 555}
    assert score_new_qso(qso) == 0


def test_score_new_qso_sans_concours_replie_sur_le_bareme_km():
    """QSO non tagué (logbook simple, contest='') : repli sur le barème
    km — pas de régression par rapport à l'ancien calcul mobile en dur."""
    from logx_utils import locator_to_latlon, haversine
    qso = {'contest': '', 'call': 'F1ABC', 'locator': 'JN25XC',
           'my_call': 'F6KQJ', 'my_locator': 'JN15XC', 'band': '144', 'mode': 'SSB'}
    a, b = locator_to_latlon('JN15XC'), locator_to_latlon('JN25XC')
    assert score_new_qso(qso) == haversine(a[0], a[1], b[0], b[1])


def test_score_new_qso_independant_de_l_historique_du_log():
    """direct_pts ne dépend jamais des ensembles 'déjà travaillé' (seule
    l'ESTIMATION de multiplicateur en dépend, voir build_ranked_spots) —
    appeler deux fois de suite le même QSO doit donner la même valeur, sans
    dépendre d'un état de shared_log qu'on ne lui passe même pas."""
    qso = {'contest': 'WAEDC_SSB', 'call': 'W1AW', 'locator': '',
           'my_call': 'F6KQJ', 'my_locator': 'JN15XC', 'band': '14', 'mode': 'SSB'}
    assert score_new_qso(qso) == score_new_qso(qso) == 1


def test_score_new_qso_champs_manquants_ne_plante_pas():
    """Le pont WSJT-X/ADIF réseau n'envoie ni 'my_call' ni 'points' — un QSO
    incomplet ne doit jamais faire planter le recalcul."""
    assert score_new_qso({}) == 0
    assert score_new_qso({'call': 'DL1ABC', 'band': '14', 'contest': 'EU_HF_CHAMP'}) == 1
