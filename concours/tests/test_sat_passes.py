# -*- coding: utf-8 -*-
"""Prédiction de passages satellite, éprouvée sur de VRAIS TLE.

CE QUI MANQUAIT. LogX savait NOMMER un satellite (logx_satellites.py, pour
l'export ADIF) et savait pointer un rotor en azimut ET en élévation
(logx_rotor.py). Entre les deux, rien : aucun moyen de savoir quand le
satellite passe ni où pointer. Il fallait ouvrir Gpredict à côté.

LES TLE DE CE FICHIER SONT AUTHENTIQUES — téléchargés de CelesTrak le
31/07/2026, groupe « amateur ». Un TLE inventé produirait une orbite absurde et
des tests qui valident du vide : c'est précisément la faute de méthode que ce
projet a passé la journée à corriger. Ils sont figés ici, donc les prédictions
sont reproductibles.

DEUX BORNES QUE J'AVAIS MAL POSÉES au premier essai, et qui disent quelque
chose du domaine :
  • « deux passages consécutifs sont espacés d'une orbite » — FAUX. La trace au
    sol dérive : il y a un groupe de passages le matin, un le soir, séparés de
    dix à quinze heures. Un écart de 908 minutes est normal, pas un bug.
  • « la distance à l'ISS est inférieure à 12 000 km » — FAUX quand elle est
    SOUS l'horizon : à −79° d'élévation elle est de l'autre côté de la Terre,
    soit jusqu'à ~13 580 km (diamètre terrestre + deux fois l'altitude).
"""
import datetime
import os
import sys

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CONCOURS not in sys.path:
    sys.path.insert(0, CONCOURS)

import logx_sat_passes as sp   # noqa: E402

pytestmark = pytest.mark.skipif(not sp.HAS_EPHEM, reason='ephem non installé')

# TLE RÉELS, CelesTrak groupe « amateur », téléchargés le 31/07/2026.
#
# PREMIER JET FAUX, et c'est la faute même que ce projet a passé la journée à
# corriger : j'avais tapé les lignes de l'ISS DE MÉMOIRE, en respectant le
# format. Le format était bon, la somme de contrôle non — ephem a refusé le
# jeu, et douze tests sont tombés d'un coup sur un KeyError. Recopier un
# checksum de tête ne marche pas mieux qu'un plan de bandes.
TLE_REEL = """ISS (ZARYA)
1 25544U 98067A   26212.11974625  .00008690  00000+0  16406-3 0  9990
2 25544  51.6317  82.6819 0007117 356.3115   3.7820 15.49277094578568
OSCAR 7 (AO-7)
1 07530U 74089B   26211.88502640 -.00000033  00000+0  84158-4 0  9994
2 07530 101.9911 225.5876 0012551  49.1780  70.3946 12.53698852365997
ES'HAIL 2
1 43700U 18090A   26211.90878125  .00000149  00000+0  00000+0 0  9996
2 43700   0.0156  73.7238 0002545  88.9212 138.8221  1.00272210 28116
"""

# QTH de référence du projet (JN15XC).
LAT, LON = 45.1042, 3.9583
# Date fixe : sans elle, les prédictions changeraient à chaque exécution.
QUAND = datetime.datetime(2026, 7, 31, 12, 0, 0)


@pytest.fixture(scope='module')
def cache():
    return {'recupere': '2026-07-31T06:00:00', 'tle': sp.parser_tle(TLE_REEL)}


# ─── Lecture du fichier TLE ──────────────────────────────────────────────────

def test_les_trois_satellites_sont_lus(cache):
    assert set(cache['tle']) == {'ISS (ZARYA)', 'OSCAR 7 (AO-7)', "ES'HAIL 2"}


def test_un_fichier_tronque_ne_produit_pas_d_orbite_absurde():
    """Un téléchargement coupé en plein vol laisserait une paire incomplète.
    On valide les préfixes '1 ' et '2 ' plutôt que de découper par paquets de
    trois — sinon les lignes glissent et les orbites deviennent fantaisistes
    sans que rien ne le signale."""
    tronque = '\n'.join(TLE_REEL.splitlines()[:5])   # 3ᵉ objet coupé
    jeux = sp.parser_tle(tronque)
    assert 'ISS (ZARYA)' in jeux
    for l1, l2 in jeux.values():
        assert l1.startswith('1 ') and l2.startswith('2 ')


