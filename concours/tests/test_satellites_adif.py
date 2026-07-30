# -*- coding: utf-8 -*-
"""Satellites : les deux champs sans lesquels un QSO satellite ne vaut rien.

MESURÉ AVANT D'ÉCRIRE. LogX savait nommer un satellite — le champ « satellite
actif » de CONFIG — mais son aide le disait elle-même : « repère informatif
uniquement ». L'export ADIF n'émettait ni PROP_MODE ni SAT_NAME, et le carnet
n'avait aucun champ satellite. Tout QSO satellite exporté vers LoTW était donc
crédité comme un contact TERRESTRE : exactement l'inverse du but.

CE QU'EXIGE LoTW, vérifié sur sa page d'aide et non de mémoire :
  • PROP_MODE = SAT — c'est lui qui range le QSO dans la catégorie satellite,
    pour le DXCC, le WAS, le VUCC et les mentions associées ;
  • SAT_NAME orthographié EXACTEMENT comme sur la liste acceptée : « if you
    enter the satellite name as AO7 instead of AO-7 the data will be rejected
    during the upload ». C'est le FICHIER ENTIER qui est refusé, pas la ligne.

D'où le parti pris testé ici : on SIGNALE une orthographe douteuse, on ne
REFUSE jamais un nom. La liste embarquée n'est pas l'autorité — celle de TQSL
l'est — et empêcher de loguer un satellite récent serait pire que le risque de
faute de frappe.
"""
import os
import sys

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CONCOURS not in sys.path:
    sys.path.insert(0, CONCOURS)

import logx_satellites as sat     # noqa: E402
import logx_export as ex          # noqa: E402
import logx_import as imp         # noqa: E402


def qso(**kw):
    q = {'call': 'DL1ABC', 'band': '144', 'mode': 'SSB', 'date': '2026-07-30',
         'time': '1200', 'rst_sent': '59', 'rst_rcvd': '59'}
    q.update(kw)
    return q


# ─── Les deux champs partent bien dans l'ADIF ────────────────────────────────

def test_UN_QSO_SATELLITE_PORTE_PROP_MODE_ET_SAT_NAME():
    """Sans les deux, LoTW crédite un contact terrestre. C'est LE défaut que ce
    chantier corrige."""
    adif = ex.build_adif([qso(sat_name='RS-44')], {'callsign': 'F4GLD'})
    assert '<prop_mode:3>SAT' in adif
    assert '<sat_name:5>RS-44' in adif


def test_UN_QSO_TERRESTRE_N_EN_PORTE_AUCUN():
    """Marquer tous les QSO « SAT » serait pire que ne rien marquer : LoTW
    rangerait 9 392 contacts terrestres dans la catégorie satellite."""
    adif = ex.build_adif([qso()], {'callsign': 'F4GLD'})
    assert 'prop_mode' not in adif and 'sat_name' not in adif


def test_les_deux_champs_vont_ENSEMBLE_ou_pas_du_tout():
    """PROP_MODE=SAT sans SAT_NAME serait accepté par l'ADIF mais inutile :
    LoTW ne saurait pas à quel satellite créditer le contact, et il ne
    compterait pour aucune mention."""
    assert sat.champs_adif({'sat_name': ''}) == {}
    assert sat.champs_adif({}) == {}
    assert set(sat.champs_adif({'sat_name': 'SO-50'})) == {'prop_mode', 'sat_name'}


def test_le_nom_est_normalise_en_majuscules_sans_espaces():
    adif = ex.build_adif([qso(sat_name=' so-50 ')], {'callsign': 'F4GLD'})
    assert '<sat_name:5>SO-50' in adif


# ─── L'aller-retour ne doit rien perdre ──────────────────────────────────────

def test_UN_ALLER_RETOUR_ADIF_NE_DEGRADE_PAS_LE_QSO(tmp_path):
    """Exporter puis réimporter ne doit pas transformer un QSO satellite en
    contact terrestre — ce serait effacer en silence le seul champ qui le rend
    créditable."""
    adif = ex.build_adif([qso(sat_name='FO-29', locator='JO40')],
                         {'callsign': 'F4GLD'})
    f = tmp_path / 'aller.adi'
    f.write_text(adif, encoding='utf-8')
    qsos, _stats = imp.parse_adif_to_qsos(f.read_text(encoding='utf-8'))
    assert qsos and qsos[0]['sat_name'] == 'FO-29'


def test_un_adif_venu_d_ailleurs_conserve_son_satellite():
    """Un carnet réimporté depuis LoTW ou un autre logiciel porte SAT_NAME."""
    brut = ('<call:6>DL1ABC<qso_date:8>20260730<time_on:4>1200'
            '<band:4>70cm<mode:3>SSB<sat_name:5>AO-91<prop_mode:3>SAT<eor>')
    qsos, _ = imp.parse_adif_to_qsos(brut)
    assert qsos[0]['sat_name'] == 'AO-91'


# ─── La validation : signaler, jamais refuser ────────────────────────────────

@pytest.mark.parametrize('nom', ['RS-44', 'SO-50', 'QO-100', 'ISS', 'AO-7'])
def test_les_satellites_connus_passent_sans_avertissement(nom):
    v = sat.valider(nom)
    assert v['ok'] and v['connu'] and v['avertissement'] == ''


