# -*- coding: utf-8 -*-
"""WWBOTA (World Wide Bunkers on the Air) — base des bunkers.

Source officielle publique, sans clé : l'export CSV maître de tous les schémas
nationaux (FBOTA, OKBOTA, UKBOTA…), https://api.wwbota.org/bunkers/?format=CSV.
En-têtes réels (vérifiés en direct) : Scheme,DXCC,Reference,Name,Type,Lat,Long,
Locator — ~31 400 bunkers, ~2,5 Mo. Sert à VALIDER une référence saisie et à la
RECHERCHER par code ou par nom, et à situer un bunker (lat/lon -> nearby), comme
SOTA/POTA/WWFF.

Droits : la base WWBOTA est protégée. Comme POTA/SOTA/WWFF, on ne redistribue
RIEN dans le dépôt : téléchargement par l'instance de l'OM + cache LOCAL
uniquement (fichier `wwbota_bunkers.csv` hors dépôt). Rafraîchissement 15 j —
cadence « vérification des listes XOTA tous les 15 jours » (F4GLD).
"""
import csv

from logx_activation_db import ActivationDatabase

WWBOTA_CSV_URL = 'https://api.wwbota.org/bunkers/?format=CSV'
BUNKERS_FILE = 'wwbota_bunkers.csv'
_ENTETE = 'Scheme,DXCC,Reference,Name,Type,Lat,Long,Locator'


def _looks_valid_bunkers_csv(content):
    """Garde-fou avant d'écraser le cache : jamais un fichier tronqué ou une page
    d'erreur à la place du vrai export (~2,5 Mo, ~31 000 lignes)."""
    if not content or len(content) < 300_000:
        return False
    return _ENTETE in content and content.count(',') > 100_000


def _parse_bunkers_csv(content):
    """CSV -> liste de dicts. 'code' = référence loggée (ex. 'B/F-0001')."""
    out = []
    for row in csv.DictReader(content.splitlines()):
        code = (row.get('Reference') or '').strip().upper()
        if not code:
            continue
        try:
            lat = float(row.get('Lat') or '')
            lon = float(row.get('Long') or '')
        except ValueError:
            lat = lon = None
        out.append({
            'code': code,
            'name': (row.get('Name') or '').strip(),
            'region': (row.get('Scheme') or '').strip(),   # schéma national (FBOTA…)
            'type': (row.get('Type') or '').strip(),
            'locator': (row.get('Locator') or '').strip(),
            'dxcc': (row.get('DXCC') or '').strip(),
            'lat': lat,
            'lon': lon,
        })
    return out


directory_db = ActivationDatabase(
    label='WWBOTA',
    source_url=WWBOTA_CSV_URL,
    cache_file=BUNKERS_FILE,
    parse_fn=_parse_bunkers_csv,
    valid_fn=_looks_valid_bunkers_csv,
    max_age_days=15,
    fetch_timeout=90,
)


def search(query, limit=25):
    return directory_db.search(query, limit=limit)


def get(code):
    return directory_db.get(code)


def nearby(lat, lon, max_km=100, limit=30):
    return directory_db.nearby(lat, lon, max_km=max_km, limit=limit)


def status():
    return directory_db.status()
