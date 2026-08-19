---
name: chantier-voix-ia-keyer-vocal-2026-08
description: "KEYER VOCAL — option voix IA cloud (ElevenLabs) avec repli automatique et silencieux sur pyttsx3 local, plus le fix layout LOGBOOK callbook+boussole côte à côte (04/08/2026, main daf11ce)"
metadata: 
  node_type: memory
  type: project
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-08-04T06:05:35.959Z
---

Suite directe de [[chantier-cat-plug-and-play-2026-08]] et du fix
[[piege-conteneur-flex-wrap-partage-composite]] — même session, même journée.

## Voix IA (demande F4GLD : « c'est faisable ? » -> « oui vas y »)

Le keyer vocal (`concours/logx_voicekeyer.py`) était **volontairement**
100% hors-ligne (pyttsx3/SAPI5) — un concours de 24-48h ne doit jamais
dépendre du réseau pour dire un indicatif. Avant d'implémenter, j'ai donné
mon avis en 2-3 phrases (question exploratoire) : faisable, mais ne
**jamais remplacer** la voix locale — l'ajouter en option avec repli
automatique. F4GLD a validé cette direction avant tout code.

**Design retenu** :
- `synthesize_to_wav_ai()` : ElevenLabs, format `pcm_24000` (PCM brut 16
  bits/24kHz) — évite d'ajouter une dépendance de décodage MP3/ffmpeg au
  projet, un simple `wave.open()` suffit à écrire le WAV.
- **Cache par texte EXACT** (hash sha256 de `fournisseur|voix|texte`,
  dossier `voice_ai_cache/`) — un CQ fixe ou une station déjà travaillée
  ne refait jamais l'appel réseau. La fonction rend TOUJOURS une copie
  jetable du cache, jamais le fichier de cache lui-même (l'appelant peut
  la supprimer librement sans affecter les prochains appels).
- `synthesize_to_wav()` essaie l'IA en priorité SI activée, retombe
  silencieusement sur pyttsx3 en cas d'échec quelconque (réseau, clé
  invalide, timeout, provider inconnu) — jamais de point de panne.
- Nouveau `post_url_json_binary()` dans `logx_utils.py` (POST JSON ->
  réponse BINAIRE) : un flux audio décodé comme de l'UTF-8 (ce que fait
  `post_url_json` existant) le corromprait silencieusement.
- Clé API (`voicekeyer_ai_api_key`) ajoutée à `SECRET_CONFIG_FIELDS`
  (client) et à la liste `fields` de `/config/secrets` (serveur) — même
  traitement que `qrz_password`/`clublog_api_key` : jamais dans
  localStorage, relue via l'endpoint authentifié au chargement de CONFIG.

**Test technique intéressant** : pour tester le repli local SANS dépendre
d'un vrai moteur SAPI5 (CI Linux/macOS, ou juste rapidité), un FAUX module
`pyttsx3` est injecté dans `sys.modules` via
`monkeypatch.setitem(sys.modules, 'pyttsx3', fake)` — évite la synthèse
audio réelle (lente, bruyante) tout en testant le VRAI corps de
`synthesize_to_wav()`.

**Vérifié en navigateur isolé** (port 8101) avec une fausse clé API :
l'appel ElevenLabs échoue (401), le repli local se déclenche, le message
est réellement synthétisé et joué (`✅ Lu (sans PTT) : ...`) — la chaîne
complète fonctionne sans jamais bloquer le keyer.

## Fix layout LOGBOOK : callbook + boussole côte à côte

Signalé par capture d'écran (04/08/2026) : le bloc callbook/historique
LoTW (sous INDICATIF) et le bloc distance+boussole (sous LOCATOR) étaient
empilés PLEINE LARGEUR, loin l'un de l'autre dans le flux (séparés par
RST/N°/LOCATOR), forçant un scroll pendant la saisie. Question de
positionnement final posée via AskUserQuestion (après LOCATOR vs après
INDICATIF) — F4GLD a choisi « après LOCATOR ».

Implémenté en déplaçant physiquement `dxccBadge`+`prevQsos` (retirés de
sous INDICATIF) pour les regrouper avec `compassInline` dans une nouvelle
ligne flex à 2 colonnes (`.callbook-compass-row`/`.callbook-compass-col`,
`flex:1;min-width:0` chacune) placée après `#locHint`. `todWidget` reste
en place (pas concerné, pas entouré sur la capture).

## Piège de suivi découvert en cours de route

`spawn_task` créé (non traité ici, hors scope) : `cfg_snap.get('contest',
'')` à `logx_http.py:2652` ne protège que contre une clé ABSENTE, pas
contre une valeur `None` explicite — `AttributeError` sur `.strip()`.
Repéré par hasard pendant la vérification navigateur isolée du 04/08.
