# -*- coding: utf-8 -*-
"""CAT Yaesu : deux protocoles, et le pilote natif n'en parle qu'un.

TROUVÉ EN CONFRONTANT logx_cat.py À LA FICHE CAT DU SKILL RADIOAMATEUR.

DÉFAUT 1 — LA FRÉQUENCE NE PARTAIT PAS AU BON FORMAT.
`ascii_encode_freq_cmd` envoyait 11 chiffres à TOUT LE MONDE, avec cette
justification écrite dans son docstring : « les modèles Yaesu acceptent aussi
ce format, au pire des zéros de tête surnuméraires sans effet ». C'était une
supposition, pas une lecture de manuel. Le CAT ASCII Yaesu est à CHAMPS DE
LARGEUR FIXE : `FA` y prend 9 chiffres.

Le code se contredisait lui-même : `_IF_FIELDS['yaesu']` déclare 9 chiffres
pour LIRE la fréquence. On en lisait 9 et on en écrivait 11. Conséquence sur
FT-891, FT-991/991A, FTDX10, FTDX101 : **cliquer un spot ne faisait pas changer
la radio de fréquence** — la fonction principale du logiciel.

DÉFAUT 2 — QUATRE POSTES PROPOSÉS QUI NE PEUVENT PAS RÉPONDRE.
Yaesu a deux familles CAT : ASCII (FT-891, FT-991, FTDX…) et BINAIRE 5 octets
(FT-817/818/857/897, FT-847, FT-100). La page CONFIG proposait les quatre
postes binaires ; le pilote leur envoyait « IF; ». Ils ne répondent jamais —
pas d'erreur, pas de trame, juste le silence, exactement le même symptôme qu'un
câble débranché. Ce sont des postes très répandus en portable et en expédition,
soit précisément l'usage que ce logiciel revendique.

RÉSERVE HONNÊTE : le format 9 chiffres vient de la fiche CAT et de la
cohérence avec le chemin de lecture déjà en place. Je n'ai pas de FT-991A pour
le vérifier sur l'air.
"""
import os
import sys

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CONCOURS not in sys.path:
    sys.path.insert(0, CONCOURS)

import logx_cat as C   # noqa: E402


class FauxPort:
    """Poste muet : enregistre ce qu'on lui écrit, ne répond rien."""

    def __init__(self):
        self.ecrit = []

    def write(self, data):
        self.ecrit.append(data)

    def read_until(self, sep, timeout=1.0):
        return b''

    def close(self):
        pass


# ─── 1. Largeur du champ fréquence ───────────────────────────────────────────

def test_yaesu_recoit_NEUF_chiffres():
    assert C.ascii_encode_freq_cmd('FA', 14074000, 'yaesu') == 'FA014074000;'


def test_kenwood_recoit_ONZE_chiffres():
    assert C.ascii_encode_freq_cmd('FA', 14074000, 'kenwood') == 'FA00014074000;'


def test_elecraft_recoit_ONZE_chiffres():
    assert C.ascii_encode_freq_cmd('FA', 7100000, 'elecraft') == 'FA00007100000;'


def test_sans_marque_on_garde_le_comportement_majoritaire():
    """Un appelant qui ne passe pas la marque ne doit pas voir son
    comportement changer — Kenwood/Elecraft sont les deux tiers des cas."""
    assert C.ascii_encode_freq_cmd('FA', 14074000) == 'FA00014074000;'


def test_LA_LECTURE_ET_L_ECRITURE_S_ACCORDENT():
    """LE test de fond. La table de lecture déclare la largeur du champ
    fréquence par marque ; l'écriture doit poser exactement la même. C'est
    leur désaccord qui constituait le défaut, et rien ne le signalait."""
    for brand, (_deb, longueur, _mp, _ml) in C._IF_FIELDS.items():
        cmd = C.ascii_encode_freq_cmd('FA', 14074000, brand)
        chiffres = ''.join(c for c in cmd if c.isdigit())
        assert len(chiffres) == longueur, (brand, cmd, longueur)


@pytest.mark.parametrize('brand', ['yaesu', 'kenwood', 'elecraft'])
def test_la_frequence_reste_juste_apres_encodage(brand):
    cmd = C.ascii_encode_freq_cmd('FA', 14074000, brand)
    assert int(cmd[2:-1]) == 14074000, cmd


def test_le_pilote_utilise_bien_la_marque():
    """La fonction pouvait être corrigée sans que l'appelant lui passe la
    marque — le défaut serait resté entier."""
    p = FauxPort()
    C.AsciiRadio(p, brand='yaesu', model='FT-991A').set_freq(14074000)
    assert p.ecrit == [b'FA014074000;'], p.ecrit


def test_et_le_kenwood_n_a_pas_ete_casse_au_passage():
    p = FauxPort()
    C.AsciiRadio(p, brand='kenwood', model='TS-590SG').set_freq(14074000)
    assert p.ecrit == [b'FA00014074000;'], p.ecrit


