# -*- coding: utf-8 -*-
"""Liste publique des utilisateurs LoTW (ARRL) — cache local.

À QUOI ÇA SERT : c'est le complément direct des alertes de besoin LoTW
(test_besoin_lotw.py). Inutile de courir après une station qui n'uploade jamais
vers LoTW — le QSO ne sera JAMAIS confirmé et ne comptera jamais pour le DXCC.

SOURCE VÉRIFIÉE le 30/07/2026 : https://lotw.arrl.org/lotw-user-activity.csv
répond 6,2 Mo, 233 627 indicatifs, une ligne `CALL,AAAA-MM-JJ,HH:MM:SS`. Le
format n'a pas été supposé — le fichier a été téléchargé et lu.

LE POINT LE PLUS IMPORTANT DE CE MODULE : « on ne sait pas » n'est pas « non ».
Tant que la liste n'est pas téléchargée (premier lancement, poste hors réseau,
expédition), is_lotw_user() renvoie None et l'interface n'affiche rien. Si
elle renvoyait False, tout l'écran annoncerait « n'utilise pas LoTW » et
l'opérateur écarterait des stations parfaitement valables.
"""
import os
import sys

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CONCOURS not in sys.path:
    sys.path.insert(0, CONCOURS)

import logx_lotwusers as lu   # noqa: E402

CSV = ('F4GLD,2025-10-15,08:12:00\n'
       'K1ABC,2026-04-18,17:00:00\n'
       '2A/DJ6AU,2012-01-04,22:44:58\n')


@pytest.fixture(autouse=True)
def table_propre():
    """Le module garde sa table en mémoire : sans remise à zéro, un test
    hériterait de la liste chargée par le précédent."""
    lu._users.clear()
    lu._loaded = False
    yield
    lu._users.clear()
    lu._loaded = False


def _charger(csv=CSV):
    lu._users.update(lu._parse(csv))
    lu._loaded = True


# ─── « On ne sait pas » n'est pas « non » ────────────────────────────────────

def test_sans_liste_la_reponse_est_None_et_pas_False():
    """LE point du module. False ferait annoncer « n'utilise pas LoTW » à
    l'écran pour TOUT LE MONDE au premier lancement, et l'opérateur écarterait
    des stations parfaitement valables."""
    lu._loaded = True          # chargé, mais vide (pas de fichier)
    assert lu.is_lotw_user('F4GLD') is None
    assert lu.disponible() is False


def test_les_spots_annotes_sans_liste_portent_None():
    lu._loaded = True
    spots = [{'call': 'F4GLD'}, {'call': 'K1ABC'}]
    lu.annoter(spots)
    assert all(s['lotw'] is None for s in spots)
    assert all(s['lotw_last'] == '' for s in spots)


def test_avec_la_liste_la_reponse_devient_franche():
    _charger()
    assert lu.is_lotw_user('F4GLD') is True
    assert lu.is_lotw_user('ZZ9ZZZ') is False


# ─── Lecture du format ARRL ──────────────────────────────────────────────────

def test_la_date_du_dernier_envoi_est_conservee():
    """Un indicatif dont le dernier envoi remonte à 2012 est utilisateur LoTW
    sur le papier seulement : la date vaut autant que la présence."""
    _charger()
    assert lu.last_upload('F4GLD') == '2025-10-15'
    assert lu.last_upload('2A/DJ6AU') == '2012-01-04'
    assert lu.last_upload('ZZ9ZZZ') == ''


def test_les_dates_sont_partagees_en_memoire():
    """233 627 lignes pour 8 213 dates distinctes : sans partage la table pèse
    33,4 Mo au lieu de 18,5 (mesuré). Sur une expédition de 15 jours en
    continu, ces 15 Mo ne sont pas anecdotiques."""
    t = lu._parse('A1AA,2020-01-01,00:00:00\nB2BB,2020-01-01,00:00:00\n')
    a, b = t['A1AA'], t['B2BB']
    assert a is b, 'les dates identiques doivent partager le meme objet'


def test_une_ligne_malformee_est_ignoree_sans_tout_casser():
    t = lu._parse('BONJOUR\nA1AA,2020-01-01,00:00:00\n,,\n')
    assert t == {'A1AA': '2020-01-01'}


