# -*- coding: utf-8 -*-
"""Galerie SSDV -- suite du socle Phase 1/2 (logx_ssdv.py assembleur pur,
logx_ssdv_reception.py client KISS live). Cadrage 12/09/2026, décisions
F4GLD :

1. **Multi-flux** : un assemblage PAR (indicatif, image_id) -- le lien
   KISS/Direwolf capte tout ce qui passe sur le port, plusieurs stations
   peuvent émettre des images en même temps. logx_ssdv.nouvel_assemblage()
   ne gère qu'UN SEUL flux (il lève si un paquet d'une autre image_id
   arrive en cours d'assemblage) -- ce module ajoute le registre multi-clés
   par-dessus, sans toucher à l'assembleur pur.
2. **Persistance** : dossier local, AUCUNE purge automatique (F4GLD :
   « tout conservé »).
3. **Nommage** : le NOM DE FICHIER est la seule source de vérité (pas de
   manifeste séparé à tenir synchronisé) -- <indicatif>_<image_id>_<epoch>.jpg,
   parsable par lister_images() sans état additionnel.

Dossier SANS point de tête (contrairement à .operator_goals.json etc.) --
choix délibéré : Handler._interdit() (logx_http.py) bloque tout segment de
chemin commençant par '.' pour empêcher qu'un secret ne soit servi par
erreur. Les images SSDV n'ont rien de secret et doivent au contraire être
servies telles quelles par le serveur de fichiers statique existant
(GET /ssdv_images/<fichier>) -- pas de endpoint de service dédié à
maintenir en parallèle. Suit le précédent concours/voice_messages/."""
import os
import re
import time

import logx_ssdv as ssdv

DOSSIER_DEFAUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ssdv_images')

# Miroir exact de nom_fichier() ci-dessous -- un indicatif SSDV valide ne
# contient que '-'/chiffres/majuscules (domaine fermé de decoder_indicatif_
# base40, voir logx_ssdv.py), jamais de séparateur '_' ni de caractère
# permettant une évasion de chemin.
_RE_NOM = re.compile(r'^(?P<indicatif>[A-Z0-9-]{1,10})_(?P<image_id>\d{1,3})_(?P<ts>\d{1,20})\.jpg$')


def nouveau_registre():
    return {}   # (indicatif, image_id) -> assemblage (logx_ssdv.nouvel_assemblage())


# Registre partagé du client KISS live (un seul thread de fond y écrit,
# voir logx_http._ssdv_paquet_recu) -- même patron que
# logx_ssdv_reception.status : état de process, pas de verrou nécessaire
# puisqu'un seul thread le mute (contrairement à `status`, jamais lu
# concurremment par le thread HTTP -- lister_images() relit le DISQUE, pas
# ce dict).
registre = nouveau_registre()


def recevoir_paquet(registre, paquet_brut):
    """Route un paquet SSDV brut (256 octets, déjà filtré/validé par
    logx_ssdv_reception._traiter_trame_kiss) vers l'assemblage (indicatif,
    image_id) correspondant, créé au besoin. Renvoie (assemblage,
    vient_de_se_completer) -- le 2e élément est True UNE SEULE FOIS, au
    paquet qui fait basculer l'assemblage à l'état complet (un paquet EOI
    dupliqué ou reçu deux fois ne redéclenche pas un second enregistrement)."""
    entete = ssdv.parser_entete(paquet_brut)
    cle = (entete['indicatif'], entete['image_id'])
    assemblage = registre.get(cle)
    etait_complet = assemblage is not None and ssdv.est_complet(assemblage)
    if assemblage is None:
        assemblage = ssdv.nouvel_assemblage()
        registre[cle] = assemblage
    ssdv.ajouter_paquet(assemblage, entete, paquet_brut)
    vient_de_se_completer = (not etait_complet) and ssdv.est_complet(assemblage)
    return assemblage, vient_de_se_completer


def nom_fichier(indicatif, image_id, ts=None):
    ts = int(ts if ts is not None else time.time())
    ind = (indicatif or '').strip() or 'INCONNU'
    return '%s_%d_%d.jpg' % (ind, image_id, ts)


def sauver_image(registre, cle, dossier=None, cfg=None, ts=None, timeout=30):
    """Assemble et écrit sur disque l'image JPEG de l'assemblage `cle`
    (indicatif, image_id), puis retire TOUJOURS l'assemblage du registre --
    en succès comme en échec (ex. binaire ssdv absent) : un paquet suivant
    de la même image_id doit repartir d'un assemblage neuf plutôt que de
    raccrocher à un état déjà consommé."""
    dossier = dossier or DOSSIER_DEFAUT
    assemblage = registre.pop(cle, None)
    if assemblage is None:
        return {'ok': False, 'error': 'assemblage introuvable pour ' + repr(cle)}
    os.makedirs(dossier, exist_ok=True)
    nom = nom_fichier(cle[0], cle[1], ts=ts)
    chemin = os.path.join(dossier, nom)
    resultat = dict(ssdv.assembler_image(assemblage, chemin, cfg=cfg, timeout=timeout))
    resultat['fichier'] = nom if resultat.get('ok') else None
    return resultat


def _depuis_nom(nom):
    m = _RE_NOM.match(nom)
    if not m:
        return None
    return {
        'fichier': nom,
        'indicatif': m.group('indicatif'),
        'image_id': int(m.group('image_id')),
        'recu_le': int(m.group('ts')),
    }


def lister_images(dossier=None):
    """Lecture seule du dossier -- aucun état en mémoire à tenir cohérent.
    Ignore silencieusement tout fichier qui ne correspond pas au motif
    (ex. .gitkeep, fichier système) plutôt que de lever. Tri du plus
    récent au plus ancien."""
    dossier = dossier or DOSSIER_DEFAUT
    if not os.path.isdir(dossier):
        return []
    items = []
    for nom in os.listdir(dossier):
        info = _depuis_nom(nom)
        if info is not None:
            items.append(info)
    items.sort(key=lambda i: i['recu_le'], reverse=True)
    return items
