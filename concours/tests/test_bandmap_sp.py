# -*- coding: utf-8 -*-
"""Band map Search & Pounce : mémoriser ce que J'ENTENDS, pas seulement le cluster.

Le band map ne lisait que /data/spots_ranked. Or le S&P fait facilement la
moitié des QSO d'un mono-opérateur, et son geste de base est : je balaie la
bande, j'entends une station, je la note, je la rappellerai dans 20 minutes.
Une station entendue mais spottée par personne était simplement perdue.

N1MM, Win-Test et DXLog remplissent leur band map avec les DEUX sources.

La partie JavaScript (fusion des deux sources, saut de spot en spot) est
EXÉCUTÉE dans un moteur V8 à partir du fichier livré, pas recopiée.
"""
import json
import os
import re
import sys
import time

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CONCOURS not in sys.path:
    sys.path.insert(0, CONCOURS)

import logx_bandmap as bm  # noqa: E402

# EV-7 28e incrément : bandmapSaut()/bandmapNoter() ont été extraites vers
# ce fichier -- doit être lu ici, plus dans logx_logbook.js.
JS = os.path.join(CONCOURS, 'logx_bandmap_sp.js')


@pytest.fixture(autouse=True)
def dossier_isole(tmp_path, monkeypatch):
    """Chaque test a son propre fichier : jamais d'écriture dans le dépôt, et
    l'état module-level repart à zéro."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(bm, '_spots', [])
    monkeypatch.setattr(bm, '_charge', False)
    return tmp_path


# ─── Mémoire locale ──────────────────────────────────────────────────────────

def test_une_station_entendue_est_memorisee():
    assert bm.ajouter('F6BC', 14025.3, '14', 'CW')['ok']
    (s,) = bm.spots()
    assert s['call'] == 'F6BC' and s['freq_khz'] == 14025.3
    assert s['source'] == 'local'


def test_renoter_la_meme_station_rafraichit_au_lieu_d_empiler():
    """En balayant, on repasse plusieurs fois sur la même station : une pile
    de doublons rendrait le band map illisible."""
    t0 = time.time()
    bm.ajouter('F6BC', 14025.3, maintenant=t0)
    res = bm.ajouter('F6BC', 14025.4, maintenant=t0 + 60)
    assert res['rafraichi'] is True
    assert len(bm.spots()) == 1


def test_l_identite_est_l_indicatif_ET_le_kHz():
    """Au kHz près : on ne retrouve jamais une station au Hz près en la
    rappelant. Mais la même station sur une AUTRE fréquence est bien une autre
    ligne — elle peut être entendue sur deux bandes."""
    bm.ajouter('F6BC', 14025.3)
    bm.ajouter('F6BC', 14025.4)     # même kHz -> une seule ligne
    assert len(bm.spots()) == 1
    bm.ajouter('F6BC', 21025.0)     # autre bande -> deuxième ligne
    assert len(bm.spots()) == 2


def test_l_indicatif_est_normalise_en_majuscules():
    bm.ajouter('f6bc ', 14025)
    assert bm.spots()[0]['call'] == 'F6BC'


@pytest.mark.parametrize('call,freq,motif', [
    ('', 14000, 'indicatif'),
    ('   ', 14000, 'indicatif'),
    ('F6BC', 0, 'manquante'),
    ('F6BC', None, 'manquante'),
    ('F6BC', 'abc', 'illisible'),
])
def test_entrees_invalides_refusees(call, freq, motif):
    res = bm.ajouter(call, freq)
    assert not res['ok'] and motif in res['error'].lower()
    assert bm.spots() == []


def test_les_spots_sont_tries_par_frequence_decroissante():
    """Même ordre que le band map à l'écran : le client n'a rien à retrier,
    et la navigation clavier suit ce qui est affiché."""
    for f in (14032.0, 14005.0, 14025.0):
        bm.ajouter('X%d' % f, f)
    assert [s['freq_khz'] for s in bm.spots()] == [14032.0, 14025.0, 14005.0]


# ─── Vieillissement ──────────────────────────────────────────────────────────

def test_un_spot_expire_disparait():
    """En concours, une station entendue il y a une heure a presque sûrement
    bougé : la garder afficherait une fréquence vide, ce qui est pire que de
    ne rien afficher."""
    bm.ajouter('VIEUX', 14099, maintenant=time.time() - bm.DUREE_VIE_S - 10)
    bm.ajouter('FRAIS', 14005)
    assert [s['call'] for s in bm.spots()] == ['FRAIS']


def test_un_spot_juste_sous_la_limite_reste():
    bm.ajouter('LIMITE', 14005, maintenant=time.time() - bm.DUREE_VIE_S + 60)
    assert [s['call'] for s in bm.spots()] == ['LIMITE']


def test_l_age_est_rendu_au_client():
    bm.ajouter('F6BC', 14005, maintenant=time.time() - 300)
    assert 290 <= bm.spots()[0]['age_s'] <= 310


def test_renoter_repousse_l_expiration():
    ancien = time.time() - bm.DUREE_VIE_S + 30
    bm.ajouter('F6BC', 14005, maintenant=ancien)
    bm.ajouter('F6BC', 14005)          # renoté maintenant
    assert bm.spots()[0]['age_s'] < 5


def test_plafond_du_nombre_de_spots():
    """Garde-fou : un band map n'est pas un journal. Sur une expédition de
    15 jours, un remplissage accidentel ne doit pas grossir sans fin."""
    base = time.time()
    for i in range(bm.MAX_SPOTS + 40):
        bm.ajouter('C%04d' % i, 14000 + i * 0.1, maintenant=base + i)
    assert len(bm.spots()) == bm.MAX_SPOTS


def test_le_plafond_garde_les_plus_recents():
    base = time.time()
    for i in range(bm.MAX_SPOTS + 5):
        bm.ajouter('C%04d' % i, 14000 + i * 0.1, maintenant=base + i)
    restants = {s['call'] for s in bm.spots()}
    assert 'C0000' not in restants
    assert 'C%04d' % (bm.MAX_SPOTS + 4) in restants


# ─── Suppression / persistance ───────────────────────────────────────────────

def test_suppression():
    bm.ajouter('F6BC', 14025.3)
    bm.ajouter('DL1XX', 14032)
    assert bm.supprimer('F6BC', 14025.3)['supprimes'] == 1
    assert [s['call'] for s in bm.spots()] == ['DL1XX']


def test_suppression_au_kHz_pres():
    bm.ajouter('F6BC', 14025.3)
    assert bm.supprimer('F6BC', 14025.4)['supprimes'] == 1


def test_vider():
    bm.ajouter('F6BC', 14025)
    assert bm.vider()['ok']
    assert bm.spots() == []


def test_le_band_map_survit_a_un_redemarrage(dossier_isole, monkeypatch):
    """Un rechargement de page ou un redémarrage serveur en plein concours ne
    doit pas effacer ce que l'opérateur a noté."""
    bm.ajouter('F6BC', 14025.3, '14', 'CW')
    monkeypatch.setattr(bm, '_spots', [])
    monkeypatch.setattr(bm, '_charge', False)
    assert [s['call'] for s in bm.spots()] == ['F6BC']