# ─── 2. Les postes au CAT binaire ────────────────────────────────────────────

BINAIRES = ['FT-817', 'FT-818', 'FT-857', 'FT-897']


@pytest.mark.parametrize('modele', BINAIRES)
def test_un_poste_binaire_est_refuse_AVEC_UNE_EXPLICATION(modele):
    msg = C.modele_non_pilotable(modele)
    assert msg, modele
    assert 'Hamlib' in msg or 'rigctld' in msg, msg


@pytest.mark.parametrize('modele', ['FT-891', 'FT-991A', 'FTDX10', 'FTDX101D',
                                    'TS-590SG', 'K3', 'IC-7300'])
def test_un_poste_pilotable_n_est_pas_refuse(modele):
    assert C.modele_non_pilotable(modele) is None, modele


def test_la_casse_et_les_espaces_ne_font_pas_passer_a_travers():
    """Le modèle vient d'un champ de configuration : il peut arriver en
    minuscules ou avec une espace."""
    for v in ('ft-857', '  FT-857 ', 'Ft-857'):
        assert C.modele_non_pilotable(v), v


@pytest.mark.parametrize('valeur', [None, '', '   '])
def test_un_modele_vide_ne_bloque_pas(valeur):
    """Sans modèle renseigné, on laisse la connexion se tenter : la marque
    suffit souvent."""
    assert C.modele_non_pilotable(valeur) is None


def test_le_refus_arrive_AVANT_l_ouverture_du_port(monkeypatch):
    """Le refus doit précéder l'ouverture du port série : sinon on attend un
    timeout, et « pas de réponse » est indiscernable d'un câble débranché."""
    ouvertures = []

    def faux_open(port, baudrate=None, **kw):
        ouvertures.append(port)
        return FauxPort()

    monkeypatch.setattr(C, '_open_serial', faux_open)
    C.disconnect_persistent()
    driver, err = C._ensure_connected({
        'enabled': True, 'mode': 'native', 'brand': 'yaesu',
        'model': 'FT-857', 'port': 'COM9', 'baudrate': 4800,
    })
    assert driver is None
    assert err and 'Hamlib' in err
    assert ouvertures == [], 'le port a ete ouvert alors que le modele est refuse'


def test_un_modele_pilotable_ouvre_bien_le_port(monkeypatch):
    """Garde-fou en miroir : le refus ne doit pas bloquer les postes valides."""
    ouvertures = []

    def faux_open(port, baudrate=None, **kw):
        ouvertures.append(port)
        return FauxPort()

    monkeypatch.setattr(C, '_open_serial', faux_open)
    C.disconnect_persistent()
    driver, err = C._ensure_connected({
        'enabled': True, 'mode': 'native', 'brand': 'yaesu',
        'model': 'FT-991A', 'port': 'COM9', 'baudrate': 38400,
    })
    C.disconnect_persistent()
    assert err is None and driver is not None
    assert ouvertures == ['COM9']


# ─── 3. La page CONFIG et le pilote doivent s'accorder ───────────────────────

def test_les_postes_refuses_sont_MARQUES_dans_la_page_config():
    """Un poste refusé côté serveur mais proposé sans mention côté page, c'est
    l'opérateur qui le découvre en concours."""
    html = os.path.join(CONCOURS, 'logx_configuration.html')
    with open(html, encoding='utf-8') as f:
        src = f.read()
    bloc = src[src.index('const CAT_MODELS'):src.index('const CAT_DEFAULT_BAUD')]
    for modele in BINAIRES:
        i = bloc.index("'%s'" % modele)
        assert "'hamlib'" in bloc[i:i + 40], modele


def test_la_page_affiche_la_mention_a_l_ecran():
    html = os.path.join(CONCOURS, 'logx_configuration.html')
    with open(html, encoding='utf-8') as f:
        src = f.read()
    assert 'rigctld/Hamlib' in src


# ─── 3. Le carnet et la radio ne parlaient pas la même langue ────────────────
#
# MESURÉ AVANT CORRECTION : « SSB » — mode par défaut au démarrage, et de loin
# le plus utilisé — ne correspondait à AUCUNE entrée, sur AUCUNE marque. La
# radio veut LSB ou USB. Cliquer un spot changeait donc la fréquence en
# laissant la radio dans le mode précédent, et l'échec était avalé.

@pytest.mark.parametrize('mhz,attendu', [
    (1.840, 'LSB'), (3.750, 'LSB'), (7.150, 'LSB'),      # 160/80/40 m
    (14.250, 'USB'), (21.300, 'USB'), (28.400, 'USB'),   # 20 m et au-dessus
    (50.150, 'USB'), (144.300, 'USB'), (432.200, 'USB'),  # VHF/UHF
])
def test_SSB_devient_LSB_ou_USB_selon_la_bande(mhz, attendu):
    """LSB sur 160/80/40 m, USB à partir du 20 m et sur toute la VHF/UHF."""
    assert C.normaliser_mode('SSB', mhz * 1e6) == attendu


