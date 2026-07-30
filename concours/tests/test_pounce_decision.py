# -*- coding: utf-8 -*-
"""Wait-and-Pounce niveaux 3 et 4 : le moteur qui décide d'appeler tout seul.

C'est le module où le logiciel se met à émettre sans qu'on ait rien touché.
Il est écrit PUR — aucune socket, aucun HTTP — précisément pour que tout le
raisonnement, y compris les cas qui feraient émettre, soit exerçable ici sans
qu'un seul octet ne parte sur l'air.

LES GARDE-FOUS SONT LE VRAI SUJET DE CE FICHIER. Une station qui émet sans
personne devant elle a plusieurs façons de mal finir, et chacune a son test :
tourner des heures, marteler une station sourde, sauter de QSO en QSO sans en
finir aucun, ou repartir toute seule après un redémarrage. Un garde-fou dont
on ne vérifie pas qu'il MORD est une décoration.

L'HORLOGE EST INJECTÉE. Vérifier une durée maximale en dormant huit heures
n'est pas une option ; et un test qui dort est un test qu'on finit par
désactiver.
"""
import os
import sys

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CONCOURS not in sys.path:
    sys.path.insert(0, CONCOURS)

import logx_pounce as p   # noqa: E402


class Horloge:
    """Horloge pilotée : le temps n'avance que quand on le décide."""

    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t

    def avancer(self, secondes):
        self.t += secondes


@pytest.fixture
def h():
    return Horloge()


@pytest.fixture
def s(h):
    sess = p.Session(horloge=h)
    sess.armer({'niveau': p.NIVEAU_APPELER, 'criteres': ['nouveau_pays']})
    return sess


def dec(call='DL1ABC', band='14', mode='FT8'):
    return {'call': call, 'band': band, 'mode': mode}


# ─── Armer : ce qui est refusé, et pourquoi ──────────────────────────────────

@pytest.mark.parametrize('niveau', [p.NIVEAU_SIGNALER, p.NIVEAU_ARMER])
def test_les_niveaux_1_et_2_n_ont_rien_a_armer(niveau, h):
    """Ils n'émettent jamais d'eux-mêmes : les « armer » n'aurait aucun sens et
    laisserait croire que la station est en train d'appeler."""
    res = p.Session(horloge=h).armer({'niveau': niveau, 'criteres': ['nouveau_pays']})
    assert res['ok'] is False and 'emettent jamais' in res['error']


def test_ARMER_SANS_AUCUN_CRITERE_EST_REFUSE(h):
    """« Appelle ce qui est intéressant » sans dire ce qui l'est voudrait dire
    « appelle tout le monde ». On refuse plutôt que de deviner — c'est le genre
    de défaut qui ne se voit qu'une fois la station lancée."""
    res = p.Session(horloge=h).armer({'niveau': p.NIVEAU_APPELER, 'criteres': []})
    assert res['ok'] is False and 'appellerait tout le monde' in res['error']


def test_un_reglage_illisible_degrade_vers_SIGNALER():
    """Le doute ne profite JAMAIS à l'émission. C'est l'inverse exact de la
    règle des filtres de spots, où le doute profite à l'affichage — dans les
    deux cas on dégrade vers l'inoffensif."""
    for brut in (None, 'nimportequoi', {'niveau': 99}, {'niveau': 'trois'}, []):
        assert p.reglages_valides(brut)['niveau'] == p.NIVEAU_SIGNALER


def test_la_duree_est_bornee():
    assert p.reglages_valides({'duree_min': 100000})['duree_min'] == p.DUREE_MAX_MIN
    assert p.reglages_valides({'duree_min': 0})['duree_min'] == 1
    assert p.reglages_valides({'duree_min': 'abc'})['duree_min'] == p.DUREE_DEFAUT_MIN


# ─── Le cas nominal ──────────────────────────────────────────────────────────

def test_une_entite_neuve_declenche_l_appel(s):
    d = s.decider(dec(), {'nouveau_pays': True})
    assert d['appeler'] is True and d['motif'] == 'entité jamais travaillée'


def test_une_station_sans_interet_n_est_pas_appelee(s):
    d = s.decider(dec(), {'nouveau_pays': False, 'besoin_lotw': True})
    assert d['appeler'] is False and d['motif'] == 'aucun critere satisfait'
    # ... sauf si le critère est coché
    s.armer({'niveau': p.NIVEAU_APPELER, 'criteres': ['nouveau_pays', 'besoin_lotw']})
    assert s.decider(dec(), {'besoin_lotw': True})['appeler'] is True


