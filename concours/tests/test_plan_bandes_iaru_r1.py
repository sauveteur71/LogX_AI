# -*- coding: utf-8 -*-
"""Le plan de bandes du logiciel confronté à la référence IARU R1 / France.

D'OÙ VIENT CE FICHIER. La table de créneaux de logx_awards venait de l'annexe C
du manuel CC Cluster. Elle est excellente — et elle décrit l'AMÉRIQUE DU NORD.
Je l'avais reprise sans vérifier à quelle région UIT elle s'applique, puis
construite dessus : déduction du mode d'un spot, réglette des fenêtres par
bande, filtre de mode de la page FOCUS, alertes « pas confirmé LoTW ».

QUATRE DÉFAUTS MESURÉS, tous corrigés ici :

  1. FT8 mal classé sur SIX bandes sur douze — PHONE sur 6 m, 2 m et 70 cm, CW
     sur 160, 80 et 12 m. C'est la suite directe du reproche de l'utilisateur
     (« si je passe en SSB je veux voir QUE les spots SSB ») : sur 2 m, le
     filtre SSB lui servait du FT8. Le mode le plus utilisé au monde, sur les
     bandes de concours THF qu'il pratique.

  2. Bornes de région 2 : 40 m jusqu'à 7,300 · 80 m jusqu'à 4,000 · 160 m
     jusqu'à 2,000 · 6 m jusqu'à 54 · 2 m jusqu'à 148 · et une bande 222 MHz
     qui n'existe pas en Europe. La réglette montrait à un opérateur français
     des centaines de kHz où il n'a pas le droit d'émettre.

  3. Le 4 m (70 MHz) proposé comme bande standard alors qu'il N'EST PAS
     attribué aux amateurs en France.

  4. Une bande WARC pouvait recevoir le liseré « bande recommandée » pendant un
     concours, alors que la convention IARU y interdit les concours.

POURQUOI DEUX MÉCANISMES DIFFÉRENTS (et pas une simple coupe). Classer un spot
et dessiner une bande n'ont pas le même besoin : une station de région 2 à
7,250 MHz fait bien de la phonie et le dire est utile, mais la réglette doit
montrer où L'OPÉRATEUR peut travailler. D'où le drapeau `fr` sur chaque ligne.
"""
import os
import sys

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CONCOURS not in sys.path:
    sys.path.insert(0, CONCOURS)

import logx_awards as aw      # noqa: E402
import logx_focus as fo       # noqa: E402


# ─── 1. Les fréquences d'appel numériques ────────────────────────────────────
# Elles sont IDENTIQUES dans les trois régions UIT — c'est tout l'intérêt de la
# convention FT8/FT4. Et plusieurs tombent dans un segment que le plan de
# bandes officiel déclare « phonie » : les conventions numériques se sont
# installées là où il restait de la place, sans redécoupage du plan. Un
# découpage par plages ne peut donc PAS y arriver seul.

FT8 = [
    (1.840, '160 m'), (3.573, '80 m'), (7.074, '40 m'), (10.136, '30 m'),
    (14.074, '20 m'), (18.100, '17 m'), (21.074, '15 m'), (24.915, '12 m'),
    (28.074, '10 m'), (50.313, '6 m'), (144.174, '2 m'), (432.174, '70 cm'),
]


@pytest.mark.parametrize('mhz,bande', FT8)
def test_FT8_est_du_NUMERIQUE_sur_les_douze_bandes(mhz, bande):
    assert aw.mode_depuis_frequence(mhz) == 'DIGITAL', bande


@pytest.mark.parametrize('mhz', [50.313, 144.174, 432.174])
def test_le_cas_qui_a_declenche_tout_ca_le_FT8_en_THF(mhz):
    """Ces trois-là étaient classées PHONE : le filtre SSB de la page FOCUS
    affichait donc du FT8 sur 6 m, 2 m et 70 cm — précisément les bandes des
    concours THF français."""
    assert aw.mode_depuis_frequence(mhz) != 'PHONE'


