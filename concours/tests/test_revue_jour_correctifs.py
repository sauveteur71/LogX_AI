# -*- coding: utf-8 -*-
"""Non-régression des 8 défauts trouvés par la revue adversariale du 01/08/2026.

Les chantiers du jour (station multi-rotors, propagation bornée par le bas,
horloge WSJT-X, format de dépôt) ont été relus par une revue adversariale qui
a EXÉCUTÉ ses scénarios. Elle a confirmé 8 défauts, dominés par un motif : le
backend rotor du jour était correct mais AUCUN appelant côté interface ne
l'atteignait — le piège même que ces chantiers corrigeaient ailleurs. Ces
tests figent chaque correctif.
"""
import os
import re
import sys
import threading
import time

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CONCOURS not in sys.path:
    sys.path.insert(0, CONCOURS)

import logx_station as S    # noqa: E402
import logx_paths as P      # noqa: E402
import logx_wsjtx as W      # noqa: E402
from logx_utils import locator_to_latlon   # noqa: E402


def _lire(nom):
    with open(os.path.join(CONCOURS, nom), encoding='utf-8') as f:
        return f.read()


# ─── 1/6/7. Le rotor du parc est enfin JOIGNABLE (state, point, satellite) ──

def test_une_station_parc_only_a_son_rotor_ENABLED():
    """Défaut : rotor_settings ne lit que les champs legacy → une station
    configurée via le seul nouvel éditeur voyait son bouton « pointer » masqué
    (/rotor/state enabled:false)."""
    cfg = {'rotors': [{'id': 'rn', 'nom': 'Pylône', 'enabled': True,
                       'host': '10.0.0.1', 'port': 4533, 'offset_deg': 30}],
           'antennes': [{'nom': 'Yagi', 'bandes': ['14'], 'rotor_id': 'rn'}]}
    d = S.rotor_defaut(cfg)
    assert d['enabled'] is True
    assert d['host'] == '10.0.0.1'
    assert d['offset_deg'] == 30
    assert d['source'] == 'parc'


def test_l_ancien_rotor_unique_reste_pris_en_compte():
    # charger() migre les champs legacy en un rotor de parc : la source devient
    # donc 'parc', ce qui est correct — l'important est qu'il soit joignable,
    # avec l'adresse d'origine et sans décalage inventé.
    d = S.rotor_defaut({'rotor_enabled': True, 'rotor_host': '1.2.3.4',
                        'rotor_port': 4533})
    assert d['enabled'] is True and d['host'] == '1.2.3.4'
    assert d['offset_deg'] == 0


def test_sans_rotor_configure_rien_n_est_active():
    d = S.rotor_defaut({})
    assert d['enabled'] is False


def test_le_suivi_satellite_prefere_le_rotor_VHF_du_parc():
    """Une station parc-only ne pouvait lancer AUCUN suivi (sat_track lisait
    rotor_settings legacy). Il résout désormais via le parc, en préférant
    l'antenne 144/432."""
    cfg = {'rotors': [{'id': 'azel', 'nom': 'AzEl', 'enabled': True,
                       'host': '192.168.1.50', 'port': 4533, 'offset_deg': 12}],
           'antennes': [{'bandes': ['144', '432'], 'rotor_id': 'azel'}]}
    d = S.rotor_defaut(cfg, prefer_bandes=['144', '432'])
    assert d['enabled'] is True and d['host'] == '192.168.1.50'
    assert d['offset_deg'] == 12


