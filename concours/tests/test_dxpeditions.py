# -*- coding: utf-8 -*-
"""DXpeditions annoncées (logx_dxpeditions) : parsing du flux NG3K ADXO,
statut actif/à venir déduit des dates, et croisement avec les spots cluster
pour la fréquence live (panneau CHASSE, demande F4GLD 04/08/2026). Sans
réseau, fetch_url mocké — même patron que tests/test_pota.py."""
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_dxpeditions as dxp
import logx_utils


def _rss(*items_desc):
    items = ''.join(
        f'<item><title>t{i}</title><description>{d}</description></item>'
        for i, d in enumerate(items_desc))
    return f'<?xml version="1.0"?><rss><channel>{items}</channel></rss>'


def _reset_cache():
    dxp._cache['data'] = None
    dxp._cache['ts'] = 0


# ─── _parse_description() (déjà en place, jamais testé jusqu'ici) ───────────

def test_parse_description_champs_complets():
    d = dxp._parse_description(
        'Jul 4-23, 2026 -- Crete -- SV9 -- QSL: LoTW -- Source: OPDX (13 May 2026) -- By HB9EMP')
    assert d['dates'] == 'Jul 4-23, 2026'
    assert d['entity'] == 'Crete'
    assert d['callsign'] == 'SV9'
    assert d['qsl'] == 'LoTW'
    assert d['source'] == 'OPDX (13 May 2026)'
    assert d['info'] == 'By HB9EMP'


def test_parse_description_champs_manquants_ne_plante_pas():
    d = dxp._parse_description('Aug 3-9, 2026 -- Tuvalu')
    assert d['dates'] == 'Aug 3-9, 2026'
    assert d['entity'] == 'Tuvalu'
    assert d['callsign'] == ''


def test_parse_description_vide():
    d = dxp._parse_description('')
    assert d == {'dates': '', 'entity': '', 'callsign': '', 'qsl': '', 'source': '', 'info': ''}


# ─── fetch_dxpeditions() : réseau mocké, cache, annotation 'worked' ─────────

def test_fetch_dxpeditions_mappe_titre_et_champs(monkeypatch):
    _reset_cache()
    xml = _rss('Aug 3-9, 2026 -- Tuvalu -- T2JK -- QSL: LoTW -- Source: MM0NDX')
    monkeypatch.setattr(logx_utils, 'fetch_url', lambda *a, **k: xml)
    out = dxp.fetch_dxpeditions()
    assert len(out) == 1
    assert out[0]['callsign'] == 'T2JK'
    assert out[0]['entity'] == 'Tuvalu'


def test_fetch_dxpeditions_entree_vide_ignoree(monkeypatch):
    _reset_cache()
    xml = _rss('', 'Aug 3-9, 2026 -- Tuvalu -- T2JK -- QSL: LoTW')
    monkeypatch.setattr(logx_utils, 'fetch_url', lambda *a, **k: xml)
    out = dxp.fetch_dxpeditions()
    assert len(out) == 1


def test_fetch_dxpeditions_cache_reutilise_sans_re_fetch(monkeypatch):
    _reset_cache()
    appels = []
    def fake_fetch(*a, **k):
        appels.append(1)
        return _rss('Aug 3-9, 2026 -- Tuvalu -- T2JK -- QSL: LoTW')
    monkeypatch.setattr(logx_utils, 'fetch_url', fake_fetch)
    dxp.fetch_dxpeditions()
    dxp.fetch_dxpeditions()
    assert len(appels) == 1, 'le cache 1h aurait du eviter le 2e appel reseau'


def test_fetch_dxpeditions_reseau_indisponible_retombe_sur_dernier_connu(monkeypatch):
    _reset_cache()
    monkeypatch.setattr(logx_utils, 'fetch_url', lambda *a, **k: None)
    assert dxp.fetch_dxpeditions() == []
    dxp._cache['data'] = [{'callsign': 'X'}]
    dxp._cache['ts'] = 0   # perime, force un re-fetch qui va echouer
    assert dxp.fetch_dxpeditions() == [{'callsign': 'X'}]


def test_fetch_dxpeditions_xml_invalide_ne_leve_jamais(monkeypatch):
    _reset_cache()
    monkeypatch.setattr(logx_utils, 'fetch_url', lambda *a, **k: 'pas du xml')
    assert dxp.fetch_dxpeditions() == []


