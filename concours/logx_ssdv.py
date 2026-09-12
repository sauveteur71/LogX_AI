# -*- coding: utf-8 -*-
"""SSDV (Slow Scan Digital Video) -- Phase 1, cadrage
docs/superpowers/specs/2026-09-11-ssdv-integration-design.md (validé par
F4GLD le 11/09/2026).

Réception d'images transmises par ballons/satellites/stations distantes au
format SSDV (256 octets/paquet, UKHAS). Portée volontairement limitée :

- le décodage/encodage RÉEL (charge utile + correction Reed-Solomon) est
  délégué au binaire externe `ssdv` (fsphil, GPL-3.0) en sous-processus --
  jamais réimplémenté ici. Même patron de licence que VOACAP
  (logx_voacap.py, PR #16) : binaire non modifié appelé en sous-processus
  séparé (« mere aggregation »), n'impose pas la GPL au reste du dépôt.
- le parseur Python ci-dessous ne lit QUE l'en-tête du paquet (15 des 256
  octets) -- utile pour le suivi/l'affichage (progression, paquets
  manquants) sans dépendre du binaire pour ça.
- résolution du binaire : config explicite (`ssdv.bin_path`) > binaire
  vendorisé (concours/vendor/ssdv/<os>/ssdv[.exe], pas encore livré à ce
  stade -- obtention/compilation du binaire est un suivi séparé, non
  bloquant : les tests couvrent le parseur/assembleur sans lui) > PATH
  système > FileNotFoundError explicite. Même patron que resoudre_jt9()
  (logx_q65_natif.py).

Offsets du format de paquet relus ligne à ligne contre le vrai code source
de fsphil/ssdv (ssdv.c/ssdv.h) le 11/09/2026 -- pas déduits d'une note
tierce (voir le cadrage cité ci-dessus pour le détail de la vérification,
y compris une contradiction NORMAL/NOFEC trouvée et corrigée pendant cette
relecture)."""
import os
import shutil
import subprocess
import sys

_ICI = os.path.dirname(os.path.abspath(__file__))

# ─── Format de paquet (256 octets, en-tête 15 octets, offsets 0-14) ─────────
TAILLE_PAQUET = 256
TAILLE_ENTETE = 15
SYNC = 0x55
TYPE_NORMAL = 0x00   # avec correction Reed-Solomon (charge utile 205 o)
TYPE_NOFEC = 0x01    # sans correction (charge utile 237 o)


# ═══════════════════════════════════════════════════════════════════════════
# Indicatif -- encodage base-40 (32 bits), format UKHAS/SSDV.
# '-' = 0, '0'-'9' = 1..10, 'A'-'Z' = 14..39 (11-13 inutilisés).
# ═══════════════════════════════════════════════════════════════════════════

_MAX_CALLSIGN = 6   # SSDV_MAX_CALLSIGN dans ssdv.h


def _valeur_base40(c):
    if c == '-':
        return 0
    if '0' <= c <= '9':
        return ord(c) - ord('0') + 1
    if 'A' <= c <= 'Z':
        return ord(c) - ord('A') + 14
    raise ValueError("caractère non encodable en base-40 : %r" % c)


def encoder_indicatif_base40(indicatif):
    indicatif = indicatif.upper()
    if len(indicatif) > _MAX_CALLSIGN:
        raise ValueError(
            "indicatif trop long pour SSDV (max %d caractères) : %r"
            % (_MAX_CALLSIGN, indicatif))
    x = 0
    for c in indicatif:
        x = x * 40 + _valeur_base40(c)
    return x


def decoder_indicatif_base40(valeur):
    if valeur == 0:
        return ''
    chiffres = []
    x = valeur
    while x > 0:
        chiffres.append(x % 40)
        x //= 40
    lettres = []
    for d in reversed(chiffres):
        if d == 0:
            lettres.append('-')
        elif 1 <= d <= 10:
            lettres.append(chr(ord('0') + d - 1))
        elif 14 <= d <= 39:
            lettres.append(chr(ord('A') + d - 14))
        else:
            raise ValueError("chiffre base-40 invalide : %d" % d)
    return ''.join(lettres)


# ═══════════════════════════════════════════════════════════════════════════
# Parseur d'en-tête -- lit uniquement les 15 premiers octets du paquet.
# ═══════════════════════════════════════════════════════════════════════════

