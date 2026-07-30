# -*- coding: utf-8 -*-
"""Locator tracker : carrés QRA entendus en FT8/FT4, croisés avec le carnet.

DEMANDE UTILISATEUR : « un locator tracker… tu vois les calls décodés et ça te
dit si tu as déjà le carré locator ou pas », avec son et couleur.

LA RÈGLE DE PORTÉE, tranchée par l'utilisateur et c'est elle qui distingue ce
tracker de GridTracker : « en concours ce sera uniquement sur la durée du
concours, mais ça peut être intéressant de le mettre devant les autres si en
plus il n'est pas dans mon log à vie ». Un carré travaillé en 2019 reste un
MULTIPLICATEUR à faire ce week-end : il doit sonner. Celui qui manque aussi au
carnet à vie vaut double et passe devant.

LE PIÈGE QUI CASSE LES IMPLÉMENTATIONS MAISON, et il est vérifié ici : « RR73 »
CORRESPOND au motif d'un carré Maidenhead — RR est un champ valide, 73 des
chiffres valides. Un parseur naïf invente donc un carré en Sibérie à chaque fin
de QSO, c'est-à-dire à peu près tout le temps.
"""
import os
import sys

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CONCOURS not in sys.path:
    sys.path.insert(0, CONCOURS)

import logx_awards as aw    # noqa: E402
import logx_wsjtx as w      # noqa: E402


# ─── Extraction du carré dans un décodage ────────────────────────────────────

@pytest.mark.parametrize('msg,attendu', [
    ('CQ F4ABC JN18', 'JN18'),
    ('CQ DX K1ABC FN42', 'FN42'),
    ('F5XYZ F4ABC JN18', 'JN18'),
    ('F5XYZ F4ABC IO91WM', 'IO91WM'),
    ('F5XYZ F4ABC -15', ''),
    ('F5XYZ F4ABC R-09', ''),
    ('CQ PJ4/K1ABC', ''),
    ('', ''),
])
def test_extraction_du_carre(msg, attendu):
    assert w.extract_grid(msg) == attendu


@pytest.mark.parametrize('fin', ['RR73', 'RRR', '73'])
def test_LE_PIEGE_les_fins_de_QSO_ne_sont_pas_des_carres(fin):
    """RR73 passe le motif Maidenhead : sans filtrage préalable, chaque fin de
    QSO inventerait un carré. C'est LE défaut classique de ces parseurs."""
    assert w.extract_grid('F5XYZ F4ABC ' + fin) == ''


def test_RR73_correspond_BIEN_au_motif_carre():
    """Verrouille la RAISON du test précédent : si un jour le motif changeait
    et cessait d'accepter RR73, le filtrage deviendrait inutile — mais si le
    filtrage sautait, plus rien ne signalerait le problème."""
    assert w._GRID_RE.match('RR73') is not None
    assert 'RR73' in w._DECODE_SKIP_TOKENS


# ─── Persistance du carré sur la durée d'un QSO ──────────────────────────────

def test_le_carre_survit_aux_messages_qui_n_en_portent_pas():
    """Sur un QSO FT8, « CQ F4ABC JN18 » est suivi de -15, RR73, 73 — aucun ne
    porte de carré. Sans mémorisation, le carré disparaîtrait une seconde après
    son apparition et l'alerte n'aurait jamais le temps de se déclencher."""
    w._decodes.clear()
    w.status['dial_mhz'] = 14.074
    for m in ('CQ F4ABC JN18', 'F5XYZ F4ABC -15', 'F5XYZ F4ABC RR73', 'F5XYZ F4ABC 73'):
        w.record_decode({'message': m, 'mode': 'FT8', 'delta_hz': 1200}, my_call='F5XYZ')
        assert w._decodes['F4ABC']['grid'] == 'JN18', m


def test_un_carre_plus_precis_remplace_le_precedent():
    w._decodes.clear()
    w.status['dial_mhz'] = 14.074
    w.record_decode({'message': 'CQ F4ABC JN18', 'mode': 'FT8'}, my_call='F5XYZ')
    w.record_decode({'message': 'F5XYZ F4ABC JN19', 'mode': 'FT8'}, my_call='F5XYZ')
    assert w._decodes['F4ABC']['grid'] == 'JN19'


# ─── La règle de portée ──────────────────────────────────────────────────────

@pytest.fixture
def carnet(monkeypatch):
    """JN18 travaillé pendant le concours en cours, JN19 seulement en 2019."""
    monkeypatch.setattr(aw, '_read_archives', lambda: [])
    monkeypatch.setattr(aw, '_read_qso_archive', lambda: [])
    monkeypatch.setattr(aw, '_load_confirmations', lambda: {})
    monkeypatch.setattr(aw, 'qso_scope_id_safe',
                        lambda q: 'RPH|2026' if q.get('contest') == 'RPH' else '')
    aw.invalidate()
    return [
        {'call': 'A', 'band': '144', 'mode': 'SSB', 'date': '2026-01-01',
         'time': '1200', 'locator': 'JN18AA', 'contest': 'RPH'},
        {'call': 'B', 'band': '144', 'mode': 'SSB', 'date': '2019-06-01',
         'time': '1200', 'locator': 'JN19AA'},
    ]


