# -*- coding: utf-8 -*-
"""Tests du module SSDV (logx_ssdv) -- Phase 1 (offline, zéro radio).

Portée volontairement limitée (cadrage docs/superpowers/specs/
2026-09-11-ssdv-integration-design.md, décisions F4GLD du 11/09/2026) :
- le parseur Python ne lit QUE l'en-tête du paquet (15 octets), jamais la
  charge utile ni le FEC Reed-Solomon -- la reconstruction JPEG complète
  reste déléguée au binaire externe `ssdv` (fsphil, GPL-3.0) en
  sous-processus, jamais réimplémentée ici ;
- les offsets testés ci-dessous ont été relus ligne à ligne contre le vrai
  code source de fsphil/ssdv (ssdv.c/ssdv.h) le 11/09/2026, PAS déduits de
  la note reçue -- une contradiction (NORMAL/NOFEC inversés) a été trouvée
  et corrigée pendant cette vérification, d'où des tests qui figent
  explicitement le sens retenu ;
- aucun test n'exige le binaire réel : les tests de sous-processus
  monkeypatchent subprocess.run (même patron que test_voacap_timeout.py) ;
  un seul test d'intégration réelle est protégé par ssdv_disponible() et se
  saute silencieusement si le binaire est absent (même patron que
  test_q65_natif.py pour jt9).
"""
import os
import subprocess
import sys

import pytest

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE not in sys.path:
    sys.path.insert(0, BASE)

import logx_ssdv as ssdv  # noqa: E402


# ═══════════════════════════════════════════════════════════════════════════
# Construction d'un paquet synthétique -- même conventions que ssdv.c
# (relues le 11/09/2026, voir docstring du module).
# ═══════════════════════════════════════════════════════════════════════════

