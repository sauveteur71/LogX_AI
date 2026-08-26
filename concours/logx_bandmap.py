# -*- coding: utf-8 -*-
"""Band map Search & Pounce : mémoriser les stations que J'ENTENDS moi-même.

Le band map ne connaissait que le cluster DX. Or le S&P représente facilement
la moitié des QSO d'un concours mono-opérateur, et son geste de base est :
je balaie la bande, j'entends une station, je note « celle-là je la rappellerai
dans 20 minutes », et je saute de station en station au clavier. Une station
entendue mais que personne n'a spottée était jusqu'ici simplement perdue.

N1MM, Win-Test et DXLog remplissent leur band map avec les DEUX sources : le
cluster ET ce que l'opérateur note en balayant. C'est la moitié qui manquait.

Choix d'architecture : le stockage est CÔTÉ SERVEUR, comme le reste. En
multi-opérateur, la station entendue par le poste 144 est immédiatement visible
du poste 432 — ce qu'un stockage navigateur ne permettrait pas. Et le band map
survit à un rechargement de page en plein concours.

VIEILLISSEMENT : un spot local a une durée de vie. En concours, une station
entendue il y a une heure a presque sûrement changé de fréquence ; la garder
affichée enverrait l'opérateur sur une fréquence vide, ce qui est pire que de
ne rien afficher. Les spots expirés disparaissent d'eux-mêmes.
"""
import json
import threading
import time

from logx_storage import save_json_atomic

FICHIER = 'bandmap_local.json'

# Durée de vie par défaut d'un spot local, en secondes. 30 minutes : au-delà,
# en concours, la station a très probablement bougé.
DUREE_VIE_S = 30 * 60

# Plafond du nombre de spots conservés. Un band map n'est pas un journal : au
# delà, ce sont les plus anciens qui partent. Garde-fou contre un remplissage
# accidentel (macro répétée, script) sur une expédition de 15 jours.
MAX_SPOTS = 500

_lock = threading.Lock()
_spots = []      # [{call, freq_khz, band, mode, ts, source, note}]
_charge = False


def _cle(call, freq_khz):
    """Identité d'un spot : l'indicatif ET la fréquence AU kHz PRÈS.

    Pas la fréquence exacte : on ne retrouve jamais une station au Hz près en
    la rappelant, et deux notes à 14 025,3 et 14 025,4 kHz seraient deux lignes
    pour la même station. Pas l'indicatif seul non plus : la même station peut
    légitimement être entendue sur deux bandes."""
    return (str(call or '').upper().strip(), int(round(float(freq_khz or 0))))


def _chemin():
    return FICHIER


def _charger_si_besoin():
    global _charge
    if _charge:
        return
    _charge = True
    try:
        with open(_chemin(), encoding='utf-8') as f:
            data = json.load(f)
        if isinstance(data, list):
            _spots.extend(d for d in data if isinstance(d, dict))
    except (OSError, ValueError):
        pass


def _sauver_locked():
    save_json_atomic(_chemin(), _spots, compact=True)


def _purger_locked(maintenant=None):
    now = time.time() if maintenant is None else maintenant
    vivants = [s for s in _spots if now - float(s.get('ts') or 0) < DUREE_VIE_S]
    if len(vivants) > MAX_SPOTS:
        vivants.sort(key=lambda s: float(s.get('ts') or 0), reverse=True)
        vivants = vivants[:MAX_SPOTS]
    if len(vivants) != len(_spots):
        _spots[:] = vivants
        return True
    return False


def ajouter(call, freq_khz, band='', mode='', note='', maintenant=None):
    """Note une station entendue. Renoter la même station à la même fréquence
    RAFRAÎCHIT son horodatage au lieu d'ajouter une ligne : en balayant, on
    repasse plusieurs fois sur la même station, et une pile de doublons rendrait
    le band map illisible."""
    call = str(call or '').upper().strip()
    if not call:
        return {'ok': False, 'error': 'Indicatif manquant'}
    # Absente et illisible ne sont pas la même chose pour l'opérateur : sans
    # pilotage CAT il n'y a PAS de fréquence (rien à corriger de son côté),
    # alors qu'une valeur illisible signale une vraie anomalie.
    if freq_khz in (None, ''):
        return {'ok': False, 'error': 'Fréquence manquante'}
    try:
        f = float(freq_khz)
    except (TypeError, ValueError):
        return {'ok': False, 'error': 'Fréquence illisible'}
    if f <= 0:
        return {'ok': False, 'error': 'Fréquence manquante'}

    now = time.time() if maintenant is None else maintenant
    cle = _cle(call, f)
    with _lock:
        _charger_si_besoin()
        for s in _spots:
            if _cle(s.get('call'), s.get('freq_khz')) == cle:
                s['ts'] = now
                # Aligner la fréquence stockée sur la dernière notée : _cle
                # identifie au kHz près, donc renoter à 14025,4 tombe sur un
                # spot noté à 14025,1. Sans cette mise à jour, la liste garde
                # l'ancienne valeur alors que la réponse renvoie la nouvelle
                # (réponse incohérente avec l'état affiché).
                s['freq_khz'] = f
                if band:
                    s['band'] = str(band)
                if mode:
                    s['mode'] = str(mode)
                if note:
                    s['note'] = str(note)[:80]
                _purger_locked(now)
                _sauver_locked()
                return {'ok': True, 'call': call, 'freq_khz': f, 'rafraichi': True}
        _spots.append({'call': call, 'freq_khz': f, 'band': str(band or ''),
                       'mode': str(mode or ''), 'ts': now,
                       'source': 'local', 'note': str(note or '')[:80]})
        _purger_locked(now)
        _sauver_locked()
    return {'ok': True, 'call': call, 'freq_khz': f, 'rafraichi': False}


def supprimer(call, freq_khz):
    cle = _cle(call, freq_khz)
    with _lock:
        _charger_si_besoin()
        avant = len(_spots)
        _spots[:] = [s for s in _spots
                     if _cle(s.get('call'), s.get('freq_khz')) != cle]
        if len(_spots) != avant:
            _sauver_locked()
    return {'ok': True, 'supprimes': avant - len(_spots)}


def vider():
    with _lock:
        _charger_si_besoin()
        _spots[:] = []
        _sauver_locked()
    return {'ok': True}


def spots(maintenant=None):
    """Spots locaux encore valides, du plus haut en fréquence au plus bas —
    même ordre que le band map, pour que le client n'ait rien à retrier."""
    with _lock:
        _charger_si_besoin()
        _purger_locked(maintenant)
        now = time.time() if maintenant is None else maintenant
        return sorted(
            ({'call': s.get('call', ''), 'freq_khz': float(s.get('freq_khz') or 0),
              'band': s.get('band', ''), 'mode': s.get('mode', ''),
              'note': s.get('note', ''), 'source': 'local',
              'age_s': int(now - float(s.get('ts') or 0))}
             for s in _spots),
            key=lambda s: s['freq_khz'], reverse=True)
