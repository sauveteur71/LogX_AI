# -*- coding: utf-8 -*-
"""Suivi rotor de la Lune (EME) : le fil entre l'éphéméride lunaire et l'antenne.

Calqué sur logx_sat_track.py, mais la Lune est un cas plus simple : elle bouge
~0,5°/min (pas de course au TCA, pas de pré-pointage d'un azimut de lever, pas
de TLE). logx_eme.moon_position() dit OÙ elle est, logx_rotor sait POINTER.
Toutes les sécurités de sat_track sont reprises : Event PAR suivi, auto-guérison
de l'orphelin, bande morte, échecs rotor bornés, corps enveloppé (état terminal
garanti), aucun appel réseau dans le handler HTTP (la boucle écrit _track, le
endpoint LIT).
"""
import math
import threading
import time

import logx_eme as eme
import logx_rotor as rotor
import logx_station as station
from logx_utils import locator_to_latlon

DEADBAND_DEG = 4.0
CADENCE_S = 10.0            # la Lune bouge ~0,5°/min : rafraîchir plus vite n'apporte rien
DUREE_MAX_S = 8 * 3600     # session EME longue ; plafond de sécurité (la boucle s'arrête au coucher)
ECHECS_ROTOR_MAX = 3
TOURS_ENTRE_LECTURES = 5

_lock = threading.Lock()
_stop_courant = None
_track = {
    'actif': False, 'phase': 'inactif', 'message': '', 'note': '',
    'cible_az': None, 'cible_el': None, 'rotor_az': None, 'rotor_el': None,
    'envois': 0, 'visible': False,
}
_track_thread = None


def etat_suivi_lune():
    """État courant, JSON-safe, sans aucun appel réseau."""
    with _lock:
        return dict(_track)


def ecart_azimut(a, b):
    """Écart angulaire le plus court entre deux azimuts, en degrés.
    |359° − 1°| vaut 2°, pas 358°."""
    try:
        d = abs(float(a) - float(b)) % 360.0
    except (TypeError, ValueError):
        return None
    return min(d, 360.0 - d)


def _fin(phase, message=''):
    with _lock:
        _track.update(actif=False, phase=phase, message=message)


def _boucle_suivi_lune(host, port, lat, lon, alt_m, stop_ev,
                       cadence_s=CADENCE_S, duree_max_s=DUREE_MAX_S,
                       deadband_deg=DEADBAND_DEG, offset_az=0.0, proto='rotctld'):
    """Corps enveloppé de bout en bout : quoi qu'il arrive, un état terminal est
    posé (leçon du verrou fantôme). `stop_ev` est PROPRE à ce suivi."""
    try:
        _boucle_suivi_lune_corps(host, port, lat, lon, alt_m, stop_ev,
                                 cadence_s, duree_max_s, deadband_deg, offset_az, proto)
    except Exception as e:
        try:
            rotor.stop(host, port, proto=proto)
        except Exception:
            pass
        _fin('erreur', 'Suivi interrompu : %s' % e)


