# -*- coding: utf-8 -*-
"""Suivi rotor de la Lune : chaque sécurité prouvée, rotor et Lune SIMULÉS.

Le rotor réel n'est pas testable côté agent : le faux enregistre les consignes,
on vérifie ce qui part réellement vers la mécanique. La Lune est une séquence de
positions (az, alt) — pas d'attente du vrai ciel ni d'ephem."""
import os
import sys

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CONCOURS not in sys.path:
    sys.path.insert(0, CONCOURS)

import logx_moon_track as mt   # noqa: E402


def test_ecart_azimut_passe_par_le_plus_court_chemin():
    assert mt.ecart_azimut(359, 1) == 2
    assert mt.ecart_azimut(1, 359) == 2
    assert mt.ecart_azimut(0, 180) == 180
    assert mt.ecart_azimut(90, 90) == 0
    assert mt.ecart_azimut('a', 1) is None


class FauxRotor:
    """Enregistre les consignes. Peut être rendu muet (panne)."""
    def __init__(self):
        self.consignes = []
        self.stops = 0
        self.panne = False

    def set_position(self, host, port, az, el=0, proto='rotctld'):
        if self.panne:
            return {'ok': False, 'error': 'rotctld injoignable (panne simulée)'}
        self.consignes.append((round(float(az), 1), round(float(el), 1)))
        return {'ok': True, 'azimuth': round(float(az), 1), 'elevation': round(float(el), 1)}

    def get_position(self, host, port, proto='rotctld'):
        if self.panne:
            return {'ok': False, 'error': 'rotctld injoignable (panne simulée)'}
        az, el = self.consignes[-1] if self.consignes else (0.0, 0.0)
        return {'ok': True, 'azimuth': az, 'elevation': el}

    def stop(self, host, port, proto='rotctld'):
        self.stops += 1
        return {'ok': True}


class FauxLune:
    """Séquence de positions lunaires (az, alt) ; None = indisponible. La
    dernière se répète."""
    def __init__(self, sequence):
        self.seq = list(sequence)
        self.i = 0

    def moon_position(self, lat, lon, elevation_m=0, when=None):
        p = self.seq[min(self.i, len(self.seq) - 1)]
        self.i += 1
        if p is None:
            return {'available': False, 'error': 'position indisponible (test)'}
        az, alt = p
        return {'available': True, 'az': az, 'alt': alt, 'visible': alt > 0,
                'distance_km': 384000.0, 'phase_pct': 50.0}


@pytest.fixture(autouse=True)
def _etat_neuf(monkeypatch):
    monkeypatch.setattr(mt, '_track', {
        'actif': False, 'phase': 'inactif', 'message': '', 'note': '',
        'cible_az': None, 'cible_el': None, 'rotor_az': None, 'rotor_el': None,
        'envois': 0, 'visible': False,
    })
    monkeypatch.setattr(mt, '_track_thread', None)
    monkeypatch.setattr(mt, '_stop_courant', None)
    yield


def _rotor(monkeypatch):
    faux = FauxRotor()
    monkeypatch.setattr(mt.rotor, 'set_position', faux.set_position)
    monkeypatch.setattr(mt.rotor, 'get_position', faux.get_position)
    monkeypatch.setattr(mt.rotor, 'stop', faux.stop)
    return faux


def _lune(monkeypatch, sequence):
    faux = FauxLune(sequence)
    monkeypatch.setattr(mt.eme, 'moon_position', faux.moon_position)
    return faux


def _lancer(sequence, monkeypatch, cadence=0.01, duree_max=30, deadband=mt.DEADBAND_DEG):
    """Exécute la boucle DANS le thread de test (déterministe)."""
    import threading as _th
    rot = _rotor(monkeypatch)
    _lune(monkeypatch, sequence)
    ev = _th.Event()
    mt._track.update(actif=True, phase='suivi')
    mt._boucle_suivi_lune('h', 1, 45.0, 4.0, 0, ev,
                          cadence_s=cadence, duree_max_s=duree_max, deadband_deg=deadband)
    return rot


