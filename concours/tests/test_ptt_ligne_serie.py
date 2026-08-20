# -*- coding: utf-8 -*-
"""PTT MATÉRIEL par ligne série (RTS/DTR) — et ses garde-fous.

CE QUE ÇA AJOUTE. Jusqu'au 20/08/2026, LogX AI ne savait faire passer un poste
en émission que par COMMANDE (TX1; en ASCII, 1C 00 01 en CI-V). La notice du
boîtier XGGComms USB Digimode-4 recommande explicitement l'inverse : lever la
ligne RTS du port série, qui commande le PTT matériel du boîtier par
opto-coupleur — parce que beaucoup de postes n'activent l'entrée audio de leur
prise DATA QUE si le PTT matériel est actionné. Piloté par commande CAT, un tel
poste passe en émission et ne sort AUCUNE puissance : la panne est silencieuse,
tout a l'air de marcher.

🚨 POURQUOI CES TESTS SONT PLUS SÉVÈRES QUE LA MOYENNE. Une commande CAT ratée
ne fait rien. Une ligne RTS restée haute, c'est une porteuse permanente que le
poste lui-même ne sait pas annuler — il ne fait qu'obéir à une broche. La
notice du Digimode-4 documente ce sinistre comme un cas de panne courant.
Chaque chemin de sortie est donc testé séparément : relâchement normal, chien
de garde, fermeture de transport, reprise du port par le CAT, arrêt du serveur.

CE QUE CES TESTS NE PROUVENT PAS : qu'un opto-coupleur réel commute. Seul
F4GLD, sur son matériel, peut l'établir. Ils prouvent que LogX AI pose et
repose les bonnes lignes aux bons moments.
"""
import os
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402

import logx_cat as cat  # noqa: E402


# ─── Double de port série : enregistre l'état RÉEL des lignes ──────────────

class FauxPort:
    """Imite SerialPort en gardant l'HISTORIQUE des lignes.

    L'historique compte autant que l'état final : lever puis baisser aussitôt
    et ne jamais lever du tout donnent le même état final, et ce ne sont pas
    du tout les mêmes comportements sur l'air."""

    ouverts = []

    def __init__(self, device, baudrate=19200, timeout=1.0):
        self.device = device
        self.baudrate = baudrate
        self.rts = False
        self.dtr = False
        self.ferme = False
        self.journal = []          # [('rts', True), ('dtr', False), ('close',)]
        self._lock = threading.Lock()
        FauxPort.ouverts.append(self)

    def regler_ligne(self, ligne, actif, attente=1.0):
        if self.ferme:
            return False
        setattr(self, ligne, bool(actif))
        self.journal.append((ligne, bool(actif)))
        return True

    def baisser_lignes(self, attente=0.3):
        a = self.regler_ligne('rts', False, attente)
        b = self.regler_ligne('dtr', False, attente)
        return a and b

    def close(self):
        self.baisser_lignes()
        self.ferme = True
        self.journal.append(('close',))

    # Suffisant pour les chemins CAT touchés ici
    def transceive(self, *a, **k):
        return b''

    def write(self, *a, **k):
        pass


@pytest.fixture(autouse=True)
def _etat_neuf():
    """Aucun test ne doit hériter d'une ligne levée par le précédent."""
    o_open, o_sleep = cat._open_serial, cat._retry_sleep
    cat._open_serial = FauxPort
    cat._retry_sleep = lambda s: None
    FauxPort.ouverts = []
    cat.relacher_ptt_ligne()
    with cat._ptt_ligne_lock:
        cat._fermer_dedie_locked()
    cat.disconnect_persistent()
    yield
    cat.relacher_ptt_ligne()
    with cat._ptt_ligne_lock:
        cat._fermer_dedie_locked()
    cat.disconnect_persistent()
    cat._open_serial, cat._retry_sleep = o_open, o_sleep


class _SerBidon:
    """L'objet pyserial, et LUI SEUL, remplacé — pas la couche testée."""

    def __init__(self):
        self.rts = True     # volontairement HAUTES au départ : un test qui
        self.dtr = True     # part de False ne prouverait pas qu'on baisse
        self.closed = False

    def close(self):
        self.closed = True


