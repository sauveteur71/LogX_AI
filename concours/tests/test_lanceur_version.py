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
BAT = os.path.join(RACINE, 'LANCER_LOGX_AI.bat')

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
    codes = (LI.OUVRIR_SEULEMENT, LI.VERSION_DIFFERENTE, LI.PORT_OCCUPE,
             LI.PAS_DEMARRE)
    assert 1 not in codes
    assert len(set(codes)) == 4


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


# ─── L'attente du démarrage ──────────────────────────────────────────────────

class _Horloge:
    """Temps simulé : les tests n'attendent jamais 40 secondes pour de vrai."""

    def __init__(self):
        self.t = 0.0

    def maintenant(self):
        return self.t

    def dormir(self, s):
        self.t += s


def test_attendre_rend_la_main_des_que_le_serveur_repond(monkeypatch):
    reponses = [None, None, '0.9-beta7']
    monkeypatch.setattr(S, 'sonde_sans_bind',
                        lambda *a, **k: reponses.pop(0))
    h = _Horloge()
    code, msg = LI.attendre(port=PORT_TEST, version_locale='0.9-beta7',
                            horloge=h.maintenant, dormir=h.dormir)
    assert code == LI.OUVRIR_SEULEMENT and msg == ''
    assert reponses == []


def test_attendre_ne_se_lie_JAMAIS_au_port(monkeypatch):
    """LE piège de ce correctif. probe() ouvre réellement le port pour tester
    s'il est libre ; l'appeler en boucle pendant que le serveur cherche à se
    lier lui volerait le port — sous Windows, allow_reuse_address étant
    volontairement désactivé, son bind échouerait en WinError 10048.
    L'attente aurait PROVOQUÉ la panne qu'elle surveille."""
    appels = []
    monkeypatch.setattr(S, '_bind_test',
                        lambda *a, **k: appels.append(a) or (True, ''))
    monkeypatch.setattr(S, 'sonde_sans_bind',
                        lambda *a, **k: '0.9-beta7')
    h = _Horloge()
    LI.attendre(port=PORT_TEST, version_locale='0.9-beta7',
                horloge=h.maintenant, dormir=h.dormir)
    assert appels == [], 'aucun bind ne doit avoir lieu pendant l attente'


def test_sonde_sans_bind_ne_se_lie_pas_non_plus(monkeypatch):
    """Garde-fou au niveau du module : si sonde_sans_bind se remettait à
    binder, le test ci-dessus deviendrait vert pour de mauvaises raisons."""
    appels = []
    monkeypatch.setattr(S, '_bind_test',
                        lambda *a, **k: appels.append(a) or (True, ''))
    monkeypatch.setattr(S, '_fetch_signature',
                        lambda *a, **k: ({'app_version': '0.9-beta7'}, ''))
    assert S.sonde_sans_bind(PORT_TEST) == '0.9-beta7'
    assert appels == []


def test_attendre_abandonne_au_bout_du_delai(monkeypatch):
    monkeypatch.setattr(S, 'sonde_sans_bind', lambda *a, **k: None)
    h = _Horloge()
    code, msg = LI.attendre(delai_max=40.0, pas=0.5, port=PORT_TEST,
                            horloge=h.maintenant, dormir=h.dormir)
    assert code == LI.PAS_DEMARRE
    assert h.t >= 40.0
    assert 'MINIMISEE' in msg, (
        'le message doit dire ou lire la cause : la fenetre du serveur est '
        'minimisee, c est tout le probleme')


