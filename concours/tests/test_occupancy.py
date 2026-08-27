# -*- coding: utf-8 -*-
"""Occupation des bandes multi-postes — cœur PUR (logx_occupancy.vue_occupation).

Carte « qui est sur quelle bande/mode » pour un log partagé (radioclub / expé /
activation spéciale). Ce module est TRANSPORT-AGNOSTIQUE : il reçoit des statuts
de postes venant de N'IMPORTE quel canal (LAN, Cloud Sync, MySQL) déjà fusionnés,
et en tire la vue d'occupation + les conflits. « Priorité locale » = le statut le
plus FRAIS gagne (le LAN est plus récent que le cloud) — émerge du latest-ts-wins.

Règle F4GLD : deux postes ne doivent jamais émettre sur la MÊME bande ET le MÊME
mode (même bande + mode différent = permis). Un tel recouvrement = conflit signalé.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import logx_occupancy as occ  # noqa: E402


def test_dedup_par_station_le_plus_frais_gagne():
    """Un même poste vu par deux canaux (LAN frais + cloud périmé) -> on garde le
    plus RÉCENT (priorité locale). Une seule ligne par poste."""
    statuts = [
        {'station': 'A', 'call': 'TM6KJS', 'band': '20', 'mode': 'SSB', 'ts': 100},   # cloud, vieux
        {'station': 'A', 'call': 'TM6KJS', 'band': '40', 'mode': 'CW', 'ts': 195},    # LAN, frais
    ]
    v = occ.vue_occupation(statuts, maintenant=200, ttl_s=180)
    assert len(v['stations']) == 1
    assert v['stations'][0]['band'] == '40' and v['stations'][0]['ts'] == 195   # le frais


def test_filtre_les_postes_perimes():
    statuts = [
        {'station': 'A', 'call': 'X', 'band': '20', 'mode': 'SSB', 'ts': 190},   # vivant
        {'station': 'B', 'call': 'Y', 'band': '40', 'mode': 'CW', 'ts': 10},     # périmé (>180 s)
    ]
    v = occ.vue_occupation(statuts, maintenant=200, ttl_s=180)
    assert [s['station'] for s in v['stations']] == ['A']


def test_conflit_meme_bande_meme_mode():
    """Deux postes sur 20 m SSB = conflit (règle « jamais 2 sur la même
    bande/mode »)."""
    statuts = [
        {'station': 'A', 'call': 'X', 'band': '20', 'mode': 'SSB', 'ts': 195},
        {'station': 'B', 'call': 'Y', 'band': '20', 'mode': 'SSB', 'ts': 195},
    ]
    v = occ.vue_occupation(statuts, maintenant=200, ttl_s=180)
    assert len(v['conflits']) == 1
    c = v['conflits'][0]
    assert c['band'] == '20' and c['mode'] == 'SSB'
    assert sorted(c['stations']) == ['A', 'B']


def test_pas_de_conflit_meme_bande_mode_different():
    """Même bande mais mode différent = PERMIS (pas de conflit)."""
    statuts = [
        {'station': 'A', 'call': 'X', 'band': '20', 'mode': 'SSB', 'ts': 195},
        {'station': 'B', 'call': 'Y', 'band': '20', 'mode': 'CW', 'ts': 195},
    ]
    v = occ.vue_occupation(statuts, maintenant=200, ttl_s=180)
    assert v['conflits'] == []
    assert len(v['stations']) == 2


def test_pas_de_conflit_bandes_differentes():
    statuts = [
        {'station': 'A', 'call': 'X', 'band': '20', 'mode': 'SSB', 'ts': 195},
        {'station': 'B', 'call': 'Y', 'band': '40', 'mode': 'SSB', 'ts': 195},
    ]
    v = occ.vue_occupation(statuts, maintenant=200, ttl_s=180)
    assert v['conflits'] == []


def test_station_sans_id_ignoree():
    statuts = [{'call': 'X', 'band': '20', 'mode': 'SSB', 'ts': 195}]   # pas de 'station'
    v = occ.vue_occupation(statuts, maintenant=200, ttl_s=180)
    assert v['stations'] == [] and v['conflits'] == []


# ─── Registre serveur ────────────────────────────────────────────────────────

def test_registre_mon_statut_et_pairs():
    occ._reset_pour_test()
    occ.poser_mon_statut('A', 'TM6KJS', '20', 'SSB', maintenant=200)
    occ.enregistrer_pair({'station': 'B', 'call': 'TM6KJS', 'band': '40', 'mode': 'CW', 'ts': 198})
    v = occ.vue(maintenant=200)
    assert sorted(s['station'] for s in v['stations']) == ['A', 'B']
    assert v['conflits'] == []                               # bandes différentes


def test_registre_conflit_moi_vs_pair():
    occ._reset_pour_test()
    occ.poser_mon_statut('A', 'TM6KJS', '20', 'SSB', maintenant=200)
    occ.enregistrer_pair({'station': 'B', 'call': 'TM6KJS', 'band': '20', 'mode': 'SSB', 'ts': 199})
    v = occ.vue(maintenant=200)
    assert len(v['conflits']) == 1 and v['conflits'][0]['band'] == '20'


def test_registre_pair_perime_purge():
    occ._reset_pour_test()
    occ.poser_mon_statut('A', 'X', '20', 'SSB', maintenant=1000)
    occ.enregistrer_pair({'station': 'B', 'call': 'Y', 'band': '40', 'mode': 'CW', 'ts': 100})  # vieux
    v = occ.vue(maintenant=1000, ttl_s=180)
    assert [s['station'] for s in v['stations']] == ['A']    # B périmé, absent
    # et purgé du registre : une 2e vue sans le ré-enregistrer reste sans B
    assert 'B' not in occ._pairs


def test_registre_pair_plus_frais_ecrase_lancien():
    occ._reset_pour_test()
    occ.enregistrer_pair({'station': 'B', 'call': 'Y', 'band': '20', 'mode': 'SSB', 'ts': 100})
    occ.enregistrer_pair({'station': 'B', 'call': 'Y', 'band': '40', 'mode': 'CW', 'ts': 200})  # plus frais
    v = occ.vue(maintenant=200)
    assert len(v['stations']) == 1 and v['stations'][0]['band'] == '40'


# ─── Canal LAN (priorité locale, instantané) ─────────────────────────────────

def test_lan_note_beacon_alimente_occupation():
    """Un beacon LAN reçu avec band/mode alimente l'occupation
    (enregistrer_pair) — la carte multi-postes en temps réel local."""
    import time as _t
    import logx_lan_sync as lan
    occ._reset_pour_test()
    raw = ('{"logx":1,"iid":"PEER1","http_port":8080,"call":"TM6KJS",'
           '"band":"20","mode":"SSB"}').encode('utf-8')
    lan.note_beacon('192.168.1.50', raw, '')          # jeton ouvert (LAN de confiance)
    v = occ.vue(_t.time())
    assert any(s['station'] == 'PEER1' and s['band'] == '20' and s['mode'] == 'SSB'
               for s in v['stations'])


def test_lan_beacon_porte_ma_bande_mode():
    """Le beacon émis inclut la bande/mode de CE poste (depuis mon_statut), pour
    que les pairs voient mon occupation."""
    import json as _j
    import logx_lan_sync as lan
    occ._reset_pour_test()
    occ.poser_mon_statut('MOI', 'TM6KJS', '40', 'CW', maintenant=1000)
    d = _j.loads(lan._my_beacon({'callsign': 'TM6KJS'}).decode('utf-8'))
    assert d['band'] == '40' and d['mode'] == 'CW'


# ─── Canal Cloud (distant, dossier partagé) ──────────────────────────────────

def test_cloud_publie_mon_statut_dans_un_fichier(tmp_path):
    """Publier écrit MON statut dans un fichier occupancy DÉDIÉ (séparé des
    fichiers de log) du dossier partagé."""
    import glob
    import os
    import time as _t
    import logx_cloudsync as cs
    occ._reset_pour_test()
    folder = str(tmp_path)
    occ.poser_mon_statut('MOI', 'TM6KJS', '20', 'SSB', _t.time())
    cs._publier_occupation(folder, {'callsign': 'TM6KJS'})
    fichiers = glob.glob(os.path.join(folder, 'logx_occupancy_*.json'))
    assert len(fichiers) == 1


def test_cloud_lit_les_pairs_et_alimente_loccupation(tmp_path):
    """Lire ramène les fichiers occupancy des AUTRES postes -> enregistrer_pair."""
    import json
    import os
    import time as _t
    import logx_cloudsync as cs
    occ._reset_pour_test()
    folder = str(tmp_path)
    # un pair dépose son fichier dans le dossier partagé
    with open(os.path.join(folder, 'logx_occupancy_TM6KJS_PEER.json'), 'w', encoding='utf-8') as f:
        json.dump({'station': 'PEER', 'call': 'TM6KJS', 'band': '40', 'mode': 'CW', 'ts': _t.time()}, f)
    cs._lire_occupation(folder, {'callsign': 'TM6KJS'})
    v = occ.vue(_t.time())
    assert any(s['station'] == 'PEER' and s['band'] == '40' for s in v['stations'])


# ─── Canal MySQL (distant temps réel, radioclub) ─────────────────────────────

class _FakeCur:
    def __init__(self, conn): self.conn = conn; self._res = []
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def execute(self, sql, params=None):
        self.conn.calls.append((sql, params))
        self._res = self.conn.rows if sql.strip().upper().startswith('SELECT STATION') else []
    def fetchall(self): return self._res


class _FakeConn:
    def __init__(self, rows=None): self.calls = []; self.rows = rows or []
    def cursor(self): return _FakeCur(self)


def test_mysql_ensure_occ_schema_cree_la_table():
    import logx_mysql_sync as mysql
    conn = _FakeConn()
    mysql._ensure_occ_schema(conn)
    assert any('create table' in s.lower() and 'occupancy' in s.lower() for s, _ in conn.calls)


def test_mysql_publie_upsert_et_lit_les_pairs():
    import logx_mysql_sync as mysql
    occ._reset_pour_test()
    conn = _FakeConn(rows=[('PEER', 'TM6KJS', '40', 'CW', 1000.0)])
    occ.poser_mon_statut('MOI', 'TM6KJS', '20', 'SSB', 1000.0)
    mysql._publier_occupation_mysql(conn, 'MOI', occ._mon_statut[0])
    assert any('insert' in s.lower() and 'occupancy' in s.lower() for s, _ in conn.calls)
    mysql._lire_occupation_mysql(conn, 'MOI')
    v = occ.vue(1000.0)
    assert any(x['station'] == 'PEER' and x['band'] == '40' for x in v['stations'])
