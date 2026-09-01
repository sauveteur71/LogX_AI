import os, sys
CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CONCOURS not in sys.path:
    sys.path.insert(0, CONCOURS)
FIXTURES = os.path.join(os.path.dirname(__file__), 'fixtures')

import pytest  # noqa: E402
import threading  # noqa: E402
import time  # noqa: E402
import wave  # noqa: E402
import logx_q65_natif as q65n  # noqa: E402


def _stdout_ref():
    with open(os.path.join(FIXTURES, 'jt9_stdout_q65_60A.txt'), encoding='utf-8') as f:
        return f.read()


def test_parse_stdout_trois_stations():
    d = q65n.parse_jt9_stdout(_stdout_ref(), freq_mhz=50.313, band='6m', now=1000.0)
    # 3 décodages, la ligne <DecodeFinished> est ignorée
    assert len(d) == 3, d
    # Assertion sur le CONTENU décodé, pas une présence de chaîne
    calls = [x['call'] for x in d]
    assert calls == ['N8JX', 'W1VD', 'VE1JF'], calls
    premier = d[0]
    assert premier['snr'] == -24
    assert abs(premier['dt'] - 2.8) < 0.01
    assert premier['delta_hz'] == 697
    assert premier['mode'] == 'Q65'
    assert premier['message'] == 'W7GJ N8JX EN73'
    assert premier['freq_mhz'] == 50.313
    assert premier['band'] == '6m'
    assert premier['last_seen'] == 1000.0


def test_parse_stdout_vide():
    assert q65n.parse_jt9_stdout('<DecodeFinished>   0   0      0\n') == []


def _jt9_dispo():
    """Détecte si jt9 est trouvable (config/binaire embarqué/PATH), sans
    planter le collecte de tests si WSJT-X n'est pas installé."""
    try:
        return q65n.resoudre_jt9() is not None
    except FileNotFoundError:
        return False


@pytest.mark.skipif(not _jt9_dispo(), reason="jt9 non installe sur cette machine")
def test_decoder_wav_echantillon_eme():
    wav = os.path.join(FIXTURES, 'q65_60A_eme_6m.wav')
    d = q65n.decoder_wav(wav, submode='A', tr_period=60, freq_mhz=50.313, band='6m')
    calls = sorted(x['call'] for x in d)
    # Le decodeur de reference sort ces 3 stations EME (mesure au spike)
    assert calls == ['N8JX', 'VE1JF', 'W1VD'], calls
    parN8JX = next(x for x in d if x['call'] == 'N8JX')
    assert parN8JX['snr'] <= -20         # near-threshold EME
    assert parN8JX['mode'] == 'Q65'


@pytest.mark.skipif(not _jt9_dispo(), reason="jt9 non installe sur cette machine")
def test_decoder_wav_ne_laisse_pas_de_dossier_temp():
    """Sans data_path fourni, decoder_wav cree un dossier temporaire interne
    et DOIT le supprimer (sinon fuite disque : un appel/60 s en Tache 5).
    Assertion sur le comportement reel : on compte les dossiers logx_q65_*
    du tmpdir systeme avant/apres un appel."""
    import glob
    import tempfile
    motif = os.path.join(tempfile.gettempdir(), 'logx_q65_*')
    avant = set(glob.glob(motif))
    wav = os.path.join(FIXTURES, 'q65_60A_eme_6m.wav')
    q65n.decoder_wav(wav, submode='A', tr_period=60, freq_mhz=50.313, band='6m')
    apres = set(glob.glob(motif))
    assert apres == avant, sorted(apres - avant)


def test_bornes_fenetre_alignee_minute():
    """Fenêtre T/R de 60 s alignée sur la minute UTC pleine : début et fin
    sont des multiples de 60, et `now` doit se situer strictement à l'intérieur
    de la fenêtre (deb <= now < fin)."""
    # 12:34:37.5 UTC → fenêtre [12:34:00, 12:35:00)
    now = 1_000_000_000 + 37.5  # peu importe l'instant exact, juste un offset
    deb, fin = q65n.bornes_fenetre(now, tr_period=60)
    assert deb <= now < fin, f"deb={deb}, now={now}, fin={fin}"
    assert fin - deb == 60
    assert int(deb) % 60 == 0, f"deb={deb} non aligné sur 60"
    assert int(fin) % 60 == 0, f"fin={fin} non aligné sur 60"


