# -*- coding: utf-8 -*-
"""Indice d'ouverture VHF (Sporadique-E et au-delà) — détecte un DÉBUT
d'ouverture à partir du flux de spots déjà collecté par ce logiciel (F5LEN,
DXSummit, DXWatch, HamQTH, HamSpirit, DXMaps — voir
logx_clusters.fetch_all_vhf_spots), plutôt que d'attendre de le remarquer
soi-même en parcourant la liste de spots.

Aucune prévision physique n'existe ici pour l'Es (contrairement au tropo —
logx_tropo.py — qui a un vrai modèle de réfractivité, ou au meteor scatter —
logx_meteors.py — qui a un calendrier d'essaims) : le Sporadique-E s'ouvre et
se ferme en quelques minutes, sans modèle météo fiable à cette échelle. Le
signal le plus tôt disponible n'est donc pas physique mais STATISTIQUE : un
afflux soudain de spots portant sur des distances inhabituelles, dans le
cluster lui-même, précède de peu la découverte de l'ouverture par la plupart
des opérateurs qui la remarquent en lisant la liste.

Principe (transparent, PAS un modèle boîte noire) : on compare une fenêtre
« maintenant » (les FENETRE_MIN dernières minutes) à une fenêtre de référence
(les BASELINE_MIN minutes précédentes) sur trois axes :
  - VOLUME : nombre de spots reçus (ratio par rapport au taux habituel).
  - PORTÉE : distance maximale opérateur -> DX parmi ces spots (un afflux de
    spots proches est juste plus de trafic local, pas une ouverture).
  - DIVERSITÉ : nombre d'indicatifs DX distincts (un seul correspondant qui
    reste spotté en boucle n'est pas une ouverture qui s'étend).

Historique conservé UNIQUEMENT en mémoire du process serveur (perdu à un
redémarrage) : l'indice n'a de sens que sur les dernières heures, un
historique qui survivrait au redémarrage n'apporterait rien.
"""
import threading
import time

from logx_clusters import fetch_all_vhf_spots
from logx_utils import haversine, locator_to_latlon

BANDES = ('50', '144')
FENETRE_MIN = 15          # fenêtre « maintenant »
BASELINE_MIN = 120        # fenêtre de référence, juste avant la fenêtre courante
GARDE_MIN = FENETRE_MIN + BASELINE_MIN + 10   # marge avant purge de l'historique
FETCH_CACHE_S = 90        # ne pas re-solliciter les clusters plus souvent que ça

_lock = threading.Lock()
_history = {b: [] for b in BANDES}     # bande -> [{'ts','call','dist_km'}, ...]
_last_fetch = {b: 0.0 for b in BANDES}


def reset_history():
    """Repart d'un historique vide — appelé par les tests, jamais en prod."""
    with _lock:
        for b in BANDES:
            _history[b] = []
            _last_fetch[b] = 0.0


def _purge(band, now):
    limite = now - GARDE_MIN * 60
    _history[band] = [s for s in _history[band] if s['ts'] >= limite]


def _collecter(band, my_lat, my_lon, now, fetch_fn):
    """Ajoute à l'historique les spots VUS MAINTENANT (un par couple
    indicatif+spotteur, pour ne pas compter deux fois le même événement si
    plusieurs sources cluster rapportent le même spot). N'écrase jamais les
    entrées d'un cycle précédent : la MÊME station spottée à nouveau au
    cycle suivant est un événement distinct (le trajet reste ouvert),
    signal utile en soi plutôt qu'un doublon à filtrer."""
    spots = fetch_fn(int(band), True, {}) or []
    vus = set()
    for s in spots:
        if not isinstance(s, dict):
            continue
        call = (s.get('call') or s.get('dx') or '').upper().strip()
        spotter = (s.get('spotter') or '').upper().strip()
        cle = (call, spotter)
        if not call or cle in vus:
            continue
        vus.add(cle)
        lat, lon = s.get('lat'), s.get('lon')
        dist = None
        if lat is not None and lon is not None and my_lat is not None:
            try:
                dist = haversine(my_lat, my_lon, lat, lon)
            except (TypeError, ValueError):
                dist = None
        _history[band].append({'ts': now, 'call': call, 'dist_km': dist})
    _purge(band, now)


def _fenetre(band, now, debut_min, fin_min):
    """Entrées de l'historique dont l'âge (minutes) est dans [debut_min, fin_min[."""
    lo, hi = now - fin_min * 60, now - debut_min * 60
    return [s for s in _history[band] if lo <= s['ts'] < hi]


NIVEAU_TXT = {
    'excellent': "Ouverture en cours — nette hausse de spots à longue distance",
    'bon':       "Signes d'ouverture — activité au-dessus de la normale",
    'moyen':     "Activité normale",
    'faible':    "Calme",
}


