# -*- coding: utf-8 -*-
"""Tests du pilotage CAT (logx_rig) contre un FAUX rigctld :
un petit serveur TCP qui parle le protocole Hamlib, sans radio.

FakeRigctld garde chaque connexion ouverte pour plusieurs commandes
successives (comme le vrai rigctld) -- reflète le passage de logx_rig.py
à une connexion TCP persistante réutilisée entre commandes (15/08/2026,
au lieu d'une connexion neuve à chaque appel) : le polling bande/mode
ouvrait/fermait 2 connexions par cycle, doublant la latence handshake TCP
pour rien. En cas d'erreur (rigctld redémarré, câble débranché...), la
connexion en cache est abandonnée et UNE reconnexion est tentée avant
d'abandonner pour de bon."""
import os
import socket
import sys
import threading

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_rig as rig


class FakeRigctld:
    """Simule rigctld : F/M règlent, f/m lisent, b enregistre le CW envoyé.
    Garde chaque connexion ouverte pour plusieurs commandes (boucle de
    lecture ligne par ligne), comme le vrai rigctld -- track connections_
    accepted pour vérifier la réutilisation/reconnexion côté client."""

    def __init__(self, drop_connection_after=None):
        self.freq = 14032000
        self.mode = 'CW'
        self.morse_sent = []
        self.connections_accepted = 0
        self.commands_seen = 0
        # Si posé, la N-ième commande TOTALE reçue (toutes connexions
        # confondues) ferme brutalement la connexion en cours SANS répondre
        # -- simule rigctld qui redémarre/le câble qui se débranche.
        self.drop_connection_after = drop_connection_after
        self.srv = socket.socket()
        self.srv.bind(('127.0.0.1', 0))
        self.port = self.srv.getsockname()[1]
        self.srv.listen(4)
        self._stop = False
        threading.Thread(target=self._serve, daemon=True).start()

    def _serve(self):
        while not self._stop:
            try:
                conn, _ = self.srv.accept()
            except OSError:
                return
            self.connections_accepted += 1
            threading.Thread(target=self._handle, args=(conn,), daemon=True).start()

    def _handle(self, conn):
        buf = b''
        with conn:
            while not self._stop:
                try:
                    chunk = conn.recv(256)
                except OSError:
                    return
                if not chunk:
                    return
                buf += chunk
                while b'\n' in buf:
                    line, buf = buf.split(b'\n', 1)
                    line = line.strip().decode()
                    if not line:
                        continue
                    self.commands_seen += 1
                    if self.drop_connection_after == self.commands_seen:
                        return  # ferme la connexion sans répondre
                    self._respond(conn, line)

    def _respond(self, conn, line):
        if line == 'f':
            conn.sendall(f'{self.freq}\n'.encode())
        elif line == 'm':
            conn.sendall(f'{self.mode}\n500\n'.encode())
        elif line.startswith('F '):
            self.freq = int(line.split()[1])
            conn.sendall(b'RPRT 0\n')
        elif line.startswith('M '):
            self.mode = line.split()[1]
            conn.sendall(b'RPRT 0\n')
        elif line.startswith('b '):
            self.morse_sent.append(line[2:])
            conn.sendall(b'RPRT 0\n')
        elif line.startswith('\\stop_morse'):
            conn.sendall(b'RPRT 0\n')
        else:
            conn.sendall(b'RPRT -1\n')

    def close(self):
        self._stop = True
        self.srv.close()


def _oublier_connexions_en_cache():
    """logx_rig garde un cache global {(host,port): socket} entre tests --
    chaque test doit repartir d'un cache vide (un nouveau FakeRigctld = un
    nouveau port, donc une clé différente, mais une connexion PRÉCÉDENTE
    laissée ouverte vers un port maintenant fermé/réutilisé fausserait un
    test suivant qui réutiliserait par hasard le même numéro de port)."""
    for s in list(rig._sockets.values()):
        try:
            s.close()
        except OSError:
            pass
    rig._sockets.clear()