def test_du_html_a_la_place_du_tle_ne_donne_rien():
    """Un portail captif répond 200 avec une page HTML."""
    assert sp.parser_tle('<html><body>Connectez-vous</body></html>') == {}
    assert sp.parser_tle('') == {}
    assert sp.parser_tle(None) == {}


# ─── Passages ────────────────────────────────────────────────────────────────

def test_l_ISS_fait_le_bon_nombre_de_passages_par_jour(cache):
    """Orbite basse à ~93 min : entre 3 et 12 passages exploitables par jour
    depuis une latitude moyenne."""
    r = sp.passages(cache, 'ISS (ZARYA)', LAT, LON, heures=24, quand=QUAND)
    assert r['available']
    assert 3 <= len(r['passages']) <= 12, len(r['passages'])


def test_chaque_passage_est_chronologiquement_coherent(cache):
    r = sp.passages(cache, 'ISS (ZARYA)', LAT, LON, heures=24, quand=QUAND)
    for p in r['passages']:
        assert p['aos_utc'] < p['tca_utc'] < p['los_utc'], p


def test_la_duree_est_celle_d_une_orbite_basse(cache):
    """Un passage LEO dure de une à vingt minutes. Une durée hors de ces
    bornes signalerait une orbite mal propagée."""
    r = sp.passages(cache, 'ISS (ZARYA)', LAT, LON, heures=24, quand=QUAND)
    for p in r['passages']:
        assert 60 <= p['duree_s'] <= 1300, p


def test_les_azimuts_et_elevations_sont_dans_leurs_bornes(cache):
    r = sp.passages(cache, 'ISS (ZARYA)', LAT, LON, heures=24, quand=QUAND)
    for p in r['passages']:
        assert 0 <= p['az_aos'] < 360 and 0 <= p['az_los'] < 360, p
        assert 0 < p['el_max'] <= 90, p


def test_le_filtre_d_elevation_ne_peut_QUE_retrancher(cache):
    """La référence conseille de viser les passages hauts (> 20-30°) : les
    rasants sont courts et bruités."""
    tous = sp.passages(cache, 'ISS (ZARYA)', LAT, LON, heures=48,
                       elevation_min=0, quand=QUAND)['passages']
    hauts = sp.passages(cache, 'ISS (ZARYA)', LAT, LON, heures=48,
                        elevation_min=30, quand=QUAND)['passages']
    assert len(hauts) <= len(tous)
    assert all(p['el_max'] >= 30 for p in hauts)


def test_la_fenetre_demandee_est_respectee(cache):
    court = sp.passages(cache, 'ISS (ZARYA)', LAT, LON, heures=3, quand=QUAND)
    long = sp.passages(cache, 'ISS (ZARYA)', LAT, LON, heures=48, quand=QUAND)
    assert len(court['passages']) < len(long['passages'])


def test_un_satellite_a_orbite_haute_donne_des_passages_LONGS(cache):
    """AO-7 est à ~1450 km : ses passages durent bien plus que ceux de l'ISS.
    C'est un contrôle croisé — si les deux donnaient la même durée, la
    propagation d'orbite serait suspecte."""
    iss = sp.passages(cache, 'ISS (ZARYA)', LAT, LON, heures=24, quand=QUAND)
    ao7 = sp.passages(cache, 'OSCAR 7 (AO-7)', LAT, LON, heures=24, quand=QUAND)
    if ao7['passages'] and iss['passages']:
        assert (max(p['duree_s'] for p in ao7['passages'])
                > max(p['duree_s'] for p in iss['passages']))


def test_un_geostationnaire_ne_fait_pas_boucler_le_calcul(cache):
    """QO-100 ne se lève ni ne se couche : next_pass() peut rendre indéfiniment
    le même instant. La boucle doit sortir, pas tourner sans fin."""
    r = sp.passages(cache, "ES'HAIL 2", LAT, LON, heures=24, quand=QUAND)
    assert r['available'] is True
    assert isinstance(r['passages'], list)


def test_le_prochain_passage_est_le_premier_de_la_liste(cache):
    liste = sp.passages(cache, 'ISS (ZARYA)', LAT, LON, heures=72, quand=QUAND)
    seul = sp.prochain_passage(cache, 'ISS (ZARYA)', LAT, LON, quand=QUAND)
    assert seul['passage']['aos_utc'] == liste['passages'][0]['aos_utc']


# ─── Position ────────────────────────────────────────────────────────────────