@pytest.mark.parametrize('mhz', [3.575, 7.0475, 14.080, 21.140, 28.180])
def test_FT4_aussi(mhz):
    assert aw.mode_depuis_frequence(mhz) == 'DIGITAL'


@pytest.mark.parametrize('mhz', [1.8366, 3.5686, 7.0386, 14.0956, 28.1246])
def test_WSPR_aussi(mhz):
    """WSPR est une balise de propagation à très faible puissance. Elle vit
    DANS le segment CW de chaque bande — d'où le classement en CW auparavant."""
    assert aw.mode_depuis_frequence(mhz) == 'DIGITAL'


# Le correctif ne doit pas tout numériser : un créneau numérique fait 3 kHz.
@pytest.mark.parametrize('mhz,attendu', [
    (14.020, 'CW'), (14.070, 'DIGITAL'), (14.250, 'PHONE'),
    (7.030, 'CW'), (7.150, 'PHONE'),
    (144.050, 'CW'), (144.300, 'PHONE'),
    (50.150, 'PHONE'), (432.200, 'PHONE'),
    (21.300, 'PHONE'), (28.400, 'PHONE'),
])
def test_le_voisinage_immediat_n_a_pas_bouge(mhz, attendu):
    assert aw.mode_depuis_frequence(mhz) == attendu


def test_un_creneau_numerique_reste_ETROIT():
    """3 kHz au-dessus de la fréquence affichée, pas davantage : sinon on
    reclasserait en numérique des QSO SSB voisins."""
    assert aw.mode_depuis_frequence(144.174) == 'DIGITAL'
    assert aw.mode_depuis_frequence(144.180) == 'PHONE'


# ─── 2. Hors des bandes françaises ───────────────────────────────────────────

HORS = [
    (1.900, '160 m France : 1,810-1,850'),
    (3.900, '80 m France : 3,500-3,800'),
    (7.250, '40 m France : 7,000-7,200'),
    (53.000, '6 m France : 50-52'),
    (147.000, '2 m région 1 : 144-146'),
    (223.000, 'la bande 222 MHz est propre à la région 2'),
    (70.200, '4 m non attribué aux amateurs en France'),
]


@pytest.mark.parametrize('mhz,pourquoi', HORS)
def test_une_frequence_hors_bande_est_SIGNALEE(mhz, pourquoi):
    assert aw.hors_bande_france(mhz) is True, pourquoi


@pytest.mark.parametrize('mhz,pourquoi', HORS)
def test_mais_elle_reste_CLASSEE(mhz, pourquoi):
    """Signaler n'est pas masquer. Une station de région 2 à 7,250 MHz est
    parfaitement en règle chez elle, et l'entendre est instructif. Ce qui ne
    l'est pas, c'est de lui répondre — ou de laisser un clic commander le QSY
    sans rien dire."""
    assert aw.mode_depuis_frequence(mhz) != ''


@pytest.mark.parametrize('mhz', [1.830, 3.750, 7.100, 14.250, 21.200,
                                 28.400, 50.150, 144.300, 432.200])
def test_une_frequence_francaise_n_est_pas_signalee(mhz):
    assert aw.hors_bande_france(mhz) is False


@pytest.mark.parametrize('valeur', [None, '', 'abc', 0, 999.0])
def test_une_valeur_inexploitable_ne_declenche_pas_l_alerte(valeur):
    """On ne signale que ce dont on est sûr : une alerte « hors bande » sur une
    fréquence illisible ferait douter l'opérateur d'un spot valide."""
    assert aw.hors_bande_france(valeur) is False


# ─── 3. Le 30 m, cas particulier strict ──────────────────────────────────────

@pytest.mark.parametrize('mhz', [10.100, 10.120, 10.136, 10.149])
def test_le_30m_est_CW_et_data_UNIQUEMENT(mhz):
    """Règle stricte du plan de bandes : jamais de phonie sur 30 m. Un spot
    classé PHONE ici serait le signe que la table a dérivé."""
    assert aw.mode_depuis_frequence(mhz) in ('CW', 'DIGITAL')


