# -*- coding: utf-8 -*-
"""Le lanceur doit ouvrir la BONNE version, ou n'ouvrir rien du tout.

DÉFAUT RÉEL, constaté sur ce poste le 27/07/2026. LANCER_RADIOCONTEST.bat
testait le port avec `curl http://localhost:8080/` : dès que quelque chose
répondait, il affichait « [OK] Serveur deja en route » et ouvrait le
navigateur, SANS jamais exécuter `python logx_serveur.py`. Or c'est
logx_serveur.py qui porte la détection d'instance déjà lancée. Un serveur
laissé en route depuis la veille servait la 0.9-beta5 ; après installation de
la 0.9-beta7, relancer le .bat rouvrait la beta5 en annonçant que tout allait
bien. Rien, nulle part, ne rapprochait les deux numéros de version.

Le mécanisme de détection existait déjà et était correct (logx_singleton) —
le lanceur l'empêchait simplement de s'exécuter. C'est le genre de panne qui
ne se voit pas : tout affiche « OK », et l'utilisateur conclut que la mise à
jour a échoué. D'où ces tests, en deux moitiés :

  1. la décision elle-même (decider) — testable sans réseau ni process ;
  2. LE CÂBLAGE DU .BAT, qui est la moitié qui a réellement lâché : le module
     peut être parfait et le lanceur continuer de le contourner.
"""
import os
import re
import subprocess
import sys

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CONCOURS not in sys.path:
    sys.path.insert(0, CONCOURS)

import logx_instance as LI       # noqa: E402
import logx_singleton as S       # noqa: E402

RACINE = os.path.dirname(CONCOURS)
BAT = os.path.join(RACINE, 'LANCER_RADIOCONTEST.bat')

PORT_TEST = 8080


def _logx(version):
    return {'state': S.LOGX, 'version': version, 'detail': ''}


# ─── La décision ─────────────────────────────────────────────────────────────

def test_meme_version_on_ouvre_seulement_le_navigateur():
    """Cas nominal légitime : l'utilisateur relance le .bat alors que son
    serveur tourne déjà. Rien à redémarrer, on lui rend sa fenêtre."""
    code, msg = LI.decider(_logx('0.9-beta7'), version_locale='0.9-beta7',
                           port=PORT_TEST)
    assert code == LI.OUVRIR_SEULEMENT
    assert msg == ''


def test_version_differente_on_n_ouvre_RIEN():
    """Le coeur du défaut : ouvrir le navigateur ici afficherait l'ancienne
    version en laissant croire que la mise à jour n'a pas pris."""
    code, msg = LI.decider(_logx('0.9-beta5'), version_locale='0.9-beta7',
                           port=PORT_TEST)
    assert code == LI.VERSION_DIFFERENTE
    assert code != LI.OUVRIR_SEULEMENT


def test_le_message_donne_LES_DEUX_numeros():
    """Ce qui manquait à l'utilisateur : voir 'beta5 répond' et 'beta7
    installée' côte à côte. Décrire le mécanisme ne suffisait pas."""
    _, msg = LI.decider(_logx('0.9-beta5'), version_locale='0.9-beta7',
                        port=PORT_TEST)
    assert '0.9-beta5' in msg
    assert '0.9-beta7' in msg


def test_version_non_communiquee_traitee_comme_differente():
    """Une instance qui ne renvoie pas app_version est antérieure au champ,
    donc plus ancienne que ce dossier. La croire à jour rouvrirait du vieux
    code en silence — le défaut d'origine, sous un autre déguisement."""
    code, _ = LI.decider(_logx(None), version_locale='0.9-beta7',
                         port=PORT_TEST)
    assert code == LI.VERSION_DIFFERENTE


def test_port_libre_on_demarre():
    code, msg = LI.decider({'state': S.FREE, 'version': None, 'detail': ''},
                           port=PORT_TEST)
    assert code == LI.DEMARRER
    assert msg == ''


def test_port_partage_on_demarre_quand_meme_mais_on_previent():
    """SHARED = un tiers écoute le port sans nous prendre nos adresses (cas
    banal d'un écouteur dual-stack). Refuser de démarrer serait une
    régression : le logiciel ne se lancerait plus du tout sur ces postes."""
    code, msg = LI.decider({'state': S.SHARED, 'version': None,
                            'detail': 'ecouteur [::]'}, port=PORT_TEST)
    assert code == LI.DEMARRER
    assert str(PORT_TEST) in msg


def test_port_pris_par_un_tiers_on_s_arrete():
    code, msg = LI.decider({'state': S.OTHER, 'version': None,
                            'detail': 'reponse HTTP 401'}, port=PORT_TEST)
    assert code == LI.PORT_OCCUPE
    assert 'AUTRE' in msg


def test_le_message_reste_en_ascii_strict():
    """Même contrainte que logx_singleton : ce texte s'affiche dans une
    console Windows dont la page de code n'est pas prévisible. Un accent y
    ressortirait mojibaké au moment précis où il faut lire une consigne."""
    _, msg = LI.decider(_logx('0.9-beta5'), version_locale='0.9-beta7',
                        port=PORT_TEST)
    assert msg.isascii(), [c for c in msg if not c.isascii()]


# ─── Les codes de sortie ─────────────────────────────────────────────────────