def test_la_position_est_physiquement_possible(cache):
    p = sp.position(cache, 'ISS (ZARYA)', LAT, LON, quand=QUAND)
    assert p['available']
    assert 0 <= p['az'] < 360 and -90 <= p['el'] <= 90
    # Sous l'horizon, l'ISS peut être de l'autre côté de la Terre : diamètre
    # terrestre (12 742 km) + deux fois l'altitude.
    assert 300 <= p['distance_km'] <= 13600, p


def test_visible_suit_l_elevation(cache):
    p = sp.position(cache, 'ISS (ZARYA)', LAT, LON, quand=QUAND)
    assert p['visible'] == (p['el'] > 0)


def test_pendant_un_passage_le_satellite_est_VISIBLE(cache):
    """Contrôle croisé entre les deux fonctions : au moment du TCA annoncé par
    passages(), position() doit voir le satellite au-dessus de l'horizon. Si
    elles se contredisaient, l'une des deux serait fausse."""
    r = sp.passages(cache, 'ISS (ZARYA)', LAT, LON, heures=24, quand=QUAND)
    p = r['passages'][0]
    tca = datetime.datetime.strptime(p['tca_utc'], '%Y-%m-%d %H:%M:%S')
    pos = sp.position(cache, 'ISS (ZARYA)', LAT, LON, quand=tca)
    assert pos['visible'], pos
    assert abs(pos['el'] - p['el_max']) < 1.5, (pos['el'], p['el_max'])


# ─── Doppler ─────────────────────────────────────────────────────────────────

def test_a_l_approche_la_frequence_MONTE():
    """Convention de signe : distance qui diminue = vitesse radiale négative =
    fréquence reçue plus haute que la nominale."""
    assert sp.doppler_hz(-7500, 145.8) > 0
    assert sp.doppler_hz(+7500, 145.8) < 0
    assert sp.doppler_hz(0, 145.8) == 0


def test_l_ordre_de_grandeur_est_le_bon_sur_2m():
    """ISS à 7,5 km/s de vitesse radiale sur 145,8 MHz : ~3,6 kHz."""
    d = sp.doppler_hz(-7500, 145.8)
    assert 3000 < d < 4200, d


def test_le_doppler_croit_avec_la_frequence():
    """Négligeable en 2 m, notable en 70 cm, fort en bande S : c'est pourquoi
    on corrige sur la liaison la plus haute."""
    d2m = abs(sp.doppler_hz(-7500, 145.8))
    d70 = abs(sp.doppler_hz(-7500, 435.0))
    assert 2.8 < d70 / d2m < 3.1


def test_AUCUN_facteur_2_contrairement_A_L_EME():
    """LE piège de recopie. En EME le signal fait l'aller ET le retour, d'où
    un décalage doublé ; ici la liaison est simple. Reprendre la formule EME
    donnerait le double et ferait rater le correspondant."""
    attendu = 7500 / 299792458.0 * 145.8e6
    assert abs(sp.doppler_hz(-7500, 145.8) - attendu) < 1.0


@pytest.mark.parametrize('v,f', [(None, 145.8), ('x', 145.8), (-7500, 0),
                                 (-7500, None), (-7500, -3)])
def test_une_entree_illisible_ne_leve_pas(v, f):
    assert sp.doppler_hz(v, f) is None


# ─── Le cache TLE, et l'expédition ───────────────────────────────────────────

def test_l_age_du_jeu_est_toujours_connu(cache):
    """La référence est formelle : « recharger souvent, sinon prédiction
    fausse ». L'âge ne doit jamais être caché."""
    a = sp.age_tle(cache, maintenant=datetime.datetime(2026, 7, 31, 12, 0))
    assert a['jours'] == 0.2 and a['etat'] == 'frais'


@pytest.mark.parametrize('jours,etat', [(0, 'frais'), (2, 'frais'),
                                        (5, 'vieux'), (13, 'vieux'),
                                        (20, 'perime'), (400, 'perime')])
def test_les_paliers_d_anciennete(jours, etat):
    base = datetime.datetime(2026, 7, 1, 12, 0)
    c = {'recupere': base.isoformat(), 'tle': {'X': ['1 ', '2 ']}}
    assert sp.age_tle(c, maintenant=base + datetime.timedelta(days=jours))['etat'] == etat


def test_un_age_inconnu_est_dit_INCONNU_pas_zero():
    """Zéro voudrait dire « tout frais » — un mensonge."""
    assert sp.age_tle({'recupere': 'n importe quoi', 'tle': {}}) is None
    assert sp.age_tle(None) is None