# ─── 4. Les bandes proposées par la page FOCUS ───────────────────────────────

def test_le_4m_n_est_PAS_propose():
    """Il est attribué dans plusieurs pays de région 1 (G, OZ, OH…), pas en
    France. Proposer une bande où l'utilisateur ne peut pas émettre, sur une
    page dont le rôle est de dire « va travailler là », est une faute."""
    assert '70' not in fo.BANDES_STANDARD


def test_mais_il_reste_atteignable_si_un_spot_y_tombe():
    """Le cas de l'expédition dans un pays qui l'attribue."""
    bandes = fo.bandes_a_proposer(spots=[{'freq': 70.200, 'band': '70'}])
    assert '70' in bandes


@pytest.mark.parametrize('b', ['1.8', '3.5', '7', '10.1', '14', '18', '21',
                               '24', '28', '50', '144', '432'])
def test_toutes_les_bandes_francaises_sont_proposees(b):
    assert b in fo.BANDES_STANDARD


# ─── 5. Pas de bande WARC recommandée pendant un concours ────────────────────
# Convention IARU : pas de concours sur 30 · 17 · 12 m. Ce sont les bandes de
# repli du trafic courant pendant qu'une épreuve occupe tout le reste.

def _spots(bande, mhz, n=40):
    return [{'freq': mhz + i / 1000.0, 'call': 'DX%d' % i, 'band': bande}
            for i in range(n)]


def test_une_WARC_pleine_de_spots_n_est_pas_recommandee_en_concours():
    """MESURÉ AVANT CORRECTION : concours sur 14 MHz, 40 spots sur 18 MHz, et
    la page collait le liseré vert sur le 17 m. Elle envoyait l'opérateur faire
    des QSO de concours là où la convention les interdit — des points refusés
    au dépouillement."""
    res = fo.classer_bandes(['14', '18'], spots=_spots('18', 18.100),
                            bandes_concours=['14'])
    reco = [c['band'] for c in res if c.get('recommandee')]
    assert '18' not in reco, reco


def test_c_est_bien_la_bande_du_concours_qui_est_recommandee():
    res = fo.classer_bandes(['14', '18'],
                            spots=_spots('18', 18.100) + _spots('14', 14.100, 5),
                            bandes_concours=['14'])
    reco = [c['band'] for c in res if c.get('recommandee')]
    assert reco == ['14'], reco


def test_hors_concours_la_WARC_redevient_recommandable():
    """C'est même une excellente bande : tranquille et ouverte. La restriction
    porte sur le concours, pas sur la bande."""
    res = fo.classer_bandes(['14', '18'], spots=_spots('18', 18.100),
                            bandes_concours=[])
    assert [c['band'] for c in res if c.get('recommandee')] == ['18']


def test_la_WARC_reste_AFFICHEE_avec_son_score():
    """On bride la RECOMMANDATION, pas l'affichage : pendant un concours on
    peut vouloir aller souffler sur le 17 m, et il faut voir ce qui s'y passe."""
    res = fo.classer_bandes(['14', '18'], spots=_spots('18', 18.100),
                            bandes_concours=['14'])
    warc = [c for c in res if c['band'] == '18'][0]
    assert warc['spots'] > 0 and warc['score'] > 0
    assert warc['warc'] is True


@pytest.mark.parametrize('b', ['10.1', '18', '24'])
def test_les_trois_bandes_WARC_sont_marquees(b):
    res = fo.classer_bandes([b], bandes_concours=['14'])
    assert res[0]['warc'] is True


@pytest.mark.parametrize('b', ['3.5', '7', '14', '21', '28'])
def test_les_bandes_de_concours_ne_sont_pas_marquees_WARC(b):
    res = fo.classer_bandes([b], bandes_concours=['14'])
    assert res[0]['warc'] is False


