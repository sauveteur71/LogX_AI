# -*- coding: utf-8 -*-
"""Audit BASSE 727 : le disjoncteur HRDLog (HRDLOG_FAIL_CIRCUIT échecs
consécutifs -> arrêt anticipé) confondait rejet-de-contenu et absence-réseau.

Le disjoncteur existe pour détecter « HRDLog injoignable » (son propre message).
Or un serveur qui RÉPOND — même en rejetant le QSO (indicatif/QSO invalide,
<insert>0</insert>) — est joignable. Compter ces rejets faisait avorter les QSO
VALIDES restants dès 5 rejets de contenu consécutifs. Seule une absence totale
de réponse (échec réseau sur tous les hôtes) doit alimenter le disjoncteur.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_qsl as qsl

NB_HOSTS = len(qsl.HRDLOG_HOSTS)


def _prep(monkeypatch):
    monkeypatch.setattr(qsl, 'qsl_settings',
                        lambda cfg: {'hrdlog_enabled': True,
                                     'hrdlog_callsign': 'F4TEST', 'hrdlog_code': 'X'})
    monkeypatch.setattr(qsl, '_single_qso_adif', lambda q, cfg: '<CALL:6>F4TEST<EOR>')


def test_rejets_contenu_consecutifs_n_avortent_pas_les_qso_suivants(monkeypatch):
    _prep(monkeypatch)
    calls = []

    def rejette(*a, **k):
        calls.append(1)
        return '<insert>0</insert>'   # serveur JOIGNABLE, rejette le contenu

    monkeypatch.setattr(qsl, '_hrdlog_post_one', rejette)
    qsos = [{'call': 'A%d' % i} for i in range(10)]
    res = qsl.upload_hrdlog({}, qsos)
    # Les 10 QSO doivent être TENTÉS (chacun essaie tous les hôtes) — pas d'arrêt
    # anticipé sur des rejets de contenu.
    assert len(calls) == 10 * NB_HOSTS, "arrêt anticipé sur rejets de contenu (QSO valides perdus)"
    assert res['failed'] == 10


def test_echecs_reseau_consecutifs_declenchent_toujours_le_disjoncteur(monkeypatch):
    _prep(monkeypatch)
    calls = []

    def injoignable(*a, **k):
        calls.append(1)
        raise OSError('réseau coupé')   # aucune réponse serveur

    monkeypatch.setattr(qsl, '_hrdlog_post_one', injoignable)
    qsos = [{'call': 'A%d' % i} for i in range(10)]
    res = qsl.upload_hrdlog({}, qsos)
    # Le disjoncteur DOIT toujours couper : seuls HRDLOG_FAIL_CIRCUIT QSO tentés.
    assert len(calls) == qsl.HRDLOG_FAIL_CIRCUIT * NB_HOSTS, "le disjoncteur réseau ne coupe plus"
    assert res['failed'] == 10
    assert 'anticip' in (res['error'] or '')
