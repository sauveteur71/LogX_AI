# -*- coding: utf-8 -*-
"""Filtres d'affichage des spots — inspirés de SET/FILTER des clusters CC.

POURQUOI CE MODULE EXISTE ALORS QUE LES SPOTS SONT DÉJÀ CLASSÉS. /data/spots_ranked
coupe à 40. Un samedi de CQ WW le cluster en débite plusieurs centaines : les 40
qui passent peuvent être 40 spots postés depuis le Japon, à propos de liaisons
qui n'existent pas depuis la France. C'est parce qu'on COUPE qu'il faut d'abord
ÉCARTER — et c'est pour ça que l'ordre des trois opérations, verrouillé plus
bas par un test de source, est le vrai sujet de ce fichier.

LES DEUX RÈGLES DE SÛRETÉ, chacune testée séparément : un spotteur dont on ne
sait pas le continent n'est jamais masqué, et un indicatif dont on ignore s'il
utilise LoTW non plus. « On ne sait pas » n'est pas « non » — sinon le filtre
viderait l'écran le premier jour, avant que lotw-user-activity.csv soit arrivé.

CE QUI N'EST PAS CONSTRUIT, ET POURQUOI : pas de filtre « spotteur à moins de
N km ». cty.dat donne la position du PAYS, pas de la station — W1AW et W6XX
rendent tous deux 37.6 / -91.87. Un test le prouve ci-dessous, pour que
personne ne rajoute ce critère en croyant bien faire.
"""
import json
import os
import re
import sys

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CONCOURS not in sys.path:
    sys.path.insert(0, CONCOURS)

import logx_spotfilter as sf   # noqa: E402

# EV-7 33e incrément : basculerContinent()/_SF_CONTINENTS (les deux seuls
# symboles lus depuis JS ci-dessous, via _fonction_js()/_liste_continents_js())
# ont été extraits vers logx_filtre_spots.js -- JS pointe désormais dessus.
JS = os.path.join(CONCOURS, 'logx_filtre_spots.js')
HTTP = os.path.join(CONCOURS, 'logx_http.py')


def spot(call='DX1AA', **kw):
    s = {'call': call, 'band': '14', 'freq': 14.020, 'spotter': 'F5ABC',
         'dx_continent': 'AS', 'already_done': False, 'lotw': True,
         'lotw_need_ici': True}
    s.update(kw)
    return s


# ─── Aucun réglage : le filtre ne doit rien retirer ──────────────────────────

@pytest.mark.parametrize('reglages', [None, {}, 'nimportequoi', 42, [],
                                      {'spotter_continents': []}])
def test_sans_reglage_rien_n_est_masque(reglages):
    spots = [spot('A'), spot('B')]
    gardes, c = sf.filtrer(spots, reglages)
    assert len(gardes) == 2 and c['masques'] == 0


def test_les_sept_continents_coches_valent_aucun_filtre():
    """Sinon l'écran annoncerait « filtre actif » alors qu'il ne retire rien,
    et la pastille d'alerte du bouton resterait allumée pour rien."""
    r = sf.reglages_valides({'spotter_continents': list(sf.CONTINENTS)})
    assert r['spotter_continents'] == []
    assert sf.actif(r) is False


# ─── Continent du spotteur : le critère qui compte ───────────────────────────

def test_seuls_les_spotteurs_du_continent_choisi_passent():
    spots = [spot('A', spotter='F5ABC'),      # EU
             spot('B', spotter='JA1XYZ'),     # AS
             spot('C', spotter='W1AW')]       # NA
    gardes, c = sf.filtrer(spots, {'spotter_continents': ['EU']})
    assert [s['call'] for s in gardes] == ['A']
    assert c['masques'] == 2
    assert c['par_critere'] == {'spotter_continents': 2}


def test_UN_SPOTTEUR_INCONNU_N_EST_JAMAIS_MASQUE():
    """Règle de sûreté. Certaines sources ne donnent pas le spotteur : filtrer
    sur une donnée absente punirait la source la plus pauvre, pas le spot le
    moins pertinent — et ferait disparaître des spots sans motif visible."""
    spots = [spot('SANS', spotter=''), spot('COURT', spotter='X'),
             spot('JA', spotter='JA1XYZ')]
    gardes, _ = sf.filtrer(spots, {'spotter_continents': ['EU']})
    assert [s['call'] for s in gardes] == ['SANS', 'COURT']