# ─── 6. Les DEUX tables de bandes du logiciel doivent s'accorder ─────────────
#
# Il y en a deux, pour deux usages différents : _CRENEAUX_KHZ (logx_awards)
# découpe les bandes en segments de mode, BANDES_MHZ (logx_transverter) donne
# les bornes d'allocation au pilotage des transverters.
#
# ELLES NE S'ACCORDAIENT PAS. La seconde décrivait encore la région 2 — 6 m
# jusqu'à 54 MHz, 2 m jusqu'à 148 — après correction de la première. Deux
# sources qui divergent sur la même grandeur, c'est exactement la forme du bug
# d'unités kHz/MHz qui avait rendu le band map muet pendant des mois. Le test
# ci-dessous existe pour que ça ne recommence pas.

def _bornes_awards(cle_mhz):
    """Bornes d'une bande vues par la table des segments de logx_awards."""
    seg = aw.segments_bande(cle_mhz)
    return (seg['lo'], seg['hi']) if seg else None


@pytest.mark.parametrize('cle', ['50', '144', '432'])
def test_les_deux_tables_de_bandes_donnent_les_MEMES_bornes(cle):
    import logx_transverter as tv
    attendu = tv.BANDES_MHZ[cle]
    obtenu = _bornes_awards(cle)
    assert obtenu is not None, cle
    assert abs(obtenu[0] - attendu[0]) < 1e-6, (cle, obtenu, attendu)
    assert abs(obtenu[1] - attendu[1]) < 1e-6, (cle, obtenu, attendu)


@pytest.mark.parametrize('cle,haut', [('50', 52.0), ('144', 146.0)])
def test_les_bornes_de_region_2_ont_bien_disparu_des_DEUX_tables(cle, haut):
    """50-54 et 144-148 sont les allocations de région 2. Un opérateur de
    région 1 n'y a pas accès."""
    import logx_transverter as tv
    assert tv.BANDES_MHZ[cle][1] == haut, cle
    assert abs(_bornes_awards(cle)[1] - haut) < 1e-6, cle


def test_les_bandes_hyperfrequences_ONT_MAINTENANT_leurs_segments():
    """CE TEST DISAIT L'INVERSE, et c'était voulu : il figeait l'absence de
    segments au-dessus de 440 MHz tant que je n'avais pas de source, avec cette
    consigne — « le jour où les segments seront ajoutés depuis une vraie
    source, il tombera et rappellera de le mettre à jour ». C'est arrivé le
    31/07/2026 : F4GLD a fourni le plan IARU R1 (édition 2017/Landshut).

    Les segments vivent dans logx_bandplan_vhf, qui garde le vocabulaire de la
    source (ATV, satellite, balises exclusives, largeurs nationales) ; la
    réglette n'en reçoit que ce qui se colore."""
    for cle in ('1296', '2320', '3400', '5760', '10368', '24048'):
        r = aw.segments_bande(cle)
        assert r is not None, cle
        assert r['segments'], cle


def test_la_reglette_ECARTE_ce_qu_elle_ne_sait_pas_colorer():
    """ATV et satellite n'ont pas d'équivalent parmi CW / numérique / phonie.
    Les ranger de force dans « phonie » dessinerait une réglette qui ment :
    mieux vaut un trou. Sur 23 cm, ATV et satellite occupent l'essentiel de
    1243-1291 — la réglette doit donc y montrer moins de segments que le plan
    n'en compte."""
    import logx_bandplan_vhf as bpv
    plan = bpv.segments('1296')
    reglette = aw.segments_bande('1296')['segments']
    assert len(reglette) < len(plan), (len(reglette), len(plan))
    for s in reglette:
        assert s['cat'] in ('CW', 'DIGITAL', 'PHONE'), s


def test_si_TOUTES_les_bandes_sont_WARC_on_recommande_quand_meme():
    """Cas tordu mais réel : un concours dont la seule bande visible est une
    WARC (World Wide Award, qui les utilise). Mieux vaut recommander que de
    laisser la page sans repère."""
    res = fo.classer_bandes(['18'], spots=_spots('18', 18.100),
                            bandes_concours=['18'])
    assert [c['band'] for c in res if c.get('recommandee')] == ['18']
