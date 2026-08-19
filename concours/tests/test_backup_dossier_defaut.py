# -*- coding: utf-8 -*-
"""La sauvegarde doit tourner MÊME si aucun dossier n'a été désigné.

DÉFAUT RÉEL, 19/08/2026 : F4GLD a perdu 9 871 QSO (2011-2026) et aucune
sauvegarde n'existait — `backup_folder` était vide, il l'est à l'installation,
et le logiciel ne l'a jamais réclamé. `backup_settings()` rendait alors
`enabled: False`, et le planificateur de `logx_serveur.py` (`if not
s['enabled']: continue`) ne sauvegardait jamais rien.

Ce banc tient trois propriétés distinctes :

1. le repli EXISTE et la sauvegarde est active sans aucune configuration ;
2. un dossier choisi reste prioritaire (on n'a pas remplacé un défaut par un
   autre) ;
3. 🚨 le repli ne FUITE PAS dans la configuration. C'est le piège central :
   `logx_cloudsync.cloudsync_settings()` replie son dossier sur
   `cfg['backup_folder']`, et un commentaire de `logx_cloudsync.py` documente
   que ce repli déclenche des I/O de scan **même avec `cloudsync_mode='off'`**
   (blocage mesuré à ~21 s sur un partage SMB injoignable). Écrire le défaut
   dans la config réveillerait donc une synchro que personne n'a demandée.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_backup as bk          # noqa: E402
import logx_cloudsync as cs       # noqa: E402


# ── 1. Sans aucune configuration, la sauvegarde tourne ────────────────────
def test_sans_dossier_configure_la_sauvegarde_est_active():
    s = bk.backup_settings({})
    assert s['enabled'] is True, (
        "sauvegarde inactive sans dossier configuré : c'est exactement ce qui "
        "a rendu la perte du 19/08/2026 irréversible")
    assert s['folder'], 'aucun dossier de repli résolu'
    assert s['par_defaut'] is True


def test_le_repli_est_un_sous_dossier_du_dossier_de_donnees(tmp_path,
                                                            monkeypatch):
    """Le dossier de données est le répertoire courant (run_backup y lit
    'logx.db' en relatif) : le repli doit en dépendre, pas être figé."""
    monkeypatch.chdir(tmp_path)
    attendu = os.path.join(os.path.realpath(str(tmp_path)), bk.DOSSIER_DEFAUT)
    obtenu = os.path.realpath(bk.backup_settings({})['folder'])
    assert obtenu == attendu, f'{obtenu!r} != {attendu!r}'


def test_config_vide_ou_absente_donne_le_meme_repli(tmp_path, monkeypatch):
    """None, {} et une chaîne vide sont trois façons d'avoir « rien »."""
    monkeypatch.chdir(tmp_path)
    ref = bk.backup_settings({})['folder']
    for cfg in (None, {}, {'backup_folder': ''}, {'backup_folder': '   '},
                {'backup_folder': None}):
        s = bk.backup_settings(cfg)
        assert s['folder'] == ref and s['enabled'] is True, f'cfg={cfg!r}'
        assert s['par_defaut'] is True, f'cfg={cfg!r}'


# ── 2. Un dossier choisi reste prioritaire ────────────────────────────────
def test_un_dossier_choisi_gagne_sur_le_repli(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    choisi = str(tmp_path / 'ailleurs')
    s = bk.backup_settings({'backup_folder': choisi})
    assert s['folder'] == choisi
    assert s['par_defaut'] is False, (
        'un dossier explicitement choisi est signalé comme un défaut : '
        "l'interface ne pourrait plus distinguer les deux cas")
    assert s['enabled'] is True


# ── 3. 🚨 Le repli ne doit PAS contaminer la configuration ────────────────
def test_le_repli_ne_reveille_pas_la_synchro_cloud(tmp_path, monkeypatch):
    """Propriété de comportement, pas de structure : on interroge cloudsync.

    Si le repli était écrit dans cfg['backup_folder'], cloudsync_settings()
    le reprendrait et se mettrait à scanner un dossier que l'utilisateur n'a
    jamais désigné — I/O bloquantes documentées dans logx_cloudsync.py.

    ⚠️ La configuration DOIT être non vide ici. `backup_settings` commence par
    `cfg = cfg or {}` : un dict vide est falsy, donc la fonction rebinderait
    une copie neuve et une contamination réelle deviendrait invisible. Une
    première version de ce test passait `{}` et ne rougissait PAS quand on
    injectait volontairement la fuite — banc vacant, trouvé par contre-épreuve.
    En production la config porte toujours au moins l'indicatif."""
    monkeypatch.chdir(tmp_path)
    cfg = {'callsign': 'F4GLD'}
    avant = dict(cfg)
    bk.backup_settings(cfg)
    bk.status(cfg)

    assert cfg == avant, (
        f"backup_settings/status ont modifié la configuration : {cfg!r} — "
        'le repli doit être RÉSOLU, jamais STOCKÉ')

    vue_par_cloudsync = cs.cloudsync_settings(cfg)
    assert not vue_par_cloudsync['folder'], (
        'la synchro cloud voit maintenant un dossier alors que rien n\'a été '
        f'configuré : {vue_par_cloudsync["folder"]!r}')
    assert vue_par_cloudsync['enabled'] is False


# ── 4. Comportement de bout en bout : des fichiers sont vraiment écrits ───
def test_run_backup_ecrit_reellement_sans_configuration(tmp_path, monkeypatch):
    """Le vrai test : on n'assère pas un dict, on regarde le disque."""
    monkeypatch.chdir(tmp_path)
    res = bk.run_backup({'callsign': 'F4GLD'}, shared_log=[
        {'call': 'CT1END/P', 'band': '144', 'mode': 'FT8'},
    ])

    assert res.get('ok') is True, f'sauvegarde refusée : {res!r}'
    dossier = os.path.join(str(tmp_path), bk.DOSSIER_DEFAUT)
    assert os.path.isdir(dossier), 'le dossier de repli n\'a pas été créé'
    ecrits = os.listdir(dossier)
    assert ecrits, 'dossier de repli vide : rien n\'a été sauvegardé'
    assert any(f.endswith('.json') for f in ecrits), (
        f'aucun carnet lisible écrit : {ecrits!r}')


def test_status_expose_que_le_dossier_est_un_repli(tmp_path, monkeypatch):
    """L'interface doit pouvoir continuer à recommander un dossier EXTERNE :
    ce repli protège du carnet vidé, pas de la perte du disque."""
    monkeypatch.chdir(tmp_path)
    st = bk.status({})
    assert st['enabled'] is True
    assert st['par_defaut'] is True
    assert st['folder']

    st2 = bk.status({'backup_folder': str(tmp_path / 'nas')})
    assert st2['par_defaut'] is False
