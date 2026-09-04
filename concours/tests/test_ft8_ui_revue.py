# -*- coding: utf-8 -*-
"""Revue UI de la page FT8 (F4GLD, 03/09/2026) — garde-fous structurels.

Deux défauts corrigés, chacun invisible en banc DOM (règle du dépôt : on assère
la STRUCTURE du source) :

  (d) « Journal d'émission illisible » : les règles .tx-audit utilisaient
      `color:var(--fg,#E9E6DF)` — or `--fg` N'EXISTE PAS dans la charte (le token
      est `--text`). Repli sur #E9E6DF (gris clair) : lisible la nuit, ILLISIBLE
      le jour (gris clair sur fond crème). Un token fantôme ne se voit pas en
      relecture rapide et ne casse aucun test « présence de couleur ».

  (f) « CQ ENTENDUS » : le SNR (dB) de chaque station n'était pas affiché, alors
      qu'il est LE critère pour choisir qui appeler. Ajouté au rendu + stocké.
"""
import os
import re

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FT8 = os.path.join(BASE, 'logx_ft8.html')


def _src():
    with open(FT8, encoding='utf-8') as f:
        return f.read()


def _sans_commentaires(txt):
    """Retire blocs /* */ et lignes //. Sans ça, un mot présent dans un
    commentaire explicatif satisfait une assertion censée viser le CODE."""
    sans_bloc = re.sub(r'/\*.*?\*/', ' ', txt, flags=re.S)
    return '\n'.join(l for l in sans_bloc.split('\n')
                     if not l.strip().startswith('//'))


# ── (d) plus aucun token fantôme --fg (illisible en mode jour) ───────────────

def test_aucun_token_fantome_fg():
    """`--fg` n'est défini nulle part (ni charte logx_theme.css ni page) : toute
    règle `var(--fg,...)` retombe sur son repli codé en dur, ce qui casse le mode
    jour. La charte expose `--text` (sombre le jour, clair la nuit) — c'est lui
    qu'il faut. Ce test ROUGIT si le token fantôme réapparaît."""
    assert 'var(--fg' not in _src(), \
        "token fantôme var(--fg...) réintroduit -> texte illisible en mode jour"


def test_journal_emission_utilise_le_token_de_theme():
    """Le journal d'émission (.ta-l) doit porter une couleur de la charte, donc
    suivre jour/nuit. On exige la structure : la règle .ta-l référence var(--text)."""
    src = _src()
    i = src.index('.tx-audit .ta-l{')
    regle = src[i:src.index('}', i)]
    assert 'var(--text)' in regle, \
        ".ta-l (lignes du journal d'émission) n'utilise pas var(--text)"


# ── (f) CQ ENTENDUS : le SNR est stocké ET affiché ──────────────────────────

def test_cq_seen_stocke_le_snr():
    """La station en CQ est mémorisée AVEC son SNR (sinon rien à afficher)."""
    src = _src()
    assert 'cqSeen.set(call, {freqHz, grid, ts: slotMs, snr: snrDb})' in src, \
        "cqSeen ne stocke pas le SNR (snr: snrDb) au moment du décodage CQ"


def test_cq_list_affiche_le_snr():
    """rendreCqList doit produire un élément SNR à partir de info.snr — structure,
    pas simple présence : la classe .snr est bien émise depuis info.snr."""
    src = _src()
    i = src.index('function rendreCqList(')
    corps = src[i:src.index('\n  }', i)]
    assert 'info.snr' in corps, "rendreCqList n'exploite pas info.snr"
    assert 'class="snr' in corps, "rendreCqList n'émet pas d'élément .snr (SNR non affiché)"


# ── (a) appairage entrée/sortie audio par appareil physique (groupId) ────────

def test_options_audio_portent_le_groupid():
    """Entrée ET sortie doivent porter data-group (le groupId partagé d'un même
    appareil physique) — sans lui, l'appairage automatique est impossible."""
    src = _src()
    assert src.count('data-group="${esc(d.groupId)}"') >= 2, \
        "les <option> audio (entrée+sortie) ne portent pas data-group"


def test_appairage_entree_sortie_sur_changement():
    """Choisir un périphérique sélectionne l'autre du même appareil : un
    appairage + des écouteurs de changement sur les deux sélecteurs."""
    src = _src()
    assert 'const apparier =' in src, "fonction d'appairage absente"
    assert "selIn.addEventListener('change'" in src, "pas d'écouteur sur l'entrée"
    assert "selOut.addEventListener('change'" in src, "pas d'écouteur sur la sortie"