def _paquet(indicatif='F4GLD', image_id=3, packet_id=5, largeur=320,
            hauteur=240, qualite=4, eoi=False, type_paquet='nofec',
            mode_mcu=0, decalage_mcu=0, id_mcu=0xFFFF):
    valeur = ssdv.encoder_indicatif_base40(indicatif)
    type_octet = 0x66 + (ssdv.TYPE_NOFEC if type_paquet == 'nofec' else ssdv.TYPE_NORMAL)
    fanions = ((qualite ^ 4) << 3) | ((1 if eoi else 0) << 2) | (mode_mcu & 0x03)
    entete = bytes([
        ssdv.SYNC,
        type_octet,
        (valeur >> 24) & 0xFF, (valeur >> 16) & 0xFF,
        (valeur >> 8) & 0xFF, valeur & 0xFF,
        image_id & 0xFF,
        (packet_id >> 8) & 0xFF, packet_id & 0xFF,
        (largeur // 16) & 0xFF,
        (hauteur // 16) & 0xFF,
        fanions,
        decalage_mcu & 0xFF,
        (id_mcu >> 8) & 0xFF, id_mcu & 0xFF,
    ])
    assert len(entete) == ssdv.TAILLE_ENTETE
    return entete + bytes(ssdv.TAILLE_PAQUET - ssdv.TAILLE_ENTETE)


# ═══════════════════════════════════════════════════════════════════════════
# Base-40 (indicatif) -- '-'=0, '0'-'9'=1..10, 'A'-'Z'=14..39, aller-retour.
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize('indicatif', ['F4GLD', 'W1AW', 'N0CALL', 'A', '2E0ABC', 'K1-2'])
def test_base40_aller_retour(indicatif):
    valeur = ssdv.encoder_indicatif_base40(indicatif)
    assert ssdv.decoder_indicatif_base40(valeur) == indicatif.upper()


def test_base40_valeurs_de_reference():
    # '-' = 0, chiffres = 1..10, lettres = 14..39 -- vérifiés contre
    # encode_callsign() de ssdv.c (relu le 11/09/2026).
    assert ssdv.encoder_indicatif_base40('-') == 0
    assert ssdv.encoder_indicatif_base40('0') == 1
    assert ssdv.encoder_indicatif_base40('9') == 10
    assert ssdv.encoder_indicatif_base40('A') == 14
    assert ssdv.encoder_indicatif_base40('Z') == 39


def test_base40_indicatif_trop_long_leve():
    with pytest.raises(ValueError):
        ssdv.encoder_indicatif_base40('BEAUCOUPTROPLONG')


def test_base40_caractere_invalide_leve():
    with pytest.raises(ValueError):
        ssdv.encoder_indicatif_base40('F4GLD!')


# ═══════════════════════════════════════════════════════════════════════════
# parser_entete() -- offsets vérifiés contre ssdv.c/ssdv.h (11/09/2026).
# ═══════════════════════════════════════════════════════════════════════════

def test_parser_entete_champs_de_base():
    p = _paquet(indicatif='F4GLD', image_id=7, packet_id=42, largeur=320,
                hauteur=240, qualite=6, eoi=False)
    e = ssdv.parser_entete(p)
    assert e['indicatif'] == 'F4GLD'
    assert e['image_id'] == 7
    assert e['packet_id'] == 42
    assert e['largeur'] == 320
    assert e['hauteur'] == 240
    assert e['qualite'] == 6
    assert e['derniere_image'] is False


def test_parser_entete_type_nofec_vs_normal():
    """Piège trouvé en vérifiant : une première lecture du code source avait
    inversé NORMAL (0x00, avec FEC Reed-Solomon) et NOFEC (0x01, sans FEC).
    Ce test fige le sens correct, relu directement dans
    ssdv_enc_get_packet()/ssdv_dec_is_packet()."""
    assert ssdv.parser_entete(_paquet(type_paquet='nofec'))['type'] == 'nofec'
    assert ssdv.parser_entete(_paquet(type_paquet='normal'))['type'] == 'normal'
    assert ssdv.TYPE_NORMAL == 0x00
    assert ssdv.TYPE_NOFEC == 0x01


def test_parser_entete_drapeau_derniere_image():
    e = ssdv.parser_entete(_paquet(eoi=True))
    assert e['derniere_image'] is True


def test_parser_entete_packet_id_grand_endian():
    # packet_id = (o[7]<<8)|o[8] -- MSB en premier.
    e = ssdv.parser_entete(_paquet(packet_id=0x1234))
    assert e['packet_id'] == 0x1234


def test_parser_entete_largeur_hauteur_multiples_de_16():
    e = ssdv.parser_entete(_paquet(largeur=352, hauteur=288))
    assert e['largeur'] == 352
    assert e['hauteur'] == 288


def test_parser_entete_paquet_trop_court_leve():
    with pytest.raises(ValueError):
        ssdv.parser_entete(bytes(10))


def test_parser_entete_sync_invalide_leve():
    p = bytearray(_paquet())
    p[0] = 0xAA
    with pytest.raises(ValueError):
        ssdv.parser_entete(bytes(p))


def test_parser_entete_type_inconnu_leve():
    p = bytearray(_paquet())
    p[1] = 0x66 + 0x05   # ni NORMAL ni NOFEC
    with pytest.raises(ValueError):
        ssdv.parser_entete(bytes(p))


# ═══════════════════════════════════════════════════════════════════════════
# Assembleur -- progression, paquets manquants/dupliqués, complétude.
# ═══════════════════════════════════════════════════════════════════════════

def test_assemblage_vide_au_depart():
    a = ssdv.nouvel_assemblage()
    assert ssdv.progression(a) == 0.0
    assert ssdv.paquets_manquants(a) == []
    assert ssdv.est_complet(a) is False


def test_assemblage_progression_sans_eoi_utilise_le_max_recu():
    a = ssdv.nouvel_assemblage()
    for pid in (0, 1, 2):
        ssdv.ajouter_paquet(a, ssdv.parser_entete(_paquet(packet_id=pid)), _paquet(packet_id=pid))
    # 3 paquets reçus sur 0..2 (borne = max reçu, pas d'EOI encore vu) = 100%
    assert ssdv.progression(a) == pytest.approx(100.0)
    ssdv.ajouter_paquet(a, ssdv.parser_entete(_paquet(packet_id=4)), _paquet(packet_id=4))
    # id 3 manquant : borne devient 4, 4 reçus sur 5 attendus
    assert ssdv.progression(a) == pytest.approx(80.0)
    assert ssdv.paquets_manquants(a) == [3]


def test_assemblage_complet_seulement_apres_eoi_et_sans_trou():
    a = ssdv.nouvel_assemblage()
    for pid in (0, 1):
        ssdv.ajouter_paquet(a, ssdv.parser_entete(_paquet(packet_id=pid)), _paquet(packet_id=pid))
    assert ssdv.est_complet(a) is False   # pas d'EOI reçu
    ssdv.ajouter_paquet(a, ssdv.parser_entete(_paquet(packet_id=2, eoi=True)), _paquet(packet_id=2, eoi=True))
    assert ssdv.est_complet(a) is True
    assert ssdv.progression(a) == pytest.approx(100.0)


def test_assemblage_eoi_avec_trou_reste_incomplet():
    a = ssdv.nouvel_assemblage()
    ssdv.ajouter_paquet(a, ssdv.parser_entete(_paquet(packet_id=0)), _paquet(packet_id=0))
    ssdv.ajouter_paquet(a, ssdv.parser_entete(_paquet(packet_id=2, eoi=True)), _paquet(packet_id=2, eoi=True))
    assert ssdv.est_complet(a) is False
    assert ssdv.paquets_manquants(a) == [1]


def test_assemblage_paquet_duplique_ne_compte_qu_une_fois():
    a = ssdv.nouvel_assemblage()
    ssdv.ajouter_paquet(a, ssdv.parser_entete(_paquet(packet_id=0)), _paquet(packet_id=0))
    ssdv.ajouter_paquet(a, ssdv.parser_entete(_paquet(packet_id=0)), _paquet(packet_id=0))
    assert len(a['paquets']) == 1


def test_assemblage_paquet_d_une_autre_image_leve():
    a = ssdv.nouvel_assemblage()
    ssdv.ajouter_paquet(a, ssdv.parser_entete(_paquet(image_id=1, packet_id=0)), _paquet(image_id=1, packet_id=0))
    with pytest.raises(ValueError):
        ssdv.ajouter_paquet(a, ssdv.parser_entete(_paquet(image_id=2, packet_id=1)), _paquet(image_id=2, packet_id=1))


def test_assemblage_paquets_ordonnes_par_packet_id():
    a = ssdv.nouvel_assemblage()
    for pid in (2, 0, 1):
        ssdv.ajouter_paquet(a, ssdv.parser_entete(_paquet(packet_id=pid)), _paquet(packet_id=pid))
    ordonnes = ssdv.paquets_ordonnes(a)
    assert len(ordonnes) == 3
    # chaque paquet brut contient son propre packet_id : reconstituer l'ordre lu
    ids_lus = [ssdv.parser_entete(p)['packet_id'] for p in ordonnes]
    assert ids_lus == [0, 1, 2]


# ═══════════════════════════════════════════════════════════════════════════
# Résolution du binaire externe -- même patron que resoudre_jt9()
# (logx_q65_natif.py) : config explicite > vendorisé > PATH > erreur.
# ═══════════════════════════════════════════════════════════════════════════

def test_resoudre_ssdv_prend_le_chemin_de_config_si_present(tmp_path):
    faux = tmp_path / 'monssdv'
    faux.write_text('faux binaire')
    chemin = ssdv.resoudre_ssdv({'ssdv': {'bin_path': str(faux)}})
    assert chemin == str(faux)


def test_resoudre_ssdv_trouve_le_binaire_vendorise(monkeypatch, tmp_path):
    vendor_dir = tmp_path / 'vendor' / 'ssdv'
    vendor_dir.mkdir(parents=True)
    nom = 'ssdv.exe' if os.name == 'nt' else 'ssdv'
    faux = vendor_dir / nom
    faux.write_text('faux binaire')
    monkeypatch.setattr(ssdv, '_ICI', str(tmp_path))
    monkeypatch.setattr(ssdv.shutil, 'which', lambda x: None)
    assert ssdv.resoudre_ssdv({}) == str(faux)


def test_resoudre_ssdv_leve_si_rien_de_disponible(monkeypatch, tmp_path):
    monkeypatch.setattr(ssdv, '_ICI', str(tmp_path))
    monkeypatch.setattr(ssdv.shutil, 'which', lambda x: None)
    with pytest.raises(FileNotFoundError):
        ssdv.resoudre_ssdv({})


def test_ssdv_disponible_reflete_resoudre_ssdv(monkeypatch, tmp_path):
    monkeypatch.setattr(ssdv, '_ICI', str(tmp_path))
    monkeypatch.setattr(ssdv.shutil, 'which', lambda x: None)
    assert ssdv.ssdv_disponible({}) is False
    monkeypatch.setattr(ssdv.shutil, 'which', lambda x: '/usr/bin/ssdv')
    assert ssdv.ssdv_disponible({}) is True


# ═══════════════════════════════════════════════════════════════════════════
# Sous-processus encode/decode -- monkeypatché, jamais le vrai binaire ici.
# ═══════════════════════════════════════════════════════════════════════════

def test_decoder_construit_la_commande_attendue(monkeypatch, tmp_path):
    appels = []

    def _run_faux(cmd, *a, **k):
        appels.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, stdout=b'', stderr=b'')
    monkeypatch.setattr(ssdv, 'resoudre_ssdv', lambda cfg=None: '/opt/ssdv')
    monkeypatch.setattr(ssdv.subprocess, 'run', _run_faux)

    src = tmp_path / 'in.bin'
    dst = tmp_path / 'out.jpg'
    src.write_bytes(b'\x00')
    r = ssdv.decoder(str(src), str(dst))
    assert r['ok'] is True
    assert appels[0][:2] == ['/opt/ssdv', '-d']
    assert str(src) in appels[0] and str(dst) in appels[0]


def test_encoder_construit_la_commande_attendue(monkeypatch, tmp_path):
    appels = []

    def _run_faux(cmd, *a, **k):
        appels.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, stdout=b'', stderr=b'')
    monkeypatch.setattr(ssdv, 'resoudre_ssdv', lambda cfg=None: '/opt/ssdv')
    monkeypatch.setattr(ssdv.subprocess, 'run', _run_faux)

    src = tmp_path / 'in.jpg'
    dst = tmp_path / 'out.bin'
    src.write_bytes(b'\xff\xd8')
    r = ssdv.encoder(str(src), str(dst), 'F4GLD', image_id=9, qualite=6)
    assert r['ok'] is True
    assert appels[0][0] == '/opt/ssdv' and appels[0][1] == '-e'
    assert 'F4GLD' in appels[0]
    assert '9' in appels[0]
    assert '6' in appels[0]


