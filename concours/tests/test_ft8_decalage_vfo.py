# -*- coding: utf-8 -*-
"""Décalage de VFO à l'émission — l'équivalent du « Fake It » de WSJT-X.

Demandé par F4GLD (19/08/2026) après son constat « wsjt x dès que je passe en
émission passe en split sur la même fréquence il doit y avoir une raison » :
« les deux », c'est-à-dire l'avertissement (voir test_ft8_ton_propre.py) ET le
décalage automatique.

SOURCE — code de WSJT-X (GPL), lu et NON recopié, dans wsjtx-3.2.0,
src/wsjtx/widgets/mainwindow.cpp, MainWindow::setXIT :

    m_XIT = (n/500)*500 - 1500;                  // division ENTIÈRE
    m_freqTxNominal = base + m_XIT;              // le VFO monte de XIT
    float f0 = TxFreqSpinBox->value() - m_XIT;   // le TON descend d'autant

LES DEUX MOITIÉS COMPTENT. Décaler le VFO sans corriger le ton changerait la
fréquence RÉELLEMENT ÉMISE : on transmettrait ailleurs, ce qui serait bien pire
que le parasite qu'on cherche à éviter. Ici les deux se compensent exactement.

CE QUE CES TESTS NE PROUVENT PAS : que la radio obéit. Aucun test ne peut le
dire — il faut un poste, et un essai sur l'air.
"""
import os
import re

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FT8_HTML = os.path.join(CONCOURS, 'logx_ft8.html')

py_mini_racer = pytest.importorskip('py_mini_racer')

TON_MIN, TON_MAX = 1500, 2000


def _lire():
    with open(FT8_HTML, encoding='utf-8') as f:
        return f.read()


def _extraire_fonction(src, nom):
    debut = src.index('function ' + nom)
    prof, i = 0, src.index('{', debut)
    while True:
        if src[i] == '{':
            prof += 1
        elif src[i] == '}':
            prof -= 1
            if prof == 0:
                return src[debut:i + 1]
        i += 1


def _sans_commentaires(src):
    return '\n'.join(l for l in src.split('\n')
                     if not l.strip().startswith('//'))


@pytest.fixture(scope='module')
def src():
    return _lire()


@pytest.fixture(scope='module')
def calc(src):
    """Exécute decalageVfoHz EXTRAITE de la page — pas une réécriture."""
    ctx = py_mini_racer.MiniRacer()
    ctx.eval(_extraire_fonction(src, 'decalageVfoHz'))
    return ctx


# ═══════════════════════════════════════════════════════════════════════════
# §1. LA PROPRIÉTÉ CENTRALE
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize('ton', list(range(200, 2851, 25)))
def test_le_ton_EMIS_tombe_toujours_dans_la_plage_propre(calc, ton):
    """LA propriété. Quelle que soit la position choisie dans le waterfall, le
    ton réellement modulé doit finir entre 1500 et 2000 Hz — sinon tout
    l'exercice n'a servi à rien. Balayé sur toute la plage réglable du champ,
    par pas de 25 Hz."""
    d = calc.eval('decalageVfoHz(%d)' % ton)
    emis = ton - d
    assert TON_MIN <= emis < TON_MAX, (
        'ton %d Hz -> décalage %d -> ton émis %d, hors de [%d, %d['
        % (ton, d, emis, TON_MIN, TON_MAX))


@pytest.mark.parametrize('ton', [1500, 1600, 1750, 1999])
def test_un_ton_deja_propre_ne_bouge_PAS_le_VFO(calc, ton):
    """Toucher au VFO sans raison serait intrusif, et ferait douter de
    l'option. Dans la plage, on ne fait rien."""
    assert calc.eval('decalageVfoHz(%d)' % ton) == 0, ton