# ─── Indicatifs portables ────────────────────────────────────────────────────

def test_un_suffixe_portable_retombe_sur_l_indicatif_de_base():
    """Un spot porte souvent /P, /MM ou /QRP alors que la liste ARRL contient
    l'indicatif nu."""
    _charger()
    assert lu.is_lotw_user('F4GLD/P') is True
    assert lu.last_upload('F4GLD/MM') == '2025-10-15'


def test_un_indicatif_portable_PRESENT_TEL_QUEL_est_prefere():
    """Vérifié dans le vrai fichier : 2A/DJ6AU y figure en tant que tel. Le
    réduire à sa racine ferait perdre l'information — et DJ6AU seul n'est PAS
    dans la liste (constaté)."""
    _charger()
    assert lu.is_lotw_user('2A/DJ6AU') is True
    assert lu.is_lotw_user('DJ6AU') is False


def test_un_prefixe_pays_ne_masque_pas_l_indicatif():
    _charger('DJ6AU,2020-01-01,00:00:00\n')
    assert lu.is_lotw_user('F/DJ6AU') is True


# ─── Le cache ne doit jamais être remplacé par n'importe quoi ────────────────

@pytest.mark.parametrize('contenu', [
    '', 'trop court',
    '<html><head><title>503</title></head><body>Service indisponible</body></html>',
])
def test_une_reponse_douteuse_ne_remplace_pas_le_cache(contenu):
    """Même garde-fou que cty.dat : une page d'erreur ou un fichier tronqué
    écraserait une liste valide, et le poste perdrait l'information jusqu'au
    prochain téléchargement réussi — potentiellement jamais, en expédition."""
    assert lu._looks_valid(contenu) is False


def test_un_vrai_contenu_est_accepte():
    faux = 'A1AA,2020-01-01,00:00:00\n' * 30000   # > 500 ko, bien formé
    assert lu._looks_valid(faux) is True


def test_hors_reseau_le_fichier_actuel_est_conserve(tmp_path, monkeypatch):
    """Sans réseau, update_if_stale ne doit RIEN casser : un poste en
    expédition continue avec la liste qu'il a."""
    cache = tmp_path / 'lotw_users.csv'
    cache.write_text(CSV, encoding='utf-8')
    monkeypatch.setattr(lu, 'LOTW_FILE', str(cache))
    monkeypatch.setattr('logx_utils.fetch_url', lambda *a, **k: None)
    assert lu.update_if_stale(force=True) is False
    assert cache.read_text(encoding='utf-8') == CSV


def test_une_erreur_reseau_ne_leve_pas(tmp_path, monkeypatch):
    def _explose(*a, **k):
        raise OSError('reseau coupe')
    monkeypatch.setattr(lu, 'LOTW_FILE', str(tmp_path / 'absent.csv'))
    monkeypatch.setattr('logx_utils.fetch_url', _explose)
    assert lu.update_if_stale(force=True) is False


def test_le_telechargement_recharge_la_table_a_chaud(tmp_path, monkeypatch):
    gros = 'A1AA,2020-01-01,00:00:00\n' * 30000
    monkeypatch.setattr(lu, 'LOTW_FILE', str(tmp_path / 'lotw_users.csv'))
    monkeypatch.setattr('logx_utils.fetch_url', lambda *a, **k: gros)
    assert lu.update_if_stale(force=True) is True
    assert lu.is_lotw_user('A1AA') is True


# ─── Annotation d'une liste de spots ─────────────────────────────────────────

def test_annoter_pose_les_deux_champs():
    _charger()
    spots = [{'call': 'F4GLD'}, {'call': 'ZZ9ZZZ'}, {'dx': 'K1ABC'}]
    lu.annoter(spots)
    assert spots[0]['lotw'] is True and spots[0]['lotw_last'] == '2025-10-15'
    assert spots[1]['lotw'] is False and spots[1]['lotw_last'] == ''
    assert spots[2]['lotw'] is True, "la cle 'dx' doit etre reconnue aussi"


def test_annoter_supporte_une_liste_vide():
    _charger()
    assert lu.annoter([]) == []
    assert lu.annoter(None) is None
