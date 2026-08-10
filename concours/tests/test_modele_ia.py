# -*- coding: utf-8 -*-
"""Quel modèle part réellement au fournisseur — et qui a le droit d'en décider.

LE BUG QUE CES TESTS EMPÊCHENT DE REVENIR (trouvé le 01/08/2026 en inventoriant
les fonctions d'IA) : la carte IA envoyait `model:'claude-sonnet-4-6'` codé en
dur dans son corps de requête. Côté serveur, `call_llm` faisait
`ai_model = model or cfg.ai_model` — le codé en dur gagnait donc TOUJOURS.

Deux conséquences, l'une silencieuse et l'autre franche :
  - un opérateur ayant choisi Opus ou Haiku dans CONFIG n'obtenait jamais son
    choix, sans le moindre message ;
  - un opérateur ayant choisi OpenAI, Mistral, xAI, DeepSeek ou Gemini voyait ce
    nom Anthropic partir TEL QUEL à leur API — échec garanti à chaque message.

Le symptôme était déroutant : la veille automatique passe par /proxy/ai, qui
ignorait déjà ce champ hors Anthropic. La surveillance de fond fonctionnait donc
pendant que le chat échouait, ce qui envoie chercher le défaut au mauvais
endroit.

LA RÈGLE POSÉE : le modèle appartient à la CONFIGURATION. Une page du navigateur
n'a pas à en décider — elle ignore quel fournisseur est réglé. Un appelant
SERVEUR garde le droit de viser un palier (Haiku pour une tâche courte), mais
seulement dans la famille du fournisseur configuré.
"""
import os
import sys

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CONCOURS not in sys.path:
    sys.path.insert(0, CONCOURS)

from logx_utils import (MODELE_DEFAUT, OPENAI_COMPATIBLE_ENDPOINTS,   # noqa: E402
                        modele_effectif)


# ─── La règle elle-même ─────────────────────────────────────────────────────

@pytest.mark.parametrize('provider, configure', [
    ('openai',   'gpt-4o'),
    ('gemini',   'gemini-2.5-pro'),
    ('mistral',  'mistral-large-latest'),
    ('xai',      'grok-4.5'),
    ('deepseek', 'deepseek-v4-pro'),
])
def test_un_nom_anthropic_ne_part_JAMAIS_a_un_autre_fournisseur(provider,
                                                                configure):
    """LE bug. Sans cette garde, « claude-sonnet-4-6 » arrivait dans le corps
    de requête d'OpenAI ou dans l'URL de Gemini."""
    assert modele_effectif(provider, 'claude-sonnet-4-6', configure) == configure


def test_un_palier_de_la_BONNE_famille_reste_honore():
    """Un appelant serveur doit pouvoir demander Haiku pour une tâche courte
    alors que la config est sur Opus — c'est légitime et sans risque."""
    assert modele_effectif('anthropic', 'claude-haiku-4-5-20251001',
                           'claude-opus-4-8') == 'claude-haiku-4-5-20251001'


def test_sans_demande_la_config_gagne():
    assert modele_effectif('anthropic', None, 'claude-opus-4-8') == 'claude-opus-4-8'
    assert modele_effectif('openai', '', 'gpt-4o-mini') == 'gpt-4o-mini'


def test_sans_rien_le_defaut_du_FOURNISSEUR_s_applique():
    """Pas celui d'Anthropic : un poste réglé sur Mistral et sans modèle choisi
    doit partir avec un modèle Mistral."""
    for provider, defaut in MODELE_DEFAUT.items():
        assert modele_effectif(provider, None, None) == defaut, provider


def test_les_defauts_suivent_la_table_des_endpoints():
    """Deux tables décrivent les mêmes fournisseurs : si elles divergent, un
    poste part avec un modèle que son endpoint ne connaît pas."""
    for provider, (_url, defaut) in OPENAI_COMPATIBLE_ENDPOINTS.items():
        assert MODELE_DEFAUT[provider] == defaut, provider


def test_un_fournisseur_hors_table_ne_se_fait_pas_imposer_un_defaut():
    """On ne sait rien de lui : lui coller un modèle Anthropic serait aussi
    arbitraire que le bug qu'on corrige."""
    assert modele_effectif('un_futur_fournisseur', 'son-modele-3',
                           'autre') == 'son-modele-3'


# ─── Le contrat côté pages : plus aucun modèle codé en dur ──────────────────

def _lire(nom):
    with open(os.path.join(CONCOURS, nom), encoding='utf-8') as f:
        return f.read()


@pytest.mark.parametrize('page', ['logx_carte.html', 'logx_configuration.html',
                                  'logx_logbook.js'])
def test_aucune_page_n_impose_un_modele_dans_son_corps_de_requete(page):
    """C'est la SOURCE du bug : une page qui envoie un nom de modèle. Le
    sélecteur de la page CONFIG (liste AI_MODELS) est autre chose — il PROPOSE
    des noms à l'opérateur, il n'en impose aucun dans une requête."""
    src = _lire(page)
    for motif in ("model:'claude", 'model:"claude', "model: 'claude",
                  "model:'gpt", "model:'gemini", "model:'mistral",
                  "model:'grok", "model:'deepseek"):
        assert motif not in src, (
            '%s impose un modèle dans une requête (%r) — c\'est le bug qui '
            'faisait échouer le chat chez tout fournisseur non-Anthropic'
            % (page, motif))


def _corps_veille():
    """Le corps de autoCheckSilently(), et lui seul. Chercher dans la page
    entière donne des faux positifs : la DÉFINITION de playAlertSound apparaît
    bien avant son appel, et un commentaire qui cite le bug corrigé ressemble
    au bug lui-même."""
    src = _lire('logx_carte.html')
    d = src.index('async function autoCheckSilently()')
    f = src.index('function scheduleAutoCheck()', d)
    return src[d:f]


def test_la_cadence_de_veille_est_dite_UNE_fois():
    """Le minuteur disait 10 min et le prompt annonçait « toutes les 5
    minutes » au modèle : il raisonnait sur une fréquence de veille fausse."""
    src = _lire('logx_carte.html')
    assert 'const AUTO_CHECK_MIN' in src
    assert 'AUTO_CHECK_MIN * 60 * 1000' in src, 'le minuteur doit lire la constante'
    corps = _corps_veille()
    assert '${AUTO_CHECK_MIN} minutes' in corps, 'le prompt doit lire la constante'
    # Aucune cadence en toutes lettres dans le prompt envoyé au modèle.
    for menteuse in ('toutes les 5 minutes', 'toutes les 10 minutes'):
        assert menteuse not in corps, menteuse


def test_une_alerte_sans_indicatif_ne_sonne_pas():
    """La convention « réponds RAS » n'est qu'un accord de texte : un modèle
    qui préface poliment ne la respecte pas et faisait sonner l'alerte pour
    rien. Une veille qui sonne à tort est une veille qu'on coupe."""
    corps = _corps_veille()
    i_calls = corps.find('const calls = extractCallsigns(reply)')
    i_garde = corps.find('if(!calls.length) return;')
    i_son = corps.find('playAlertSound()')
    assert i_calls != -1, "l'extraction d'indicatifs a disparu"
    assert i_garde != -1, 'la garde « pas d\'indicatif, pas d\'alerte » a disparu'
    assert i_son != -1, "l'appel du son d'alerte a disparu"
    assert i_calls < i_garde < i_son, (
        'la garde doit être posée entre l\'extraction et le son')