def test_un_fichier_illisible_ne_fait_pas_planter(dossier_isole, monkeypatch):
    (dossier_isole / bm.FICHIER).write_text('{ ceci nest pas du json', encoding='utf-8')
    monkeypatch.setattr(bm, '_spots', [])
    monkeypatch.setattr(bm, '_charge', False)
    assert bm.spots() == []
    assert bm.ajouter('F6BC', 14025)['ok']


def test_aucun_fichier_temporaire_ne_reste(dossier_isole):
    bm.ajouter('F6BC', 14025)
    assert [p.name for p in dossier_isole.glob('*.tmp')] == []


# ─── Côté navigateur : fusion et navigation ──────────────────────────────────

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


def _moteur_saut(spots, freq_khz):
    ctx = py_mini_racer.MiniRacer()
    ctx.eval("""
        var journal = [];
        var _bmSpots = %s;
        var rigState = %s;
        var isSetupDone = true;
        function notify(m){ journal.push(['notify', m]); }
        function trF(s){ return s; }
        function bandmapClick(call, f){ journal.push(['qsy', call, f]); }
        %s
    """ % (json.dumps(spots),
           json.dumps({'enabled': True, 'freq_khz': freq_khz} if freq_khz else {}),
           _fonction_js('bandmapSaut')))
    return ctx


SPOTS_JS = [{'call': 'HAUT', 'freq': 14.100}, {'call': 'MILIEU', 'freq': 14.050},
            {'call': 'BAS', 'freq': 14.010}]


def test_saut_vers_le_bas_prend_le_spot_juste_en_dessous():
    ctx = _moteur_saut(SPOTS_JS, 14050)
    ctx.eval('bandmapSaut(1)')
    assert json.loads(ctx.eval('JSON.stringify(journal)')) == [['qsy', 'BAS', 14.010]]


def test_saut_vers_le_haut_prend_le_spot_juste_au_dessus():
    """La liste est triée en fréquence DÉCROISSANTE : « vers le haut » est le
    dernier élément encore au-dessus, pas le premier de la liste."""
    ctx = _moteur_saut(SPOTS_JS, 14050)
    ctx.eval('bandmapSaut(-1)')
    assert json.loads(ctx.eval('JSON.stringify(journal)')) == [['qsy', 'HAUT', 14.100]]


def test_saut_en_bout_de_bande_previent_sans_bouger_la_radio():
    ctx = _moteur_saut(SPOTS_JS, 14010)
    ctx.eval('bandmapSaut(1)')
    j = json.loads(ctx.eval('JSON.stringify(journal)'))
    assert j and j[0][0] == 'notify' and 'dernier' in j[0][1]


def test_saut_sans_radio_part_du_premier_spot():
    ctx = _moteur_saut(SPOTS_JS, None)
    ctx.eval('bandmapSaut(1)')
    assert json.loads(ctx.eval('JSON.stringify(journal)')) == [['qsy', 'HAUT', 14.100]]


def test_saut_sur_band_map_vide_ne_plante_pas():
    ctx = _moteur_saut([], 14050)
    ctx.eval('bandmapSaut(1)')
    j = json.loads(ctx.eval('JSON.stringify(journal)'))
    assert j and j[0][0] == 'notify'


def test_le_saut_ne_reste_pas_coince_sur_la_frequence_courante():
    """Un spot pile sur la fréquence de la radio ne doit pas être choisi comme
    « suivant » : on ne bougerait pas."""
    ctx = _moteur_saut([{'call': 'ICI', 'freq': 14.050}, {'call': 'PLUSBAS', 'freq': 14.040}], 14050)
    ctx.eval('bandmapSaut(1)')
    assert json.loads(ctx.eval('JSON.stringify(journal)')) == [['qsy', 'PLUSBAS', 14.040]]


def test_les_raccourcis_sont_documentes_dans_l_aide():
    with open(os.path.join(CONCOURS, 'logx_logbook.html'), encoding='utf-8') as f:
        html = f.read()
    assert 'Ctrl+↑' in html and 'Ctrl+Entrée' in html