def test_decoder_binaire_absent_renvoie_erreur_propre(monkeypatch, tmp_path):
    def _leve(cfg=None):
        raise FileNotFoundError('ssdv introuvable')
    monkeypatch.setattr(ssdv, 'resoudre_ssdv', _leve)
    r = ssdv.decoder(str(tmp_path / 'in.bin'), str(tmp_path / 'out.jpg'))
    assert r['ok'] is False
    assert 'introuvable' in r['error'].lower()


def test_decoder_echec_sous_processus_devient_erreur_propre(monkeypatch, tmp_path):
    def _run_qui_echoue(cmd, *a, **k):
        return subprocess.CompletedProcess(cmd, 1, stdout=b'', stderr=b'paquets corrompus')
    monkeypatch.setattr(ssdv, 'resoudre_ssdv', lambda cfg=None: '/opt/ssdv')
    monkeypatch.setattr(ssdv.subprocess, 'run', _run_qui_echoue)
    r = ssdv.decoder(str(tmp_path / 'in.bin'), str(tmp_path / 'out.jpg'))
    assert r['ok'] is False
    assert 'paquets corrompus' in r['error']


def test_decoder_timeout_devient_erreur_propre(monkeypatch, tmp_path):
    def _run_qui_timeout(cmd, *a, **k):
        raise subprocess.TimeoutExpired(cmd=cmd, timeout=k.get('timeout', 30))
    monkeypatch.setattr(ssdv, 'resoudre_ssdv', lambda cfg=None: '/opt/ssdv')
    monkeypatch.setattr(ssdv.subprocess, 'run', _run_qui_timeout)
    r = ssdv.decoder(str(tmp_path / 'in.bin'), str(tmp_path / 'out.jpg'), timeout=1)
    assert r['ok'] is False
    assert 'délai' in r['error'].lower() or 'delai' in r['error'].lower()