ENTENDUS = [{'call': 'W1', 'grid': 'JN18', 'band': '144'},
            {'call': 'W2', 'grid': 'JN19', 'band': '144'},
            {'call': 'W3', 'grid': 'JN20', 'band': '144'}]


def test_en_concours_un_carre_de_2019_RESONNE(carnet):
    """C'est un multiplicateur à refaire ce week-end : le taire ferait perdre
    des points. C'est toute la différence avec un suivi « à vie » seul."""
    par_call = {c['call']: c for c in aw.suivi_carres(ENTENDUS, carnet, scope_id='RPH|2026')}
    assert par_call['W2']['interet'] == 1


def test_le_carre_jamais_travaille_A_VIE_passe_DEVANT(carnet):
    """Double intérêt : multiplicateur ET carré neuf pour les diplômes."""
    r = aw.suivi_carres(ENTENDUS, carnet, scope_id='RPH|2026')
    assert r[0]['call'] == 'W3' and r[0]['interet'] == 2
    assert r[0]['neuf_a_vie'] is True


def test_deja_fait_pendant_le_concours_reste_silencieux(carnet):
    par_call = {c['call']: c for c in aw.suivi_carres(ENTENDUS, carnet, scope_id='RPH|2026')}
    assert par_call['W1']['interet'] == 0 and par_call['W1']['libelle'] == ''


def test_hors_concours_seul_le_A_VIE_compte(carnet):
    """Sans concours actif, les deux référentiels se confondent : JN19,
    travaillé en 2019, ne doit plus rien déclencher."""
    par_call = {c['call']: c for c in aw.suivi_carres(ENTENDUS, carnet, scope_id='')}
    assert par_call['W3']['interet'] == 2
    assert par_call['W1']['interet'] == 0
    assert par_call['W2']['interet'] == 0, 'deja au carnet a vie'


def test_le_filtre_par_bande(carnet):
    entendus = ENTENDUS + [{'call': 'W4', 'grid': 'JN21', 'band': '50'}]
    r = aw.suivi_carres(entendus, carnet, scope_id='', bande='144')
    assert 'W4' not in {c['call'] for c in r}


def test_un_locator_par_defaut_ne_declenche_rien(carnet):
    """Même garde que la carte : JJ00AA n'est pas une position."""
    r = aw.suivi_carres([{'call': 'X', 'grid': 'JJ00AA', 'band': '144'}],
                        carnet, scope_id='')
    assert r == []


def test_une_entree_sans_carre_est_ignoree(carnet):
    """En FT8 la plupart des décodages n'ont pas de carré : ils ne doivent ni
    planter ni apparaître."""
    r = aw.suivi_carres([{'call': 'X', 'band': '144'},
                         {'call': 'Y', 'grid': '', 'band': '144'}],
                        carnet, scope_id='')
    assert r == []


def test_liste_vide(carnet):
    assert aw.suivi_carres([], carnet) == []
    assert aw.suivi_carres(None, carnet) == []


# ─── Le câblage de l'alerte ──────────────────────────────────────────────────

def _js():
    with open(os.path.join(CONCOURS, 'logx_logbook.js'), encoding='utf-8') as f:
        return f.read()


def test_deux_sons_distincts_selon_l_interet():
    """Les deux cas n'appellent pas la même réaction : le double intérêt doit
    s'entendre sans regarder l'écran."""
    src = _js()
    bloc = src[src.index('function appliquerSuiviCarres'):]
    bloc = bloc[:bloc.index('\n}')]
    assert bloc.count('playBeep(') == 2
    assert 'playBeep(1760' in bloc and 'playBeep(988' in bloc


def test_une_seule_alerte_par_carre_et_par_bande():
    """En FT8 la même station réapparaît toutes les 15 secondes : un son à
    chaque cycle rendrait le poste inutilisable."""
    src = _js()
    bloc = src[src.index('function appliquerSuiviCarres'):]
    bloc = bloc[:bloc.index('\n}')]
    assert '_carresAlertes' in bloc and 'continue' in bloc
    assert "c.grid + '|' + (c.band" in bloc


def test_le_conteneur_vise_existe_vraiment():
    """Piège déjà rencontré sur ce projet : un getElementById sur un id absent,
    gardé par un if, donne une panne parfaitement silencieuse."""
    with open(os.path.join(CONCOURS, 'logx_logbook.html'), encoding='utf-8') as f:
        html = f.read()
    for ident in ('carresBox', 'carresEntendus'):
        assert 'id="%s"' % ident in html, ident


def test_le_panneau_reste_masque_s_il_n_y_a_rien():
    src = _js()
    bloc = src[src.index('function appliquerSuiviCarres'):]
    bloc = bloc[:bloc.index('\n}')]
    assert "items.length ? '' : 'none'" in bloc
