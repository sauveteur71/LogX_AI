# -*- coding: utf-8 -*-
"""Suivi rotor d'un passage satellite : chaque sécurité prouvée.

CE QUE CE FICHIER TESTE EN PRIORITÉ : les protections MATÉRIELLES et le motif
anti-verrou-fantôme, parce qu'un défaut ici ne casse pas un affichage — il use
une mécanique, immobilise une antenne, ou bloque le suivi jusqu'au redémarrage.
Le verrou fantôme du téléchargement a été corrigé HIER (logx_update, f54dbb8) ;
ce module applique le même motif dès la conception, et ces tests vérifient
qu'il y est vraiment.

Le rotor est un FAUX qui enregistre chaque consigne : on vérifie ce qui part
réellement vers la mécanique, pas un état intermédiaire.
"""
import os
import sys
import time

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CONCOURS not in sys.path:
    sys.path.insert(0, CONCOURS)

import logx_sat_track as st   # noqa: E402
from logx_utils import utcnow


class FauxRotor:
    """Enregistre les consignes. Peut être rendu muet (panne)."""

    def __init__(self):
        self.consignes = []       # [(az, el)]
        self.stops = 0
        self.panne = False

    def set_position(self, host, port, az, el=0):
        if self.panne:
            return {'ok': False, 'error': 'rotctld injoignable (panne simulée)'}
        self.consignes.append((round(float(az), 1), round(float(el), 1)))
        return {'ok': True, 'azimuth': round(float(az), 1),
                'elevation': round(float(el), 1)}

    def get_position(self, host, port):
        if self.panne:
            return {'ok': False, 'error': 'rotctld injoignable (panne simulée)'}
        az, el = self.consignes[-1] if self.consignes else (0.0, 0.0)
        return {'ok': True, 'azimuth': az, 'elevation': el}

    def stop(self, host, port):
        self.stops += 1
        return {'ok': True}


class FauxCiel:
    """Séquence de positions satellite : chaque appel à position() consomme la
    suivante (la dernière se répète). Simule un passage sans attendre le vrai
    ciel ni dépendre d'un TLE."""

    def __init__(self, sequence):
        self.seq = list(sequence)
        self.i = 0

    def position(self, cache, nom, lat, lon, alt=0, quand=None):
        p = self.seq[min(self.i, len(self.seq) - 1)]
        self.i += 1
        if p is None:
            return {'available': False, 'error': 'position indisponible (test)'}
        az, el = p
        return {'available': True, 'az': az, 'el': el, 'visible': el > 0,
                'distance_km': 1000.0, 'range_rate_ms': 0.0}


@pytest.fixture(autouse=True)
def _etat_neuf(monkeypatch):
    monkeypatch.setattr(st, '_track', {
        'actif': False, 'sat': '', 'phase': 'inactif', 'message': '',
        'cible_az': None, 'cible_el': None, 'rotor_az': None, 'rotor_el': None,
        'envois': 0, 'visible': False,
    })
    monkeypatch.setattr(st, '_track_thread', None)
    monkeypatch.setattr(st, '_stop_courant', None)
    yield
    st.arreter_suivi()
    t = st._track_thread
    if t is not None and hasattr(t, 'join') and t.is_alive():
        t.join(timeout=10)
        assert not t.is_alive(), 'boucle de suivi trainarde'


def _rotor(monkeypatch):
    faux = FauxRotor()
    monkeypatch.setattr(st.rotor, 'set_position', faux.set_position)
    monkeypatch.setattr(st.rotor, 'get_position', faux.get_position)
    monkeypatch.setattr(st.rotor, 'stop', faux.stop)
    return faux


def _ciel(monkeypatch, sequence):
    faux = FauxCiel(sequence)
    monkeypatch.setattr(st.sp, 'position', faux.position)
    return faux


def _lancer(sequence, monkeypatch, cadence=0.01, duree_max=30,
            deadband=st.DEADBAND_DEG):
    """Exécute la boucle DANS le thread de test (déterministe), avec un faux
    ciel et un faux rotor."""
    import threading as _th
    rotor = _rotor(monkeypatch)
    _ciel(monkeypatch, sequence)
    ev = _th.Event()
    st._track.update(actif=True, sat='FAUX-1', phase='attente')
    st._boucle_suivi('FAUX-1', 'h', 1, 45.0, 4.0, 0, {'tle': {}}, ev,
                     cadence_s=cadence, duree_max_s=duree_max,
                     deadband_deg=deadband)
    return rotor


