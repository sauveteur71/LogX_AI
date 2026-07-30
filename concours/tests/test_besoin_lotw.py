# -*- coding: utf-8 -*-
"""Besoins LoTW par créneau entité × bande × mode.

DEMANDE UTILISATEUR, mot pour mot : « même si je les ai contactés ça m'apporte
rien, je veux une alerte jusqu'à ce que j'aie le DXCC confirmé par LoTW et pas
autre chose car ça n'a pas de valeur ».

DEUX CHANGEMENTS DE FOND par rapport à l'alerte « new one » existante, et ce
sont eux que ces tests protègent :

1. LE CRITÈRE. `new_one()` répond à « jamais CONTACTÉ ». Ici on répond à « pas
   encore CONFIRMÉ PAR LoTW », seule chose que l'ARRL accepte. Un QSO confirmé
   par eQSL ou par carte papier RESTE donc un besoin — c'est contre-intuitif
   pour du code (« il y a une confirmation, donc c'est bon ») et c'est
   exactement le piège à ne pas retomber dedans.

2. L'AXE MODE. `new_one()` ne connaît que (entité, bande). Le DXCC se poursuit
   par créneau entité × bande × mode (CW / Phonie / Numérique).
"""
import os
import sys

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CONCOURS not in sys.path:
    sys.path.insert(0, CONCOURS)

import logx_awards as aw   # noqa: E402


def _qso(call, band, mode, time='1200'):
    return {'call': call, 'band': band, 'mode': mode,
            'date': '2026-01-01', 'time': time}


@pytest.fixture
def sans_fichiers(monkeypatch):
    """Ni archives ni QSL du poste : le test décide seul des confirmations."""
    monkeypatch.setattr(aw, '_read_archives', lambda: [])
    monkeypatch.setattr(aw, '_read_qso_archive', lambda: [])

    def _conf(d):
        monkeypatch.setattr(aw, '_load_confirmations', lambda: d)
        aw.invalidate()
    return _conf


LOG = [_qso('W1ABC', '14', 'SSB', '1200'),
       _qso('W1ABC', '7', 'CW', '1300'),
       _qso('JA1XYZ', '14', 'FT8', '1400')]


# ─── Le critère : LoTW et rien d'autre ───────────────────────────────────────

def test_confirme_lotw_n_est_plus_un_besoin(sans_fichiers):
    sans_fichiers({'W1ABC|14|SSB': {'lotw': '2026-01-10'}})
    assert aw.besoin_lotw('W1ABC', '14', 'SSB', LOG)['besoin'] is False


def test_confirme_eQSL_SEULEMENT_reste_un_besoin(sans_fichiers):
    """LE point de la demande. eQSL n'a aucune valeur pour le DXCC : traiter
    « il existe une confirmation » comme « c'est acquis » redonnerait
    exactement l'alerte inutile que l'utilisateur veut éviter."""
    sans_fichiers({'W1ABC|7|CW': {'eqsl': '2026-01-11'}})
    r = aw.besoin_lotw('W1ABC', '7', 'CW', LOG)
    assert r['besoin'] is True


def test_une_carte_papier_ou_clublog_ne_suffit_pas_non_plus(sans_fichiers):
    sans_fichiers({'W1ABC|7|CW': {'clublog': True, 'eqsl': True}})
    assert aw.besoin_lotw('W1ABC', '7', 'CW', LOG)['besoin'] is True


def test_un_qso_simplement_travaille_reste_un_besoin(sans_fichiers):
    """Le cas le plus courant : contacté, jamais confirmé."""
    sans_fichiers({})
    assert aw.besoin_lotw('W1ABC', '14', 'SSB', LOG)['besoin'] is True


# ─── L'axe bande × mode ──────────────────────────────────────────────────────

def test_confirme_sur_une_bande_ne_couvre_pas_les_autres(sans_fichiers):
    sans_fichiers({'W1ABC|14|SSB': {'lotw': True}})
    assert aw.besoin_lotw('W1ABC', '21', 'SSB', LOG)['besoin'] is True