def _vrai_port():
    """Un VRAI cat.SerialPort, sans ouvrir de port physique.

    🚨 POURQUOI CE DÉTOUR PLUTÔT QUE FauxPort. Quatre tests de ce fichier
    ont été trouvés VACANTS par contre-épreuve le 20/08/2026 : écrits contre
    FauxPort, ils vérifiaient la réimplémentation du banc et pas le code de
    production. On pouvait casser SerialPort.baisser_lignes(), SerialPort.
    close() et l'aiguillage RTS/DTR de SerialPort.regler_ligne() sans qu'un
    seul test ne bronche. « Un test de comportement écrit contre un
    mannequin ne contraint que le mannequin » — c'est écrit dans le CLAUDE.md
    de ce dépôt, et c'est arrivé encore une fois.

    Ici on instancie la VRAIE classe (sans __init__, qui ouvrirait un port)
    et on ne remplace que l'objet pyserial sous-jacent."""
    p = cat.SerialPort.__new__(cat.SerialPort)
    p._lock = threading.Lock()
    p._ser = _SerBidon()
    return p


def _cfg(**extra):
    base = {'cat_enabled': True, 'cat_mode': 'native', 'cat_brand': 'yaesu',
            'cat_model': 'FT-991A', 'cat_port': 'COM4', 'cat_baudrate': 38400}
    base.update(extra)
    return base


# ─── LE DÉFAUT QUE CE LOT COMBLE ───────────────────────────────────────────

def test_une_config_existante_ne_change_PAS_de_methode_d_emission():
    """LA PROPRIÉTÉ LA PLUS IMPORTANTE DU LOT. /config/save REMPLACE toute la
    config, jamais de patch partiel : si l'absence des nouveaux champs ne
    valait pas « commande CAT », le premier enregistrement de n'importe quel
    utilisateur basculerait sa station sur une méthode d'émission que
    personne n'a demandée."""
    s = cat.cat_settings({'cat_enabled': True, 'cat_port': 'COM4'})
    assert s['ptt_method'] == 'cat'
    assert s['ptt_port'] == ''


def test_une_valeur_inconnue_retombe_sur_la_commande_CAT():
    """Config corrompue, faute de frappe, champ d'une version future : le
    repli doit être la méthode HISTORIQUE, jamais une ligne série."""
    for valeur in ('vox', '', None, 'cts', 'ptt', 'serie'):
        s = cat.cat_settings({'cat_ptt_method': valeur})
        assert s['ptt_method'] == 'cat', valeur


def test_rts_et_dtr_sont_acceptees_et_normalisees():
    """Casse et espaces parasites viennent d'un fichier édité à la main ou
    d'un profil importé — les refuser pour ça serait gratuit."""
    assert cat.cat_settings({'cat_ptt_method': 'rts'})['ptt_method'] == 'rts'
    assert cat.cat_settings({'cat_ptt_method': 'DTR'})['ptt_method'] == 'dtr'
    assert cat.cat_settings({'cat_ptt_method': ' RTS '})['ptt_method'] == 'rts'


def test_un_champ_mal_type_ne_fait_pas_PLANTER_la_lecture_de_config():
    """DÉFAUT RÉEL TROUVÉ PAR CE TEST (20/08/2026). `(x or '').strip()`
    levait une AttributeError sur un entier, une liste ou un booléen.

    Anodin tant que le PTT passait par une commande. Plus du tout depuis :
    cat_settings() est appelée par le dispatch AVANT de relâcher l'émission.
    Une exception ici fait échouer /rig/ptt {on:false} par une erreur 500,
    c'est-à-dire laisse le poste EN ÉMISSION à cause d'un champ mal typé."""
    for valeur in (42, ['rts'], {'a': 1}, True, 3.5):
        s = cat.cat_settings({'cat_ptt_method': valeur, 'cat_port': valeur,
                              'cat_brand': valeur, 'cat_model': valeur})
        assert s['ptt_method'] == 'cat', valeur
        assert isinstance(s['port'], str)


# ─── Lever et reposer la ligne ─────────────────────────────────────────────

def test_le_ptt_rts_leve_reellement_la_ligne_RTS():
    r = cat.set_ptt_ligne(_cfg(cat_ptt_method='rts'), True)
    assert r['ok'] and r['methode'] == 'rts'
    port = FauxPort.ouverts[-1]
    assert port.rts is True, 'RTS doit être haut pendant l\'émission'
    assert port.dtr is False, 'DTR ne doit pas bouger quand RTS est la ligne choisie'


def test_le_ptt_dtr_leve_DTR_et_pas_RTS():
    cat.set_ptt_ligne(_cfg(cat_ptt_method='dtr'), True)
    port = FauxPort.ouverts[-1]
    assert port.dtr is True and port.rts is False


