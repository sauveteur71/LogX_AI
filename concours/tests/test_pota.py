# -*- coding: utf-8 -*-
"""Spots d'activateurs POTA (logx_pota) — sans réseau, fetch_url mocké."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_pota as pota

SAMPLE = [{
    'spotId': 53769145, 'activator': '9A/DF5WC', 'frequency': '10115', 'mode': 'CW',
    'reference': 'HR-0139', 'parkName': None, 'spotTime': '2026-07-21T05:50:58',
    'spotter': '9A/DF5WC', 'comments': 'QRT', 'source': 'Ham2K Portable Logger',
    'invalid': None, 'name': 'Otok Rab Natura 2000', 'locationDesc': 'HR-PG',
    'grid4': 'JN74', 'grid6': 'JN74js', 'latitude': 44.7772, 'longitude': 14.7569,
    'count': 5, 'expire': 343,
}]


def test_fetch_pota_spots_mappe_les_champs(monkeypatch):
    def fake_fetch(url, timeout=10):
        assert url == pota.POTA_SPOTS_URL
        return json.dumps(SAMPLE)
    import logx_utils
    monkeypatch.setattr(logx_utils, 'fetch_url', fake_fetch)
    pota._cache.update(data=None, ts=0)

    spots = pota.fetch_pota_spots()
    assert len(spots) == 1
    s = spots[0]
    assert s['call'] == '9A/DF5WC'
    assert s['reference'] == 'HR-0139'
    assert s['mode'] == 'CW'
    assert s['freq'] == 10115.0
    assert s['band'] == '10.1'         # 10.115 MHz -> bande 30 m (WARC)
    assert s['grid'] == 'JN74js'
    assert s['park_name'] == 'Otok Rab Natura 2000'
    assert s['source'] == 'pota'


def test_cache_reutilise_sans_re_fetch(monkeypatch):
    calls = {'n': 0}
    def fake_fetch(url, timeout=10):
        calls['n'] += 1
        return json.dumps(SAMPLE)
    import logx_utils
    monkeypatch.setattr(logx_utils, 'fetch_url', fake_fetch)
    pota._cache.update(data=None, ts=0)

    pota.fetch_pota_spots()
    pota.fetch_pota_spots()
    assert calls['n'] == 1   # 2e appel servi depuis le cache (TTL 90 s)


def test_reseau_indisponible_retombe_sur_liste_vide(monkeypatch):
    def fake_fetch(url, timeout=10):
        return None
    import logx_utils
    monkeypatch.setattr(logx_utils, 'fetch_url', fake_fetch)
    pota._cache.update(data=None, ts=0)

    assert pota.fetch_pota_spots() == []


def test_json_invalide_ne_leve_jamais(monkeypatch):
    def fake_fetch(url, timeout=10):
        return 'pas du json'
    import logx_utils
    monkeypatch.setattr(logx_utils, 'fetch_url', fake_fetch)
    pota._cache.update(data=None, ts=0)

    assert pota.fetch_pota_spots() == []


# ─── post_spot (auto-spot, POST) ─────────────────────────────────────────────
# Format vérifié contre hunterlog (cf. docstring du module) : activator/
# spotter/frequency/reference/mode/source/comments, endpoint /spot/.

def test_post_spot_valide_champs_avant_tout_appel_reseau(monkeypatch):
    """Une erreur de saisie triviale ne doit jamais déclencher un aller-retour
    réseau — le mock lève si jamais il est appelé."""
    import logx_utils

    def boom(*a, **k):
        raise AssertionError('post_url_json ne doit pas être appelé')
    monkeypatch.setattr(logx_utils, 'post_url_json', boom)

    assert pota.post_spot('', 'FR-0123', 14285, 'SSB')['error'] == 'Indicatif activateur manquant'
    assert pota.post_spot('F4GLD', '', 14285, 'SSB')['error'] == 'Référence parc manquante'
    assert pota.post_spot('F4GLD', 'FR-0123', 0, 'SSB')['error'] == 'Fréquence manquante ou invalide'
    assert pota.post_spot('F4GLD', 'FR-0123', 14285, '')['error'] == 'Mode manquant'


def test_post_spot_succes_construit_le_bon_payload(monkeypatch):
    captured = {}
    def fake_post(url, payload, timeout=10, headers=None):
        captured['url'] = url
        captured['payload'] = payload
        captured['headers'] = headers
        return 200, '{"status":"ok"}'
    import logx_utils
    monkeypatch.setattr(logx_utils, 'post_url_json', fake_post)

    r = pota.post_spot('f4gld', 'fr-0123', 14285.0, 'ssb', comment='CQ POTA')
    assert r['ok'] is True
    assert captured['url'] == pota.POTA_POST_SPOT_URL == 'https://api.pota.app/spot/'
    assert captured['payload'] == {
        'activator': 'F4GLD', 'spotter': 'F4GLD', 'frequency': '14285.0',
        'reference': 'FR-0123', 'mode': 'SSB', 'source': 'LogXAI',
        'comments': 'CQ POTA',
    }
    assert captured['headers']['User-Agent'].startswith('LogXAI/')


def test_post_spot_spotter_distinct_de_l_activateur(monkeypatch):
    """Cas d'un opérateur qui spotte un P2P (chasseur != activateur)."""
    captured = {}
    def fake_post(url, payload, timeout=10, headers=None):
        captured['payload'] = payload
        return 200, 'ok'
    import logx_utils
    monkeypatch.setattr(logx_utils, 'post_url_json', fake_post)

    pota.post_spot('DL1AA', 'FR-0123', 14285, 'CW', spotter='F4GLD')
    assert captured['payload']['activator'] == 'DL1AA'
    assert captured['payload']['spotter'] == 'F4GLD'