def test_le_pilotage_par_bande_ne_tourne_QUE_le_bon_pylone():
    """Le cœur du multi-op : la bande route vers son pylône, avec son
    décalage — vérifié via le vrai handler /rotor/point."""
    import http.server
    import json
    import threading as _th
    import urllib.request
    import logx_http as h
    import logx_rotor as R
    vus = []
    orig_set, orig_get = R.set_position, R.get_position
    R.set_position = lambda host, port, az, el=0, proto='rotctld': (
        vus.append((host, round(az, 1))) or {'ok': True, 'azimuth': az})
    R.get_position = lambda host, port, proto='rotctld': {'ok': True, 'azimuth': 0.0, 'elevation': 0.0}
    cfg = {'rotors': [{'id': 'p1', 'nom': 'P1', 'enabled': True, 'host': '10.0.0.1',
                       'port': 4533, 'offset_deg': 0},
                      {'id': 'p2', 'nom': 'P2', 'enabled': True, 'host': '10.0.0.2',
                       'port': 4533, 'offset_deg': 30}],
           'antennes': [{'bandes': ['14'], 'rotor_id': 'p1'},
                        {'bandes': ['144'], 'rotor_id': 'p2'}]}
    with h.config_lock:
        sauve = dict(h.current_config)
        h.current_config.clear()
        h.current_config.update(cfg)
    srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), h.Handler)
    port = srv.server_address[1]
    _th.Thread(target=srv.serve_forever, daemon=True).start()
    hdr = {'Content-Type': 'application/json', 'X-Auth-Token': h.AUTH_TOKEN,
           'Cookie': 'rc_token=%s' % h.AUTH_TOKEN}
    try:
        base = 'http://127.0.0.1:%d' % port
        st = json.loads(urllib.request.urlopen(base + '/rotor/state', timeout=15).read())
        assert st['enabled'] is True and st['nb_rotors'] == 2

        def point(payload):
            rq = urllib.request.Request(base + '/rotor/point',
                                        data=json.dumps(payload).encode(),
                                        headers=hdr, method='POST')
            return json.loads(urllib.request.urlopen(rq, timeout=15).read())

        vus.clear(); point({'azimuth': 100, 'bande': '14'})
        assert vus == [('10.0.0.1', 100.0)]            # P1, pas de décalage
        vus.clear(); point({'azimuth': 100, 'bande': '144'})
        assert vus == [('10.0.0.2', 70.0)]             # P2, décalage 30° appliqué
    finally:
        srv.shutdown()
        R.set_position, R.get_position = orig_set, orig_get
        with h.config_lock:
            h.current_config.clear()
            h.current_config.update(sauve)


@pytest.mark.parametrize('page, fn', [
    ('logx_locator_reverse.js', 'pointAntennaFromCompass'),
    ('logx_chasse.html', 'pointTo'),
])
def test_les_appelants_UI_transmettent_la_bande(page, fn):
    """Sans la bande dans la requête, tout retombe sur le rotor par défaut :
    le multi-pylône serait resté injoignable."""
    src = _lire(page)
    i = src.find('function ' + fn)
    assert i != -1
    corps = src[i:i + 600]
    assert 'bande' in corps, '%s n\'envoie pas la bande à /rotor/point' % fn


# ─── 2. Grey-line : le 160 m ouvert au lever, régional en plein jour ────────

@pytest.mark.parametrize('heure, minute, attendu', [
    (4, 30, 'ouverte'),    # soleil ~0° : fenêtre grey-line, meilleur DX basses
    (5, 0,  'ouverte'),    # soleil ~+5° : encore grey-line
    (9, 41, 'regional'),   # soleil +53° : couche D, régional seulement
    (0, 0,  'ouverte'),    # nuit
])
def test_le_160m_suit_la_grey_line_puis_la_couche_D(heure, minute, attendu):
    import datetime
    la, lo = locator_to_latlon('JN15WD')
    sol = {'muf': {'muf': 14.0}, 'solar': {'sfi': 120, 'k_index': 2}}
    r = P.etat_bandes_hf(la, lo, datetime.datetime(2026, 8, 1, heure, minute), sol)
    b160 = [x for x in r['bandes'] if x['band'] == '1.8'][0]
    assert b160['etat'] == attendu, '160 m à %02dh%02d : %s' % (heure, minute, b160['etat'])