def test_suit_la_lune_puis_s_arrete_au_coucher(monkeypatch):
    # Montée puis descente sous l'horizon.
    seq = [(180, 10), (185, 25), (200, 45), (215, 20), (230, -2)]
    rot = _lancer(seq, monkeypatch)
    assert rot.consignes, 'aucune consigne pendant la visibilité'
    assert rot.stops >= 1, 'rotor non stoppé au coucher'
    etat = mt.etat_suivi_lune()
    assert etat['actif'] is False
    assert etat['phase'] == 'fini'
    assert 'couch' in etat['message'].lower()


def test_jamais_d_elevation_negative_envoyee(monkeypatch):
    seq = [(180, 30), (185, 0.4), (190, -3)]
    rot = _lancer(seq, monkeypatch, deadband=0.1)
    for az, el in rot.consignes:
        assert el >= 0, rot.consignes


def test_la_bande_morte_evite_les_micro_corrections(monkeypatch):
    seq = [(180.0 + i * 0.3, 30.0 + i * 0.2) for i in range(10)] + [(183, -1)]
    rot = _lancer(seq, monkeypatch)
    assert len(rot.consignes) == 1, rot.consignes


def test_un_vrai_deplacement_traverse_la_bande_morte(monkeypatch):
    seq = [(180, 30), (190, 40), (183, -1)]
    rot = _lancer(seq, monkeypatch)
    assert len(rot.consignes) == 2, rot.consignes


def test_le_passage_au_nord_est_signale(monkeypatch):
    seq = [(350, 30), (10, 40), (15, -1)]
    _lancer(seq, monkeypatch, deadband=4.0)
    assert 'tour complet' in (mt.etat_suivi_lune().get('note') or ''), mt.etat_suivi_lune()


def test_la_duree_maximale_arrete_le_suivi(monkeypatch):
    seq = [(180, 30)] * 10000
    rot = _lancer(seq, monkeypatch, cadence=0.001, duree_max=0.05)
    etat = mt.etat_suivi_lune()
    assert etat['phase'] == 'fini'
    assert 'maximale' in etat['message']
    assert rot.stops >= 1


def test_trois_echecs_rotor_consecutifs_arretent_avec_message(monkeypatch):
    import threading as _th
    rot = _rotor(monkeypatch)
    rot.panne = True
    _lune(monkeypatch, [(180 + i * 10, 30) for i in range(50)])
    mt._track.update(actif=True)
    mt._boucle_suivi_lune('h', 1, 45.0, 4.0, 0, _th.Event(), cadence_s=0.01, duree_max_s=30)
    etat = mt.etat_suivi_lune()
    assert etat['phase'] == 'erreur'
    assert 'injoignable' in etat['message']


def test_une_ephemeride_indisponible_pose_un_etat_terminal(monkeypatch):
    rot = _lancer([(180, 30), None], monkeypatch)
    etat = mt.etat_suivi_lune()
    assert etat['phase'] == 'erreur'
    assert rot.stops >= 1


def test_une_exception_dans_le_corps_pose_TOUJOURS_un_etat_terminal(monkeypatch):
    import threading as _th
    _rotor(monkeypatch)

    def boum(*a, **k):
        raise RuntimeError('exception arbitraire (test)')
    monkeypatch.setattr(mt.eme, 'moon_position', boum)
    mt._track.update(actif=True)
    mt._boucle_suivi_lune('h', 1, 45.0, 4.0, 0, _th.Event(), cadence_s=0.01, duree_max_s=30)
    etat = mt.etat_suivi_lune()
    assert etat['actif'] is False
    assert etat['phase'] == 'erreur'
    assert 'interrompu' in etat['message']


