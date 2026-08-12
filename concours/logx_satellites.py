# -*- coding: utf-8 -*-
"""Satellites : les deux champs sans lesquels un QSO satellite ne vaut RIEN.

CE QUI A ÉTÉ MESURÉ AVANT D'ÉCRIRE UNE LIGNE. LogX savait déjà nommer un
satellite — le champ « satellite actif » de CONFIG — mais son aide le disait
elle-même : « repère informatif uniquement ». Et l'export ADIF n'émettait ni
PROP_MODE ni SAT_NAME. Conséquence : tout QSO satellite exporté vers LoTW était
crédité comme un contact TERRESTRE ordinaire. Pour un opérateur satellite,
c'est l'inverse du but recherché.

CE QU'EXIGE LoTW, vérifié sur sa propre page d'aide :
  • PROP_MODE = SAT  — c'est LUI qui range le QSO dans la catégorie satellite,
    pour le DXCC, le WAS, le VUCC et les mentions associées ;
  • SAT_NAME au format cc-nn, ORTHOGRAPHIÉ EXACTEMENT comme sur la liste
    acceptée. « if you enter the satellite name as AO7 instead of AO-7 the data
    will be rejected during the upload » — le fichier ENTIER est refusé, pas
    seulement la ligne fautive.

D'où le parti pris de ce module : proposer une LISTE plutôt qu'un champ libre.
Une faute de frappe qui ne se révèle qu'au téléversement, des jours après le
QSO, est exactement le genre d'erreur qu'un logiciel doit rendre impossible.
La saisie libre reste permise — la liste ci-dessous ne peut pas être
exhaustive — mais elle est signalée comme non vérifiée.

LA BANDE : c'est la MONTANTE. En liaison croisée, l'ADIF veut dans BAND la
bande sur laquelle ON ÉMET, la descendante allant dans BAND_RX. C'est
contre-intuitif — on entend la descendante, c'est elle qu'on a en tête — et
c'est une source d'erreur classique, d'où le rappel ici.

LA LISTE N'EST PAS L'AUTORITÉ. La référence est celle de TQSL (l'éditeur ADIF
de TrustedQSL) ; celle-ci couvre les satellites durablement actifs et sert à
éviter les fautes de frappe, pas à interdire. Un satellite absent doit pouvoir
être saisi.
"""
import re

PROP_MODE_SAT = 'SAT'

# Format imposé par LoTW : des lettres, un TIRET, un nombre. Le tiret n'est
# PAS optionnel — c'est tout l'objet du contrôle. « AO7 » est la faute
# classique, et elle fait rejeter le fichier entier ; une expression tolérante
# l'aurait déclarée « bien formée » et le garde-fou n'aurait rien gardé.
# Les noms sans chiffre, comme ISS, passent par la liste embarquée : elle est
# consultée AVANT ce contrôle.
_FORMAT = re.compile(r'^[A-Z]{1,4}-\d{1,3}$')

# Satellites durablement actifs, avec l'orthographe EXACTE attendue par LoTW.
# Volontairement conservatrice : mieux vaut une liste courte et juste qu'une
# longue et périmée — un nom obsolète ferait rejeter le téléversement aussi
# sûrement qu'une faute de frappe. À revoir périodiquement contre TQSL.
SATELLITES = [
    ('AO-7',    'AMSAT-OSCAR 7 — le doyen, actif par intermittence'),
    ('AO-27',   'AO-27 — FM, actif par intermittence'),
    ('AO-73',   'FUNcube-1'),
    ('AO-91',   'Fox-1B / RadFxSat'),
    ('AO-92',   'Fox-1D — statut variable, verifier AMSAT avant de compter dessus'),
    ('CAS-4A',  'CAS-4A'),
    ('CAS-4B',  'CAS-4B'),
    ('EO-88',   'FUNcube-5 / Nayif-1'),
    ('FO-29',   'JAS-2 / Fuji-OSCAR 29'),
    ('FO-118',  'CAS-5A'),
    ('IO-117',  'GreenCube — numérique, messagerie'),
    ('ISS',     'Station spatiale internationale (relais FM / APRS)'),
    ('JO-97',   'JY1-Sat'),
    ('PO-101',  'Diwata-2'),
    ('QO-100',  'Es hail 2 — GÉOSTATIONNAIRE : aucun suivi, antenne fixe'),
    ('RS-44',   'DOSAAF-85 — grande empreinte, très utilisé'),
    ('SO-50',   'SaudiSat-1C — FM, le plus populaire des débutants'),
    ('TO-108',  'CAS-6'),
    ('UVSQ-1',  'UVSQ-Sat'),
]

NOMS = [nom for nom, _ in SATELLITES]


def connu(nom):
    """Ce nom figure-t-il dans la liste embarquée ?"""
    return str(nom or '').strip().upper() in NOMS


def normaliser(nom):
    """Met en forme sans jamais RÉÉCRIRE un nom que l'on ne connaît pas.

    On corrige la casse et les espaces — inoffensif — mais on n'invente pas de
    tiret : transformer « AO7 » en « AO-7 » serait deviner, et deviner juste
    aujourd'hui ne garantit pas de deviner juste demain. On préfère signaler.
    """
    return str(nom or '').strip().upper().replace(' ', '')


def valider(nom):
    """Retourne {'ok', 'nom', 'connu', 'avertissement'}.

    Ne REFUSE jamais un nom : la liste embarquée n'est pas l'autorité, et
    empêcher de loguer un satellite récent serait pire que le risque de faute.
    On signale, l'opérateur tranche.
    """
    n = normaliser(nom)
    if not n:
        return {'ok': False, 'nom': '', 'connu': False,
                'avertissement': 'Nom de satellite vide'}
    if connu(n):
        return {'ok': True, 'nom': n, 'connu': True, 'avertissement': ''}
    if not _FORMAT.match(n):
        return {'ok': True, 'nom': n, 'connu': False,
                'avertissement': "Format inhabituel : LoTW attend « cc-nn » "
                                 "(ex. AO-7). Un nom mal orthographie fait "
                                 "rejeter TOUT le fichier au televersement."}
    return {'ok': True, 'nom': n, 'connu': False,
            'avertissement': "Satellite absent de la liste embarquee : verifie "
                             "l'orthographe dans TQSL avant de televerser."}


def champs_adif(qso):
    """Les champs ADIF satellite d'un QSO, ou {} si ce n'en est pas un.

    PROP_MODE n'est posé QUE si un satellite est nommé. Un QSO marqué « SAT »
    sans SAT_NAME serait accepté par l'ADIF mais inutile : LoTW ne saurait pas
    à quel satellite le créditer, et il ne compterait pour aucune mention.
    """
    nom = normaliser((qso or {}).get('sat_name'))
    if not nom:
        return {}
    return {'prop_mode': PROP_MODE_SAT, 'sat_name': nom}