def test_le_relachement_repose_la_ligne():
    cfg = _cfg(cat_ptt_method='rts')
    cat.set_ptt_ligne(cfg, True)
    port = FauxPort.ouverts[-1]
    assert port.rts is True
    r = cat.set_ptt_ligne(cfg, False)
    assert r['ok'] and r['ptt'] is False
    assert port.rts is False


def test_le_relachement_repose_les_DEUX_lignes():
    """On ne relit pas la config au moment de couper : si l'état interne
    s'est désynchronisé de la réalité, c'est précisément là qu'il ne faut pas
    lui faire confiance."""
    cfg = _cfg(cat_ptt_method='rts')
    cat.set_ptt_ligne(cfg, True)
    port = FauxPort.ouverts[-1]
    port.dtr = True          # simule une ligne haute dont on ignore l'origine
    cat.relacher_ptt_ligne()
    assert port.rts is False and port.dtr is False


def test_l_etat_est_lisible_pendant_l_emission():
    cat.set_ptt_ligne(_cfg(cat_ptt_method='rts'), True)
    etat = cat.etat_ptt_ligne()
    assert etat['actif'] is True and etat['ligne'] == 'rts' and etat['port'] == 'COM4'
    cat.relacher_ptt_ligne()
    assert cat.etat_ptt_ligne() == {'actif': False}


# ─── Le cas qui justifie tout le lot ───────────────────────────────────────

def test_on_peut_emettre_meme_si_le_CAT_est_DESACTIVE():
    """LE CAS RÉEL DU 20/08/2026. Un boîtier d'interface porte trois choses
    sur un seul câble USB : l'audio, le CAT et la ligne PTT. Quand le câble
    CAT ne fonctionne pas, l'audio et la ligne PTT, eux, fonctionnent
    toujours. Exiger un CAT valide pour lever une ligne série reviendrait à
    refuser d'émettre pour une raison sans rapport avec l'émission — et
    priverait de FT8 exactement les opérateurs que ce mode existe pour
    dépanner."""
    import logx_voicekeyer as vk
    cfg = {'cat_enabled': False, 'cat_port': 'COM4', 'cat_ptt_method': 'rts'}
    r = vk.set_ptt(cfg, True)
    assert r['ok'] is True, (
        "le PTT matériel ne doit pas dépendre d'un CAT actif : %r" % r)
    assert FauxPort.ouverts[-1].rts is True
    vk.set_ptt(cfg, False)


def test_le_dispatch_du_keyer_vocal_passe_par_la_ligne_serie():
    """Bout en bout par le VRAI cat_settings : une faute de frappe sur le nom
    de la clé désactiverait la fonction en silence, et `.get()` dans le
    dispatch (volontaire, pour ne jamais lever d'exception sur le chemin de
    RELÂCHEMENT) empêcherait de le voir autrement."""
    import logx_voicekeyer as vk
    r = vk.set_ptt(_cfg(cat_ptt_method='rts'), True)
    assert r.get('methode') == 'rts', (
        'le dispatch doit atteindre set_ptt_ligne, pas la commande CAT : %r' % r)
    vk.set_ptt(_cfg(cat_ptt_method='rts'), False)


def test_sans_methode_serie_le_dispatch_ne_touche_AUCUNE_ligne():
    """Non-régression : le chemin historique ne doit pas se mettre à piloter
    des lignes de contrôle au passage."""
    import logx_voicekeyer as vk
    vk.set_ptt(_cfg(), True)
    assert all(p.rts is False for p in FauxPort.ouverts), (
        'aucune ligne ne doit être levée par la commande CAT'
    )


# ─── Partage du port : un port série ne s'ouvre pas deux fois ──────────────

def test_meme_port_que_le_CAT_le_transport_est_REUTILISE():
    """Sous Windows, ouvrir COM4 une seconde fois échoue. Le montage le plus
    courant (un seul boîtier) fait justement passer CAT et PTT par le même
    FTDI : ouvrir un second handle serait une panne garantie."""
    cfg = _cfg(cat_ptt_method='rts')
    cat._ensure_connected(cat.cat_settings(cfg))
    avant = len(FauxPort.ouverts)
    cat.set_ptt_ligne(cfg, True)
    assert len(FauxPort.ouverts) == avant, (
        'un second port a été ouvert sur le même device'
    )
    assert FauxPort.ouverts[-1].rts is True