def test_module_importe_sans_sounddevice(monkeypatch):
    """sounddevice est un import PARESSEUX (opt-in, natif) : le module doit
    rester importable même si le paquet/wheel PortAudio est absent ou
    échoue à charger sur la plateforme."""
    import importlib
    import builtins
    reel = builtins.__import__

    def faux(nom, *a, **k):
        if nom == 'sounddevice':
            raise ImportError('simulé')
        return reel(nom, *a, **k)

    monkeypatch.setattr(builtins, '__import__', faux)
    importlib.reload(q65n)              # ne doit PAS lever
    assert hasattr(q65n, 'parse_jt9_stdout')
    importlib.reload(q65n)              # rétablir l'état normal (sans monkeypatch)


def test_traiter_fenetre_alimente_le_cache(monkeypatch, tmp_path):
    q65n.arreter_moteur()  # état propre
    # NOTE (défaut du brief corrigé) : le brief original utilisait un
    # last_seen littéral 5000.0 (epoch ~1970), incompatible avec
    # decodes_natifs() qui compare à time.time() RÉEL (~1.79 milliard en
    # 2026) — l'entrée aurait été jugée "trop vieille" pour n'importe quel
    # max_age raisonnable, y compris avec l'implémentation de référence du
    # brief lui-même (témoin rouge/vert l'a confirmé). Ancré sur time.time()
    # courant pour rester un test de RECENCE valide, déterministe et non
    # flaky (la marge de 10 000 s absorbe toute lenteur d'exécution).
    maintenant = time.time()
    faux = [{'call': 'DL7APV', 'grid': 'JO62', 'mode': 'Q65',
             'message': 'CQ DL7APV JO62', 'snr': -21, 'dt': 2.7,
             'delta_hz': 800, 'freq_mhz': 144.124, 'band': '2m',
             'last_seen': maintenant}]
    monkeypatch.setattr(q65n, 'decoder_wav', lambda *a, **k: faux)
    monkeypatch.setattr(q65n, 'ecrire_wav_12k', lambda *a, **k: None)
    cfg = {'eme': {'submode': 'A', 'band': '2m', 'rf_mhz': 144.124}}
    q65n._traiter_fenetre(b'\x00\x00' * 10, maintenant, cfg)
    d = q65n.decodes_natifs(max_age=10_000)
    assert [x['call'] for x in d] == ['DL7APV']
    assert d[0]['mode'] == 'Q65'
    q65n.arreter_moteur()  # nettoie le cache pour les tests suivants


def test_decodes_natifs_purge_les_vieux(monkeypatch):
    q65n.arreter_moteur()
    vieux = [{'call': 'OLD', 'mode': 'Q65', 'message': '', 'snr': -20,
              'dt': 0.0, 'delta_hz': 0, 'grid': '', 'freq_mhz': 0.0,
              'band': '', 'last_seen': 1.0}]
    monkeypatch.setattr(q65n, 'decoder_wav', lambda *a, **k: vieux)
    monkeypatch.setattr(q65n, 'ecrire_wav_12k', lambda *a, **k: None)
    q65n._traiter_fenetre(b'', 1.0, {'eme': {}})
    assert q65n.decodes_natifs(max_age=1) == []   # trop vieux → purgé
    q65n.arreter_moteur()


def test_traiter_fenetre_nettoie_son_tmpdir(monkeypatch):
    """Ruling 2 : _traiter_fenetre crée son propre tmpdir (data_path fourni à
    decoder_wav) et DOIT le supprimer lui-même — decoder_wav ne le fait pas
    puisqu'un data_path explicite lui est passé (comportement Tâche 2)."""
    import glob
    import tempfile
    q65n.arreter_moteur()
    vus = []

    def faux_decoder(wav_path, **k):
        vus.append(k['data_path'])
        assert os.path.isdir(k['data_path'])  # existe PENDANT le décodage
        return []

    monkeypatch.setattr(q65n, 'decoder_wav', faux_decoder)
    monkeypatch.setattr(q65n, 'ecrire_wav_12k', lambda *a, **k: None)
    motif = os.path.join(tempfile.gettempdir(), 'logx_q65_*')
    avant = set(glob.glob(motif))
    q65n._traiter_fenetre(b'', 1.0, {'eme': {}})
    apres = set(glob.glob(motif))
    assert apres == avant, sorted(apres - avant)   # aucun dossier laissé
    assert len(vus) == 1 and not os.path.isdir(vus[0])  # supprimé après coup
    q65n.arreter_moteur()


def test_ecrire_wav_12k(tmp_path):
    """Écrit un fichier WAV PCM 16 bit mono 12 kHz à partir d'octets int16
    little-endian, puis vérifie les paramètres du fichier produit."""
    p = str(tmp_path / 'x.wav')
    q65n.ecrire_wav_12k(p, b'\x00\x00' * 12000)   # 1 s de silence
    with wave.open(p, 'rb') as w:
        assert w.getframerate() == 12000, f"Framerate={w.getframerate()}, attendu 12000"
        assert w.getnchannels() == 1, f"Channels={w.getnchannels()}, attendu 1"
        assert w.getsampwidth() == 2, f"Sampwidth={w.getsampwidth()}, attendu 2"
        assert w.getnframes() == 12000, f"Frames={w.getnframes()}, attendu 12000"


