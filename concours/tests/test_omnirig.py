# -*- coding: utf-8 -*-
"""Tests du pilotage OmniRig (logx_omnirig) : aucun vrai objet COM/pywin32
touché — `_open_com` est remplacé par une fabrique renvoyant un faux objet
Rig1/Rig2 en mémoire, comme `_open_ws` dans tests/test_tci.py."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_omnirig as omnirig


class _FakeRig:
    """Double d'IRigX : mêmes attributs que l'objet COM réel (Status, Freq,
    Mode, Tx, RigType), lève une exception si `raise_on` matche l'attribut
    lu/écrit — simule une radio qui plante en cours d'appel."""

    def __init__(self, status=omnirig.ST_ONLINE, freq=14195000,
                 mode=omnirig.PM_SSB_U, rig_type='Icom IC-7300', raise_on=None):
        self.Status = status
        self.Freq = freq
        self.Mode = mode
        self.Tx = omnirig.PM_RX
        self.RigType = rig_type
        self._raise_on = raise_on or ()

    def _maybe_raise(self, name):
        if name in self._raise_on:
            raise RuntimeError(f'COM cassé sur {name}')


class _FakeOmniRig:
    def __init__(self, rig1=None, rig2=None):
        self.Rig1 = rig1 or _FakeRig()
        self.Rig2 = rig2 or _FakeRig(status=omnirig.ST_NOTCONFIGURED)


def _install_fake(monkeypatch, fake):
    monkeypatch.setattr(omnirig, '_open_com', lambda: fake)


# ─── omnirig_settings() : pure, jamais d'exception ─────────────────────────

def test_settings_defauts_surs_sur_cfg_vide():
    s = omnirig.omnirig_settings({})
    assert s == {'enabled': False, 'rig_num': 1}


def test_settings_defauts_surs_sur_cfg_none():
    s = omnirig.omnirig_settings(None)
    assert s['enabled'] is False
    assert s['rig_num'] == 1


def test_settings_rig_num_2_accepte():
    s = omnirig.omnirig_settings({'omnirig_enabled': True, 'omnirig_rig_num': 2})
    assert s == {'enabled': True, 'rig_num': 2}


def test_settings_rig_num_invalide_replie_sur_1():
    s = omnirig.omnirig_settings({'omnirig_rig_num': 'n_importe_quoi'})
    assert s['rig_num'] == 1
    s2 = omnirig.omnirig_settings({'omnirig_rig_num': 3})
    assert s2['rig_num'] == 1


# ─── get_state() ────────────────────────────────────────────────────────────

def test_get_state_desactive_ne_touche_jamais_com(monkeypatch):
    # _open_com reste None/pas patché : si le code appelait quand même le
    # COM, ce test planterait au lieu de retourner proprement.
    monkeypatch.setattr(omnirig, '_open_com', None)
    r = omnirig.get_state({'omnirig_enabled': False})
    assert r['ok'] is False
    assert r['enabled'] is False


def test_get_state_en_ligne_retourne_freq_et_mode(monkeypatch):
    fake = _FakeOmniRig(rig1=_FakeRig(status=omnirig.ST_ONLINE, freq=7074000,
                                       mode=omnirig.PM_DIG_U, rig_type='Yaesu FTDX10'))
    _install_fake(monkeypatch, fake)
    r = omnirig.get_state({'omnirig_enabled': True, 'omnirig_rig_num': 1})
    assert r == {'ok': True, 'enabled': True, 'freq_hz': 7074000,
                 'freq_khz': 7074.0, 'mode': 'DATA', 'device': 'Yaesu FTDX10'}


def test_get_state_rig2_hors_ligne_erreur_explicite(monkeypatch):
    fake = _FakeOmniRig(rig2=_FakeRig(status=omnirig.ST_NOTRESPONDING))
    _install_fake(monkeypatch, fake)
    r = omnirig.get_state({'omnirig_enabled': True, 'omnirig_rig_num': 2})
    assert r['ok'] is False
    assert r['enabled'] is True
    assert 'Rig2' in r['error']
    assert 'ne répond pas' in r['error']


