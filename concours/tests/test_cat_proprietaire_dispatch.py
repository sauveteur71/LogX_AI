# -*- coding: utf-8 -*-
"""Dispatch CAT propriétaire (OmniRig/FlexRadio/Icom-remote) + PowerGenius XL
dans logx_http.py — vérifie que _rig_state_dict_impl() route vers le bon
module selon cat_mode, et que _pgxl_state_dict() délègue à logx_powergenius,
sur le même motif que les tests de dispatch tci/flrig/rigctld déjà existants
(voir tests/test_voicekeyer.py pour le même principe côté PTT).

Deuxième moitié du fichier : tests HTTP de bout en bout (vrai serveur sur
port éphémère, même harnais que tests/test_cat_detection_http.py) pour les
points d'intégration que les tests unitaires ci-dessus ne peuvent pas
couvrir seuls — /rig/qsy, /rig/cw, /rig/stop, /rig/connect_test, /pgxl/test
et /hardware/state pour les 3 nouveaux modes CAT + PowerGenius XL. Ajoutés
après une revue adversariale (06/08/2026) qui a trouvé ces points
d'intégration non exercés — en particulier le refus propre du QSY en mode
'flex' (logx_flexradio.py n'expose PAS de set_freq : un appel accidentel y
lèverait une AttributeError bien réelle sur du code qui piloterait une
vraie radio en émission)."""
import http.server
import json
import os
import re
import sys
import threading
import urllib.error
import urllib.request

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_http as httpmod


def test_rig_state_dict_impl_dispatch_omnirig(monkeypatch):
    import logx_cat as cat
    import logx_omnirig as omnirig
    monkeypatch.setattr(cat, 'cat_settings', lambda cfg: {'enabled': True, 'mode': 'omnirig'})
    monkeypatch.setattr(omnirig, 'get_state', lambda cfg: {'ok': True, 'via': 'omnirig'})
    assert httpmod._rig_state_dict_impl({}) == {'ok': True, 'via': 'omnirig'}


def test_rig_state_dict_impl_dispatch_flex(monkeypatch):
    import logx_cat as cat
    import logx_flexradio as flexradio
    monkeypatch.setattr(cat, 'cat_settings', lambda cfg: {'enabled': True, 'mode': 'flex'})
    monkeypatch.setattr(flexradio, 'get_state', lambda cfg: {'ok': True, 'via': 'flex'})
    assert httpmod._rig_state_dict_impl({}) == {'ok': True, 'via': 'flex'}


def test_rig_state_dict_impl_dispatch_icom_remote(monkeypatch):
    import logx_cat as cat
    import logx_icomremote as icomremote
    monkeypatch.setattr(cat, 'cat_settings', lambda cfg: {'enabled': True, 'mode': 'icom_remote'})
    monkeypatch.setattr(icomremote, 'get_state', lambda cfg: {'ok': False, 'via': 'icom_remote'})
    assert httpmod._rig_state_dict_impl({}) == {'ok': False, 'via': 'icom_remote'}


def test_rig_state_dict_impl_mode_inconnu_retombe_sur_rigctld(monkeypatch):
    """Un cat_mode qui ne correspond à AUCUNE des 6 valeurs connues (config
    corrompue, ancienne valeur retirée...) doit retomber sur le comportement
    historique (rigctld) plutôt que de lever une exception — même garantie
    que pour les 4 modes préexistants."""
    import logx_cat as cat
    import logx_rig as rig
    monkeypatch.setattr(cat, 'cat_settings', lambda cfg: {'enabled': True, 'mode': 'inconnu'})
    monkeypatch.setattr(rig, 'rig_settings', lambda cfg: {'enabled': False})
    assert httpmod._rig_state_dict_impl({}) == {'enabled': False}


def test_pgxl_state_dict_delegue_a_powergenius(monkeypatch):
    import logx_powergenius as pgxl
    monkeypatch.setattr(pgxl, 'get_state', lambda cfg: {'ok': True, 'fwd_dbm': 45.2})
    assert httpmod._pgxl_state_dict({}) == {'ok': True, 'fwd_dbm': 45.2}


# ─── Tests HTTP de bout en bout (vrai serveur, port éphémère) ────────────────

@pytest.fixture
def server():
    srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), httpmod.Handler)
    port = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        yield f'http://127.0.0.1:{port}'
    finally:
        srv.shutdown()
        srv.server_close()
        t.join(timeout=5)


