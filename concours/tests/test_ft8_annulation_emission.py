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
import re

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FT8_HTML = os.path.join(CONCOURS, 'logx_ft8.html')

py_mini_racer = pytest.importorskip('py_mini_racer')


def _lire():
    with open(FT8_HTML, encoding='utf-8') as f:
        return f.read()


def _sans_commentaires(js):
    """Retire les commentaires JS AVANT toute analyse du code.

    Piège confirmé par revue adversariale le 18/08/2026, et reproduit : un
    test qui cherche « generationTx » dans le texte brut d'une fonction est
    satisfait par le PAVÉ DE COMMENTAIRE qui explique generationTx. On pouvait
    donc remplacer la seule ligne de contrôle réelle par « if(false) » sans
    faire tomber un seul test. Un test dont la mission est d'interdire une
    fiction ne doit pas pouvoir être satisfait par de la prose.

    Le `(?<!:)` évite d'amputer « https:// » dans une chaîne — ce fichier n'en
    contient pas aujourd'hui, mais un dépouilleur qui casse le jour où l'on
    ajoute une URL serait un piège à retardement.
    """
    js = re.sub(r'/\*[\s\S]*?\*/', '', js)
    return re.sub(r'(?<!:)//[^\n]*', '', js)


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
    """Commentaires DÉPOUILLÉS : chacune de ces trois fonctions porte un pavé
    qui EXPLIQUE pourquoi elle doit faire vieillir le jeton, et ce pavé cite
    forcément annulerEmissionsProgrammees. Sans dépouillement, on pouvait
    supprimer l'appel réel — le seul geste qui empêche une trame déjà
    programmée de partir — sans que ce test bouge d'un pouce.

    C'est exactement ce qu'a démontré la revue adversariale sur le test frère
    du séquenceur (mutation en `if(false)`, 47 tests verts)."""
    corps = _sans_commentaires(_fonction(_lire(), chemin))
    # STRUCTURE, pas présence. `assert 'annulerEmissionsProgrammees' in corps`
    # était satisfait par `if(false) annulerEmissionsProgrammees();` — vérifié
    # par mutation : la suite restait verte alors que le geste était neutralisé.
    # On exige donc l'appel en TÊTE D'INSTRUCTION, seule forme qui s'exécute
    # inconditionnellement.
    assert re.search(r'(?m)^\s*annulerEmissionsProgrammees\(\);', corps), (
        '%s doit appeler annulerEmissionsProgrammees INCONDITIONNELLEMENT '
        "(l'appel ne doit pas être sous une condition)" % chemin)


def test_stop_annule_avant_de_couper_l_audio():
    """L'annulation doit être le PREMIER geste : couper l'audio et relâcher le
    PTT ne sert à rien tant que l'émission n'est pas encore partie, et c'est
    précisément ce cas que le bouton ne traitait pas.

    Comparer des positions dans du texte NON dépouillé était doublement
    fragile : un commentaire mentionnant l'un des deux noms suffisait à
    inverser l'ordre mesuré, sans que l'ordre du CODE ait changé."""
    corps = _sans_commentaires(_fonction(_lire(), 'stopEmission'))
    assert corps.index('annulerEmissionsProgrammees') < corps.index('couperAudioTx')


# ─── L'opérateur doit POUVOIR couper : bouton visible, Échap actif ──────────

def test_le_bouton_de_coupure_est_visible_pendant_l_attente():
    """Il était piloté par le seul pttDemande, donc masqué exactement pendant
    la fenêtre où il aurait servi. Commentaires dépouillés, même raison que
    ci-dessus."""
    assert 'emissionProgrammee' in _sans_commentaires(
        _fonction(_lire(), 'majBoutonStop'))


def test_echap_agit_dans_les_trois_etats_ou_quelque_chose_peut_partir():
    """Échap ne doit laisser AUCUN trou, et les trois états ne se recouvrent
    pas :

        pttDemande          le PTT est engagé, la trame est sur l'air
        emissionProgrammee  une trame attend son créneau (jusqu'à 16 s)
        seq                 une séquence tourne, même entre deux trames

    Ce test cherchait auparavant la chaîne littérale « e.key === 'Escape' ».
    Il figeait donc l'ÉCRITURE de la condition, pas ce qu'elle garantit : la
    réécrire en « if(e.key !== 'Escape') return; » — strictement équivalente,
    et plus lisible avec trois états — le faisait rougir sans qu'aucune
    régression n'ait eu lieu. On teste maintenant la propriété.

    Et on dépouille les commentaires avant d'analyser : le pavé qui EXPLIQUE
    ces trois états les nomme tous les trois. Sans dépouillement, on pourrait
    supprimer la condition entière sans faire tomber le test — défaut
    réellement constaté ailleurs dans ce chantier."""
    src = _sans_commentaires(_lire())
    i = src.index('Escape')
    zone = src[i:i + 400]
    assert 'stopEmission' in zone, 'Échap doit appeler la coupure'
    for etat in ('pttDemande', 'emissionProgrammee', 'seq'):
        assert etat in zone, "Échap ignore l'état %s" % etat


def test_l_indicateur_est_leve_puis_baisse_autour_de_l_attente():
    """Laissé à true après coup, le bouton resterait affiché sans rien à
    couper — une commande qui ment est pire qu'une commande absente."""
    corps = _fonction(_lire(), 'envoyerMessage')
    i_attente = corps.index('prochain - Date.now()')
    assert 'emissionProgrammee = true' in corps[:i_attente]
    assert 'emissionProgrammee = false' in corps[i_attente:]


# ─── Comportement, sur les vraies fonctions ─────────────────────────────────

