# -*- coding: utf-8 -*-
"""Le modèle temporel du dépôt : UTC NAÏF, partout, et un seul point d'entrée.

`datetime.datetime.utcnow()` est déprécié depuis Python 3.12 et programmé pour
suppression. Le remplacer naïvement par `datetime.now(datetime.UTC)` aurait
changé la SÉMANTIQUE — naïf devient aware, et les deux ne se soustraient pas :
ephem, les dates ADIF/Cabrillo du log, les caches déjà écrits sur le disque des
utilisateurs et l'API ionosondes KC2G rendent tous des datetime naïfs.

Ces tests verrouillent les deux moitiés du contrat : `utcnow()` rend bien du
naïf, et plus aucun appel déprécié ne subsiste dans le dépôt.
"""
import ast
import datetime
import os
import pathlib
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_sat_passes as sp                                        # noqa: E402
from logx_utils import utcnow, as_naive_utc                         # noqa: E402

RACINE = pathlib.Path(__file__).resolve().parent.parent


# ─── utcnow() ────────────────────────────────────────────────────────────────

def test_utcnow_rend_un_datetime_naif():
    """LE point du chantier. Un aware ici casserait toutes les soustractions
    contre les datetime naïfs du log, d'ephem et des caches."""
    assert utcnow().tzinfo is None


def test_utcnow_donne_bien_l_heure_utc_et_non_l_heure_locale():
    """Le poste de développement est en UTC+1/+2 : un `datetime.now()` sans
    fuseau passerait le test précédent tout en décalant l'heure d'une heure ou
    deux — assez pour horodater des QSO de concours à côté."""
    ecart = abs((utcnow() - datetime.datetime.now(datetime.UTC).replace(tzinfo=None))
                .total_seconds())
    assert ecart < 5


# ─── as_naive_utc() ──────────────────────────────────────────────────────────

def test_as_naive_utc_convertit_vraiment_au_lieu_de_depouiller():
    """Un aware à +02:00 doit RECULER de deux heures, pas simplement perdre son
    fuseau. Dépouiller sans convertir garderait 14:00 pour un instant qui est
    12:00 UTC — une erreur de deux heures, silencieuse."""
    plus_deux = datetime.timezone(datetime.timedelta(hours=2))
    aware = datetime.datetime(2026, 8, 1, 14, 0, tzinfo=plus_deux)
    assert as_naive_utc(aware) == datetime.datetime(2026, 8, 1, 12, 0)
    assert as_naive_utc(aware).tzinfo is None


def test_as_naive_utc_laisse_passer_le_naif_et_le_none():
    naif = datetime.datetime(2026, 8, 1, 12, 0)
    assert as_naive_utc(naif) is naif
    assert as_naive_utc(None) is None


# ─── Frontière de lecture : le cache TLE déjà présent sur les disques ────────

def test_age_tle_lit_le_cache_naif_existant():
    """Non-régression : les caches DÉJÀ écrits chez les utilisateurs portent un
    horodatage sans fuseau. Ils doivent rester lisibles après la migration."""
    maintenant = datetime.datetime(2026, 8, 1, 12, 0)
    cache = {'recupere': datetime.datetime(2026, 7, 30, 12, 0).isoformat(),
             'tle': {'ISS': ['1 ...', '2 ...']}}
    assert sp.age_tle(cache, maintenant)['jours'] == 2.0


def test_age_tle_survit_a_un_horodatage_avec_fuseau():
    """Durcissement : un cache recopié d'une autre installation, ou écrit par
    une version ultérieure, peut porter « +00:00 ». La soustraction se fait
    HORS du try/except du parsing — sans normalisation, le TypeError remontait
    à l'appelant et emportait l'écran satellite."""
    cache = {'recupere': datetime.datetime(2026, 7, 30, 12, 0,
                                           tzinfo=datetime.UTC).isoformat(),
             'tle': {'ISS': ['1 ...', '2 ...']}}
    assert sp.age_tle(cache, datetime.datetime(2026, 8, 1, 12, 0))['jours'] == 2.0


def test_age_tle_horodatage_illisible_rend_none():
    assert sp.age_tle({'recupere': 'pas une date', 'tle': {'ISS': []}}) is None


# ─── Garde-fou : plus aucun appel déprécié dans le dépôt ────────────────────

def test_plus_aucun_appel_a_datetime_utcnow_dans_le_depot():
    """Verrouille la migration.

    L'analyse passe par l'AST et non par une recherche textuelle : elle ignore
    donc les docstrings et les commentaires qui CITENT l'ancien appel (celui de
    logx_utils.utcnow explique précisément pourquoi il a disparu), tout en
    attrapant aussi bien `datetime.datetime.utcnow()` que l'alias
    `_dt.datetime.utcnow()` utilisé dans plusieurs modules.
    """
    fautifs = []
    fichiers = sorted(RACINE.glob('logx_*.py')) + sorted((RACINE / 'tests').glob('*.py'))
    for chemin in fichiers:
        arbre = ast.parse(chemin.read_text(encoding='utf-8'), str(chemin))
        for noeud in ast.walk(arbre):
            if (isinstance(noeud, ast.Call)
                    and isinstance(noeud.func, ast.Attribute)
                    and noeud.func.attr == 'utcnow'):
                fautifs.append(f'{chemin.name}:{noeud.lineno}')
    assert not fautifs, (
        "Appel(s) déprécié(s) réintroduit(s) — utiliser logx_utils.utcnow() : "
        + ', '.join(fautifs))
