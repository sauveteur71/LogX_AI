# -*- coding: utf-8 -*-
"""Utilitaires génériques : réseau (fetch_url), géodésie locator/distance/azimut, modes numériques."""

import urllib.request
import urllib.error
import math
import datetime
import ssl as _ssl

PORT = 8080
CURRENT_YEAR = datetime.datetime.now().year



# ─── MODES NUMÉRIQUES À FILTRER ──────────────────────────────────────────────
MODES_NUMERIQUES = ['FT8','FT4','JS8','WSPR','PSK','RTTY','DIGI','DATA','MFSK']



# ─── UTILS ───────────────────────────────────────────────────────────────────
# Python 3.13 active VERIFY_X509_STRICT par défaut, ce qui rejette le certificat
# racine des antivirus interceptant le HTTPS (Avast Web Shield : "Basic
# Constraints of CA cert not marked critical") — et donc TOUTES les requêtes
# HTTPS sur ces machines. SSL_CTX garde la vérification complète des certificats
# (racine Avast présente dans le magasin Windows) mais retire seulement le mode
# strict, i.e. le comportement de Python <= 3.12. À passer en context= sur tout
# urlopen HTTPS du projet.
SSL_CTX = _ssl.create_default_context()
if hasattr(_ssl, 'VERIFY_X509_STRICT'):
    SSL_CTX.verify_flags &= ~_ssl.VERIFY_X509_STRICT

# NOTE SÉCURITÉ : il n'y a PLUS de repli en CERT_NONE. L'ancien code retentait
# automatiquement SANS vérification de certificat dès la moindre erreur SSL — un
# attaquant en interception (WiFi public, DNS spoofing) n'avait qu'à présenter un
# certificat invalide pour déclencher lui-même ce repli et servir du contenu
# forgé (spots, données injectées dans l'app qui pilote la radio). SSL_CTX vérifie
# toujours les certificats contre le magasin Windows (racine Avast incluse) ; seul
# le mode STRICT de Python 3.13 est désactivé. Une vraie erreur SSL échoue net.

def fetch_url(url, timeout=10):
    req = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0 (compatible; LogXAI/2.0)',
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=SSL_CTX) as resp:
            charset = resp.headers.get_content_charset() or 'utf-8'
            return resp.read().decode(charset, errors='replace')
    except Exception as e:
        print(f"  [FETCH] {url[:60]}... -> {e}")
        return None

def locator_to_latlon(loc):
    if not loc or len(loc) < 6:
        return None, None
    l = loc.upper()
    try:
        lon = (ord(l[0])-65)*20 - 180 + int(l[2])*2 + (ord(l[4])-65)*(2/24) + 1/24
        lat = (ord(l[1])-65)*10 - 90  + int(l[3])   + (ord(l[5])-65)*(1/24) + 0.5/24
        return lat, lon
    except:
        return None, None

def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    dLat = math.radians(lat2-lat1)
    dLon = math.radians(lon2-lon1)
    a = math.sin(dLat/2)**2 + math.cos(math.radians(lat1))*math.cos(math.radians(lat2))*math.sin(dLon/2)**2
    return int(R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a)))

def bearing(lat1, lon1, lat2, lon2):
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lon2-lon1)
    y = math.sin(dl)*math.cos(phi2)
    x = math.cos(phi1)*math.sin(phi2) - math.sin(phi1)*math.cos(phi2)*math.cos(dl)
    b = math.degrees(math.atan2(y, x))
    return int((b+360) % 360)

def cardinal(deg):
    dirs = ['N','NNE','NE','ENE','E','ESE','SE','SSE','S','SSO','SO','OSO','O','ONO','NO','NNO']
    return dirs[round(deg/22.5) % 16]

def is_digital_mode(text):
    return any(m in text.upper() for m in MODES_NUMERIQUES)
