# -*- coding: utf-8 -*-
"""Garde-fou anti-destruction du carnet — le carnet ne disparaît plus en silence.

DÉFAUT RÉEL, 16-19/08/2026, station F4GLD. Un carnet de 9874 QSO importé le
16/08 s'est retrouvé réduit à 2 QSO le 19/08. Mesuré sur la base elle-même :
1558 pages LIBÉRÉES sur 1570 — les lignes ont bien été supprimées par SQLite
dans ce fichier. Ni /log/reset (rien dans qso_archive depuis le 18/07) ni
« archiver et vider » (aucun dossier créé après le 14/08), c'est-à-dire aucun
des deux seuls chemins qui laissent une copie. La cause exacte n'a PAS été
identifiée — et c'est la raison d'être de ces tests : ils ne ferment pas UN
chemin, ils ferment le GOULOT par lequel toute destruction doit passer.

DEUX MOITIÉS, ET IL FAUT LES DEUX :
 1. refuser la destruction (sinon le carnet part) ;
 2. journaliser ce qui est saisi APRÈS le refus (sinon le garde-fou devient
    lui-même le second sinistre : la persistance est gelée, l'opérateur
    continue de logger, et tout part à la coupure — la sauvegarde automatique
    ne rattrape rien, elle est DÉSACTIVÉE tant qu'aucun dossier n'est
    configuré, voir logx_backup.backup_settings).

Ces tests s'exécutent contre le VRAI module, dans un dossier temporaire, et
mesurent l'état RÉEL de la base SQLite — pas un mannequin.
"""
import json
import os
import sqlite3
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_storage as st


def _qso(i):
    return {'id': 1000 + i, 'call': f'F{i}ABC', 'band': '14', 'mode': 'CW',
            'contest': '', 'date': '20260801', 'time': '12:03',
            'operator': 'OP1', 'points': 1, 'locator': 'JO31AA'}


def _in_tmp(tmp_path, fn):
    old = os.getcwd()
    os.chdir(tmp_path)
    saved = (list(st.shared_log), st.log_version, st.load_failed,
             st.ecriture_bloquee, set(st._journal_ids))
    try:
        st.shared_log[:] = []
        st.log_version = 0
        st.load_failed = False
        st.ecriture_bloquee = None
        st._journal_ids = set()
        st._forget_disk_state()
        return fn()
    finally:
        st.shared_log[:] = saved[0]
        st.log_version, st.load_failed = saved[1], saved[2]
        st.ecriture_bloquee = saved[3]
        st._journal_ids = saved[4]
        st._forget_disk_state()
        os.chdir(old)


def _en_base():
    """Ce qu'il y a RÉELLEMENT dans la table, relu depuis le disque."""
    conn = sqlite3.connect(st.DB_FILE)
    try:
        return [r[0] for r in conn.execute('SELECT call FROM qso ORDER BY rowid_pk')]
    finally:
        conn.close()


def _remplir(n):
    st.shared_log[:] = [_qso(i) for i in range(n)]
    st.bump_log_version()
    st.save_log_to_disk()


# ═══════════════════════════════════════════════════════════════════════════
# §1. LE REFUS
# ═══════════════════════════════════════════════════════════════════════════

def test_le_carnet_ne_peut_pas_etre_remplace_par_une_poignee(tmp_path):
    """L'INCIDENT, en réduction. 200 QSO en base, la mémoire n'en a plus que
    2 : sans consentement explicite, l'écriture doit être REFUSÉE et la base
    rester intacte."""
    def run():
        _remplir(200)
        assert len(_en_base()) == 200
        st.shared_log[:] = [_qso(0), _qso(1)]
        st.bump_log_version()
        st.save_log_to_disk()
        assert len(_en_base()) == 200, (
            'le carnet a été détruit : %d lignes restantes' % len(_en_base()))
        assert st.ecriture_bloquee, "le refus doit être signalé, pas silencieux"
    _in_tmp(tmp_path, run)


def test_le_JSON_de_secours_est_intact_lui_aussi(tmp_path):
    """shared_log.json est la dernière copie LISIBLE du carnet. _ecrire_tout
    le réécrit APRÈS le DELETE : un refus placé trop tard sauverait la base et
    perdrait le JSON."""
    def run():
        _remplir(200)
        st.shared_log[:] = [_qso(0)]
        st.bump_log_version()
        st.save_log_to_disk()
        with open('shared_log.json', encoding='utf-8') as f:
            assert len(json.load(f)) == 200
    _in_tmp(tmp_path, run)


