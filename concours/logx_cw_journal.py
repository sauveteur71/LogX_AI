# -*- coding: utf-8 -*-
"""Journal TX CW structuré (keyer CW Phase 1c, F4GLD 23/08).

Avant, seule une trace `print()` console gardait le texte réellement manipulé.
Ici un journal EN MÉMOIRE, borné et horodaté UTC, avec le backend qui a émis —
consultable via GET /rig/cw/journal. C'est l'enregistrement de ce qui est
RÉELLEMENT parti à la clé (audit d'émission), distinct du simple écho client du
terminal. Ne persiste pas sur disque : un journal d'émission n'a pas à survivre
au redémarrage et ne doit pas grossir sans fin.
"""
import time
from collections import deque

_MAX = 200
_journal = deque(maxlen=_MAX)


def enregistrer(texte, backend, wpm=None, freq_khz=None, _horloge=time.time):
    """Ajoute une entrée pour un envoi CW réellement accepté. Ne lève JAMAIS
    (un défaut de journalisation ne doit pas casser une émission en cours)."""
    try:
        t = _horloge()
        _journal.append({
            'time': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(t)),
            'text': str(texte or '')[:200],
            'backend': str(backend or ''),
            'wpm': wpm,
            'freq_khz': freq_khz,
        })
    except Exception:
        pass


def entrees(limite=50):
    """Les `limite` dernières entrées (la plus récente en dernier)."""
    try:
        n = max(0, min(_MAX, int(limite)))
    except (TypeError, ValueError):
        n = 50
    return list(_journal)[-n:]


def _vider():
    """Réinitialise le journal (tests / bouton d'effacement éventuel)."""
    _journal.clear()