# ─── Le passage nominal ─────────────────────────────────────────────────────

def test_un_passage_complet_suit_puis_s_arrete_au_LOS(monkeypatch):
    """Montée 10°→60°, descente, LOS : le rotor reçoit des consignes pendant
    la partie visible, puis stop() au LOS, et l'état finit 'fini'."""
    seq = [(180, 10), (185, 25), (190, 45), (195, 60), (200, 45),
           (205, 20), (210, 5), (215, -2)]
    rotor = _lancer(seq, monkeypatch)
    assert rotor.consignes, 'aucune consigne envoyée pendant le passage'
    assert rotor.stops >= 1, 'le rotor n\'a pas été stoppé au LOS'
    etat = st.etat_suivi()
    assert etat['actif'] is False
    assert etat['phase'] == 'fini'
    assert 'LOS' in etat['message']


def test_JAMAIS_d_elevation_negative_envoyee(monkeypatch):
    """La consigne d'élévation est clampée ≥ 0 quoi que dise l'éphéméride —
    un rotor commandé sous l'horizon force sur sa butée mécanique."""
    seq = [(180, 30), (185, 0.4), (190, -3)]
    rotor = _lancer(seq, monkeypatch, deadband=0.1)
    for az, el in rotor.consignes:
        assert el >= 0, rotor.consignes


# ─── La bande morte protège la mécanique ────────────────────────────────────

def test_la_bande_morte_evite_les_micro_corrections(monkeypatch):
    """Dix positions à moins de 4° d'écart : UNE seule consigne doit partir.
    Corriger au demi-degré n'apporte rien en radio (lobe d'une Yagi VHF/UHF en
    dizaines de degrés) et use la mécanique."""
    seq = [(180.0 + i * 0.3, 30.0 + i * 0.2) for i in range(10)] + [(183, -1)]
    rotor = _lancer(seq, monkeypatch)
    assert len(rotor.consignes) == 1, rotor.consignes


def test_un_vrai_deplacement_traverse_la_bande_morte(monkeypatch):
    seq = [(180, 30), (190, 40), (183, -1)]
    rotor = _lancer(seq, monkeypatch)
    assert len(rotor.consignes) == 2, rotor.consignes


def test_l_ecart_d_azimut_passe_par_le_plus_court_chemin():
    """|359° − 1°| vaut 2°, pas 358° : sans le modulo, un passage traversant
    le nord commanderait un tour complet à chaque itération."""
    assert st.ecart_azimut(359, 1) == 2
    assert st.ecart_azimut(1, 359) == 2
    assert st.ecart_azimut(0, 180) == 180
    assert st.ecart_azimut(90, 90) == 0
    assert st.ecart_azimut('a', 1) is None


def test_un_passage_traversant_le_nord_ne_commande_pas_de_tour_complet(monkeypatch):
    """358° → 2° : l'écart réel est 4°, dans la bande morte à 4,5 — aucune
    nouvelle consigne ne doit partir."""
    seq = [(358, 30), (2, 32), (5, -1)]
    rotor = _lancer(seq, monkeypatch, deadband=4.5)
    assert len(rotor.consignes) == 1, rotor.consignes


# ─── Les arrêts de sécurité ─────────────────────────────────────────────────

def test_la_duree_maximale_arrete_le_suivi(monkeypatch):
    """Un satellite qui resterait « visible » pour toujours (éphéméride
    aberrante) ne doit pas faire tourner la boucle sans fin."""
    seq = [(180, 30)] * 10000
    rotor = _lancer(seq, monkeypatch, cadence=0.001, duree_max=0.05)
    etat = st.etat_suivi()
    assert etat['phase'] == 'fini'
    assert 'maximale' in etat['message']
    assert rotor.stops >= 1


def test_trois_echecs_rotor_consecutifs_arretent_avec_message(monkeypatch):
    """rotctld tombé en plein passage : on n'insiste pas indéfiniment contre
    un boîtier muet."""
    rotor = _rotor(monkeypatch)
    rotor.panne = True
    _ciel(monkeypatch, [(180 + i * 10, 30) for i in range(50)])
    import threading as _th
    st._track.update(actif=True, sat='FAUX-1')
    st._boucle_suivi('FAUX-1', 'h', 1, 45.0, 4.0, 0, {'tle': {}}, _th.Event(),
                     cadence_s=0.01, duree_max_s=30)
    etat = st.etat_suivi()
    assert etat['phase'] == 'erreur'
    assert 'injoignable' in etat['message']


