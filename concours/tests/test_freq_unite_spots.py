# -*- coding: utf-8 -*-
"""Unité des fréquences de spots : le champ 'freq' n'en avait aucune de fixe.

CE QUI A ÉTÉ MESURÉ, le 30/07/2026, en appelant les lecteurs pour de vrai :

    DXSummit HF    1825.8 → 28485      kHz
    DXHeat         7089   → 144360     kHz
    DXSummit VHF   50.313 → 144.480    MHz   <— l'intrus

Les sources ne s'accordent pas, et /data/spots_ranked recopiait la valeur
telle quelle. AUCUN écran ne pouvait donc être juste : logx_chasse.html
supposait des kHz (juste en HF, faux en VHF), tandis que le band map, le
bandscope, la chute d'eau, le scope détaché, la réglette et les fenêtres par
bande supposaient des MHz. En pratique le band map n'affichait QUE les spots
DXSummit VHF — les seuls du bon côté du hasard — et tout le reste du cluster
était invisible sans le moindre message.

Pire, silencieusement : bandmapClick(call, mhz) fait Math.round(mhz*1000)
avant de commander le QSY. Un spot HF affiché aurait envoyé la radio à
21 263 000 kHz. Les deux défauts se masquaient l'un l'autre — la liste vide
empêchait le clic. C'est le genre de paire qui survit des mois.

LA CORRECTION : une seule unité, le kHz, imposée au serveur par freq_en_khz(),
qui tranche PAR LA BANDE et non par la magnitude. Les clients convertissent
en un seul point chacun.
"""
import io
import os
import sys

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CONCOURS not in sys.path:
    sys.path.insert(0, CONCOURS)

from logx_clusters import freq_en_khz   # noqa: E402


def _lire(nom):
    return io.open(os.path.join(CONCOURS, nom), encoding='utf-8').read()


# ─── La conversion elle-même ─────────────────────────────────────────────────

@pytest.mark.parametrize('valeur,bande,attendu', [
    # Valeurs RÉELLEMENT observées sur chaque source, avec leur bande.
    (1825.8, '1.8', 1825.8),        # DXSummit HF — deja des kHz
    (14074.0, '14', 14074.0),       # DXSummit HF
    (28485.0, '28', 28485.0),       # DXSummit HF
    (7089.0, '7', 7089.0),          # DXHeat
    (144360.0, '144', 144360.0),    # DXHeat, VHF mais en kHz
    (50.313, '50', 50313.0),        # DXSummit VHF — des MHz, a convertir
    (144.480, '144', 144480.0),     # DXSummit VHF
    (10136.0, '10.1', 10136.0),     # bande WARC, cle non entiere
    (10.136, '10.1', 10136.0),
])
def test_chaque_source_ramenee_en_kHz(valeur, bande, attendu):
    assert freq_en_khz(valeur, bande) == pytest.approx(attendu)


def test_POURQUOI_LA_BANDE_ET_PAS_LA_MAGNITUDE():
    """Le cas qui condamne le seuil de magnitude, et la raison d'être du
    paramètre 'band'.

    En micro-ondes, 10368 est un nombre parfaitement plausible EN MHz : c'est
    la bande 3 cm. Une règle « au-dessus de 1000, ce sont des kHz » le
    laisserait tel quel et placerait la station à 10,368 MHz — sur 30 mètres.
    La clé de bande lève l'ambiguïté sans deviner.
    """
    assert freq_en_khz(10368.0, '10368') == 10368000.0     # 3 cm, des MHz
    assert freq_en_khz(10136.0, '10.1') == 10136.0         # 30 m, des kHz
    # Et sans bande, on n'a QUE la magnitude — d'où l'erreur assumée :
    assert freq_en_khz(10368.0) == 10368.0


@pytest.mark.parametrize('mauvais', [None, '', 0, '0', 'abc', [], {}])
def test_une_frequence_illisible_rend_zero_sans_lever(mauvais):
    assert freq_en_khz(mauvais, '14') == 0.0


def test_une_bande_illisible_retombe_sur_la_magnitude():
    assert freq_en_khz(14074.0, 'HF') == 14074.0
    assert freq_en_khz(14.074, '') == 14074.0


