# -*- coding: utf-8 -*-
"""Décodeur RTTY (Baudot/ITA2) dans le navigateur.

CQ WW RTTY, CQ WPX RTTY et WAE RTTY sont des concours majeurs où beaucoup de
stations F sont actives. Jusqu'ici le RTTY n'existait que comme étiquette de
mode dans le log : il fallait ouvrir N1MM à côté. N1MM lui-même s'interface
avec MMTTY/MMVARI/Fldigi, trois logiciels externes ; ici tout est dans la page.

POURQUOI CES TESTS SONT REPRÉSENTATIFS, contrairement à ceux du décodeur CW :
le RTTY est généré par machine à cadence FIXE (45,45 bauds, décalage 170 Hz),
là où le CW dépend de la main de l'opérateur. Un signal AFSK synthétique est
donc un vrai signal RTTY, pas une approximation — on encode un texte, on le
décode, et on compare. Le décodeur est exercé de bout en bout, DSP comprise,
sans radio.

Ce que ces tests NE prouvent PAS : le comportement en pile-up réel, avec QRM,
QSB et plusieurs stations dans le filtre. Ça reste à éprouver sur l'air.
"""
import json
import os

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS = os.path.join(CONCOURS, 'logx_rttydecoder.js')

py_mini_racer = pytest.importorskip('py_mini_racer')


@pytest.fixture(scope='module')
def moteur():
    ctx = py_mini_racer.MiniRacer()
    with open(JS, encoding='utf-8') as f:
        ctx.eval(f.read())
    # Bruit blanc reproductible : un générateur à graine, pour qu'un échec
    # soit rejouable à l'identique.
    ctx.eval("""
    function avecBruit(sig, niveau, graine){
      var s = graine || 1, out = new Float32Array(sig.length);
      for(var i=0;i<sig.length;i++){
        s = (s*1103515245 + 12345) & 0x7fffffff;
        out[i] = sig[i] + ((s/0x7fffffff)*2-1)*niveau;
      }
      return out;
    }
    function allerRetour(texte, optsEnc, optsDec){
      var sig = rttyEncodeSamples(texte, optsEnc || {});
      return rttyDecodeSamples(sig, optsDec || {});
    }""")
    return ctx


def _aller_retour(moteur, texte, enc=None, dec=None):
    return moteur.eval('allerRetour(%s, %s, %s)' % (
        json.dumps(texte), json.dumps(enc or {}), json.dumps(dec or {}))).strip()


# ─── Aller-retour ────────────────────────────────────────────────────────────

@pytest.mark.parametrize('texte', [
    'TEST',
    'CQ TEST DE F4GLD',
    'F6BC 599 001',                 # bascule chiffres
    'DE F4GLD/P',                   # indicatif portable
    '599 014 014',
    'RTTY IS FUN',
])
def test_un_signal_encode_se_decode_a_l_identique(moteur, texte):
    assert _aller_retour(moteur, texte) == texte


def test_la_bascule_lettres_chiffres_est_geree(moteur):
    """En Baudot, chiffres et lettres partagent les mêmes 5 bits : c'est une
    bascule LTRS/FIGS qui décide. La rater fait sortir « TEST » là où la
    station a envoyé « 5943 »."""
    assert _aller_retour(moteur, 'AB 12 CD 34') == 'AB 12 CD 34'


def test_les_bascules_repetees_ne_derivent_pas(moteur):
    """Un message qui alterne sans cesse lettres et chiffres : chaque bascule
    doit être suivie, sinon la fin du message est illisible."""
    t = 'A1B2C3D4E5F6G7H8'
    assert _aller_retour(moteur, t) == t


# ─── Robustesse ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize('niveau', [0.0, 0.25, 0.5, 0.8, 1.2])
def test_le_bruit_blanc_ne_casse_pas_le_decodage(moteur, niveau):
    """Le signal est à 0,5 d'amplitude : à 1,2 de bruit, il est enterré pour
    l'œil. Les détecteurs I/Q sont étroits, ils s'en sortent."""
    texte = 'CQ TEST DE F4GLD'
    sortie = moteur.eval(
        'rttyDecodeSamples(avecBruit(rttyEncodeSamples(%s), %f, 7))'
        % (json.dumps(texte), niveau)).strip()
    assert sortie == texte


