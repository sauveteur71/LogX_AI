# -*- coding: utf-8 -*-
"""Tests de logx_ssdv_galerie -- registre multi-flux (indicatif, image_id) +
persistance disque des images SSDV complètes (cadrage 12/09/2026, décisions
F4GLD : un assemblage par flux, aucune purge automatique, nom de fichier
comme seule source de vérité pour la liste)."""
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE not in sys.path:
    sys.path.insert(0, BASE)

import logx_ssdv as ssdv               # noqa: E402
import logx_ssdv_galerie as galerie    # noqa: E402
from test_ssdv_reception import _paquet_ssdv   # noqa: E402


def _entete(paquet):
    return ssdv.parser_entete(paquet)


def test_recevoir_paquet_cree_un_assemblage_pour_un_nouveau_flux():
    reg = galerie.nouveau_registre()
    paquet = _paquet_ssdv(packet_id=0, indicatif='F4GLD', image_id=1)
    assemblage, complet = galerie.recevoir_paquet(reg, paquet)
    assert complet is False
    assert reg[('F4GLD', 1)] is assemblage
    assert assemblage['indicatif'] == 'F4GLD'
    assert assemblage['image_id'] == 1


def test_recevoir_paquet_suit_deux_flux_independants_sans_lever():
    # Régression du bug que ce module existe pour éviter : logx_ssdv.
    # ajouter_paquet() lève si un paquet d'une AUTRE image_id arrive
    # pendant l'assemblage en cours -- le registre doit router chaque
    # paquet vers SON assemblage, jamais faire cohabiter deux flux dans
    # un seul assemblage logx_ssdv.
    reg = galerie.nouveau_registre()
    p1 = _paquet_ssdv(packet_id=0, indicatif='F4GLD', image_id=1)
    p2 = _paquet_ssdv(packet_id=0, indicatif='F5ABC', image_id=7)
    galerie.recevoir_paquet(reg, p1)
    galerie.recevoir_paquet(reg, p2)   # ne doit pas lever
    assert set(reg.keys()) == {('F4GLD', 1), ('F5ABC', 7)}
    assert reg[('F4GLD', 1)]['paquets'].keys() == {0}
    assert reg[('F5ABC', 7)]['paquets'].keys() == {0}


def test_vient_de_se_completer_vrai_une_seule_fois():
    reg = galerie.nouveau_registre()
    # image à un seul paquet : celui-ci porte déjà le fanion EOI.
    paquet = _paquet_ssdv(packet_id=0, indicatif='F4GLD', image_id=1, eoi=True)
    _, complet1 = galerie.recevoir_paquet(reg, paquet)
    assert complet1 is True
    # le même paquet (EOI dupliqué, ex. retransmission) ne doit PAS
    # redéclencher un second "vient de se compléter".
    _, complet2 = galerie.recevoir_paquet(reg, paquet)
    assert complet2 is False


def test_vient_de_se_completer_faux_tant_quil_manque_un_paquet():
    reg = galerie.nouveau_registre()
    p0 = _paquet_ssdv(packet_id=0, indicatif='F4GLD', image_id=1)
    p2 = _paquet_ssdv(packet_id=2, indicatif='F4GLD', image_id=1, eoi=True)
    _, c0 = galerie.recevoir_paquet(reg, p0)
    _, c2 = galerie.recevoir_paquet(reg, p2)
    assert c0 is False
    assert c2 is False   # packet_id=1 manquant malgré l'EOI reçu


def test_nom_fichier_format_et_ts_par_defaut():
    nom = galerie.nom_fichier('F4GLD', 3, ts=1700000000)
    assert nom == 'F4GLD_3_1700000000.jpg'
    # ts par défaut : un entier plausible (epoch actuel), pas planté/absent.
    nom_auto = galerie.nom_fichier('F4GLD', 3)
    assert nom_auto.startswith('F4GLD_3_') and nom_auto.endswith('.jpg')


def test_nom_fichier_indicatif_vide_devient_inconnu():
    assert galerie.nom_fichier('', 0, ts=1) == 'INCONNU_0_1.jpg'