def test_port_PTT_distinct_un_transport_dedie_est_ouvert():
    cfg = _cfg(cat_ptt_method='rts', cat_ptt_port='COM9')
    cat.set_ptt_ligne(cfg, True)
    dedie = FauxPort.ouverts[-1]
    assert dedie.device == 'COM9' and dedie.rts is True


def test_le_port_PTT_vide_signifie_le_meme_que_le_CAT():
    """Demander à l'opérateur de recopier le même numéro de port deux fois
    serait un piège : il oublierait, et le PTT viserait le vide."""
    s = cat.cat_settings(_cfg(cat_ptt_method='rts'))
    assert cat.port_ptt_effectif(s) == 'COM4'


def test_le_CAT_recupere_un_port_tenu_par_le_PTT():
    """Sans ça, LogX AI se bloquerait LUI-MÊME : le PTT dédié tiendrait COM4,
    l'ouverture CAT échouerait en « déjà utilisé », et le message accuserait
    un autre logiciel."""
    cfg = _cfg(cat_ptt_method='rts')
    cat.set_ptt_ligne(cfg, True)
    dedie = FauxPort.ouverts[-1]
    assert dedie.ferme is False
    driver, err = cat._ensure_connected(cat.cat_settings(cfg))
    assert err is None, err
    assert dedie.ferme is True, 'le port PTT dédié devait être rendu au CAT'
    assert dedie.rts is False, 'et la ligne reposée en le rendant'


# ─── Les garde-fous, un par un ─────────────────────────────────────────────

def test_le_VRAI_SerialPort_aiguille_bien_RTS_et_DTR():
    """Contre une inversion des deux lignes : lever DTR quand on demande RTS
    ferait émettre un boîtier câblé sur DTR pendant qu'on croit piloter
    l'autre — et surtout, la ligne qu'on croit reposer ne serait pas la
    bonne. Testé sur la VRAIE classe (voir _vrai_port)."""
    p = _vrai_port()
    p._ser.rts = p._ser.dtr = False
    assert p.regler_ligne('dtr', True) is True
    assert p._ser.dtr is True and p._ser.rts is False
    p._ser.dtr = False
    assert p.regler_ligne('rts', True) is True
    assert p._ser.rts is True and p._ser.dtr is False


def test_le_VRAI_SerialPort_repose_les_DEUX_lignes():
    """baisser_lignes() est le chemin des coupures d'urgence : il ne doit
    dépendre d'aucune configuration lue au pire moment."""
    p = _vrai_port()
    assert p.baisser_lignes() is True
    assert p._ser.rts is False and p._ser.dtr is False


def test_fermer_un_VRAI_transport_repose_les_lignes_AVANT_de_fermer():
    """En pratique le pilote relâche les lignes à la fermeture — mais « en
    pratique » ne vaut pas pour un émetteur. Si le PTT matériel est câblé sur
    RTS, une ligne restée haute est une porteuse sur l'air que plus personne
    ne surveille."""
    p = _vrai_port()
    p.close()
    assert p._ser.rts is False and p._ser.dtr is False, (
        'les lignes doivent être reposées à la fermeture'
    )
    assert p._ser.closed is True


def test_une_reconnexion_CAT_oublie_l_emission_en_cours():
    """Le transport qui portait la ligne disparaît (sauvegarde CONFIG,
    bascule de focus SO2R, port tombé) : l'état interne doit cesser de
    désigner un objet mort, sinon un relâchement ultérieur viserait un
    transport fermé et croirait avoir coupé."""
    cfg = _cfg(cat_ptt_method='rts')
    cat._ensure_connected(cat.cat_settings(cfg))
    cat.set_ptt_ligne(cfg, True)
    assert cat.etat_ptt_ligne()['actif'] is True
    cat.disconnect_persistent()
    assert cat.etat_ptt_ligne()['actif'] is False, (
        "l'état doit refléter que plus rien ne peut émettre"
    )


