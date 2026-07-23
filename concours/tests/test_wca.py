# -*- coding: utf-8 -*-
"""Géocodage (sens direct) de la référence WCA activée — logx_wca.

WCALIST.ods ne fournit aucune coordonnée : geocode_castle()/get_castle_geocoded()
sont les seules briques réseau du module, et ne doivent JAMAIS toucher au vrai
Nominatim ni au vrai wca_geocode_cache.json pendant les tests (fetch_url mocké,
cache redirigé vers un fichier temporaire, base de châteaux entièrement seedée
en mémoire — jamais de déclenchement du téléchargement réel de WCALIST.ods)."""
import json
import os
import sys
import threading
import time as time_mod

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_wca as wca


def _seed_castle(code='DL-00001', name='Burg Test', location='Test Region', prefix='DL'):
    """Peuple _state directement (jamais ensure_loading_started : pas de vrai
    téléchargement de WCALIST.ods pendant les tests)."""
    entry = {'code': code, 'castle_no': '1', 'prefix': prefix,
             'name': name, 'location': location}
    wca._state['by_code'] = {code: entry}
    wca._state['list'] = [entry]
    wca._state['loaded'] = True
    wca._state['loading'] = False
    wca._state['error'] = None
    return entry


def _reset_geocode_state(monkeypatch, tmp_path):
    monkeypatch.setattr(wca, '_geocode_cache', None)
    monkeypatch.setattr(wca, '_last_nominatim_call', [0.0])
    monkeypatch.setattr(wca, 'GEOCODE_CACHE_FILE', str(tmp_path / 'wca_geocode_cache.json'))


def _fake_fetch_ok(lat='50.123456', lon='10.654321'):
    calls = {'n': 0, 'urls': []}
    def fake_fetch(url, timeout=10):
        calls['n'] += 1
        calls['urls'].append(url)
        return json.dumps([{'lat': lat, 'lon': lon, 'display_name': 'x'}])
    return fake_fetch, calls


# ─── geocode_castle : succès + cache ─────────────────────────────────────────

def test_geocode_castle_interroge_nominatim_et_met_en_cache(monkeypatch, tmp_path):
    _seed_castle()
    _reset_geocode_state(monkeypatch, tmp_path)
    fake_fetch, calls = _fake_fetch_ok()
    import logx_utils
    monkeypatch.setattr(logx_utils, 'fetch_url', fake_fetch)

    r = wca.geocode_castle('DL-00001')
    assert r == {'lat': 50.123456, 'lon': 10.654321}
    assert calls['n'] == 1
    # La requête porte bien le nom + la localisation du château (pays via cty.dat,
    # non ré-affirmé ici pour ne pas dépendre du libellé exact de cty.dat).
    assert 'Burg+Test' in calls['urls'][0] or 'Burg%20Test' in calls['urls'][0]
    assert 'Test+Region' in calls['urls'][0] or 'Test%20Region' in calls['urls'][0]

    # Persisté sur disque, pour survivre à un redémarrage.
    with open(wca.GEOCODE_CACHE_FILE, encoding='utf-8') as f:
        disk = json.load(f)
    assert disk['DL-00001']['lat'] == 50.123456

    # 2e appel : servi par le cache mémoire, jamais un 2e appel réseau.
    r2 = wca.geocode_castle('DL-00001')
    assert r2 == r
    assert calls['n'] == 1


def test_geocode_castle_reference_inconnue_aucun_appel_reseau(monkeypatch, tmp_path):
    """Jamais de géocodage pour une référence absente de la base — une frappe
    invalide/incomplète ne doit pas déclencher de requête Nominatim."""
    wca._state['by_code'] = {}
    wca._state['list'] = []
    wca._state['loaded'] = True
    wca._state['loading'] = False
    _reset_geocode_state(monkeypatch, tmp_path)
    fake_fetch, calls = _fake_fetch_ok()
    import logx_utils
    monkeypatch.setattr(logx_utils, 'fetch_url', fake_fetch)

    assert wca.geocode_castle('ZZ-99999') is None
    assert calls['n'] == 0


def test_geocode_castle_echec_reseau_renvoie_none_sans_exception(monkeypatch, tmp_path):
    _seed_castle()
    _reset_geocode_state(monkeypatch, tmp_path)
    import logx_utils
    monkeypatch.setattr(logx_utils, 'fetch_url', lambda url, timeout=10: None)

    assert wca.geocode_castle('DL-00001') is None


