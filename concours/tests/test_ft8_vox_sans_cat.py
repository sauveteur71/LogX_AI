# -*- coding: utf-8 -*-
"""FT8 : émettre en VOX quand aucun pilotage radio n'est configuré.

LE DÉFAUT. Sans CAT, le serveur répond `non_engage` à la demande de PTT (aucun
pilote appelé), et `envoyerMessage()` sortait là : **aucune forme d'onde
n'était fabriquée**. Or le message affiché à l'opérateur conseillait « passe en
émission au micro ou en VOX » — un conseil impossible à suivre, puisque rien
n'était joué dans la carte son. Il tournait en rond.

TRANCHÉ PAR F4GLD LE 20/08/2026 : le VOX doit marcher réellement. La forme
d'onde part dans la carte son, et c'est le VOX du poste qui déclenche
l'émission. Usage courant en FT8, et c'est ce que le message promettait déjà.

CE QUE ÇA ENGAGE — et c'est tout l'objet de ces tests. Sans commande CAT, le
logiciel ne peut plus faire taire la radio par CAT : **couper le SON devient la
seule coupure réelle**. Deux propriétés deviennent donc critiques, alors
qu'elles étaient anodines avant :

  - `pttDemande` doit passer à VRAI, parce que c'est lui qui rend le bouton
    STOP visible. L'ancien chemin le mettait à FALSE : la radio aurait émis
    avec le bouton d'arrêt caché.
  - le chien de garde doit rester ARMÉ. L'ancien chemin le désarmait.

CE QUE CES TESTS NE PROUVENT PAS. Qu'un VOX réel se déclenche : ça dépend du
poste, de son seuil VOX et du niveau de la carte son. Seul un essai sur l'air
le dira. Ils tiennent la LOGIQUE de la page : le chemin n'est plus coupé, et
les garde-fous qui restent sont armés.

Les commentaires sont dépouillés avant analyse — un pavé qui EXPLIQUE une
propriété satisferait sinon une recherche de texte sans qu'une seule ligne de
code ne l'applique. Piège payé plusieurs fois sur ce dépôt.
"""
import os
import re

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGE = os.path.join(CONCOURS, 'logx_ft8.html')


def _code_sans_commentaires():
    with open(PAGE, encoding='utf-8') as f:
        src = f.read()
    src = re.sub(r'/\*.*?\*/', '', src, flags=re.S)      # blocs /* ... */
    return '\n'.join(re.sub(r'//.*$', '', li) for li in src.splitlines())


def _bloc_vox(code):
    """Le bloc `if(enVox){ ... }` seul, pour ne rien valider sur du code voisin."""
    i = code.index('if(enVox){')
    return code[i:i + 900]


def test_le_vox_est_decide_avant_la_sortie_anticipee():
    """LE point structurel du correctif. Si la décision restait DANS le bloc de
    refus, son `return false` final s'appliquerait aussi au VOX et rien ne
    serait joué — le correctif serait mort-né sans que rien ne le signale.
    """
    code = _code_sans_commentaires()
    assert 'const enVox = !ptt.ok && !!ptt.nonEngage;' in code, (
        'la décision VOX doit être prise avant le bloc de sortie')
    i_vox = code.index('const enVox')
    i_sortie = code.index('if(!ptt.ok && !enVox){')
    assert i_vox < i_sortie, (
        'enVox doit être calculé AVANT le bloc de sortie qui le teste')


def test_la_sortie_anticipee_ne_couvre_plus_le_cas_sans_cat():
    """Contrôle du complément : le bloc qui renonce à émettre doit exclure
    explicitement le VOX, sinon on retombe dans le défaut."""
    code = _code_sans_commentaires()
    assert 'if(!ptt.ok && !enVox){' in code, (
        "le bloc de refus doit exclure le cas VOX ; sans le `&& !enVox` il "
        'reprend tous les refus, VOX compris')


def test_le_bouton_stop_est_visible_pendant_une_emission_vox():
    """Sans CAT, le STOP est la seule barrière. `pttDemande` le commande via
    majBoutonStop() — l'ancien chemin le mettait à false ici."""
    bloc = _bloc_vox(_code_sans_commentaires())
    assert 'pttDemande = true;' in bloc, (
        'le VOX doit poser pttDemande = true : sinon la radio émet et le '
        "bouton STOP reste caché")
    assert 'majBoutonStop();' in bloc, (
        'poser pttDemande ne suffit pas, il faut rafraîchir le bouton')
    assert 'pttDemande = false' not in bloc, (
        'le VOX ne doit surtout pas remettre pttDemande à false')


def test_le_chien_de_garde_reste_arme_en_vox():
    """L'ancien chemin appelait desarmerChienDeGarde() en sortant. En VOX on
    n'en sort plus : il doit rester armé pendant toute la modulation."""
    bloc = _bloc_vox(_code_sans_commentaires())
    assert 'desarmerChienDeGarde' not in bloc, (
        'le chien de garde ne doit pas être désarmé sur le chemin VOX — '
        "c'est un des deux garde-fous qui restent sans CAT")


def test_l_operateur_est_prevenu_que_c_est_le_son_qui_coupe():
    """Intuitivité, et sécurité : sans CAT, « arrêter » ne veut plus dire la
    même chose. Le message doit dire ce qui coupe réellement."""
    code = _code_sans_commentaires()
    bloc = _bloc_vox(code)
    assert 'VOX' in bloc, 'le message doit nommer le VOX'
    assert 'STOP' in bloc and ('Échap' in bloc or 'Echap' in bloc), (
        "le message doit dire PAR QUOI on arrête, puisque le CAT ne peut plus "
        'le faire')


def test_la_coupure_du_son_existe_bien_et_passe_par_la_source_vivante():
    """Le VOX ne s'appuie sur AUCUN mécanisme nouveau : il réutilise la coupure
    audio déjà en place. Ce test le vérifie plutôt que de le supposer — si
    jouerForme() cessait d'inscrire sa source, STOP redeviendrait décoratif
    sans que rien d'autre ne change à l'écran.
    """
    code = _code_sans_commentaires()
    assert 'sourcesTxVivantes.add(src)' in code, (
        'jouerForme() doit inscrire sa source pour que STOP puisse la couper')
    assert 'function couperAudioTx' in code, (
        'la fonction de coupure audio doit exister')
    i_couper = code.index('function couperAudioTx')
    corps = code[i_couper:i_couper + 700]
    assert '.stop(' in corps, (
        "couperAudioTx doit réellement arrêter la source, pas seulement "
        'vider un registre')