def test_une_remise_a_zero_EXPLICITE_passe_toujours(tmp_path):
    """Le garde-fou ne doit pas casser /log/reset ni « archiver et vider » :
    ce sont des destructions VOULUES, et toutes deux archivent avant."""
    def run():
        _remplir(200)
        st.shared_log[:] = []
        st.bump_log_version()
        st.save_log_to_disk(effacement_autorise=True)
        assert _en_base() == []
        assert not st.ecriture_bloquee
    _in_tmp(tmp_path, run)


@pytest.mark.parametrize('perdus', [0, 1, 3, 10, 24])
def test_aucun_faux_positif_sous_le_seuil(tmp_path, perdus):
    """Un garde-fou qui refuse tout ne serait pas un garde-fou. Supprimer
    quelques QSO — le cas courant — doit passer sans un mot. 24 est la valeur
    juste sous le seuil : la borne elle-même est testée."""
    def run():
        _remplir(200)
        st.shared_log[:] = [_qso(i) for i in range(200 - perdus)]
        st.bump_log_version()
        st.save_log_to_disk()
        assert not st.ecriture_bloquee, (
            'faux positif pour %d QSO supprimés' % perdus)
        assert len(_en_base()) == 200 - perdus
    _in_tmp(tmp_path, run)


def test_le_carnet_peut_GRANDIR_librement(tmp_path):
    """Un import ADIF de 9874 QSO ne doit évidemment rien déclencher."""
    def run():
        _remplir(10)
        st.shared_log[:] = [_qso(i) for i in range(500)]
        st.bump_log_version()
        st.save_log_to_disk()
        assert len(_en_base()) == 500
        assert not st.ecriture_bloquee
    _in_tmp(tmp_path, run)


def test_la_voie_DELTA_est_bornee_elle_aussi(tmp_path):
    """Fermer la seule réécriture complète laisserait la même destruction
    passer ligne à ligne par DELETE FROM qso WHERE id=?, simplement plus
    lentement. Le carnet est assez gros pour que _plan_ecriture choisisse le
    delta (seuil amorti = len(data)//200)."""
    def run():
        _remplir(9000)
        st.shared_log[:] = [_qso(i) for i in range(9000 - 40)]
        st.bump_log_version()
        st.save_log_to_disk()
        assert len(_en_base()) == 9000, (
            'la voie delta a laissé passer la saignée : %d' % len(_en_base()))
        assert st.ecriture_bloquee
        assert 'delta' in st.ecriture_bloquee['ou']
    _in_tmp(tmp_path, run)


# ═══════════════════════════════════════════════════════════════════════════
# §2. LE REFUS NE DOIT PAS SE RETOURNER CONTRE SON BUT
# ═══════════════════════════════════════════════════════════════════════════

def test_le_refus_n_oublie_PAS_l_etat_du_disque(tmp_path):
    """Piège central : le `except Exception` de save_log_to_disk appelle
    _forget_disk_state(), qui remet _disk_version à None — or c'est ce None qui
    fait rechoisir la réécriture complète. Signaler le refus par une exception
    générique réarmerait donc exactement ce qu'on vient de refuser."""
    def run():
        _remplir(200)
        avant = st._disk_version
        assert avant is not None
        st.shared_log[:] = [_qso(0)]
        st.bump_log_version()
        st.save_log_to_disk()
        assert st._disk_version == avant, (
            "le miroir a été oublié : la sauvegarde suivante repasserait par "
            'la branche destructive')
        assert st._disk_ids, 'les ids du disque ont été perdus'
    _in_tmp(tmp_path, run)


def test_la_memoire_n_est_PAS_touchee_par_le_refus(tmp_path):
    """On ne « répare » surtout pas shared_log en le rechargeant : les QSO
    saisis depuis la divergence n'existent QUE là. Ce serait une seconde perte
    par-dessus la première."""
    def run():
        _remplir(200)
        st.shared_log[:] = [_qso(777)]
        st.bump_log_version()
        st.save_log_to_disk()
        assert [q['call'] for q in st.shared_log] == ['F777ABC']
    _in_tmp(tmp_path, run)


def test_le_refus_est_COLLANT(tmp_path, monkeypatch):
    """Un refus recalculé à chaque QSO se rejoue des centaines de fois ; il
    suffit qu'une évaluation passe pour que la destruction ait lieu.

    On COMPTE les ouvertures de la base : après le refus, plus une seule.
    Comparer l'état affiché ne suffisait pas — il reste identique même quand
    le garde-fou se rejoue, donc le test restait vert sous mutation. Trouvé
    par contre-épreuve."""
    def run():
        _remplir(200)
        st.shared_log[:] = [_qso(0)]
        st.bump_log_version()
        st.save_log_to_disk()            # refus
        assert st.ecriture_bloquee

        ouvertures = []
        vrai_db = st._db
        monkeypatch.setattr(st, '_db',
                            lambda: (ouvertures.append(1), vrai_db())[1])
        for i in range(5):
            st.shared_log.append(_qso(900 + i))
            st.bump_log_version()
            st.save_log_to_disk()
        monkeypatch.undo()
        assert ouvertures == [], (
            'la base a été rouverte %d fois après le refus : le garde-fou se '
            'rejoue, et il suffit qu\'une évaluation passe' % len(ouvertures))
        assert len(_en_base()) == 200
    _in_tmp(tmp_path, run)