def _ctx(onde_en_vol=False):
    """Charge la VRAIE annulerEmissionsProgrammees avec des mannequins qui
    ENREGISTRENT ce qu'elle fait. stopEmission est asynchrone et tire trop de
    dépendances de la page pour être exécutée hors navigateur ; son câblage sur
    le compteur est vérifié statiquement plus haut. Ce qui se vérifie ICI,
    c'est le comportement de l'annulation elle-même.

    `onde_en_vol` simule une trame DÉJÀ en cours de lecture — le cas où le
    jeton, à lui seul, ne peut rien."""
    ctx = py_mini_racer.MiniRacer()
    ctx.eval("""
      var generationTx = 0;
      var __audioCoupe = 0, __pttRelache = 0;
      var pttDemande = true;
      var sourcesTxVivantes = new Set();
      function couperAudioTx(){ __audioCoupe++; sourcesTxVivantes.clear(); }
      function relacherPtt(){ __pttRelache++; return Promise.resolve(true); }
    """)
    if onde_en_vol:
        ctx.eval("sourcesTxVivantes.add({stop: function(){}});")
    ctx.eval(_fonction(_lire(), 'annulerEmissionsProgrammees'))
    return ctx


def test_annuler_coupe_la_trame_deja_en_l_air():
    """LE défaut trouvé par la deuxième revue adversariale.

    Le jeton ne peut rien contre une trame DÉJÀ en cours de lecture : il
    n'atteint que les émissions encore en attente de leur créneau. Or
    couperAudioTx() n'était appelée que par stopEmission() et le chien de
    garde. Trois gestes que l'opérateur lit comme « arrête d'émettre » —
    couper l'écoute, décocher « Activer l'émission », STOP SÉQUENCE — laissaient
    donc la forme d'onde moduler le poste jusqu'à son terme, soit jusqu'à
    12,64 s après l'ordre. Mesuré à 7,6 s pour un ordre donné en milieu de
    trame, pendant que l'écran affichait « arrêté »."""
    ctx = _ctx(onde_en_vol=True)
    ctx.eval('annulerEmissionsProgrammees();')
    assert ctx.eval('__audioCoupe') == 1, "l'audio en vol n'a pas été coupé"
    assert ctx.eval('__pttRelache') == 1, 'le PTT est resté engagé'


def test_annuler_ne_touche_a_rien_quand_aucune_onde_ne_joue():
    """Contre-épreuve : couper l'audio et relâcher le PTT alors que rien n'est
    en l'air enverrait des ordres radio inutiles à chaque arrêt de séquence, et
    ferait clignoter l'état d'émission sans raison."""
    ctx = _ctx(onde_en_vol=False)
    ctx.eval('annulerEmissionsProgrammees();')
    assert ctx.eval('__audioCoupe') == 0
    assert ctx.eval('__pttRelache') == 0


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


# ─── Ré-entrance et coupure de TOUTES les ondes ─────────────────────────────
# Deux constats critiques confirmés par la revue adversariale du 18/08/2026.
# Ils sont ANTÉRIEURS à ce correctif, mais ils démentaient précisément la
# promesse d'écran qu'il renforce (« Émission coupée — retour à l'écoute »).

def test_envoyer_message_refuse_une_seconde_emission_programmee():
    """repondreEtEnvoyer() (double-clic) appelle envoyerMessage DIRECTEMENT :
    sendBtn.disabled ne protégeait rien. Deux double-clics dans la même
    fenêtre de 15 s programmaient DEUX émissions sur le MÊME créneau — deux
    PTT et deux ondes FT8 simultanées. Mesuré : la seconde onde modulait
    encore 11,6 s après l'ordre d'arrêt, l'écran affichant le contraire."""
    corps = _fonction(_lire(), 'envoyerMessage')
    i_garde = corps.index('if(emissionProgrammee)')
    i_prog = corps.index('emissionProgrammee = true')
    assert i_garde < i_prog, 'la garde doit précéder la programmation'
    # Et elle doit le DIRE : un refus silencieux laisse cliquer sans comprendre.
    assert 'txStatus' in corps[i_garde:i_prog]


def test_la_garde_ne_bloque_pas_sur_un_ptt_non_relache():
    """Nuance relevée par le vérificateur : pttDemande peut rester à true
    après un relâchement non confirmé. L'inclure dans la garde interdirait
    toute émission ultérieure — alors que le code prévoit explicitement de la
    permettre (emissionAnterieureNonRelachee)."""
    corps = _fonction(_lire(), 'envoyerMessage')
    i = corps.index('if(emissionProgrammee)')
    assert 'pttDemande' not in corps[i:i + 80]
    assert 'emissionAnterieureNonRelachee' in corps, \
        'le chemin qui autorise une émission après un PTT non relâché doit rester'


def test_couper_audio_arrete_toutes_les_ondes_vivantes():
    """La prise était UNIQUE et écrasée par la seconde onde : couperAudioTx()
    n'arrêtait que la dernière. Un ensemble, parcouru intégralement."""
    src = _lire()
    assert 'sourceTxEnCours' not in src, 'la prise unique ne doit plus exister'
    corps = _fonction(src, 'couperAudioTx')
    assert 'for(' in corps and 'sourcesTxVivantes' in corps
    assert 'Array.from' in corps, \
        'copier avant de parcourir : stop() retire l\'élément via onended'


def test_chaque_onde_est_enregistree_puis_retiree():
    """Une onde jamais retirée de l'ensemble ferait grossir la collection à
    chaque émission, et couperAudioTx() appellerait stop() sur des sources
    mortes à l'infini."""
    corps = _fonction(_lire(), 'jouerForme')
    assert 'sourcesTxVivantes.add(src)' in corps
    assert 'sourcesTxVivantes.delete(src)' in corps