def test_le_continent_deja_calcule_est_reutilise():
    """logx_http annote spotter_continent en une passe avant de filtrer : la
    valeur posée doit primer sur un nouveau lookup cty.dat."""
    s = spot('A', spotter='JA1XYZ', spotter_continent='EU')
    assert sf.continent_spotteur(s) == 'EU'
    gardes, _ = sf.filtrer([s], {'spotter_continents': ['EU']})
    assert len(gardes) == 1


def test_POURQUOI_PAS_DE_FILTRE_PAR_DISTANCE():
    """Verrouille la raison d'une ABSENCE. cty.dat rend la position du PAYS :
    W1AW (Connecticut) et W6XX (Californie) tombent sur le même point. Un
    filtre « spotteur à moins de N km » aurait l'air de marcher et se
    tromperait de 4 000 km. Si un jour cty.dat devenait précis par indicatif,
    ce test tomberait — et le critère redeviendrait défendable."""
    import logx_dxcc as dxcc
    est, ouest = dxcc.lookup('W1AW'), dxcc.lookup('W6XX')
    assert (est['lat'], est['lon']) == (ouest['lat'], ouest['lon'])


# ─── Les autres critères ─────────────────────────────────────────────────────

def test_continent_de_la_station_dx():
    spots = [spot('A', dx_continent='AS'), spot('B', dx_continent='NA')]
    gardes, _ = sf.filtrer(spots, {'dx_continents': ['NA']})
    assert [s['call'] for s in gardes] == ['B']


def test_masquer_les_deja_travailles():
    spots = [spot('A', already_done=True), spot('B', already_done=False)]
    gardes, c = sf.filtrer(spots, {'masquer_deja_faits': True})
    assert [s['call'] for s in gardes] == ['B']
    assert c['par_critere'] == {'masquer_deja_faits': 1}


def test_UN_LOTW_INCONNU_N_EST_JAMAIS_MASQUE():
    """Deuxième règle de sûreté. lotw vaut True / False / None ; None veut dire
    « liste pas encore téléchargée », pas « n'utilise pas LoTW ». Masquer sur
    None viderait l'écran au premier démarrage."""
    spots = [spot('OUI', lotw=True), spot('NON', lotw=False),
             spot('INCONNU', lotw=None), spot('ABSENT')]
    spots[3].pop('lotw')
    gardes, _ = sf.filtrer(spots, {'seulement_lotw': True})
    assert [s['call'] for s in gardes] == ['OUI', 'INCONNU', 'ABSENT']


def test_seulement_les_besoins_dxcc():
    spots = [spot('A', lotw_need_ici=True), spot('B', lotw_need_ici=False)]
    gardes, _ = sf.filtrer(spots, {'seulement_besoins': True})
    assert [s['call'] for s in gardes] == ['A']


def test_les_criteres_se_cumulent():
    spots = [spot('BON', spotter='F5ABC', already_done=False),
             spot('FAIT', spotter='F5ABC', already_done=True),
             spot('LOIN', spotter='JA1XYZ', already_done=False)]
    gardes, c = sf.filtrer(spots, {'spotter_continents': ['EU'],
                                   'masquer_deja_faits': True})
    assert [s['call'] for s in gardes] == ['BON']
    assert c['masques'] == 2


def test_l_ordre_de_classement_est_conserve():
    """Le filtre retire, il ne retrie pas : le classement par valeur calculé en
    amont doit survivre intact."""
    spots = [spot('1'), spot('2', spotter='JA1XYZ'), spot('3'), spot('4')]
    gardes, _ = sf.filtrer(spots, {'spotter_continents': ['EU']})
    assert [s['call'] for s in gardes] == ['1', '3', '4']


# ─── Le repêchage par alerte ─────────────────────────────────────────────────