def parser_entete(paquet):
    if len(paquet) < TAILLE_ENTETE:
        raise ValueError(
            "paquet trop court pour un en-tête SSDV (%d < %d octets)"
            % (len(paquet), TAILLE_ENTETE))
    if paquet[0] != SYNC:
        raise ValueError(
            "octet de synchronisation invalide : 0x%02X attendu 0x%02X"
            % (paquet[0], SYNC))
    type_brut = paquet[1] - 0x66
    if type_brut not in (TYPE_NORMAL, TYPE_NOFEC):
        raise ValueError("type de paquet SSDV inconnu : octet 0x%02X" % paquet[1])
    valeur_indicatif = int.from_bytes(paquet[2:6], 'big')
    fanions = paquet[11]
    return {
        'type': 'normal' if type_brut == TYPE_NORMAL else 'nofec',
        'indicatif': decoder_indicatif_base40(valeur_indicatif),
        'image_id': paquet[6],
        'packet_id': (paquet[7] << 8) | paquet[8],
        'largeur': paquet[9] * 16,
        'hauteur': paquet[10] * 16,
        'qualite': ((fanions >> 3) & 0x07) ^ 4,
        'derniere_image': bool((fanions >> 2) & 1),
        'mode_mcu': fanions & 0x03,
        'decalage_mcu': paquet[12],
        'id_mcu': (paquet[13] << 8) | paquet[14],
    }


# ═══════════════════════════════════════════════════════════════════════════
# Glue transport (Phase 2, cadrage docs/superpowers/specs/2026-09-11-ssdv-
# phase2-transport-cadrage.md) -- extrait un paquet SSDV du champ INFO
# d'une trame AX.25 déjà désencapsulée (logx_ax25.parser_entete). Ne valide
# QUE la taille : la validation structurelle complète (sync, type...) reste
# dans parser_entete() ci-dessus, jamais dupliquée ici.
# ═══════════════════════════════════════════════════════════════════════════

def paquet_depuis_trame_ax25(entete_ax25):
    """entete_ax25 : dict renvoyé par logx_ax25.parser_entete(). Renvoie le
    champ INFO s'il a la taille d'un paquet SSDV (256 octets), sinon None
    -- une trame AX.25/APRS ordinaire (position, message texte...) n'a
    aucune raison d'avoir cette taille exacte par hasard, mais ce n'est
    qu'un premier filtre bon marché : appeler parser_entete() sur le
    résultat pour la vraie validation avant de l'utiliser."""
    info = entete_ax25.get('info', b'')
    return info if len(info) == TAILLE_PAQUET else None


# ═══════════════════════════════════════════════════════════════════════════
# Assembleur d'image -- suivi de progression, paquets manquants/dupliqués.
# Ne touche jamais la charge utile : la reconstruction JPEG réelle passe par
# assembler_image() -> decoder() (le binaire externe).
# ═══════════════════════════════════════════════════════════════════════════

def nouvel_assemblage():
    return {
        'image_id': None,
        'indicatif': None,
        'largeur': None,
        'hauteur': None,
        'eoi_id': None,
        'paquets': {},   # packet_id -> paquet brut (256 octets)
    }


def ajouter_paquet(assemblage, entete, paquet_brut):
    if assemblage['image_id'] is not None and assemblage['image_id'] != entete['image_id']:
        raise ValueError(
            "paquet de l'image %d reçu pendant l'assemblage de l'image %d"
            % (entete['image_id'], assemblage['image_id']))
    assemblage['image_id'] = entete['image_id']
    assemblage['indicatif'] = entete['indicatif']
    if entete['largeur']:
        assemblage['largeur'] = entete['largeur']
    if entete['hauteur']:
        assemblage['hauteur'] = entete['hauteur']
    if entete['derniere_image']:
        assemblage['eoi_id'] = entete['packet_id']
    assemblage['paquets'][entete['packet_id']] = paquet_brut
    return assemblage


def _borne(assemblage):
    if assemblage['eoi_id'] is not None:
        return assemblage['eoi_id']
    if assemblage['paquets']:
        return max(assemblage['paquets'])
    return None


def progression(assemblage):
    borne = _borne(assemblage)
    if borne is None:
        return 0.0
    recus = sum(1 for i in range(borne + 1) if i in assemblage['paquets'])
    return recus / (borne + 1) * 100.0


def paquets_manquants(assemblage):
    borne = _borne(assemblage)
    if borne is None:
        return []
    return [i for i in range(borne + 1) if i not in assemblage['paquets']]


def est_complet(assemblage):
    return assemblage['eoi_id'] is not None and not paquets_manquants(assemblage)


def paquets_ordonnes(assemblage):
    return [assemblage['paquets'][i] for i in sorted(assemblage['paquets'])]