def test_fetch_dxpeditions_annotation_worked(monkeypatch):
    _reset_cache()
    xml = _rss(
        'Aug 3-9, 2026 -- Tuvalu -- T2JK -- QSL: LoTW',
        'Aug 5-10, 2026 -- Crete -- SV9XYZ -- QSL: LoTW')
    monkeypatch.setattr(logx_utils, 'fetch_url', lambda *a, **k: xml)
    out = dxp.fetch_dxpeditions(worked_entities={'Crete'})
    par_entite = {e['entity']: e['worked'] for e in out}
    assert par_entite['Tuvalu'] is False
    assert par_entite['Crete'] is True


# ─── _parse_date_range() ──────────────────────────────────────────────────

def test_parse_date_range_meme_mois():
    assert dxp._parse_date_range('Aug 3-9, 2026') == (date(2026, 8, 3), date(2026, 8, 9))


def test_parse_date_range_mois_different():
    assert dxp._parse_date_range('Jul 7-Aug 4, 2026') == (date(2026, 7, 7), date(2026, 8, 4))


def test_parse_date_range_un_seul_jour():
    assert dxp._parse_date_range('Aug 5, 2026') == (date(2026, 8, 5), date(2026, 8, 5))


def test_parse_date_range_franchissement_annee():
    assert dxp._parse_date_range('Dec 28-Jan 15, 2027') == (date(2026, 12, 28), date(2027, 1, 15))


def test_parse_date_range_format_inconnu_ne_leve_jamais():
    assert dxp._parse_date_range('quelque chose de bizarre') == (None, None)
    assert dxp._parse_date_range('') == (None, None)
    assert dxp._parse_date_range(None) == (None, None)


def test_parse_date_range_date_invalide_ne_leve_jamais():
    assert dxp._parse_date_range('Feb 30, 2026') == (None, None)


# ─── _match_spot_freq() ────────────────────────────────────────────────────

def test_match_spot_freq_trouve():
    spots = {'HF': [{'dx': 'SV9XYZ', 'freq': 14195.0}]}
    freq, band = dxp._match_spot_freq('SV9XYZ', spots)
    assert freq == 14195.0 and band == 'HF'


def test_match_spot_freq_insensible_a_la_casse():
    spots = {'HF': [{'dx': 'sv9xyz', 'freq': 14195.0}]}
    freq, band = dxp._match_spot_freq('SV9XYZ', spots)
    assert freq == 14195.0


def test_match_spot_freq_ignore_le_suffixe_portable_du_spot():
    spots = {'HF': [{'dx': 'SV9XYZ/P', 'freq': 14195.0}]}
    freq, band = dxp._match_spot_freq('SV9XYZ', spots)
    assert freq == 14195.0


def test_match_spot_freq_ne_matche_que_le_premier_indicatif_de_ng3k():
    """NG3K liste parfois plusieurs opérateurs séparés par une virgule — on
    ne matche que le premier segment, cas le plus courant (expédition mono-
    indicatif)."""
    spots = {'HF': [{'dx': 'SV9XYZ', 'freq': 14195.0}]}
    freq, band = dxp._match_spot_freq('SV9XYZ, HB9EMP', spots)
    assert freq == 14195.0


def test_match_spot_freq_aucune_correspondance():
    spots = {'HF': [{'dx': 'W1AW', 'freq': 14195.0}]}
    assert dxp._match_spot_freq('SV9XYZ', spots) == (None, None)


def test_match_spot_freq_indicatif_vide():
    assert dxp._match_spot_freq('', {'HF': [{'dx': 'W1AW', 'freq': 14195.0}]}) == (None, None)


def test_match_spot_freq_sans_spots():
    assert dxp._match_spot_freq('SV9XYZ', None) == (None, None)
    assert dxp._match_spot_freq('SV9XYZ', {}) == (None, None)


# ─── fetch_dxpeditions_chasse() ───────────────────────────────────────────

def test_chasse_statut_actif_selon_la_date(monkeypatch):
    _reset_cache()
    xml = _rss('Aug 3-9, 2026 -- Tuvalu -- T2JK -- QSL: LoTW')
    monkeypatch.setattr(logx_utils, 'fetch_url', lambda *a, **k: xml)
    out = dxp.fetch_dxpeditions_chasse(today=date(2026, 8, 5))
    assert out[0]['status'] == 'active'


def test_chasse_statut_a_venir(monkeypatch):
    _reset_cache()
    xml = _rss('Aug 3-9, 2026 -- Tuvalu -- T2JK -- QSL: LoTW')
    monkeypatch.setattr(logx_utils, 'fetch_url', lambda *a, **k: xml)
    out = dxp.fetch_dxpeditions_chasse(today=date(2026, 7, 1))
    assert out[0]['status'] == 'upcoming'