def test_un_spot_sous_alerte_TRAVERSE_le_filtre():
    """Décision de conception : une alerte de trop coûte trois secondes, une
    3Y0 manquée parce que seul un W l'avait spottée ne se rattrape pas. Sans ce
    repêchage, une alerte sonnerait pour un spot absent de la liste."""
    spots = [spot('RARE', spotter='W1AW'), spot('BANAL', spotter='W1AW')]
    gardes, c = sf.filtrer(spots, {'spotter_continents': ['EU']},
                           calls_alertes=['RARE'])
    assert [s['call'] for s in gardes] == ['RARE']
    assert gardes[0]['hors_filtre'] is True
    assert c['repeches'] == 1 and c['masques'] == 1


def test_un_spot_repeche_puis_redevenu_normal_perd_sa_marque():
    """Les dicts de spots sont réutilisés d'un rafraîchissement à l'autre : une
    marque hors_filtre oubliée laisserait un liseré jaune permanent."""
    s = spot('A', spotter='W1AW', hors_filtre=True)
    gardes, _ = sf.filtrer([s], {'spotter_continents': ['NA']})
    assert 'hors_filtre' not in gardes[0]


# ─── Robustesse ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize('brut,attendu', [
    ({'spotter_continents': 'eu,na'}, ['EU', 'NA']),
    ({'spotter_continents': ' eu ; as '}, ['EU', 'AS']),
    ({'spotter_continents': ['EU', 'EU']}, ['EU']),
    ({'spotter_continents': ['ZZ', 'EU']}, ['EU']),
    ({'spotter_continents': 'ZZ'}, []),
    ({'spotter_continents': None}, []),
    ({'spotter_continents': 12}, []),
])
def test_reglages_illisibles_degradent_vers_ne_rien_filtrer(brut, attendu):
    """Perdre un filtre est bénin ; masquer des spots par accident ne l'est
    pas. Le doute profite toujours à l'affichage."""
    assert sf.reglages_valides(brut)['spotter_continents'] == attendu


def test_un_spot_biscornu_s_affiche_au_lieu_de_disparaitre():
    spots = [{'call': None}, {}, spot('OK')]
    gardes, _ = sf.filtrer(spots, {'spotter_continents': ['EU'],
                                   'seulement_lotw': True})
    assert len(gardes) == 3


def test_liste_vide():
    assert sf.filtrer([], {'spotter_continents': ['EU']}) == ([], {
        'total': 0, 'gardes': 0, 'masques': 0, 'repeches': 0, 'par_critere': {}})
    assert sf.filtrer(None, None)[0] == []


def test_le_resume_annonce_toujours_ce_qui_est_cache():
    """Sans ce compte, une liste vide veut dire à la fois « le filtre coupe
    tout » et « le cluster est muet », qui appellent des réactions opposées."""
    assert sf.resume({'masques': 0}) == ''
    assert sf.resume({'masques': 1}) == '1 spot masqué'
    assert '12 spots masqués' in sf.resume({'masques': 12})
    assert 'alerte' in sf.resume({'masques': 3, 'repeches': 1})


# ─── L'ORDRE des opérations dans /data/spots_ranked ──────────────────────────

def test_LE_VRAI_SUJET_alertes_puis_filtre_puis_coupe_a_40():
    """L'invariant qui rend tout l'édifice correct, verrouillé sur la source.

    Les alertes voient TOUT le cluster (elles ne doivent rien rater), le filtre
    s'applique ENSUITE, et la coupe à 40 vient EN DERNIER. Filtrer après la
    coupe n'écarterait que ce qui a déjà survécu — c'est-à-dire rien d'utile.
    """
    src = open(HTTP, encoding='utf-8').read()
    bloc = src[src.index("if path == '/data/spots_ranked':"):]
    bloc = bloc[:bloc.index("if path == '/wsjtx/state':")]
    i_alertes = bloc.index('alerts.check_alerts')
    i_filtre = bloc.index('spotfilter.filtrer')
    i_coupe = bloc.index('visibles[:40]')
    assert i_alertes < i_filtre < i_coupe


def test_le_spotteur_est_bien_transmis_au_client():
    """Il existait dans le cache cluster mais mourait au moment de construire
    la réponse : sans lui, le filtre par continent de spotteur est aveugle."""
    src = open(HTTP, encoding='utf-8').read()
    bloc = src[src.index("if path == '/data/spots_ranked':"):]
    bloc = bloc[:bloc.index("if path == '/wsjtx/state':")]
    assert "'spotter': s.get('spotter', '')" in bloc