def test_get_state():
    _oublier_connexions_en_cache()
    fake = FakeRigctld()
    try:
        st = rig.get_state('127.0.0.1', fake.port)
        assert st['ok'] and st['freq_hz'] == 14032000
        assert st['freq_khz'] == 14032.0 and st['mode'] == 'CW'
    finally:
        fake.close()


def test_qsy_avec_mode():
    _oublier_connexions_en_cache()
    fake = FakeRigctld()
    try:
        r = rig.set_freq('127.0.0.1', fake.port, 3512000, mode='LSB')
        assert r['ok']
        assert fake.freq == 3512000 and fake.mode == 'LSB'
    finally:
        fake.close()


def test_send_morse():
    _oublier_connexions_en_cache()
    fake = FakeRigctld()
    try:
        r = rig.send_morse('127.0.0.1', fake.port, 'TU 5NN F6KQJ')
        assert r['ok']
        assert fake.morse_sent == ['TU 5NN F6KQJ']
    finally:
        fake.close()


def test_radio_injoignable_erreur_propre():
    _oublier_connexions_en_cache()
    r = rig.get_state('127.0.0.1', 1)      # port fermé
    assert not r['ok'] and 'injoignable' in r['error']
    r = rig.set_freq('127.0.0.1', 1, 14000000)
    assert not r['ok']


def test_settings_par_defaut_desactive():
    s = rig.rig_settings({})
    assert s['enabled'] is False           # jamais actif sans opt-in explicite
    s2 = rig.rig_settings({'rig_enabled': True, 'rig_host': '192.168.1.50',
                           'rig_port': '4532'})
    assert s2 == {'enabled': True, 'host': '192.168.1.50', 'port': 4532}


def test_connexion_reutilisee_entre_plusieurs_commandes():
    """get_state() (2 commandes : f, m) puis set_freq() (1-2 commandes)
    sur le MÊME (host, port) ne doivent ouvrir qu'UNE seule connexion TCP
    côté serveur -- pas une par commande."""
    _oublier_connexions_en_cache()
    fake = FakeRigctld()
    try:
        assert rig.get_state('127.0.0.1', fake.port)['ok']
        assert rig.set_freq('127.0.0.1', fake.port, 7032000)['ok']
        assert rig.get_state('127.0.0.1', fake.port)['ok']
        assert fake.connections_accepted == 1
        assert fake.commands_seen >= 5   # f, m, F, f, m
    finally:
        fake.close()


def test_reconnexion_automatique_apres_perte_de_connexion():
    """La 2e commande ('m', après 'f' pour get_state()) fait fermer la
    connexion sans répondre côté serveur (rigctld redémarré / câble
    débranché) -- la reconnexion + retentative UNIQUE côté _command() rend
    la coupure TRANSPARENTE pour l'appelant : get_state() réussit quand
    même, dans le MÊME appel, sans que get_state() lui-même n'ait besoin de
    savoir qu'une connexion a été perdue au milieu."""
    _oublier_connexions_en_cache()
    fake = FakeRigctld(drop_connection_after=2)
    try:
        st = rig.get_state('127.0.0.1', fake.port)
        assert st['ok'] and st['freq_hz'] == 14032000 and st['mode'] == 'CW'
        # 1re connexion coupée après la commande #2 ('m'), 2e ouverte par la
        # retentative automatique de _command() pour renvoyer cette même 'm'.
        assert fake.connections_accepted == 2
    finally:
        fake.close()


def test_connexion_neuve_apres_radio_injoignable_puis_de_nouveau_dispo():
    """Un cache de connexion vers un port maintenant fermé ne doit jamais
    faire échouer indéfiniment les appels suivants vers une radio de
    nouveau disponible sur un port différent."""
    _oublier_connexions_en_cache()
    r = rig.get_state('127.0.0.1', 1)  # port fermé -- pas de connexion en cache créée
    assert not r['ok']
    fake = FakeRigctld()
    try:
        st = rig.get_state('127.0.0.1', fake.port)
        assert st['ok']
    finally:
        fake.close()