def test_la_conversion_est_idempotente():
    """Appliquée deux fois, elle ne doit pas multiplier deux fois — sinon un
    refactor qui la place à deux endroits enverrait la radio dans le décor."""
    une = freq_en_khz(50.313, '50')
    assert freq_en_khz(une, '50') == une


# ─── Le point de conversion unique, côté serveur ─────────────────────────────

def test_spots_ranked_normalise_la_frequence():
    src = _lire('logx_http.py')
    bloc = src[src.index("if path == '/data/spots_ranked':"):]
    bloc = bloc[:bloc.index("if path == '/wsjtx/state':")]
    assert "freq_en_khz(s.get('freq', ''), s.get('band', ''))" in bloc


def test_freq_en_khz_est_bien_importee():
    """Piège déjà rencontré sur ce projet : logx_http fait un `from ... import`
    en tête, et un appel qualifié `clusters.freq_en_khz` y lèverait NameError
    à l'exécution seulement — jamais à l'import, donc jamais en test."""
    src = _lire('logx_http.py')
    assert 'freq_en_khz)' in src.split('from logx_clusters import')[1][:600]


# ─── Chaque client convertit, en UN seul endroit ─────────────────────────────

def test_band_map_convertit_a_l_entree():
    """Le band map raisonne en MHz partout (_BM_RANGE, bandscope, chute d'eau,
    bandmapClick) : la conversion doit être unique et à l'entrée, sinon elle
    finit par manquer à un endroit."""
    src = _lire('logx_logbook.js')
    assert 'const clusterMhz = (d.spots || []).map(' in src
    assert '/ 1000' in src[src.index('const clusterMhz'):][:200]
    # Apres la conversion, plus AUCUNE lecture directe de d.spots : c'est ce
    # qui garantit que la conversion est unique et qu'aucun chemin ne la saute.
    apres = src[src.index('const clusterCles'):]
    apres = apres[:apres.index('_bmSpots = spots')]
    assert 'd.spots' not in apres


def test_le_scope_detache_convertit_aussi():
    src = _lire('logx_scope.html')
    assert '(parseFloat(s.freq)||0)/1000' in src


def test_les_fenetres_par_bande_affichent_des_MHz():
    src = _lire('logx_bande.html')
    assert 'const mhz = (parseFloat(s.freq) || 0) / 1000;' in src
    assert 'const smhz = (parseFloat(s.freq) || 0) / 1000;' in src


def test_la_carte_ne_libelle_plus_des_kHz_en_MHz():
    src = _lire('logx_carte.html')
    assert '`${s.freq} MHz`' not in src


def test_la_page_chasse_reste_en_kHz_et_devient_juste_partout():
    """Elle était la SEULE à supposer des kHz — donc juste en HF et fausse en
    VHF. En imposant le kHz partout, elle devient juste sans être touchée. Ce
    test verrouille le fait qu'on ne l'a pas « corrigée » par erreur."""
    src = _lire('logx_chasse.html')
    assert '(s.freq/1000).toFixed(3)' in src


# ─── Le QSY depuis une fenêtre par bande ─────────────────────────────────────

def test_LE_CLIC_QSY_ENVOIE_UN_CHAMP_QUE_LE_SERVEUR_LIT():
    """/rig/qsy ne lit QUE freq_hz ou freq_khz. La version précédente envoyait
    {freq: "..."}, jamais relu : le clic sur une épingle de la réglette ne
    faisait rien, radio allumée ou non, et sans message d'erreur."""
    src = _lire('logx_bande.html')
    bloc = src[src.index('async function qsy('):]
    bloc = bloc[:bloc.index('\n  }')]
    assert 'freq_khz' in bloc
    assert 'JSON.stringify({freq:' not in bloc


def test_le_serveur_ne_lit_QUE_freq_hz_ou_freq_khz():
    """Verrouille la RAISON du test précédent. Si /rig/qsy acceptait un jour un
    champ 'freq', le test ci-dessus deviendrait inutile — mais tant que ce
    n'est pas le cas, envoyer autre chose est une panne silencieuse."""
    src = _lire('logx_http.py')
    bloc = src[src.index("if self.path == '/rig/qsy':"):]
    bloc = bloc[:bloc.index('Fréquence manquante')]
    assert "payload.get('freq_hz')" in bloc and "payload.get('freq_khz')" in bloc
    assert "payload.get('freq')" not in bloc