def test_l_arret_demande_stoppe_le_rotor(monkeypatch):
    rotor = _rotor(monkeypatch)
    _ciel(monkeypatch, [(180, 30)] * 1000)
    import threading as _th
    ev = _th.Event()
    ev.set()
    st._track.update(actif=True, sat='FAUX-1')
    st._boucle_suivi('FAUX-1', 'h', 1, 45.0, 4.0, 0, {'tle': {}}, ev,
                     cadence_s=0.01, duree_max_s=30)
    etat = st.etat_suivi()
    assert etat['phase'] == 'fini'
    assert rotor.stops >= 1


def test_une_ephemeride_indisponible_pose_un_etat_terminal(monkeypatch):
    rotor = _lancer([(180, 30), None], monkeypatch)
    etat = st.etat_suivi()
    assert etat['phase'] == 'erreur'
    assert rotor.stops >= 1


def test_une_exception_dans_le_corps_pose_TOUJOURS_un_etat_terminal(monkeypatch):
    """Le filet extérieur — la leçon du verrou fantôme appliquée ici. Sans
    lui, une exception laisserait actif=True à jamais."""
    _rotor(monkeypatch)

    def boum(*a, **k):
        raise RuntimeError('exception arbitraire (test)')
    import threading as _th
    monkeypatch.setattr(st.sp, 'position', boum)
    st._track.update(actif=True, sat='FAUX-1')
    st._boucle_suivi('FAUX-1', 'h', 1, 45.0, 4.0, 0, {'tle': {}}, _th.Event(),
                     cadence_s=0.01, duree_max_s=30)
    etat = st.etat_suivi()
    assert etat['actif'] is False
    assert etat['phase'] == 'erreur'
    assert 'interrompu' in etat['message']


# ─── Le pré-pointage ────────────────────────────────────────────────────────

def test_sous_l_horizon_on_pre_pointe_l_azimut_de_LEVER(monkeypatch):
    """Le satellite est à l'azimut 100° SOUS l'horizon, il se lèvera à 250° :
    l'antenne doit aller à 250° (là où il apparaîtra), pas à 100°."""
    rotor = _rotor(monkeypatch)
    _ciel(monkeypatch, [(100, -20), (100, -15), (250, 2), (255, 10), (260, -1)])
    monkeypatch.setattr(st.sp, 'prochain_passage', lambda *a, **k: {
        'available': True,
        'passage': {'aos_utc': '2026-08-01 10:00:00', 'az_aos': 250.0,
                    'az_los': 30.0, 'el_max': 40.0, 'duree_s': 600,
                    'tca_utc': '', 'los_utc': ''}})
    import threading as _th
    st._track.update(actif=True, sat='FAUX-1')
    st._boucle_suivi('FAUX-1', 'h', 1, 45.0, 4.0, 0, {'tle': {}}, _th.Event(),
                     cadence_s=0.01, duree_max_s=30)
    assert rotor.consignes[0] == (250.0, 0.0), rotor.consignes


# ─── demarrer_suivi : refus synchrones et anti-orphelin ─────────────────────

CFG = {'rotor_enabled': True, 'rotor_host': '127.0.0.1', 'rotor_port': 4533,
       'locator': 'JN15XC', 'altitude': 0}


def _prets(monkeypatch, visible=True):
    rotor = _rotor(monkeypatch)
    monkeypatch.setattr(st.sp, 'charger_tle',
                        lambda *a, **k: {'recupere': 'x', 'tle': {'FAUX-1': ['1 ', '2 ']}})
    monkeypatch.setattr(st.sp, 'position', lambda *a, **k: {
        'available': True, 'az': 180.0, 'el': 30.0 if visible else -30.0,
        'visible': visible, 'distance_km': 900.0, 'range_rate_ms': 0.0})
    return rotor


def test_refus_si_rotor_desactive(monkeypatch):
    ok, msg = st.demarrer_suivi('FAUX-1', dict(CFG, rotor_enabled=False))
    assert ok is False and 'CONFIG' in msg


def test_refus_si_locator_absent(monkeypatch):
    _prets(monkeypatch)
    ok, msg = st.demarrer_suivi('FAUX-1', dict(CFG, locator=''))
    assert ok is False and 'ocator' in msg


def test_refus_si_pas_de_TLE(monkeypatch):
    _rotor(monkeypatch)
    monkeypatch.setattr(st.sp, 'charger_tle', lambda *a, **k: None)
    ok, msg = st.demarrer_suivi('FAUX-1', CFG)
    assert ok is False and 'TLE' in msg