def test_get_state_mode_inconnu_devient_chaine_vide(monkeypatch):
    fake = _FakeOmniRig(rig1=_FakeRig(mode=999999))
    _install_fake(monkeypatch, fake)
    r = omnirig.get_state({'omnirig_enabled': True})
    assert r['ok'] is True
    assert r['mode'] == ''


def test_get_state_pywin32_absent_message_clair(monkeypatch):
    monkeypatch.setattr(omnirig, '_open_com', None)
    r = omnirig.get_state({'omnirig_enabled': True})
    assert r['ok'] is False
    assert 'pywin32' in r['error']


def test_get_state_exception_com_ne_remonte_jamais(monkeypatch):
    fake = _FakeOmniRig(rig1=_FakeRig(status=omnirig.ST_ONLINE))

    class _Boom:
        def __getattr__(self, name):
            raise RuntimeError('objet COM invalide')

    _install_fake(monkeypatch, _Boom())
    r = omnirig.get_state({'omnirig_enabled': True})
    assert r == {'ok': False, 'error': 'OmniRig injoignable (objet COM invalide)'}


# ─── set_freq() / set_mode() ────────────────────────────────────────────────

def test_set_freq_ecrit_sur_le_bon_rig(monkeypatch):
    rig1 = _FakeRig(status=omnirig.ST_ONLINE)
    fake = _FakeOmniRig(rig1=rig1)
    _install_fake(monkeypatch, fake)
    r = omnirig.set_freq({'omnirig_enabled': True, 'omnirig_rig_num': 1}, 21295000)
    assert r == {'ok': True}
    assert rig1.Freq == 21295000


def test_set_freq_avec_mode_ecrit_les_deux(monkeypatch):
    rig1 = _FakeRig(status=omnirig.ST_ONLINE)
    _install_fake(monkeypatch, _FakeOmniRig(rig1=rig1))
    r = omnirig.set_freq({'omnirig_enabled': True}, 14020000, mode='cw')
    assert r == {'ok': True}
    assert rig1.Freq == 14020000
    assert rig1.Mode == omnirig.PM_CW_U


def test_set_freq_mode_inconnu_ignore_silencieusement_le_mode(monkeypatch):
    rig1 = _FakeRig(status=omnirig.ST_ONLINE, mode=omnirig.PM_AM)
    _install_fake(monkeypatch, _FakeOmniRig(rig1=rig1))
    r = omnirig.set_freq({'omnirig_enabled': True}, 3573000, mode='PLOUF')
    assert r == {'ok': True}
    assert rig1.Freq == 3573000
    assert rig1.Mode == omnirig.PM_AM  # inchangé


def test_set_freq_desactive_refuse(monkeypatch):
    monkeypatch.setattr(omnirig, '_open_com', None)
    r = omnirig.set_freq({'omnirig_enabled': False}, 14000000)
    assert r['ok'] is False


def test_set_freq_rig_hors_ligne_refuse(monkeypatch):
    _install_fake(monkeypatch, _FakeOmniRig(rig1=_FakeRig(status=omnirig.ST_PORTBUSY)))
    r = omnirig.set_freq({'omnirig_enabled': True}, 14000000)
    assert r['ok'] is False
    assert 'occupé' in r['error']


def test_set_mode_valide(monkeypatch):
    rig1 = _FakeRig(status=omnirig.ST_ONLINE)
    _install_fake(monkeypatch, _FakeOmniRig(rig1=rig1))
    r = omnirig.set_mode({'omnirig_enabled': True}, 'lsb')
    assert r == {'ok': True}
    assert rig1.Mode == omnirig.PM_SSB_L


def test_set_mode_invalide_refuse_avant_tout_appel_com(monkeypatch):
    monkeypatch.setattr(omnirig, '_open_com', None)  # ne doit jamais être appelé
    r = omnirig.set_mode({'omnirig_enabled': True}, 'BLABLA')
    assert r['ok'] is False
    assert 'BLABLA' in r['error']


# ─── set_ptt() ───────────────────────────────────────────────────────────────

def test_set_ptt_on_puis_off(monkeypatch):
    rig1 = _FakeRig(status=omnirig.ST_ONLINE)
    _install_fake(monkeypatch, _FakeOmniRig(rig1=rig1))
    r_on = omnirig.set_ptt({'omnirig_enabled': True}, True)
    assert r_on == {'ok': True}
    assert rig1.Tx == omnirig.PM_TX
    r_off = omnirig.set_ptt({'omnirig_enabled': True}, False)
    assert r_off == {'ok': True}
    assert rig1.Tx == omnirig.PM_RX


