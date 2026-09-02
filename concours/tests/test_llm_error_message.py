# -*- coding: utf-8 -*-
"""_llm_error_message : rendre lisible l'erreur d'un fournisseur IA.

L'app renvoyait « HTTP Error 400: Bad Request » (opaque) là où l'API donnait la
vraie cause (ex. « anthropic-workspace-id is required… », clé/modèle refusé). Le
helper extrait le message utile du corps JSON, avec repli sur un extrait brut.
"""
import os
import sys

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CONCOURS not in sys.path:
    sys.path.insert(0, CONCOURS)

import logx_http as h  # noqa: E402


def test_extrait_message_anthropic():
    body = (b'{"type":"error","error":{"type":"invalid_request_error",'
            b'"message":"anthropic-workspace-id is required when authenticating '
            b'with an identity-linked API key"}}')
    m = h._llm_error_message('anthropic', 400, body)
    assert 'anthropic' in m and 'HTTP 400' in m and 'workspace-id' in m
    assert 'Bad Request' not in m          # plus le message opaque


def test_extrait_message_openai():
    body = b'{"error":{"message":"Incorrect API key provided","type":"invalid_request_error"}}'
    m = h._llm_error_message('openai', 401, body)
    assert 'Incorrect API key' in m and 'HTTP 401' in m


def test_corps_non_json_repli_brut():
    m = h._llm_error_message('gemini', 503, b'Service Unavailable')
    assert 'Service Unavailable' in m and 'HTTP 503' in m


def test_corps_vide_ne_plante_pas():
    m = h._llm_error_message('anthropic', 500, b'')
    assert 'HTTP 500' in m and 'anthropic' in m
