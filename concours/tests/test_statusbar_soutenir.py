# -*- coding: utf-8 -*-
"""Lien « soutenir » de la barre de statut (logx_statusbar.js) : don libre au
Radio-Club du Velay (F6KQJ) via HelloAsso, demandé par F4GLD le 21/08/2026 en
même temps que le widget de don du site vitrine (gh-pages). Même emplacement
partagé que GUIDE/signaler un problème -- une seule modification vue sur les
15 pages de l'application.

Test textuel/structurel (lecture du fichier en Python, sans DOM ni
py_mini_racer), dans l'esprit de tests/test_ux_mode_debutant_partout.py."""
import os

CONCOURS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATUSBAR_JS = os.path.join(CONCOURS_DIR, 'logx_statusbar.js')
I18N_JS = os.path.join(CONCOURS_DIR, 'logx_i18n.js')

HELLOASSO_URL = 'https://www.helloasso.com/associations/radioclub-du-velay/formulaires/2'


def _lire(path):
    with open(path, encoding='utf-8') as f:
        return f.read()


def test_lien_soutenir_present_et_bien_positionne():
    """Placé APRÈS #rcsbReportItem (dernier item actionnable existant de la
    barre) -- ne perturbe pas l'ordre #rcsbVersion < #rcsbUiModeItem <
    #rcsbReportItem déjà couvert par tests/test_ux_mode_debutant_partout.py."""
    src = _lire(STATUSBAR_JS)
    assert 'id="rcsbDonateItem"' in src
    i_report = src.index('id="rcsbReportItem"')
    i_donate = src.index('id="rcsbDonateItem"')
    assert i_report < i_donate, (
        "#rcsbDonateItem doit venir après #rcsbReportItem, pas avant ni au milieu")


def test_lien_soutenir_pointe_vers_la_bonne_page_helloasso():
    src = _lire(STATUSBAR_JS)
    i = src.index('id="rcsbDonateItem"')
    bloc = src[i:i + 400]
    assert f'href="{HELLOASSO_URL}"' in bloc, bloc
    assert 'target="_blank"' in bloc and 'rel="noopener' in bloc, (
        "un lien externe de la barre de statut doit s'ouvrir dans un nouvel "
        "onglet sans exposer window.opener, même convention que #rcsbGuideLink")


def test_lien_soutenir_traduit_juste_apres_signaler_un_probleme_dans_les_7_langues():
    """logx_i18n.js duplique le dictionnaire T par section de page -- « signaler
    un problème » et « GUIDE » y apparaissent donc à PLUSIEURS endroits du
    fichier, un seul étant celui du bloc de la barre de statut. La clé
    "soutenir" doit suivre IMMÉDIATEMENT l'occurrence de « signaler un
    problème » ajoutée avec elle (même geste d'édition), pas n'importe
    laquelle des occurrences du mot ailleurs dans le fichier."""
    src = _lire(I18N_JS)
    attendus = {
        'en': 'report a problem', 'de': 'Problem melden', 'es': 'informar de un problema',
        'it': 'segnala un problema', 'pt': 'comunicar um problema',
        'nl': 'een probleem melden', 'pl': 'zgłoś problem',
    }
    for lang, trad in attendus.items():
        marker = f'"signaler un problème": "{trad}",'
        assert marker in src, f'{lang} : marqueur "signaler un problème" introuvable'
        i = src.index(marker) + len(marker)
        suite = src[i:i + 200]
        assert '"soutenir":' in suite, (
            f'{lang} : "soutenir" ne suit pas immédiatement "signaler un problème"')