def test_set_ptt_desactive_ne_touche_jamais_com(monkeypatch):
    monkeypatch.setattr(omnirig, '_open_com', None)
    r = omnirig.set_ptt({'omnirig_enabled': False}, True)
    assert r['ok'] is False


def test_set_ptt_rig_hors_ligne_refuse(monkeypatch):
    _install_fake(monkeypatch, _FakeOmniRig(rig1=_FakeRig(status=omnirig.ST_DISABLED)))
    r = omnirig.set_ptt({'omnirig_enabled': True}, True)
    assert r['ok'] is False
    assert 'désactivé' in r['error']


# ─── test_connection() : jamais d'effet de bord matériel ───────────────────

def test_test_connection_en_ligne(monkeypatch):
    _install_fake(monkeypatch, _FakeOmniRig(rig1=_FakeRig(
        status=omnirig.ST_ONLINE, freq=50313000, rig_type='Elecraft K4')))
    r = omnirig.test_connection(1)
    assert r['ok'] is True
    assert r['device'] == 'Elecraft K4'
    assert r['freq_hz'] == 50313000


def test_test_connection_ne_bascule_jamais_le_ptt(monkeypatch):
    rig1 = _FakeRig(status=omnirig.ST_ONLINE)
    assert rig1.Tx == omnirig.PM_RX
    _install_fake(monkeypatch, _FakeOmniRig(rig1=rig1))
    omnirig.test_connection(1)
    assert rig1.Tx == omnirig.PM_RX  # test_connection n'a jamais écrit Tx


def test_test_connection_hors_ligne_message_actionnable(monkeypatch):
    _install_fake(monkeypatch, _FakeOmniRig(rig1=_FakeRig(status=omnirig.ST_NOTCONFIGURED)))
    r = omnirig.test_connection(1)
    assert r['ok'] is False
    assert 'OmniRig' in r['error']


def test_test_connection_rig_num_hors_bornes_replie_sur_1(monkeypatch):
    rig1 = _FakeRig(status=omnirig.ST_ONLINE, rig_type='Rig1Type')
    fake = _FakeOmniRig(rig1=rig1, rig2=_FakeRig(status=omnirig.ST_ONLINE, rig_type='Rig2Type'))
    _install_fake(monkeypatch, fake)
    r = omnirig.test_connection(99)
    assert r['ok'] is True
    assert r['device'] == 'Rig1Type'


# ─── _status_label() ─────────────────────────────────────────────────────────

def test_status_label_connu_et_inconnu():
    assert omnirig._status_label(omnirig.ST_ONLINE) == 'en ligne'
    assert 'inconnu' in omnirig._status_label(42)
    assert 'illisible' in omnirig._status_label('pas un entier')


# ─── auto-guérison de _com_call() après des timeouts consécutifs ──────────
# Pas de vrai sleep ici : on remplace directement _EXECUTOR par un faux
# executor dont .submit(...).result(...) lève TimeoutError immédiatement —
# simule un worker COM bloqué pour de vrai (boîte de dialogue modale
# OmniRig, port série gelé) sans attendre TIMEOUT_S + 2 secondes par appel.

class _FakeFutureTimeout:
    def result(self, timeout=None):
        raise omnirig._cf.TimeoutError()


class _FakeExecutorAlwaysTimeout:
    def submit(self, func, *args, **kwargs):
        return _FakeFutureTimeout()


def test_com_call_sous_le_seuil_ne_remplace_pas_lexecutor(monkeypatch):
    fake_executor = _FakeExecutorAlwaysTimeout()
    monkeypatch.setattr(omnirig, '_EXECUTOR', fake_executor)
    monkeypatch.setattr(omnirig, '_consecutive_timeouts', 0)

    for i in range(omnirig._TIMEOUT_THRESHOLD - 1):
        r = omnirig._com_call(1, lambda rig: {'ok': True})
        assert r['ok'] is False
        assert 'délai dépassé' in r['error']
        assert omnirig._EXECUTOR is fake_executor  # pas encore remplacé
        assert omnirig._consecutive_timeouts == i + 1


