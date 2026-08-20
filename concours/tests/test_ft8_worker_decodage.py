# -*- coding: utf-8 -*-
"""Le décodage FT8 doit tourner HORS du fil principal, sans casser l'émission.

Le décodage bloquait le fil principal 1 942 ms par créneau (mesuré en
navigateur réel sur la page elle-même). Pendant ce temps, ni la cascade ne se
redessine, ni le collecteur audio ne s'exécute : les blocs sautés font dériver
l'horloge du tampon — le décodage se sabotait lui-même. Sorti dans un Worker :
**12 ms**, soit sous les 400 ms de DERIVE_MAX_MS, et les 3 mêmes messages
décodés à l'identique.

⚠️ ASSERTIONS STRUCTURELLES, ET C'EST LE SEUL CHOIX POSSIBLE ICI. py_mini_racer
(le moteur JS de la suite) n'a NI Worker NI window : aucun test de ce dépôt ne
peut exécuter ce chemin. La preuve de comportement a été faite en navigateur
réel — encodage d'un message connu, synthèse GFSK, envoi au Worker, texte
rendu identique — et les chiffres sont consignés dans le commentaire de
logx_ft8.html. Ce banc-ci tient les propriétés que la structure doit garder.
"""
import io
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGE = os.path.join(RACINE, 'logx_ft8.html')
WORKER = os.path.join(RACINE, 'logx_ft8_worker.js')


def _lire(p):
    return io.open(p, encoding='utf-8').read()


def _sans_commentaires(txt):
    """Retire les DEUX formes de commentaire JS.

    Le fichier explique longuement ces mécanismes ; une recherche naïve serait
    satisfaite par la prose. Les blocs `/* … */` comptent autant que les `//`
    — un correctif neutralisé par un bloc commenté passerait sinon au vert."""
    sans_bloc = re.sub(r'/\*.*?\*/', ' ', txt, flags=re.S)
    return '\n'.join(l for l in sans_bloc.split('\n')
                     if not l.strip().startswith('//'))


# ── 1. Le Worker existe et embarque ce qu'il faut ─────────────────────────
def test_le_worker_existe():
    assert os.path.isfile(WORKER), 'logx_ft8_worker.js a disparu'


def test_le_worker_importe_le_codec_et_le_dsp():
    code = _sans_commentaires(_lire(WORKER))
    m = re.search(r'importScripts\(([^)]*)\)', code)
    assert m, 'le Worker n\'importe plus ses modules'
    args = m.group(1)
    assert 'logx_ft8_codec.js' in args, 'le codec n\'est plus importé'
    assert 'logx_ft8_dsp.js' in args, 'le DSP n\'est plus importé'


def test_le_worker_n_utilise_aucun_objet_de_page():
    """Un Worker n'a ni window, ni document, ni localStorage. Les y référencer
    lèverait à la première exécution — donc en trafic, pas en test."""
    code = _sans_commentaires(_lire(WORKER))
    for interdit in ('window.', 'document.', 'localStorage', 'navigator.'):
        assert interdit not in code, (
            f'le Worker référence « {interdit} », qui n\'existe pas dans un '
            'Worker : le décodage lèverait dès le premier créneau')


def test_le_worker_repond_meme_en_cas_d_echec():
    """Sans réponse, la page attendrait un créneau qui ne vient jamais et le
    séquenceur resterait figé sur « j'attends sa réponse »."""
    code = _sans_commentaires(_lire(WORKER))
    i_catch = code.find('catch')
    assert i_catch != -1, 'le Worker n\'attrape plus les erreurs de décodage'
    i_post = code.find('postMessage', i_catch)
    assert i_post != -1, (
        'aucun postMessage après le catch : un décodage en échec laisserait '
        'la page (et le séquenceur) en attente indéfinie')
    # ⚠️ La présence du postMessage APRÈS le catch ne suffit pas : un `return`
    # dans le catch le rendrait inatteignable sans rien déplacer. Première
    # version de ce test : VACANTE, la mutation « return dans le catch »
    # passait au vert.
    corps_catch = code[i_catch:i_post]
    assert 'return' not in corps_catch, (
        'le bloc catch sort par return : le postMessage qui suit devient '
        'inatteignable et la page attend une réponse qui ne vient jamais')


