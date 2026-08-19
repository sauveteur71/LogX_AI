# -*- coding: utf-8 -*-
"""Propreté du signal émis : avertir quand le ton salit la bande.

Parti d'un constat de F4GLD (19/08/2026) : « je constate que wsjt x des que je
passe en émission passe en split sur la meme fréquence il doit y avoir une
raison ».

Il y en a une, et elle est DOCUMENTÉE. Guide utilisateur WSJT-X (Joseph H.
Taylor Jr, K1JT, v2.6.0 et v2.6.1), à propos des modes de split « Rig » et
« Fake It » : garder l'audio d'émission « in the range 1500 to 2000 Hz so that
audio harmonics cannot pass through the Tx sideband filter ».

LE MÉCANISME. Notre signal est un ton audio injecté dans un émetteur SSB, qui
produit inévitablement des harmoniques. Un ton de 700 Hz a son harmonique 2 à
1400 Hz — EN PLEIN DANS la passe-bande : elle part sur l'air comme parasite,
sur une fréquence où quelqu'un d'autre trafique. Un ton de 1600 Hz a la sienne
à 3200 Hz, hors du filtre, donc supprimée.

CE QUE CETTE PAGE FAIT : elle émet le ton tel quel, sans toucher au VFO. Elle
ne peut donc pas encore ÉVITER le parasite — mais elle cesse de le produire en
silence. Le décalage automatique du VFO (« Fake It ») demande le CAT et une
vérification sur une vraie radio ; il n'est pas fait ici.

VÉRIFIÉ EN NAVIGATEUR (le seul moyen pour ce défaut-ci — voir plus bas) :
700 Hz -> avis « harmonique 2 à 1400 Hz » ; 1200 -> « 2400 Hz » ; 1500, 1800 et
2000 -> aucun avis ; 2500 -> avis de bord de passe-bande, texte différent.

🚨 DÉFAUT INTRODUIT PUIS CORRIGÉ, à retenir : la première rédaction avait
inséré tout ce bloc DANS le corps de dessinerAxe() — la fonction qui trace
l'axe du waterfall. Le code était syntaxiquement parfait,
test_bloc_script_entier_s_evalue_jusqu_au_bout restait VERT, et pourtant
majTonPropre n'était jamais défini au chargement (window.majTonPropre ===
undefined en navigateur). Un test de syntaxe ne peut pas voir ça : il faut
vérifier que la fonction EXISTE. C'est ce que fait le test de portée ci-dessous.
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


@pytest.fixture(scope='module')
def src():
    return _lire()


@pytest.fixture
def page():
    """Exécute majTonPropre EXTRAITE de la page, avec un DOM minimal."""
    src = _lire()
    deb = src.index('const TON_PROPRE_MIN')
    # Le bloc se termine là où commence la fonction suivante du même niveau.
    fin = src.index('  function clicWaterfall(evt){', deb)
    ctx = py_mini_racer.MiniRacer()
    ctx.eval("""
    var __champ = {value: '1500'};
    var __avis = {style: {display: 'none'}, className: '', innerHTML: '',
                  textContent: '', addEventListener: function(){}};
    var document = {getElementById: function(id){
      if(id === 'ft8Tone0') return __champ;
      if(id === 'tonAvis') return __avis;
      return null;   // #tonCorriger : le lien n'existe pas dans ce socle
    }};
    var window = {};
    """)
    ctx.eval(src[deb:fin].replace('window.majTonPropre', 'var majTonPropre'))
    return ctx


def _avis(page, ton):
    page.eval('__champ.value = %r; majTonPropre();' % str(ton))
    return {'visible': page.eval("__avis.style.display !== 'none'"),
            'texte': page.eval('__avis.innerHTML') or ''}


# ═══════════════════════════════════════════════════════════════════════════
# §1. LA RÈGLE, ET SA SOURCE
# ═══════════════════════════════════════════════════════════════════════════

def test_les_bornes_sont_celles_du_guide_WSJTX(src):
    """1500 et 2000 ne sont pas choisies ici : elles sont REPRISES du guide
    WSJT-X. Une valeur de domaine sans source citable est interdite dans ce
    dépôt, et une valeur habillée d'une fausse source est pire encore."""
    assert re.search(r'TON_PROPRE_MIN\s*=\s*1500', src), 'borne basse'
    assert re.search(r'TON_PROPRE_MAX\s*=\s*2000', src), 'borne haute'
    i = src.index('TON_PROPRE_MIN')
    contexte = src[max(0, i - 2200):i]
    assert 'WSJT-X' in contexte and 'K1JT' in contexte, (
        'la source doit être citée près des bornes : %r' % contexte[-500:])
    assert 'audio harmonics cannot pass' in contexte, (
        'la phrase du guide doit être citée telle quelle, pas paraphrasée')


