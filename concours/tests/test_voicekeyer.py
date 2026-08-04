# -*- coding: utf-8 -*-
"""Tests du keyer vocal dynamique (logx_voicekeyer) : épellation
phonétique, expansion de macros, orchestration PTT+lecture. Jamais de vrai
TTS/audio/CAT dans ces tests — tout est mocké, seule la logique est testée."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_voicekeyer as vk


# ─── Épellation phonétique ────────────────────────────────────────────────────

def test_spell_callsign_simple():
    assert vk.spell_callsign('F4GLD') == 'Foxtrot Four Golf Lima Delta'


def test_spell_callsign_minuscules():
    assert vk.spell_callsign('f4gld') == 'Foxtrot Four Golf Lima Delta'


def test_spell_callsign_suffixe_connu():
    # Le « / » se dit maintenant « stroke » AVANT le mot du suffixe.
    assert vk.spell_callsign('F4GLD/P') == 'Foxtrot Four Golf Lima Delta stroke portable'
    assert vk.spell_callsign('F4GLD/QRP') == 'Foxtrot Four Golf Lima Delta stroke Q R P'


def test_spell_callsign_suffixe_inconnu_epele():
    assert vk.spell_callsign('F4GLD/5') == 'Foxtrot Four Golf Lima Delta stroke Five'


def test_spell_callsign_prefixe_stroke():
    # Préfixe DX : « DL/ON4DRT » -> le « / » se dit, aucun mot de suffixe.
    assert vk.spell_callsign('DL/ON4DRT') == \
        'Delta Lima stroke Oscar November Four Delta Romeo Tango'


def test_spell_callsign_prefixe_ET_suffixe():
    # DEUX « / » : préfixe portable. C'est le cas que l'ancienne version
    # (partition sur un seul « / ») escamotait en silence.
    assert vk.spell_callsign('F/DL1UTY/P') == \
        'Foxtrot stroke Delta Lima One Uniform Tango Yankee stroke portable'


def test_spell_callsign_stroke_toujours_international_meme_pour_station_francaise():
    # « stroke » est le mot international, jamais traduit en « barre » --
    # même pour un indicatif français (retour F4GLD 04/08/2026 : entendu
    # « barre » au lieu de « stroke » pour MYCALL=F4GLD/P, jamais ainsi en
    # vrai sur l'air).
    assert vk.spell_callsign('F4GLD/P') == 'Foxtrot Four Golf Lima Delta stroke portable'


def test_spell_callsign_vide():
    assert vk.spell_callsign('') == ''
    assert vk.spell_callsign(None) == ''


def test_spell_digits_report():
    assert vk.spell_digits('59') == 'Five Nine'
    assert vk.spell_digits('599') == 'Five Nine Nine'


def test_spell_digits_serie_avec_zero():
    assert vk.spell_digits('042') == 'Zero Four Two'


def test_spell_digits_vide():
    assert vk.spell_digits('') == ''
    assert vk.spell_digits(None) == ''


# ─── Expansion des macros vocales ────────────────────────────────────────────

def test_expand_voice_text_call_et_mycall():
    ctx = {'call': 'DL1AA', 'mycall': 'F4GLD'}
    out = vk.expand_voice_text('{CALL} de {MYCALL}', ctx)
    assert out == 'Delta Lima One Alpha Alpha de Foxtrot Four Golf Lima Delta'


def test_expand_voice_text_report_et_serie():
    # Sans indicatif de correspondant -> anglais international, EN TOUTES LETTRES.
    ctx = {'rst_sent': '59', 'nr': '001'}
    out = vk.expand_voice_text('{RST_SENT} {NR}', ctx)
    assert out == 'fifty-nine zero zero one'


# ─── Nombres en toutes lettres (le cœur de la demande) ──────────────────────

def test_number_to_words_anglais():
    cas = {0: 'zero', 5: 'five', 15: 'fifteen', 20: 'twenty', 42: 'forty-two',
           59: 'fifty-nine', 73: 'seventy-three', 100: 'one hundred',
           599: 'five hundred ninety-nine', 2024: 'two thousand twenty-four'}
    for n, mot in cas.items():
        assert vk.number_to_words(n, 'en') == mot, n


def test_number_to_words_francais_cas_piegeux():
    cas = {0: 'zéro', 16: 'seize', 21: 'vingt et un', 22: 'vingt-deux',
           59: 'cinquante-neuf', 60: 'soixante', 61: 'soixante et un',
           70: 'soixante-dix', 71: 'soixante et onze', 72: 'soixante-douze',
           76: 'soixante-seize', 77: 'soixante-dix-sept', 80: 'quatre-vingts',
           81: 'quatre-vingt-un', 90: 'quatre-vingt-dix', 91: 'quatre-vingt-onze',
           99: 'quatre-vingt-dix-neuf', 73: 'soixante-treize', 100: 'cent',
           200: 'deux cents', 201: 'deux cent un',
           599: 'cinq cent quatre-vingt-dix-neuf', 1000: 'mille',
           2024: 'deux mille vingt-quatre'}
    for n, mot in cas.items():
        assert vk.number_to_words(n, 'fr') == mot, n


def test_spell_number_zeros_de_tete_et_alphanumerique():
    assert vk.spell_number('59', 'fr') == 'cinquante-neuf'
    assert vk.spell_number('001', 'fr') == 'zéro zéro un'
    assert vk.spell_number('042', 'fr') == 'zéro quarante-deux'
    assert vk.spell_number('001', 'en') == 'zero zero one'
    assert vk.spell_number('00', 'fr') == 'zéro zéro'
    assert vk.spell_number('3A', 'en') == 'Three Alpha'   # non numérique -> phonétique
    assert vk.spell_number('', 'fr') == ''


# ─── Langue et remerciement dérivés de l'indicatif ──────────────────────────

def _mock_country(monkeypatch, name):
    import logx_dxcc as dxcc
    monkeypatch.setattr(dxcc, 'lookup', lambda call: {'country': name} if call else None)


def test_lang_for_call_france_vs_reste(monkeypatch):
    _mock_country(monkeypatch, 'France')
    assert vk.lang_for_call('F5ABC') == 'fr'
    _mock_country(monkeypatch, 'Fed. Rep. of Germany')
    assert vk.lang_for_call('DL1AA') == 'en'
    _mock_country(monkeypatch, '')
    assert vk.lang_for_call('X') == 'en'


def test_thanks_word_par_pays(monkeypatch):
    for pays, mot in [('France', 'merci'), ('Japan', 'arigato'),
                      ('Fed. Rep. of Germany', 'danke'), ('Italy', 'grazie'),
                      ('Spain', 'gracias'), ('Brazil', 'obrigado'),
                      ('United States', 'thanks')]:
        _mock_country(monkeypatch, pays)
        assert vk.thanks_word('CALL') == mot, pays
    _mock_country(monkeypatch, 'Mongolia')
    assert vk.thanks_word('JT1X') == ''          # pas de mot dédié -> juste 73


def test_closing_73_selon_indicatif(monkeypatch):
    _mock_country(monkeypatch, 'France')
    assert vk.closing_73({'call': 'F5ABC'}) == 'soixante-treize merci'
    _mock_country(monkeypatch, 'Japan')
    assert vk.closing_73({'call': 'JA1XYZ'}) == 'seventy-three arigato'
    _mock_country(monkeypatch, 'Mongolia')
    assert vk.closing_73({'call': 'JT1X'}) == 'seventy-three'   # 73 seul si pas de mot


def test_expand_report_francais_pour_station_F(monkeypatch):
    _mock_country(monkeypatch, 'France')
    ctx = {'call': 'F5ABC', 'rst_sent': '59', 'mycall': 'F4GLD'}
    out = vk.expand_voice_text('{CALL} {RST_SENT} {TNX}', ctx)
    assert 'Foxtrot Five Alpha Bravo Charlie' in out    # indicatif phonétique international
    assert 'cinquante-neuf' in out                       # report en français
    assert out.endswith('soixante-treize merci')          # clôture 73 + merci


def test_expand_voice_text_mycall_suffixe_reste_en_stroke_meme_en_francais(monkeypatch):
    """Reproduction exacte du bouton « Tester » de CONFIG (retour F4GLD
    04/08/2026) : MYCALL=F4GLD/P dérive la langue française (F4GLD -> France)
    pour les NOMBRES, mais le « / » doit rester « stroke » (mot international,
    jamais traduit) même si le message entier est par ailleurs en français."""
    _mock_country(monkeypatch, 'France')
    out = vk.expand_voice_text('{MYCALL}', {'mycall': 'F4GLD/P'})
    assert out == 'Foxtrot Four Golf Lima Delta stroke portable'


def test_expand_report_anglais_pour_station_DL(monkeypatch):
    _mock_country(monkeypatch, 'Fed. Rep. of Germany')
    ctx = {'call': 'DL1AA', 'rst_sent': '59'}
    out = vk.expand_voice_text('{RST_SENT} {TNX}', ctx)
    assert 'fifty-nine' in out and out.endswith('seventy-three danke')


def test_expand_voice_text_placeholders_manquants_deviennent_vides():
    out = vk.expand_voice_text('CQ {MYCALL}', {})
    assert out == 'CQ '


def test_voice_macros_default_ont_les_champs_attendus():
    for m in vk.VOICE_MACROS_DEFAULT:
        assert {'key', 'label', 'text'} <= set(m)


# ─── Réglages ─────────────────────────────────────────────────────────────────

def test_voicekeyer_settings_defaut():
    s = vk.voicekeyer_settings({})
    assert s['enabled'] is False and s['rate'] == 175 and s['device'] == ''


def test_voicekeyer_settings_personnalises():
    s = vk.voicekeyer_settings({'voicekeyer_enabled': True, 'voicekeyer_device': '3',
                                 'voicekeyer_voice_id': 'xyz', 'voicekeyer_rate': '150'})
    assert s == {'enabled': True, 'device': '3', 'voice_id': 'xyz', 'rate': 150,
                 'ai': {'enabled': False, 'provider': 'elevenlabs', 'api_key': '', 'voice_id': ''}}


def test_voicekeyer_settings_rate_invalide_retombe_sur_defaut():
    assert vk.voicekeyer_settings({'voicekeyer_rate': 'abc'})['rate'] == 175


# ─── Listes (jamais d'exception si moteur/peripherique indisponible) ────────

def test_list_output_devices_ne_plante_pas():
    assert isinstance(vk.list_output_devices(), list)


def test_list_tts_voices_ne_plante_pas():
    assert isinstance(vk.list_tts_voices(), list)


# ─── Orchestration send_voice_message (PTT + synthèse + lecture, tout mocké) ──

def test_send_voice_message_desactive():
    r = vk.send_voice_message({}, 'CQ test')
    assert not r['ok'] and 'désactivé' in r['error'].lower()


def test_send_voice_message_texte_vide():
    r = vk.send_voice_message({'voicekeyer_enabled': True}, '  ')
    assert not r['ok'] and 'vide' in r['error'].lower()


def test_send_voice_message_synthese_indisponible(monkeypatch):
    monkeypatch.setattr(vk, 'synthesize_to_wav', lambda *a, **k: None)
    r = vk.send_voice_message({'voicekeyer_enabled': True}, 'CQ test')
    assert not r['ok'] and 'synthèse' in r['error'].lower()


def test_send_voice_message_ptt_refuse(monkeypatch, tmp_path):
    fake_wav = tmp_path / 'x.wav'
    fake_wav.write_bytes(b'RIFF....WAVEfmt ')
    monkeypatch.setattr(vk, 'synthesize_to_wav', lambda *a, **k: str(fake_wav))
    monkeypatch.setattr(vk, '_set_ptt', lambda cfg, on: {'ok': False, 'error': 'radio injoignable'})
    r = vk.send_voice_message({'voicekeyer_enabled': True}, 'CQ test')
    assert not r['ok'] and 'PTT refusé' in r['error']
    assert not fake_wav.exists()   # le WAV temporaire est nettoyé même en échec


def test_send_voice_message_chemin_complet(monkeypatch, tmp_path):
    fake_wav = tmp_path / 'y.wav'
    fake_wav.write_bytes(b'RIFF....WAVEfmt ')
    ptt_calls = []
    played = []
    monkeypatch.setattr(vk, 'synthesize_to_wav', lambda *a, **k: str(fake_wav))
    monkeypatch.setattr(vk, '_set_ptt', lambda cfg, on: ptt_calls.append(on) or {'ok': True})
    monkeypatch.setattr(vk, 'play_wav', lambda path, device=None: played.append(path))
    r = vk.send_voice_message({'voicekeyer_enabled': True}, 'CQ test')
    assert r['ok'] and r['text'] == 'CQ test'
    assert ptt_calls == [True, False]     # PTT activé puis relâché, dans cet ordre
    assert played == [str(fake_wav)]
    assert not fake_wav.exists()           # nettoyage du WAV temporaire


def test_send_voice_message_erreur_lecture_relache_quand_meme_le_ptt(monkeypatch, tmp_path):
    fake_wav = tmp_path / 'z.wav'
    fake_wav.write_bytes(b'RIFF....WAVEfmt ')
    ptt_calls = []
    monkeypatch.setattr(vk, 'synthesize_to_wav', lambda *a, **k: str(fake_wav))
    monkeypatch.setattr(vk, '_set_ptt', lambda cfg, on: ptt_calls.append(on) or {'ok': True})
    def boom(path, device=None):
        raise RuntimeError('périphérique audio indisponible')
    monkeypatch.setattr(vk, 'play_wav', boom)
    r = vk.send_voice_message({'voicekeyer_enabled': True}, 'CQ test')
    assert not r['ok'] and 'Lecture audio' in r['error']
    assert ptt_calls == [True, False]      # le PTT est bien relâché même après l'erreur


# ─── skip_ptt : bouton "Tester" de CONFIG, prévisualisation sans radio ────────
# Retour F4GLD 04/08/2026 : le test échouait systématiquement tant que le
# pilotage CAT n'était pas configuré, alors que l'opérateur veut juste
# vérifier le périphérique audio/la voix choisis.

def test_send_voice_message_skip_ptt_fonctionne_sans_pilotage_configure(monkeypatch, tmp_path):
    """Le PTT ne doit MEME PAS être tenté : _set_ptt ne doit jamais être
    appelé, contrairement au chemin normal (test_send_voice_message_ptt_refuse
    ci-dessus, qui échoue precisement quand _set_ptt échoue)."""
    fake_wav = tmp_path / 'skip.wav'
    fake_wav.write_bytes(b'RIFF....WAVEfmt ')
    ptt_calls = []
    played = []
    monkeypatch.setattr(vk, 'synthesize_to_wav', lambda *a, **k: str(fake_wav))
    monkeypatch.setattr(vk, '_set_ptt',
        lambda cfg, on: ptt_calls.append(on) or (_ for _ in ()).throw(
            AssertionError('_set_ptt ne doit jamais être appelé avec skip_ptt=True')))
    monkeypatch.setattr(vk, 'play_wav', lambda path, device=None: played.append(path))
    r = vk.send_voice_message({'voicekeyer_enabled': True}, 'CQ test', skip_ptt=True)
    assert r['ok'] and r['text'] == 'CQ test'
    assert ptt_calls == []                 # jamais appelé
    assert played == [str(fake_wav)]
    assert not fake_wav.exists()


def test_send_voice_message_skip_ptt_par_defaut_faux():
    """skip_ptt doit être opt-in explicite — le déclenchement réel depuis le
    logbook (envoyer_message()/send_voice_message() sans l'argument) doit
    conserver l'exigence PTT à l'identique, sinon un message pourrait
    sembler "envoyé" sans que la radio ait réellement transmis."""
    import inspect
    sig = inspect.signature(vk.send_voice_message)
    assert sig.parameters['skip_ptt'].default is False


def test_send_voice_message_skip_ptt_erreur_lecture_pas_de_ptt_release(monkeypatch, tmp_path):
    """Si la lecture échoue avec skip_ptt=True, aucune tentative de
    relâchement PTT ne doit avoir lieu (rien n'a été engagé)."""
    fake_wav = tmp_path / 'skip_err.wav'
    fake_wav.write_bytes(b'RIFF....WAVEfmt ')
    ptt_calls = []
    monkeypatch.setattr(vk, 'synthesize_to_wav', lambda *a, **k: str(fake_wav))
    monkeypatch.setattr(vk, '_set_ptt', lambda cfg, on: ptt_calls.append(on) or {'ok': True})
    def boom(path, device=None):
        raise RuntimeError('périphérique audio indisponible')
    monkeypatch.setattr(vk, 'play_wav', boom)
    r = vk.send_voice_message({'voicekeyer_enabled': True}, 'CQ test', skip_ptt=True)
    assert not r['ok'] and 'Lecture audio' in r['error']
    assert ptt_calls == []


# ─── Dispatch PTT selon le mode CAT actif ─────────────────────────────────────

def test_set_ptt_dispatch_natif(monkeypatch):
    import logx_cat as cat
    monkeypatch.setattr(cat, 'cat_settings', lambda cfg: {'enabled': True, 'mode': 'native'})
    monkeypatch.setattr(cat, 'set_ptt', lambda cfg, on: {'ok': True, 'via': 'native', 'on': on})
    r = vk._set_ptt({}, True)
    assert r == {'ok': True, 'via': 'native', 'on': True}


def test_set_ptt_dispatch_tci(monkeypatch):
    import logx_cat as cat
    import logx_tci as tci
    monkeypatch.setattr(cat, 'cat_settings', lambda cfg: {'enabled': True, 'mode': 'tci'})
    monkeypatch.setattr(tci, 'set_ptt', lambda cfg, on: {'ok': True, 'via': 'tci', 'on': on})
    r = vk._set_ptt({}, False)
    assert r == {'ok': True, 'via': 'tci', 'on': False}


def test_set_ptt_dispatch_flrig(monkeypatch):
    import logx_cat as cat
    import logx_flrig as flrig
    monkeypatch.setattr(cat, 'cat_settings', lambda cfg: {'enabled': True, 'mode': 'flrig'})
    monkeypatch.setattr(flrig, 'flrig_settings', lambda cfg: {'host': 'h', 'port': 12345})
    monkeypatch.setattr(flrig, 'set_ptt', lambda host, port, on: {'ok': True, 'via': 'flrig', 'host': host})
    r = vk._set_ptt({}, True)
    assert r == {'ok': True, 'via': 'flrig', 'host': 'h'}


def test_set_ptt_dispatch_rigctld(monkeypatch):
    import logx_cat as cat
    import logx_rig as rig
    monkeypatch.setattr(cat, 'cat_settings', lambda cfg: {'enabled': False, 'mode': 'native'})
    monkeypatch.setattr(rig, 'rig_settings', lambda cfg: {'enabled': True, 'host': 'h', 'port': 1})
    monkeypatch.setattr(rig, 'set_ptt', lambda host, port, on: {'ok': True, 'via': 'rigctld', 'host': host})
    r = vk._set_ptt({}, True)
    assert r == {'ok': True, 'via': 'rigctld', 'host': 'h'}


# ─── voicekeyer_settings() : sous-dict 'ai' ───────────────────────────────────

def test_voicekeyer_settings_ai_par_defaut_desactivee():
    s = vk.voicekeyer_settings({'voicekeyer_enabled': True})
    assert s['ai'] == {'enabled': False, 'provider': 'elevenlabs', 'api_key': '', 'voice_id': ''}


def test_voicekeyer_settings_ai_configuree():
    s = vk.voicekeyer_settings({
        'voicekeyer_ai_enabled': True, 'voicekeyer_ai_provider': 'elevenlabs',
        'voicekeyer_ai_api_key': 'sk-abc', 'voicekeyer_ai_voice_id': 'v123'})
    assert s['ai'] == {'enabled': True, 'provider': 'elevenlabs',
                       'api_key': 'sk-abc', 'voice_id': 'v123'}


# ─── synthesize_to_wav_ai() : dispatch fournisseur + cache ────────────────────
# Jamais de vrai appel réseau ici : AI_PROVIDERS['elevenlabs'] est monkeypatché.
# Le cache vit dans _AI_CACHE_DIR (relatif) — TOUJOURS redirigé vers tmp_path
# dans ces tests (voir piege-tests-ecrivent-dans-le-depot en mémoire projet :
# des tests qui écrivent dans concours/ sont un vrai bug, pas un détail).

def test_synthesize_to_wav_ai_provider_inconnu_rend_none(monkeypatch, tmp_path):
    monkeypatch.setattr(vk, '_AI_CACHE_DIR', str(tmp_path / 'cache'))
    assert vk.synthesize_to_wav_ai('CQ test', 'provider_bidon', 'sk-abc', 'v1') is None


def test_synthesize_to_wav_ai_sans_cle_rend_none(monkeypatch, tmp_path):
    monkeypatch.setattr(vk, '_AI_CACHE_DIR', str(tmp_path / 'cache'))
    assert vk.synthesize_to_wav_ai('CQ test', 'elevenlabs', '', 'v1') is None


def test_synthesize_to_wav_ai_sans_voice_id_rend_none(monkeypatch, tmp_path):
    monkeypatch.setattr(vk, '_AI_CACHE_DIR', str(tmp_path / 'cache'))
    assert vk.synthesize_to_wav_ai('CQ test', 'elevenlabs', 'sk-abc', '') is None


def _fake_pcm(n_frames=4000):
    # PCM 16 bits mono : n_frames * 2 octets, valeurs arbitraires mais non
    # nulles pour que ce ne soit pas juste un silence.
    return bytes((i % 200) for i in range(n_frames * 2))


def test_synthesize_to_wav_ai_cache_miss_appelle_le_fournisseur_et_peuple_le_cache(monkeypatch, tmp_path):
    monkeypatch.setattr(vk, '_AI_CACHE_DIR', str(tmp_path / 'cache'))
    calls = []
    def fake_provider(api_key, voice_id, text, timeout):
        calls.append((api_key, voice_id, text))
        return _fake_pcm()
    monkeypatch.setitem(vk.AI_PROVIDERS, 'elevenlabs', fake_provider)

    path = vk.synthesize_to_wav_ai('CQ Contest, F4GLD', 'elevenlabs', 'sk-abc', 'v1')
    assert path and os.path.exists(path)
    assert calls == [('sk-abc', 'v1', 'CQ Contest, F4GLD')]

    cache_path = vk._ai_cache_path('elevenlabs', 'v1', 'CQ Contest, F4GLD')
    assert os.path.exists(cache_path)
    assert path != cache_path            # copie jetable, jamais le fichier de cache lui-même
    import wave
    with wave.open(path, 'rb') as wf:
        assert wf.getnchannels() == 1 and wf.getframerate() == 24000


def test_synthesize_to_wav_ai_cache_hit_ne_rappelle_jamais_le_fournisseur(monkeypatch, tmp_path):
    monkeypatch.setattr(vk, '_AI_CACHE_DIR', str(tmp_path / 'cache'))
    def boom(*a, **k):
        raise AssertionError('le fournisseur ne doit pas être rappelé sur un cache hit')
    monkeypatch.setitem(vk.AI_PROVIDERS, 'elevenlabs', boom)

    cache_path = vk._ai_cache_path('elevenlabs', 'v1', 'CQ Contest, F4GLD')
    os.makedirs(os.path.dirname(cache_path), exist_ok=True)
    vk._write_wav_from_pcm(cache_path, _fake_pcm())
    cache_mtime = os.path.getmtime(cache_path)

    path = vk.synthesize_to_wav_ai('CQ Contest, F4GLD', 'elevenlabs', 'sk-abc', 'v1')
    assert path and path != cache_path
    assert os.path.getmtime(cache_path) == cache_mtime   # jamais réécrit


def test_synthesize_to_wav_ai_echec_fournisseur_rend_none_et_ne_cree_pas_le_cache(monkeypatch, tmp_path):
    monkeypatch.setattr(vk, '_AI_CACHE_DIR', str(tmp_path / 'cache'))
    monkeypatch.setitem(vk.AI_PROVIDERS, 'elevenlabs', lambda *a, **k: None)

    path = vk.synthesize_to_wav_ai('CQ test', 'elevenlabs', 'sk-abc', 'v1')
    assert path is None
    assert not os.path.exists(vk._ai_cache_path('elevenlabs', 'v1', 'CQ test'))


# ─── synthesize_to_wav() : priorité IA + repli local silencieux ───────────────
# Un vrai pyttsx3/SAPI5 n'est PAS mocké ailleurs dans ce fichier (les tests
# send_voice_message monkeypatchent synthesize_to_wav ENTIÈREMENT) — ici on a
# besoin du VRAI corps de la fonction pour tester le dispatch IA -> local, donc
# on injecte un faux module pyttsx3 dans sys.modules : rapide, silencieux,
# fonctionne même sur une machine sans moteur SAPI5 installé (CI Linux/macOS).
class _FakePyttsx3Engine:
    def __init__(self):
        self._voice = None
        self._rate = None
    def getProperty(self, name):
        return [] if name == 'voices' else None
    def setProperty(self, name, val):
        pass
    def save_to_file(self, text, path):
        with open(path, 'wb') as f:
            f.write(b'RIFF....WAVEfmt ' + b'\x00' * 100)   # > 100 octets : passe le controle anti-echec-silencieux
    def runAndWait(self):
        pass
    def stop(self):
        pass


def _install_fake_pyttsx3(monkeypatch):
    import sys as _sys
    import types as _types
    fake = _types.ModuleType('pyttsx3')
    fake.init = lambda: _FakePyttsx3Engine()
    monkeypatch.setitem(_sys.modules, 'pyttsx3', fake)


def test_synthesize_to_wav_sans_ai_ne_touche_jamais_synthesize_to_wav_ai(monkeypatch):
    """Comportement inchangé pour tout appelant existant qui n'a jamais
    connu ce paramètre (contrat rétro-compatible)."""
    def boom(*a, **k):
        raise AssertionError('synthesize_to_wav_ai ne doit pas être appelé sans ai=')
    monkeypatch.setattr(vk, 'synthesize_to_wav_ai', boom)
    monkeypatch.setattr(vk, '_voice_id_for_lang', lambda engine, lang: None)
    _install_fake_pyttsx3(monkeypatch)
    path = vk.synthesize_to_wav('CQ test')     # pas de kwarg ai= du tout
    assert path and os.path.exists(path)


def test_synthesize_to_wav_ai_desactivee_ne_lappelle_pas(monkeypatch):
    def boom(*a, **k):
        raise AssertionError('synthesize_to_wav_ai ne doit pas être appelé si ai.enabled est faux')
    monkeypatch.setattr(vk, 'synthesize_to_wav_ai', boom)
    monkeypatch.setattr(vk, '_voice_id_for_lang', lambda engine, lang: None)
    _install_fake_pyttsx3(monkeypatch)
    path = vk.synthesize_to_wav('CQ test', ai={'enabled': False})
    assert path and os.path.exists(path)


def test_synthesize_to_wav_essaie_lia_en_priorite(monkeypatch, tmp_path):
    fake_ai_wav = tmp_path / 'ai.wav'
    fake_ai_wav.write_bytes(b'RIFF....WAVEfmt ' + b'\x00' * 100)
    monkeypatch.setattr(vk, 'synthesize_to_wav_ai', lambda *a, **k: str(fake_ai_wav))
    path = vk.synthesize_to_wav('CQ test', ai={'enabled': True, 'provider': 'elevenlabs',
                                               'api_key': 'sk-abc', 'voice_id': 'v1'})
    assert path == str(fake_ai_wav)


def test_synthesize_to_wav_repli_local_silencieux_si_lia_echoue(monkeypatch, capsys):
    """C'est LE point central de la fonctionnalité : un fournisseur IA
    injoignable/mal configuré ne doit JAMAIS empêcher le keyer vocal de
    fonctionner — le concours ne dépend jamais du réseau (retour F4GLD
    04/08/2026)."""
    monkeypatch.setattr(vk, 'synthesize_to_wav_ai', lambda *a, **k: None)
    monkeypatch.setattr(vk, '_voice_id_for_lang', lambda engine, lang: None)
    _install_fake_pyttsx3(monkeypatch)
    path = vk.synthesize_to_wav('CQ test', ai={'enabled': True, 'provider': 'elevenlabs',
                                               'api_key': 'sk-abc', 'voice_id': 'v1'})
    assert path and os.path.exists(path)
    assert 'repli sur la voix locale' in capsys.readouterr().out


def test_set_ptt_dispatch_rien_active(monkeypatch):
    import logx_cat as cat
    import logx_rig as rig
    monkeypatch.setattr(cat, 'cat_settings', lambda cfg: {'enabled': False, 'mode': 'native'})
    monkeypatch.setattr(rig, 'rig_settings', lambda cfg: {'enabled': False, 'host': '', 'port': 0})
    r = vk._set_ptt({}, True)
    assert not r['ok'] and 'désactivé' in r['error'].lower()
