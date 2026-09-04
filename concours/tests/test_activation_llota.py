# -*- coding: utf-8 -*-
"""LLOTA (Lakes and Lagoons On The Air) ajouté aux programmes portables.

Programme XOTA « plans d'eau » (lacs, lagunes, réservoirs, barrages),
https://llota.app/ . Intégration v1 = **validation syntaxique seule** : aucune
API/catalogue confirmé (site inaccessible en accès automatisé, HTTP 403), donc
pas de branche dispatcher, pas de lookup distant, pas de table de coordonnées.
LLOTA n'a PAS de champ ADIF dédié -> mécanisme générique SIG/SIG_INFO (comme
WCA/ARLHS/GMA/WWBOTA).

Valeurs métier (min 10 QSO ; 200 m du bord ; 400 m² de surface minimale) =
CONFIRMÉES au règlement officiel (reglas.html, texte fourni par F4GLD le
2026-09-04 ; le site reste inaccessible en accès automatisé, HTTP 403, mais les
règles sont maintenant sourcées). Seul le min_qso est modélisé en v1 ;
distance/surface restent hors périmètre v1 (documentées, non bloquantes).

Format de référence CONFIRMÉ : `^LL[A-Z]{2}-\\d{4,}$` = préfixe « LL » + code
pays LLOTA (2 lettres) + tiret + 4+ chiffres. Le règlement (reglas.html) l'imposait
(« LLCL-xxxx ») et une VRAIE référence l'a confirmé le 2026-09-04 : **LLNZ-0359**
(Lac Huro, Nouvelle-Zélande). Une recherche secondaire donnait par erreur la forme
nue « CL-0001 » (inférence sans accès au catalogue) — écartée par la réf réelle.
"""
import os
import re
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
os.chdir(BASE)

import logx_activation as act   # noqa: E402


def _lire(nom):
    with open(os.path.join(BASE, nom), encoding='utf-8') as f:
        return f.read()


# ─── Registre Python (la source canonique) ──────────────────────────────────

def test_llota_present_dans_program_specs():
    assert 'LLOTA' in act.PROGRAM_SPECS
    spec = act.PROGRAM_SPECS['LLOTA']
    assert spec['name'] == 'Lakes and Lagoons On The Air'
    assert spec['sig'] == 'LLOTA'
    assert spec['min_qso'] == 10             # confirmé au règlement officiel (reglas.html)
    assert 'adif_tag' not in spec            # pas de tag ADIF dédié -> SIG générique


def test_llota_reference_valide():
    # Format confirmé LLxx-nnnn = préfixe LL + code pays (2 lettres) + tiret + 4+ chiffres.
    assert act.validate_ref('LLOTA', 'LLNZ-0359')       # VRAIE réf (Lac Huro, NZ), vérifiée
    assert act.validate_ref('LLOTA', 'LLCL-0001')       # Chili (exemple du règlement)
    assert act.validate_ref('LLOTA', 'LLFR-1234')       # France
    assert act.validate_ref('LLOTA', 'LLUS-00001')      # 5 chiffres : {4,} l'accepte
    # normalisation commune (strip/upper) : la saisie brute passe aussi
    assert act.validate_ref('LLOTA', ' llnz-0359 ')


def test_llota_reference_invalide():
    assert not act.validate_ref('LLOTA', 'CL-0001')    # forme nue SANS préfixe LL (inférence erronée)
    assert not act.validate_ref('LLOTA', 'LLC-0001')   # code pays 1 lettre après LL
    assert not act.validate_ref('LLOTA', 'LLNZ-035')   # 3 chiffres (< 4)
    assert not act.validate_ref('LLOTA', 'LLNZ0359')   # tiret manquant
    assert not act.validate_ref('LLOTA', 'LLNZ-ABCD')  # partie numérique non chiffrée
    assert not act.validate_ref('LLOTA', 'LLNZX-0359') # LL + 3 lettres


# ─── Garde-fou d'architecture : syntactic-only (pas de lookup muet) ──────────

def test_llota_absent_de_la_whitelist_ref_info():
    """v1 = validation syntaxique SEULE. LLOTA ne doit PAS entrer dans la
    whitelist PROGRAMMES de logx_ref_info.js : sinon le relevé « fiche »
    interrogerait /activation_db/lookup?program=LLOTA, pour lequel AUCUNE
    branche dispatcher n'existe -> lookup muet, et test_ref_info_dispatcher_
    parite.py rougirait (invariant PROGRAMMES ⊆ dispatcher)."""
    src = _lire('logx_ref_info.js')
    m = re.search(r'var\s+PROGRAMMES\s*=\s*\{([^}]*)\}', src)
    assert m, 'PROGRAMMES introuvable dans logx_ref_info.js'
    assert 'LLOTA' not in m.group(1), (
        "LLOTA ne doit pas être dans PROGRAMMES (aucune branche dispatcher "
        "-> lookup muet + parité cassée)")


def test_llota_pas_dans_le_catalogue_ui():
    """ACTIVATION_DB_PROGRAMS = programmes à CATALOGUE (recherche/à proximité).
    LLOTA n'en a pas (syntactic-only) -> ne doit pas y figurer."""
    src = _lire('logx_configuration.js')
    m = re.search(r'ACTIVATION_DB_PROGRAMS\s*=\s*\{(.*?)\n\}', src, re.S)
    assert m, 'ACTIVATION_DB_PROGRAMS introuvable'
    assert not re.search(r'\bLLOTA\s*:', m.group(1)), (
        "LLOTA ne doit pas être une clé de ACTIVATION_DB_PROGRAMS (pas de catalogue)")


# ─── Câblage UI : LLOTA réellement sélectionnable (portable ET chasseur) ─────

def test_llota_dans_les_listes_portables_js():
    src = _lire('logx_logbook.js')
    m_ref = re.search(r'REF_PROGRAMS\s*=\s*\[([^\]]*)\]', src)
    assert m_ref and "'LLOTA'" in m_ref.group(1), \
        "LLOTA absent de REF_PROGRAMS (sélecteur MES RÉFÉRENCES portable)"
    m_min = re.search(r'ACT_MIN\s*=\s*\{([^}]*)\}', src)
    assert m_min and re.search(r'LLOTA\s*:\s*10', m_min.group(1)), \
        "LLOTA:10 absent de ACT_MIN (seuil de progression UI)"


def test_llota_option_dans_les_selecteurs_html():
    # MON programme portable (CONFIG) + programme du correspondant (LOGBOOK)
    assert 'value="LLOTA"' in _lire('logx_configuration.html'), \
        "option LLOTA absente du sélecteur activation_program (CONFIG)"
    assert 'value="LLOTA"' in _lire('logx_logbook.html'), \
        "option LLOTA absente du sélecteur du correspondant (#theirRefProg)"