@pytest.mark.parametrize('offset', [0, 10, 25, 50])
def test_un_desaccord_modere_reste_lisible(moteur, offset):
    """L'opérateur n'est jamais pile sur la fréquence. Jusqu'à 50 Hz d'écart
    sur un décalage de 170 Hz, le décodage doit tenir."""
    texte = 'CQ TEST DE F4GLD'
    assert _aller_retour(moteur, texte,
                         enc={'mark': 2125 + offset, 'space': 2295 + offset}) == texte


def test_un_desaccord_important_degrade_mais_ne_plante_pas(moteur):
    """À 80 Hz, on est à mi-chemin entre les deux tons : le décodage devient
    faux. Il doit se dégrader, pas lever."""
    sortie = _aller_retour(moteur, 'CQ TEST DE F4GLD',
                           enc={'mark': 2205, 'space': 2375})
    assert isinstance(sortie, str)


def test_le_silence_ne_produit_aucun_caractere(moteur):
    """Sans signal, l'écran doit rester vide — pas de caractères aléatoires
    qui feraient croire à du trafic."""
    sortie = moteur.eval(
        'rttyDecodeSamples(new Float32Array(44100))').strip()
    assert sortie == ''


def test_du_bruit_seul_ne_remplit_pas_l_ecran(moteur):
    """Le bit de stop DOIT être un mark : c'est ce contrôle qui écarte les
    trames de bruit. Sans lui, un décodeur écrit n'importe quoi en permanence
    dès qu'il n'y a pas de station."""
    sortie = moteur.eval(
        'rttyDecodeSamples(avecBruit(new Float32Array(44100*2), 0.5, 3))').strip()
    assert len(sortie) <= 12, 'trop de caracteres nes du bruit seul : %r' % sortie


@pytest.mark.parametrize('ampl', [0.05, 0.2, 1.0])
def test_le_niveau_du_signal_n_a_pas_d_importance(moteur, ampl):
    """La décision compare les deux tons entre eux : elle ne dépend donc pas
    du niveau d'entrée, et le réglage du gain de la carte son ne doit pas
    devenir un paramètre critique."""
    texte = 'TEST DE F4GLD'
    assert _aller_retour(moteur, texte, enc={'amplitude': ampl}) == texte


def test_une_frequence_d_echantillonnage_differente_fonctionne(moteur):
    """La fréquence de la carte son varie d'un poste à l'autre (44,1 ou
    48 kHz) : le décodeur la prend du contexte audio, il doit suivre."""
    texte = 'CQ DE F4GLD'
    assert _aller_retour(moteur, texte,
                         enc={'sampleRate': 48000}, dec={'sampleRate': 48000}) == texte


# ─── Table Baudot ────────────────────────────────────────────────────────────

def test_la_table_lettres_est_conforme_a_ITA2(moteur):
    attendu = {1: 'E', 3: 'A', 4: ' ', 16: 'T', 24: 'O', 31: None}
    for code, car in attendu.items():
        assert moteur.eval('RTTY_LTRS[%d]' % code) == car


def test_les_codes_de_bascule_ne_produisent_pas_de_caractere(moteur):
    """LTRS et FIGS pilotent l'état, ils ne s'écrivent pas."""
    assert moteur.eval("rttyBaudotChar(31, {figs:true})") == ''
    assert moteur.eval("rttyBaudotChar(27, {figs:false})") == ''


def test_le_panneau_cw_reste_cable_dans_le_logbook():
    """Garde-fou : le panneau CW s'appelle cwPanel et non cwDecoder. Viser le
    mauvais identifiant n'aurait levé AUCUNE erreur — le décodeur CW serait
    simplement resté affiché en RTTY. Le RTTY, lui, a été extrait vers sa
    propre fenêtre détachée (logx_rtty.html, EV-7 phase 2 incrément B) --
    testé séparément ci-dessous."""
    with open(os.path.join(CONCOURS, 'logx_logbook.html'), encoding='utf-8') as f:
        html = f.read()
    with open(os.path.join(CONCOURS, 'logx_logbook.js'), encoding='utf-8') as f:
        js = f.read()
    assert 'id="cwPanel"' in html, 'identifiant absent du balisage : cwPanel'
    assert 'cwPanel' in js, 'identifiant jamais utilise cote JS : cwPanel'


