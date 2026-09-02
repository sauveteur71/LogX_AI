# Décodage Q65 natif (hors-ligne) — Plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Décoder le Q65 EME hors-ligne dans le cockpit EME de LogX AI, sans WSJT-X lancé, en pilotant le binaire `jt9` de référence en sous-processus.

**Architecture:** Une source EME **additionnelle et opt-in** : la carte son est captée en 12 kHz mono, segmentée en fenêtres de 60 s alignées sur la minute UTC, chaque fenêtre est décodée par `jt9` embarqué, et les décodages sont normalisés sur la **structure exacte** que le cockpit consomme déjà (`wsjtx.eme_decodes()`). Le pont UDP WSJT-X existant n'est pas touché ; un sélecteur de source dans `config.json` choisit l'un ou l'autre.

**Tech Stack:** Python 3 (`subprocess`, `wave`, `struct`), dépendance audio `sounddevice` (PortAudio), `jt9.exe` (WSJT-X, GPLv3), pytest.

**Spec:** `docs/superpowers/specs/2026-09-01-q65-decodage-natif-design.md`

## Global Constraints

- **Langue** : commentaires, messages, docstrings et UI en **français**.
- **Licence** : LogX AI et WSJT-X sont GPLv3 ; embarquer `jt9` vanilla K1JT est autorisé (livrer/offrir sa source, conserver ses copyrights).
- **Périmètre V1 = réception Q65 seulement.** INTERDIT dans ce plan : tout code d'émission/PTT (relève du skill `tx-human-consent`), JT65 (dépendance KVASD non-GPL), MAP65/large bande, orchestration IA.
- **Audio jt9 = 12 kHz mono 16 bit** (pas 48 kHz).
- **Ne rien casser du chemin UDP** : `wsjtx.eme_decodes()` et le pont UDP restent inchangés ; le natif est désactivé par défaut.
- **Méthode de test du dépôt** : obtenir un TÉMOIN VERT avant toute mutation ; après correctif, remettre le défaut, vérifier que le test ROUGIT, restaurer (contrôle md5). Assertions sur le **contenu décodé** et la **structure**, jamais sur une simple présence de chaîne.
- **Format de décodage cible produit** (structure consommée par le cockpit, cf. `logx_eme.html` `renderDecodes` et `wsjtx.recent_decodes`) : dict avec au minimum
  `{'call': str, 'grid': str, 'mode': 'Q65', 'message': str, 'snr': int, 'dt': float, 'delta_hz': int, 'freq_mhz': float, 'band': str, 'last_seen': float}`.

---

## Structure des fichiers