def test_refus_si_satellite_inconnu(monkeypatch):
    _rotor(monkeypatch)
    monkeypatch.setattr(st.sp, 'charger_tle', lambda *a, **k: {'tle': {}})
    monkeypatch.setattr(st.sp, 'position',
                        lambda *a, **k: {'available': False, 'error': 'Satellite inconnu du jeu TLE : X'})
    ok, msg = st.demarrer_suivi('X', CFG)
    assert ok is False and 'inconnu' in msg


def test_refus_si_le_passage_est_trop_lointain(monkeypatch):
    """Un rotor immobilisé « en attente » pendant des heures est un piège :
    l'opérateur oublie le suivi et cherche pourquoi son antenne ne répond
    plus. Refus avec l'heure du passage — il sait quand revenir."""
    import datetime
    _prets(monkeypatch, visible=False)
    aos = utcnow() + datetime.timedelta(hours=3)
    monkeypatch.setattr(st.sp, 'prochain_passage', lambda *a, **k: {
        'available': True,
        'passage': {'aos_utc': aos.strftime('%Y-%m-%d %H:%M:%S'),
                    'az_aos': 250.0, 'az_los': 30.0, 'el_max': 40.0,
                    'duree_s': 600, 'tca_utc': '', 'los_utc': ''}})
    ok, msg = st.demarrer_suivi('FAUX-1', CFG)
    assert ok is False
    assert aos.strftime('%H:%M') in msg


def test_accepte_si_le_passage_est_proche(monkeypatch):
    import datetime
    _prets(monkeypatch, visible=False)
    aos = utcnow() + datetime.timedelta(minutes=5)
    monkeypatch.setattr(st.sp, 'prochain_passage', lambda *a, **k: {
        'available': True,
        'passage': {'aos_utc': aos.strftime('%Y-%m-%d %H:%M:%S'),
                    'az_aos': 250.0, 'az_los': 30.0, 'el_max': 40.0,
                    'duree_s': 600, 'tca_utc': '', 'los_utc': ''}})
    ok, msg = st.demarrer_suivi('FAUX-1', CFG)
    assert ok is True, msg
    st.arreter_suivi()


def test_refus_si_le_rotor_ne_repond_pas(monkeypatch):
    rotor = _prets(monkeypatch)
    rotor.panne = True
    ok, msg = st.demarrer_suivi('FAUX-1', CFG)
    assert ok is False and 'injoignable' in msg


def test_un_suivi_VIVANT_refuse_le_second(monkeypatch):
    _prets(monkeypatch)
    ok, msg = st.demarrer_suivi('FAUX-1', CFG)
    assert ok is True, msg
    ok2, msg2 = st.demarrer_suivi('FAUX-1', CFG)
    assert ok2 is False and 'déjà en cours' in msg2
    st.arreter_suivi()


def test_un_suivi_ORPHELIN_est_gueri_et_le_second_part(monkeypatch):
    """Le motif anti-verrou-fantôme : actif=True sans thread vivant est un
    cadavre — il ne doit JAMAIS bloquer le suivi jusqu'au redémarrage."""
    _prets(monkeypatch)
    st._track['actif'] = True
    st._track_thread = None
    ok, msg = st.demarrer_suivi('FAUX-1', CFG)
    assert ok is True, msg
    st.arreter_suivi()


# ─── L'état est JSON-safe ───────────────────────────────────────────────────

def test_l_etat_est_serialisable_JSON(monkeypatch):
    """Il part tel quel dans /data/sat : un objet Thread qui s'y glisserait
    casserait l'endpoint entier."""
    import json
    _prets(monkeypatch)
    ok, _ = st.demarrer_suivi('FAUX-1', CFG)
    assert ok
    json.dumps(st.etat_suivi())   # ne doit pas lever
    st.arreter_suivi()


# ─── Les correctifs de la revue adversariale (01/08/2026) ───────────────────
# 16 constats confirmés par des vérificateurs indépendants ; chacun de ceux qui
# touchent la boucle est reproduit ici.

