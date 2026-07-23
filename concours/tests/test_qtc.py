# -*- coding: utf-8 -*-
"""Tests bas niveau du modèle QTC (WAE) dans logx_storage : attribution d'id
et rétro-compatibilité au chargement des séries enregistrées avant l'ajout de
la saisie détaillée. Les tests d'endpoint HTTP (/qtc/add, /qtc/delete) vivent
dans tests/test_http_scope_endpoints.py ; ceux de l'export Cabrillo dans
tests/test_export.py."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_storage as st


def _in_tmp(tmp_path, fn):
    """Exécute fn dans un dossier vierge (QTC_FILE est un chemin relatif)."""
    old = os.getcwd()
    os.chdir(tmp_path)
    saved_log = list(st.qtc_log)
    saved_next_id = st._qtc_next_id
    try:
        st.qtc_log[:] = []
        return fn()
    finally:
        st.qtc_log[:] = saved_log
        st._qtc_next_id = saved_next_id
        os.chdir(old)


def test_next_qtc_id_est_croissant(tmp_path):
    def run():
        a = st.next_qtc_id()
        b = st.next_qtc_id()
        c = st.next_qtc_id()
        assert a < b < c
    _in_tmp(tmp_path, run)


def test_load_qtc_backfill_id_series_ancien_format(tmp_path):
    """Une série enregistrée avant l'ajout de la saisie détaillée n'a pas de
    champ 'id' — le chargement doit lui en attribuer un (voir /qtc/delete,
    qui cible une série par id) sans dupliquer les id déjà présents."""
    def run():
        with open(st.QTC_FILE, 'w', encoding='utf-8') as f:
            json.dump([
                {'call': 'F5ABC', 'count': 4, 'contest': 'WAEDC_SSB',
                 'date': '20270911', 'time': '10:00'},               # sans id (ancien format)
                {'id': 5, 'call': 'DL0XM', 'count': 2, 'contest': 'WAEDC_SSB',
                 'date': '20270911', 'time': '11:00', 'direction': 'sent'},
            ], f)
        st.load_qtc_from_disk()
        ids = [q['id'] for q in st.qtc_log]
        assert len(ids) == len(set(ids)), 'ids dupliqués après rétro-compatibilité'
        assert all(isinstance(i, int) for i in ids)
        # Le prochain id distribué ne doit jamais entrer en collision avec
        # l'id 5 déjà présent dans le fichier.
        assert st.next_qtc_id() not in ids
    _in_tmp(tmp_path, run)


def test_qtc_total_et_count_for_call_lisent_aussi_les_series_detaillees(tmp_path):
    """qtc_total/qtc_count_for_call ne lisent que 'count'/'call'/'contest' —
    une série détaillée (avec 'entries') doit donc compter exactement comme
    l'ancien format tant que 'count' est cohérent avec len(entries)."""
    def run():
        st.qtc_log[:] = [{
            'id': st.next_qtc_id(), 'call': 'DL0XM', 'count': 3,
            'contest': 'WAEDC_SSB', 'date': '20270911', 'time': '10:00',
            'direction': 'sent', 'entries': [
                {'time': '0030', 'call': 'YU1ZZ', 'nr': '62'},
                {'time': '0031', 'call': 'YU2ZZ', 'nr': '63'},
                {'time': '0032', 'call': 'YU3ZZ', 'nr': '64'},
            ]}]
        scope = 'WAEDC_SSB#2027'
        assert st.qtc_total(scope) == 3
        assert st.qtc_count_for_call('DL0XM', scope) == 3
    _in_tmp(tmp_path, run)