def test_l_etat_est_serialisable_JSON(monkeypatch):
    import json
    _lancer([(180, 30), (185, -1)], monkeypatch)
    json.dumps(mt.etat_suivi_lune(), allow_nan=False)   # ne doit pas lever


CFG = {'rotor_enabled': True, 'rotor_host': '127.0.0.1', 'rotor_port': 4533,
       'locator': 'JN15XC', 'altitude': 0}


def _prets(monkeypatch, visible=True):
    rot = _rotor(monkeypatch)
    monkeypatch.setattr(mt.eme, 'HAS_EPHEM', True)
    monkeypatch.setattr(mt.eme, 'moon_position', lambda lat, lon, alt=0, when=None: {
        'available': True, 'az': 180.0, 'alt': 30.0 if visible else -30.0,
        'visible': visible, 'distance_km': 384000.0, 'phase_pct': 50.0})
    monkeypatch.setattr(mt.eme, 'moon_rise_set', lambda lat, lon, alt=0, when=None: {
        'available': True, 'rise_utc': '2026/9/1 21:14:00', 'set_utc': '2026/9/2 06:02:00'})
    return rot


def test_refus_si_ephem_absent(monkeypatch):
    _prets(monkeypatch)
    monkeypatch.setattr(mt.eme, 'HAS_EPHEM', False)
    ok, msg = mt.demarrer_suivi_lune(CFG)
    assert ok is False and 'ephem' in msg.lower()


def test_refus_si_rotor_desactive(monkeypatch):
    _prets(monkeypatch)
    ok, msg = mt.demarrer_suivi_lune(dict(CFG, rotor_enabled=False))
    assert ok is False and 'CONFIG' in msg


def test_refus_si_locator_absent(monkeypatch):
    _prets(monkeypatch)
    ok, msg = mt.demarrer_suivi_lune(dict(CFG, locator=''))
    assert ok is False and 'ocator' in msg


def test_refus_si_lune_sous_l_horizon_avec_heure_de_lever(monkeypatch):
    _prets(monkeypatch, visible=False)
    ok, msg = mt.demarrer_suivi_lune(CFG)
    assert ok is False
    assert '21:14' in msg   # l'heure du prochain lever, pour savoir quand revenir


def test_refus_si_rotor_ne_repond_pas(monkeypatch):
    rot = _prets(monkeypatch)
    rot.panne = True
    ok, msg = mt.demarrer_suivi_lune(CFG)
    assert ok is False and 'injoignable' in msg


def test_un_suivi_VIVANT_refuse_le_second(monkeypatch):
    _prets(monkeypatch)
    ok, msg = mt.demarrer_suivi_lune(CFG)
    assert ok is True, msg
    ok2, msg2 = mt.demarrer_suivi_lune(CFG)
    assert ok2 is False and 'déjà en cours' in msg2
    mt.arreter_suivi_lune()


def test_un_suivi_ORPHELIN_est_gueri_et_le_second_part(monkeypatch):
    _prets(monkeypatch)
    mt._track['actif'] = True
    mt._track_thread = None
    ok, msg = mt.demarrer_suivi_lune(CFG)
    assert ok is True, msg
    mt.arreter_suivi_lune()


def test_les_NaN_du_rotor_ne_partent_pas_dans_le_JSON(monkeypatch):
    import json
    _prets(monkeypatch)
    monkeypatch.setattr(mt.rotor, 'get_position',
                        lambda h, p, proto='rotctld': {'ok': True, 'azimuth': float('nan'),
                                                       'elevation': float('inf')})
    monkeypatch.setattr(mt, '_boucle_suivi_lune', lambda *a, **k: None)
    ok, msg = mt.demarrer_suivi_lune(CFG)
    assert ok, msg
    etat = mt.etat_suivi_lune()
    assert etat['rotor_az'] is None and etat['rotor_el'] is None
    json.dumps(etat, allow_nan=False)
    mt.arreter_suivi_lune()