def test_un_stop_RETARDE_ne_tue_pas_le_suivi_suivant(monkeypatch):
    """Constat SAT-TRACK-2. L'Event d'arrêt est PAR SUIVI : un POST d'arrêt
    retardé (multi-op, pile réseau lente) émis pour le suivi N ne doit pas
    tuer le suivi N+1 — sur une expédition, l'orbite ratée ne repasse pas
    avant des heures."""
    _prets(monkeypatch)
    ok, _ = st.demarrer_suivi('FAUX-1', CFG)
    assert ok
    ancien_ev = st._stop_courant
    st.arreter_suivi()
    t = st._track_thread
    t.join(timeout=10)
    assert not t.is_alive()

    ok, msg = st.demarrer_suivi('FAUX-1', CFG)
    assert ok, msg
    # Le stop RETARDÉ arrive maintenant, visant l'ANCIEN suivi.
    ancien_ev.set()
    time.sleep(0.2)
    assert st.etat_suivi()['actif'] is True, (
        'le stop retardé du suivi précédent a tué le suivi courant')
    st.arreter_suivi()


def test_aucune_consigne_POSTHUME_apres_l_arret(monkeypatch):
    """Constat SAT-TRACK-3. Un stop posé pendant le calcul du tour ne doit pas
    laisser partir une dernière consigne après « Arrêté par l'opérateur »."""
    import threading as _th
    rotor = _rotor(monkeypatch)
    ev = _th.Event()

    class CielQuiArrete:
        """Pose le stop PENDANT le calcul de position — la fenêtre exacte du
        constat : entre la vérification de tête de tour et l'envoi."""
        def __init__(self):
            self.n = 0

        def position(self, *a, **k):
            self.n += 1
            if self.n == 2:
                ev.set()
            return {'available': True, 'az': 100.0 + self.n * 20, 'el': 30.0,
                    'visible': True, 'distance_km': 900.0, 'range_rate_ms': 0.0}

    monkeypatch.setattr(st.sp, 'position', CielQuiArrete().position)
    st._track.update(actif=True, sat='FAUX-1')
    st._boucle_suivi('FAUX-1', 'h', 1, 45.0, 4.0, 0, {'tle': {}}, ev,
                     cadence_s=0.01, duree_max_s=30)
    # Tour 1 : consigne envoyée. Tour 2 : le stop tombe pendant position() —
    # la consigne du tour 2 ne doit PAS partir.
    assert len(rotor.consignes) == 1, rotor.consignes
    assert st.etat_suivi()['phase'] == 'fini'


def test_l_arret_reveille_la_boucle_SANS_attendre_la_cadence(monkeypatch):
    """Constat SAT-TRACK-3 (second volet). La boucle dort sur l'Event, pas sur
    une horloge : avec une cadence d'UNE HEURE, l'arrêt doit quand même être
    immédiat."""
    import threading as _th
    _rotor(monkeypatch)
    _ciel(monkeypatch, [(180, 30)] * 1000)
    ev = _th.Event()
    fini = _th.Event()

    def _run():
        st._boucle_suivi('FAUX-1', 'h', 1, 45.0, 4.0, 0, {'tle': {}}, ev,
                         cadence_s=3600, duree_max_s=7200)
        fini.set()

    t = _th.Thread(target=_run, daemon=True)
    st._track.update(actif=True, sat='FAUX-1')
    t.start()
    time.sleep(0.3)          # la boucle a fait son 1er tour et dort (1 h)
    debut = time.monotonic()
    ev.set()
    assert fini.wait(timeout=5), "la boucle n'est pas sortie de sa dormance"
    assert time.monotonic() - debut < 2.0, "l'arrêt a attendu la cadence"
    t.join(timeout=5)


def test_le_grand_tour_au_nord_est_SIGNALE(monkeypatch):
    """Constat SAT-1. La consigne brute saute de plus de 180° : un rotor sans
    chevauchement fait un tour complet — on ne peut pas l'empêcher, on le DIT."""
    seq = [(350, 30), (10, 40), (15, -1)]
    _lancer(seq, monkeypatch, deadband=4.0)
    assert 'tour complet' in (st.etat_suivi().get('note') or ''), st.etat_suivi()


