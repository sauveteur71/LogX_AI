# -*- coding: utf-8 -*-
"""Keyer vocal (DVK) : les messages partent par la RADIO, pas par les enceintes.

Le panneau existait déjà, mais il était inopérant pour le trafic :
`voicePlay()` faisait un simple `new Audio().play()` — sortie par défaut du
navigateur, aucun PTT — et les enregistrements dormaient en localStorage, donc
perdus dès qu'on ouvrait le log depuis un autre poste.

Or toute la plomberie existait : logx_voicekeyer sait déjà lever le PTT dans
les trois modes CAT et jouer un WAV vers le périphérique choisi en CONFIG.
C'est le chemin du callbot. Les messages enregistrés l'empruntent désormais.

En phonie, c'est ce qui rend l'ESM utilisable : un concours SSB de 24 h détruit
la voix, et le DVK est ce qui permet de tenir avec un CQ identique à la 900e
répétition.
"""
import io
import os
import struct
import sys
import wave

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CONCOURS not in sys.path:
    sys.path.insert(0, CONCOURS)

import logx_voicekeyer as vk  # noqa: E402


@pytest.fixture(autouse=True)
def dossier_isole(tmp_path, monkeypatch):
    """Chaque test écrit dans son propre dossier : jamais dans le dépôt."""
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _wav(secondes=1.0, sr=8000, canaux=1):
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as w:
        w.setnchannels(canaux)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(b''.join(struct.pack('<h', 0)
                               for _ in range(int(sr * secondes) * canaux)))
    return buf.getvalue()


# ─── Stockage côté serveur ───────────────────────────────────────────────────

def test_un_message_enregistre_est_relu_avec_sa_duree():
    assert vk.messages_disponibles() == {}
    res = vk.enregistrer_message('V1', _wav(1.5))
    assert res['ok'] and res['seconds'] == 1.5
    assert vk.messages_disponibles() == {'V1': 1.5}


def test_le_message_survit_a_un_changement_de_poste():
    """C'était le défaut : en localStorage, l'enregistrement n'existait que
    dans LE navigateur qui l'avait fait. Ici il est sur le serveur, donc vu
    par tous les postes — on le vérifie en relisant depuis le disque."""
    vk.enregistrer_message('V2', _wav(0.5))
    chemin = vk.chemin_emplacement('V2')
    assert os.path.exists(chemin)
    with wave.open(chemin, 'rb') as wf:
        assert wf.getnframes() > 0


def test_suppression():
    vk.enregistrer_message('V1', _wav())
    assert vk.supprimer_message('V1')['ok']
    assert vk.messages_disponibles() == {}
    # Supprimer un emplacement déjà vide ne doit pas être une erreur.
    assert vk.supprimer_message('V1')['ok']


# ─── Refus : la clé vient du réseau ──────────────────────────────────────────

@pytest.mark.parametrize('cle', [
    '../../evil', '../secret', 'V1/../../x', 'V9', '', 'v1', 'V1.wav',
    'C:/Windows/System32/x',
])
def test_aucune_cle_hors_liste_n_ecrit_quoi_que_ce_soit(cle, dossier_isole):
    """La clé est comparée à une liste FERMÉE, pas nettoyée : un nom construit
    à partir d'une chaîne reçue finit toujours par écrire hors du dossier."""
    assert vk.chemin_emplacement(cle) is None
    res = vk.enregistrer_message(cle, _wav())
    assert not res['ok'] and 'inconnu' in res['error'].lower()
    # Rien n'a été créé nulle part sous le dossier de travail.
    crees = [p for p in dossier_isole.rglob('*') if p.is_file()]
    assert crees == [], "des fichiers ont été écrits : %s" % crees


def test_un_message_vide_est_refuse():
    assert not vk.enregistrer_message('V1', b'')['ok']


def test_ce_qui_n_est_pas_un_wav_est_refuse_a_l_enregistrement():
    """Le refus doit tomber MAINTENANT : un fichier illisible ne se
    découvrirait sinon qu'au moment de le passer sur l'air."""
    res = vk.enregistrer_message('V1', b'ceci nest pas un fichier wav')
    assert not res['ok'] and 'illisible' in res['error'].lower()
    assert vk.messages_disponibles() == {}


def test_un_wav_invalide_n_ecrase_pas_le_message_deja_en_place():
    """Écriture par fichier temporaire puis remplacement atomique : un envoi
    corrompu ne doit pas détruire le CQ qui marchait."""
    vk.enregistrer_message('V1', _wav(2.0))
    vk.enregistrer_message('V1', b'corrompu')
    assert vk.messages_disponibles() == {'V1': 2.0}