@pytest.mark.parametrize('mode', ['FT8', 'FT4', 'JS8', 'PSK', 'PSK31', 'RTTY',
                                  'MSK144', 'Q65', 'JT65', 'DIGITAL', 'DATA'])
@pytest.mark.parametrize('brand', ['yaesu', 'kenwood', 'elecraft', 'icom'])
def test_tout_mode_numerique_atteint_une_entree_reelle(mode, brand):
    """Aucun ne doit retomber dans le vide."""
    nom = C.normaliser_mode(mode, 14.074e6, brand)
    if brand == 'icom':
        assert nom in C.CIV_MODES, (mode, brand, nom)
    else:
        assert nom in C.ASCII_MODES[brand + '_rev'], (mode, brand, nom)


@pytest.mark.parametrize('mhz', [3.573, 7.074, 10.136])
def test_LE_NUMERIQUE_RESTE_EN_USB_SOUS_10_MHz(mhz):
    """LE piège. La phonie est en LSB sur 80 et 40 m, mais le FT8 y est en USB
    — comme sur toutes les bandes. Appliquer la règle de la phonie au FT8
    mettrait la radio en LSB sur 7,074 : la station serait inaudible."""
    for brand in ('kenwood', 'elecraft', 'icom'):
        assert C.normaliser_mode('FT8', mhz * 1e6, brand) == 'USB', brand
    assert C.normaliser_mode('FT8', mhz * 1e6, 'yaesu') == 'DATA-USB'


def test_le_yaesu_a_bien_un_creneau_DATA():
    """Il manquait de la table : la radio ne pouvait pas être mise en
    numérique par le logiciel."""
    assert C.ASCII_MODES['yaesu_rev']['DATA-USB'] == 'C'


@pytest.mark.parametrize('mode', ['SSB', 'CW', 'FM', 'AM', 'RTTY', 'FT8',
                                  'FT4', 'PSK', 'USB', 'LSB'])
@pytest.mark.parametrize('brand', ['yaesu', 'kenwood', 'elecraft'])
def test_AUCUN_mode_du_carnet_ne_tombe_dans_le_vide(mode, brand):
    """Le test qui aurait attrapé le défaut : passer TOUT le vocabulaire du
    carnet, pas seulement celui que la table connaissait déjà."""
    assert C.ascii_encode_mode_cmd(mode, brand, freq_hz=14.074e6), (mode, brand)


@pytest.mark.parametrize('mode', ['SSB', 'CW', 'FM', 'AM', 'RTTY', 'FT8', 'PSK'])
def test_idem_cote_Icom(mode):
    assert C.CIV_MODES.get(C.normaliser_mode(mode, 14.074e6, 'icom')) is not None, mode


def test_sans_frequence_on_choisit_USB():
    """Le moins dommageable : USB couvre 20 m et au-dessus plus toute la
    VHF/UHF, et une erreur de bande latérale s'entend tout de suite."""
    assert C.normaliser_mode('SSB') == 'USB'
    assert C.normaliser_mode('SSB', None) == 'USB'
    assert C.normaliser_mode('SSB', 'abc') == 'USB'


@pytest.mark.parametrize('valeur', [None, '', '   '])
def test_un_mode_vide_reste_vide(valeur):
    assert C.normaliser_mode(valeur) == ''


def test_un_mode_deja_correct_traverse_sans_changement():
    for m in ('CW', 'AM', 'FM', 'USB', 'LSB'):
        assert C.normaliser_mode(m, 14e6, 'yaesu') == m


def test_la_casse_et_le_soulignement_sont_tolerés():
    """Les modes viennent de sources variées : ADIF, cluster, WSJT-X."""
    assert C.normaliser_mode('ssb', 14e6) == 'USB'
    assert C.normaliser_mode('ft8', 14e6, 'yaesu') == 'DATA-USB'
    assert C.normaliser_mode('js8call', 14e6, 'kenwood') == 'USB'


def test_l_echec_du_mode_n_est_plus_avale(monkeypatch):
    """set_freq ignorait le retour de set_mode : la radio restait dans son
    mode précédent sans que rien ne le dise. C'est ce silence qui a laissé
    « SSB » inconnu passer inaperçu pendant tout le développement."""
    class Radio:
        def set_freq(self, hz):
            return {'ok': True}

        def set_mode(self, mode, freq_hz=None):
            return {'ok': False, 'error': 'Mode inconnu pour yaesu : ZZZ'}

    monkeypatch.setattr(C, '_ensure_connected', lambda s: (Radio(), None))
    monkeypatch.setattr(C, 'cat_settings',
                        lambda cfg: {'enabled': True, 'mode': 'native'})
    r = C.set_freq({}, 14074000, 'ZZZ')
    assert r['ok'] is True
    assert 'mode_error' in r, r