def test_les_NaN_du_rotor_ne_partent_pas_dans_le_JSON(monkeypatch):
    """Constat C3. rotctld peut répondre « nan » ; float('nan') parse sans
    erreur et casserait le client JSON. On ne publie que du fini.

    Ce test vise UNIQUEMENT le filtrage synchrone fait par demarrer_suivi()
    avant de lancer le thread — pas le comportement de la boucle. `_boucle_
    suivi` est donc neutralisée : sans ça, le vrai thread démarré par
    demarrer_suivi() peut faire son premier tour (calculer la cible depuis
    sp.position, 180.0 ici) et écraser rotor_az=None par cette valeur AVANT
    que ce test relise l'état — une course gagnée localement (le thread n'a
    pas eu le temps de tourner) mais perdue sur un runner CI plus chargé.
    Constatée en CI le 06/08/2026 : assert (180.0 is None)."""
    import json
    _rotor(monkeypatch)
    monkeypatch.setattr(st.rotor, 'get_position',
                        lambda h, p: {'ok': True, 'azimuth': float('nan'),
                                      'elevation': float('inf')})
    monkeypatch.setattr(st.sp, 'charger_tle',
                        lambda *a, **k: {'recupere': 'x',
                                         'tle': {'FAUX-1': ['1 ', '2 ']}})
    monkeypatch.setattr(st.sp, 'position', lambda *a, **k: {
        'available': True, 'az': 180.0, 'el': 30.0, 'visible': True,
        'distance_km': 900.0, 'range_rate_ms': 0.0})
    monkeypatch.setattr(st, '_boucle_suivi', lambda *a, **k: None)
    ok, msg = st.demarrer_suivi('FAUX-1', CFG)
    assert ok, msg
    etat = st.etat_suivi()
    assert etat['rotor_az'] is None and etat['rotor_el'] is None
    json.dumps(etat, allow_nan=False)   # lèverait sur NaN/inf
    st.arreter_suivi()


def test_la_position_rotor_affichee_est_RELUE_pas_l_echo(monkeypatch):
    """Constats SAT-2/C5. set_position ne renvoie qu'un écho de la consigne ;
    la boucle RELIT la vraie position tous les TOURS_ENTRE_LECTURES tours et
    publie CETTE mesure — un rotor à la traîne devient visible."""
    import threading as _th

    class RotorALaTraine(FauxRotor):
        def get_position(self, host, port):
            # La mécanique est LOIN de la dernière consigne.
            return {'ok': True, 'azimuth': 42.0, 'elevation': 7.0}

    rotor = RotorALaTraine()
    monkeypatch.setattr(st.rotor, 'set_position', rotor.set_position)
    monkeypatch.setattr(st.rotor, 'get_position', rotor.get_position)
    monkeypatch.setattr(st.rotor, 'stop', rotor.stop)
    # Assez de tours visibles pour dépasser TOURS_ENTRE_LECTURES.
    seq = ([(180 + i, 30) for i in range(st.TOURS_ENTRE_LECTURES + 2)]
           + [(200, -1)])
    _ciel(monkeypatch, seq)
    st._track.update(actif=True, sat='FAUX-1')
    st._boucle_suivi('FAUX-1', 'h', 1, 45.0, 4.0, 0, {'tle': {}}, _th.Event(),
                     cadence_s=0.01, duree_max_s=30)
    etat = st.etat_suivi()
    assert etat['rotor_az'] == 42.0 and etat['rotor_el'] == 7.0, (
        "la position affichée est encore l'écho de la consigne, pas la mesure")


def test_la_duree_max_est_dimensionnee_par_le_passage(monkeypatch):
    """Constat SAT-3. Suivi lancé avant un passage dont le LOS est au-delà du
    forfait de 45 min : la durée max doit couvrir le passage (+ marge), pas le
    couper en plein vol."""
    import datetime
    captures = {}
    _prets(monkeypatch, visible=False)
    los = utcnow() + datetime.timedelta(minutes=70)
    aos = utcnow() + datetime.timedelta(minutes=5)
    monkeypatch.setattr(st.sp, 'prochain_passage', lambda *a, **k: {
        'available': True,
        'passage': {'aos_utc': aos.strftime('%Y-%m-%d %H:%M:%S'),
                    'los_utc': los.strftime('%Y-%m-%d %H:%M:%S'),
                    'az_aos': 250.0, 'az_los': 30.0, 'el_max': 40.0,
                    'duree_s': 600, 'tca_utc': ''}})

    def espion(*args, **kwargs):
        captures['duree_max_s'] = kwargs.get('duree_max_s')
        # Ne pas lancer la vraie boucle : on ne teste que le dimensionnement.
        st._fin('fini', 'espion')

    monkeypatch.setattr(st, '_boucle_suivi', espion)
    ok, msg = st.demarrer_suivi('FAUX-1', CFG)
    assert ok, msg
    st._track_thread.join(timeout=5)
    # ~70 min de LOS + 10 min de marge > forfait de 45 min.
    assert captures['duree_max_s'] > st.DUREE_MAX_S, captures
    assert captures['duree_max_s'] <= 4 * 3600