# ═══════════════════════════════════════════════════════════════════════════
# §3. LE JOURNAL D'APPOINT — la moitié sans laquelle le gel serait un sinistre
# ═══════════════════════════════════════════════════════════════════════════

def test_ce_qui_est_loggue_APRES_le_refus_n_est_pas_perdu(tmp_path):
    """LA propriété qui rend le gel acceptable. Après le refus la persistance
    normale est suspendue — mais l'opérateur, lui, continue de trafiquer."""
    def run():
        _remplir(200)
        st.shared_log[:] = [_qso(0)]
        st.bump_log_version()
        st.save_log_to_disk()            # refus
        st.shared_log.append(_qso(801))  # QSO fait APRÈS le refus
        st.bump_log_version()
        st.save_log_to_disk()
        assert os.path.exists(st.FICHIER_JOURNAL), (
            "rien n'a été mis de côté : tout serait perdu à la coupure")
        with open(st.FICHIER_JOURNAL, encoding='utf-8') as f:
            consignes = [json.loads(l) for l in f if l.strip()]
        assert 'F801ABC' in [q['call'] for q in consignes]
    _in_tmp(tmp_path, run)


def _lignes_journal():
    with open(st.FICHIER_JOURNAL, encoding='utf-8') as f:
        return [json.loads(l)['call'] for l in f if l.strip()]


def test_le_journal_est_APPEND_ONLY(tmp_path):
    """Une réécriture pourrait être tronquée par la panne même qu'elle
    documente. Et un QSO déjà consigné ne doit pas l'être deux fois.

    On lit le CONTENU, pas la taille du fichier : comparer des tailles restait
    vert quand on remplaçait le mode 'a' par 'w', parce que la ligne réécrite
    se trouvait être un peu plus longue que la précédente. Trouvé par
    contre-épreuve — « exiger une structure, pas une coïncidence »."""
    def run():
        _remplir(200)
        st.shared_log[:] = [_qso(0)]
        st.bump_log_version()
        st.save_log_to_disk()
        assert _lignes_journal() == ['F0ABC']

        st.save_log_to_disk()            # rien de neuf
        assert _lignes_journal() == ['F0ABC'], (
            'un QSO déjà consigné a été réécrit une seconde fois')

        st.shared_log.append(_qso(802))
        st.bump_log_version()
        st.save_log_to_disk()
        # LA propriété : la ligne ANCIENNE doit avoir survécu à l'ajout.
        assert _lignes_journal() == ['F0ABC', 'F802ABC'], (
            'le journal a été réécrit au lieu d\'être complété : %r'
            % _lignes_journal())
    _in_tmp(tmp_path, run)


def test_le_journal_est_POUSSE_SUR_LE_SUPPORT(tmp_path):
    """Un carnet « sauvé » dans un tampon système ne survit pas à une coupure
    secteur — qui est exactement le cas d'usage de ce journal. Aucun test de
    comportement ne peut observer un fsync : la propriété se tient donc par
    une assertion sur le code lui-même, commentaires retirés."""
    import inspect
    import re
    src = inspect.getsource(st._journaliser)
    src = '\n'.join(l for l in src.split('\n')
                    if not l.strip().startswith('#'))
    assert re.search(r'os\.fsync\(\s*f\.fileno\(\)\s*\)', src), (
        "_journaliser doit forcer l'écriture sur le support : %r" % src)
    assert 'f.flush()' in src, (
        'fsync sans flush préalable ne pousse pas le tampon Python : %r' % src)


def test_le_redemarrage_REPREND_les_QSO_du_journal(tmp_path):
    """La boucle complète : refus, trafic, coupure, redémarrage. Rien ne doit
    manquer — ni les 200 de la base, ni celui saisi pendant le gel."""
    def run():
        _remplir(200)
        st.shared_log[:] = [_qso(0)]
        st.bump_log_version()
        st.save_log_to_disk()
        st.shared_log.append(_qso(803))
        st.bump_log_version()
        st.save_log_to_disk()
        # Coupure, puis redémarrage : mémoire vide, drapeaux remis à zéro.
        st.shared_log[:] = []
        st.ecriture_bloquee = None
        st._journal_ids = set()
        st.load_log_from_disk()
        calls = [q['call'] for q in st.shared_log]
        assert len(calls) == 201, 'carnet rechargé : %d QSO' % len(calls)
        assert 'F803ABC' in calls, 'le QSO du gel a été perdu au redémarrage'
        assert 'F0ABC' in calls and 'F199ABC' in calls
    _in_tmp(tmp_path, run)


