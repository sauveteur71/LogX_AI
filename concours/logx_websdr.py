# -*- coding: utf-8 -*-
"""Annuaire de récepteurs WebSDR — étendre son écoute au-delà de sa station.

Un WebSDR/KiwiSDR est un récepteur radio piloté à distance via un navigateur :
n'importe qui peut l'écouter et le régler, en simultané avec d'autres
auditeurs. Utile pour se faire écouter depuis une autre région/pays (contrôle
de propagation), écouter une bande fermée depuis chez soi, ou repérer une
station avant de tenter le contact.

Liste STATIQUE, volontairement courte et vérifiée à la main (chaque entrée a
été confirmée active au moment de l'ajout) plutôt qu'un gros annuaire agrégé
automatiquement : ces récepteurs sont opérés bénévolement par d'autres
radioamateurs ou associations, sur des connexions personnelles — la
disponibilité n'est PAS garantie 24/7 (contrairement aux gros annuaires
websdr.org/kiwisdr.com/receiverbook, plus complets mais pas maintenus par ce
logiciel). Facile à compléter : ajoute une entrée au tableau ci-dessous.
"""

WEBSDR_DIRECTORY = [
    {
        'name': 'SHTSF — Société Havraise de Télégraphie Sans Fil',
        'city': 'Le Havre', 'country': 'France', 'continent': 'Europe',
        'url': 'http://kiwisdr.shtsf.fr/',
        'bands': 'HF complet (10 kHz – 30 MHz)', 'kind': 'KiwiSDR',
    },
    {
        'name': 'F4KJI — Batima Electronic',
        'city': '', 'country': 'France', 'continent': 'Europe',
        'url': 'http://www.f4kji.fr:8901/',
        'bands': 'LF, 160m, 60m, 6m', 'kind': 'WebSDR',
    },
    {
        'name': 'WebSDR University of Twente',
        'city': 'Enschede', 'country': 'Pays-Bas', 'continent': 'Europe',
        'url': 'http://websdr.ewi.utwente.nl:8901/',
        'bands': 'HF large bande (0 – 30 MHz, plusieurs récepteurs simultanés)',
        'kind': 'WebSDR',
        'note': "Le tout premier WebSDR au monde (2008) — référence du projet, très stable.",
    },
    {
        'name': 'Northern Utah WebSDR',
        'city': 'Corinne, Utah', 'country': 'États-Unis', 'continent': 'Amérique du Nord',
        'url': 'http://www.sdrutah.org',
        'bands': 'HF + VHF/UHF (2200 m à 2 m), plusieurs récepteurs', 'kind': 'WebSDR',
    },
    {
        'name': 'MWRS — Manly-Warringah Radio Society',
        'city': 'Sydney (NSW)', 'country': 'Australie', 'continent': 'Océanie',
        'url': 'http://websdr.mwrs.org.au:8073',
        'bands': 'HF (antenne boucle magnétique)', 'kind': 'KiwiSDR',
    },
    {
        'name': 'ZR6AIC WebSDR',
        'city': '', 'country': 'Afrique du Sud', 'continent': 'Afrique',
        'url': 'http://zr6aic.giga.co.za:8902/',
        'bands': 'HF + satellite 70cm', 'kind': 'WebSDR',
    },
    {
        'name': 'APPR WebSDR',
        'city': '', 'country': 'Brésil', 'continent': 'Amérique du Sud',
        'url': 'http://appr.org.br:8901/',
        'bands': 'HF', 'kind': 'WebSDR',
        'note': 'Association radioamateur locale.',
    },
]


def list_websdr():
    """Copie de l'annuaire (jamais la liste originale — appelant ne doit pas
    pouvoir la muter par effet de bord)."""
    return [dict(e) for e in WEBSDR_DIRECTORY]
