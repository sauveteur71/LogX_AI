# -*- coding: utf-8 -*-
"""Localisation des textes déterministes du coach : logx_coach_i18n.t().

Fonction PURE (aucun réseau, aucun état). Contrat (docstring du module) :
- langue connue + clé connue -> template de cette langue, formaté avec les params ;
- langue inconnue ou 'auto' -> français ;
- clé absente d'une langue -> repli français ; absente partout -> chaîne vide ;
- ne lève JAMAIS : un template avec un placeholder non fourni retombe sur le FR
  puis, en dernier recours, retourne le template brut.
Valeurs FR/EN/DE asserties = celles réellement présentes dans le module (source
de vérité), pas des valeurs inventées.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_coach_i18n as ci


def test_langue_connue_selectionne_la_bonne_table():
    # Sélection de langue : fr/en/de donnent bien TROIS textes distincts.
    assert ci.t('fr', 'band_open') == "ouverte à cette heure"
    assert ci.t('en', 'band_open') == 'open at this hour'
    assert ci.t('de', 'band_open') == 'zu dieser Zeit offen'


def test_substitution_de_parametres():
    assert ci.t('fr', 'mult_suffix', w=3) == " — mult ×3"
    assert ci.t('en', 'mult_suffix', w=5) == ' — mult ×5'


def test_langue_auto_ou_inconnue_retombe_sur_le_francais():
    fr = ci.t('fr', 'band_open')
    assert ci.t('auto', 'band_open') == fr
    assert ci.t('zz', 'band_open') == fr          # code de langue inexistant
    assert ci.t(None, 'band_open') == fr          # None -> FR (get renvoie None -> or _FR)


def test_cle_absente_partout_donne_chaine_vide():
    assert ci.t('fr', '__cle_inexistante_zzz__') == ''
    assert ci.t('en', '__cle_inexistante_zzz__') == ''


def test_cle_absente_dans_une_langue_retombe_sur_le_francais():
    # Cherche une vraie clé présente en FR mais absente d'au moins une autre
    # langue ; si elle existe, le repli FR doit s'appliquer. (Documente le
    # comportement de la ligne « tpl = _FR.get(key) » ; si parité totale,
    # aucune clé trouvée et le test ne fait qu'attester la parité.)
    fr_keys = set(ci._FR)
    trouve = False
    for lang, table in ci.LANG_TABLES.items():
        if lang == 'fr':
            continue
        for k in fr_keys - set(table):
            if '{' in ci._FR[k]:
                continue  # évite les templates à params pour cette assertion
            assert ci.t(lang, k) == ci._FR[k], (lang, k)
            trouve = True
            break
        if trouve:
            break
    # non-vacant : soit on a exercé un repli réel, soit la parité est totale
    # (dans ce cas l'invariant ci-dessous tient trivialement).
    assert trouve or all(set(ci._FR) <= set(t) for t in ci.LANG_TABLES.values())


def test_ne_leve_jamais_sur_placeholder_manquant():
    # mult_suffix attend {w} ; sans le fournir, la fonction ne doit PAS lever
    # et retombe sur le template brut (placeholder non substitué conservé).
    r = ci.t('fr', 'mult_suffix')          # aucun param
    assert isinstance(r, str) and '{w}' in r
    # idem pour une langue traduite
    r2 = ci.t('de', 'mult_suffix')
    assert isinstance(r2, str) and '{w}' in r2
