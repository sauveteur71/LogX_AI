# -*- coding: utf-8 -*-
"""Non-régression : la persistance du log doit être INCRÉMENTALE.

Avant ce correctif, save_log_to_disk() faisait un `DELETE FROM qso` suivi de
la RÉINSERTION DE TOUT LE CARNET, puis réécrivait intégralement
shared_log.json — et elle est appelée UNE FOIS PAR QSO (/log/add, /log/update,
/log/delete, /qsl_scan/upload, et une fois par QSO tiré par Cloud Sync). Le
coût d'un seul QSO était donc linéaire en taille du carnet, et le coût cumulé
quadratique. Mesuré (POST /log/add réel, SSD local) :

    carnet      0 QSO ->    10 ms
    carnet 20 000 QSO ->   487 ms
    carnet 80 000 QSO -> 2 089 ms   (shared_log.json = 29,4 Mo réécrits)

soit, pour une DXpedition de 80 000 QSO, de l'ordre du téraoctet réellement
écrit sur le support — et 2 secondes de gel de l'interface par QSO au bout de
quelques jours de pile-up, là où rien n'est réparable.

Ces tests mesurent le TRAVAIL fourni (nombre de QSO re-sérialisés, nombre de
réécritures du JSON), jamais une durée : aucune dépendance à la vitesse de la
machine, donc aucun risque d'instabilité en CI."""
import json
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_storage as st


def _qso(i):
    return {'id': 1000 + i, 'call': f'F{i}ABC', 'band': '14', 'mode': 'CW',
            'contest': 'EU_HF_CHAMP', 'date': '20260801', 'time': '12:03',
            'operator': 'OP1', 'points': 1, 'locator': 'JO31AA',
            'rst_sent': '599', 'num_sent': f'{i:03d}'}


def _in_tmp(tmp_path, fn):
    """Exécute fn dans un dossier vierge, avec l'état module remis à neuf
    (les chemins de logx_storage sont relatifs au dossier courant)."""
    old = os.getcwd()
    os.chdir(tmp_path)
    saved = (list(st.shared_log), list(st.deleted_qsos),
             st.log_version, st.hard_reset_version)
    try:
        st.shared_log[:] = []
        st.deleted_qsos[:] = []
        st.log_version = 0
        st.hard_reset_version = 0
        return fn()
    finally:
        st.shared_log[:] = saved[0]
        st.deleted_qsos[:] = saved[1]
        st.log_version, st.hard_reset_version = saved[2], saved[3]
        os.chdir(old)


class _Compteurs:
    """Compte le travail réellement fourni par save_log_to_disk() :
    - `lignes` : QSO re-sérialisés pour SQLite (1 par ligne écrite) ;
    - `json`   : réécritures COMPLÈTES de shared_log.json."""

    def __init__(self, monkeypatch):
        self.lignes = 0
        self.json = 0
        vrai_row = st._row_from_qso
        vrai_json = st.save_json_atomic

        def row(q):
            self.lignes += 1
            return vrai_row(q)

        def js(path, data, lock=None, compact=False):
            if path == 'shared_log.json':
                self.json += 1
            return vrai_json(path, data, lock=lock, compact=compact)

        monkeypatch.setattr(st, '_row_from_qso', row)
        monkeypatch.setattr(st, 'save_json_atomic', js)

    def raz(self):
        self.lignes = 0
        self.json = 0


def _ajouter(qso):
    """Réplique EXACTE du protocole de logx_http.add_qso_to_log()."""
    with st.log_lock:
        st.shared_log.append(qso)
        st.bump_log_version()
        st.stamp_qso_version(qso)
    st.save_log_to_disk()


def _db_calls():
    conn = sqlite3.connect(st.DB_FILE)
    try:
        return [r[0] for r in conn.execute('SELECT call FROM qso ORDER BY rowid_pk')]
    finally:
        conn.close()


def test_un_qso_ne_reecrit_pas_tout_le_carnet(tmp_path, monkeypatch):
    """LE test du défaut : sur un carnet de 4 000 QSO, ajouter 10 QSO ne doit
    pas re-sérialiser 40 000 lignes ni réécrire 10 fois le JSON complet."""
    def run():
        c = _Compteurs(monkeypatch)
        N = 4000
        st.shared_log[:] = [_qso(i) for i in range(N)]
        st.save_log_to_disk()                     # matérialise la base (1 écriture complète)
        assert c.lignes == N                      # la sauvegarde initiale, elle, écrit tout
        c.raz()

        for i in range(N, N + 10):
            _ajouter(_qso(i))

        assert c.lignes <= 10 * 5, (
            f"{c.lignes} QSO re-sérialisés pour 10 QSO ajoutés à un carnet de "
            f"{N} : la persistance réécrit TOUT le carnet à chaque QSO "
            f"(coût cumulé quadratique — de l'ordre du To écrit sur une "
            f"expédition de 80 000 QSO)")
        assert c.json <= 2, (
            f"shared_log.json réécrit {c.json} fois pour 10 QSO ajoutés : à "
            f"80 000 QSO ce fichier pèse 29 Mo, soit 29 Mo écrits PAR QSO")

        # …et le carnet sur disque est malgré tout EXACT
        assert _db_calls() == [q['call'] for q in st.shared_log]
    _in_tmp(tmp_path, run)