def test_aucun_code_utile_ne_vaut_1():
    """Python sort avec 1 sur toute exception non rattrapée. Si un code utile
    valait 1, un simple ImportError dans ce pré-contrôle aurait fait ouvrir le
    navigateur (ou refuser le démarrage) sans qu'aucun serveur ne tourne."""
    codes = (LI.OUVRIR_SEULEMENT, LI.VERSION_DIFFERENTE, LI.PORT_OCCUPE)
    assert 1 not in codes
    assert len(set(codes)) == 3


def test_un_plantage_du_precontrole_fait_demarrer_le_serveur():
    """Le repli doit être 'démarrer', jamais 'ne rien faire' : logx_serveur.py
    refait la même sonde pour son propre compte."""
    prog = ('import sys; sys.path.insert(0, %r); import logx_instance;\n'
            'raise ImportError("simulation")' % CONCOURS)
    r = subprocess.run([sys.executable, '-c', prog], capture_output=True)
    assert r.returncode == 1              # le code du plantage...
    assert r.returncode not in (LI.OUVRIR_SEULEMENT, LI.VERSION_DIFFERENTE,
                                LI.PORT_OCCUPE)   # ...n'est aucun code utile


def test_le_code_de_sortie_arrive_reellement_au_shell():
    """main() a beau renvoyer le bon entier, c'est sys.exit qui le transmet au
    .bat. Vérifié pour de vrai, dans un process séparé."""
    prog = (
        'import sys; sys.path.insert(0, %r)\n'
        'import logx_singleton, logx_instance\n'
        'logx_singleton.probe = lambda *a, **k: '
        '{"state": logx_singleton.LOGX, "version": "0.0-vieille", "detail": ""}\n'
        'sys.exit(logx_instance.main())\n' % CONCOURS)
    r = subprocess.run([sys.executable, '-c', prog], capture_output=True)
    assert r.returncode == LI.VERSION_DIFFERENTE
    assert b'0.0-vieille' in r.stdout


# ─── Le câblage du lanceur (la moitié qui a lâché) ───────────────────────────

@pytest.fixture(scope='module')
def bat():
    with open(BAT, encoding='utf-8', errors='replace') as f:
        return f.read()


def test_le_lanceur_ne_court_circuite_plus_avec_curl(bat):
    """LA régression à empêcher. `curl` répondait « quelque chose écoute »,
    jamais « la bonne version écoute » — et faisait sauter l'appel à
    logx_serveur.py, seul porteur de la détection."""
    curl = [l for l in bat.splitlines()
            if 'curl' in l.lower() and not l.strip().startswith('::')]
    assert curl == [], curl


def test_le_lanceur_appelle_le_precontrole(bat):
    assert 'logx_instance.py' in bat


def test_le_lanceur_teste_les_codes_reellement_definis(bat):
    """Les codes vivent dans logx_instance.py ; le .bat les recopie en dur —
    il n'a pas d'autre choix. Ce test est le lien qui empêche les deux de
    diverger en silence, ce qui rendrait le contrôle inopérant sans erreur."""
    testes = set(int(n) for n in re.findall(r'"%ETAT%"=="(\d+)"', bat))
    assert testes == {LI.OUVRIR_SEULEMENT, LI.VERSION_DIFFERENTE,
                      LI.PORT_OCCUPE}


def test_le_lanceur_n_ouvre_pas_le_navigateur_sur_une_autre_version(bat):
    """Il doit sortir AVANT :ouvre_browser. Un `goto ouvre_browser` dans cette
    branche ramènerait exactement le défaut d'origine."""
    bloc = bat[bat.index('"%ETAT%"=="11"'):]
    bloc = bloc[:bloc.index(')')]
    assert 'exit /b' in bloc
    assert 'ouvre_browser' not in bloc


def test_le_lanceur_ouvre_encore_le_navigateur_a_version_egale(bat):
    """L'inverse compte autant : relancer le .bat sur son propre serveur en
    cours doit rendre la fenêtre, pas exiger un redémarrage."""
    bloc = bat[bat.index('"%ETAT%"=="10"'):]
    bloc = bloc[:bloc.index(')')]
    assert 'goto ouvre_browser' in bloc


# ─── Le serveur lui-même annonce le décalage de version ──────────────────────

def test_le_serveur_passe_sa_propre_version_a_la_sonde():
    """Le .exe (LogXAI.exe) ne passe jamais par le .bat : il tombe dans le
    même piège par son propre chemin. C'est logx_serveur.py qui doit alors
    nommer les deux versions."""
    with open(os.path.join(CONCOURS, 'logx_serveur.py'), encoding='utf-8') as f:
        src = f.read()
    bloc = src[src.index('message_deja_lance'):]
    bloc = bloc[:400]
    assert 'version_locale=APP_VERSION' in bloc


def test_message_deja_lance_se_tait_si_les_versions_concordent():
    """Pas de faux avertissement quand tout va bien."""
    msg = S.message_deja_lance(8080, '0.9-beta7', version_locale='0.9-beta7')
    assert 'ATTENTION' not in msg


def test_message_deja_lance_sans_version_locale_reste_l_ancien_texte():
    """Appelé sans le nouveau paramètre (autres appelants, tests existants),
    le message ne doit pas changer de forme."""
    msg = S.message_deja_lance(8080, '0.9-beta5')
    assert 'ATTENTION' not in msg
    assert '0.9-beta5' in msg
