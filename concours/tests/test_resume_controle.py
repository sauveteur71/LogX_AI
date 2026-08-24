# -*- coding: utf-8 -*-
"""IA-1 lot 4 — résumé pré-vol INFORMATIF avant export/LoTW.

resume_controle compte les findings par niveau (s'appuie sur validate_log, même
vérité que le panneau VÉRIFIER). upload_lotw JOINT ce résumé à sa réponse mais
ne bloque JAMAIS l'upload (masquer != bloquer) : un log en erreur est tout de
même proposé à tqsl."""
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
os.chdir(BASE)

import logx_validator as v   # noqa: E402
import logx_qsl as qsl        # noqa: E402


def test_resume_compte_par_niveau():
    log = [{'call': 'F4ABC', 'band': '14', 'freq': '7.0', 'mode': 'SSB',
            'date': '20260101', 'time': '1200', 'rst_sent': '59', 'rst_rcvd': '59'}]
    r = v.resume_controle(log, '', {})
    assert set(r) >= {'erreurs', 'attentions', 'infos', 'ok'}
    assert r['attentions'] >= 1                      # freq/bande incohérente
    assert r['ok'] is (r['erreurs'] == 0)


def test_upload_lotw_joint_le_controle_et_tente_malgre_erreurs(monkeypatch):
    # LoTW configuré + tqsl simulés : on prouve (1) que la réponse porte
    # 'controle' et (2) que tqsl EST appelé même quand le log est en erreur.
    monkeypatch.setattr(qsl, 'qsl_settings',
                        lambda cfg: {'lotw_upload_enabled': True,
                                     'lotw_station_location': 'HOME'})
    monkeypatch.setattr(qsl, '_find_tqsl_binary', lambda: 'tqsl')

    class _Proc:
        returncode = 0
        stdout = ''
        stderr = ''

    appels = {'tqsl': False}

    def _fake_run(args, timeout=90):
        appels['tqsl'] = True
        return _Proc()

    monkeypatch.setattr(qsl, '_run_tqsl', _fake_run)

    # QSO SANS indicatif -> validate_log le classe 'erreur' (indicatif_vide).
    qsos = [{'call': '', 'band': '14', 'mode': 'SSB', 'date': '20260101',
             'time': '1200', 'rst_sent': '59', 'rst_rcvd': '59'}]
    res = qsl.upload_lotw({}, qsos)

    assert appels['tqsl'] is True                    # upload TENTÉ malgré l'erreur
    assert res.get('ok') is True
    assert 'controle' in res                         # résumé joint
    assert res['controle']['erreurs'] >= 1           # l'erreur est bien comptée