# ─── RULING contrôleur (Tâche 7) : demarrer_moteur durci contre un échec ────
# de FluxCapture.demarrer() (carte son absente/échec sounddevice). Avant
# durcissement : _flux était assigné AVANT l'appel à .demarrer(), donc un
# échec laissait _flux non-None (worker zombie compris) et un appel suivant
# répondait à tort {'ok': True, 'deja': True}, alors qu'aucune capture ne
# tournait réellement.

def test_demarrer_moteur_echec_ne_laisse_pas_d_etat_zombie(monkeypatch):
    q65n.arreter_moteur()  # état propre avant le témoin

    def _boom(self):
        raise RuntimeError('materiel absent')
    monkeypatch.setattr(q65n.FluxCapture, 'demarrer', _boom)

    r = q65n.demarrer_moteur({'eme': {}})
    assert r['ok'] is False
    assert 'materiel absent' in r.get('error', '')
    assert q65n._flux is None, (
        "un flux qui a echoue a demarrer ne doit pas rester assigne")
    assert q65n._worker is None, (
        "le worker doit etre arrete/nettoye apres un echec de demarrage")
    vivants = [t for t in threading.enumerate() if t.name == 'q65-natif-worker']
    assert not vivants, "aucun thread worker zombie apres un echec de demarrage"


def test_demarrer_moteur_reussit_vraiment_apres_un_echec_precedent(monkeypatch):
    """Contre-épreuve du témoin ci-dessus : après l'échec, un second appel qui
    réussit doit RÉELLEMENT démarrer — pas répondre {'deja': True} sur un état
    fantôme laissé par l'échec précédent."""
    q65n.arreter_moteur()

    def _boom(self):
        raise RuntimeError('materiel absent')
    monkeypatch.setattr(q65n.FluxCapture, 'demarrer', _boom)
    r1 = q65n.demarrer_moteur({'eme': {}})
    assert r1['ok'] is False

    monkeypatch.setattr(q65n.FluxCapture, 'demarrer', lambda self: None)
    r2 = q65n.demarrer_moteur({'eme': {}})
    assert r2['ok'] is True
    assert not r2.get('deja'), (
        "le second appel doit demarrer pour de vrai, pas repondre "
        "deja=True sur l'etat fantome laisse par l'echec precedent")
    assert q65n._flux is not None
    q65n.arreter_moteur()  # nettoie pour les tests suivants


def test_demarrer_moteur_normalise_audio_device_vide_en_none(monkeypatch):
    """cfg.eme.audio_device vient d'un <select> HTML : une chaîne vide quand
    rien n'est sélectionné. FluxCapture/sounddevice attendent un entier ou
    None (périphérique par défaut) — même convention que
    logx_voicekeyer.play_wav (device_idx = int(x) if x not in (None, '')
    else None), à respecter ici aussi pour ne pas planter sounddevice avec
    une chaîne vide."""
    q65n.arreter_moteur()
    vu = {}

    def _capture(self):
        vu['device_index'] = self.device_index
    monkeypatch.setattr(q65n.FluxCapture, 'demarrer', _capture)
    q65n.demarrer_moteur({'eme': {'audio_device': ''}})
    assert vu['device_index'] is None
    q65n.arreter_moteur()


def test_demarrer_moteur_normalise_audio_device_chaine_en_entier(monkeypatch):
    q65n.arreter_moteur()
    vu = {}

    def _capture(self):
        vu['device_index'] = self.device_index
    monkeypatch.setattr(q65n.FluxCapture, 'demarrer', _capture)
    q65n.demarrer_moteur({'eme': {'audio_device': '2'}})
    assert vu['device_index'] == 2
    q65n.arreter_moteur()


def test_demarrer_moteur_reentrant_sur_un_vrai_demarrage(monkeypatch):
    """Non-régression du comportement réentrant existant : un second appel
    alors que le moteur tourne VRAIMENT ne relance rien."""
    q65n.arreter_moteur()
    monkeypatch.setattr(q65n.FluxCapture, 'demarrer', lambda self: None)
    r1 = q65n.demarrer_moteur({'eme': {}})
    assert r1['ok'] is True and not r1.get('deja')
    r2 = q65n.demarrer_moteur({'eme': {}})
    assert r2 == {'ok': True, 'deja': True}
    q65n.arreter_moteur()