def _get(base, path):
    with urllib.request.urlopen(base + path, timeout=5) as r:
        return r.status, json.loads(r.read().decode('utf-8'))


def _post(base, path, payload):
    body = json.dumps(payload).encode('utf-8') if payload is not None else b''
    req = urllib.request.Request(
        base + path, data=body, method='POST',
        headers={'Content-Type': 'application/json', 'X-RC-Token': httpmod.AUTH_TOKEN})
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, json.loads(r.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode('utf-8'))


def _cfg(**kw):
    base = {'cat_enabled': '1'}
    base.update(kw)
    return base


def test_rig_qsy_mode_flex_refuse_proprement_sans_appeler_set_freq(server, monkeypatch):
    """logx_flexradio.py n'expose PAS set_freq — un appel accidentel lèverait
    une AttributeError. Le dispatch doit refuser AVANT tout appel."""
    monkeypatch.setattr(httpmod, 'current_config', _cfg(cat_mode='flex'))
    import logx_flexradio as flexradio
    assert not hasattr(flexradio, 'set_freq')   # confirme la prémisse du test
    status, d = _post(server, '/rig/qsy', {'freq_hz': 14074000})
    assert status == 502   # échec QSY -> 502 (même convention que rigctld, voir ligne finale du bloc)
    assert d['ok'] is False
    assert 'FlexRadio' in d['error']


def test_rig_set_power_mode_natif_appelle_cat_set_power(server, monkeypatch):
    import logx_cat as cat
    monkeypatch.setattr(httpmod, 'current_config', _cfg(cat_mode='native'))
    captured = {}
    monkeypatch.setattr(cat, 'set_power', lambda cfg, watts:
                        captured.update(watts=watts) or {'ok': True, 'watts': int(watts)})
    status, d = _post(server, '/rig/set_power', {'watts': 50})
    assert status == 200 and d == {'ok': True, 'watts': 50}
    assert captured['watts'] == 50


def test_rig_set_power_refus_icom_remonte_400(server, monkeypatch):
    """cat.set_power() refuse déjà Icom en interne (voir tests/test_cat.py) --
    ce test vérifie seulement que le refus remonte bien en 400 côté HTTP,
    pas la logique de refus elle-même."""
    import logx_cat as cat
    monkeypatch.setattr(httpmod, 'current_config', _cfg(cat_mode='native', cat_brand='icom'))
    monkeypatch.setattr(cat, 'set_power', lambda cfg, watts:
                        {'ok': False, 'error': 'Réglage de puissance indisponible en CI-V'})
    status, d = _post(server, '/rig/set_power', {'watts': 50})
    assert status == 400
    assert d['ok'] is False
    assert 'CI-V' in d['error']


def test_rig_set_power_watts_manquant_400(server, monkeypatch):
    monkeypatch.setattr(httpmod, 'current_config', _cfg(cat_mode='native'))
    status, d = _post(server, '/rig/set_power', {})
    assert status == 400
    assert d['ok'] is False


def test_rig_set_power_watts_non_numerique_400(server, monkeypatch):
    monkeypatch.setattr(httpmod, 'current_config', _cfg(cat_mode='native'))
    status, d = _post(server, '/rig/set_power', {'watts': 'beaucoup'})
    assert status == 400
    assert d['ok'] is False


def test_rig_qsy_mode_omnirig_appelle_set_freq_avec_les_bons_arguments(server, monkeypatch):
    monkeypatch.setattr(httpmod, 'current_config', _cfg(cat_mode='omnirig'))
    import logx_omnirig as omnirig
    captured = {}
    monkeypatch.setattr(omnirig, 'set_freq', lambda cfg, freq_hz, mode=None:
                        captured.update(freq_hz=freq_hz, mode=mode) or {'ok': True})
    status, d = _post(server, '/rig/qsy', {'freq_hz': 14074000, 'mode': 'USB'})
    assert status == 200 and d == {'ok': True}
    assert captured == {'freq_hz': 14074000, 'mode': 'USB'}


def test_rig_qsy_mode_icom_remote_appelle_set_freq(server, monkeypatch):
    monkeypatch.setattr(httpmod, 'current_config', _cfg(cat_mode='icom_remote'))
    import logx_icomremote as icomremote
    monkeypatch.setattr(icomremote, 'set_freq', lambda cfg, freq_hz, mode=None:
                        {'ok': False, 'error': 'Protocole de pairing Icom réseau non implémenté'})
    status, d = _post(server, '/rig/qsy', {'freq_hz': 14074000})
    assert status == 502
    assert 'non implémenté' in d['error']