def _boucle_suivi_lune_corps(host, port, lat, lon, alt_m, stop_ev,
                             cadence_s, duree_max_s, deadband_deg, offset_az, proto):
    debut = time.monotonic()
    vu_au_dessus = False
    echecs = 0
    derniere_consigne = None
    tours = 0
    lecture_az = lecture_el = None

    while True:
        if stop_ev.is_set():
            rotor.stop(host, port, proto=proto)
            _fin('fini', "Arrêté par l'opérateur.")
            return
        if time.monotonic() - debut > duree_max_s:
            rotor.stop(host, port, proto=proto)
            _fin('fini', 'Durée maximale de suivi atteinte (%d h) — arrêt '
                         'automatique.' % (duree_max_s // 3600))
            return

        pos = eme.moon_position(lat, lon, alt_m)
        if not pos.get('available'):
            rotor.stop(host, port, proto=proto)
            _fin('erreur', pos.get('error', 'Position de la Lune indisponible.'))
            return

        el = pos['alt']
        visible = el > 0
        note = ''

        if visible:
            vu_au_dessus = True
            cible_az, cible_el = pos['az'], max(0.0, el)
            phase = 'suivi'
        elif vu_au_dessus:
            rotor.stop(host, port, proto=proto)
            _fin('fini', 'Lune couchée — fin de fenêtre.')
            return
        else:
            # Défensif : le démarrage est refusé sous l'horizon, on n'attend pas.
            rotor.stop(host, port, proto=proto)
            _fin('fini', 'Lune sous l\'horizon.')
            return

        envoyer = derniere_consigne is None
        if not envoyer:
            d_az = ecart_azimut(cible_az, derniere_consigne[0])
            d_el = abs(cible_el - derniere_consigne[1])
            envoyer = (d_az is not None and d_az > deadband_deg) or d_el > deadband_deg
            if envoyer and abs(float(cible_az) - derniere_consigne[0]) > 180:
                note = ('Passage de la Lune au nord : un rotor sans '
                        'chevauchement fait un tour complet ici.')

        envoi_ok = None
        if envoyer:
            if stop_ev.is_set():
                continue
            az_envoi = station.azimut_rotor({'offset_deg': offset_az}, cible_az)
            if az_envoi is None:
                az_envoi = cible_az
            r = rotor.set_position(host, port, az_envoi, cible_el, proto=proto)
            if r.get('ok'):
                echecs = 0
                derniere_consigne = (cible_az, cible_el)
                envoi_ok = r
            else:
                echecs += 1
                if echecs >= ECHECS_ROTOR_MAX:
                    rotor.stop(host, port, proto=proto)
                    _fin('erreur', 'Rotor injoignable (%d échecs consécutifs) — %s'
                         % (echecs, r.get('error', '')))
                    return

        tours += 1
        if tours % TOURS_ENTRE_LECTURES == 0:
            lu = rotor.get_position(host, port, proto=proto)
            if lu.get('ok') and math.isfinite(lu['azimuth']) and math.isfinite(lu['elevation']):
                lecture_az, lecture_el = lu['azimuth'], lu['elevation']

        with _lock:
            maj = {'phase': phase, 'visible': visible, 'note': note,
                   'cible_az': round(float(cible_az), 1),
                   'cible_el': round(float(cible_el), 1)}
            if envoi_ok is not None:
                maj['envois'] = _track['envois'] + 1
            if lecture_az is not None:
                maj['rotor_az'], maj['rotor_el'] = lecture_az, lecture_el
            elif envoi_ok is not None:
                maj['rotor_az'] = envoi_ok['azimuth']
                maj['rotor_el'] = envoi_ok['elevation']
            _track.update(maj)

        if stop_ev.wait(cadence_s):
            continue


def demarrer_suivi_lune(cfg):
    """Démarre le suivi lunaire. (ok, message) — refus SYNCHRONES : tout ce qui
    peut être vérifié avant de lancer le thread l'est ici, pour que l'opérateur
    ait la raison sous les yeux immédiatement."""
    global _track_thread, _stop_courant

    if not eme.HAS_EPHEM:
        return False, ("Bibliothèque 'ephem' non installée (pip install ephem) — "
                       'position de la Lune indisponible.')

    rs = station.rotor_defaut(cfg, prefer_bandes=['144', '432', '1296'])
    if not rs['enabled']:
        return False, ('Rotor non activé — voir CONFIG, section rotor '
                       '(mode expert).')

    lat, lon = locator_to_latlon((cfg or {}).get('locator', '') or '')
    if lat is None:
        return False, 'Locator manquant ou invalide (page CONFIG).'
    alt_m = (cfg or {}).get('altitude', 0) or 0

    pos = eme.moon_position(lat, lon, alt_m)
    if not pos.get('available'):
        return False, pos.get('error', 'Position de la Lune indisponible.')
    if not pos.get('visible'):
        info = eme.moon_rise_set(lat, lon, alt_m)
        lever = (info.get('rise_utc') if info.get('available') else None) or '?'
        return False, ("La Lune est sous l'horizon — prochain lever : %s UTC." % lever)

    r = rotor.get_position(rs['host'], rs['port'], proto=rs.get('proto', 'rotctld'))
    if not r.get('ok'):
        return False, r.get('error', 'Rotor injoignable.')

    with _lock:
        if _track['actif']:
            if _track_thread is not None and _track_thread.is_alive():
                return False, 'Un suivi lunaire est déjà en cours.'
            _track.update(actif=False, phase='erreur',
                          message='Suivi précédent interrompu sans état terminal '
                                  '— réinitialisé automatiquement.')
        ev = threading.Event()
        t = threading.Thread(
            target=_boucle_suivi_lune,
            args=(rs['host'], rs['port'], lat, lon, alt_m, ev),
            kwargs={'duree_max_s': DUREE_MAX_S, 'offset_az': rs['offset_deg'],
                    'proto': rs.get('proto', 'rotctld')},
            daemon=True)
        _track.update(actif=True, phase='suivi', message='', note='',
                      cible_az=None, cible_el=None,
                      rotor_az=r['azimuth'] if math.isfinite(r['azimuth']) else None,
                      rotor_el=r['elevation'] if math.isfinite(r['elevation']) else None,
                      envois=0, visible=True)
        try:
            t.start()
        except Exception as e:
            _track.update(actif=False, phase='erreur',
                          message='Impossible de démarrer le suivi : %s' % e)
            _track_thread = None
            return False, 'Impossible de démarrer le suivi : %s' % e
        _track_thread = t
        _stop_courant = ev
    return True, ''


def arreter_suivi_lune():
    """Demande d'arrêt du suivi courant — la boucle s'arrête immédiatement (elle
    dort sur cet Event) et stoppe le rotor."""
    with _lock:
        ev = _stop_courant
    if ev is not None:
        ev.set()
    return True, ''
