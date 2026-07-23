# -*- coding: utf-8 -*-
"""Enregistreur audio par QSO (tampon glissant) — logx_logbook.js/html.

Fonctionnalité 100% navigateur (MediaRecorder, getUserMedia, Web Audio,
File System Access) : aucune de ces API n'existe côté Python, donc pas de
logique métier à exécuter ici. Ces tests sont des garde-fous statiques
(présence des briques clés, branchement dans submitQSO, absence de la chaîne
interdite) qui déclenchent si quelqu'un supprime la fonctionnalité ou casse
son branchement par inadvertance.

La vérification FONCTIONNELLE réelle (encodage WAV, découpe des dernières
secondes, tolérance à un micro refusé) a été faite dans un vrai moteur JS —
voir le résumé de commit pour le détail des cas testés."""
import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS_PATH = os.path.join(BASE, 'logx_logbook.js')
HTML_PATH = os.path.join(BASE, 'logx_logbook.html')


def _read(path):
    with open(path, encoding='utf-8') as f:
        return f.read()


def test_pas_de_qso_director():
    """Interdiction absolue (nom d'un concurrent) — jamais dans le code."""
    assert 'QSO Director' not in _read(JS_PATH)
    assert 'QSO Director' not in _read(HTML_PATH)


def test_briques_enregistreur_presentes_dans_le_js():
    js = _read(JS_PATH)
    for marker in (
        'function startAudioRecorder', 'function stopAudioRecorder',
        'async function toggleAudioRecorder', 'async function captureQsoAudioClip',
        'function _recStartSegment', 'function _recFinishCurrentSegment',
        'function _encodeWavFromBuffers', 'function _floatChannelsToWav',
        'function _recClipName', 'function _recSaveClip', 'function chooseRecDir',
        'async function loadAudioInputDevices',
    ):
        assert marker in js, f'{marker!r} manquant dans logx_logbook.js'


def test_pas_de_flux_continu_sans_decoupage_en_segments():
    """Piège connu : un WebM/Ogg découpé en plein milieu d'un flux continu
    n'est pas rejouable (seul le tout premier fragment porte l'en-tête du
    conteneur) — la fonctionnalité DOIT redémarrer périodiquement le
    MediaRecorder pour produire des segments autonomes décodables un par un."""
    js = _read(JS_PATH)
    assert 'REC_SEGMENT_MS' in js
    assert '_recRestartSegment' in js
    assert 'setInterval(_recRestartSegment' in js


def test_capture_clip_branchee_dans_les_trois_chemins_de_succes_submitQSO():
    """Le clip doit se déclencher à chaque QSO réellement enregistré : succès
    serveur direct, doublon confirmé par l'opérateur, ET repli hors-ligne —
    sinon un des trois modes de validation resterait silencieusement sans
    enregistrement audio."""
    js = _read(JS_PATH)
    start = js.index('async function submitQSO')
    end = js.index('function clearForm', start)
    submit_body = js[start:end]
    assert submit_body.count('captureQsoAudioClip(') == 3


def test_capture_clip_ignoree_si_desactivee():
    """Garde-fou explicite en tête de captureQsoAudioClip : ne rien faire
    (ni ouverture de flux, ni notification) si l'enregistreur est éteint."""
    js = _read(JS_PATH)
    start = js.index('async function captureQsoAudioClip')
    end = js.index('\n}', start)
    body = js[start:end]
    assert 'if(!recEnabled || !_recStream) return;' in body


def test_panneau_html_present_avec_ses_controles():
    """Les deux contrôles demandés (activer/désactiver + choix du micro),
    plus le choix de dossier (File System Access)."""
    html = _read(HTML_PATH)
    assert 'id="qsoRecPanel"' in html
    assert 'onclick="toggleAudioRecorder()"' in html
    assert 'id="qsoRecDevice"' in html and 'onchange="onRecDeviceChange()"' in html
    assert 'onclick="chooseRecDir()"' in html


def test_nom_de_fichier_suit_le_format_indicatif_bande_date_heure():
    """Vérifie la construction du nom attendu (indicatif_bande_date_heure)
    directement dans le code source de _recClipName, sans dupliquer sa regex
    (dupliquer la regex en Python ne testerait que la copie, pas le JS réel)."""
    js = _read(JS_PATH)
    start = js.index('function _recClipName')
    end = js.index('\n}', start)
    body = js[start:end]
    assert "`${call}_${band}_${qso.date || ''}_${time}.wav`" in body


def test_wav_pas_de_concatenation_naive_de_conteneurs():
    """Piège connu : concaténer plusieurs fichiers WebM/Ogg bout à bout ne
    rejoue souvent que le premier auprès du lecteur — le code doit décoder
    chaque segment en PCM (decodeAudioData) puis ré-encoder un seul WAV."""
    js = _read(JS_PATH)
    assert 'decodeAudioData' in js
    assert "type: 'audio/wav'" in js
