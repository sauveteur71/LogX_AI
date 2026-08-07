# -*- coding: utf-8 -*-
"""Vocabulaire radioamateur : plus d'« activation » ni d'« activateur » à l'écran.

DEMANDE UTILISATEUR, mot pour mot : « supprime ce language cibiste avec
ACTIVATION ACTIVATEUR etc on est radioamateur ! »

CE QUI A ÉTÉ CHANGÉ ET CE QUI NE L'A PAS ÉTÉ. Seuls les textes VUS par
l'opérateur. Les identifiants de code — activation_program, my_activation_ref,
logx_activation.py, applyActivationMode — gardent leur nom : ils n'apparaissent
jamais à l'écran, et les renommer obligerait à migrer la configuration et les
sauvegardes déjà écrites sur le disque, pour zéro changement visible.

L'anglais et l'allemand gardent « activation » / « Aktivierung » : ce sont les
termes officiels de POTA, SOTA et WWFF dans ces langues, employés par leurs
propres règlements et leurs API. Traduire n'est pas transposer un choix
d'écriture français.

LE PIÈGE QUE CE FICHIER SURVEILLE. Les clés du dictionnaire i18n SONT les
phrases françaises. Changer le texte d'une page sans changer la clé ne casse
rien de visible en français — mais les sept traductions décrochent en silence,
et personne ne le remarque avant qu'un utilisateur étranger ne se plaigne. Les
deux doivent bouger ensemble, et c'est ce qui est vérifié ici.
"""
import io
import json
import os
import re
import sys

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CONCOURS not in sys.path:
    sys.path.insert(0, CONCOURS)


def _lire(nom):
    return io.open(os.path.join(CONCOURS, nom), encoding='utf-8').read()


# Les phrases françaises qui sont À LA FOIS dans une page et clés du
# dictionnaire. C'est exactement l'ensemble où une divergence est silencieuse.
PHRASES_TRADUITES = [
    ('logx_chasse.html', 'STATIONS POTA EN DIRECT'),
    ('logx_chasse.html', 'STATIONS SOTA EN DIRECT'),
    ('logx_chasse.html', 'STATIONS WWFF EN DIRECT'),
    ('logx_chasse.html', "Aucun trafic POTA signalé pour l'instant."),
    ('logx_chasse.html', "Aucun trafic SOTA signalé pour l'instant."),
    ('logx_chasse.html', "Aucun trafic WWFF signalé pour l'instant."),
    ('logx_chasse.html', "Aucun trafic WCA/COTA annoncé pour l'instant."),
]


def _cles_i18n():
    """Toutes les clés du dictionnaire, relues comme du JSON pour restituer
    fidèlement les échappements (apostrophes, accents, retours à la ligne)."""
    src = _lire('logx_i18n.js')
    cles = set()
    for m in re.finditer(r'"(?:[^"\\]|\\.)*"\s*:', src):
        brut = m.group(0).rstrip().rstrip(':').rstrip()
        try:
            cles.add(json.loads(brut))
        except ValueError:
            pass
    return cles


@pytest.mark.parametrize('fichier,phrase', PHRASES_TRADUITES)
def test_la_phrase_de_la_page_est_bien_une_cle_de_traduction(fichier, phrase):
    """Si ce test tombe, la page est en français correct mais ne se traduit
    plus dans AUCUNE des sept langues — panne parfaitement invisible ici."""
    assert phrase in _lire(fichier), 'absente de la page'
    assert phrase in _cles_i18n(), 'presente dans la page mais plus traduite'


def test_aucune_ancienne_cle_orpheline_ne_subsiste():
    """Une clé restée sur l'ancien libellé ne casse rien mais ne sert plus à
    rien : elle ne sera jamais retrouvée, et masque le fait qu'il manque une
    traduction."""
    orphelines = [k for k in _cles_i18n()
                  if re.search(r'\bactivat(eur|ion)s?\b', k, re.I)]
    assert orphelines == [], orphelines


# ─── Le vocabulaire visible ──────────────────────────────────────────────────

MOT = re.compile(r'activat(eur|ion)s?', re.I)
# Identifiants de code : jamais vus par l'opérateur, volontairement conservés.
IDENT = re.compile(
    r'activation(Bar|Suggestions|Validation|Nearby|Program|Timer|Ref|Mode|Wca|Search|_program|_ref|_db)|'
    r'Activation(Mode|Program|Ref|Bar|Refs)|myActivationRef|selfSpotActivation|'
    r'refreshActivation|applyActivationMode|searchActivation|_activationSearch|'
    r'logx_activation|/activation|desactivation|désactivation', re.I)
COMMENTAIRE = re.compile(r'^\s*(//|/\*|\*|<!--|#)')


@pytest.mark.parametrize('fichier', [
    'logx_configuration.html', 'logx_logbook.html', 'logx_mobile.html',
    'logx_panel.html',
])
def test_plus_aucun_texte_visible_ne_porte_le_mot(fichier):
    restes = []
    for n, ligne in enumerate(_lire(fichier).split('\n'), 1):
        if not MOT.search(ligne) or COMMENTAIRE.match(ligne):
            continue
        if MOT.search(IDENT.sub('', ligne)):
            restes.append('%d: %s' % (n, ligne.strip()[:100]))
    assert restes == [], restes


def test_la_section_CONFIG_porte_le_nouveau_nom():
    src = _lire('logx_configuration.html')
    assert 'EXPÉDITION / PORTABLE' in src
    assert 'EXPÉDITION / ACTIVATION' not in src


def test_LES_MESSAGES_QUI_CITENT_LA_SECTION_ONT_SUIVI():
    """Piège déjà rencontré sur ce projet : renommer un libellé et laisser des
    messages qui renvoient à l'ancien. L'opérateur cherche alors dans CONFIG un
    menu qui n'existe plus, et conclut que le logiciel ment.

    EV-7 : le message SOTA qui cite la section (dans selfSpotSota()) a été
    extrait de logx_logbook.js vers logx_popout_selfspot.js."""
    for f in ('logx_sota_spot.py', 'logx_logbook.js', 'logx_popout_selfspot.js'):
        assert 'EXPÉDITION/ACTIVATION' not in _lire(f), f
    for f in ('logx_sota_spot.py', 'logx_popout_selfspot.js'):
        assert 'EXPÉDITION/PORTABLE' in _lire(f), f


def test_le_mot_DESACTIVATION_n_a_pas_ete_emporte():
    """« désactivation » n'a rien à voir : c'est l'arrêt d'un enregistreur.
    Un remplacement trop large l'aurait avalé au passage."""
    assert 'désactivation volontaire' in _lire('logx_logbook.js')


def test_l_anglais_garde_le_terme_officiel_des_programmes():
    """POTA, SOTA et WWFF disent « activator » et « activation » dans leurs
    propres règlements. Le choix d'écriture est français, pas universel."""
    src = _lire('logx_i18n.js')
    assert 'LIVE POTA ACTIVATORS' in src
    assert 'No POTA activation currently reported.' in src
