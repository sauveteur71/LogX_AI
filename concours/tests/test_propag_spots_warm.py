# -*- coding: utf-8 -*-
"""PROPAG : réchauffage du cache de spots de la bande focalisée (défaut F4GLD,
25/08/2026 : /data/focus lisait le cache sans jamais le remplir hors concours,
d'où « Aucun spot » à l'ouverture sur 80 m).

- _warm_key_for_band(band) : bande MHz -> clé SPOTS_CACHE ('HF'/'144'/'432'/'50')
  ou None. PURE.
- _warm_band_spots(band, cfg, now, spawn) : lance le bon fetcher en tâche de
  fond, throttlé par clé. `spawn`/`now` injectés -> pas de réseau ni de thread.
- Câblage : /data/focus appelle _warm_band_spots sur la bande demandée.
"""
import os
import re
import sys

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CONCOURS not in sys.path:
    sys.path.insert(0, CONCOURS)
os.chdir(CONCOURS)

import logx_http as h  # noqa: E402


# ─── _warm_key_for_band : mapping pur ──────────────────────────────────────

def test_key_hf_pour_bandes_deca():
    for b in ('1.8', '3.5', '7', '10', '14', '18', '21', '24', '28'):
        assert h._warm_key_for_band(b) == 'HF', b


def test_key_vhf_et_50():
    assert h._warm_key_for_band('144') == '144'
    assert h._warm_key_for_band('432') == '432'
    assert h._warm_key_for_band('50') == '50'


def test_key_none_hors_couverture():
    for b in ('', None, '2.4', '1296', 'xxx'):
        assert h._warm_key_for_band(b) is None, b


# ─── _warm_band_spots : déclenchement + throttle (spawn/now injectés) ───────

def _reset():
    with h._SPOTS_WARM_LOCK:
        h._SPOTS_WARM_TS.clear()


def test_declenche_le_bon_fetcher_hf():
    _reset()
    lances = []
    key = h._warm_band_spots('3.5', {'callsign': 'F4GLD', 'toggles': {}},
                             now=1000.0, spawn=lambda t: lances.append(t))
    assert key == 'HF'
    assert len(lances) == 1        # une tâche de fond lancée (non exécutée ici)


def test_bande_non_couverte_ne_lance_rien():
    _reset()
    lances = []
    key = h._warm_band_spots('1296', {}, now=1000.0, spawn=lambda t: lances.append(t))
    assert key is None
    assert lances == []


def test_throttle_par_cle():
    _reset()
    lances = []
    spawn = lambda t: lances.append(t)
    cfg = {'callsign': 'F4GLD', 'toggles': {}}
    assert h._warm_band_spots('3.5', cfg, now=1000.0, spawn=spawn) == 'HF'
    # même clé, dans la fenêtre de throttle -> pas de nouveau fetch
    assert h._warm_band_spots('7', cfg, now=1000.0 + h.WARM_THROTTLE_S - 1, spawn=spawn) is None
    # après la fenêtre -> re-fetch autorisé
    assert h._warm_band_spots('14', cfg, now=1000.0 + h.WARM_THROTTLE_S + 1, spawn=spawn) == 'HF'
    assert len(lances) == 2


def test_cles_independantes_dans_le_throttle():
    _reset()
    lances = []
    spawn = lambda t: lances.append(t)
    cfg = {'toggles': {}}
    assert h._warm_band_spots('3.5', cfg, now=1000.0, spawn=spawn) == 'HF'
    # 144 est une AUTRE clé : pas throttlée par le fetch HF
    assert h._warm_band_spots('144', cfg, now=1000.0, spawn=spawn) == '144'
    assert len(lances) == 2


# ─── Câblage : /data/focus réchauffe la bande demandée ─────────────────────

def test_focus_appelle_le_rechauffage():
    src = open(os.path.join(CONCOURS, 'logx_http.py'), encoding='utf-8').read()
    m = re.search(r"if path\.startswith\('/data/focus'\):.*?ranked, meta = build_ranked_spots",
                  src, re.S)
    assert m, 'handler /data/focus introuvable'
    assert '_warm_band_spots(bande, cfg_snap)' in m.group(0)