def test_un_jeu_PERIME_reste_utilisable(cache):
    """CONTRAINTE D'EXPÉDITION : quinze jours sans Internet, rien de réparable
    sur place. Une prédiction dégradée vaut infiniment mieux que pas de
    prédiction — on informe, on ne bloque pas."""
    vieux = dict(cache, recupere='2020-01-01T00:00:00')
    assert sp.age_tle(vieux)['etat'] == 'perime'
    r = sp.passages(vieux, 'ISS (ZARYA)', LAT, LON, heures=24, quand=QUAND)
    assert r['available'] and r['passages']


def test_un_cache_absent_ne_leve_pas(tmp_path):
    assert sp.charger_tle(str(tmp_path)) is None


def test_ecriture_puis_relecture(tmp_path):
    jeux = sp.parser_tle(TLE_REEL)
    sp.sauver_tle(jeux, str(tmp_path))
    relu = sp.charger_tle(str(tmp_path))
    assert relu['tle'] == jeux
    assert sp.age_tle(relu)['etat'] == 'frais'


# ─── Le rafraîchissement ne doit jamais détruire ce qui marche ───────────────

def test_une_reponse_de_portail_captif_NE_REMPLACE_PAS_le_cache(tmp_path, monkeypatch):
    """LE cas qui compte en expédition : un réseau captif répond 200 avec une
    page HTML. Le téléchargement « réussit » et rend zéro satellite. Écraser
    le cache là-dessus, c'est perdre la seule chose encore utilisable."""
    jeux = sp.parser_tle(TLE_REEL)
    sp.sauver_tle(jeux, str(tmp_path))
    import logx_utils
    monkeypatch.setattr(logx_utils, 'fetch_url',
                        lambda *a, **k: '<html>Portail de connexion</html>')
    r = sp.rafraichir_tle(str(tmp_path))
    assert r['ok'] is False
    assert sp.charger_tle(str(tmp_path))['tle'] == jeux, 'le cache a ete detruit'


def test_un_reseau_muet_ne_detruit_rien_non_plus(tmp_path, monkeypatch):
    jeux = sp.parser_tle(TLE_REEL)
    sp.sauver_tle(jeux, str(tmp_path))
    import logx_utils
    monkeypatch.setattr(logx_utils, 'fetch_url', lambda *a, **k: None)
    assert sp.rafraichir_tle(str(tmp_path))['ok'] is False
    assert sp.charger_tle(str(tmp_path))['tle'] == jeux


def test_une_exception_reseau_est_rattrapee(tmp_path, monkeypatch):
    import logx_utils

    def boum(*a, **k):
        raise OSError('DNS muet')
    monkeypatch.setattr(logx_utils, 'fetch_url', boum)
    r = sp.rafraichir_tle(str(tmp_path))
    assert r['ok'] is False and 'error' in r


def test_un_jeu_valide_est_bien_ecrit(tmp_path, monkeypatch):
    """Miroir des trois précédents : le refus ne doit pas bloquer le cas
    normal. On fabrique un jeu assez gros pour passer le seuil de plausibilité."""
    import logx_utils
    gros = '\n'.join(
        "SAT-%02d\n1 %05dU 98067A   26211.55759847  .00016717  00000+0  30074-3 0  999%d"
        "\n2 %05d  51.6394 220.4384 0004847 108.2864  25.6438 15.50128875 4612%d"
        % (i, 25544 + i, i % 10, 25544 + i, i % 10) for i in range(15))
    monkeypatch.setattr(logx_utils, 'fetch_url', lambda *a, **k: gros)
    r = sp.rafraichir_tle(str(tmp_path))
    assert r['ok'] is True and r['nb'] == 15


# ─── Satellite inconnu ───────────────────────────────────────────────────────

def test_un_satellite_absent_du_jeu_est_refuse_proprement(cache):
    for f in (sp.position, sp.passages):
        r = f(cache, 'SAT-QUI-N-EXISTE-PAS', LAT, LON)
        assert r['available'] is False and 'error' in r


@pytest.mark.parametrize('nom', ['ISS (ZARYA)', 'iss (zarya)', 'ISS(ZARYA)'])
def test_la_correspondance_de_nom_est_tolerante(cache, nom):
    """CelesTrak écrit « AO-7 », AMSAT parfois « AO-07 », l'opérateur saisit ce
    qu'il voit."""
    assert sp.position(cache, nom, LAT, LON, quand=QUAND)['available']


def test_les_satellites_connus_sont_listables(cache):
    assert 'ISS (ZARYA)' in sp.satellites_connus(cache)
    assert sp.satellites_connus(None) == []