@pytest.mark.parametrize('mode', ['omnirig', 'flex', 'icom_remote'])
def test_rig_cw_refuse_proprement_pour_les_3_nouveaux_modes(server, monkeypatch, mode):
    """Aucun des 3 modules n'expose send_cw — le dispatch doit refuser (400)
    plutôt que de lever une AttributeError."""
    monkeypatch.setattr(httpmod, 'current_config', _cfg(cat_mode=mode))
    status, d = _post(server, '/rig/cw', {'text': 'CQ TEST'})
    assert status == 400
    assert d['ok'] is False
    assert 'CW' in d['error']


@pytest.mark.parametrize('mode', ['omnirig', 'flex', 'icom_remote'])
def test_rig_stop_refuse_proprement_pour_les_3_nouveaux_modes(server, monkeypatch, mode):
    monkeypatch.setattr(httpmod, 'current_config', _cfg(cat_mode=mode))
    status, d = _post(server, '/rig/stop', {})
    assert status == 400
    assert d['ok'] is False


def test_rig_connect_test_mode_omnirig_route_vers_le_bon_module(server, monkeypatch):
    import logx_omnirig as omnirig
    captured = {}
    monkeypatch.setattr(omnirig, 'test_connection', lambda rig_num=1:
                        captured.update(rig_num=rig_num) or {'ok': True})
    status, d = _post(server, '/rig/connect_test', {'mode': 'omnirig', 'rig_num': 2})
    assert status == 200 and d == {'ok': True}
    assert captured['rig_num'] == 2


def test_rig_connect_test_mode_flex_port_invalide_retombe_sur_le_defaut(server, monkeypatch):
    """Un port non convertible en int (champ mal formé côté client, ou requête
    forgée) ne doit jamais faire planter le handler — repli sur DEFAULT_PORT."""
    import logx_flexradio as flexradio
    captured = {}
    monkeypatch.setattr(flexradio, 'test_connection', lambda host, port:
                        captured.update(host=host, port=port) or {'ok': True})
    status, d = _post(server, '/rig/connect_test', {'mode': 'flex', 'port': 'abc'})
    assert status == 200 and d == {'ok': True}
    assert captured['port'] == flexradio.DEFAULT_PORT


def test_rig_connect_test_mode_icom_remote_route_vers_le_bon_module(server, monkeypatch):
    import logx_icomremote as icomremote
    monkeypatch.setattr(icomremote, 'test_connection', lambda host, port:
                        {'ok': False, 'error': 'Protocole de pairing Icom réseau non implémenté'})
    status, d = _post(server, '/rig/connect_test', {'mode': 'icom_remote', 'host': '192.0.2.1'})
    assert status == 502
    assert 'non implémenté' in d['error']


def test_pgxl_test_corps_de_requete_malforme_ne_plante_pas(server, monkeypatch):
    """JSON invalide dans le corps -> payload={} (comme les autres routes de
    ce fichier) plutôt qu'une exception non gérée. Depuis le garde anti-SSRF
    (host vide n'est pas local/LAN), la requête est désormais rejetée AVANT
    d'atteindre test_connection — jamais appelée, plus besoin de la simuler."""
    import logx_powergenius as pgxl
    captured = {}
    monkeypatch.setattr(pgxl, 'test_connection', lambda host, port, timeout:
                        captured.update(host=host, port=port, timeout=timeout)
                        or {'ok': False, 'error': 'Adresse IP/hôte manquante'})
    req = urllib.request.Request(
        server + '/pgxl/test', data=b'{not valid json', method='POST',
        headers={'Content-Type': 'application/json', 'X-RC-Token': httpmod.AUTH_TOKEN})
    with pytest.raises(urllib.error.HTTPError) as exc:
        urllib.request.urlopen(req, timeout=5)
    assert exc.value.code == 400
    assert captured == {}


def test_pgxl_test_ok_true_renvoie_200(server, monkeypatch):
    import logx_powergenius as pgxl
    monkeypatch.setattr(pgxl, 'test_connection', lambda host, port, timeout: {'ok': True})
    status, d = _post(server, '/pgxl/test', {'host': '192.0.2.1', 'port': 9008})
    assert status == 200 and d == {'ok': True}