def test_confirme_en_phonie_ne_couvre_pas_le_CW(sans_fichiers):
    """Même entité, même bande, mode différent : c'est un autre créneau."""
    sans_fichiers({'W1ABC|14|SSB': {'lotw': True}})
    assert aw.besoin_lotw('W1ABC', '14', 'CW', LOG)['besoin'] is True


def test_les_modes_numeriques_comptent_pour_UN_seul_creneau(sans_fichiers):
    """FT8, RTTY et PSK tombent dans la même catégorie « numérique » — le DXCC
    ne distingue pas chaque mode numérique, et compter FT8 et FT4 séparément
    gonflerait artificiellement le besoin."""
    sans_fichiers({'JA1XYZ|14|FT8': {'lotw': True}})
    assert aw.besoin_lotw('JA1XYZ', '14', 'RTTY', LOG)['besoin'] is False
    assert aw._mode_category('FT8') == aw._mode_category('RTTY') == 'DIGITAL'


def test_les_phonies_comptent_pour_UN_seul_creneau(sans_fichiers):
    sans_fichiers({'W1ABC|14|SSB': {'lotw': True}})
    assert aw.besoin_lotw('W1ABC', '14', 'USB', LOG)['besoin'] is False


# ─── Priorité : l'entité jamais confirmée nulle part ─────────────────────────

def test_jamais_confirme_nulle_part_est_signale_a_part(sans_fichiers):
    """C'est le cas qui fait avancer le compteur DXCC, il doit se distinguer
    d'un simple créneau manquant sur une entité déjà acquise."""
    sans_fichiers({'W1ABC|14|SSB': {'lotw': True}})
    assert aw.besoin_lotw('JA1XYZ', '14', 'FT8', LOG)['raison'] == 'jamais_confirme'
    assert aw.besoin_lotw('W1ABC', '21', 'SSB', LOG)['raison'] == 'creneau'


def test_un_indicatif_inconnu_ne_declenche_rien(sans_fichiers):
    sans_fichiers({})
    assert aw.besoin_lotw('', '14', 'SSB', LOG)['besoin'] is False
    assert aw.besoin_lotw('XX', '14', 'SSB', LOG)['besoin'] is False


# ─── La liste des spots ──────────────────────────────────────────────────────

def test_les_spots_deja_confirmes_sont_ecartes(sans_fichiers):
    sans_fichiers({'W1ABC|14|SSB': {'lotw': True}})
    spots = [{'call': 'W1ABC', 'band': '14', 'mode': 'SSB'},
             {'call': 'JA1XYZ', 'band': '14', 'mode': 'FT8'}]
    besoins = aw.besoins_lotw_spottes(spots, LOG)
    assert [b['call'] for b in besoins] == ['JA1XYZ']


def test_les_entites_jamais_confirmees_passent_en_tete(sans_fichiers):
    """Sur une liste longue, l'opérateur regarde les premières lignes."""
    sans_fichiers({'W1ABC|14|SSB': {'lotw': True}})
    spots = [{'call': 'W1ABC', 'band': '21', 'mode': 'SSB'},   # créneau
             {'call': 'JA1XYZ', 'band': '14', 'mode': 'FT8'}]  # jamais confirmé
    besoins = aw.besoins_lotw_spottes(spots, LOG)
    assert besoins[0]['raison'] == 'jamais_confirme'


def test_le_meme_creneau_spotte_deux_fois_n_apparait_qu_une(sans_fichiers):
    sans_fichiers({})
    spots = [{'call': 'JA1XYZ', 'band': '14', 'mode': 'FT8'}] * 3
    assert len(aw.besoins_lotw_spottes(spots, LOG)) == 1


