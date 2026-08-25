---
name: radio-video-analysis
description: Analyse des vidéos radioamateur, transceivers, CAT, FT8, antennes, logiciels et procédures techniques.
disable-model-invocation: true
---

# Mission

Analyse les vidéos radioamateur avec leur transcription et leurs images horodatées.

Ce skill est le COMPLÉMENT métier du skill `watch` (bradautomates/claude-video),
qui fournit `/watch` : téléchargement, extraction d'images horodatées et
transcription. `watch` fait « voir et entendre » la vidéo ; ce skill dit QUOI en
extraire et COMMENT le restituer pour LogX AI. Enchaînement type :
`/watch <URL>` puis appliquer la grille ci-dessous à ce que `watch` a ramené.

# Informations à extraire

- Marque et modèle de la radio.
- Version du firmware si visible.
- Logiciel utilisé.
- Système d'exploitation.
- Connexion CAT : USB, série, réseau ou adaptateur.
- Numéro de port COM ou périphérique, sans conserver les données personnelles.
- Débit, parité, bits, stop bits et handshaking.
- Adresse CI-V si visible.
- Mode radio : USB, USB-DATA, DATA-U, DATA-L ou autre.
- Fréquence et bande.
- Configuration split.
- Méthode PTT : CAT, RTS, DTR ou VOX.
- Entrée et sortie audio.
- Fréquence d'échantillonnage et résolution audio.
- Paramètres FT8, FT4, WSJT-X ou autre logiciel.
- Câblage et connecteurs.
- Menus radio modifiés.
- Erreurs ou avertissements observés.
- Timestamps précis de chaque information.

# Règles

- Ne jamais déduire un réglage qui n'est pas visible ou dit clairement.
- Marquer chaque élément comme CONFIRMÉ, PROBABLE ou INCONNU.
- Ne jamais présenter une commande CAT comme universelle.
- Vérifier le modèle exact de la radio.
- Comparer les réglages trouvés avec le manuel officiel du modèle.
- Ne jamais déclencher PTT ou émission RF.
- Ne jamais copier de clé API, mot de passe, certificat ou jeton.
- Signaler toute contradiction entre l'image, la transcription et la documentation officielle.

# Format de sortie

## Identification
## Matériel
## Câblage
## Réglages CAT
## Réglages audio
## Réglages FT8
## Procédure étape par étape
## Erreurs observées
## Tableau des timestamps
## Points à vérifier dans le manuel officiel
## Données confirmées / probables / inconnues