def test_le_journal_est_repris_MEME_SANS_BASE(tmp_path):
    """Le cas où le journal compte le PLUS : plus de base du tout. S'il ne
    reste que lui sur le disque, il est la seule copie survivante.

    Première version du correctif : le rejeu n'était branché que sur la
    branche « base présente » de load_log_from_disk(). Il était donc inerte
    exactement quand il servait, et le fichier restait sur le disque pour être
    rejoué à un moment arbitraire plus tard. Trouvé en suite complète, pas en
    lecture — le journal orphelin polluait les tests suivants."""
    def run():
        # Un journal, et RIEN d'autre : ni logx.db, ni shared_log.json.
        with open(st.FICHIER_JOURNAL, 'w', encoding='utf-8') as f:
            for i in (11, 12):
                f.write(json.dumps(_qso(i)) + '\n')
        assert not os.path.exists(st.DB_FILE)
        st.load_log_from_disk()
        assert [q['call'] for q in st.shared_log] == ['F11ABC', 'F12ABC'], (
            'le journal orphelin a été ignoré : %r'
            % [q.get('call') for q in st.shared_log])
        # ET il doit avoir été PERSISTÉ : rester en mémoire ne suffit pas.
        assert sorted(_en_base()) == ['F11ABC', 'F12ABC'], (
            "les QSO repris n'ont pas atteint la base : %r" % _en_base())
        assert not os.path.exists(st.FICHIER_JOURNAL), (
            'le journal doit être mis de côté après reprise'
        )
    _in_tmp(tmp_path, run)


def test_le_journal_est_MIS_DE_COTE_pas_supprime(tmp_path):
    """Si le rejeu se passait mal, le fichier doit rester lisible sur le
    disque, avec son horodatage."""
    def run():
        _remplir(200)
        st.shared_log[:] = [_qso(0)]
        st.bump_log_version()
        st.save_log_to_disk()
        st.shared_log[:] = []
        st.ecriture_bloquee = None
        st._journal_ids = set()
        st.load_log_from_disk()
        assert not os.path.exists(st.FICHIER_JOURNAL), (
            'le journal doit être renommé après rejeu, sinon il se rejoue '
            'à chaque démarrage')
        archives = [f for f in os.listdir('.')
                    if f.startswith('logx_journal_secours.') and f.endswith('.jsonl')]
        assert archives, 'le journal a été supprimé au lieu d\'être mis de côté'
    _in_tmp(tmp_path, run)


def test_un_chargement_en_echec_journalise_AUSSI(tmp_path):
    """load_failed existait avant ce lot et perdait déjà, en silence, tout ce
    qui était saisi après lui : il ne fait qu'un print() vers une console que
    personne ne regarde. Il doit profiter du même filet."""
    def run():
        _remplir(200)
        st.load_failed = True
        st.shared_log.append(_qso(804))
        st.bump_log_version()
        st.save_log_to_disk()
        assert os.path.exists(st.FICHIER_JOURNAL)
        with open(st.FICHIER_JOURNAL, encoding='utf-8') as f:
            calls = [json.loads(l)['call'] for l in f if l.strip()]
        assert 'F804ABC' in calls
        assert len(_en_base()) == 200, 'la base ne devait pas être touchée'
    _in_tmp(tmp_path, run)


# ═══════════════════════════════════════════════════════════════════════════
# §4. L'OPÉRATEUR DOIT L'APPRENDRE
# ═══════════════════════════════════════════════════════════════════════════

def test_l_etat_est_lisible_par_le_client(tmp_path):
    """load_failed n'a JAMAIS été visible ailleurs que sur une console : c'est
    ce qui laissait l'opérateur logger dans le vide pendant des heures."""
    def run():
        assert st.etat_persistance() == {'ok': True}
        _remplir(200)
        st.shared_log[:] = [_qso(0)]
        st.bump_log_version()
        st.save_log_to_disk()
        etat = st.etat_persistance()
        assert etat['ok'] is False
        assert etat['sur_disque'] == 200 and etat['en_memoire'] == 1
        # Le message doit dire QUOI FAIRE, pas seulement ce qui s'est passé.
        assert 'redémarre' in etat['message'].lower()
        assert 'rien' in etat['message'].lower()
    _in_tmp(tmp_path, run)


def test_un_chargement_en_echec_est_lisible_lui_aussi(tmp_path):
    def run():
        st.load_failed = True
        etat = st.etat_persistance()
        assert etat['ok'] is False and etat['raison'] == 'chargement'
        assert 'redémarre' in etat['message'].lower()
    _in_tmp(tmp_path, run)
