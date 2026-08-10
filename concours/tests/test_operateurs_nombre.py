# -*- coding: utf-8 -*-
"""Choix DIRECT du nombre d'operateurs, et plafond reellement atteignable.

Deux besoins exprimes par des utilisateurs :

1) « je veux pouvoir choisir un nombre d'operateurs avant de faire ma liste » —
   il fallait cliquer « Ajouter un operateur » une fois par ligne, soit neuf
   clics pour une equipe de dix. Un champ de saisie directe a ete ajoute.

2) Le plafond etait de 5 en CONCOURS/EXPEDITION. Un operateur a 10 en
   DXpedition, ou une equipe de 9 en contest IOTA (cas rapporte), etait
   simplement BLOQUE, sans recours : impossible de declarer son equipe. La
   limite n'avait aucune justification technique — RADIOCLUB tournait deja a
   40 avec le meme export EDI (au-dela de 2 operateurs, tout le monde passe
   par Remarks, que l'on soit 6 ou 30).

Le VRAI code est extrait du fichier livre et execute dans un moteur JS reel
(V8 via py_mini_racer), comme tests/test_config_bands_modes_from_server.py :
une reecriture pourrait diverger de ce qui tourne chez l'utilisateur.
"""
import os
import re

import pytest

py_mini_racer = pytest.importorskip(
    'py_mini_racer', reason='py_mini_racer absent (voir requirements.txt)')

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML = os.path.join(BASE, 'logx_configuration.html')


def _source():
    with open(HTML, encoding='utf-8') as f:
        return f.read()


def _extraire(nom, src):
    """Extrait `function <nom>(...){...}` par comptage d'accolades."""
    m = re.search(r'function\s+' + re.escape(nom) + r'\s*\(', src)
    assert m, '%s() introuvable dans logx_configuration.html' % nom
    i = src.index('{', m.end() - 1)
    profondeur = 0
    for j in range(i, len(src)):
        if src[j] == '{':
            profondeur += 1
        elif src[j] == '}':
            profondeur -= 1
            if profondeur == 0:
                return src[m.start():j + 1]
    raise AssertionError('accolade fermante de %s() introuvable' % nom)


@pytest.mark.parametrize('mode,attendu', [
    ('simple', 1),          # mono-operateur par conception
    ('expedition', 40),     # 10 operateurs en DXpedition doivent passer
    ('contest', 40),        # equipe de 9 en IOTA doit passer
    ('radioclub', 40),
])
def test_plafond_par_mode(mode, attendu):
    ctx = py_mini_racer.MiniRacer()
    ctx.eval('var __mode = %r; function getUsageMode(){ return __mode; }' % mode)
    ctx.eval(_extraire('opRowCap', _source()))
    assert ctx.eval('opRowCap()') == attendu


def test_dix_operateurs_sont_atteignables_hors_mode_simple():
    """Le besoin exprime, teste tel quel : 10 doit passer sans etre rabote."""
    ctx = py_mini_racer.MiniRacer()
    ctx.eval("function getUsageMode(){ return 'expedition'; }")
    ctx.eval(_extraire('opRowCap', _source()))
    assert ctx.eval('Math.min(10, opRowCap())') == 10


def test_le_champ_de_saisie_du_nombre_existe():
    """Sans ce champ, on retombe sur « un clic par operateur »."""
    src = _source()
    assert 'id="opCountInput"' in src, 'champ de saisie du nombre absent'
    assert 'setOperatorCount(' in src, 'aucun appel a setOperatorCount'


def test_reduire_le_nombre_demande_confirmation_si_saisie_existante():
    """Garde-fou contre une perte de donnees SILENCIEUSE : reduire l'effectif
    supprime les DERNIERES lignes. Si elles contiennent deja un indicatif,
    l'utilisateur doit etre prevenu — la veille d'un concours, perdre une
    saisie sans un mot serait la pire des surprises."""
    fn = _extraire('setOperatorCount', _source())
    # _confirmConfigBanner() (bandeau non bloquant, chantier dialogues non
    # bloquants, 10/08/2026) a remplacé confirm() natif.
    assert '_confirmConfigBanner(' in fn, (
        'setOperatorCount() supprime des lignes sans jamais demander '
        'confirmation')
    assert 'operatorRowFilled(' in fn, (
        'la confirmation doit dependre de la presence reelle d une saisie, '
        'pas etre demandee a chaque reduction')


def test_setOperatorCount_ne_reconstruit_pas_la_grille():
    """ensureOperatorRows() VIDE la grille avant de la reconstruire : l'appeler
    ici effacerait les operateurs deja saisis. setOperatorCount doit passer par
    les ajouts/retraits incrementaux, qui preservent l'existant."""
    fn = _extraire('setOperatorCount', _source())
    assert 'ensureOperatorRows' not in fn, (
        'setOperatorCount() passe par ensureOperatorRows() : les saisies '
        'existantes seraient effacees')
    assert 'addOperatorRow()' in fn and 'removeLastOperatorRow()' in fn
