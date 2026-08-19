---
name: chantier-voicekeyer-piper-local-2026-08
description: "Piper (moteur TTS neuronal local, gratuit) ajouté comme alternative à ElevenLabs pour le keyer vocal — F4GLD a refusé l'abonnement cloud (04/08/2026, main bbe3a8c)"
metadata: 
  node_type: memory
  type: project
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-08-04T07:43:44.774Z
---

Suite directe de [[chantier-voix-ia-keyer-vocal-2026-08]], même journée. Après
avoir testé la voix ElevenLabs ajoutée plus tôt, F4GLD a jugé l'abonnement
payant inacceptable : *« eleventslabs necessite un abonnement supplementaire
pour moi ce n'est pas une solution »*. J'avais proposé Piper (rhasspy/piper,
moteur neuronal 100% local, gratuit) comme alternative dans une réponse
exploratoire précédente ; confirmé avec *« je crois que piper serait le
mieux »*.

## Architecture retenue : 3 étages, chacun silencieux à l'échec

`synthesize_to_wav()` essaie dans l'ordre, avec repli automatique à chaque
étage (jamais de point de panne réseau pendant un concours) :
1. **Voix IA cloud** (ElevenLabs, si activée) — la plus naturelle, payante.
2. **Piper** (si activé) — neuronal, local, gratuit. Choix retenu par F4GLD.
3. **pyttsx3/SAPI5** — toujours disponible, dernier recours.

## Intégration technique

- **PAS un paquet pip du projet** : Piper est invoqué en sous-processus
  (`subprocess.run([exe, '--model', model, '--output_file', path],
  input=text.encode(...))`), exactement comme sounddevice s'appuie sur
  PortAudio en externe. `requirements.txt` documente juste comment
  l'installer (`pip install piper-tts` côté opérateur, modèle .onnx
  téléchargé une fois sur huggingface.co/rhasspy/piper-voices) — rien
  d'ajouté aux dépendances réelles du projet.
- Champs CONFIG (`voicekeyer_piper_enabled/_exe/_model`) sont des chemins
  locaux, PAS des secrets — contrairement à la clé API ElevenLabs, ils
  suivent le mécanisme de config normal (pas `SECRET_CONFIG_FIELDS`).
- Vérifié en navigateur isolé avec un exécutable Piper volontairement
  inexistant (`piper_not_installed_xyz`) : repli propre sur SAPI5, message
  réellement synthétisé et joué — la chaîne à 3 étages fonctionne même
  quand Piper n'est pas encore installé sur la machine.

## Piège évité par construction

`synthesize_to_wav_piper()` pré-crée le fichier temporaire via
`tempfile.mkstemp()` AVANT d'appeler `subprocess.run()` — `os.path.getsize()`
ne peut donc jamais lever `FileNotFoundError` même si Piper échoue sans
rien écrire (le fichier vide pré-existant donne simplement une taille de 0,
sous le seuil de 100 octets qui déclenche le repli).