def _niveau(ratio, dist_max, diversite):
    """Score simple, chaque axe plafonné pour qu'aucun ne domine seul à lui
    tout seul (un seul spot à 2000 km n'est pas encore une ouverture, un
    déluge de spots tous proches non plus)."""
    score = 0
    if ratio >= 3:
        score += 3
    elif ratio >= 1.8:
        score += 2
    elif ratio >= 1.2:
        score += 1
    if dist_max is not None:
        if dist_max >= 1200:
            score += 3
        elif dist_max >= 600:
            score += 2
        elif dist_max >= 300:
            score += 1
    if diversite >= 5:
        score += 2
    elif diversite >= 2:
        score += 1
    # « excellent » exige AUSSI de la diversité : un seul correspondant
    # spotté en boucle (le même spotteur qui republie, ou un DX qui traîne)
    # peut cumuler volume et distance sans que ce soit une vraie ouverture
    # qui s'étend à d'autres stations — le score seul ne suffit pas à
    # l'écarter, il faut un vrai gate sur ce troisième axe.
    if score >= 6 and diversite >= 2:
        return 'excellent', score
    if score >= 4:
        return 'bon', score
    if score >= 1:
        return 'moyen', score
    return 'faible', score


def opening_index(band, my_locator='', now=None, fetch_fn=None):
    """Indice d'ouverture pour une bande ('50' ou '144').

    `now`/`fetch_fn` sont des points d'injection pour les tests (horloge et
    source réseau déterministes) ; en usage normal, laissés à None.

    Retourne {'ok', 'band', 'level', 'score', 'title', 'reason',
    'volume_15min', 'baseline_rate_15min', 'dist_max_km', 'diversity'}
    ou {'ok': False, 'error'}."""
    band = str(band)
    if band not in _history:
        return {'ok': False, 'error': 'Bande non prise en charge pour cet indice : ' + band}
    now = now if now is not None else time.time()
    fetch_fn = fetch_fn or fetch_all_vhf_spots

    my_lat, my_lon = (None, None)
    if my_locator:
        my_lat, my_lon = locator_to_latlon(my_locator)

    with _lock:
        if now - _last_fetch[band] >= FETCH_CACHE_S:
            try:
                _collecter(band, my_lat, my_lon, now, fetch_fn)  # purge aussi, en interne
            except Exception as e:
                print(f"[ES-OPENING] collecte {band} MHz échouée : {e}")
            _last_fetch[band] = now
        else:
            # La collecte (et sa purge) est sautée la plupart des appels, à
            # cause du cache réseau ci-dessus — sans cette ligne, une entrée
            # trop vieille ne serait jamais retirée tant qu'un fetch frais ne
            # se déclenche pas, ce qui peut prendre des heures en pratique.
            _purge(band, now)

        fen_now = _fenetre(band, now, 0, FENETRE_MIN)
        fen_base = _fenetre(band, now, FENETRE_MIN, FENETRE_MIN + BASELINE_MIN)

        vol_now = len(fen_now)
        diversite = len({s['call'] for s in fen_now})
        vol_base = len(fen_base)
        # Ramené à un taux par FENETRE_MIN pour comparer deux fenêtres de
        # durées différentes (BASELINE_MIN >> FENETRE_MIN).
        taux_base = vol_base / (BASELINE_MIN / FENETRE_MIN) if vol_base else 0.0
        ratio = (vol_now / taux_base) if taux_base > 0 else (2.0 if vol_now > 0 else 0.0)

        dists = [s['dist_km'] for s in fen_now if s.get('dist_km') is not None]
        dist_max = max(dists) if dists else None

        level, score = _niveau(ratio, dist_max, diversite)

        bouts = [f"{vol_now} spot(s) / {FENETRE_MIN} min"]
        if taux_base > 0:
            bouts[0] += f" (x{ratio:.1f} vs habituel)"
        if dist_max:
            bouts.append(f"jusqu'à {dist_max} km")
        if diversite:
            bouts.append(f"{diversite} indicatif(s) distinct(s)")

        return {
            'ok': True, 'band': band, 'level': level, 'score': score,
            'title': NIVEAU_TXT[level], 'reason': ' — '.join(bouts),
            'volume_15min': vol_now, 'baseline_rate_15min': round(taux_base, 1),
            'dist_max_km': dist_max, 'diversity': diversite,
        }


def opening_summary(my_locator='', now=None, fetch_fn=None):
    """{'50': opening_index(...), '144': opening_index(...)} — un seul appel
    pour alimenter le panneau côté client plutôt que deux requêtes HTTP."""
    return {b: opening_index(b, my_locator, now=now, fetch_fn=fetch_fn) for b in BANDES}
