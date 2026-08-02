# -*- coding: utf-8 -*-
"""Suivi rotor d'un passage satellite : le fil entre la prédiction et l'antenne.

CE QUI EXISTAIT DÉJÀ, et qu'il suffisait de relier : logx_sat_passes sait OÙ
est le satellite (azimut/élévation à l'instant T), logx_rotor sait POINTER
l'antenne (rotctld, azimut ET élévation). Entre les deux, l'opérateur suivait
le passage à la main — dix minutes de manivelle pendant lesquelles il ne
trafique pas.

─── LES CHOIX D'INGÉNIERIE, ET POURQUOI ────────────────────────────────────────

BANDE MORTE (deadband) : le rotor n'est commandé que si l'écart cible/dernière
consigne dépasse DEADBAND_DEG. Corriger au demi-degré n'apporte RIEN en radio —
le lobe à −3 dB d'une Yagi VHF/UHF se compte en dizaines de degrés — et use la
mécanique : relais qui cliquettent toutes les deux secondes, moteurs sollicités
en permanence pendant dix minutes. 4° par défaut : invisible pour l'antenne,
reposant pour le rotor.

CADENCE 2 s : l'ÉLÉVATION reste toujours dans la bande morte entre deux tours
(< 2°/tour mesuré). L'AZIMUT, lui, peut atteindre ~14°/s au TCA d'un passage
quasi zénithal — 27,7° entre deux tours, MESURÉ par la revue sur un passage
ISS à 86° avec le TLE réel. Une consigne part alors à chaque tour, et un rotor
réel (5-6°/s en azimut) prend du retard au plus près : c'est le cas difficile
CONNU de tout suivi satellite, pas un défaut de cette boucle — l'antenne
rattrape en quelques secondes après le TCA, et le lobe d'une Yagi couvre
l'écart transitoire. Ne pas « corriger » en accélérant la cadence : le rotor
est le facteur limitant, pas le calcul.

PASSAGE TRAVERSANT LE NORD : la consigne envoyée est l'azimut vrai 0-360.
Quand la trajectoire passe de 359° à 1°, un rotor SANS overlap fait le grand
tour (~1 min) en plein passage — limite matérielle connue. La boucle le
DÉTECTE (saut de consigne > 90° au plus court chemin… impossible ; en pratique
un écart de consigne brute > 180°) et le signale dans l'état (`note`), pour
que l'opérateur sache pourquoi son antenne fait un tour complet.

PRÉ-POINTAGE : lancé avant l'AOS, le suivi pointe immédiatement l'azimut de
LEVER du satellite, élévation 0 — un rotor peut mettre plus d'une minute à
traverser, autant le faire pendant que le satellite est encore sous l'horizon.
REFUS si le prochain passage est à plus de PREAVIS_MAX_S : un rotor immobilisé
« en attente » pendant des heures est un piège pour l'opérateur qui a oublié le
suivi et se demande pourquoi son antenne ne répond plus.

─── LES SÉCURITÉS, chacune née d'un défaut réel ────────────────────────────────

UN SEUL SUIVI, ET PAS DE VERROU FANTÔME. Même motif que le téléchargement de
mise à jour, corrigé HIER après diagnostic (logx_update, commit f54dbb8) :
référence du thread hors de l'état JSON, démarrage sous verrou d'un seul bloc,
start() sous try, et AUTO-GUÉRISON de l'orphelin (état « actif » avec un thread
mort = cadavre, remplacé). Le corps de la boucle est enveloppé de bout en
bout : QUOI QU'IL ARRIVE, un état terminal est posé.

ARRÊT AU LOS : dès que le satellite repasse sous l'horizon, stop() du rotor et
fin du suivi. Jamais d'élévation négative envoyée (set_position clampe déjà,
ceinture et bretelles).

DURÉE MAXIMALE : attente + passage + marge. Un suivi qui tourne au-delà est un
défaut, pas un service — même philosophie que le désarmement du Wait & Pounce.

ÉCHECS ROTOR BORNÉS : trois échecs consécutifs (rotctld tombé, câble) → arrêt
avec message. Jamais de boucle infinie d'erreurs contre un boîtier muet.

AUCUN APPEL RÉSEAU DANS LE HANDLER HTTP pour l'état : la boucle écrit _track,
l'endpoint LIT. La dernière position rotor connue vient de la boucle elle-même.
"""
import threading
import time