- **Créer** `concours/logx_q65_natif.py` — pipeline natif complet, responsabilité unique : « produire des décodages Q65 au format cockpit à partir d'une carte son, sans WSJT-X ». Sous-parties : parsing stdout, runner subprocess, segmenteur/écriture wav, capture audio, orchestrateur + cache TTL.
- **Créer** `concours/tests/test_q65_natif.py` — tests unitaires + intégration (skip si `jt9` absent).
- **Créer** `concours/tests/fixtures/q65_60A_eme_6m.wav` — échantillon EME officiel (fixture d'intégration, témoin vert réel).
- **Créer** `concours/tests/fixtures/jt9_stdout_q65_60A.txt` — capture stdout de référence (fixture parser, pur, pas de binaire requis).
- **Modifier** `concours/logx_http.py:2197-2209` (`_eme_cockpit_dict`) — sélection de source.
- **Modifier** `concours/logx_configuration.html` + `concours/logx_configuration.js` — sélecteur de source EME + carte son (plomberie station, `expert-only`).
- **Modifier** `concours/config.example.json` — documenter la section `"eme"`.
- **Modifier** `.github/workflows/build-release.yml` (Task 8) — embarquer `jt9` vanilla.

---

### Task 1: Parser du stdout jt9 → décodages normalisés

**Files:**
- Create: `concours/logx_q65_natif.py`
- Create: `concours/tests/fixtures/jt9_stdout_q65_60A.txt`
- Test: `concours/tests/test_q65_natif.py`

**Interfaces:**
- Consumes: `logx_wsjtx.extract_calls(message: str, my_call: str = '') -> list[str]` (indicatifs plausibles ; garde l'émetteur en position 2 pour un échange tiers) et `logx_wsjtx.extract_grid(message: str) -> str` (carré Maidenhead, **piège RR73/RRR/73 déjà géré**). Réutilisées pour la cohérence avec le chemin UDP — ne PAS réécrire un extracteur de carré (le motif `[A-R]{2}\d{2}` matche « RR73 » : bug garanti).
- Produces:
  `parse_jt9_stdout(stdout: str, *, freq_mhz: float = 0.0, band: str = '', my_call: str = '', now: float | None = None) -> list[dict]`
  Chaque dict a les clés du format cockpit (cf. Global Constraints). `my_call` (indicatif station, exclu de l'extraction) et `now` (défaut : horloge courante) injectables pour les tests.

- [ ] **Step 1: Créer la fixture stdout de référence**

Créer `concours/tests/fixtures/jt9_stdout_q65_60A.txt` avec le stdout mesuré au spike (3 stations EME) :

```
0000 -24  2.8  697 :  W7GJ N8JX EN73                        q0 
0000 -20  2.8 1420 :  W7GJ W1VD FN31                        q0 
0000 -19  2.8 1620 :  W7GJ VE1JF RRR                        q0 
<DecodeFinished>   0   3     1000
```

- [ ] **Step 2: Écrire le test qui échoue**

```python
# concours/tests/test_q65_natif.py
import os, sys
CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CONCOURS not in sys.path:
    sys.path.insert(0, CONCOURS)
FIXTURES = os.path.join(os.path.dirname(__file__), 'fixtures')

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
```

- [ ] **Step 3: Lancer le test, vérifier l'échec**

Run: `cd concours && python -m pytest tests/test_q65_natif.py -v`
Expected: FAIL (module `logx_q65_natif` inexistant / `parse_jt9_stdout` non défini).

- [ ] **Step 4: Implémenter le parser minimal**

```python
# concours/logx_q65_natif.py
# -*- coding: utf-8 -*-
"""Décodage Q65 EME natif (hors-ligne) : capture carte son → segments 12 kHz
alignés UTC → jt9 embarqué → décodages au format cockpit. N'émet JAMAIS ;
réception seule (l'émission relèverait du skill tx-human-consent)."""
import re
import time

import logx_wsjtx as wsjtx

# Ligne stdout jt9 : "HHMM SNR DT FREQ :  message ... qN"
_LIGNE = re.compile(
    r'^\s*\d{4}\s+(-?\d+)\s+([\d.+-]+)\s+(\d+)\s+:\s+(.*?)\s+q\S*\s*$'
)


def parse_jt9_stdout(stdout, *, freq_mhz=0.0, band='', my_call='', now=None):
    """Transforme le stdout d'un décodage jt9 Q65 en liste de décodages
    normalisés (mêmes clés que wsjtx.eme_decodes()). Ignore <DecodeFinished>
    et toute ligne hors-format. Réutilise extract_calls/extract_grid de
    logx_wsjtx (cohérence avec le chemin UDP, piège RR73 déjà géré)."""
    if now is None:
        now = time.time()
    out = []
    for ligne in (stdout or '').splitlines():
        m = _LIGNE.match(ligne)
        if not m:
            continue
        snr, dt, dfreq, message = m.groups()
        message = message.strip()
        calls = wsjtx.extract_calls(message, my_call)
        out.append({
            'call': calls[0] if calls else '',
            'grid': wsjtx.extract_grid(message),
            'mode': 'Q65',
            'message': message,
            'snr': int(snr),
            'dt': float(dt),
            'delta_hz': int(dfreq),
            'freq_mhz': freq_mhz,
            'band': band,
            'last_seen': now,
        })
    return out
```

- [ ] **Step 5: Lancer le test, vérifier le succès**

Run: `cd concours && python -m pytest tests/test_q65_natif.py -v`
Expected: PASS (2 tests).

- [ ] **Step 6: Contre-épreuve par mutation**

Remplacer `int(snr)` par `abs(int(snr))` dans le parser. Relancer : le test DOIT rougir (`premier['snr'] == -24` échoue). Restaurer, relancer : vert. Contrôler `git diff` vide sur le fichier source.

- [ ] **Step 7: Commit**

```bash
git add concours/logx_q65_natif.py concours/tests/test_q65_natif.py concours/tests/fixtures/jt9_stdout_q65_60A.txt
git commit -m "feat(q65-natif): parser stdout jt9 -> decodages format cockpit"
```

---

### Task 2: Runner jt9 (sous-processus) sur un .wav

**Files:**
- Modify: `concours/logx_q65_natif.py`
- Create: `concours/tests/fixtures/q65_60A_eme_6m.wav` (copier depuis l'échantillon officiel téléchargé au spike)
- Test: `concours/tests/test_q65_natif.py`

**Interfaces:**
- Consumes: `parse_jt9_stdout(...)` (Task 1).
- Produces:
  `resoudre_jt9(cfg: dict | None = None) -> str` — chemin absolu du binaire jt9 (config `eme.jt9_path` > binaire embarqué > `jt9`/`jt9.exe` du PATH) ; lève `FileNotFoundError` explicite si absent.
  `decoder_wav(wav_path: str, *, submode: str = 'A', tr_period: int = 60, jt9_path: str | None = None, data_path: str | None = None, ap: dict | None = None, freq_mhz: float = 0.0, band: str = '', timeout: float = 55.0) -> list[dict]`
  `ap` (décodage assisté, optionnel) : `{'my_call','my_grid','his_call','his_grid','qso_prog'}` → flags `-c/-G/-x/-g/-Q`.

- [ ] **Step 1: Copier la fixture wav**

```bash
cp "<scratchpad>/q65_60A_eme_6m.wav" concours/tests/fixtures/q65_60A_eme_6m.wav
```
(échantillon EME Q65-60A 6 m officiel : `sourceforge.net/projects/wsjt/files/samples/Q65/60A_EME_6m/210106_1621.wav`, 12 kHz mono 16 bit.)

- [ ] **Step 2: Écrire le test d'intégration qui échoue**

```python
import shutil
import pytest

def _jt9_dispo():
    try:
        return q65n.resoudre_jt9() is not None
    except FileNotFoundError:
        return False

@pytest.mark.skipif(not _jt9_dispo(), reason="jt9 non installé sur cette machine")
def test_decoder_wav_echantillon_eme():
    wav = os.path.join(FIXTURES, 'q65_60A_eme_6m.wav')
    d = q65n.decoder_wav(wav, submode='A', tr_period=60, freq_mhz=50.313, band='6m')
    calls = sorted(x['call'] for x in d)
    # Le décodeur de référence sort ces 3 stations EME (mesuré au spike)
    assert calls == ['N8JX', 'VE1JF', 'W1VD'], calls
    parN8JX = next(x for x in d if x['call'] == 'N8JX')
    assert parN8JX['snr'] <= -20         # near-threshold EME
    assert parN8JX['mode'] == 'Q65'
```

- [ ] **Step 3: Lancer, vérifier l'échec**

Run: `cd concours && python -m pytest tests/test_q65_natif.py::test_decoder_wav_echantillon_eme -v`
Expected: FAIL (`decoder_wav` non défini). Si `jt9` absent : SKIP (attendu ; l'implémenteur doit disposer de WSJT-X pour ce test — sinon le noter et s'appuyer sur Task 1).

- [ ] **Step 4: Implémenter le runner**

```python
import os
import shutil
import subprocess
import tempfile


def resoudre_jt9(cfg=None):
    p = ((cfg or {}).get('eme', {}) or {}).get('jt9_path')
    if p and os.path.isfile(p):
        return p
    # Binaire embarqué (Task 8) : concours/vendor/jt9/<os>/jt9[.exe]
    ici = os.path.dirname(os.path.abspath(__file__))
    for nom in ('jt9.exe', 'jt9'):
        cand = os.path.join(ici, 'vendor', 'jt9', nom)
        if os.path.isfile(cand):
            return cand
    trouve = shutil.which('jt9') or shutil.which('jt9.exe')
    if trouve:
        return trouve
    raise FileNotFoundError(
        "jt9 introuvable : renseigne eme.jt9_path dans config.json, "
        "installe WSJT-X, ou fournis le binaire embarqué."
    )


def decoder_wav(wav_path, *, submode='A', tr_period=60, jt9_path=None,
                data_path=None, ap=None, freq_mhz=0.0, band='', timeout=55.0):
    jt9_path = jt9_path or resoudre_jt9()
    tmp = data_path or tempfile.mkdtemp(prefix='logx_q65_')
    argv = [jt9_path, '-3', '-p', str(int(tr_period)), '-b', submode,
            '-q', '-a', tmp, wav_path]
    if ap:
        for flag, cle in (('-c', 'my_call'), ('-G', 'my_grid'),
                          ('-x', 'his_call'), ('-g', 'his_grid'),
                          ('-Q', 'qso_prog')):
            if ap.get(cle) not in (None, ''):
                argv += [flag, str(ap[cle])]
    res = subprocess.run(argv, capture_output=True, text=True,
                         timeout=timeout)
    return parse_jt9_stdout(res.stdout, freq_mhz=freq_mhz, band=band)
```

- [ ] **Step 5: Lancer, vérifier le succès**

Run: `cd concours && python -m pytest tests/test_q65_natif.py -v`
Expected: PASS (parser + intégration ; ou SKIP intégration si pas de jt9).

- [ ] **Step 6: Contre-épreuve**

Muter `'-3'` en `'-8'` (FT8) dans `argv`. Relancer : l'intégration DOIT rougir (0 décodage Q65 ou calls ≠ attendus). Restaurer, vérifier vert + md5.

- [ ] **Step 7: Commit**

```bash
git add concours/logx_q65_natif.py concours/tests/test_q65_natif.py concours/tests/fixtures/q65_60A_eme_6m.wav
git commit -m "feat(q65-natif): runner jt9 subprocess + test integration echantillon EME"
```

---

### Task 3: Bornes de fenêtre UTC + écriture WAV 12 kHz

**Files:**
- Modify: `concours/logx_q65_natif.py`
- Test: `concours/tests/test_q65_natif.py`

**Interfaces:**
- Produces:
  `bornes_fenetre(now: float, tr_period: int = 60) -> tuple[float, float]` — début/fin epoch de la fenêtre T/R **alignée** (ex. tr_period=60 → alignée sur la minute UTC pleine).
  `ecrire_wav_12k(path: str, echantillons: bytes) -> None` — écrit un WAV PCM 16 bit **mono 12000 Hz** à partir d'octets int16 little-endian.

- [ ] **Step 1: Écrire les tests qui échouent**

```python
import wave

def test_bornes_fenetre_alignee_minute():
    # 12:34:37.5 UTC → fenêtre [12:34:00, 12:35:00)
    now = 1_000_000_000 + 37.5  # peu importe l'instant exact
    deb, fin = q65n.bornes_fenetre(now, tr_period=60)
    assert deb <= now < fin
    assert fin - deb == 60
    assert int(deb) % 60 == 0            # alignée sur la minute
    assert int(fin) % 60 == 0

def test_ecrire_wav_12k(tmp_path):
    p = str(tmp_path / 'x.wav')
    q65n.ecrire_wav_12k(p, b'\x00\x00' * 12000)   # 1 s de silence
    with wave.open(p, 'rb') as w:
        assert w.getframerate() == 12000
        assert w.getnchannels() == 1
        assert w.getsampwidth() == 2
        assert w.getnframes() == 12000
```

- [ ] **Step 2: Lancer, vérifier l'échec**

Run: `cd concours && python -m pytest tests/test_q65_natif.py -k "bornes or ecrire" -v`
Expected: FAIL (fonctions non définies).

- [ ] **Step 3: Implémenter**

```python
import wave


def bornes_fenetre(now, tr_period=60):
    """Début/fin (epoch) de la fenêtre T/R alignée contenant `now`."""
    tr = int(tr_period)
    debut = (int(now) // tr) * tr
    return float(debut), float(debut + tr)


def ecrire_wav_12k(path, echantillons):
    """WAV PCM 16 bit mono 12 kHz — format d'entrée attendu par jt9."""
    with wave.open(path, 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(12000)
        w.writeframes(echantillons)
```

- [ ] **Step 4: Lancer, vérifier le succès**

Run: `cd concours && python -m pytest tests/test_q65_natif.py -k "bornes or ecrire" -v`
Expected: PASS.

- [ ] **Step 5: Contre-épreuve**

Muter `setframerate(12000)` en `setframerate(48000)`. Le test rougit. Restaurer, vérifier md5.

- [ ] **Step 6: Commit**

```bash
git add concours/logx_q65_natif.py concours/tests/test_q65_natif.py
git commit -m "feat(q65-natif): bornes fenetre UTC + ecriture WAV 12kHz"
```

---

### Task 4: Adaptateur de capture carte son (sounddevice)

**Files:**
- Modify: `concours/logx_q65_natif.py`
- Modify: `concours/requirements.txt` (ou l'endroit où les dépendances runtime sont déclarées — vérifier lequel avant d'ajouter)

**Interfaces:**
- Produces:
  `lister_peripheriques_entree() -> list[dict]` — `[{'index': int, 'nom': str, 'canaux': int, 'freq_defaut': int}]`.
  `class FluxCapture` — `__init__(self, device_index: int | None, on_fenetre: callable)` ; `demarrer()` / `arreter()`. Ouvre un flux 12 kHz mono, accumule les échantillons, et à chaque fenêtre `bornes_fenetre` complète appelle `on_fenetre(echantillons_bytes: bytes, t_debut: float)`.

> **Test :** pas de test unitaire simulant du matériel (interdit par la règle « pas de test contre un mannequin »). `lister_peripheriques_entree()` est vérifié manuellement ; `FluxCapture` est validé par la vérification d'intégration de Task 5. Fournir à la place un test que le module s'importe sans erreur même si `sounddevice` est absent (import paresseux).

- [ ] **Step 1: Décider et déclarer la dépendance**

Vérifier où sont déclarées les dépendances runtime (chercher `requirements*.txt` / `pyproject.toml`). Ajouter `sounddevice` (PortAudio). Import **paresseux** dans le module pour ne pas casser l'app si la lib manque (le natif est opt-in).

- [ ] **Step 2: Test « import sans sounddevice »**

```python
def test_module_importe_sans_sounddevice(monkeypatch):
    import importlib, builtins
    reel = builtins.__import__
    def faux(nom, *a, **k):
        if nom == 'sounddevice':
            raise ImportError('simulé')
        return reel(nom, *a, **k)
    monkeypatch.setattr(builtins, '__import__', faux)
    importlib.reload(q65n)              # ne doit PAS lever
    assert hasattr(q65n, 'parse_jt9_stdout')
    importlib.reload(q65n)              # rétablir l'état normal
```

- [ ] **Step 3: Lancer → doit échouer si l'import de sounddevice est au niveau module**

Run: `cd concours && python -m pytest tests/test_q65_natif.py -k import_sans -v`
Expected: FAIL tant que `import sounddevice` est en tête de module.

- [ ] **Step 4: Implémenter avec import paresseux**

```python
def _sd():
    import sounddevice as sd   # import paresseux : opt-in
    return sd


def lister_peripheriques_entree():
    sd = _sd()
    out = []
    for i, d in enumerate(sd.query_devices()):
        if d.get('max_input_channels', 0) > 0:
            out.append({'index': i, 'nom': d['name'],
                        'canaux': d['max_input_channels'],
                        'freq_defaut': int(d.get('default_samplerate', 0))})
    return out


class FluxCapture:
    """Capte une entrée audio en 12 kHz mono et livre des fenêtres T/R
    complètes à `on_fenetre`. Ne fait AUCUN décodage lui-même."""
    def __init__(self, device_index, on_fenetre, tr_period=60):
        self.device_index = device_index
        self.on_fenetre = on_fenetre
        self.tr_period = tr_period
        self._stream = None
        self._buf = bytearray()
        self._fenetre = None

    def demarrer(self):
        sd = _sd()
        self._stream = sd.RawInputStream(
            samplerate=12000, channels=1, dtype='int16',
            device=self.device_index, callback=self._cb)
        self._stream.start()

    def _cb(self, indata, frames, time_info, status):
        now = time.time()
        deb, _ = bornes_fenetre(now, self.tr_period)
        if self._fenetre is None:
            self._fenetre = deb
        if deb != self._fenetre:                 # fenêtre terminée
            self.on_fenetre(bytes(self._buf), self._fenetre)
            self._buf = bytearray()
            self._fenetre = deb
        self._buf += bytes(indata)

    def arreter(self):
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None
```

- [ ] **Step 5: Lancer, vérifier le succès + vérif manuelle**

Run: `cd concours && python -m pytest tests/test_q65_natif.py -k import_sans -v` → PASS.
Vérif manuelle (si carte son dispo) : `python -c "import logx_q65_natif as q; print(q.lister_peripheriques_entree())"` liste au moins une entrée.

- [ ] **Step 6: Commit**

```bash
git add concours/logx_q65_natif.py concours/tests/test_q65_natif.py concours/requirements.txt
git commit -m "feat(q65-natif): capture carte son 12kHz (import paresseux, opt-in)"
```

---

### Task 5: Orchestrateur + cache TTL `decodes_natifs()`

**Files:**
- Modify: `concours/logx_q65_natif.py`
- Test: `concours/tests/test_q65_natif.py`

**Interfaces:**
- Consumes: `decoder_wav(...)`, `ecrire_wav_12k(...)`, `FluxCapture`, `bornes_fenetre(...)`.
- Produces:
  `demarrer_moteur(cfg: dict) -> dict` / `arreter_moteur() -> dict` (état).
  `decodes_natifs(max_age: float = wsjtx._DECODE_TTL) -> list[dict]` — décodages récents (mêmes clés que `wsjtx.eme_decodes()`), purge au-delà de `max_age`.
  `_traiter_fenetre(echantillons: bytes, t_debut: float, cfg: dict) -> None` — écrit le wav, décode, insère au cache (testé directement, sans matériel).

- [ ] **Step 1: Écrire le test qui échoue (sans matériel : on injecte le décodage)**

```python
def test_traiter_fenetre_alimente_le_cache(monkeypatch, tmp_path):
    q65n.arreter_moteur()  # état propre
    faux = [{'call': 'DL7APV', 'grid': 'JO62', 'mode': 'Q65',
             'message': 'CQ DL7APV JO62', 'snr': -21, 'dt': 2.7,
             'delta_hz': 800, 'freq_mhz': 144.124, 'band': '2m',
             'last_seen': 5000.0}]
    monkeypatch.setattr(q65n, 'decoder_wav', lambda *a, **k: faux)
    monkeypatch.setattr(q65n, 'ecrire_wav_12k', lambda *a, **k: None)
    cfg = {'eme': {'submode': 'A', 'band': '2m', 'rf_mhz': 144.124}}
    q65n._traiter_fenetre(b'\x00\x00' * 10, 5000.0, cfg)
    d = q65n.decodes_natifs(max_age=10_000)
    assert [x['call'] for x in d] == ['DL7APV']
    assert d[0]['mode'] == 'Q65'

def test_decodes_natifs_purge_les_vieux(monkeypatch):
    q65n.arreter_moteur()
    vieux = [{'call': 'OLD', 'mode': 'Q65', 'message': '', 'snr': -20,
              'dt': 0.0, 'delta_hz': 0, 'grid': '', 'freq_mhz': 0.0,
              'band': '', 'last_seen': 1.0}]
    monkeypatch.setattr(q65n, 'decoder_wav', lambda *a, **k: vieux)
    monkeypatch.setattr(q65n, 'ecrire_wav_12k', lambda *a, **k: None)
    q65n._traiter_fenetre(b'', 1.0, {'eme': {}})
    assert q65n.decodes_natifs(max_age=1) == []   # trop vieux → purgé
```

- [ ] **Step 2: Lancer, vérifier l'échec**

Run: `cd concours && python -m pytest tests/test_q65_natif.py -k "traiter or purge" -v`
Expected: FAIL.

- [ ] **Step 3: Implémenter l'orchestrateur**

```python
import os
import tempfile
import threading

_cache = []                 # liste de décodages récents
_cache_lock = threading.Lock()
_flux = None


def _traiter_fenetre(echantillons, t_debut, cfg):
    eme = (cfg or {}).get('eme', {}) or {}
    submode = eme.get('submode', 'A')
    band = eme.get('band', '')
    rf = float(eme.get('rf_mhz', 0.0) or 0.0)
    tmpdir = tempfile.mkdtemp(prefix='logx_q65_')
    wav = os.path.join(tmpdir, 'seg.wav')
    ecrire_wav_12k(wav, echantillons)
    decs = decoder_wav(wav, submode=submode, tr_period=int(eme.get('tr_period', 60)),
                       jt9_path=eme.get('jt9_path'), data_path=tmpdir,
                       freq_mhz=rf, band=band)
    with _cache_lock:
        _cache.extend(decs)


def decodes_natifs(max_age=wsjtx._DECODE_TTL):
    limite = time.time() - max_age
    with _cache_lock:
        _cache[:] = [d for d in _cache if d.get('last_seen', 0) >= limite]
        return list(_cache)


def demarrer_moteur(cfg):
    global _flux
    if _flux is not None:
        return {'ok': True, 'deja': True}
    idx = ((cfg or {}).get('eme', {}) or {}).get('audio_device')
    _flux = FluxCapture(idx, lambda ech, t: _traiter_fenetre(ech, t, cfg),
                        tr_period=int((cfg.get('eme', {}) or {}).get('tr_period', 60)))
    _flux.demarrer()
    return {'ok': True}


def arreter_moteur():
    global _flux
    if _flux is not None:
        _flux.arreter()
        _flux = None
    with _cache_lock:
        _cache.clear()
    return {'ok': True}
```

- [ ] **Step 4: Lancer, vérifier le succès**

Run: `cd concours && python -m pytest tests/test_q65_natif.py -v`
Expected: PASS (tous).

- [ ] **Step 5: Contre-épreuve**

Muter la purge : `>= limite` → `>= 0`. `test_decodes_natifs_purge_les_vieux` DOIT rougir. Restaurer, md5.

- [ ] **Step 6: Commit**

```bash
git add concours/logx_q65_natif.py concours/tests/test_q65_natif.py
git commit -m "feat(q65-natif): orchestrateur + cache TTL decodes_natifs()"
```

---

### Task 6: Sélection de source dans `_eme_cockpit_dict`

**Files:**
- Modify: `concours/logx_http.py:2197-2209`
- Modify: `concours/config.example.json`
- Test: `concours/tests/test_eme_source_selection.py` (nouveau)

**Interfaces:**
- Consumes: `logx_q65_natif.decodes_natifs()`, `logx_wsjtx.eme_decodes()`.
- Produces: `_eme_cockpit_dict` renvoie `decodes` issus de la source configurée (`cfg.eme.source` ∈ {`'wsjtx'` (défaut), `'natif'`}).

- [ ] **Step 1: Écrire le test qui échoue**

```python
# concours/tests/test_eme_source_selection.py
import os, sys
CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CONCOURS not in sys.path:
    sys.path.insert(0, CONCOURS)
import logx_http, logx_wsjtx, logx_q65_natif  # noqa: E402


def test_source_defaut_wsjtx(monkeypatch):
    monkeypatch.setattr(logx_wsjtx, 'eme_decodes', lambda *a, **k: [{'call': 'UDP'}])
    monkeypatch.setattr(logx_q65_natif, 'decodes_natifs', lambda *a, **k: [{'call': 'NATIF'}])
    d = logx_http._eme_cockpit_dict({'locator': '', 'eme': {}}, '2m')
    assert [x['call'] for x in d['decodes']] == ['UDP']


def test_source_natif_si_configuree(monkeypatch):
    monkeypatch.setattr(logx_wsjtx, 'eme_decodes', lambda *a, **k: [{'call': 'UDP'}])
    monkeypatch.setattr(logx_q65_natif, 'decodes_natifs', lambda *a, **k: [{'call': 'NATIF'}])
    d = logx_http._eme_cockpit_dict({'locator': '', 'eme': {'source': 'natif'}}, '2m')
    assert [x['call'] for x in d['decodes']] == ['NATIF']
```

- [ ] **Step 2: Lancer, vérifier l'échec**

Run: `cd concours && python -m pytest tests/test_eme_source_selection.py -v`
Expected: FAIL (`test_source_natif_si_configuree` : la sélection n'existe pas encore, renvoie 'UDP').

- [ ] **Step 3: Implémenter la sélection**

Dans `_eme_cockpit_dict`, remplacer la ligne `'decodes': wsjtx.eme_decodes(),` par une variable calculée juste avant le `return` :

```python
    src = ((cfg_snap or {}).get('eme', {}) or {}).get('source', 'wsjtx')
    if src == 'natif':
        import logx_q65_natif as q65n
        decodes = q65n.decodes_natifs()
    else:
        decodes = wsjtx.eme_decodes()
```
et `'decodes': decodes,` dans le dict retourné.

- [ ] **Step 4: Lancer, vérifier le succès**

Run: `cd concours && python -m pytest tests/test_eme_source_selection.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Contre-épreuve**

Forcer `src = 'wsjtx'` en dur. `test_source_natif_si_configuree` rougit. Restaurer, md5.

- [ ] **Step 6: Documenter la config**

Dans `concours/config.example.json`, ajouter une section commentée :
```json
"eme": { "source": "wsjtx", "audio_device": null, "submode": "A", "tr_period": 60, "jt9_path": null }
```

- [ ] **Step 7: Commit**

```bash
git add concours/logx_http.py concours/config.example.json concours/tests/test_eme_source_selection.py
git commit -m "feat(q65-natif): selection source EME (wsjtx|natif) dans le cockpit"
```

---

### Task 7: UI CONFIG — sélecteur de source + carte son (expert-only)

**Files:**
- Modify: `concours/logx_configuration.html`
- Modify: `concours/logx_configuration.js`
- Modify: `concours/logx_http.py` (endpoints `GET /eme/audio-devices`, `POST /eme/moteur`)

**Interfaces:**
- Produces (endpoints) :
  `GET /eme/audio-devices` → `{'devices': [ {index,nom,canaux,freq_defaut} ]}` (via `logx_q65_natif.lister_peripheriques_entree()`).
  `POST /eme/moteur` body `{'action':'start'|'stop'}` → `demarrer_moteur(cfg)` / `arreter_moteur()`.

> **Test :** l'UI relève de la plomberie station ; pas de test JS neuf ici (cf. règles du dépôt sur les tests JS). Vérification par les tests Python des endpoints + revue visuelle. Placer les contrôles sous `expert-only` (source EME + carte son = résidu « plomberie de station », pas chemin critique). Icônes : suivre la convention SVG monochrome ; si un libellé est réécrit en JS via `.textContent`, laisser l'emoji (piège documenté dans CLAUDE.md).

- [ ] **Step 1: Endpoint liste des périphériques (test Python d'abord)**

Écrire un test qui appelle le handler et vérifie la forme `{'devices': [...]}` en monkeypatchant `lister_peripheriques_entree`. Lancer → échec.

- [ ] **Step 2: Implémenter les deux endpoints** dans le routeur de `logx_http.py` (suivre le motif d'un endpoint EME existant, ex. `/eme/cockpit`). Relancer → succès. Contre-épreuve sur la forme de sortie.

- [ ] **Step 3: Bloc UI CONFIG** : dans la section EME/plomberie de `logx_configuration.html`, ajouter (classe `expert-only`) un `<select>` source (WSJT-X / LogX natif), un `<select>` carte son peuplé via `GET /eme/audio-devices`, un `<select>` sous-mode, et un bouton Démarrer/Arrêter appelant `POST /eme/moteur`. Câbler dans `logx_configuration.js` en suivant le motif de sauvegarde config existant.

- [ ] **Step 4: Vérification manuelle** : la page CONFIG affiche les contrôles en mode expert, masqués en mode simple ; sélectionner « LogX natif » + une carte son, Démarrer, et confirmer que le cockpit EME affiche des décodages issus du natif.

- [ ] **Step 5: Commit**

```bash
git add concours/logx_configuration.html concours/logx_configuration.js concours/logx_http.py concours/tests/
git commit -m "feat(q65-natif): UI CONFIG source EME + carte son + endpoints moteur"
```

---

### Task 8: Embarquer `jt9` vanilla K1JT dans les releases (multi-OS)

**Files:**
- Modify: `.github/workflows/build-release.yml`
- Create: `concours/vendor/jt9/README.md` (provenance, version, licence GPLv3, lien source)

> **Note de séquencement :** Tasks 1-7 sont fonctionnelles et testables **sans** cette tâche (via `eme.jt9_path` pointant sur un `jt9` local). Cette tâche rend le natif utilisable par un utilisateur qui n'a PAS WSJT-X. Elle peut être livrée séparément.

- [ ] **Step 1** : Déterminer la version WSJT-X vanilla cible et l'emplacement de ses binaires `jt9` + dépendances (DLL FFTW, runtime Fortran/C) par OS. Documenter dans `vendor/jt9/README.md` (version exacte, URL source, licence).
- [ ] **Step 2** : Adapter `build-release.yml` pour récupérer/empaqueter le `jt9` de l'OS courant sous `concours/vendor/jt9/` dans chaque artefact (Win/macOS/Linux).
- [ ] **Step 3** : Vérifier que `resoudre_jt9()` (Task 2) trouve bien le binaire embarqué quand `eme.jt9_path` est nul, sur une machine SANS WSJT-X installé.
- [ ] **Step 4** : Respect GPL : s'assurer que la source correspondante de `jt9` est offerte (lien + version figés dans le README vendor) et les copyrights conservés.
- [ ] **Step 5: Commit**

```bash
git add .github/workflows/build-release.yml concours/vendor/jt9/README.md
git commit -m "build(q65-natif): embarquer jt9 vanilla GPLv3 dans les releases"
```

---

## Auto-revue (couverture spec)

- **§4 réception Q65 hors-ligne** → Tasks 1-5 (parser, runner, segmenteur, capture, orchestrateur).
- **§5.1 source additionnelle opt-in** → Task 6 (défaut `wsjtx`) + Task 7 (UI).
- **§5.2 jt9 vanilla embarqué** → Task 8 (+ `resoudre_jt9` Task 2).
- **§6.1 capture audio = vrai travail** → Tasks 3-4-5.
- **§3.1 format de sortie** → Task 1 (stdout ; note : `q65_decodes.txt`/confiance = enrichissement ultérieur, non requis par le cockpit).
- **§7 tests témoin vert + mutation** → contre-épreuve dans chaque task testable ; fixture EME réelle (Task 2).
- **§3.2 KVASD / JT65** → hors périmètre (Global Constraints), aucune task JT65. ✔
- **Émission** → hors périmètre, aucune task TX. ✔

Types vérifiés cohérents entre tasks : `parse_jt9_stdout`, `decoder_wav`, `resoudre_jt9`, `bornes_fenetre`, `ecrire_wav_12k`, `FluxCapture`, `demarrer_moteur`/`arreter_moteur`/`decodes_natifs`, `_traiter_fenetre`, `lister_peripheriques_entree` — noms et signatures identiques partout.