def test_assembler_image_ecrit_les_paquets_ordonnes_puis_decode(monkeypatch, tmp_path):
    """assembler_image() doit concaténer les paquets bruts DANS L'ORDRE du
    packet_id (pas l'ordre d'arrivée) dans un fichier temporaire, puis
    appeler decoder() dessus -- vérifié en interceptant decoder()."""
    a = ssdv.nouvel_assemblage()
    for pid in (1, 0, 2):
        ssdv.ajouter_paquet(a, ssdv.parser_entete(_paquet(packet_id=pid, eoi=(pid == 2))),
                             _paquet(packet_id=pid, eoi=(pid == 2)))

    vu = {}

    def _decoder_faux(chemin_bin, chemin_jpeg, cfg=None, timeout=30):
        with open(chemin_bin, 'rb') as f:
            contenu = f.read()
        vu['contenu'] = contenu
        vu['sortie'] = chemin_jpeg
        return {'ok': True}
    monkeypatch.setattr(ssdv, 'decoder', _decoder_faux)

    dst = tmp_path / 'image.jpg'
    r = ssdv.assembler_image(a, str(dst))
    assert r['ok'] is True
    assert vu['sortie'] == str(dst)
    # 3 paquets de 256 octets, dans l'ordre 0,1,2
    assert len(vu['contenu']) == 3 * ssdv.TAILLE_PAQUET
    ids_lus = [ssdv.parser_entete(vu['contenu'][i * ssdv.TAILLE_PAQUET:(i + 1) * ssdv.TAILLE_PAQUET])['packet_id']
               for i in range(3)]
    assert ids_lus == [0, 1, 2]