def test_UN_REFUS_DIT_TOUJOURS_POURQUOI(s):
    """Sans surveillance, c'est la seule trace de pourquoi la station n'a pas
    appelé un DX qu'on attendait. Un refus muet rendrait le niveau 4
    indébogable."""
    cas = [
        (dec(call=''), {}, 'indicatif vide'),
        (dec(), {}, 'aucun critere satisfait'),
    ]
    for d, i, attendu in cas:
        assert s.decider(d, i)['motif'] == attendu
    s.reglages['exclus'] = ['DL1ABC']
    assert s.decider(dec(), {'nouveau_pays': True})['motif'] == 'indicatif exclu'


# ─── Les garde-fous, un par un ───────────────────────────────────────────────

def test_GARDE_FOU_duree_la_session_s_arrete_TOUTE_SEULE(s, h):
    """Le garde-fou obligatoire du niveau 4. Sans lui, une session lancée le
    samedi soir émet encore le dimanche midi."""
    assert s.decider(dec(), {'nouveau_pays': True})['appeler'] is True
    h.avancer(p.DUREE_DEFAUT_MIN * 60 + 1)
    d = s.decider(dec(), {'nouveau_pays': True})
    assert d['appeler'] is False and d['motif'] == 'duree ecoulee'
    assert s.active is False, 'la session doit se desarmer elle-meme'


def test_GARDE_FOU_un_seul_appel_en_vol(s, h):
    """WSJT-X mène UN QSO à la fois. Ré-armer à chaque décodage le ferait
    sauter de station en station sans en terminer aucune."""
    s.noter_appel('DL1ABC', 'entité jamais travaillée')
    d = s.decider(dec(call='EA5XYZ'), {'nouveau_pays': True})
    assert d['appeler'] is False and 'DL1ABC en cours' in d['motif']


def test_un_appel_qui_n_aboutit_pas_libere_la_place(s, h):
    """Sinon une station qui ne répond jamais bloquerait la session entière."""
    s.noter_appel('DL1ABC')
    h.avancer(p.CYCLES_AVANT_ABANDON * p.DUREE_CYCLE_S + 1)
    assert s.decider(dec(call='EA5XYZ'), {'nouveau_pays': True})['appeler'] is True


def test_GARDE_FOU_pas_plus_de_trois_appels_a_la_meme_station(s):
    """Si elle n'a pas répondu en trois cycles, elle ne nous entend pas.
    Insister encombre la fréquence sans rien apporter."""
    for _ in range(p.CYCLES_AVANT_ABANDON):
        assert s.decider(dec(), {'nouveau_pays': True})['appeler'] is True
        s.noter_appel('DL1ABC')
        s.appel_en_cours = ''      # la station a fini son cycle sans repondre
    d = s.decider(dec(), {'nouveau_pays': True})
    assert d['appeler'] is False and 'sans reponse' in d['motif']


def test_GARDE_FOU_plafond_d_appels_desarme_la_session(s):
    """Filet contre l'emballement : en FT8 un QSO prend au mieux une minute.
    Trente appels en un quart d'heure signale un defaut, pas un bon week-end."""
    for i in range(p.PLAFOND_APPELS):
        s.noter_appel('ST%03d' % i)
        s.appel_en_cours = ''
    d = s.decider(dec(call='NOUVEAU'), {'nouveau_pays': True})
    assert d['appeler'] is False and 'plafond' in d['motif']
    assert s.active is False


def test_un_QSO_abouti_retire_la_station_des_candidats(s):
    s.noter_appel('DL1ABC')
    s.noter_qso('DL1ABC')
    assert s.appel_en_cours == ''
    assert s.decider(dec(), {'nouveau_pays': True})['appeler'] is False


def _arbre():
    """L'AST du module, pas son texte : chercher « logx_wsjtx » dans la source
    trouve aussi les commentaires qui expliquent pourquoi il n'y est pas. Une
    première version de ces deux tests tombait précisément là-dessus."""
    import ast
    with open(os.path.join(CONCOURS, 'logx_pounce.py'), encoding='utf-8') as f:
        return ast.parse(f.read())


def _noms_appeles(arbre):
    import ast
    noms = set()
    for n in ast.walk(arbre):
        if isinstance(n, ast.Call):
            f = n.func
            noms.add(f.attr if isinstance(f, ast.Attribute) else
                     getattr(f, 'id', ''))
    return noms