# ── 2. 🚨 La table de hachage est partagée avec l'ÉMISSION ────────────────
def test_le_worker_ne_garde_aucun_etat_entre_deux_creneaux():
    """La table est reconstruite à chaque message. Un état résident diverge de
    la page dès la première entrée ajoutée côté ÉMISSION, et le désaccord
    reste invisible jusqu'au jour où un indicatif composé ne passe plus."""
    code = _sans_commentaires(_lire(WORKER))
    i_msg = code.index('onmessage')
    corps = code[i_msg:]
    assert 'ft8CreateHashTable()' in corps, (
        'la table de hachage n\'est plus reconstruite dans le gestionnaire de '
        'message : le Worker garde un état qui divergera de la page')


def test_la_page_fusionne_les_hachages_sans_remplacer():
    """La page peut avoir enrichi sa table côté ÉMISSION pendant que le Worker
    travaillait : un remplacement en bloc perdrait ces entrées."""
    code = _sans_commentaires(_lire(PAGE))
    i = code.index('function recevoirDecodage')
    corps = code[i:i + 1400]
    assert 'hashTable.byN22.set(' in corps, (
        'la page ne fusionne plus les hachages rendus par le Worker')
    assert not re.search(r'hashTable\s*=', corps), (
        'la page REMPLACE la table de hachage au lieu de la fusionner : les '
        'entrées ajoutées côté émission pendant le décodage seraient perdues')


# ── 3. 🚨 Les échantillons ne doivent PAS être transférés ─────────────────
def test_les_echantillons_partent_par_copie_pas_par_transfert():
    """`fenetre.samples` est réutilisé juste après par surveillerSilenceAnormal.
    Un transfert le viderait côté page : la surveillance mesurerait un tableau
    vide, donc « silence » à chaque créneau."""
    code = _sans_commentaires(_lire(PAGE))
    i = code.index("type: 'decoder'")
    appel = code[max(0, i - 300):i + 600]
    assert 'postMessage(' in appel, 'l\'envoi au Worker a disparu'
    # postMessage(objet) et RIEN d'autre. Un second argument est la liste des
    # transférables — la forme réelle serait `}, [ … ]`, pas `], [ … ]` :
    # une première version de ce test cherchait la mauvaise, et n'aurait donc
    # jamais mordu.
    assert not re.search(r'postMessage\(\s*\{[\s\S]*?\}\s*,\s*\[', appel), (
        'un second argument est passé à postMessage : ce serait la liste des '
        'transférables, et transférer les échantillons les viderait côté page '
        '— surveillerSilenceAnormal mesurerait alors un tableau vide')


# ── 4. Le repli synchrone reste atteignable ───────────────────────────────
def test_le_repli_synchrone_existe_toujours():
    """file://, navigateur ancien, CSP stricte : `new Worker` peut échouer.
    Perdre le décodage vaudrait bien pire que le garder lent."""
    code = _sans_commentaires(_lire(PAGE))
    i = code.index('function obtenirWorkerFt8')
    corps = code[i:i + 1200]
    assert 'try' in corps and 'catch' in corps, (
        'la création du Worker n\'est plus protégée : un contexte sans Worker '
        'ferait perdre TOUT le décodage')
    # ⚠️ Assertion portée sur le BLOC CATCH, pas sur la fonction entière :
    # `ft8Worker = false` existe aussi dans le gestionnaire onerror, et une
    # recherche large l'y trouvait — première version VACANTE, la mutation
    # « catch vidé » passait au vert.
    i_catch = corps.index('catch')
    bloc_catch = corps[i_catch:corps.index('}', corps.index('{', i_catch))]
    assert re.search(r'ft8Worker\s*=\s*false', bloc_catch), (
        'le bloc catch ne marque plus le Worker comme indisponible : la page '
        'retenterait `new Worker` à chaque créneau, sans jamais replier')

    # Et le décodage synchrone doit rester présent dans verifierCycle.
    j = code.index('function verifierCycle')
    cycle = code[j:j + 4000]
    assert 'ft8DecodeAudioAll(' in cycle, (
        'le décodage synchrone de repli a disparu de verifierCycle')


def test_les_deux_chemins_concluent_par_la_meme_fonction():
    code = _sans_commentaires(_lire(PAGE))
    assert 'function conclureCreneau' in code, (
        'conclureCreneau a disparu : les deux chemins divergeraient')
    # Appelée depuis le retour du Worker ET depuis le repli synchrone.
    assert len(re.findall(r'conclureCreneau\(', code)) >= 3, (
        'conclureCreneau n\'est plus appelée par tous les chemins '
        '(retour du Worker, repli synchrone, Worker cassé en vol)')