def test_hardware_state_contient_la_cle_pgxl(server, monkeypatch):
    """Point d'intégration précis : que le dict LITTÉRAL retourné par le
    handler /hardware/state contienne bien 'pgxl', pas seulement que
    _pgxl_state_dict() fonctionne isolément (voir test au-dessus)."""
    import logx_powergenius as pgxl
    monkeypatch.setattr(pgxl, 'get_state', lambda cfg: {'enabled': False})
    status, d = _get(server, '/hardware/state')
    assert status == 200
    assert 'pgxl' in d
    assert d['pgxl'] == {'enabled': False}


# ─── Parité CONFIG_SECTIONS / renderConfigTree() / _catStatus() ─────────────
# Un bug identique (catégorie ajoutée à CONFIG_SECTIONS mais oubliée dans le
# tableau codé en dur de l'ancienne renderHub(), badge du hub jamais mis à
# jour) a déjà été trouvé et corrigé sur ce fichier pour la catégorie 'relay'.
# Depuis la refonte sidebar (08/08/2026), renderHub() a été renommée
# renderConfigTree() et réécrite pour itérer CONFIG_SECTIONS DIRECTEMENT —
# la 2e liste dupliquée (cause structurelle du bug) a disparu, donc la classe
# de bug entière est désormais impossible plutôt que seulement détectée après
# coup. Le test ci-dessous vérifie que cette itération directe n'a pas été
# réintroduite en régression (une 2e liste codée en dur qui reviendrait).

def _config_html_source():
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(base, 'logx_configuration.html'), encoding='utf-8') as f:
        src = f.read()
    # Script inline extrait vers logx_configuration.js (10/08/2026).
    js_path = os.path.join(base, 'logx_configuration.js')
    if os.path.exists(js_path):
        with open(js_path, encoding='utf-8') as f:
            src += '\n' + f.read()
    return src


def _config_sections_keys(src):
    m = re.search(r'const CONFIG_SECTIONS\s*=\s*\[(.*?)\];', src, re.S)
    assert m, "CONFIG_SECTIONS introuvable"
    return re.findall(r"\[\s*'([a-z_]+)'\s*,", m.group(1))


def _cat_status_keys(src):
    m = re.search(r'function _catStatus\(cat\)\{.*?switch\(cat\)\{(.*?)\n  \}\n\}', src, re.S)
    assert m, "_catStatus() introuvable"
    return re.findall(r"case '([a-z_]+)':", m.group(1))


def test_render_config_tree_itere_config_sections_directement():
    src = _config_html_source()
    m = re.search(r'function renderConfigTree\(\)\{(.*?)\n\}', src, re.S)
    assert m, "renderConfigTree() introuvable (ex-renderHub())"
    assert 'CONFIG_SECTIONS.forEach' in m.group(1), (
        "renderConfigTree() ne semble plus itérer CONFIG_SECTIONS directement "
        "— une 2e liste dupliquée a peut-être été réintroduite (régression du "
        "bug historique 'catégorie ajoutée mais badge jamais mis à jour')")


def test_config_sections_ont_toutes_un_cas_dans_cat_status():
    src = _config_html_source()
    sections = set(_config_sections_keys(src))
    statuses = set(_cat_status_keys(src))
    manquantes = sections - statuses
    assert not manquantes, (
        f"Catégorie(s) sans case dans _catStatus() (badge jamais calculé) : {manquantes}")


def test_pgxl_acom_fusionnes_dans_amp_pas_de_categorie_separee():
    """Retour F4GLD (15/08/2026) : 'pgxl'/'acom' ne sont plus des catégories
    CONFIG_SECTIONS à part (rejet explicite du schéma 6b/6c) — leurs champs
    sont fusionnés à l'intérieur de la catégorie unique 'amp'. Le case
    _catStatus('amp') doit couvrir les 3 chemins d'activation possibles
    (amp_enabled générique + pgxl_enabled + acom_enabled dédiés)."""
    src = _config_html_source()
    assert 'pgxl' not in _config_sections_keys(src)
    assert 'acom' not in _config_sections_keys(src)
    assert 'amp' in _cat_status_keys(src)
    m = re.search(r"case 'amp':(.*?)case '", src, re.S)
    assert m, "case 'amp' introuvable dans _catStatus()"
    assert 'pgxl_enabled' in m.group(1) and 'acom_enabled' in m.group(1)