def test_geocode_castle_echec_mis_en_cache_temporairement(monkeypatch, tmp_path):
    """Un échec (réseau ou château introuvable sur Nominatim) est mis en cache
    pour éviter de marteler Nominatim à chaque validation de la même
    référence, mais reste re-tentable après GEOCODE_NEG_RETRY_DAYS (transitoire
    possible, contrairement à un succès qui lui est définitif)."""
    _seed_castle()
    _reset_geocode_state(monkeypatch, tmp_path)
    fake_fetch, calls = _fake_fetch_ok()
    import logx_utils
    # Le throttle Nominatim (1 req/s) n'est pas l'objet de ce test (couvert par
    # test_throttle_nominatim_espace_les_appels) : neutralisé pour rester rapide.
    monkeypatch.setattr(time_mod, 'sleep', lambda s: None)

    monkeypatch.setattr(logx_utils, 'fetch_url', lambda url, timeout=10: None)
    assert wca.geocode_castle('DL-00001') is None
    assert calls['n'] == 0   # échec vient de fake_fetch=None, pas du compteur ok

    # Re-tenter tout de suite après : pas de 2e requête (cache d'échec frais).
    monkeypatch.setattr(logx_utils, 'fetch_url', fake_fetch)
    assert wca.geocode_castle('DL-00001') is None
    assert calls['n'] == 0

    # Mais après expiration du cache d'échec, on retente vraiment.
    cache = wca._load_geocode_cache()
    cache['DL-00001']['ts'] = time_mod.time() - (wca.GEOCODE_NEG_RETRY_DAYS + 1) * 86400
    r = wca.geocode_castle('DL-00001')
    assert r == {'lat': 50.123456, 'lon': 10.654321}
    assert calls['n'] == 1


# ─── Concurrence : TOCTOU sur le chargement du cache disque ─────────────────

def test_geocode_castle_concurrence_ne_perd_pas_de_resultat(monkeypatch, tmp_path):
    """Repro concrète du TOCTOU sur _geocode_cache : deux TOUT premiers appels
    concurrents à geocode_castle(), pour deux châteaux distincts, ne doivent
    jamais faire disparaître silencieusement le résultat de l'un des deux au
    moment de la sauvegarde sur disque.

    Avant le fix, _load_geocode_cache() testait 'is not None' SANS verrou et
    geocode_castle() l'appelait HORS de _geocode_lock : si les deux threads
    passaient ce test avant que l'un des deux n'affecte la variable globale,
    chacun créait son PROPRE dict Python et le capturait dans sa variable
    locale 'cache' — mais _save_geocode_cache() persiste toujours la variable
    GLOBALE, jamais cette référence locale. Résultat : l'écriture de l'un des
    deux threads (celui dont le dict local a cessé d'être la référence
    globale au moment du save) disparaissait silencieusement, et le disque ne
    contenait jamais les deux entrées à la fois.

    Le chevauchement est forcé de façon déterministe (pas d'espoir dans la
    chance de l'ordonnanceur) : open(GEOCODE_CACHE_FILE) est intercepté pour
    ne rendre la main qu'une fois que les deux threads y sont entrés — ce qui
    n'arrive que si le chargement du cache n'est pas sérialisé par le verrou."""
    entry_a = {'code': 'DL-00001', 'castle_no': '1', 'prefix': 'DL',
               'name': 'Burg Alpha', 'location': 'Region Alpha'}
    entry_b = {'code': 'DL-00002', 'castle_no': '2', 'prefix': 'DL',
               'name': 'Burg Beta', 'location': 'Region Beta'}
    wca._state['by_code'] = {'DL-00001': entry_a, 'DL-00002': entry_b}
    wca._state['list'] = [entry_a, entry_b]
    wca._state['loaded'] = True
    wca._state['loading'] = False
    wca._state['error'] = None
    _reset_geocode_state(monkeypatch, tmp_path)
    monkeypatch.setattr(time_mod, 'sleep', lambda s: None)  # throttle non testé ici

    def fake_fetch(url, timeout=10):
        if 'Alpha' in url:
            return json.dumps([{'lat': '1.111', 'lon': '1.111'}])
        return json.dumps([{'lat': '2.222', 'lon': '2.222'}])
    import logx_utils
    monkeypatch.setattr(logx_utils, 'fetch_url', fake_fetch)

    # N'attend que 0.3s : avec le verrou correct, le 2e thread ne PEUT de
    # toute façon jamais atteindre open() pendant que le 1er tient
    # _geocode_lock (il bloque avant, sur l'acquisition du verrou) — la
    # barrière expire donc systématiquement dans ce cas, peu importe la durée.
    barrier = threading.Barrier(2, timeout=0.3)
    real_open = open
    def sync_open(path, *a, **kw):
        if path == wca.GEOCODE_CACHE_FILE:
            try:
                barrier.wait()
            except threading.BrokenBarrierError:
                pass
        return real_open(path, *a, **kw)
    monkeypatch.setattr('builtins.open', sync_open)

    results = {}
    def run(code, key):
        results[key] = wca.geocode_castle(code)

    t1 = threading.Thread(target=run, args=('DL-00001', 'a'))
    t2 = threading.Thread(target=run, args=('DL-00002', 'b'))
    t1.start()
    t2.start()
    t1.join(timeout=5)
    t2.join(timeout=5)
    assert not t1.is_alive() and not t2.is_alive()

    assert results['a'] == {'lat': 1.111, 'lon': 1.111}
    assert results['b'] == {'lat': 2.222, 'lon': 2.222}

    # Les DEUX résultats doivent être persistés — pas seulement celui du
    # thread qui a « gagné » la course sur la référence _geocode_cache.
    with real_open(wca.GEOCODE_CACHE_FILE, encoding='utf-8') as f:
        disk = json.load(f)
    assert disk.get('DL-00001', {}).get('lat') == 1.111
    assert disk.get('DL-00002', {}).get('lat') == 2.222