def test_com_call_atteint_le_seuil_remplace_lexecutor_et_remet_le_compteur_a_zero(monkeypatch):
    fake_executor = _FakeExecutorAlwaysTimeout()
    monkeypatch.setattr(omnirig, '_EXECUTOR', fake_executor)
    monkeypatch.setattr(omnirig, '_consecutive_timeouts', omnirig._TIMEOUT_THRESHOLD - 1)

    r = omnirig._com_call(1, lambda rig: {'ok': True})
    assert r['ok'] is False
    assert 'exécuteur neuf' in r['error']
    assert omnirig._EXECUTOR is not fake_executor  # remplacé
    assert isinstance(omnirig._EXECUTOR, omnirig._cf.ThreadPoolExecutor)
    assert omnirig._consecutive_timeouts == 0

    # le nouvel executor doit être pleinement opérationnel pour l'appel suivant
    fake = _FakeOmniRig(rig1=_FakeRig(status=omnirig.ST_ONLINE, freq=1234000))
    _install_fake(monkeypatch, fake)
    r2 = omnirig.get_state({'omnirig_enabled': True})
    assert r2['ok'] is True
    assert r2['freq_hz'] == 1234000


def test_com_call_succes_isole_remet_le_compteur_a_zero(monkeypatch):
    """Un timeout SOUS le seuil suivi d'un appel qui aboutit doit remettre le
    compteur à zéro — pas de dérive lente vers un remplacement d'executor à
    cause de timeouts isolés et non consécutifs."""
    monkeypatch.setattr(omnirig, '_EXECUTOR', _FakeExecutorAlwaysTimeout())
    monkeypatch.setattr(omnirig, '_consecutive_timeouts', 0)
    omnirig._com_call(1, lambda rig: {'ok': True})
    assert omnirig._consecutive_timeouts == 1

    monkeypatch.setattr(omnirig, '_EXECUTOR',
                         omnirig._cf.ThreadPoolExecutor(max_workers=1, thread_name_prefix='test_omnirig'))
    fake = _FakeOmniRig(rig1=_FakeRig(status=omnirig.ST_ONLINE))
    _install_fake(monkeypatch, fake)
    r = omnirig.get_state({'omnirig_enabled': True})
    assert r['ok'] is True
    assert omnirig._consecutive_timeouts == 0


def test_com_call_echec_propre_non_timeout_remet_aussi_le_compteur_a_zero(monkeypatch):
    """Un rig hors ligne (échec 'propre', pas un timeout) prouve que le
    worker répond : le compteur de timeouts consécutifs doit être remis à
    zéro, pas seulement sur un succès complet ('ok': True)."""
    monkeypatch.setattr(omnirig, '_consecutive_timeouts', omnirig._TIMEOUT_THRESHOLD - 1)
    _install_fake(monkeypatch, _FakeOmniRig(rig1=_FakeRig(status=omnirig.ST_NOTRESPONDING)))
    r = omnirig.get_state({'omnirig_enabled': True})
    assert r['ok'] is False
    assert omnirig._consecutive_timeouts == 0


# ─── _do_com_call() : robustesse pythoncom absent (CI non-Windows) ─────────

def test_do_com_call_fonctionne_sans_pythoncom_installe(monkeypatch):
    """Sur la CI (Ubuntu), `import pythoncom` échoue toujours — le module ne
    doit pas planter pour autant tant que `_open_com` est injecté."""
    fake = _FakeOmniRig(rig1=_FakeRig(status=omnirig.ST_ONLINE, freq=1000000))
    _install_fake(monkeypatch, fake)
    result = omnirig._do_com_call(1, lambda rig: {'ok': True, 'freq': rig.Freq})
    assert result == {'ok': True, 'freq': 1000000}


def test_open_com_none_sans_pywin32_get_state_message_clair():
    # Ne patche RIEN : si pywin32 n'est pas installé dans cet environnement
    # de test (cas normal sous Linux/CI), _open_com doit valoir None.
    if omnirig.HAS_PYWIN32:
        return  # environnement avec pywin32 réellement installé : rien à vérifier ici
    assert omnirig._open_com is None
    r = omnirig.get_state({'omnirig_enabled': True})
    assert r['ok'] is False
    assert 'pywin32' in r['error']