def test_taille_maximale():
    res = vk.enregistrer_message('V1', b'x' * (vk.TAILLE_MAX + 1))
    assert not res['ok'] and 'trop long' in res['error'].lower()


def test_aucun_fichier_temporaire_ne_reste_apres_un_refus(dossier_isole):
    vk.enregistrer_message('V1', b'corrompu')
    restes = [p.name for p in dossier_isole.rglob('*.tmp')]
    assert restes == []


# ─── Émission ────────────────────────────────────────────────────────────────

def test_emission_sans_pilotage_radio_refuse_proprement():
    """Sans radio, le PTT ne peut pas être levé. La réponse doit être un refus
    explicite, jamais une exception : cet appel vient du handler HTTP."""
    vk.enregistrer_message('V1', _wav())
    res = vk.envoyer_message({'voicekeyer_enabled': '1'}, 'V1')
    assert res['ok'] is False and 'ptt' in res['error'].lower()


def test_emission_d_un_emplacement_vide():
    res = vk.envoyer_message({'voicekeyer_enabled': '1'}, 'V3')
    assert not res['ok'] and 'aucun message' in res['error'].lower()


def test_emission_si_keyer_desactive():
    vk.enregistrer_message('V1', _wav())
    res = vk.envoyer_message({}, 'V1')
    assert not res['ok'] and 'désactivé' in res['error'].lower()


def test_emission_d_un_emplacement_inconnu():
    res = vk.envoyer_message({'voicekeyer_enabled': '1'}, '../../evil')
    assert not res['ok']


def test_le_ptt_est_relache_meme_si_la_lecture_echoue(monkeypatch):
    """Le point le plus dangereux du module : une radio laissée en émission
    continue met en péril l'ampli. Le relâchement doit avoir lieu même quand
    la lecture audio lève."""
    vk.enregistrer_message('V1', _wav())
    etats = []

    def faux_ptt(cfg, on):
        etats.append(on)
        return {'ok': True}

    def lecture_qui_echoue(path, device=None):
        raise RuntimeError('périphérique audio absent')

    monkeypatch.setattr(vk, '_set_ptt', faux_ptt)
    monkeypatch.setattr(vk, 'play_wav', lecture_qui_echoue)

    res = vk.envoyer_message({'voicekeyer_enabled': '1'}, 'V1')
    assert not res['ok']
    assert etats == [True, False], "le PTT doit être levé puis RELÂCHÉ"


def test_echec_de_relachement_du_ptt_signale_fort(monkeypatch):
    """Si le PTT ne retombe pas, ça ne doit pas passer pour un succès."""
    vk.enregistrer_message('V1', _wav())
    monkeypatch.setattr(vk, '_set_ptt',
                        lambda cfg, on: {'ok': True} if on else {'ok': False, 'error': 'bloqué'})
    monkeypatch.setattr(vk, 'play_wav', lambda path, device=None: None)

    res = vk.envoyer_message({'voicekeyer_enabled': '1'}, 'V1')
    assert res['ok'] is False
    assert res.get('ptt_release_failed') is True
    assert 'émission' in res['error']


def test_le_message_enregistre_n_est_pas_supprime_apres_emission(monkeypatch):
    """Contrairement au WAV de synthèse (temporaire), le message de
    l'opérateur doit rester : il sert 900 fois dans le week-end."""
    vk.enregistrer_message('V1', _wav())
    monkeypatch.setattr(vk, '_set_ptt', lambda cfg, on: {'ok': True})
    monkeypatch.setattr(vk, 'play_wav', lambda path, device=None: None)

    assert vk.envoyer_message({'voicekeyer_enabled': '1'}, 'V1')['ok']
    assert vk.messages_disponibles() == {'V1': 1.0}


def test_le_peripherique_de_config_est_celui_utilise(monkeypatch):
    """Le message doit sortir par le câble vers la radio, pas par la sortie
    par défaut — c'est exactement ce que `new Audio().play()` ne savait pas
    faire."""
    vk.enregistrer_message('V1', _wav())
    vus = {}
    monkeypatch.setattr(vk, '_set_ptt', lambda cfg, on: {'ok': True})
    monkeypatch.setattr(vk, 'play_wav',
                        lambda path, device=None: vus.update(device=device, path=path))

    vk.envoyer_message({'voicekeyer_enabled': '1', 'voicekeyer_device': '7'}, 'V1')
    assert vus['device'] == '7'
    assert vus['path'].endswith('V1.wav')
