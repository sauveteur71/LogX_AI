# -*- coding: utf-8 -*-
"""Régressions ciblées trouvées par une revue de code adversariale du
commit DXHeat (24/07/2026), sur build_ranked_spots() (logx_scoring.py) :

Problème 2 [HIGH] : fetch_dxheat() (logx_clusters.py) peuple spot['locator']
avec un vrai DXLocator structuré, mais build_ranked_spots() ne le lisait
jamais — il ne relisait QUE le commentaire libre via extract_dx_locator(),
qui renvoie '' quand ce commentaire est vide (cas réel de l'échantillon
DXHeat du commit : F4NBH/P, Comment=""). Le bénéfice annoncé par le commit
("un vrai champ locator structuré... plus fiable, utilisé en priorité")
était donc inopérant.

Problème 3 [MEDIUM] : le lot générique 'HF' (qui contient désormais aussi les
spots VHF/UHF de DXHeat, cf. tests/test_dxheat.py) n'est jamais dédupliqué
contre les caches dédiés '144 MHz'/'432 MHz'/'50 MHz' — une même station
spottée par les deux pipelines lors du même cycle de rafraîchissement
(logx_http.do_refresh lance _fetch_spots_hf_src ET _fetch_spots_vhf_src en
parallèle) apparaissait deux fois dans la liste classée finale d'un concours
mixte HF+VHF."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_storage as st
from logx_scoring import build_ranked_spots


def _base_cfg(contest=''):
    """Pas de concours actif : filter_spots_for_contest() ne restreint alors
    ni bande ni mode (même convention que tests/test_scoring.py)."""
    return {'contest': contest, 'callsign_contest': 'F6KQJ', 'locator': 'JN15XC'}


def _isolated(fn):
    """Isole shared_log (liste globale mutable de logx_storage, lue telle
    quelle par build_ranked_spots) — même pattern que tests/test_storage.py."""
    saved = list(st.shared_log)
    st.shared_log[:] = []
    try:
        return fn()
    finally:
        st.shared_log[:] = saved


# ─── Problème 2 : locator structuré DXHeat utilisé en priorité ──────────────

def test_locator_structure_dxheat_utilise_meme_avec_commentaire_vide():
    """Reproduction directe de l'échantillon du commit : F4NBH/P, locator
    DXHeat='JN16AA', commentaire vide. Avant correctif, extract_dx_locator()
    ne trouvait rien dans un commentaire vide -> locator='', lat/lon=None,
    dist_km=0 malgré un vrai locator connu."""
    spot = {
        'dx': 'F4NBH/P', 'locator': 'JN16AA', 'info': '', 'spotter': 'PD3RL',
        'freq': 7148.0, 'mode': 'LSB', 'time': '15:40', 'source': 'dxheat',
    }
    ranked, meta = _isolated(lambda: build_ranked_spots({}, {'HF': [spot]}, _base_cfg()))
    assert len(ranked) == 1
    r = ranked[0]
    assert r['locator'] == 'JN16AA'
    assert r['lat'] is not None and r['lon'] is not None
    assert r['dist_km'] > 0


def test_locator_structure_prime_sur_une_grille_erronee_dans_le_commentaire():
    """Le locator structuré (déjà celui du DX, fourni par l'API) doit primer
    même si le commentaire contient par ailleurs une grille (typiquement
    celle du SPOTTEUR, pas du DX — le piège qu'extract_dx_locator() gère par
    validation cty.dat pour les autres sources)."""
    spot = {
        'dx': 'DL3AMB', 'locator': 'JO51AA', 'info': 'CW tu Fred 559 GDX',
        'spotter': 'HZ1BH', 'freq': 14021.0, 'mode': 'CW', 'source': 'dxheat',
    }
    ranked, meta = _isolated(lambda: build_ranked_spots({}, {'HF': [spot]}, _base_cfg()))
    assert ranked[0]['locator'] == 'JO51AA'


def test_locator_structure_invalide_retombe_sur_le_commentaire():
    """Un champ 'locator' vide ou mal formé (source autre que DXHeat, ou
    DXLocator absent) ne doit pas empêcher le repli existant sur
    extract_dx_locator() (parsing + validation cty.dat du commentaire)."""
    spot = {
        'dx': 'F1ABC', 'locator': '', 'info': 'JN25XC bonne puissance',
        'spotter': 'F5XYZ', 'freq': 14020.0, 'mode': 'CW', 'source': 'cluster',
    }
    ranked, meta = _isolated(lambda: build_ranked_spots({}, {'HF': [spot]}, _base_cfg()))
    assert ranked[0]['locator'] == 'JN25XC'


# ─── Problème 3 : dédup croisée lot générique 'HF' vs cache dédié VHF ───────

def test_dedup_station_vhf_presente_a_la_fois_dans_hf_et_144():
    """Même station (EU6AX, échantillon réel DXHeat de tests/test_dxheat.py),
    même bande réelle (144 MHz, freq 144174 kHz) : une fois dans le lot
    générique 'HF' (DXHeat, reclassée via band_eff), une fois dans le cache
    dédié '144 MHz' (pipeline VHF/UHF existant). Sans dédup croisée, elle
    apparaît deux fois dans la liste classée finale."""
    dupe_dxheat = {
        'dx': 'EU6AX', 'locator': 'KO33SV', 'info': '', 'spotter': 'UA3ARC',
        'freq': 144174.0, 'mode': 'FT8', 'time': '15:19', 'source': 'dxheat',
    }
    dupe_vhf = {
        'dx': 'EU6AX', 'locator': 'KO33SV', 'info': '', 'spotter': 'UA3ARC',
        'freq': 144174.0, 'mode': 'FT8', 'time': '15:19', 'source': 'cluster',
    }
    ranked, meta = _isolated(lambda: build_ranked_spots(
        {}, {'HF': [dupe_dxheat], '144 MHz': [dupe_vhf]}, _base_cfg()))
    matches = [r for r in ranked if r['call'] == 'EU6AX' and r['band'] == '144']
    assert len(matches) == 1


def test_pas_de_dedup_entre_bandes_differentes():
    """Garde-fou : le dédup est par (indicatif, bande) — la MÊME station sur
    DEUX bandes différentes reste bien deux opportunités distinctes (RPH,
    IARU VHF/UHF comptent chaque bande séparément)."""
    spot_144 = {
        'dx': 'F1ABC', 'locator': 'JN25XC', 'info': '', 'spotter': 'F5XYZ',
        'freq': 144300.0, 'mode': 'SSB', 'source': 'cluster',
    }
    spot_432 = {
        'dx': 'F1ABC', 'locator': 'JN25XC', 'info': '', 'spotter': 'F5XYZ',
        'freq': 432300.0, 'mode': 'SSB', 'source': 'cluster',
    }
    ranked, meta = _isolated(lambda: build_ranked_spots(
        {}, {'144 MHz': [spot_144], '432 MHz': [spot_432]}, _base_cfg()))
    calls = [(r['call'], r['band']) for r in ranked]
    assert ('F1ABC', '144') in calls and ('F1ABC', '432') in calls
    assert len(ranked) == 2


def test_pas_de_qso_director():
    """Interdiction absolue répétée par l'utilisateur (voir CLAUDE.md)."""
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logx_scoring.py')
    with open(path, encoding='utf-8') as f:
        assert 'QSO Director' not in f.read()