# ─── get_castle_geocoded : fusion sans mutation de l'état partagé ───────────

def test_get_castle_geocoded_fusionne_sans_muter_letat(monkeypatch, tmp_path):
    entry = _seed_castle()
    _reset_geocode_state(monkeypatch, tmp_path)
    fake_fetch, calls = _fake_fetch_ok()
    import logx_utils
    monkeypatch.setattr(logx_utils, 'fetch_url', fake_fetch)

    merged = wca.get_castle_geocoded('DL-00001')
    assert merged['code'] == 'DL-00001' and merged['name'] == 'Burg Test'
    assert merged['lat'] == 50.123456 and merged['lon'] == 10.654321
    # L'entrée d'origine (utilisée aussi par search_castles/get_castle) reste
    # intacte : aucune fuite de lat/lon dans le dict partagé de _state.
    assert 'lat' not in entry and 'lon' not in entry
    assert 'lat' not in wca._state['by_code']['DL-00001']


def test_get_castle_geocoded_ref_introuvable(monkeypatch, tmp_path):
    wca._state['by_code'] = {}
    wca._state['list'] = []
    wca._state['loaded'] = True
    wca._state['loading'] = False
    _reset_geocode_state(monkeypatch, tmp_path)
    assert wca.get_castle_geocoded('ZZ-99999') is None


def test_get_castle_geocoded_echec_geocodage_lat_lon_none(monkeypatch, tmp_path):
    """Château valide mais non géocodable (échec/introuvable sur Nominatim) :
    l'entrée reste renvoyée (référence toujours valable) avec lat/lon à None,
    plutôt que de faire disparaître le résultat entier."""
    _seed_castle()
    _reset_geocode_state(monkeypatch, tmp_path)
    import logx_utils
    monkeypatch.setattr(logx_utils, 'fetch_url', lambda url, timeout=10: None)

    merged = wca.get_castle_geocoded('DL-00001')
    assert merged is not None and merged['lat'] is None and merged['lon'] is None


# ─── Respect de la politique d'usage Nominatim (1 requête/s max) ────────────

def test_throttle_nominatim_espace_les_appels(monkeypatch):
    calls = {'now': 100.0}
    def fake_time():
        return calls['now']
    sleeps = []
    def fake_sleep(s):
        sleeps.append(s)
        calls['now'] += s
    monkeypatch.setattr(time_mod, 'time', fake_time)
    monkeypatch.setattr(time_mod, 'sleep', fake_sleep)
    monkeypatch.setattr(wca, '_last_nominatim_call', [0.0])

    wca._throttle_nominatim()   # jamais appelé encore -> pas d'attente
    assert sleeps == []
    wca._throttle_nominatim()   # immédiatement après -> attend le complément à 1s
    assert len(sleeps) == 1 and abs(sleeps[0] - 1.0) < 1e-9
