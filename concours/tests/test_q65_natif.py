import os, sys
CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CONCOURS not in sys.path:
    sys.path.insert(0, CONCOURS)
FIXTURES = os.path.join(os.path.dirname(__file__), 'fixtures')

import pytest  # noqa: E402
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