def test_le_carnet_n_est_parcouru_qu_une_fois_pour_toute_la_liste(sans_fichiers,
                                                                  monkeypatch):
    """Appeler besoin_lotw() par spot relirait le carnet entier à chaque ligne.
    Quelques centaines de spots suffisent alors à rendre la page inutilisable —
    d'où le calcul groupé, que ce test verrouille."""
    sans_fichiers({})
    appels = []
    vrai = aw.collect_all_qsos
    monkeypatch.setattr(aw, 'collect_all_qsos',
                        lambda *a, **k: appels.append(1) or vrai(*a, **k))
    spots = [{'call': c, 'band': '14', 'mode': 'SSB'}
             for c in ('W1ABC', 'JA1XYZ', 'VK3ZZZ', 'PY2AAA', 'ZS6BBB')]
    aw.besoins_lotw_spottes(spots, LOG)
    assert len(appels) == 1, 'le log doit etre parcouru une seule fois'


def test_une_liste_de_spots_vide_ne_leve_pas(sans_fichiers):
    sans_fichiers({})
    assert aw.besoins_lotw_spottes([], LOG) == []
    assert aw.besoins_lotw_spottes(None, LOG) == []


# ─── Mode déduit de la fréquence (inspiré du manuel CC User, annexe C) ───────
# DÉFAUT RÉEL CORRIGÉ. _mode_category() renvoyait DIGITAL pour tout mode
# absent, vide ou inconnu. Or beaucoup de spots du cluster n'indiquent PAS le
# mode : un DX en CW spotté sans ce champ était donc rangé dans le créneau
# NUMÉRIQUE, et l'alerte « pas confirmé LoTW en CW » ne se déclenchait jamais
# pour lui.
#
# La solution est celle qu'applique CC Cluster depuis toujours, et son manuel
# en donne la raison : « beaucoup de spots DX n'indiquent pas le mode
# réellement utilisé, mais TOUS indiquent la fréquence — c'est un champ
# obligatoire de tout spot valide ». La table de créneaux vient de son
# annexe C.

@pytest.mark.parametrize('mhz,attendu', [
    (1.820, 'CW'), (1.900, 'PHONE'),
    (3.520, 'CW'), (3.590, 'DIGITAL'), (3.750, 'PHONE'),
    (7.030, 'CW'), (7.074, 'DIGITAL'), (7.150, 'PHONE'),
    (10.120, 'CW'), (10.136, 'DIGITAL'),
    (14.020, 'CW'), (14.074, 'DIGITAL'), (14.250, 'PHONE'),
    (21.030, 'CW'), (21.074, 'DIGITAL'), (21.300, 'PHONE'),
    (28.020, 'CW'), (28.074, 'DIGITAL'), (28.400, 'PHONE'),
    (144.050, 'CW'), (144.300, 'PHONE'),
])
def test_le_mode_se_deduit_de_la_frequence(mhz, attendu):
    assert aw.mode_depuis_frequence(mhz) == attendu


def test_un_spot_CW_sans_mode_n_est_plus_range_en_numerique():
    """LE défaut : sans fréquence, un mode absent tombait en DIGITAL."""
    assert aw._mode_category(None) == 'DIGITAL'          # ancien comportement
    assert aw._mode_category(None, 14.020) == 'CW'       # corrigé


def test_le_mode_ANNONCE_prime_sur_la_frequence():
    """Rien n'interdit un QSO CW dans un segment phonie : une information
    explicite vaut mieux qu'un découpage par plage."""
    assert aw._mode_category('CW', 14.250) == 'CW'
    assert aw._mode_category('FT8', 14.020) == 'DIGITAL'


def test_une_frequence_en_kHz_est_acceptee():
    """Selon la source, un spot arrive en MHz (14.074) ou en kHz (14074)."""
    assert aw.mode_depuis_frequence(14074) == 'DIGITAL'
    assert aw.mode_depuis_frequence(14.074) == 'DIGITAL'


@pytest.mark.parametrize('valeur', [None, '', 'abc', 0])
def test_une_frequence_inexploitable_ne_leve_pas(valeur):
    assert aw.mode_depuis_frequence(valeur) == ''


def test_hors_de_toute_bande_amateur_on_ne_devine_pas():
    """Mieux vaut ne rien conclure que d'inventer un créneau."""
    assert aw.mode_depuis_frequence(12.000) == ''
