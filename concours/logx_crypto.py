# -*- coding: utf-8 -*-
"""Chiffrement au repos des identifiants stockés dans .server_config.json
(mots de passe cluster ON4KST/QRZ/eQSL/LoTW, clés API IA/ClubLog/QRZCQ...).

AES-256-GCM avec une clé locale générée une fois (.logx_key, à côté de
.server_config.json — jamais suivie par git, permissions restreintes sur
POSIX). PAS une phrase secrète demandée à l'utilisateur : LogX AI reste
zéro-clic au démarrage, et cette protection couvre l'EXPOSITION ACCIDENTELLE
du fichier de config (copie, sauvegarde, dossier Cloud Sync partagé avec
d'autres services, capture d'écran de la config...), pas un attaquant ayant
déjà un accès complet à ce même poste sous ce même compte — DPAPI (Windows)
ou Keychain (macOS) ne feraient guère mieux dans ce cas précis, tout en
cassant le multi-plateforme (LogX tourne aussi sur Linux).

Dépendance optionnelle (cryptography, voir requirements.txt) : si absente,
les secrets restent en clair (comportement historique, avertissement affiché
UNE FOIS plutôt qu'un crash) — même philosophie que pyserial/ephem/pyttsx3
ailleurs dans ce projet : le cœur du serveur fonctionne sans.

Migration transparente : une valeur déjà en clair dans une config existante
(avant ce chantier, ou sauvegardée sans `cryptography` installé) n'a pas le
préfixe ENC_PREFIX — decrypt() la renvoie telle quelle, sans erreur. Elle
sera chiffrée au prochain /config/save.
"""
import base64
import os

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    HAS_CRYPTOGRAPHY = True
except Exception:
    HAS_CRYPTOGRAPHY = False

KEY_FILE = '.logx_key'
ENC_PREFIX = 'enc:v1:'

# Liste UNIQUE des champs secrets — reprise de l'endpoint /config/secrets
# (logx_http.py) qui l'exposait déjà en dur : une deuxième liste écrite à la
# main aurait fini par diverger (le genre de piège déjà rencontré sur ce
# projet — voir mémoire "liste d'identifiants écrite à la main").
SECRET_FIELDS = (
    'api_key', 'clublog_api_key', 'clublog_password', 'eqsl_password',
    'lan_sync_token', 'lotw_password', 'on4kst_password', 'qrz_password',
    'qrzcq_api_key', 'hrdlog_code', 'qrz_logbook_key', 'sota_client_id',
    'cloudsync_secret', 'voicekeyer_ai_api_key', 'mysql_password',
    'relay_password', 'icomremote_password',
)

_cache = {'key': None, 'warned_missing_lib': False}


def _load_or_create_key():
    """Clé AES 256 bits persistée dans KEY_FILE. Générée une seule fois ;
    un fichier corrompu ou de mauvaise taille est traité comme absent plutôt
    que de faire planter le serveur (une config déchiffrable devient alors
    illisible avec la NOUVELLE clé — préférable à un crash au démarrage)."""
    if _cache['key'] is not None:
        return _cache['key']
    key = None
    if os.path.exists(KEY_FILE):
        try:
            with open(KEY_FILE, 'rb') as f:
                data = f.read()
            if len(data) == 32:
                key = data
        except Exception:
            key = None
    if key is None:
        key = os.urandom(32)
        try:
            with open(KEY_FILE, 'wb') as f:
                f.write(key)
            try:
                os.chmod(KEY_FILE, 0o600)
            except Exception:
                pass  # Windows : chmod n'a pas de sens ici, l'ACL du profil utilisateur suffit
        except Exception:
            pass  # Écriture impossible (FS en lecture seule...) : la clé ne survivra
                  # pas au redémarrage, mais le process en cours reste fonctionnel.
    _cache['key'] = key
    return key


def reset_key_cache():
    """Pour les tests : oublie la clé en mémoire, pour qu'un prochain appel
    relise/régénère KEY_FILE plutôt que de garder une clé d'un test précédent."""
    _cache['key'] = None
    _cache['warned_missing_lib'] = False


def encrypt(plaintext):
    """str -> str chiffrée (préfixée ENC_PREFIX), ou INCHANGÉE si vide ou si
    `cryptography` est absent (avertissement affiché une seule fois)."""
    if not plaintext:
        return plaintext
    if not HAS_CRYPTOGRAPHY:
        if not _cache['warned_missing_lib']:
            _cache['warned_missing_lib'] = True
            print("[CRYPTO] Module 'cryptography' absent : identifiants stockes en "
                  "clair (pip install cryptography pour les chiffrer au repos).")
        return plaintext
    try:
        key = _load_or_create_key()
        nonce = os.urandom(12)
        ct = AESGCM(key).encrypt(nonce, plaintext.encode('utf-8'), None)
        return ENC_PREFIX + base64.b64encode(nonce + ct).decode('ascii')
    except Exception as e:
        print(f"[CRYPTO] Chiffrement echoue, valeur laissee en clair : {e}")
        return plaintext


def decrypt(value):
    """Inverse de encrypt(). Une valeur sans ENC_PREFIX est renvoyée TELLE
    QUELLE (config déjà en clair) — jamais d'erreur sur une ancienne config."""
    if not value or not isinstance(value, str) or not value.startswith(ENC_PREFIX):
        return value
    if not HAS_CRYPTOGRAPHY:
        # Chiffré sur un poste qui avait `cryptography`, relu sur un poste où
        # elle a été désinstallée depuis : impossible à déchiffrer, mais ça ne
        # doit pas empêcher le serveur de démarrer pour autant.
        print("[CRYPTO] Valeur chiffree mais module 'cryptography' absent : "
              "champ vide plutot qu'une erreur au demarrage.")
        return ''
    try:
        key = _load_or_create_key()
        raw = base64.b64decode(value[len(ENC_PREFIX):])
        nonce, ct = raw[:12], raw[12:]
        return AESGCM(key).decrypt(nonce, ct, None).decode('utf-8')
    except Exception as e:
        print(f"[CRYPTO] Dechiffrement echoue (cle changee ou fichier corrompu ?) : {e}")
        return ''


def encrypt_config(cfg):
    """Nouveau dict, champs secrets chiffrés — pour écrire .server_config.json.
    Ne modifie JAMAIS le dict reçu : current_config doit rester en clair en
    mémoire, le reste de l'appli ne doit rien savoir de ce chiffrement."""
    out = dict(cfg)
    for f in SECRET_FIELDS:
        if out.get(f):
            out[f] = encrypt(str(out[f]))
    return out


def decrypt_config(cfg):
    """Inverse — appelé une seule fois, juste après la lecture de
    .server_config.json au démarrage du serveur."""
    out = dict(cfg)
    for f in SECRET_FIELDS:
        if out.get(f):
            out[f] = decrypt(out[f])
    return out
