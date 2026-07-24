# -*- coding: utf-8 -*-
"""Tests du panneau CONDITIONS de l'écran mural : détection du contexte
VHF/UHF (logx_wall._vhf_active, pilote l'affichage du panneau EME — jamais
pertinent sur un poste HF pur) et accès non bloquant à la météo locale
(logx_weather.get_weather_cached), même patron que get_solar_cached()/
get_muf_cached() dans logx_clusters.py."""
import http.server
import json
import os
import sys
import threading
import time
import urllib.request

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_http as httpmod


# ─── logx_wall._vhf_active / wall_state()['vhf_active'] ─────────────────────

def test_vhf_active_vrai_pour_concours_144_432():
    import logx_wall as wall
    assert wall._vhf_active({'contest': 'REF_RPH'}) is True   # bandes ['144','432']


def test_vhf_active_faux_pour_concours_hf_pur():
    import logx_wall as wall
    assert wall._vhf_active({'contest': 'CQ_WW_CW'}) is False   # bandes HF seules


def test_vhf_active_toggle_parasite_ne_contredit_pas_un_concours_hf_defini():
    """Un toggle CONFIG resté coché (résidu d'une session VHF précédente) ne
    doit jamais rallumer le panneau EME sur un concours dont la fiche définit
    des bandes 100% HF — sinon l'encart devient hors-sujet sur un poste HF."""
    import logx_wall as wall
    cfg = {'contest': 'CQ_WW_CW', 'toggles': {'band_2m': True, 'band_70cm': True}}
    assert wall._vhf_active(cfg) is False


def test_vhf_active_repli_toggle_si_concours_indetermine():
    import logx_wall as wall
    assert wall._vhf_active({'contest': '', 'toggles': {'band_70cm': True}}) is True
    assert wall._vhf_active({'contest': '', 'toggles': {}}) is False
    assert wall._vhf_active({'contest': 'INCONNU_XYZ', 'toggles': {'band_23cm': True}}) is True


def test_vhf_active_6m_seul_reste_faux():
    """50 MHz (6 m) est volontairement exclu : EME hors de portée en pratique."""
    import logx_wall as wall
    assert wall._vhf_active({'contest': '', 'toggles': {'band_6m': True}}) is False


def test_vhf_active_cfg_absent_ou_vide_ne_plante_pas():
    import logx_wall as wall
    assert wall._vhf_active(None) is False
    assert wall._vhf_active({}) is False


def test_wall_state_expose_vhf_active():
    import logx_wall as wall
    st_vhf = wall.wall_state([], {'contest': 'REF_RPH', 'locator': 'JN15XC'})
    assert st_vhf['vhf_active'] is True
    st_hf = wall.wall_state([], {'contest': 'CQ_WW_CW', 'locator': 'JN15XC'})
    assert st_hf['vhf_active'] is False


# ─── logx_weather.get_weather_cached : jamais bloquant ──────────────────────

def _reset_weather_cache():
    import logx_weather as weather
    weather._cache.update(ts=0, data=None, key='')
    if weather._weather_refresh_lock.locked():
        weather._weather_refresh_lock.release()


def test_weather_cached_sans_locator():
    import logx_weather as weather
    assert weather.get_weather_cached(None, None) == {
        'ok': False, 'error': 'Locator station non défini'}


def test_weather_cached_cache_froid_ne_bloque_pas_et_se_peuple_en_fond(monkeypatch):
    """Premier appel sur un point jamais vu : doit revenir IMMÉDIATEMENT
    (le vrai fetch réseau part dans un thread détaché), puis un appel
    ultérieur voit le cache peuplé par ce thread de fond."""
    import logx_weather as weather
    _reset_weather_cache()
    calls = []

    def fake_get_weather(lat, lon):
        calls.append((lat, lon))
        data = {'ok': True, 'temp': 12, 'wind': 8, 'gust': 10, 'precip': 0,
                 'desc': 'Ciel clair', 'icon': '☀️', 'warn': ''}
        weather._cache.update(ts=time.time(), data=data, key=f'{lat:.2f},{lon:.2f}')
        return data

    monkeypatch.setattr(weather, 'get_weather', fake_get_weather)

    t0 = time.time()
    first = weather.get_weather_cached(45.0, 4.0)
    elapsed = time.time() - t0
    assert elapsed < 0.5, "get_weather_cached() a bloqué le thread appelant"
    assert first == {'ok': False, 'error': 'Météo en cours de récupération…', 'stale': True}

    deadline = time.time() + 2
    while not calls and time.time() < deadline:
        time.sleep(0.02)
    assert calls, "le rafraîchissement en tâche de fond n'a jamais tourné"

    second = weather.get_weather_cached(45.0, 4.0)
    assert second['ok'] is True and second['temp'] == 12 and second['stale'] is False


