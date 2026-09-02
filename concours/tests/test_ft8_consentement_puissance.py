# -*- coding: utf-8 -*-
"""Sécurité FT8 : consentement puissance à la 1ʳᵉ émission + alerte si aucune
limite configurée.

LE DÉFAUT (remonté par F4GLD) : sa TOUTE PREMIÈRE émission FT8 est partie à
100 W sans la moindre alerte. Cause : appliquerProtectionPuissance() restait
MUET (`_avisPuissance('')`) quand aucune limite de puissance n'était configurée
dans CONFIG — la radio partait donc à sa puissance phonie (100 W) en porteuse
continue (FT8 = 100 % du cycle de service). « Ce ne doit pas être possible. »

CE QUI EST TENU ICI :
  - branche « aucune limite » : ALERTE rouge au lieu du silence ;
  - onArmChange : la 1ʳᵉ émission est BLOQUÉE tant que le consentement n'est pas
    donné (refus -> on désarme, on sort avant d'émettre) ;
  - le consentement est mémorisé (une seule fois par installation) ;
  - le texte du consentement nomme le risque (pleine puissance / final / ampli).

Assertions STRUCTURELLES sur le vrai source (le corps réel d'onArmChange et
d'appliquerProtectionPuissance, pas leur présence ailleurs) + test COMPORTEMENTAL
des helpers de consentement extraits verbatim et exécutés dans un moteur JS réel.
"""
import os
import re

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGE_FT8 = os.path.join(CONCOURS, 'logx_ft8.html')


def _lire(chemin):
    with open(chemin, encoding='utf-8') as f:
        return f.read()


def _sans_commentaires(src):
    src = re.sub(r'<!--.*?-->', '', src, flags=re.S)
    src = re.sub(r'/\*.*?\*/', '', src, flags=re.S)
    return '\n'.join(re.sub(r'//.*$', '', li) for li in src.splitlines())


# ─── Structure : la branche sans limite ALERTE au lieu de se taire ───────────

def test_sans_limite_configuree_le_code_alerte_au_lieu_de_se_taire():
    code = _sans_commentaires(_lire(PAGE_FT8))
    i = code.index('function appliquerProtectionPuissance()')
    corps = code[i:code.index('\n  }', i)]
    j = corps.index('if(!voulue)')
    branche = corps[j:corps.index('return', j)]
    assert "_avisPuissance('')" not in branche, (
        "la branche « aucune limite » ne doit plus être muette :\n" + branche)
    assert "'err'" in branche, ("l'alerte doit être en style err (rouge) :\n" + branche)
    assert 'puissance' in branche.lower(), branche


# ─── Structure : onArmChange bloque la 1ʳᵉ émission sans consentement ─────────

def test_onArmChange_bloque_sans_consentement_avant_d_emettre():
    code = _sans_commentaires(_lire(PAGE_FT8))
    i = code.index('window.onArmChange = function()')
    corps = code[i:code.index('};', i)]
    assert '_ft8PuissanceConsentie' in corps and '_demanderConsentementPuissance' in corps, corps
    i_consent = corps.index('_demanderConsentementPuissance')
    i_apply = corps.index('appliquerProtectionPuissance()')
    assert i_consent < i_apply, (
        'le consentement doit être demandé AVANT la protection/l\'émission')
    # un refus doit désarmer la case ET sortir avant d'appliquer la protection
    avant_apply = corps[i_consent:i_apply]
    assert 'box.checked = false' in avant_apply and 'return' in avant_apply, (
        'un refus doit désarmer et sortir avant d\'émettre :\n' + corps)


def test_le_consentement_explique_le_risque_puissance():
    code = _sans_commentaires(_lire(PAGE_FT8))
    i = code.index('function _demanderConsentementPuissance()')
    corps = code[i:code.index('\n  }', i)]
    bas = corps.lower()
    assert '100' in corps, 'le texte doit chiffrer le risque (100 % / 100 W)'
    assert 'final' in bas or 'ampli' in bas, 'le risque matériel doit être nommé'
    assert 'config' in bas, 'le message doit orienter vers le réglage de puissance'


# ─── Comportement : les helpers de consentement, extraits VERBATIM et exécutés ─

py_mini_racer = pytest.importorskip(
    'py_mini_racer', reason='py_mini_racer absent — test JS réel ignoré')


def _extraire_helpers():
    """Bloc réel : de `const _CLE_CONSENT_PUISSANCE` à juste avant
    `function appliquerProtectionPuissance`. On teste le VRAI code, pas une copie."""
    src = _lire(PAGE_FT8)
    deb = src.index('const _CLE_CONSENT_PUISSANCE')
    fin = src.index('function appliquerProtectionPuissance()', deb)
    return src[deb:fin]


def _ctx(confirm_val=None, deja_consenti=False):
    ctx = py_mini_racer.MiniRacer()
    ctx.eval("""
    var __store = {};
    var localStorage = {
      getItem: function(k){ return (k in __store) ? __store[k] : null; },
      setItem: function(k,v){ __store[k] = String(v); }
    };
    var __confirmVal = null; var __confirmAppels = 0;
    function puissanceVoulueW(){ return 0; }
    """)
    if deja_consenti:
        ctx.eval("__store['logx_ft8_puissance_consentie'] = '1';")
    if confirm_val is not None:
        ctx.eval('var confirm = function(){ __confirmAppels++; return %s; };'
                 % ('true' if confirm_val else 'false'))
    ctx.eval(_extraire_helpers())
    return ctx


def test_consentement_bloque_puis_memorise():
    # refus -> false, et rien n'est mémorisé (on pourra re-demander)
    ctx = _ctx(confirm_val=False)
    assert ctx.eval('_ft8PuissanceConsentie()') is False
    assert ctx.eval('_demanderConsentementPuissance()') is False
    # acceptation -> true, puis on mémorise -> plus jamais demandé
    ctx = _ctx(confirm_val=True)
    assert ctx.eval('_demanderConsentementPuissance()') is True
    ctx.eval('_marquerPuissanceConsentie();')
    assert ctx.eval('_ft8PuissanceConsentie()') is True


def test_consentement_deja_donne_reste_vrai():
    ctx = _ctx(confirm_val=False, deja_consenti=True)
    assert ctx.eval('_ft8PuissanceConsentie()') is True   # drapeau lu depuis localStorage


def test_hors_navigateur_ne_bloque_pas():
    """Sans confirm (banc/headless), pas de radio à protéger : ne pas bloquer."""
    ctx = _ctx(confirm_val=None)                          # confirm indéfini
    assert ctx.eval('_demanderConsentementPuissance()') is True
