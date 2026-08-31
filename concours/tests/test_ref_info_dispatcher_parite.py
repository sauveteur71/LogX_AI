# -*- coding: utf-8 -*-
"""Parité relevé de saisie (JS) ↔ dispatcher /activation_db (Python).

DEUX LISTES JUMELLES, piège récurrent du dépôt : logx_ref_info.js interroge
/activation_db/lookup pour les seuls programmes de sa liste `PROGRAMMES` ; le
serveur ne répond que pour les programmes du dispatcher `_activation_db_adapter`. Si un
programme figure côté JS SANS branche Python, le relevé lance une requête que le
serveur ne sait pas servir -> enrichissement muet à la saisie, SANS erreur. Ce
sens-là est le dangereux, et rien ne le verrouillait.

On tient donc l'invariant : PROGRAMMES(JS) ⊆ dispatcher(Python). L'inverse est
permis (le serveur PEUT savoir valider un programme pas encore enrichi côté
saisie). WCA a été activé au relevé le 31/08 (à la demande de F4GLD) : il est
désormais des deux côtés."""
import os
import re

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _programmes_js():
    src = open(os.path.join(CONCOURS, 'logx_ref_info.js'), encoding='utf-8').read()
    m = re.search(r'var PROGRAMMES\s*=\s*\{([^}]*)\}', src)
    assert m, 'PROGRAMMES introuvable dans logx_ref_info.js'
    return set(re.findall(r'([A-Z0-9]+)\s*:', m.group(1)))


def _programmes_python():
    src = open(os.path.join(CONCOURS, 'logx_http.py'), encoding='utf-8').read()
    # Le dispatcher _activation_db_adapter : toutes les branches `program == 'X'`.
    deb = src.index('def _activation_db_adapter')
    fin = src.index('\n\ndef ', deb + 10)
    corps = src[deb:fin]
    return set(re.findall(r"program == '([A-Z0-9]+)'", corps))


def test_tout_programme_du_releve_a_une_branche_serveur():
    js = _programmes_js()
    py = _programmes_python()
    manquants = js - py
    assert not manquants, (
        'ces programmes sont interrogés par le relevé (logx_ref_info.js) mais '
        "n'ont AUCUNE branche dans le dispatcher _activation_db_adapter -> lookup muet : %s"
        % sorted(manquants))


def test_les_quatre_referentiels_de_la_session_sont_des_deux_cotes():
    """Non-régression : DFCF/WWBOTA/GMA/ARLHS doivent rester câblés bout en bout
    (relevé JS ET dispatcher Python)."""
    js, py = _programmes_js(), _programmes_python()
    for prog in ('DFCF', 'WWBOTA', 'GMA', 'ARLHS'):
        assert prog in js, '%s absent de PROGRAMMES (relevé de saisie)' % prog
        assert prog in py, '%s absent du dispatcher _activation_db_adapter' % prog


def test_wca_est_active_au_releve_de_saisie():
    """Activé le 31/08 (F4GLD « active wca ») : WCA doit être des deux côtés, et
    le lookup exposer un 'region' (alias de 'location') pour l'affichage
    « nom · lieu » du relevé."""
    assert 'WCA' in _programmes_js() and 'WCA' in _programmes_python()
    src = open(os.path.join(CONCOURS, 'logx_wca.py'), encoding='utf-8').read()
    corps = src[src.index('def get_castle_geocoded'):]
    corps = corps[:corps.index('\n\n\n')] if '\n\n\n' in corps else corps[:2000]
    assert "merged['region']" in corps, (
        "get_castle_geocoded doit exposer 'region' (alias de 'location') pour "
        "le relevé de saisie :\n" + corps)
