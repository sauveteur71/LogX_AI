# -*- coding: utf-8 -*-
"""Keyer CW série DTR/RTS — couche matérielle (Phase 3B).

La boucle _executer() est testée avec un FAUX port (qui trace les bascules de
ligne) et un sleep injecté : on vérifie l'ORDRE des bascules, l'arrêt qui coupe
et relâche la clé, la sélection DTR vs RTS, et le fire-and-forget de envoyer().
Aucune émission réelle (pas de vrai port série).
"""
import os
import sys
import threading

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_cw_serial as cw


class FauxPort:
    """Trace chaque écriture de dtr/rts sous forme (ligne, valeur)."""
    def __init__(self):
        object.__setattr__(self, 'trace', [])
        object.__setattr__(self, 'dtr', False)
        object.__setattr__(self, 'rts', False)
        object.__setattr__(self, 'ferme', False)

    def __setattr__(self, k, v):
        object.__setattr__(self, k, v)
        if k in ('dtr', 'rts'):
            self.trace.append((k, v))

    def close(self):
        object.__setattr__(self, 'ferme', True)


def setup_function(_):
    cw._fermer_locked()
    cw._stop.clear()


def test_executer_toggle_dtr_dans_l_ordre_et_releve_la_cle():
    port = FauxPort()
    seq = cw.keying_sequence('A', 20)                 # . -
    cw._executer(port, 'DTR', seq, threading.Event(), lambda s: False)
    vals = [v for (ln, v) in port.trace if ln == 'dtr']
    assert vals == [True, False, True, False]         # dit, gap, dah, KEY UP final
    assert port.dtr is False


def test_arret_pendant_l_attente_coupe_et_releve():
    port = FauxPort()
    stop = threading.Event()

    def sleep_qui_arrete(_):
        stop.set()
        return True                                    # attente interrompue

    cw._executer(port, 'DTR', cw.keying_sequence('CQ', 20), stop, sleep_qui_arrete)
    assert port.dtr is False                           # clé relâchée malgré l'arrêt
    downs = [v for (ln, v) in port.trace if ln == 'dtr' and v is True]
    assert len(downs) == 1                             # une seule mise sous tension avant l'arrêt


def test_ligne_rts_ne_touche_pas_dtr():
    port = FauxPort()
    cw._executer(port, 'RTS', cw.keying_sequence('E', 20), threading.Event(), lambda s: False)
    assert any(ln == 'rts' and v is True for (ln, v) in port.trace)
    assert not any(ln == 'dtr' and v is True for (ln, v) in port.trace)


def test_parametres_defauts_et_bornage():
    p = cw.parametres({'cw_serial_enabled': '1', 'cw_serial_port': 'COM3',
                       'cw_serial_line': 'rts', 'cw_serial_wpm': 200})
    assert p['enabled'] and p['line'] == 'RTS' and p['wpm'] == 99   # WPM borné
    p2 = cw.parametres({})
    assert not p2['enabled'] and p2['line'] == 'DTR' and p2['wpm'] == 22
    assert cw.parametres({'cw_serial_line': 'xyz'})['line'] == 'DTR'  # ligne invalide -> DTR


def test_envoyer_manipule_en_fond_puis_releve(monkeypatch):
    port = FauxPort()
    monkeypatch.setattr(cw, '_ouvrir_port', lambda nom: port)
    cfg = {'cw_serial_enabled': '1', 'cw_serial_port': 'COM9',
           'cw_serial_line': 'DTR', 'cw_serial_wpm': 40}
    res = cw.envoyer(cfg, 'E')
    assert res['ok'] and res['wpm'] == 40
    if cw._thread:
        cw._thread.join(2.0)
    assert any(ln == 'dtr' and v is True for (ln, v) in port.trace)   # a bien manipulé
    assert port.dtr is False                                          # KEY UP à la fin


def test_envoyer_desactive_ou_sans_port_refuse():
    assert cw.envoyer({'cw_serial_enabled': ''}, 'CQ')['ok'] is False
    assert cw.envoyer({'cw_serial_enabled': '1', 'cw_serial_port': ''}, 'CQ')['ok'] is False


def test_http_route_le_backend_serie_entre_winkeyer_et_cat():
    src = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            'logx_http.py'), encoding='utf-8').read()
    i_wk = src.index("if wk.parametres(cfg_snap)['enabled']")
    i_ser = src.index("if cws.parametres(cfg_snap)['enabled']")
    i_cat = src.index("import logx_cat as cat", i_ser)
    assert i_wk < i_ser < i_cat            # série : APRÈS WinKeyer, AVANT CAT
    assert "cws.envoyer(cfg_snap" in src and "cws.arreter(cfg_snap)" in src


def test_arreter_coupe_une_manip_en_cours(monkeypatch):
    port = FauxPort()
    monkeypatch.setattr(cw, '_ouvrir_port', lambda nom: port)
    # texte long à 5 WPM -> émission longue, on l'arrête tout de suite
    cfg = {'cw_serial_enabled': '1', 'cw_serial_port': 'COM9', 'cw_serial_wpm': 5}
    cw.envoyer(cfg, 'CQ CQ CQ DE F4GLD')
    res = cw.arreter(cfg)
    assert res['ok']
    if cw._thread:
        cw._thread.join(2.0)
    assert port.dtr is False                                          # clé relâchée après arrêt