# ── (c) écoute automatique, plus de « bouton pour démarrer » ─────────────────

def test_ecoute_demarre_automatiquement():
    """demarrerEcoute existe ET est appelé au CHARGEMENT des périphériques :
    l'écoute ne dépend plus d'un clic. On vise l'appel d'auto-démarrage dans le
    bloc de chargement (repéré par `apparier`, qui n'existe QUE là) — un simple
    comptage serait satisfait par la définition `demarrerEcoute(){` elle-même."""
    src = _src()
    assert 'function demarrerEcoute(' in src, "helper demarrerEcoute absent"
    # Ancre newline + 6 espaces : c'est l'appel AUTONOME d'auto-démarrage (dans
    # le try de chargement des périphériques). ATTENTION au piège de sous-chaîne :
    # `redemarrerEcoute();` CONTIENT `demarrerEcoute();`, et les 2 autres appels
    # sont indentés de 4 espaces — seul l'auto-start est en `\n      ` (6 espaces).
    assert '\n      demarrerEcoute();' in src, \
        "l'appel d'auto-démarrage (demarrerEcoute() au chargement) est absent : écoute non auto"


def test_toggle_ne_gate_plus_le_demarrage():
    """window.toggleRx ne doit plus être un « démarrer » à part entière : quand
    l'écoute est inactive, il délègue à demarrerEcoute (démarrage auto), pas à
    l'ancienne séquence de bouton."""
    src = _src()
    i = src.index('window.toggleRx = function(){')
    corps = src[i:src.index('\n  };', i)]
    assert 'demarrerEcoute()' in corps, "toggleRx ne délègue pas à demarrerEcoute"


# ── (g) vu-mètre de niveau audio RX ─────────────────────────────────────────

def test_vumetre_rx_present_et_alimente():
    """Barre du vu-mètre dans le HTML + fonction de mise à jour + alimentation
    par la boucle waterfall (sinon la barre resterait figée)."""
    src = _src()
    assert 'id="rxNiveauBarre"' in src, "élément du vu-mètre RX absent du HTML"
    assert 'function majNiveauRx(' in src, "fonction majNiveauRx absente"
    assert 'majNiveauRx(dataArray, nBins)' in src, \
        "le vu-mètre n'est pas alimenté par boucleWaterfall"


# ── (e) axe du waterfall non tronqué (labels centrés, axe rehaussé) ──────────

def test_axe_waterfall_non_tronque():
    """« Il manque des bouts sous le waterfall » (même en plein écran = clip
    FIXE) : l'axe de 16 px coupait le bas des labels (baseline alphabétique à
    0.75 h). Axe rehaussé (22 px) + baseline CENTRÉE -> labels entiers."""
    src = _src()
    assert 'canvas#axisCanvas{width:100%;height:22px' in src, "l'axe du waterfall n'a pas été rehaussé"
    i = src.index('function dessinerAxe(')
    corps = src[i:src.index('\n  }', i)]
    assert "textBaseline = 'middle'" in corps, "dessinerAxe ne centre pas verticalement les labels"
    assert 'h*0.5)' in corps, "labels pas dessinés au centre vertical de l'axe"


# ── (b) indicatif relu sans recharger + invalidation TX si changement ───────

def test_identite_relue_au_focus():
    """La page relit l'indicatif quand elle redevient visible / reprend le
    focus : plus de « CQ TM6KJS » figé jusqu'à un F5."""
    src = _src()
    assert "addEventListener('visibilitychange'" in src, "pas de relecture à la visibilité"
    assert "window.addEventListener('focus'" in src, "pas de relecture au focus"


def test_changement_indicatif_invalide_l_emission():
    """tx-human-consent : un changement d'indicatif (identité station) doit
    INVALIDER une émission armée/programmée (désarmement via onArmChange), pas
    la laisser partir avec l'ancien indicatif sans nouvelle validation."""
    src = _src()
    i = src.index('async function chargerIdentite(')
    # DÉPOUILLER les commentaires : « onArmChange » apparaît aussi dans un pavé
    # explicatif de la fonction — sans ça, retirer le CODE d'invalidation
    # laisserait le test vert (le mot survit dans le commentaire).
    corps = _sans_commentaires(src[i:i + 1700])
    assert 'const ancienCall = myCall' in corps, "chargerIdentite ne mémorise pas l'ancien indicatif"
    assert 'ancienCall !== myCall' in corps, "aucune détection de changement d'indicatif"
    assert 'onArmChange()' in corps, \
        "un changement d'indicatif n'appelle pas onArmChange() : émission non invalidée (tx-human-consent violé)"