def test_attendre_tolere_un_localhost_lent(monkeypatch):
    """DEFAUT REEL (F4GLD 02/09) : sous un antivirus qui inspecte 127.0.0.1
    (~2 s/requete, Avast Web Shield), la sonde par defaut (budget 2.0) tombait
    pile sur la latence -> sonde None -> le lanceur croyait le serveur absent
    et N'OUVRAIT PAS le navigateur, serveur pourtant demarre. L'attente
    post-demarrage doit donc passer a sonde_sans_bind un timeout ET un budget
    GENEREUX, franchement au-dessus de cette latence."""
    vus = {}

    def faux_sonde(port, *a, **k):
        vus['timeout'] = k.get('timeout')
        vus['budget'] = k.get('budget')
        return '0.9-beta7'

    monkeypatch.setattr(S, 'sonde_sans_bind', faux_sonde)
    h = _Horloge()
    code, _ = LI.attendre(port=PORT_TEST, version_locale='0.9-beta7',
                          horloge=h.maintenant, dormir=h.dormir)
    assert code == LI.OUVRIR_SEULEMENT
    # marge nette au-dessus de la latence antivirus mesuree (~2 s) :
    assert (vus['timeout'] or 0) >= 4.0, 'timeout d attente trop court pour un localhost lent'
    assert (vus['budget'] or 0) >= 4.0, 'budget d attente trop court pour un localhost lent'
    # et strictement plus genereux que le defaut de la sonde de pre-controle
    # (sans quoi le durcissement n aurait rien change au cas qui a echoue) :
    assert (vus['budget'] or 0) > S._HTTP_BUDGET


def test_le_message_d_echec_reste_en_ascii(monkeypatch):
    """Trouvé en l'exécutant pour de vrai : mes guillemets « » ressortaient
    en mojibake dans la console Windows."""
    monkeypatch.setattr(S, 'sonde_sans_bind', lambda *a, **k: None)
    monkeypatch.setattr(LI, 'journal_erreurs_frais', lambda *a, **k: '')
    h = _Horloge()
    _, msg = LI.attendre(delai_max=1.0, pas=0.5, port=PORT_TEST,
                         horloge=h.maintenant, dormir=h.dormir)
    assert msg.isascii(), [c for c in msg if not c.isascii()]


def test_le_journal_accentue_ne_casse_pas_le_message(tmp_path, monkeypatch):
    """DÉFAUT TROUVÉ PAR LA SUITE COMPLÈTE, pas par relecture — et pas un
    caprice de test. Tout ce module est écrit en ASCII à la main, mais la fin
    de errors.log vient d'ailleurs : c'est une trace Python, dont les messages
    et les chemins de fichiers portent des accents. Le message de diagnostic
    redevenait donc mojibaké dans la console Windows, précisément au moment où
    l'utilisateur a besoin de le lire.

    Le test d'origine lisait le VRAI errors.log du poste : il passait ou non
    selon ce que la suite venait d'y écrire. Celui-ci fixe le contenu."""
    import logx_errorlog
    journal = tmp_path / 'errors.log'
    journal.write_text(
        "Traceback : fichier déjà supprimé, opération annulée\n"
        "  File \"C:\\Users\\opérateur\\Bureau\\log.py\", line 3\n",
        encoding='utf-8')
    monkeypatch.setattr(logx_errorlog, 'log_path', lambda: str(journal))
    monkeypatch.setattr(S, 'sonde_sans_bind', lambda *a, **k: None)
    h = _Horloge()
    _, msg = LI.attendre(delai_max=1.0, pas=0.5, port=PORT_TEST,
                         horloge=h.maintenant, dormir=h.dormir)
    assert msg.isascii(), [c for c in msg if not c.isascii()]
    # Repli lisible, pas une bouillie : les accents tombent, le texte reste.
    assert 'deja supprime' in msg
    assert 'operateur' in msg


def test_attendre_n_ouvre_rien_si_c_est_une_autre_version_qui_repond(monkeypatch):
    """Course entre deux lancements : le serveur qu'on vient de lancer s'est
    effacé devant une instance déjà en place."""
    monkeypatch.setattr(S, 'sonde_sans_bind',
                        lambda *a, **k: '0.9-beta5')
    h = _Horloge()
    code, msg = LI.attendre(port=PORT_TEST, version_locale='0.9-beta7',
                            horloge=h.maintenant, dormir=h.dormir)
    assert code == LI.VERSION_DIFFERENTE
    assert '0.9-beta5' in msg and '0.9-beta7' in msg


def test_journal_d_erreurs_perime_n_est_PAS_affiche(tmp_path, monkeypatch):
    """Même famille d'erreur que celle qui m'a fait annoncer une suite verte
    en lisant un rapport de la veille : un journal d'erreurs n'est pas effacé
    entre deux lancements. L'afficher sans regarder sa date désignerait la
    panne de la semaine dernière comme cause du problème du jour."""
    import logx_errorlog
    vieux = tmp_path / 'errors.log'
    vieux.write_text('panne de la semaine derniere\n', encoding='utf-8')
    monkeypatch.setattr(logx_errorlog, 'log_path', lambda: str(vieux))
    mtime = os.path.getmtime(str(vieux))
    assert LI.journal_erreurs_frais(maintenant=mtime + 10) != ''
    assert LI.journal_erreurs_frais(maintenant=mtime + 10_000) == ''


