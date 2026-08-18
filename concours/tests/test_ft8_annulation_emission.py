# -*- coding: utf-8 -*-
"""Une émission PROGRAMMÉE doit renoncer si l'opérateur coupe entre-temps.

Défaut mesuré en navigateur le 18/08/2026, horodaté :

    15:38:45  clic « Envoyer »  ->  « Programmé pour 15:39:00 UTC… »
    15:38:49  ordre d'arrêt
    15:38:55  écran : « Émission coupée — retour à l'écoute »
    15:39:00  PTT ON     <- la radio passe en émission
    15:39:12  PTT OFF       12,9 s d'émission, 10,7 s APRÈS l'ordre d'arrêt

envoyerMessage() aligne l'émission sur le prochain créneau UTC de 15 s : il
peut donc s'écouler jusqu'à 16 s entre le clic et le PTT. Pendant tout ce
temps, txArmed n'était testé qu'UNE FOIS, AVANT l'attente. Ni STOP ÉMISSION ni
Échap ne pouvaient rien : stopEmission() coupait un audio pas encore joué et
relâchait un PTT pas encore demandé, pendant que la promesse d'attente suivait
son cours. L'écran affirmait le contraire de ce que faisait la radio.

Ce défaut concerne le chemin MANUEL — le bouton « Envoyer ». Il n'a rien à
voir avec le séquenceur, dont la version qui portait ce correctif est restée
en brouillon : le correctif est donc extrait et porté seul.

Les fonctions sont EXTRAITES de logx_ft8.html et exécutées telles quelles.
"""
import os

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FT8_HTML = os.path.join(CONCOURS, 'logx_ft8.html')

py_mini_racer = pytest.importorskip('py_mini_racer')


def _lire():
    with open(FT8_HTML, encoding='utf-8') as f:
        return f.read()


def _fonction(src, nom):
    for motif in ('function ' + nom, 'window.' + nom + ' ='):
        d = src.find(motif)
        if d >= 0:
            break
    assert d >= 0, nom + ' introuvable'
    d = src.rfind('\n', 0, d) + 1
    prof, i = 0, src.index('{', d)
    while True:
        if src[i] == '{':
            prof += 1
        elif src[i] == '}':
            prof -= 1
            if prof == 0:
                return src[d:i + 1]
        i += 1


# ─── Le contrôle existe, et il est APRÈS l'attente ──────────────────────────

def test_le_jeton_est_capture_avant_l_attente_et_verifie_apres():
    """L'ordre est tout : capturer après l'attente ne servirait à rien, et
    vérifier avant reviendrait au défaut d'origine."""
    corps = _fonction(_lire(), 'envoyerMessage')
    i_capture = corps.index('const maGeneration = generationTx')
    i_attente = corps.index('prochain - Date.now()')
    i_controle = corps.index('maGeneration !== generationTx')
    assert i_capture < i_attente < i_controle


def test_le_controle_couvre_aussi_le_desarmement():
    """Décocher « Activer l'émission » pendant l'attente est un ordre d'arrêt.
    Le jeton le couvre déjà (onArmChange l'incrémente), mais txArmed est
    revérifié en plus : deux barrières valent mieux qu'une sur ce chemin."""
    corps = _fonction(_lire(), 'envoyerMessage')
    i = corps.index('maGeneration !== generationTx')
    assert '!txArmed' in corps[i:i + 120]


def test_le_controle_precede_toute_prise_de_ptt():
    """Si le contrôle tombait après armerChienDeGarde()/pttOn(true), la radio
    serait déjà passée en émission."""
    corps = _fonction(_lire(), 'envoyerMessage')
    i_controle = corps.index('maGeneration !== generationTx')
    i_ptt = corps.index('pttOn(true)')
    assert i_controle < i_ptt


@pytest.mark.parametrize('chemin', ['stopEmission', 'onArmChange', 'arreterRx'])
def test_chaque_chemin_d_arret_annule_les_emissions_programmees(chemin):
    assert 'annulerEmissionsProgrammees' in _fonction(_lire(), chemin), chemin


def test_stop_annule_avant_de_couper_l_audio():
    """L'annulation doit être le PREMIER geste : couper l'audio et relâcher le
    PTT ne sert à rien tant que l'émission n'est pas encore partie, et c'est
    précisément ce cas que le bouton ne traitait pas."""
    corps = _fonction(_lire(), 'stopEmission')
    assert corps.index('annulerEmissionsProgrammees') < corps.index('couperAudioTx')


# ─── L'opérateur doit POUVOIR couper : bouton visible, Échap actif ──────────

def test_le_bouton_de_coupure_est_visible_pendant_l_attente():
    """Il était piloté par le seul pttDemande, donc masqué exactement pendant
    la fenêtre où il aurait servi."""
    assert 'emissionProgrammee' in _fonction(_lire(), 'majBoutonStop')


def test_echap_agit_pendant_l_attente():
    src = _lire()
    i = src.index("e.key === 'Escape'")
    assert 'emissionProgrammee' in src[i:i + 160]


def test_l_indicateur_est_leve_puis_baisse_autour_de_l_attente():
    """Laissé à true après coup, le bouton resterait affiché sans rien à
    couper — une commande qui ment est pire qu'une commande absente."""
    corps = _fonction(_lire(), 'envoyerMessage')
    i_attente = corps.index('prochain - Date.now()')
    assert 'emissionProgrammee = true' in corps[:i_attente]
    assert 'emissionProgrammee = false' in corps[i_attente:]


# ─── Comportement, sur les vraies fonctions ─────────────────────────────────

def _ctx():
    """Charge la SEULE fonction de compteur : stopEmission est asynchrone et
    tire trop de dépendances de la page pour être exécutée hors navigateur.
    Son câblage sur le compteur est vérifié statiquement plus haut
    (test_chaque_chemin_d_arret_annule_les_emissions_programmees et
    test_stop_annule_avant_de_couper_l_audio) ; ce qui se vérifie ICI, c'est
    que le compteur lui-même se comporte comme un jeton fiable."""
    ctx = py_mini_racer.MiniRacer()
    ctx.eval('var generationTx = 0;')
    ctx.eval(_fonction(_lire(), 'annulerEmissionsProgrammees'))
    return ctx


def test_annuler_fait_avancer_le_jeton():
    """La preuve de comportement : après annulation, toute émission programmée
    AVANT se reconnaît périmée en comparant sa valeur capturée."""
    ctx = _ctx()
    avant = ctx.eval('generationTx')
    ctx.eval('annulerEmissionsProgrammees();')
    assert ctx.eval('generationTx') > avant


def test_le_jeton_ne_recule_jamais():
    """Un compteur qui reviendrait en arrière ferait passer une émission
    périmée pour valide."""
    ctx = _ctx()
    vus = []
    for _ in range(5):
        ctx.eval('annulerEmissionsProgrammees();')
        vus.append(ctx.eval('generationTx'))
    assert vus == sorted(vus) and len(set(vus)) == len(vus)


def test_le_message_d_annulation_est_explicite():
    """Une émission qui ne part pas doit le DIRE : sans message, l'opérateur
    ne sait pas si son ordre a été pris en compte."""
    corps = _fonction(_lire(), 'envoyerMessage')
    i = corps.index('maGeneration !== generationTx')
    assert 'annulée' in corps[i:i + 400].lower()