def test_un_CHANGEMENT_DE_CONFIG_oublie_aussi_l_emission_en_cours():
    """Deuxième chemin de destruction du transport, distinct du précédent et
    NON couvert par lui : _ensure_connected() ferme et rouvre dès que la clé
    (port, marque, modèle, vitesse, adresse CI-V) change.

    Ce n'est pas un cas de laboratoire — la cartographie du 20/08/2026 l'a
    établi : une sauvegarde CONFIG le déclenche, et une simple bascule de
    focus SO2R aussi, puisque config_radio_active() remappe cat2_* en cat_*.
    Donc en pleine exploitation.

    ⚠️ Ce test a été ajouté APRÈS contre-épreuve : la mutation « ne pas
    oublier l'émission dans _ensure_connected » restait VERTE, le seul test
    existant passant par disconnect_persistent()."""
    cfg = _cfg(cat_ptt_method='rts')
    cat._ensure_connected(cat.cat_settings(cfg))
    cat.set_ptt_ligne(cfg, True)
    assert cat.etat_ptt_ligne()['actif'] is True
    # Même port, vitesse différente : la clé change, le transport est recréé.
    cat._ensure_connected(cat.cat_settings(_cfg(cat_ptt_method='rts',
                                                cat_baudrate=9600)))
    assert cat.etat_ptt_ligne()['actif'] is False, (
        "l'état interne désigne un transport fermé : un relâchement viserait "
        'un objet mort et croirait avoir coupé'
    )


def test_le_chien_de_garde_repose_la_ligne_que_personne_n_a_relachee(monkeypatch):
    """Page fermée en pleine émission, navigateur tué, coupure réseau : plus
    personne n'enverra le PTT OFF. C'est le seul garde-fou qui reste."""
    monkeypatch.setattr(cat, 'PTT_LIGNE_DUREE_MIN_S', 0.05)
    monkeypatch.setattr(cat, 'PTT_LIGNE_DUREE_MAX_S', 0.05)
    cat.set_ptt_ligne(_cfg(cat_ptt_method='rts'), True, duree_max_s=0.05)
    port = FauxPort.ouverts[-1]
    assert port.rts is True
    deadline = time.monotonic() + 3.0
    while port.rts and time.monotonic() < deadline:
        time.sleep(0.02)
    assert port.rts is False, "le chien de garde n'a pas reposé la ligne"
    assert cat.etat_ptt_ligne()['actif'] is False


def test_le_relachement_normal_desarme_le_chien_de_garde():
    """Un minuteur laissé courir reposerait une ligne relevée entre-temps par
    l'émission SUIVANTE — il couperait un opérateur en plein trafic."""
    cfg = _cfg(cat_ptt_method='rts')
    cat.set_ptt_ligne(cfg, True, duree_max_s=10)
    cat.set_ptt_ligne(cfg, False)
    with cat._ptt_ligne_lock:
        assert cat._ptt_chien is None


def test_la_duree_annoncee_est_bornee():
    """Une valeur absurde ne doit pas pouvoir désarmer le chien de garde."""
    assert cat._duree_chien(None) == cat.PTT_LIGNE_DUREE_MAX_S
    assert cat._duree_chien('bavardage') == cat.PTT_LIGNE_DUREE_MAX_S
    assert cat._duree_chien(-5) == cat.PTT_LIGNE_DUREE_MAX_S
    assert cat._duree_chien(0) == cat.PTT_LIGNE_DUREE_MAX_S
    assert cat._duree_chien(10_000) == cat.PTT_LIGNE_DUREE_MAX_S
    assert cat._duree_chien(0.1) == cat.PTT_LIGNE_DUREE_MIN_S
    assert cat._duree_chien(18) == 18


def test_le_plafond_couvre_la_plus_longue_image_SSTV():
    """CALIBRAGE MESURÉ, pas estimé. Les durées d'émission réelles des modes
    SSTV proposés par LogX AI ont été obtenues en faisant tourner l'encodeur
    du dépôt (sstvEncodeSamples) : PD290 = 289,7 s, Scottie DX = 269,9 s. Un
    plafond en dessous ferait du chien de garde LA panne — il trancherait une
    image en cours, en plein trafic, sans que personne comprenne pourquoi."""
    assert cat.PTT_LIGNE_DUREE_MAX_S >= 290, (
        'le plafond doit couvrir la PD290 (289,7 s mesurées)'
    )


def test_le_relachement_sans_rien_d_ouvert_ne_ment_pas():
    """Répondre « je n'ai pas pu couper » quand il n'y avait rien à couper
    déclencherait une alarme rouge pour rien — et une alarme qui crie pour
    rien finit par ne plus être lue."""
    r = cat.relacher_ptt_ligne()
    assert r['ok'] is True and r.get('rien_a_relacher') is True