def test_post_spot_reseau_injoignable(monkeypatch):
    import logx_utils
    monkeypatch.setattr(logx_utils, 'post_url_json', lambda *a, **k: (None, None))

    r = pota.post_spot('F4GLD', 'FR-0123', 14285, 'SSB')
    assert r['ok'] is False and 'injoignable' in r['error']


def test_post_spot_refuse_par_le_serveur(monkeypatch):
    import logx_utils
    monkeypatch.setattr(logx_utils, 'post_url_json',
                        lambda *a, **k: (400, 'reference invalide'))

    r = pota.post_spot('F4GLD', 'FR-9999999', 14285, 'SSB')
    assert r['ok'] is False
    assert '400' in r['error'] and 'reference invalide' in r['error']


# ─── Régressions revue adversariale du commit e9a01b8 ───────────────────────

def test_post_spot_reference_non_chaine_ne_plante_pas(monkeypatch):
    """Reproduit le bug HIGH : un payload JSON peut envoyer une référence
    numérique ({"reference": 123}, ex. un client mal formé ou du JS qui
    n'a pas casté). Avant le correctif, (reference or '').strip() levait
    une AttributeError ('int' object has no attribute 'strip') puisqu'un
    int non nul est "truthy" et n'a pas de .strip()."""
    captured = {}
    def fake_post(url, payload, timeout=10, headers=None):
        captured['payload'] = payload
        return 200, 'ok'
    import logx_utils
    monkeypatch.setattr(logx_utils, 'post_url_json', fake_post)

    r = pota.post_spot('F4GLD', 123, 14285, 'SSB')
    assert r['ok'] is True
    assert captured['payload']['reference'] == '123'


def test_post_spot_frequence_arrondie_sans_bruit_flottant(monkeypatch):
    """Reproduit le bug MEDIUM : str(freq_khz) sur un float issu d'une
    conversion (MHz*1000, division...) peut contenir du bruit IEEE-754
    (ex. 21444.052489233058) au lieu d'une fréquence propre — jamais ce
    qu'on veut envoyer à l'API publique POTA. f'{freq_khz:.1f}' arrondit
    à la décimale (résolution largement suffisante en kHz)."""
    captured = {}
    def fake_post(url, payload, timeout=10, headers=None):
        captured['payload'] = payload
        return 200, 'ok'
    import logx_utils
    monkeypatch.setattr(logx_utils, 'post_url_json', fake_post)

    bruit_ieee754 = 21444.052489233058
    assert str(bruit_ieee754) == '21444.052489233058'  # le bug, si on l'avait laissé
    pota.post_spot('F4GLD', 'FR-0123', bruit_ieee754, 'SSB')
    assert captured['payload']['frequency'] == '21444.1'


# ─── export_filename (export ADIF prêt à téléverser) ─────────────────────────
# Format vérifié contre l'exemple officiel de docs.pota.app/docs/
# activator_reference/submitting_logs.html : KA8H@US-1515-20201127.adi

def test_export_filename_format_nominal():
    qsos = [{'date': '20260816'}, {'date': '20260816'}]
    assert pota.export_filename('F4GLD', 'FR-0123', qsos) == 'F4GLD@FR-0123-20260816.adi'


def test_export_filename_indicatif_et_ref_normalises():
    """Minuscules, espaces ou suffixe /P dans l'indicatif : tout ce qui
    n'est pas lettre/chiffre/tiret est retiré (le fichier doit rester un nom
    de fichier valide sur tout OS, et matcher le format attendu par POTA)."""
    qsos = [{'date': '20260816'}]
    assert pota.export_filename('f4gld/p', 'fr-0123', qsos) == 'F4GLDP@FR-0123-20260816.adi'


def test_export_filename_prend_la_date_la_plus_recente():
    """En usage normal, activation_qsos() a déjà réduit le lot à un seul jour
    UTC pour POTA — mais si jamais plusieurs dates cohabitent (ex. appel
    direct sans passer par ce filtre), on prend la plus récente plutôt que de
    planter ou de prendre la première rencontrée."""
    qsos = [{'date': '20260814'}, {'date': '20260816'}, {'date': '20260815'}]
    assert pota.export_filename('F4GLD', 'FR-0123', qsos) == 'F4GLD@FR-0123-20260816.adi'


def test_export_filename_sans_date_ni_qso_ne_plante_pas():
    assert pota.export_filename('F4GLD', 'FR-0123', []) == 'F4GLD@FR-0123.adi'
    assert pota.export_filename('', '', []) == 'LOG@PARK.adi'