def test_le_sequenceur_est_prevenu_sur_tous_les_chemins():
    """Un créneau qu'on n'a pas pu décoder reste un créneau où la cible n'a
    rien dit de perceptible. Ne pas prévenir le séquenceur le figerait."""
    code = _sans_commentaires(_lire(PAGE))
    n = len(re.findall(r'seqExaminerCreneau\(', code))
    assert n >= 3, (
        f'seqExaminerCreneau n\'est appelée que {n} fois : il faut au moins '
        'la fin de conclureCreneau, la fenêtre manquante, et le créneau sauté')


def test_un_creneau_saute_ne_lance_pas_un_second_decodage():
    """Deux décodages en vol donneraient des résultats entrelacés, attribués
    au mauvais créneau."""
    code = _sans_commentaires(_lire(PAGE))
    i = code.index('function verifierCycle')
    cycle = code[i:i + 4000]
    # ⚠️ Exiger la CONDITION, pas la simple mention du nom : la variable est
    # aussi ASSIGNÉE quelques lignes plus bas, si bien qu'un `if(false)` à la
    # place du garde laissait le test au vert. Première version VACANTE.
    assert re.search(r'if\s*\(\s*ft8DecodageEnVol\s*\)', cycle), (
        'le garde contre deux décodages simultanés n\'est plus une condition '
        'sur ft8DecodageEnVol : deux décodages en vol donneraient des '
        'résultats entrelacés, attribués au mauvais créneau')


def test_un_jeton_ecarte_les_reponses_perimees():
    code = _sans_commentaires(_lire(PAGE))
    i = code.index('function recevoirDecodage')
    corps = code[i:i + 800]
    assert 'jeton' in corps and 'return' in corps, (
        'aucun jeton de génération : une réponse périmée écrirait les '
        'décodages d\'un créneau dans le compte-rendu d\'un autre')


# ── 4bis. 🚨 L'ORDRE des créneaux remis au séquenceur ─────────────────────
def test_aucun_creneau_n_est_livre_avant_celui_qui_decode_encore():
    """Trouvé par revue adversariale APRÈS une première implémentation qui
    avait le défaut : un créneau sans fenêtre audio, ou sauté, était remis au
    séquenceur IMMÉDIATEMENT — donc AVANT celui qui décodait encore. Le
    séquenceur jugeait N+1 avant N et concluait « elle n'a pas répondu » sur
    une réponse qui n'était pas encore arrivée."""
    code = _sans_commentaires(_lire(PAGE))
    assert 'function livrerOuDifferer' in code, (
        "plus de file d'attente : un créneau peut doubler celui qui décode")
    i = code.index('function livrerOuDifferer')
    corps = code[i:i + 400]
    assert re.search(r'if\s*\(\s*ft8DecodageEnVol\s*\)', corps), (
        'livrerOuDifferer ne regarde plus si un décodage est en vol')

    # Les deux chemins « pas de décodage » doivent passer par la file, JAMAIS
    # appeler seqExaminerCreneau en direct.
    j = code.index('function verifierCycle')
    cycle = code[j:code.index('function conclureCreneau')]
    assert 'seqExaminerCreneau(' not in cycle, (
        'verifierCycle appelle seqExaminerCreneau en direct : le créneau '
        'peut doubler un décodage encore en vol')
    assert cycle.count('livrerOuDifferer(') >= 2, (
        'les deux chemins sans décodage (fenêtre absente, créneau sauté) ne '
        'passent pas tous les deux par la file')


def test_la_file_est_videe_apres_chaque_decodage():
    code = _sans_commentaires(_lire(PAGE))
    i = code.index('function conclureCreneau')
    corps = code[i:]
    i_seq = corps.index('seqExaminerCreneau(')
    assert 'viderCreneauxDifferes()' in corps[i_seq:i_seq + 300], (
        "la file n'est pas vidée après la conclusion du créneau : les "
        'créneaux mis de côté ne seraient jamais remis au séquenceur')


# ── 5. Le Worker doit être EMBARQUÉ dans l'exécutable ─────────────────────
def test_le_worker_est_embarque_par_pyinstaller():
    """Un .js oublié dans le bundle = décodage cassé UNIQUEMENT dans la
    release, invisible en développement. C'est exactement la classe de défaut
    qui a laissé une release cassée deux jours (Tree() vs Analysis())."""
    spec = _lire(os.path.join(RACINE, 'logx.spec'))
    assert "glob.glob('*.js')" in spec.replace('"', "'"), (
        'le spec PyInstaller n\'embarque plus les .js par glob : vérifier que '
        'logx_ft8_worker.js est inclus autrement')