@pytest.mark.parametrize('ton', [1500, 1600, 1800, 2000])
def test_dans_la_plage_propre_aucun_avis(page, ton):
    """Avertir sur un réglage correct rendrait l'avertissement inaudible."""
    r = _avis(page, ton)
    assert not r['visible'], '%d Hz ne doit rien déclencher : %r' % (ton, r)


@pytest.mark.parametrize('ton', [200, 700, 1200, 1499])
def test_ton_bas_l_avis_CHIFFRE_l_harmonique(page, ton):
    """« Trop bas » n'apprend rien. On donne la fréquence exacte où le parasite
    va tomber, pour CE ton — c'est ce qui rend l'avis actionnable."""
    r = _avis(page, ton)
    assert r['visible'], '%d Hz doit avertir' % ton
    assert str(2 * ton) in r['texte'], (
        "l'avis doit chiffrer l'harmonique 2 (%d Hz) : %r" % (2 * ton, r['texte']))
    assert 'parasite' in r['texte'], r['texte']


@pytest.mark.parametrize('ton', [2001, 2500, 2800])
def test_ton_haut_l_avis_donne_l_AUTRE_raison(page, ton):
    """Au-dessus de 2000 Hz l'harmonique 2 est DÉJÀ hors filtre : le risque
    n'est plus la pollution mais l'atténuation par le bord de la passe-bande.
    Servir la même explication serait faux."""
    r = _avis(page, ton)
    assert r['visible'], '%d Hz doit avertir' % ton
    assert 'parasite' not in r['texte'], (
        'un ton haut ne produit pas le parasite décrit pour un ton bas : %r'
        % r['texte'])
    assert 'passe-bande' in r['texte'] and 'puissance' in r['texte'], r['texte']


def test_l_avis_disparait_quand_on_revient_dans_la_plage(page):
    """Un avertissement qui reste après correction fait douter de tous les
    autres."""
    assert _avis(page, 700)['visible']
    r = _avis(page, 1700)
    assert not r['visible'] and not r['texte'], r


# ═══════════════════════════════════════════════════════════════════════════
# §2. LA PORTÉE — le défaut réellement commis
# ═══════════════════════════════════════════════════════════════════════════

def test_majTonPropre_est_definie_au_NIVEAU_SUPERIEUR(src):
    """🚨 LE défaut introduit puis corrigé. Le bloc avait atterri dans le corps
    de dessinerAxe() : syntaxe parfaite, bloc <script> évalué sans erreur, et
    pourtant la fonction n'existait pas au chargement.

    On vérifie qu'elle N'EST PAS à l'intérieur d'une autre fonction, en
    comparant sa position à celle des fonctions voisines."""
    i = src.index('window.majTonPropre')
    axe = src.index('function dessinerAxe(')
    # dessinerAxe se termine avant que majTonPropre ne commence : comptage
    # d'accolades depuis sa déclaration.
    prof, k = 0, src.index('{', axe)
    while True:
        if src[k] == '{':
            prof += 1
        elif src[k] == '}':
            prof -= 1
            if prof == 0:
                break
        k += 1
    assert i > k, (
        'majTonPropre est définie DANS dessinerAxe() : elle ne sera assignée '
        "que si cette fonction tourne, et les constantes seront redéclarées à "
        'chaque tracé')


def test_le_champ_ecoute_la_saisie_ET_le_clic_sur_la_cascade(src):
    """clicWaterfall() écrit dans le champ puis émet un événement `change` :
    n'écouter que `input` laisserait l'avis sur l'ancienne valeur après un clic
    dans le waterfall — c'est-à-dire précisément le geste qui déplace le ton."""
    m = re.search(r'<input[^>]*id="ft8Tone0"[^>]*>', src, re.S)
    assert m, 'champ introuvable'
    balise = m.group(0)
    assert 'oninput="majTonPropre()"' in balise, balise
    assert 'onchange="majTonPropre()"' in balise, (
        'sans onchange, un clic sur la cascade ne rafraîchit pas l\'avis : %r'
        % balise)
    assert "dispatchEvent(new Event('change'))" in src, (
        'clicWaterfall doit continuer à émettre change')


def test_l_avis_n_est_pas_reserve_au_mode_expert(src):
    """Ce qu'on met sur l'air concerne les voisins de fréquence, pas le niveau
    de l'opérateur. Un débutant est même celui qui a le plus besoin de le
    savoir."""
    m = re.search(r'<span id="tonAvis"[^>]*>', src)
    assert m, 'zone d\'avis introuvable'
    assert 'expert-only' not in m.group(0), m.group(0)
