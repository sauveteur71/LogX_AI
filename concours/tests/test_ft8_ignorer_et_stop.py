# -*- coding: utf-8 -*-
"""Deux trous du chemin d'arrêt / de non-perte du séquenceur FT8.

Les deux viennent d'une revue adversariale dont le diagnostic INITIAL était
faux, et dont la RÉFUTATION a désigné les vrais défauts. Mesuré à la main
avant d'écrire une ligne.

1. « IGNORER » APRÈS UN ÉCHEC D'ÉCRITURE EFFAÇAIT LA FICHE SANS TRACE.
   `marquerNonEnregistre` n'avait qu'UN site d'appel : `offrirLogQso`, à
   l'arrivée d'un indicatif DIFFÉRENT. La branche d'échec de
   `confirmerLogQso` ne marque rien et laisse le bandeau OUVERT — délibéré,
   pour permettre un nouvel essai. Le seul geste qui referme ce bandeau est
   « Ignorer », qui mettait `qsoEnAttente` à null sans rien poser. Un clic,
   un indicatif, plus rien à l'écran.

2. LE BOUTON STOP N'ÉTAIT TENU PAR AUCUN TEST. `window.seqStop` — le bouton
   rouge qui arrête une émission automatique — n'apparaissait **0 fois** dans
   les 16 fichiers de tests FT8 (compté). On pouvait le neutraliser sans
   qu'aucun test ne rougisse, sur la fonction qui émet sans surveillance.

⚠️ ASSERTIONS STRUCTURELLES, ET C'EST DÉLIBÉRÉ. Un banc de COMPORTEMENT
serait ici VACANT : les mannequins DOM du dépôt (`__El`/`__El2` dans
test_ft8_sequenceur.py) n'ont ni `querySelector` ni `remove`, et leur
`innerHTML` n'est qu'une chaîne — y poser `innerHTML=''` ne vide pas
`children`. Un test « la ligne rouge survit » y passerait au vert AVEC le
défaut en place. C'est le piège maison : « un test écrit contre un mannequin
ne contraint que le mannequin ».
"""
import io
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PAGE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    'logx_ft8.html')


def _sans_commentaires(txt):
    """Retire les commentaires JS — les DEUX formes.

    Indispensable ici : le fichier EXPLIQUE ces défauts en toutes lettres, et
    une recherche naïve serait satisfaite par la prose qui les décrit.

    ⚠️ Les blocs `/* … */` comptent autant que les lignes `//`. Une première
    version ne retirait que les `//` : la contre-épreuve a alors montré qu'une
    ligne simplement commentée en `/* seq = null; */` laissait le test au
    VERT — le défaut était neutralisé et le banc ne le voyait pas. C'est le
    piège maison, attrapé sur ce banc même."""
    sans_bloc = re.sub(r'/\*.*?\*/', ' ', txt, flags=re.S)
    return '\n'.join(l for l in sans_bloc.split('\n')
                     if not l.strip().startswith('//'))


def _corps(nom, taille=1400):
    src = io.open(PAGE, encoding='utf-8').read()
    i = src.index(nom)
    return _sans_commentaires(src[i:i + taille])


# ── 1. « Ignorer » laisse une trace après un échec ────────────────────────
def test_ignorer_apres_echec_pose_une_ligne_non_enregistre():
    corps = _corps('window.annulerLogQso')
    assert re.search(r'marquerNonEnregistre\s*\(', corps), (
        '« Ignorer » referme le bandeau sans marquer la fiche : après un '
        'échec d\'écriture, un seul clic la fait disparaître sans trace')


def test_le_marquage_est_conditionne_a_un_echec_reel():
    """Sans garde, « Ignorer » sur un QSO qu'on refuse simplement poserait
    une ligne rouge mensongère."""
    corps = _corps('window.annulerLogQso')
    m = re.search(r'if\s*\([^)]*qsoEchecEcriture[^)]*\)\s*'
                  r'marquerNonEnregistre', corps)
    assert m, ('le marquage n\'est pas conditionné à un échec d\'écriture : '
               'refuser un QSO poserait une trace « NON ENREGISTRÉ » fausse')


def test_le_drapeau_est_arme_par_la_branche_d_echec():
    # Fenêtre large : le corps de confirmerLogQso fait plus de 60 lignes, et
    # la branche d'échec est tout à la fin (constaté en écrivant ce test).
    corps = _corps('window.confirmerLogQso', 5000)
    i_echec = corps.find('if(!ok)')
    assert i_echec != -1, 'la branche d\'échec de confirmerLogQso a disparu'
    assert 'qsoEchecEcriture = true' in corps[i_echec:], (
        'la branche d\'échec n\'arme plus le drapeau : « Ignorer » '
        'redeviendrait silencieux')


def test_le_drapeau_est_baisse_quand_la_ligne_est_deja_posee():
    """offrirLogQso pose déjà la ligne rouge pour l'indicatif précédent ;
    laisser le drapeau armé en poserait une SECONDE, pour un QSO que
    l'opérateur ne fait que refuser."""
    corps = _corps('function offrirLogQso', 1200)
    i_marque = corps.find('marquerNonEnregistre(')
    assert i_marque != -1
    assert 'qsoEchecEcriture = false' in corps[i_marque:], (
        'le drapeau reste armé après la pose de la ligne rouge')


# ── 2. Le bouton STOP est enfin tenu ──────────────────────────────────────
def test_le_bouton_stop_arrete_bien_la_sequence():
    """`window.seqStop` n'apparaissait dans AUCUN des 16 fichiers de tests
    FT8. C'est le bouton d'arrêt d'une émission sans surveillance."""
    corps = _corps('window.seqStop', 200)
    assert re.search(r'window\.seqStop\s*=\s*function\s*\(\s*\)\s*\{\s*'
                     r'seqArreter\s*\(', corps), (
        'seqStop n\'appelle plus seqArreter : le bouton STOP n\'arrête plus '
        'la séquence')


def test_le_bouton_stop_est_bien_cable_sur_seqStop():
    """L'autre moitié de la propriété : la fonction peut être parfaite, si
    le bouton n'y est plus câblé l'opérateur n'a plus d'arrêt."""
    src = io.open(PAGE, encoding='utf-8').read()
    m = re.search(r'<button[^>]*id="seqStopBtn"[^>]*>', src)
    assert m, 'le bouton STOP a disparu de la page'
    assert 'seqStop()' in m.group(0), (
        f'le bouton STOP n\'appelle plus seqStop() : {m.group(0)[:120]}')


def test_seqarreter_coupe_reellement_la_sequence():
    """Ce que seqStop délègue doit encore couper : sans cette assertion, le
    test précédent serait satisfait par un seqArreter devenu inerte."""
    corps = _corps('function seqArreter', 900)
    assert re.search(r'\bseq\s*=\s*null', corps), (
        'seqArreter ne remet plus `seq` à null : la séquence survivrait à '
        'un appui sur STOP')