def test_le_panneau_rtty_est_bien_cable_dans_sa_fenetre_detachee():
    """Même garde-fou que ci-dessus, côté RTTY : logx_rtty.html doit charger
    le DSP et exposer les bons identifiants, sans dépendre de LOGBOOK."""
    with open(os.path.join(CONCOURS, 'logx_rtty.html'), encoding='utf-8') as f:
        html = f.read()
    assert 'logx_rttydecoder.js' in html, 'le script du decodeur n est pas charge'
    for ident in ('rttyOutput', 'rttyStartBtn', 'rttyMark', 'rttyShift'):
        assert 'id="%s"' % ident in html, 'identifiant absent du balisage : ' + ident
        assert ident in html, 'identifiant jamais utilise cote JS : ' + ident


# ─── Clic-pour-loguer ────────────────────────────────────────────────────────
# C'est CE geste qui fait la vitesse en RTTY : l'indicatif est deja affiche a
# l'ecran, le recopier a la main est du temps perdu et une source de faute.
#
# La premiere version lisait window.getSelection(), avec repli sur la position
# du curseur. Les deux se sont reveles inutilisables dans la page reelle : une
# selection posee par programme rend une chaine VIDE. Chaque indicatif est
# donc devenu un element cliquable a part entiere — le clic arrive
# directement sur sa cible, sans passer par aucune API de selection.

def _est_indicatif(moteur_logbook, mot):
    return moteur_logbook.eval('rttyEstIndicatif(%s)' % json.dumps(mot))


@pytest.fixture(scope='module')
def moteur_logbook():
    """Extrait la seule fonction de reconnaissance depuis sa fenêtre détachée
    (logx_rtty.html, EV-7 phase 2 incrément B -- auparavant logx_rtty_panel.js,
    chargé dans logx_logbook.html). La fonction est en JS pur au milieu d'un
    fichier HTML : une simple recherche de sous-chaîne suffit, comme pour les
    fichiers .js purs (même motif que test_logbook_menu_debut_fin.py)."""
    ctx = py_mini_racer.MiniRacer()
    with open(os.path.join(CONCOURS, 'logx_rtty.html'), encoding='utf-8') as f:
        src = f.read()
    debut = src.index('function rttyEstIndicatif(')
    fin = src.index('\n  }', debut) + 4
    ctx.eval(src[debut:fin])
    return ctx


@pytest.mark.parametrize('mot', ['F6BC', 'DL1XX', 'F4GLD/P', 'W1AW', 'VK9DX', 'G0ABC/MM'])
def test_un_indicatif_est_reconnu(moteur_logbook, mot):
    assert _est_indicatif(moteur_logbook, mot) == mot


@pytest.mark.parametrize('mot', [
    'CQ', 'TEST', 'DE', 'K', 'RTTY', 'TU',      # mots du trafic
    '599', '001', '',                            # report et numero de serie
])
def test_ce_qui_n_est_pas_un_indicatif_n_est_pas_cliquable(moteur_logbook, mot):
    """« 599 » et « 001 » sont dans TOUS les echanges RTTY : les rendre
    cliquables, c'est risquer de loguer « 599 » comme indicatif."""
    assert _est_indicatif(moteur_logbook, mot) == ''


def test_la_ponctuation_parasite_est_retiree(moteur_logbook):
    assert _est_indicatif(moteur_logbook, 'F6BC,') == 'F6BC'
    assert _est_indicatif(moteur_logbook, '*F6BC*') == 'F6BC'


def test_limite_connue_le_report_abrege_5NN_reste_cliquable(moteur_logbook):
    """Limite ASSUMEE : « 5NN » (report 599 abrege) a un chiffre et des
    lettres, comme un indicatif. Il est meme structurellement plausible —
    « 5N » est le prefixe du Nigeria. Le distinguer demanderait une vraie
    grammaire d indicatifs, pour un benefice faible : un clic de travers
    remplit un champ visible, que l operateur corrige aussitot. On le
    documente plutot que de bricoler une exception."""
    assert _est_indicatif(moteur_logbook, '5NN') == '5NN'