# ═══════════════════════════════════════════════════════════════════════════
# Résolution + appel du binaire externe `ssdv` (sous-processus).
# ═══════════════════════════════════════════════════════════════════════════

def resoudre_ssdv(cfg=None):
    """Chemin absolu du binaire ssdv, par ordre de priorité : config
    `ssdv.bin_path` explicite > binaire vendorisé
    (concours/vendor/ssdv/<nom>) > ssdv/ssdv.exe sur le PATH. Lève
    FileNotFoundError explicite si aucun des trois (même patron que
    resoudre_jt9(), logx_q65_natif.py)."""
    p = ((cfg or {}).get('ssdv', {}) or {}).get('bin_path')
    if p and os.path.isfile(p):
        return p
    for nom in ('ssdv.exe', 'ssdv'):
        cand = os.path.join(_ICI, 'vendor', 'ssdv', nom)
        if os.path.isfile(cand):
            return cand
    trouve = shutil.which('ssdv') or shutil.which('ssdv.exe')
    if trouve:
        return trouve
    raise FileNotFoundError(
        "binaire ssdv introuvable : renseigne ssdv.bin_path dans config.json, "
        "installe ssdv (fsphil/ssdv), ou attends le binaire vendorisé."
    )


def ssdv_disponible(cfg=None):
    try:
        resoudre_ssdv(cfg)
        return True
    except FileNotFoundError:
        return False


def _env_avec_libs(chemin_bin):
    """Même raisonnement que _env_avec_libs() de logx_q65_natif.py : le
    binaire vendorisé et ses dépendances dynamiques vivent ensemble, il faut
    que le sous-processus les trouve -- y compris figé sous PyInstaller."""
    env = os.environ.copy()
    if os.name == 'nt':
        return env
    var = 'DYLD_LIBRARY_PATH' if sys.platform == 'darwin' else 'LD_LIBRARY_PATH'
    d = os.path.dirname(os.path.abspath(chemin_bin))
    ancien = env.get(var, '')
    env[var] = d + (os.pathsep + ancien if ancien else '')
    return env


def _lancer(cmd, chemin_bin, timeout):
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=timeout,
                            env=_env_avec_libs(chemin_bin))
    except subprocess.TimeoutExpired:
        return {'ok': False, 'error': "délai dépassé (ssdv bloqué)"}
    if r.returncode != 0:
        err = (r.stderr or b'').decode('utf-8', 'replace').strip()
        return {'ok': False, 'error': err or "ssdv a échoué (code %d)" % r.returncode}
    return {'ok': True}


def decoder(chemin_paquets, chemin_sortie_jpeg, cfg=None, timeout=30):
    """Décode un fichier de paquets SSDV bruts (concaténés) en JPEG, via le
    binaire externe `ssdv -d`."""
    try:
        chemin_bin = resoudre_ssdv(cfg)
    except FileNotFoundError as e:
        return {'ok': False, 'error': str(e)}
    cmd = [chemin_bin, '-d', chemin_paquets, chemin_sortie_jpeg]
    return _lancer(cmd, chemin_bin, timeout)


def encoder(chemin_image, chemin_sortie_bin, indicatif, image_id=0, qualite=4,
            cfg=None, timeout=30):
    """Encode une image JPEG en flux de paquets SSDV, via `ssdv -e`."""
    try:
        chemin_bin = resoudre_ssdv(cfg)
    except FileNotFoundError as e:
        return {'ok': False, 'error': str(e)}
    cmd = [chemin_bin, '-e', '-c', indicatif, '-i', str(image_id), '-q', str(qualite),
           chemin_image, chemin_sortie_bin]
    return _lancer(cmd, chemin_bin, timeout)


def assembler_image(assemblage, chemin_sortie_jpeg, cfg=None, timeout=30):
    """Écrit les paquets de l'assemblage dans l'ordre du packet_id vers un
    fichier temporaire, puis délègue la reconstruction JPEG à decoder()
    (le binaire externe -- jamais réimplémentée ici, cf. docstring du
    module)."""
    import tempfile
    ordonnes = paquets_ordonnes(assemblage)
    fd, chemin_tmp = tempfile.mkstemp(suffix='.bin')
    try:
        with os.fdopen(fd, 'wb') as f:
            for p in ordonnes:
                f.write(p)
        return decoder(chemin_tmp, chemin_sortie_jpeg, cfg=cfg, timeout=timeout)
    finally:
        try:
            os.remove(chemin_tmp)
        except OSError:
            pass
