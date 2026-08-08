# -*- coding: utf-8 -*-
"""Publication MQTT optionnelle des événements du shack — QSO loggués,
fréquence radio courante, score du concours en cours — vers un broker LOCAL
(Mosquitto, ou tout broker MQTT du réseau) pour un tableau de bord externe
(Node-RED, Home Assistant, OBS...) sans coupler LogX à un outil précis.

DÉSACTIVÉE PAR DÉFAUT. Dépendance paho-mqtt OPTIONNELLE (voir requirements.txt,
non installée par défaut) : si le paquet est absent, toute l'API de ce module
reste appelable sans jamais lever d'exception — elle ne fait simplement rien
(HAS_PAHO=False). Même politique de dégradation que pyserial/pyttsx3/ephem
ailleurs dans le projet (cf. logx_cat.HAS_PYSERIAL, logx_eme.HAS_EPHEM).

Topics publiés (préfixe configurable, "logx" par défaut) :
  <préfixe>/qso        JSON du QSO qui vient d'être loggué.
  <préfixe>/rig/freq   {freq_khz, mode} — fréquence radio courante.
  <préfixe>/score      {score, contest} — score total du concours en cours.

Publication fire-and-forget, JAMAIS dans le thread HTTP : une fois connecté,
paho gère sa propre boucle réseau (connexion/reconnexion) dans un thread
interne à la lib (loop_start()) ; publish() ne fait que déposer le message
dans une file interne et revient immédiatement, sans E/S bloquante. Les
appelants (logx_http.py) enveloppent malgré tout chaque appel dans un thread
démon, par cohérence avec le même schéma déjà utilisé pour Club Log Live/QRZ
Logbook/réseau ADIF dans add_qso_to_log() — fire-and-forget explicite, pas de
confiance aveugle dans le comportement interne d'une lib tierce."""
import json
import threading
import uuid

try:
    import paho.mqtt.client as mqtt
    HAS_PAHO = True
except Exception:
    mqtt = None
    HAS_PAHO = False

DEFAULT_PORT = 1883

_INSTANCE_ID = uuid.uuid4().hex[:8]  # id unique par process — voir _ensure_client

_client = None
_client_target = None      # (host, port) actuellement connecté — voir _ensure_client
_client_lock = threading.Lock()

_last_freq_khz = None       # anti-spam de /rig/freq — voir freq_changed()
_freq_lock = threading.Lock()


def mqtt_settings(cfg):
    """Même schéma que wsjtx_settings()/rig_settings() (logx_wsjtx.py) :
    enabled/host/port/prefix lus depuis la config passée, avec repli sur
    config.json (poste qui redémarre sans repasser par /config/save)."""
    cfg = cfg or {}
    enabled = bool(cfg.get('mqtt_enabled'))
    host = cfg.get('mqtt_host')
    port = cfg.get('mqtt_port')
    prefix = cfg.get('mqtt_topic_prefix')
    if not enabled or not host:
        try:
            with open('config.json', encoding='utf-8') as f:
                m = (json.load(f).get('mqtt', {}) or {})
            enabled = enabled or bool(m.get('enabled'))
            host = host or m.get('host')
            port = port or m.get('port')
            prefix = prefix or m.get('topic_prefix')
        except Exception:
            pass
    try:
        port = int(port)
    except (TypeError, ValueError):
        port = DEFAULT_PORT
    return {'enabled': enabled, 'host': (host or 'localhost').strip(),
            'port': port, 'prefix': (prefix or 'logx').strip().strip('/') or 'logx'}