def test_le_qso_est_sur_disque_des_son_ajout(tmp_path, monkeypatch):
    """Le gain de coût ne doit PAS venir d'une écriture différée : la base
    (source de vérité, transactionnelle) doit contenir le QSO dès le retour de
    save_log_to_disk(), sinon une coupure secteur en expédition perdrait tout
    ce qui n'a pas encore été vidangé."""
    def run():
        _Compteurs(monkeypatch)
        st.shared_log[:] = [_qso(i) for i in range(300)]
        st.save_log_to_disk()
        for i in range(300, 310):
            _ajouter(_qso(i))
            assert _db_calls()[-1] == _qso(i)['call'], (
                'QSO absent de logx.db au retour de save_log_to_disk() : '
                'écriture différée = QSO perdus à la coupure suivante')
    _in_tmp(tmp_path, run)


def test_suppression_et_correction_restent_exactes_et_bon_marche(tmp_path, monkeypatch):
    """Les autres mutations unitaires (/log/update, /log/delete,
    /qsl_scan/upload) doivent elles aussi être incrémentales ET exactes."""
    def run():
        c = _Compteurs(monkeypatch)
        N = 2000
        st.shared_log[:] = [_qso(i) for i in range(N)]
        st.save_log_to_disk()
        c.raz()

        # /log/update : remplacement en place, id conservé
        corrige = dict(_qso(5), call='F5CORR')
        with st.log_lock:
            for i, q in enumerate(st.shared_log):
                if q.get('id') == corrige['id']:
                    st.shared_log[i] = corrige
                    break
            st.bump_log_version()
            st.stamp_qso_version(corrige)
        st.save_log_to_disk()

        # /log/delete : tombstone + retrait
        with st.log_lock:
            st.shared_log[:] = [q for q in st.shared_log if q.get('id') != 1007]
            st.bump_log_version()
            st.mark_qso_deleted(1007)
        st.save_log_to_disk()

        # /qsl_scan/upload : mutation EN PLACE du dict déjà dans shared_log
        with st.log_lock:
            cible = next(q for q in st.shared_log if q.get('id') == 1009)
            cible['qsl_scan'] = 'scans/1009.jpg'
            st.bump_log_version()
            st.stamp_qso_version(cible)
        st.save_log_to_disk()

        assert c.lignes <= 15, (
            f'{c.lignes} QSO re-sérialisés pour 3 mutations unitaires sur un '
            f'carnet de {N}')
        assert _db_calls() == [q['call'] for q in st.shared_log]

        # Rechargement complet : le disque restitue EXACTEMENT la mémoire
        attendu = [q['call'] for q in st.shared_log]
        st.shared_log[:] = []
        st.load_log_from_disk()
        assert [q['call'] for q in st.shared_log] == attendu
        assert next(q for q in st.shared_log if q['id'] == 1005)['call'] == 'F5CORR'
        assert next(q for q in st.shared_log if q['id'] == 1009)['qsl_scan'] == 'scans/1009.jpg'
        assert not any(q['id'] == 1007 for q in st.shared_log)
    _in_tmp(tmp_path, run)


def test_json_de_secours_rattrape_le_carnet(tmp_path, monkeypatch):
    """shared_log.json n'est plus réécrit à chaque QSO, mais il ne doit pas
    pour autant se périmer indéfiniment : il rattrape le carnet au fil des
    ajouts (réécriture complète amortie)."""
    def run():
        _Compteurs(monkeypatch)
        st.shared_log[:] = [_qso(i) for i in range(500)]
        st.save_log_to_disk()
        for i in range(500, 900):
            _ajouter(_qso(i))
        with open('shared_log.json', encoding='utf-8') as f:
            secours = json.load(f)
        assert len(secours) >= 850, (
            f'shared_log.json figé à {len(secours)} QSO alors que le carnet en '
            f'compte {len(st.shared_log)} : le secours lisible ne rattrape '
            f'jamais le carnet')
    _in_tmp(tmp_path, run)


def test_reset_puis_reprise_ne_ressuscite_aucun_qso(tmp_path, monkeypatch):
    """Un effacement en masse (/log/reset, /log/archive?clear=true) doit vider
    la table : une persistance incrémentale mal fichue laisserait les anciens
    QSO en base, qui réapparaîtraient au redémarrage suivant."""
    def run():
        _Compteurs(monkeypatch)
        st.shared_log[:] = [_qso(i) for i in range(50)]
        st.save_log_to_disk()
        with st.log_lock:
            st.shared_log.clear()
        st.bump_log_version()
        st.mark_hard_reset()
        # effacement_autorise=True : ce test REJOUE /log/reset, et le vrai
        # /log/reset porte ce consentement depuis l'ajout du garde-fou
        # anti-destruction (logx_storage._SEUIL_PERTE_MASSIVE). Sans lui, le
        # garde-fou refuse — et c'est exactement ce qu'on lui demande : 50 QSO
        # en base remplacés par 0 sans que personne l'ait demandé, c'est
        # l'incident du 16-19/08/2026. Ne PAS retirer ce paramètre pour
        # « faire passer le test » : ce serait rouvrir le trou.
        st.save_log_to_disk(effacement_autorise=True)
        assert _db_calls() == []
        for i in range(900, 903):
            _ajouter(_qso(i))
        st.shared_log[:] = []
        st.load_log_from_disk()
        assert [q['call'] for q in st.shared_log] == ['F900ABC', 'F901ABC', 'F902ABC']
    _in_tmp(tmp_path, run)