def test_sauver_image_appelle_assembler_image_avec_le_bon_chemin(monkeypatch, tmp_path):
    reg = galerie.nouveau_registre()
    paquet = _paquet_ssdv(packet_id=0, indicatif='F4GLD', image_id=1, eoi=True)
    galerie.recevoir_paquet(reg, paquet)

    appels = []

    def _faux_assembler(assemblage, chemin_sortie_jpeg, cfg=None, timeout=30):
        appels.append((assemblage, chemin_sortie_jpeg, cfg, timeout))
        return {'ok': True}

    monkeypatch.setattr(galerie.ssdv, 'assembler_image', _faux_assembler)
    resultat = galerie.sauver_image(reg, ('F4GLD', 1), dossier=str(tmp_path),
                                     cfg={'x': 1}, ts=42, timeout=5)
    assert resultat['ok'] is True
    assert resultat['fichier'] == 'F4GLD_1_42.jpg'
    assert len(appels) == 1
    _, chemin, cfg, timeout = appels[0]
    assert chemin == os.path.join(str(tmp_path), 'F4GLD_1_42.jpg')
    assert cfg == {'x': 1}
    assert timeout == 5
    # l'assemblage est retiré du registre une fois traité (succès ou pas).
    assert ('F4GLD', 1) not in reg


def test_sauver_image_retire_lassemblage_meme_en_echec(monkeypatch, tmp_path):
    reg = galerie.nouveau_registre()
    paquet = _paquet_ssdv(packet_id=0, indicatif='F4GLD', image_id=1, eoi=True)
    galerie.recevoir_paquet(reg, paquet)
    monkeypatch.setattr(galerie.ssdv, 'assembler_image',
                         lambda *a, **k: {'ok': False, 'error': 'binaire ssdv introuvable'})
    resultat = galerie.sauver_image(reg, ('F4GLD', 1), dossier=str(tmp_path), ts=1)
    assert resultat['ok'] is False
    assert resultat['fichier'] is None
    assert ('F4GLD', 1) not in reg


def test_sauver_image_assemblage_absent_renvoie_erreur_sans_lever(tmp_path):
    reg = galerie.nouveau_registre()
    resultat = galerie.sauver_image(reg, ('INEXISTANT', 9), dossier=str(tmp_path))
    assert resultat['ok'] is False
    assert 'error' in resultat


def test_lister_images_dossier_absent_renvoie_liste_vide(tmp_path):
    assert galerie.lister_images(dossier=str(tmp_path / 'nexiste_pas')) == []


def test_lister_images_ignore_fichiers_non_conformes(tmp_path):
    (tmp_path / '.gitkeep').write_bytes(b'')
    (tmp_path / 'notes.txt').write_bytes(b'')
    (tmp_path / 'F4GLD_1_100.jpg').write_bytes(b'\xff\xd8\xff')
    images = galerie.lister_images(dossier=str(tmp_path))
    assert len(images) == 1
    assert images[0]['fichier'] == 'F4GLD_1_100.jpg'
    assert images[0]['indicatif'] == 'F4GLD'
    assert images[0]['image_id'] == 1
    assert images[0]['recu_le'] == 100


def test_lister_images_trie_plus_recent_dabord(tmp_path):
    (tmp_path / 'F4GLD_1_100.jpg').write_bytes(b'')
    (tmp_path / 'F5ABC_2_300.jpg').write_bytes(b'')
    (tmp_path / 'F6XYZ_3_200.jpg').write_bytes(b'')
    images = galerie.lister_images(dossier=str(tmp_path))
    assert [i['fichier'] for i in images] == [
        'F5ABC_2_300.jpg', 'F6XYZ_3_200.jpg', 'F4GLD_1_100.jpg']


def test_nom_fichier_round_trip_avec_lister_images(tmp_path):
    # Le générateur et le parseur doivent rester en phase -- toute
    # divergence orphelinerait silencieusement un fichier bien écrit.
    nom = galerie.nom_fichier('F4GLD', 12, ts=555)
    (tmp_path / nom).write_bytes(b'')
    images = galerie.lister_images(dossier=str(tmp_path))
    assert len(images) == 1
    assert images[0] == {'fichier': nom, 'indicatif': 'F4GLD', 'image_id': 12, 'recu_le': 555}
