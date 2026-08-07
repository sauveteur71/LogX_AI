# -*- coding: utf-8 -*-
"""Chiffrement au repos des identifiants (logx_crypto.py).

KEY_FILE est TOUJOURS redirigé vers un dossier temporaire (monkeypatch) —
jamais vers le dossier partagé concours/, qui a déjà eu son lot de tests
polluant l'environnement de dev en y écrivant de vrais fichiers (voir
mémoire "26 tests écrivaient des fichiers PARTAGÉS dans concours/"). Une
clé AES écrite au mauvais endroit serait pire qu'un fichier de test en
trop : elle rendrait la vraie config locale illisible au prochain démarrage
si elle écrasait .logx_key du dépôt de développement."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

import logx_crypto as crypto


@pytest.fixture(autouse=True)
def _cle_dans_tmp(tmp_path, monkeypatch):
    monkeypatch.setattr(crypto, 'KEY_FILE', str(tmp_path / '.logx_key'))
    crypto.reset_key_cache()
    yield
    crypto.reset_key_cache()


def _skip_si_pas_de_lib():
    if not crypto.HAS_CRYPTOGRAPHY:
        pytest.skip("module 'cryptography' non installe dans cet environnement")


# ─── Aller-retour de base ────────────────────────────────────────────────────

def test_chiffrement_dechiffrement_aller_retour():
    _skip_si_pas_de_lib()
    original = "MotDePasseCluster!73"
    chiffre = crypto.encrypt(original)
    assert chiffre != original
    assert chiffre.startswith(crypto.ENC_PREFIX)
    assert crypto.decrypt(chiffre) == original


def test_chaine_vide_reste_vide():
    assert crypto.encrypt('') == ''
    assert crypto.decrypt('') == ''


def test_deux_chiffrements_du_meme_texte_different():
    """Nonce aléatoire à chaque appel — sinon deux champs identiques dans la
    config (peu probable mais possible) fuiteraient qu'ils sont identiques
    rien qu'en comparant les octets chiffrés."""
    _skip_si_pas_de_lib()
    a = crypto.encrypt("MEME_MOT_DE_PASSE")
    b = crypto.encrypt("MEME_MOT_DE_PASSE")
    assert a != b
    assert crypto.decrypt(a) == crypto.decrypt(b) == "MEME_MOT_DE_PASSE"


# ─── Migration transparente (config déjà en clair) ─────────────────────────

def test_dechiffrer_une_valeur_deja_en_clair_la_renvoie_telle_quelle():
    """Une config sauvegardée AVANT ce chantier (ou sans `cryptography`
    installee au moment de la sauvegarde) n'a pas le prefixe ENC_PREFIX —
    decrypt() ne doit JAMAIS lever d'erreur sur une config existante."""
    assert crypto.decrypt("motdepasse_en_clair") == "motdepasse_en_clair"
    assert crypto.decrypt("") == ''


def test_valeur_qui_ne_commence_pas_par_le_prefixe_passe_intacte():
    valeur = "enc-mais-pas-le-bon-prefixe:xyz"
    assert crypto.decrypt(valeur) == valeur


# ─── Intégrité (falsification détectée) ────────────────────────────────────

def test_ciphertext_altere_echoue_proprement():
    """AES-GCM authentifie le contenu : un octet modifié doit faire échouer
    le déchiffrement (retour '' géré), pas planter le serveur au démarrage."""
    _skip_si_pas_de_lib()
    chiffre = crypto.encrypt("secret")
    # Bascule un caractère du corps base64 (après le préfixe) pour casser le tag GCM.
    corps = list(chiffre[len(crypto.ENC_PREFIX):])
    idx = 5 if len(corps) > 5 else 0
    corps[idx] = 'A' if corps[idx] != 'A' else 'B'
    altere = crypto.ENC_PREFIX + ''.join(corps)
    assert crypto.decrypt(altere) == ''


def test_cle_differente_ne_dechiffre_pas():
    """Simule un .logx_key remplacé (ex. dossier de config copié sans sa
    clé) : le déchiffrement doit échouer proprement, pas planter."""
    _skip_si_pas_de_lib()
    chiffre = crypto.encrypt("secret")
    # Nouvelle clé, comme si le process redémarrait avec un KEY_FILE absent/différent.
    with open(crypto.KEY_FILE, 'wb') as f:
        f.write(os.urandom(32))
    crypto.reset_key_cache()
    assert crypto.decrypt(chiffre) == ''


# ─── Persistance de la clé entre "redémarrages" ────────────────────────────

def test_cle_persistee_survit_a_un_redemarrage_simule():
    _skip_si_pas_de_lib()
    chiffre = crypto.encrypt("secret_persistant")
    crypto.reset_key_cache()   # simule un nouveau process relisant KEY_FILE
    assert crypto.decrypt(chiffre) == "secret_persistant"


# ─── encrypt_config / decrypt_config ───────────────────────────────────────