def _ensure_client(settings):
    """(Re)crée le client paho et démarre sa boucle réseau en tâche de fond
    si besoin (idempotent — ne reconnecte pas si host/port n'ont pas changé
    depuis le dernier appel). connect_async() ne fait QUE mémoriser les
    paramètres de connexion (aucune E/S, pas de résolution DNS synchrone) ;
    la connexion/reconnexion réelle est déléguée au thread interne démarré
    par loop_start() — cet appel ne bloque donc jamais l'appelant, même sur
    un broker injoignable ou un DNS muet (même principe que fetch_url()
    ailleurs dans le projet, mais ici c'est paho qui gère le thread)."""
    global _client, _client_target
    target = (settings['host'], settings['port'])
    with _client_lock:
        if _client is not None and _client_target == target:
            return _client
        if _client is not None:
            try:
                _client.loop_stop()
                _client.disconnect()
            except Exception:
                pass
            _client = None
            _client_target = None
        try:
            c = mqtt.Client(client_id=f'logx-ai-{_INSTANCE_ID}', clean_session=True)
            c.connect_async(target[0], target[1], keepalive=30)
            c.loop_start()
            _client = c
            _client_target = target
            print(f"[MQTT] Connexion vers {target[0]}:{target[1]} lancée en tâche de fond")
        except Exception as e:
            print(f"[MQTT] Impossible d'initialiser le client ({target[0]}:{target[1]}) : {e}")
            _client = None
            _client_target = None
    return _client


def _publish(cfg, topic_suffix, payload):
    """Publication best-effort — ne lève JAMAIS : un broker injoignable ou
    paho absent ne doit pas faire échouer le log d'un QSO ni l'affichage du
    score. Silencieux si MQTT désactivé ou le paquet optionnel non installé."""
    if not HAS_PAHO:
        return
    settings = mqtt_settings(cfg)
    if not settings['enabled']:
        return
    topic = f"{settings['prefix']}/{topic_suffix}"
    try:
        client = _ensure_client(settings)
        if client is None:
            return
        body = payload if isinstance(payload, (str, bytes)) else json.dumps(payload, ensure_ascii=False)
        client.publish(topic, body, qos=0, retain=False)
    except Exception as e:
        print(f"[MQTT] Publication '{topic}' abandonnée : {e}")


def publish_qso(cfg, qso):
    """Topic <préfixe>/qso — un message par QSO loggué (saisie manuelle,
    WSJT-X, réseau ADIF...), quelle que soit la source (voir add_qso_to_log
    dans logx_http.py, chemin commun à toutes les sources d'insertion)."""
    qso = qso or {}
    payload = {k: qso.get(k) for k in (
        'call', 'band', 'mode', 'date', 'time', 'rst_sent', 'rst_rcvd',
        'locator', 'points', 'contest', 'operator') if qso.get(k) is not None}
    if 'operator' in payload:
        # Jamais l'ID de créneau brut ('OP1') vers un tableau de bord tiers
        # (Node-RED, Home Assistant, overlay de streaming...) — même bug que
        # LOGBOOK/export ADIF, voir logx_export.resolve_operator_callsign.
        from logx_export import resolve_operator_callsign
        payload['operator'] = resolve_operator_callsign(payload['operator'], cfg or {})
    _publish(cfg, 'qso', payload)


def publish_score(cfg, score, contest=''):
    """Topic <préfixe>/score — score total du concours en cours (portée
    active, voir qso_scope_id), publié à chaque QSO ajouté."""
    _publish(cfg, 'score', {'score': score, 'contest': contest})


def publish_rig_freq(cfg, freq_khz, mode=''):
    """Topic <préfixe>/rig/freq — fréquence radio courante (kHz). À appeler
    seulement après freq_changed() côté appelant (évite de publier à chaque
    poll du logbook alors que la radio n'a pas bougé)."""
    _publish(cfg, 'rig/freq', {'freq_khz': freq_khz, 'mode': mode})


def freq_changed(freq_khz, tolerance=0.05):
    """Vrai seulement si `freq_khz` diffère réellement de la dernière valeur
    publiée — évite de publier (et de créer un thread démon) à chaque poll du
    logbook (3 s de cadence rapide, voir adaptivePoll côté client) alors que
    la radio n'a pas bougé depuis le cycle précédent."""
    global _last_freq_khz
    if freq_khz is None:
        return False
    with _freq_lock:
        if _last_freq_khz is not None and abs(_last_freq_khz - freq_khz) < tolerance:
            return False
        _last_freq_khz = freq_khz
        return True