def test_chasse_expedition_terminee_retiree(monkeypatch):
    _reset_cache()
    xml = _rss(
        'Aug 3-9, 2026 -- Tuvalu -- T2JK -- QSL: LoTW',
        'Aug 20-25, 2026 -- Crete -- SV9XYZ -- QSL: LoTW')
    monkeypatch.setattr(logx_utils, 'fetch_url', lambda *a, **k: xml)
    out = dxp.fetch_dxpeditions_chasse(today=date(2026, 9, 1))
    entites = [e['entity'] for e in out]
    assert 'Tuvalu' not in entites and 'Crete' not in entites


def test_chasse_spot_cluster_force_le_statut_actif_et_donne_la_frequence(monkeypatch):
    """Une expédition annoncée pour PLUS TARD, mais déjà repérée sur le
    cluster (les op's démarrent souvent en avance) : le spot doit l'emporter
    sur le calcul de dates."""
    _reset_cache()
    xml = _rss('Aug 3-9, 2026 -- Tuvalu -- T2JK -- QSL: LoTW')
    monkeypatch.setattr(logx_utils, 'fetch_url', lambda *a, **k: xml)
    spots = {'HF': [{'dx': 'T2JK', 'freq': 21295.0}]}
    out = dxp.fetch_dxpeditions_chasse(spots_by_band=spots, today=date(2026, 8, 1))
    assert out[0]['status'] == 'active'
    assert out[0]['freq_khz'] == 21295.0
    assert out[0]['spot_band'] == 'HF'


def test_chasse_dates_illisibles_donne_unknown_pas_une_exception(monkeypatch):
    _reset_cache()
    xml = _rss('n\'importe quoi -- Tuvalu -- T2JK -- QSL: LoTW')
    monkeypatch.setattr(logx_utils, 'fetch_url', lambda *a, **k: xml)
    out = dxp.fetch_dxpeditions_chasse(today=date(2026, 8, 1))
    assert out[0]['status'] == 'unknown'


def test_chasse_tri_actives_avec_frequence_dabord(monkeypatch):
    _reset_cache()
    xml = _rss(
        'Aug 1-15, 2026 -- Tuvalu -- T2JK -- QSL: LoTW',        # active, pas de spot
        'Aug 1-15, 2026 -- Crete -- SV9XYZ -- QSL: LoTW',       # active, spottee
        'Sep 1-15, 2026 -- Aruba -- P40AA -- QSL: LoTW')        # a venir
    monkeypatch.setattr(logx_utils, 'fetch_url', lambda *a, **k: xml)
    spots = {'HF': [{'dx': 'SV9XYZ', 'freq': 14195.0}]}
    out = dxp.fetch_dxpeditions_chasse(spots_by_band=spots, today=date(2026, 8, 5))
    assert [e['entity'] for e in out] == ['Crete', 'Tuvalu', 'Aruba']


# ─── GET /data/dxpeditions_active (câblage HTTP, logx_http.py) ─────────────
# Même harnais que tests/test_config_endpoint_usage_mode.py : vrai serveur
# sur port éphémère, la logique elle-même est déjà couverte ci-dessus.

def test_endpoint_dxpeditions_active(monkeypatch):
    import http.server
    import json
    import threading
    import urllib.request
    import logx_http as httpmod

    monkeypatch.setattr(httpmod, 'current_config', {'callsign': 'F4GLD', 'contest': ''})
    monkeypatch.setattr(httpmod, 'shared_log', [])
    monkeypatch.setattr(httpmod, '_spots_from_caches', lambda: {'HF': []})

    def fake_chasse(worked_entities=None, spots_by_band=None, today=None):
        assert spots_by_band == {'HF': []}
        return [{'callsign': 'T2JK', 'entity': 'Tuvalu', 'status': 'active',
                 'freq_khz': 21295.0, 'spot_band': 'HF'}]

    import logx_dxpeditions
    monkeypatch.setattr(logx_dxpeditions, 'fetch_dxpeditions_chasse', fake_chasse)

    srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), httpmod.Handler)
    port = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        with urllib.request.urlopen(f'http://127.0.0.1:{port}/data/dxpeditions_active', timeout=5) as r:
            status, body = r.status, json.loads(r.read().decode('utf-8'))
    finally:
        srv.shutdown()
        srv.server_close()
        t.join(timeout=5)

    assert status == 200
    assert body['expeditions'][0]['callsign'] == 'T2JK'
    assert body['expeditions'][0]['freq_khz'] == 21295.0