# ═══════════════════════════════════════════════════════════════════════════
# Intégration réelle -- sautée si le binaire n'est pas disponible sur cette
# machine (même patron que test_q65_natif.py pour jt9 : pas de dépendance
# CI, mais vérifiable en local une fois le binaire vendorisé/compilé).
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.skipif(not ssdv.ssdv_disponible(), reason="binaire ssdv non disponible sur cette machine")
def test_integration_reelle_encode_decode_aller_retour(tmp_path):
    # Pillow n'est pas une dépendance du dépôt (vérifié : aucun autre usage) --
    # ce test, déjà protégé par ssdv_disponible(), se saute AUSSI proprement
    # si Pillow est absent plutôt que de la rendre obligatoire pour tous.
    Image = pytest.importorskip('PIL.Image')
    img = Image.new('RGB', (32, 32), color=(255, 0, 0))
    src = tmp_path / 'test.jpg'
    img.save(str(src), 'JPEG')

    bin_path = tmp_path / 'test.bin'
    r_enc = ssdv.encoder(str(src), str(bin_path), 'F4GLD', image_id=1)
    assert r_enc['ok'] is True, r_enc

    dst = tmp_path / 'roundtrip.jpg'
    r_dec = ssdv.decoder(str(bin_path), str(dst))
    assert r_dec['ok'] is True, r_dec
    assert dst.is_file()
