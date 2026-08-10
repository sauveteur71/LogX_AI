# -*- coding: utf-8 -*-
"""Prefetch au démarrage des bases POTA/SOTA/WWFF/IOTA/WCA (analyse
concurrentielle 10/08/2026, recommandation P2 : Wavelog peuple ces mêmes
référentiels dès sa migration de mise à jour, "out of the box").

Sans ce prefetch, ActivationDatabase.ensure_loading_started() (cf.
logx_activation_db.py) n'était déclenché qu'au tout premier appel de
/activation_db/search -- c'est-à-dire la toute première fois qu'un opérateur
tape dans le champ "MA RÉFÉRENCE ACTIVÉE". Sur un poste neuf (pas de cache
disque), ce champ restait donc sans autocomplétion pendant tout le temps du
téléchargement (jusqu'à 60s de timeout).

Le bloc ajouté vit dans `if __name__ == '__main__':` (logx_serveur.py) --
comme le reste du câblage de démarrage de ce fichier (autostart, TLE, LoTW,
WebSDR...), il n'est ni importable ni exécutable directement par pytest, et
suit donc le même patron déjà établi dans ce dépôt pour ce genre de câblage :
un test STRUCTUREL sur le texte source (voir aussi
tests/test_hardware_cat_script_order.py pour le même principe côté JS),
plutôt qu'une exécution réelle du serveur. Le comportement RUNTIME de
ensure_loading_started() lui-même est déjà couvert par
tests/test_iota.py et tests/test_wca.py."""
import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SERVEUR_PATH = os.path.join(BASE, 'logx_serveur.py')

with open(SERVEUR_PATH, encoding='utf-8') as _f:
    _SRC = _f.read()


def test_les_5_bases_activation_sont_prechargees_au_demarrage():
    attendus = {
        'SOTA': 'sota.ensure_loading_started()',
        'POTA': 'pota.parks_db.ensure_loading_started()',
        'WWFF': 'wwff.directory_db.ensure_loading_started()',
        'IOTA': 'iota.groups_db.ensure_loading_started()',
        'WCA':  'wca.ensure_loading_started()',
    }
    manquants = [nom for nom, appel in attendus.items() if appel not in _SRC]
    assert not manquants, (
        f"le démarrage du serveur ne précharge plus les bases : {manquants} -- "
        "sans ce prefetch, l'autocomplétion de MA RÉFÉRENCE ACTIVÉE reste vide "
        "pendant tout le téléchargement au tout premier essai de l'opérateur")


def test_le_prefetch_est_reellement_appele_pas_seulement_defini():
    """Un `def _maj_activation_db(): ...` jamais appelé serait aussi invisible
    qu'une absence totale -- vérifie l'appel, pas juste la définition."""
    deb = _SRC.index('def _maj_activation_db()')
    fin = _SRC.index('\n\n', deb)
    corps_et_suite = _SRC[deb:fin + 40]
    assert '_maj_activation_db()' in corps_et_suite.split('\n', 1)[1], \
        "_maj_activation_db() est définie mais jamais appelée au démarrage"


def test_le_prefetch_tolere_lechec_dun_programme_sans_bloquer_les_autres():
    """Chacun des 5 imports/appels doit être dans son propre try/except --
    si logx_wca (par ex.) lève à l'import, SOTA/POTA/WWFF/IOTA doivent quand
    même démarrer (même philosophie que _maj_tle/_maj_lotw/_maj_websdr
    juste au-dessus dans ce fichier : jamais bloquant, jamais tout-ou-rien)."""
    deb = _SRC.index('def _maj_activation_db()')
    apres_def = deb + len('def _maj_activation_db()')
    fin = _SRC.index('_maj_activation_db()', apres_def) + len('_maj_activation_db()')
    corps = _SRC[deb:fin]
    assert corps.count('try:') == 5, (
        "chaque base doit avoir son propre try/except -- un seul bloc "
        "englobant ferait échouer tout le prefetch si UN SEUL programme "
        "a un souci d'import")
