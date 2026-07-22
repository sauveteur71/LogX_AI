# -*- coding: utf-8 -*-
"""Moteur générique de base de références téléchargeable (parcs/refuges/iles/...).

Mutualise le pattern déjà éprouvé et testé dans logx_sota.py (chargement en
tâche de fond — jamais le thread HTTP —, cache disque avec péremption,
recherche insensible aux accents, "nearby" par haversine) pour les nouveaux
programmes POTA/WWFF/IOTA — sans toucher à logx_sota.py, déjà en production.
Chaque programme fournit juste : l'URL source, un nom de fichier de cache, et
une fonction de parsing (contenu brut -> liste de dicts avec au moins les
clés 'code' et 'name' ; 'lat'/'lon' en float activent nearby()).

WCA (Castles) n'utilise PAS ce moteur : sa source est un classeur .ods
(binaire, à dézipper) sans coordonnées GPS — cf. logx_wca.py, qui reprend le
même schéma (thread de fond, cache disque, statut) mais avec un parsing propre
à son format.
"""
import os
import tempfile
import threading
import time
import unicodedata


def strip_accents(s):
    return ''.join(c for c in unicodedata.normalize('NFKD', s or '') if not unicodedata.combining(c))


def age_days(path):
    if not os.path.exists(path):
        return None
    return (time.time() - os.path.getmtime(path)) / 86400


def atomic_write(path, content):
    target_dir = os.path.dirname(os.path.abspath(path)) or '.'
    fd, tmp = tempfile.mkstemp(prefix=os.path.basename(path) + '.', suffix='.tmp', dir=target_dir)
    with os.fdopen(fd, 'w', encoding='utf-8', newline='') as f:
        f.write(content)
    os.replace(tmp, path)


class ActivationDatabase:
    """Base de références générique : téléchargement + cache disque + recherche.

    parse_fn(content:str) -> list[dict] avec au minimum la clé 'code' (str,
    identifiant unique — la référence telle que loggée, ex. 'F-0123'). 'lat'/
    'lon' (float ou None) activent nearby(). Les autres clés (name, region,
    points...) varient par programme et sont renvoyées telles quelles.
    valid_fn(content:str) -> bool : garde-fou avant d'écraser le cache disque
    (taille minimale, marqueurs attendus) — jamais un téléchargement tronqué
    ou une page d'erreur à la place du vrai export.
    """

    def __init__(self, label, source_url, cache_file, parse_fn, valid_fn,
                 max_age_days=30, fetch_timeout=60):
        self.label = label
        self.source_url = source_url
        self.cache_file = cache_file
        self.parse_fn = parse_fn
        self.valid_fn = valid_fn
        self.max_age_days = max_age_days
        self.fetch_timeout = fetch_timeout
        self._state = {'by_code': {}, 'list': [], 'loading': False, 'loaded': False, 'error': None}
        self._lock = threading.Lock()

    def _load_from_disk_or_network(self):
        try:
            age = age_days(self.cache_file)
            content = None
            if age is not None and age < self.max_age_days:
                try:
                    with open(self.cache_file, encoding='utf-8', errors='replace') as f:
                        content = f.read()
                except OSError:
                    content = None
                if content and not self.valid_fn(content):
                    content = None
            if not content:
                from logx_utils import fetch_url
                downloaded = fetch_url(self.source_url, timeout=self.fetch_timeout)
                if downloaded and self.valid_fn(downloaded):
                    content = downloaded
                    try:
                        atomic_write(self.cache_file, content)
                    except OSError as e:
                        print(f"[{self.label}] Ecriture cache impossible (non bloquant): {e}")
                elif not content:
                    with self._lock:
                        self._state['loading'] = False
                        self._state['error'] = 'Base indisponible (réseau/cache)'
                    return

            items = self.parse_fn(content)
            by_code = {it['code']: it for it in items if it.get('code')}
            with self._lock:
                self._state['by_code'] = by_code
                self._state['list'] = items
                self._state['loaded'] = True
                self._state['loading'] = False
                self._state['error'] = None
            print(f"[{self.label}] {len(items)} entrées chargées")
        except Exception as e:
            with self._lock:
                self._state['loading'] = False
                self._state['error'] = str(e)
            print(f"[{self.label}] Erreur chargement: {e}")

    def ensure_loading_started(self):
        with self._lock:
            if self._state['loaded'] or self._state['loading']:
                return
            self._state['loading'] = True
        threading.Thread(target=self._load_from_disk_or_network, daemon=True).start()

    def status(self):
        self.ensure_loading_started()
        with self._lock:
            return {'ready': self._state['loaded'], 'loading': self._state['loading'],
                    'count': len(self._state['list']), 'error': self._state['error']}

    def get(self, code):
        self.ensure_loading_started()
        code = (code or '').strip().upper()
        with self._lock:
            return self._state['by_code'].get(code)

    def search(self, query, limit=25, name_keys=('name', 'region')):
        self.ensure_loading_started()
        query = (query or '').strip()
        if len(query) < 2:
            return []
        q_upper = query.upper()
        q_folded = strip_accents(query).lower()
        with self._lock:
            items = self._state['list']
            if not items:
                return []
            by_code_prefix = [it for it in items if it['code'].startswith(q_upper)]
            if len(by_code_prefix) >= limit:
                return by_code_prefix[:limit]

            def matches_name(it):
                for k in name_keys:
                    if q_folded in strip_accents(str(it.get(k, ''))).lower():
                        return True
                return False

            by_name = [it for it in items if matches_name(it)]
            seen = {it['code'] for it in by_code_prefix}
            merged = by_code_prefix + [it for it in by_name if it['code'] not in seen]
            return merged[:limit]

    def nearby(self, lat, lon, max_km=100, limit=30):
        self.ensure_loading_started()
        try:
            lat, lon = float(lat), float(lon)
        except (TypeError, ValueError):
            return []
        from logx_utils import haversine, bearing, cardinal
        with self._lock:
            items = list(self._state['list'])
        out = []
        for it in items:
            if it.get('lat') is None or it.get('lon') is None:
                continue
            dist = haversine(lat, lon, it['lat'], it['lon'])
            if dist > max_km:
                continue
            brg = bearing(lat, lon, it['lat'], it['lon'])
            out.append({**it, 'dist_km': dist, 'bearing': brg, 'cardinal': cardinal(brg)})
        out.sort(key=lambda it: it['dist_km'])
        return out[:limit]