def test_weather_cached_perime_sert_lancien_cache_marque_stale(monkeypatch):
    """Cache existant mais > CACHE_S : on sert quand même l'ancienne valeur
    (mieux qu'un trou), marquée 'stale', tout en relançant un rafraîchissement
    en fond — même logique que get_solar_cached()/get_muf_cached()."""
    import logx_weather as weather
    _reset_weather_cache()
    old_data = {'ok': True, 'temp': 1, 'wind': 2, 'gust': 3, 'precip': 0,
                'desc': 'x', 'icon': 'x', 'warn': ''}
    weather._cache.update(ts=time.time() - weather.CACHE_S - 10, data=old_data, key='45.00,4.00')
    monkeypatch.setattr(weather, 'get_weather', lambda lat, lon: None)

    out = weather.get_weather_cached(45.001, 4.001)   # arrondi -> même clé '45.00,4.00'
    assert out['ok'] is True and out['temp'] == 1 and out['stale'] is True


def test_weather_cached_nouveau_lieu_ne_sert_pas_la_meteo_dun_autre_qth(monkeypatch):
    """Après un changement de locator, ne JAMAIS servir la météo (température,
    vent) d'un ancien QTH sous prétexte qu'elle est "en cache" — trompeur pour
    la sécurité antenne."""
    import logx_weather as weather
    _reset_weather_cache()
    weather._cache.update(ts=time.time(), data={'ok': True, 'temp': 99, 'wind': 50}, key='0.00,0.00')
    monkeypatch.setattr(weather, 'get_weather', lambda lat, lon: None)

    out = weather.get_weather_cached(45.0, 4.0)
    assert out['ok'] is False
    assert 'temp' not in out


# ─── GET /data/weather : garde-fou bout-en-bout contre un retour au blocage ──

@pytest.fixture
def server():
    srv = http.server.HTTPServer(('127.0.0.1', 0), httpmod.Handler)
    port = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        yield f'http://127.0.0.1:{port}'
    finally:
        srv.shutdown()
        t.join(timeout=5)


def _get(base, path):
    with urllib.request.urlopen(base + path, timeout=5) as r:
        return json.loads(r.read().decode('utf-8'))


def test_endpoint_data_weather_passe_par_le_cache_non_bloquant(server, monkeypatch):
    """Régression : /data/weather doit appeler get_weather_cached() (jamais
    bloquant), PAS get_weather() (bloquant jusqu'à ~18 s si le cache est
    périmé) — sinon l'écran mural, pollé en continu, gèle sa connexion."""
    import logx_weather as weather
    monkeypatch.setattr(httpmod, 'current_config', {'locator': 'JN15XC'})
    monkeypatch.setattr(weather, 'get_weather_cached',
                         lambda lat, lon: {'ok': True, 'marker': 'cache-non-bloquant'})
    called_blocking = []
    monkeypatch.setattr(weather, 'get_weather', lambda lat, lon: called_blocking.append(1))

    d = _get(server, '/data/weather')
    assert d.get('marker') == 'cache-non-bloquant'
    assert not called_blocking, "le handler appelle encore la version bloquante get_weather()"


def test_endpoint_data_wall_expose_vhf_active(server, monkeypatch):
    monkeypatch.setattr(httpmod, 'current_config', {'contest': 'REF_RPH', 'locator': 'JN15XC'})
    monkeypatch.setattr(httpmod, 'shared_log', [])
    d = _get(server, '/data/wall')
    assert d['vhf_active'] is True