def test_LA_FAUTE_QUI_FAIT_REJETER_TOUT_LE_FICHIER_EST_SIGNALEE():
    """« AO7 » au lieu de « AO-7 » : LoTW refuse le TÉLÉVERSEMENT ENTIER. Une
    erreur qui ne se révèle que des jours après le QSO est exactement ce qu'un
    logiciel doit rendre impossible — ou au minimum annoncer."""
    v = sat.valider('AO7')
    assert v['ok'] is True, 'on signale, on ne refuse pas'
    assert v['connu'] is False
    assert 'rejeter' in v['avertissement'].lower()


def test_UN_SATELLITE_INCONNU_RESTE_LOGGABLE():
    """La liste embarquée n'est pas l'autorité — celle de TQSL l'est. Empêcher
    de loguer un satellite lancé le mois dernier serait pire que le risque de
    faute de frappe."""
    v = sat.valider('XW-5')
    assert v['ok'] is True and v['nom'] == 'XW-5'
    assert 'TQSL' in v['avertissement']


def test_ON_NE_REECRIT_JAMAIS_UN_NOM_INCONNU():
    """Transformer « AO7 » en « AO-7 » serait deviner. Deviner juste
    aujourd'hui ne garantit pas de deviner juste demain, et un nom réécrit à
    tort fait rejeter le fichier tout autant."""
    assert sat.normaliser('AO7') == 'AO7'
    assert sat.valider('AO7')['nom'] == 'AO7'


def test_un_nom_vide_n_est_pas_un_satellite():
    for vide in ('', '   ', None):
        assert sat.valider(vide)['ok'] is False
        assert sat.est_satellite({'sat_name': vide}) is False


# ─── La liste embarquée ──────────────────────────────────────────────────────

def test_tous_les_noms_de_la_liste_respectent_le_format_LoTW():
    """Un nom mal formé DANS notre propre liste ferait rejeter le fichier de
    l'opérateur qui nous a fait confiance."""
    for nom in sat.NOMS:
        v = sat.valider(nom)
        assert v['connu'], nom
        assert nom == nom.upper().strip(), nom


def test_la_liste_couvre_les_satellites_les_plus_utilises():
    """SO-50 est le premier satellite de presque tous les débutants, RS-44 a la
    plus grande empreinte, QO-100 est géostationnaire et ne demande aucun
    suivi. Les oublier viderait la liste de son intérêt."""
    for incontournable in ('SO-50', 'RS-44', 'QO-100', 'ISS'):
        assert incontournable in sat.NOMS


def test_QO_100_est_signale_comme_GEOSTATIONNAIRE():
    """C'est LA information qui change tout pour l'opérateur : antenne fixe,
    aucun suivi, disponible en permanence. La noyer dans une liste serait
    passer à côté du seul conseil utile."""
    libelle = dict(sat.SATELLITES)['QO-100']
    assert 'ÉOSTATIONNAIRE' in libelle.upper() or 'GEOSTATIONNAIRE' in libelle.upper()


def test_LE_SELECTEUR_DE_CONFIG_ET_LA_LISTE_NE_DIVERGENT_PAS():
    """Deux listes de satellites qui ne s'accordent pas, c'est un nom
    sélectionnable à l'écran mais inconnu à la validation : l'opérateur ne
    serait jamais prévenu que son fichier va être rejeté.

    « AUTRE » est la seule valeur tolérée hors liste : c'est un marqueur du
    sélecteur, pas un satellite — et il ne doit JAMAIS partir dans SAT_NAME.
    """
    import re
    html = open(os.path.join(CONCOURS, 'logx_configuration.html'),
                encoding='utf-8').read()
    i = html.index('id="active_satellite"')
    bloc = html[i:html.index('</select>', i)]
    valeurs = [v for v in re.findall(r'<option value="([^"]*)"', bloc) if v]
    inconnus = [v for v in valeurs if v != 'AUTRE' and not sat.connu(v)]
    assert inconnus == [], inconnus


def test_AUTRE_N_EST_JAMAIS_ENVOYE_A_LoTW():
    """SAT_NAME=AUTRE ferait rejeter le fichier ENTIER — pire que ne rien
    envoyer du tout."""
    http = open(os.path.join(CONCOURS, 'logx_http.py'), encoding='utf-8').read()
    corps = http[http.index('def _tamponner_satellite'):http.index('def add_qso_to_log')]
    assert "!= 'AUTRE'" in corps


def test_un_QSO_qui_porte_DEJA_un_satellite_n_est_pas_ecrase():
    """Il peut venir d'un import ADIF ou d'un autre poste : sa valeur est plus
    sûre qu'un réglage global resté sur le satellite de la veille."""
    http = open(os.path.join(CONCOURS, 'logx_http.py'), encoding='utf-8').read()
    corps = http[http.index('def _tamponner_satellite'):http.index('def add_qso_to_log')]
    assert "if qso.get('sat_name'):" in corps and 'return qso' in corps


def test_la_valeur_PROP_MODE_est_celle_du_protocole():
    """« SAT » n'est pas un choix : c'est la valeur d'énumération ADIF. La
    changer romprait tout crédit satellite sans message d'erreur."""
    assert sat.PROP_MODE_SAT == 'SAT'