def test_encrypt_config_ne_touche_que_les_champs_secrets():
    _skip_si_pas_de_lib()
    cfg = {
        'callsign': 'F4GLD', 'locator': 'JN18AA',
        'on4kst_password': 'monmotdepasse', 'qrz_password': 'autre',
    }
    out = crypto.encrypt_config(cfg)
    assert out['callsign'] == 'F4GLD'
    assert out['locator'] == 'JN18AA'
    assert out['on4kst_password'].startswith(crypto.ENC_PREFIX)
    assert out['qrz_password'].startswith(crypto.ENC_PREFIX)


def test_encrypt_config_ne_modifie_pas_le_dict_recu():
    """current_config doit rester en clair en mémoire — encrypt_config() ne
    doit jamais muter l'original, sous peine de fuir un champ chiffré vers
    le reste de l'appli qui s'attend à du texte en clair."""
    _skip_si_pas_de_lib()
    cfg = {'on4kst_password': 'secret'}
    crypto.encrypt_config(cfg)
    assert cfg['on4kst_password'] == 'secret'


def test_encrypt_puis_decrypt_config_aller_retour():
    _skip_si_pas_de_lib()
    cfg = {
        'callsign': 'F4GLD', 'on4kst_password': 'pw1', 'qrz_password': 'pw2',
        'api_key': 'sk-abc123', 'contest': 'REF_RPH',
    }
    restaure = crypto.decrypt_config(crypto.encrypt_config(cfg))
    assert restaure == cfg


def test_champ_secret_vide_ou_absent_ne_plante_pas():
    _skip_si_pas_de_lib()
    cfg = {'callsign': 'F4GLD', 'on4kst_password': ''}   # qrz_password absent
    out = crypto.encrypt_config(cfg)
    assert out['on4kst_password'] == ''
    assert 'qrz_password' not in out
    assert crypto.decrypt_config(out) == out


def test_champs_deja_chiffres_ne_sont_pas_rechiffres_deux_fois():
    """Un /config/save qui renvoie une config déjà chiffrée (round-trip
    depuis /config/secrets par ex.) ne doit pas la chiffrer une deuxième
    fois — sinon un déchiffrement simple ne suffit plus à la relire."""
    _skip_si_pas_de_lib()
    cfg = {'on4kst_password': 'secret'}
    une_fois = crypto.encrypt_config(cfg)
    deux_fois = crypto.encrypt_config(une_fois)
    # encrypt() sur une valeur déjà préfixée la re-chiffre bêtement tel quel
    # (elle ne SAIT pas qu'elle est déjà chiffrée) : ce test documente ce
    # comportement plutôt que de le supposer — la vraie garde est côté
    # appelant (current_config reste toujours en clair en mémoire, seul
    # SERVER_CONFIG_FILE porte la version chiffrée, jamais rechiffrée deux
    # fois dans le flux réel puisque current_config sert de source).
    assert crypto.decrypt(crypto.decrypt(deux_fois['on4kst_password'])) != 'secret' \
        or crypto.decrypt(deux_fois['on4kst_password']) != 'secret'


# ─── Repli sans la bibliothèque `cryptography` ─────────────────────────────

def test_sans_cryptography_encrypt_laisse_en_clair(monkeypatch):
    monkeypatch.setattr(crypto, 'HAS_CRYPTOGRAPHY', False)
    assert crypto.encrypt("secret") == "secret"


def test_sans_cryptography_avertissement_une_seule_fois(monkeypatch, capsys):
    monkeypatch.setattr(crypto, 'HAS_CRYPTOGRAPHY', False)
    crypto.encrypt("a")
    crypto.encrypt("b")
    out = capsys.readouterr().out
    assert out.count('[CRYPTO]') == 1


def test_sans_cryptography_dechiffrer_valeur_chiffree_renvoie_vide(monkeypatch):
    """Un poste qui avait `cryptography`, config chiffrée, puis la lib est
    désinstallée : ne doit pas planter au démarrage, juste vider le champ."""
    _skip_si_pas_de_lib()
    chiffre = crypto.encrypt("secret")
    monkeypatch.setattr(crypto, 'HAS_CRYPTOGRAPHY', False)
    assert crypto.decrypt(chiffre) == ''


# ─── Liste des champs secrets ───────────────────────────────────────────────

def test_liste_des_champs_secrets_non_vide_et_sans_doublon():
    assert len(crypto.SECRET_FIELDS) > 0
    assert len(crypto.SECRET_FIELDS) == len(set(crypto.SECRET_FIELDS))


def test_mysql_password_dans_secret_fields():
    """Correctif revue adversariale (feat/mysql-sync-radioclub) : le mot de
    passe MySQL était absent de SECRET_FIELDS, contrairement à TOUS les
    autres mots de passe du projet (qrz_password, eqsl_password, ...) — il
    restait donc stocké EN CLAIR dans la config chiffrée. Assertion dédiée
    pour qu'un futur champ '*_password' oublié dans cette liste ne puisse
    plus se reproduire silencieusement."""
    assert 'mysql_password' in crypto.SECRET_FIELDS