import logx_rotor as rotor
import logx_sat_passes as sp
from logx_utils import locator_to_latlon, utcnow

# Choix d'ingénierie — voir l'en-tête pour la justification de chacun.
DEADBAND_DEG = 4.0
CADENCE_S = 2.0
PREAVIS_MAX_S = 15 * 60      # refus si l'AOS est à plus de 15 min
DUREE_MAX_S = 45 * 60        # attente (≤15 min) + passage LEO (≤20 min) + marge
ECHECS_ROTOR_MAX = 3

_lock = threading.Lock()
# L'Event d'arrêt est PAR SUIVI, créé dans demarrer_suivi et passé à la boucle
# — jamais un Event module partagé. Constat de revue : un POST d'arrêt retardé
# (multi-op, pile réseau lente) émis pour le suivi N aurait tué le suivi N+1
# démarré entre-temps ; sur une expédition, l'orbite ratée ne repasse pas
# avant des heures. `_stop_courant` ne sert qu'à arreter_suivi(), sous _lock.
_stop_courant = None
_track = {
    'actif': False,
    'sat': '',
    'phase': 'inactif',      # inactif | attente | suivi | fini | erreur
    'message': '',
    'note': '',              # avertissement non bloquant (ex. grand tour au nord)
    'cible_az': None, 'cible_el': None,
    'rotor_az': None, 'rotor_el': None,
    'envois': 0,             # nombre de consignes réellement envoyées
    'visible': False,
}
# Hors de _track : l'état est sérialisé JSON tel quel vers le client, un objet
# Thread n'y a pas sa place (même raison que _download_thread dans logx_update).
_track_thread = None


def etat_suivi():
    """État courant, JSON-safe, sans aucun appel réseau."""
    with _lock:
        return dict(_track)


def ecart_azimut(a, b):
    """Écart angulaire le plus court entre deux azimuts, en degrés.

    |359° − 1°| vaut 2°, pas 358° : sans le modulo, un passage qui traverse le
    nord ferait croire à un écart géant et commanderait un tour complet à
    chaque itération.
    """
    try:
        d = abs(float(a) - float(b)) % 360.0
    except (TypeError, ValueError):
        return None
    return min(d, 360.0 - d)


def _los_en_cours(cache, nom, lat, lon, altitude_m=0):
    """LOS du passage EN COURS si le satellite est déjà levé, sinon None.

    `next_pass(singlepass=False)` calcule le PROCHAIN lever et le PROCHAIN
    coucher indépendamment l'un de l'autre : si le satellite est déjà
    au-dessus de l'horizon, le « prochain coucher » retourné est celui du
    passage en cours, quelle que soit sa durée déjà écoulée. Une recherche
    par décalage arrière fixe échouerait dès que ce décalage tombe encore
    DANS le passage — exactement le cas d'un passage long (IO-117/GreenCube)
    rejoint en retard. Repose sur les mêmes primitives privées que celles
    utilisées par logx_sat_passes.passages() (`_corps`, `_observer`).
    """
    if not sp.HAS_EPHEM:
        return None
    sat = sp._corps(cache, nom)
    if sat is None:
        return None
    try:
        obs = sp._observer(lat, lon, altitude_m)
        sat.compute(obs)
        if float(sat.alt) <= 0:
            return None  # pas encore levé : le prochain passage s'en charge
        _, _, _, _, los, _ = obs.next_pass(sat, singlepass=False)
        return los.datetime()
    except (ValueError, TypeError):
        return None