@pytest.mark.parametrize('ton', list(range(200, 2851, 25)))
def test_le_decalage_est_un_multiple_de_500_Hz(calc, ton):
    """Le VFO reste ainsi sur une fréquence ronde, lisible sur l'afficheur du
    poste. C'est la raison d'être de la division entière par 500 dans la
    formule de référence."""
    d = calc.eval('decalageVfoHz(%d)' % ton)
    assert d % 500 == 0, 'ton %d -> décalage %d, non multiple de 500' % (ton, d)


@pytest.mark.parametrize('ton,attendu', [
    (700, 1700), (1200, 1700), (1600, 1600), (2000, 1500), (2500, 1500),
])
def test_les_valeurs_verifiees_a_la_main_sur_la_source(calc, ton, attendu):
    """Les cinq couples calculés à la lecture du code de WSJT-X. S'ils
    changent, c'est que la formule a été retouchée."""
    assert ton - calc.eval('decalageVfoHz(%d)' % ton) == attendu


# ═══════════════════════════════════════════════════════════════════════════
# §2. LA COMPENSATION — l'erreur qui ferait émettre ailleurs
# ═══════════════════════════════════════════════════════════════════════════

def test_le_ton_genere_compense_EXACTEMENT_le_decalage(src):
    """Si le VFO monte de X et que le ton ne descend pas de X, la fréquence
    réellement émise change : on transmet ailleurs. C'est LE défaut à ne pas
    commettre, et il serait invisible depuis l'écran."""
    i = src.index('const tone0 = tonVoulu - decalage;')
    assert i > 0
    zone = _sans_commentaires(src[i - 1500:i])
    assert 'freq_hz: freqAvantHz + d' in zone, (
        'le VFO doit être décalé de + d, et le ton de - d : %r' % zone[-500:])


def test_le_VFO_est_decale_AVANT_le_PTT_jamais_pendant(src):
    """WSJT-X pose la même règle (« if (m_transmitting && !tx_QSY_allowed)
    return; ») : bouger la fréquence en pleine émission étale le signal sur la
    bande."""
    i_qsy = src.index("body: JSON.stringify({freq_hz: freqAvantHz + d})")
    i_modul = src.index('await jouerForme(wave, 12000);')
    assert i_qsy < i_modul, 'le QSY doit précéder la modulation'


# ═══════════════════════════════════════════════════════════════════════════
# §3. SÛRETÉ — ce qui ne doit jamais arriver à la radio
# ═══════════════════════════════════════════════════════════════════════════

def test_l_option_est_DESACTIVEE_par_defaut(src):
    """Rien ne doit toucher au VFO de l'opérateur sans qu'il l'ait demandé."""
    m = re.search(r'<input[^>]*id="ft8DecalageVfo"[^>]*>', src)
    assert m, 'case à cocher introuvable'
    assert 'checked' not in m.group(0), (
        'la case doit être décochée à la livraison : %r' % m.group(0))


def test_aucun_QSY_sans_pilotage_radio(src):
    """Sans CAT il n'y a pas de VFO à décaler. Tenter quand même laisserait
    croire que le signal est propre alors qu'il ne l'est pas."""
    i = src.index('const caseVfo = document.getElementById')
    zone = _sans_commentaires(src[i:i + 400])
    assert 'rigFreqKhz > 0' in zone, (
        'le décalage doit exiger une fréquence radio connue : %r' % zone[:300])
    assert 'caseVfo.checked' in zone, zone[:300]


