# -*- coding: utf-8 -*-
"""_refresh_tropo_async ne doit pas rester en deadlock si le thread ne démarre pas.

La fonction acquiert _tropo_refresh_lock (non-bloquant) puis lance un thread qui
le relâche dans un finally. Si threading.Thread(...).start() lève (épuisement
des threads sur un run de 360 h en expédition), le thread ne s'exécute jamais,
le verrou n'est JAMAIS relâché, et tout rafraîchissement tropo ultérieur est
bloqué définitivement. Correctif : relâcher le verrou si le démarrage échoue.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_tropo as t


class _FailingThread:
    def __init__(self, *a, **k):
        pass

    def start(self):
        raise RuntimeError("can't start new thread")


def test_echec_demarrage_thread_relache_le_verrou():
    orig = t.threading.Thread
    t.threading.Thread = _FailingThread
    try:
        try:
            t._refresh_tropo_async(48.0, 2.0)
        except RuntimeError:
            pass  # l'exception se propage (attendu) — mais le verrou doit être libre
        acquis = t._tropo_refresh_lock.acquire(blocking=False)
        assert acquis, "verrou non relâché après échec du thread -> deadlock permanent"
        t._tropo_refresh_lock.release()
    finally:
        t.threading.Thread = orig