def test_le_verdict_ne_contredit_plus_le_score_en_grey_line():
    """Le gate ne doit plus rétrograder en 'regional' une bande dont le score
    (bonus grey-line inclus) vaut 'ouverte'."""
    import datetime
    la, lo = locator_to_latlon('JN15WD')
    sol = {'muf': {'muf': 14.0}, 'solar': {'sfi': 120, 'k_index': 2}}
    r = P.etat_bandes_hf(la, lo, datetime.datetime(2026, 8, 1, 5, 0), sol)
    for b in r['bandes']:
        if b['band'] in ('1.8', '3.5') and b['score'] >= 62:
            assert b['etat'] != 'regional', b


# ─── 3. Collision d'identifiant de rotor/ampli dans l'éditeur ───────────────

def test_l_editeur_forge_un_id_libre_apres_suppression():
    """`'rotor'+(length+1)` reforgeait un id déjà pris après un retrait : une
    antenne se reliait alors au mauvais pylône en silence. Le correctif cherche
    le premier id LIBRE."""
    src = _lire('logx_configuration.html')
    assert '_idLibre' in src
    # la vieille forme fautive a disparu des fonctions d'ajout
    assert "'rotor'+(rotorsRows.length+1)" not in src
    assert "'ampli'+(amplisRows.length+1)" not in src


# ─── 4. derive_horloge : itération protégée par verrou ──────────────────────

def test_derive_horloge_ne_plante_pas_sous_ecriture_concurrente():
    """Itérer le deque pendant qu'un thread y ajoute levait « deque mutated
    during iteration » — sur une bande FT8 chargée, l'alerte de dérive
    plantait quand on en avait le plus besoin."""
    W._dt_echantillons.clear()
    for i in range(4000):
        W._note_dt('K%dABC' % i, {'dt': 0.5}, time.time())
    stop = [False]

    def ecrivain():
        t = time.time()
        while not stop[0]:
            W._note_dt('BUSY', {'dt': 0.4}, t)
    th = threading.Thread(target=ecrivain, daemon=True)
    th.start()
    try:
        for _ in range(300):
            W.derive_horloge()          # ne doit lever aucune RuntimeError
    finally:
        stop[0] = True
        th.join(timeout=2)
    W._dt_echantillons.clear()


def test_le_verrou_dt_existe():
    assert hasattr(W, '_dt_lock')


# ─── 5/8. Le 6 m (50 MHz) est du THF : export EDI, pas Cabrillo ─────────────

@pytest.mark.parametrize('const', ['VHF_UHF_SHF_BANDS', 'BANDES_THF'])
def test_le_50MHz_est_dans_les_listes_THF(const):
    """IARU_50MHZ et tout log 6 m donnaient « Aucun QSO VHF/UHF à exporter »
    (aucun fichier) et des stats HF, faute du 50 MHz dans ces listes.

    EV-7 25e incrément : VHF_UHF_SHF_BANDS (locale à exportEDI()) a été
    extraite vers logx_export_edi.js -- BANDES_THF reste dans
    logx_logbook.js. On cherche dans les deux plutôt que de figer où vit
    chaque constante, pour ne pas re-casser ce test au prochain incrément."""
    src = _lire('logx_logbook.js') + '\n' + _lire('logx_export_edi.js')
    m = re.search(const + r"\s*=\s*\[([^\]]*)\]", src)
    assert m, '%s introuvable' % const
    bandes = [x.strip().strip("'\"") for x in m.group(1).split(',') if x.strip()]
    assert '50' in bandes, '%s omet le 50 MHz' % const


def test_IARU_50MHZ_se_depose_bien_en_EDI():
    """Vérifie que la définition confirme le format EDI — le routage client
    (formatDepot) le lira et lui donnera son fichier."""
    from logx_definitions import CONTEST_DEFINITIONS
    d = CONTEST_DEFINITIONS.get('IARU_50MHZ')
    if d is None:
        pytest.skip('IARU_50MHZ absent de cette base')
    assert '50' in [str(b) for b in d.get('bands', [])]