def _modules_importes(arbre):
    import ast
    mods = set()
    for n in ast.walk(arbre):
        if isinstance(n, ast.Import):
            mods.update(a.name.split('.')[0] for a in n.names)
        elif isinstance(n, ast.ImportFrom) and n.module:
            mods.add(n.module.split('.')[0])
    return mods


def test_UNE_SESSION_NE_SURVIT_PAS_A_UN_REDEMARRAGE():
    """Une station qui se remettrait à émettre toute seule après un
    redémarrage inopiné est exactement ce qu'il ne faut pas. La session vit en
    mémoire et n'est jamais persistée — donc aucune écriture sur disque."""
    assert p.session.active is False
    appeles = _noms_appeles(_arbre())
    for interdit in ('open', 'dump', 'save_json_atomic', 'write_text'):
        assert interdit not in appeles, 'le module ne doit rien ecrire sur disque'


# ─── Filtres bande et mode ───────────────────────────────────────────────────

def test_le_filtre_de_bande(s):
    s.reglages['bandes'] = ['14', '21']
    assert s.decider(dec(band='14'), {'nouveau_pays': True})['appeler'] is True
    d = s.decider(dec(band='7'), {'nouveau_pays': True})
    assert d['appeler'] is False and 'hors selection' in d['motif']


def test_le_filtre_de_mode(s):
    s.reglages['modes'] = ['FT8']
    assert s.decider(dec(mode='FT8'), {'nouveau_pays': True})['appeler'] is True
    assert s.decider(dec(mode='FT4'), {'nouveau_pays': True})['appeler'] is False


def test_liste_vide_veut_dire_TOUTES(s):
    s.reglages['bandes'] = []
    for b in ('1.8', '14', '144'):
        assert s.decider(dec(band=b), {'nouveau_pays': True})['appeler'] is True


# ─── Le journal, indispensable au niveau 4 ───────────────────────────────────

def test_TOUT_CE_QUI_PART_EST_JOURNALISE(s):
    """Sans surveillance, c'est la seule façon de savoir après coup ce que la
    station a fait en votre nom."""
    s.noter_appel('DL1ABC', 'entité jamais travaillée')
    (entree,) = s.journal
    assert entree['call'] == 'DL1ABC'
    assert entree['motif'] == 'entité jamais travaillée'
    assert entree['essai'] == 1 and entree['t'] > 0


def test_l_etat_expose_ce_qu_il_faut_pour_surveiller_a_distance(s):
    s.noter_appel('DL1ABC', 'test')
    e = s.etat()
    assert e['active'] is True and e['appels'] == 1
    assert e['appel_en_cours'] == 'DL1ABC'
    assert e['restant_s'] > 0
    assert e['journal'][-1]['call'] == 'DL1ABC'


def test_le_niveau_4_est_signale_comme_tel(h):
    """L'écran doit pouvoir dire « personne devant la radio » sans deviner."""
    sess = p.Session(horloge=h)
    sess.armer({'niveau': p.NIVEAU_SANS_PERSONNE, 'criteres': ['nouveau_pays']})
    assert sess.etat()['sans_personne'] is True
    sess.armer({'niveau': p.NIVEAU_APPELER, 'criteres': ['nouveau_pays']})
    assert sess.etat()['sans_personne'] is False


def test_desarmer_conserve_le_motif(s):
    s.desarmer('arret manuel')
    assert s.etat()['active'] is False
    assert s.etat()['motif_arret'] == 'arret manuel'


def test_une_session_inactive_n_appelle_jamais(h):
    sess = p.Session(horloge=h)
    d = sess.decider(dec(), {'nouveau_pays': True})
    assert d['appeler'] is False and d['motif'] == 'session inactive'


# ─── L'invariant du module ───────────────────────────────────────────────────

def test_LE_MODULE_NE_PARLE_A_PERSONNE():
    """Il ne connaît ni socket, ni HTTP, ni WSJT-X. C'est ce qui permet de
    tester ici tous les cas qui FERAIENT émettre, sans qu'un octet ne parte.

    Contrôlé sur l'AST : la source, elle, MENTIONNE logx_wsjtx dans le
    commentaire qui explique justement pourquoi elle ne l'importe pas."""
    arbre = _arbre()
    importes = _modules_importes(arbre)
    for interdit in ('socket', 'urllib', 'http', 'logx_wsjtx', 'logx_http'):
        assert interdit not in importes, interdit
    for interdit in ('sendto', 'send', 'urlopen', 'connect'):
        assert interdit not in _noms_appeles(arbre), interdit