def test_l_arret_du_serveur_repose_la_ligne_du_transport_CAT():
    """Dernier filet : un serveur qu'on ferme pendant une émission ne doit
    pas laisser la porteuse derrière lui.

    ⚠️ PREMIÈRE VERSION DE CE TEST : VACANTE, trouvée par contre-épreuve.
    Elle utilisait un port PTT DÉDIÉ : supprimer l'appel à
    relacher_ptt_ligne() dans _relacher_a_l_arret() ne changeait alors rien,
    parce que la fermeture du port dédié (juste après) reposait les lignes de
    toute façon. Le test réussissait sur le défaut qu'il visait.

    On place donc la ligne sur le transport CAT PARTAGÉ, que _relacher_a_l_
    arret() ne ferme pas : seul le relâchement explicite peut alors la
    reposer."""
    cfg = _cfg(cat_ptt_method='rts')
    driver, err = cat._ensure_connected(cat.cat_settings(cfg))
    assert err is None, err
    partage = FauxPort.ouverts[-1]
    cat.set_ptt_ligne(cfg, True)
    assert partage.rts is True, 'le transport CAT devait porter la ligne'
    cat._relacher_a_l_arret()
    assert partage.rts is False, (
        "l'arrêt du serveur doit reposer la ligne, pas compter sur une "
        'fermeture qui ne viendra pas'
    )


# ─── Ordre des verrous : l'interblocage serait total ───────────────────────

def test_relachement_et_connexion_concurrents_ne_s_interbloquent_pas():
    """_ensure_connected tient _persistent_lock et prend _ptt_ligne_lock.
    Si relacher_ptt_ligne prenait les deux dans l'autre sens, deux threads
    HTTP suffiraient à figer le serveur — PTT compris, donc émetteur en
    l'air. Ce test échouerait par TIMEOUT, pas par assertion."""
    cfg = _cfg(cat_ptt_method='rts')
    cat.set_ptt_ligne(cfg, True)
    fini = threading.Event()

    def _tourne():
        for _ in range(60):
            cat._ensure_connected(cat.cat_settings(cfg))
            cat.relacher_ptt_ligne()
            cat.set_ptt_ligne(cfg, True)
        fini.set()

    t = threading.Thread(target=_tourne, daemon=True)
    t.start()
    for _ in range(60):
        cat.relacher_ptt_ligne()
        cat.etat_ptt_ligne()
    assert fini.wait(20), 'interblocage : ordre des verrous inversé'


def test_couper_n_attend_pas_indefiniment_un_verrou_de_port_occupe():
    """transceive_listen() garde le verrou d'instance pendant TOUTE une
    fenêtre d'écoute (plusieurs secondes pour une ligne de spectre CI-V).
    Attendre ce verrou pour reposer RTS, c'est accepter que l'ordre de
    couper patiente pendant que l'émetteur reste sur l'air."""
    if not cat.HAS_PYSERIAL:
        pytest.skip('pyserial absent')
    port = cat.SerialPort.__new__(cat.SerialPort)
    port._lock = threading.Lock()

    class _Ser:
        rts = True
        dtr = True
    port._ser = _Ser()
    port._lock.acquire()          # simule une écoute longue en cours

    # ⚠️ POURQUOI UN THREAD ET PAS UN APPEL DIRECT. Écrit en appel direct, ce
    # test ne FAILLIT pas quand la propriété est violée : il PEND, pour
    # toujours, verrou tenu. Mesuré le 20/08/2026 en contre-épreuve — la
    # mutation « attendre le verrou indéfiniment » a figé la suite au lieu de
    # la faire rougir, et le harnais a été tué au bout de 10 minutes en
    # laissant la mutation dans le fichier. Un test de non-blocage doit
    # lui-même être incapable de bloquer.
    resultat = {}

    def _essaie():
        resultat['debut'] = time.monotonic()
        resultat['ok'] = port.regler_ligne('rts', False, attente=0.05)
        resultat['fin'] = time.monotonic()

    t = threading.Thread(target=_essaie, daemon=True)
    t.start()
    t.join(timeout=5.0)
    try:
        assert not t.is_alive(), (
            'la coupure attend le verrou indéfiniment : sur un port occupé par '
            "une écoute longue (scope CI-V), l'ordre de reposer RTS ne "
            "partirait jamais et l'émetteur resterait sur l'air"
        )
        assert resultat.get('ok') is True
        assert resultat['fin'] - resultat['debut'] < 2.0
        assert port._ser.rts is False
    finally:
        port._lock.release()
