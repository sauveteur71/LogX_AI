# -*- coding: utf-8 -*-
"""Garde de réentrance de syncOfflineQueue() dans logx_mobile.html.

pollWall() (setInterval 5 s) appelle syncOfflineQueue() à chaque réseau OK.
La fonction lit la file au début (loadOfflineQueue) et ne la ré-écrit qu'à la
fin (saveOfflineQueue), en awaitant un POST /log/add par QSO entre les deux.
Si un envoi dépasse 5 s (WiFi de terrain instable), une 2e passe relit la MÊME
file et re-poste les mêmes QSO avec force:true -> DOUBLONS dans le carnet.

Le correctif pose un verrou de réentrance : une 2e entrée pendant qu'une passe
est en cours doit retourner IMMÉDIATEMENT, sans relire la file (loadOfflineQueue
n'est PAS rappelée). Test comportemental sur la VRAIE fonction extraite de la
page : verrou posé -> loadOfflineQueue non appelée ; verrou levé -> appelée.
"""
import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML = open(os.path.join(BASE, 'logx_mobile.html'), encoding='utf-8').read()


def _extraire_fn(src, nom):
    i = src.find('async function ' + nom)   # préserver le mot-clé async
    if i == -1:
        i = src.index('function ' + nom)
    j = src.index('{', i)
    prof, k = 0, j
    while k < len(src):
        if src[k] == '{':
            prof += 1
        elif src[k] == '}':
            prof -= 1
            if prof == 0:
                return src[i:k + 1]
        k += 1
    raise AssertionError('fonction %s introuvable' % nom)


def _ctx():
    from py_mini_racer import py_mini_racer as m
    c = m.MiniRacer()
    # Nom du flag repéré dans le correctif (déclaré au scope module). On le
    # fournit comme global var pour qu'il persiste entre les eval du test.
    c.eval('var _syncingQueue = false;')
    # Stub instrumenté : compte les appels, renvoie une file vide (la fonction
    # s'arrête alors juste après, sans toucher fetch — suffisant pour observer
    # si la file a été RELUE).
    c.eval('var _loadCalls = 0; function loadOfflineQueue(){ _loadCalls++; return []; }')
    c.eval(_extraire_fn(HTML, 'syncOfflineQueue'))
    return c


def test_verrou_pose_bloque_la_relecture_de_la_file():
    c = _ctx()
    c.eval('_syncingQueue = true;')          # une passe est déjà en cours
    c.eval('syncOfflineQueue();')
    assert c.eval('_loadCalls') == 0, "une 2e passe ne doit PAS relire la file quand une passe est en cours"


def test_verrou_leve_laisse_passer():
    c = _ctx()
    c.eval('_syncingQueue = false;')
    c.eval('syncOfflineQueue();')
    assert c.eval('_loadCalls') == 1, "sans passe en cours, la file doit être lue normalement"
