import os, sys
CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CONCOURS not in sys.path:
    sys.path.insert(0, CONCOURS)
FIXTURES = os.path.join(os.path.dirname(__file__), 'fixtures')

import pytest  # noqa: E402
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