def test_la_frequence_est_restauree_dans_un_finally(src):
    """Une radio laissée décalée écoute ET émet à côté, sans que rien ne le
    dise. C'est la même classe de danger qu'un PTT non relâché, donc la même
    discipline : restauration inconditionnelle, y compris sur exception."""
    i = src.index('const tone0 = tonVoulu - decalage;')
    j = src.index('} finally {', i)
    apres = src[j:j + 1800]
    assert 'freq_hz: freqAvantHz}' in apres, (
        'la restauration doit être DANS le finally : %r' % apres[:600])
    # ET elle doit être gardée par la SEULE condition qui a un sens : « on a
    # bien décalé quelque chose ». Chercher l'appel seul restait vert quand on
    # remplaçait cette garde par `if(false)` — l'appel était toujours dans le
    # texte, simplement plus jamais atteint. Trouvé par contre-épreuve.
    assert 'if(freqAvantHz){' in apres, (
        'la restauration doit être conditionnée à freqAvantHz, et à rien '
        "d'autre : %r" % apres[:600])
    # Et elle doit précéder toute sortie : on n'accepte pas un `return` avant.
    avant_restauration = apres[:apres.index('freq_hz: freqAvantHz}')]
    assert 'return' not in avant_restauration, (
        'rien ne doit pouvoir sortir avant la restauration : %r'
        % avant_restauration[-400:])


def test_la_restauration_reessaie_avant_d_abandonner(src):
    """Un unique appel qui échoue laisserait la radio décalée sans que
    personne ne le sache — c'est exactement le raisonnement déjà appliqué à
    relacherPtt()."""
    i = src.index('let remise = false;')
    zone = _sans_commentaires(src[i:i + 600])
    m = re.search(r'for\(let essai = 0; essai < (\d+) && !remise', zone)
    assert m, 'la restauration doit boucler : %r' % zone[:300]
    # On LIT le nombre : `essai < \d+` acceptait aussi 1, c'est-à-dire un seul
    # appel — exactement le défaut que ce test prétend interdire. Trouvé par
    # contre-épreuve.
    assert int(m.group(1)) >= 2, (
        'un seul essai ne vaut pas mieux que pas de boucle : essai < %s'
        % m.group(1))


def test_un_echec_de_restauration_DECLENCHE_L_ALARME(src):
    """Le silence serait ici le pire des comportements : l'opérateur
    continuerait à trafiquer sur une fréquence qui n'est pas la sienne."""
    i = src.index('if(!remise){')
    zone = src[i:i + 700]
    assert 'pttAlarme' in zone, (
        "l'alarme existante doit être réutilisée : %r" % zone[:300])
    assert 'FRÉQUENCE NON RESTAURÉE' in zone, zone[:300]
    assert 'freqAvantHz / 1000' in zone, (
        'le message doit donner la fréquence à remettre : %r' % zone[:400])


def test_un_echec_du_DECALAGE_n_arme_pas_la_restauration(src):
    """Si le QSY aller a échoué, la radio n'a pas bougé : tenter un « retour »
    la déplacerait pour de bon. Le drapeau doit être remis à zéro."""
    i = src.index('if(r.ok){ decalage = d; }')
    zone = _sans_commentaires(src[i:i + 300])
    # On vise la branche ELSE explicitement. Chercher « freqAvantHz = 0 » dans
    # la zone restait vert quand on vidait le else : le bloc catch voisin, qui
    # contient la même affectation, suffisait à satisfaire l'assertion.
    # Trouvé par contre-épreuve — « présence au lieu de structure », encore.
    assert re.search(r'else\s*\{\s*freqAvantHz\s*=\s*0\s*;', zone), (
        'un QSY aller refusé doit désarmer le retour DANS le else — sinon on '
        'déplacerait une radio qui n\'a jamais bougé : %r' % zone[:250])


def test_la_source_WSJTX_est_citee_avec_la_formule(src):
    """Valeur de domaine : source citable ou rien. Et la citation doit dire
    d'où elle vient précisément, pas « d'après WSJT-X »."""
    i = src.index('function decalageVfoHz')
    contexte = src[max(0, i - 1800):i]
    assert 'mainwindow.cpp' in contexte and 'setXIT' in contexte, (
        'le fichier et la fonction d\'origine doivent être nommés : %r'
        % contexte[-500:])
    assert 'GPL' in contexte and 'pas recopié' in contexte, (
        'la licence et le fait de ne pas avoir recopié doivent être dits')