def test_journal_d_erreurs_absent_ne_fait_pas_echouer_le_diagnostic(monkeypatch):
    """Le diagnostic ne doit pas planter parce que le diagnostic a raté."""
    import logx_errorlog
    monkeypatch.setattr(logx_errorlog, 'log_path', lambda: '/n/existe/pas.log')
    assert LI.journal_erreurs_frais() == ''


def test_le_mode_attente_est_atteignable_en_ligne_de_commande(monkeypatch):
    """C'est `--attendre` que le .bat appelle : si l'argument n'était pas lu,
    le lanceur relancerait le pré-contrôle et croirait le port libre."""
    monkeypatch.setattr(S, 'sonde_sans_bind',
                        lambda *a, **k: LI.APP_VERSION)
    monkeypatch.setattr(S, 'probe',
                        lambda *a, **k: pytest.fail('probe() ne doit pas etre '
                                                    'appelee en mode attente'))
    assert LI.main(['--attendre']) == LI.OUVRIR_SEULEMENT


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
                      LI.PORT_OCCUPE}, (
        'PAS_DEMARRE (13) est volontairement absent : apres l attente, tout '
        'code autre que 10 tombe dans :probleme, ce qui couvre aussi les '
        'codes futurs')


def test_seul_le_code_10_mene_au_navigateur(bat):
    """Invariant central du lanceur : on n'ouvre une page que si un serveur de
    LA BONNE version a répondu. Toute autre issue doit mener à :probleme."""
    for ligne in bat.splitlines():
        if 'goto ouvre_browser' in ligne or 'goto probleme' in ligne:
            if 'ouvre_browser' in ligne and '"%ETAT%"' in ligne:
                assert '"%ETAT%"=="10"' in ligne, ligne
    # Le bloc parenthésé du cas 10 (pré-contrôle) est la seule autre porte.
    bloc10 = bat[bat.index('"%ETAT%"=="10" ('):]
    bloc10 = bloc10[:bloc10.index('\n)')]
    assert 'goto ouvre_browser' in bloc10


def test_le_lanceur_sort_sans_rien_ouvrir_sur_les_cas_de_refus(bat):
    """11 et 12 doivent partir vers :probleme, qui se termine par un exit —
    jamais retomber dans :ouvre_browser."""
    for code in ('11', '12'):
        assert 'if "%%ETAT%%"=="%s" goto probleme' % code in bat, code
    bloc = bat[bat.index(':probleme'):]
    bloc = bloc[:bloc.index(':ouvre_browser')]
    assert 'exit /b' in bloc


def test_le_lanceur_attend_la_reponse_du_serveur_pas_un_delai_fixe(bat):
    """DÉFAUT CORRIGÉ. Le lanceur faisait `timeout /t 3` puis ouvrait le
    navigateur quoi qu'il arrive. La fenêtre du serveur étant minimisée
    (`start /MIN`), un refus de démarrer restait invisible et la page
    s'ouvrait sur une adresse morte. Et 3 s n'était qu'une devinette : sur un
    poste lent, le navigateur s'ouvrait trop tôt sur la même erreur alors que
    tout allait bien."""
    assert '--attendre' in bat
    apres_demarrage = bat[bat.index('start "LogX Serveur"'):]
    apres_demarrage = apres_demarrage[:apres_demarrage.index(':ouvre_browser')]
    assert '--attendre' in apres_demarrage, (
        "l'attente doit venir APRES le lancement du serveur")
    # Hors commentaires : ceux-ci CITENT l'ancien `timeout /t 3` pour expliquer
    # ce qui a ete corrige, et faisaient echouer l'assertion a tort.
    code_seul = [l for l in apres_demarrage.splitlines()
                 if not l.strip().startswith('::')]
    assert not any('timeout /t' in l for l in code_seul), (
        'plus aucune attente en aveugle entre le demarrage et le navigateur')


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