def test_le_reglage_ne_passe_PAS_par_config_save():
    """/config/save REMPLACE tout current_config. Un poste secondaire qui
    pousserait son filtre par cette route écraserait la configuration entière
    de la station. La route dédiée n'écrit qu'une clé."""
    src = open(HTTP, encoding='utf-8').read()
    bloc = src[src.index("if self.path == '/spots/filter':"):]
    bloc = bloc[:bloc.index('return', bloc.index('self._json'))]
    assert "current_config['spot_filter']" in bloc
    assert 'current_config.update' not in bloc


# ─── Côté navigateur : la bascule des pastilles ──────────────────────────────

py_mini_racer = pytest.importorskip('py_mini_racer')


def _fonction_js(nom):
    """Extrait une fonction du fichier LIVRÉ, par comptage d'accolades."""
    src = open(JS, encoding='utf-8').read()
    m = re.search(r'^function %s\(' % re.escape(nom), src, re.M)
    assert m, 'fonction introuvable : ' + nom
    i = src.index('{', m.start())
    prof = 0
    for j in range(i, len(src)):
        if src[j] == '{':
            prof += 1
        elif src[j] == '}':
            prof -= 1
            if prof == 0:
                return src[m.start():j + 1]
    raise AssertionError('accolade non refermee : ' + nom)


def _liste_continents_js():
    """La liste du client, lue dans le fichier livré — pas recopiée ici, sinon
    le test ne verrait jamais une divergence avec le serveur."""
    src = open(JS, encoding='utf-8').read()
    m = re.search(r'const _SF_CONTINENTS = (\[[^\]]*\]);', src)
    assert m, '_SF_CONTINENTS introuvable'
    return json.loads(m.group(1).replace("'", '"'))


def test_client_et_serveur_listent_LES_MEMES_continents():
    """Une pastille AN côté écran sans AN côté serveur donnerait un filtre qui
    masque tout sans que rien ne l'explique."""
    assert _liste_continents_js() == list(sf.CONTINENTS)


def _moteur_bascule(depart):
    ctx = py_mini_racer.MiniRacer()
    ctx.eval("""
        const _SF_CONTINENTS = %s;
        var _spotFiltre = {spotter_continents: %s, dx_continents: []};
        var envois = 0;
        function dessinerChipsFiltre(){}
        function majSpotFiltre(){ envois++; }
        %s
    """ % (json.dumps(list(sf.CONTINENTS)), json.dumps(depart),
           _fonction_js('basculerContinent')))
    return ctx


def _sel(ctx):
    return json.loads(ctx.eval('JSON.stringify(_spotFiltre.spotter_continents)'))


def test_depuis_TOUS_le_premier_clic_ENLEVE_le_continent_clique():
    """Les sept pastilles sont allumées quand la liste est vide (= tous). Un
    clic sur EU doit vouloir dire « plus d'EU », pas « EU seulement » — c'est
    l'inverse qu'on obtient si on part de la liste vide au lieu de la pleine."""
    ctx = _moteur_bascule([])
    ctx.eval("basculerContinent('spotter_continents','EU')")
    reste = _sel(ctx)
    assert 'EU' not in reste and len(reste) == len(sf.CONTINENTS) - 1


def test_recliquer_rallume():
    ctx = _moteur_bascule([])
    ctx.eval("basculerContinent('spotter_continents','EU')")
    ctx.eval("basculerContinent('spotter_continents','EU')")
    assert _sel(ctx) == [], 'les sept coches doivent retomber sur le joker'


def test_tout_eteindre_ne_vide_pas_l_ecran():
    """Décocher le dernier continent revient à « tous », pas à « rien » : une
    liste vide sans explication est le pire état possible pendant un concours."""
    ctx = _moteur_bascule(['EU'])
    ctx.eval("basculerContinent('spotter_continents','EU')")
    assert _sel(ctx) == []


def test_chaque_bascule_enregistre_le_reglage():
    ctx = _moteur_bascule([])
    ctx.eval("basculerContinent('spotter_continents','EU')")
    assert ctx.eval('envois') == 1