def demarrer_suivi(nom_sat, cfg):
    """Démarre le suivi. (ok, message) — les refus sont SYNCHRONES : tout ce
    qui peut être vérifié avant de lancer le thread l'est ici, pour que
    l'opérateur ait la raison sous les yeux immédiatement, pas dans un état à
    aller relire."""
    global _track_thread

    # Le rotor du parc lié à l'antenne VHF/UHF (144 puis 432), sinon le premier
    # rotor actif, sinon l'ancien rotor unique — la MÊME résolution que
    # /rotor/point et /rotor/state (revue 01/08/2026). Sans elle, une station
    # configurée uniquement via le nouvel éditeur de parc ne pouvait lancer
    # aucun suivi, et le décalage mécanique n'était jamais appliqué au passage.
    import logx_station as station
    rs = station.rotor_defaut(cfg, prefer_bandes=['144', '432'])
    if not rs['enabled']:
        return False, ('Rotor non activé — voir CONFIG, section rotor '
                       '(mode expert).')

    lat, lon = locator_to_latlon((cfg or {}).get('locator', '') or '')
    if lat is None:
        return False, 'Locator manquant ou invalide (page CONFIG).'
    alt_m = (cfg or {}).get('altitude', 0) or 0

    cache = sp.charger_tle()
    if not cache:
        return False, ('Aucun jeu TLE en cache — il se télécharge au '
                       'démarrage du serveur (CelesTrak).')

    nom = str(nom_sat or '').strip()
    pos = sp.position(cache, nom, lat, lon, alt_m)
    if not pos.get('available'):
        return False, pos.get('error', 'Satellite inconnu.')

    # Sous l'horizon : n'accepter que si le passage est proche. Un rotor
    # immobilisé « en attente » pendant des heures est un piège.
    if not pos.get('visible'):
        r = sp.prochain_passage(cache, nom, lat, lon, alt_m)
        p = (r or {}).get('passage')
        if not p:
            return False, 'Aucun passage prévu dans les prochaines 72 h.'
        try:
            import datetime
            aos = datetime.datetime.strptime(p['aos_utc'], '%Y-%m-%d %H:%M:%S')
            dans_s = (aos - utcnow()).total_seconds()
        except (ValueError, KeyError):
            return False, 'Passage illisible dans la prédiction.'
        if dans_s > PREAVIS_MAX_S:
            return False, ('Prochain passage à %s UTC — lance le suivi moins '
                           'de %d minutes avant.'
                           % (p['aos_utc'][11:16], PREAVIS_MAX_S // 60))

    # Le rotor répond-il ? UN appel, borné à 3 s (TIMEOUT_S de logx_rotor) —
    # même ordre de grandeur que les endpoints /rotor existants.
    r = rotor.get_position(rs['host'], rs['port'])
    if not r.get('ok'):
        return False, r.get('error', 'Rotor injoignable.')

    # DURÉE MAXIMALE DIMENSIONNÉE PAR LE PASSAGE quand on le connaît. Le
    # forfait de 45 min coupait un long passage en plein vol si le suivi était
    # lancé tôt ; à l'inverse, pour un satellite visible en permanence
    # (QO-100 : antenne fixe, un suivi n'y sert à rien), le forfait reste le
    # garde-fou qui rend l'antenne à l'opérateur.
    duree_max = DUREE_MAX_S
    try:
        import datetime
        if pos.get('visible'):
            los = _los_en_cours(cache, nom, lat, lon, alt_m)
        else:
            los = datetime.datetime.strptime(p['los_utc'], '%Y-%m-%d %H:%M:%S')
        if los is not None:
            duree_max = min(4 * 3600, max(
                DUREE_MAX_S,
                (los - utcnow()).total_seconds() + 600))
    except (ValueError, KeyError, TypeError):
        pass

    import math
    global _track_thread, _stop_courant
    with _lock:
        if _track['actif']:
            if _track_thread is not None and _track_thread.is_alive():
                return False, 'Un suivi est déjà en cours (%s).' % _track['sat']
            # Orphelin : état « actif » sans thread vivant — le verrou fantôme
            # d'hier, ici impossible par construction.
            _track.update(actif=False, phase='erreur',
                          message='Suivi précédent interrompu sans état '
                                  'terminal — réinitialisé automatiquement.')
        # Un Event NEUF pour CE suivi : un arrêt retardé visant l'ancien ne
        # peut pas tuer celui-ci (constat de revue SAT-TRACK-2).
        ev = threading.Event()
        t = threading.Thread(
            target=_boucle_suivi,
            args=(nom, rs['host'], rs['port'], lat, lon, alt_m, cache, ev),
            kwargs={'duree_max_s': duree_max, 'offset_az': rs['offset_deg']},
            daemon=True)
        _track.update(actif=True, sat=nom, phase='attente', message='', note='',
                      cible_az=None, cible_el=None,
                      # rotctld peut répondre « nan » — float('nan') parse sans
                      # erreur et un NaN dans le JSON casserait le client
                      # (constat C3). On ne publie que du fini.
                      rotor_az=r['azimuth'] if math.isfinite(r['azimuth']) else None,
                      rotor_el=r['elevation'] if math.isfinite(r['elevation']) else None,
                      envois=0, visible=bool(pos.get('visible')))
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


def arreter_suivi():
    """Demande d'arrêt du suivi COURANT — la boucle s'arrête immédiatement
    (elle dort sur cet Event, pas sur une horloge) et stoppe le rotor.
    Sous _lock : l'Event visé est celui du suivi en cours, jamais celui d'un
    suivi passé ou futur."""
    with _lock:
        ev = _stop_courant
    if ev is not None:
        ev.set()
    return True, ''


def _fin(phase, message=''):
    with _lock:
        _track.update(actif=False, phase=phase, message=message)


# Relire la VRAIE position du rotor tous les N tours (N×cadence = 10 s) :
# set_position ne renvoie qu'un ÉCHO de la consigne, jamais une mesure —
# afficher cet écho comme « position rotor » mentait dès que la mécanique
# était à la traîne ou dépointée (constats SAT-2/C5). Une transaction « p »
# de plus toutes les 10 s est négligeable pour rotctld.
TOURS_ENTRE_LECTURES = 5


def _boucle_suivi(nom, host, port, lat, lon, alt_m, cache, stop_ev,
                  cadence_s=CADENCE_S, duree_max_s=DUREE_MAX_S,
                  deadband_deg=DEADBAND_DEG, offset_az=0.0):
    """Le corps du suivi. Enveloppé de bout en bout : quoi qu'il arrive, un
    état terminal est posé — la leçon du verrou fantôme, appliquée d'entrée.
    `stop_ev` est l'Event PROPRE à ce suivi (jamais un Event module partagé).
    `offset_az` = décalage mécanique du pylône, appliqué à l'azimut envoyé."""
    try:
        _boucle_suivi_corps(nom, host, port, lat, lon, alt_m, cache, stop_ev,
                            cadence_s, duree_max_s, deadband_deg, offset_az)
    except Exception as e:
        try:
            rotor.stop(host, port)
        except Exception:
            pass
        _fin('erreur', 'Suivi interrompu : %s' % e)


def _boucle_suivi_corps(nom, host, port, lat, lon, alt_m, cache, stop_ev,
                        cadence_s, duree_max_s, deadband_deg, offset_az=0.0):
    import math
    debut = time.monotonic()
    vu_au_dessus = False
    echecs = 0
    derniere_consigne = None     # (az, el) réellement envoyée
    pre_pointe = False
    tours = 0
    lecture_az = lecture_el = None   # dernière VRAIE position lue du rotor

    while True:
        if stop_ev.is_set():
            rotor.stop(host, port)
            _fin('fini', 'Arrêté par l\'opérateur.')
            return
        if time.monotonic() - debut > duree_max_s:
            rotor.stop(host, port)
            _fin('fini', 'Durée maximale de suivi atteinte (%d min) — arrêt '
                         'automatique.' % (duree_max_s // 60))
            return

        pos = sp.position(cache, nom, lat, lon, alt_m)
        if not pos.get('available'):
            rotor.stop(host, port)
            _fin('erreur', pos.get('error', 'Position satellite indisponible.'))
            return

        el = pos['el']
        visible = el > 0
        note = ''

        if visible:
            vu_au_dessus = True
            cible_az, cible_el = pos['az'], max(0.0, el)
            phase = 'suivi'
        elif vu_au_dessus:
            # LOS : le passage est terminé.
            rotor.stop(host, port)
            _fin('fini', 'Passage terminé (LOS).')
            return
        else:
            # Attente : pré-pointer l'azimut de LEVER, une seule fois — le
            # satellite est sous l'horizon, son azimut actuel n'intéresse pas
            # l'antenne, c'est là où il va apparaître qui compte.
            phase = 'attente'
            if not pre_pointe:
                r = sp.prochain_passage(cache, nom, lat, lon, alt_m)
                p = (r or {}).get('passage')
                if not p:
                    rotor.stop(host, port)
                    _fin('erreur', 'Passage attendu introuvable dans la '
                                   'prédiction.')
                    return
                cible_az, cible_el = p['az_aos'], 0.0
            else:
                cible_az, cible_el = derniere_consigne

        # Bande morte : ne commander que si l'écart en vaut la peine.
        envoyer = derniere_consigne is None
        if not envoyer:
            d_az = ecart_azimut(cible_az, derniere_consigne[0])
            d_el = abs(cible_el - derniere_consigne[1])
            envoyer = (d_az is not None and d_az > deadband_deg) or d_el > deadband_deg
            # Passage traversant le nord : la consigne BRUTE saute (359→1) et
            # un rotor sans overlap fait le grand tour en plein passage. On ne
            # peut pas l'empêcher — on le DIT (voir en-tête du module).
            if envoyer and abs(float(cible_az) - derniere_consigne[0]) > 180:
                note = ('Trajectoire au passage du nord : un rotor sans '
                        'chevauchement fait un tour complet ici.')

        envoi_ok = None
        if envoyer:
            # Re-vérifier l'arrêt JUSTE avant de commander : sans ça, un stop
            # posé pendant le calcul laissait partir une consigne posthume
            # après le « Arrêté par l'opérateur » (constat SAT-TRACK-3).
            if stop_ev.is_set():
                continue
            # Décalage mécanique du pylône appliqué à l'AZIMUT envoyé (l'azimut
            # vrai reste cible_az pour l'affichage et la logique). Sans lui, un
            # rotor dont le zéro n'est pas au nord dépointe tout le passage.
            import logx_station as _st
            az_envoi = _st.azimut_rotor({'offset_deg': offset_az}, cible_az)
            if az_envoi is None:
                az_envoi = cible_az
            r = rotor.set_position(host, port, az_envoi, cible_el)
            if r.get('ok'):
                echecs = 0
                derniere_consigne = (cible_az, cible_el)
                pre_pointe = True
                envoi_ok = r
            else:
                echecs += 1
                if echecs >= ECHECS_ROTOR_MAX:
                    rotor.stop(host, port)
                    _fin('erreur', 'Rotor injoignable (%d échecs consécutifs) '
                                   '— %s' % (echecs, r.get('error', '')))
                    return

        # Relecture périodique de la VRAIE position (voir TOURS_ENTRE_LECTURES).
        tours += 1
        if tours % TOURS_ENTRE_LECTURES == 0:
            lu = rotor.get_position(host, port)
            # Un échec de LECTURE ne compte pas dans `echecs` : celui-ci
            # protège l'envoi de consignes, pas l'affichage.
            if lu.get('ok') and math.isfinite(lu['azimuth']) \
                    and math.isfinite(lu['elevation']):
                lecture_az, lecture_el = lu['azimuth'], lu['elevation']

        # UNE seule écriture de l'état par tour, sous UNE prise de verrou :
        # deux prises successives laissaient un lecteur voir un état mi-ancien
        # mi-nouveau (constat SAT-TRACK-4).
        with _lock:
            maj = {'phase': phase, 'visible': visible, 'sat': nom,
                   'note': note,
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

        # Dormir sur l'EVENT, pas sur une horloge : un arrêt demandé pendant
        # la dormance réveille immédiatement (constat SAT-TRACK-3), au lieu
        # d'attendre jusqu'à 2 s avec le rotor encore en mouvement.
        if stop_ev.wait(cadence_s):
            continue
