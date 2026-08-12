# -*- coding: utf-8 -*-
"""Pilotage CAT via OmniRig (VE3NEA) — backend candidat pour rejoindre
logx_cat (série natif), logx_tci (WebSocket), logx_rig (rigctld/Hamlib) et
logx_flrig (XML-RPC). PAS ENCORE câblé dans le dispatch HTTP/CONFIG à ce
stade (aucun appel depuis logx_cat.py ni depuis le serveur HTTP) : ce module
est autonome et testé isolément, le branchement dans le dispatch existant
sera fait dans un commit séparé — ne pas supposer qu'un réglage
`omnirig_enabled` dans CONFIG a un quelconque effet côté serveur avant ça.

OmniRig est un composant COM Windows autonome, très répandu chez les
utilisateurs de loggers de contest (il tourne déjà en tâche de fond chez
beaucoup d'opérateurs, souvent lancé par un autre logiciel comme N1MM+) :
il dialogue lui-même en série avec la radio et expose un objet COM
"OmniRig.OmniRigX" que d'autres programmes pilotent — LogX est ici un pur
CLIENT COM, jamais un serveur : OmniRig doit déjà tourner et être configuré
côté opérateur (port série, marque/modèle) pour Rig1 et/ou Rig2.

Sources vérifiées via WebFetch pendant l'implémentation, contre le fichier
IDL officiel du dépôt (github.com/VE3NEA/OmniRig, OmniRig.ridl) :
  - coclass OmniRigX, uuid 0839E8C6-ED30-4950-8087-966F970F0CAE — objet COM
    créable, propriétés Rig1/Rig2 (interface IRigX) sur l'objet racine
    IOmniRigX.
  - IRigX : RigType (BSTR), Status (RigStatusX), StatusStr (BSTR),
    Freq/FreqA/FreqB (long, Hz, get/put), Mode (RigParamX, get/put),
    Tx (RigParamX, get/put — PM_RX/PM_TX).
  - enum RigParamX (bitmask, valeurs numériques confirmées dans le .ridl) :
    PM_RX=2097152, PM_TX=4194304, PM_CW_U=8388608, PM_CW_L=16777216,
    PM_SSB_U=33554432, PM_SSB_L=67108864, PM_DIG_U=134217728,
    PM_DIG_L=268435456, PM_AM=536870912, PM_FM=1073741824.
  - enum RigStatusX : ST_NOTCONFIGURED=0, ST_DISABLED=1, ST_PORTBUSY=2,
    ST_NOTRESPONDING=3, ST_ONLINE=4 — seul ST_ONLINE garantit une radio qui
    répond réellement.
Binding Python communautaire consulté pour la forme générale de l'API
(getParam/setFrequency/setMode/setTx/setRx) : github.com/4Z1KD/omnipyrig
(son README ne montre qu'un wrapper haut niveau, pas les noms de propriétés
COM bruts — c'est le .ridl officiel ci-dessus qui fait foi ici).

⚠️ PAS vérifié par WebFetch, à confirmer sur un vrai poste Windows avant
usage réel : le ProgID exact "OmniRig.OmniRigX" passé à
win32com.client.Dispatch(). Il n'apparaît pas littéralement dans l'extrait
du .ridl récupéré (qui donne le nom de coclass "OmniRigX" et son CLSID, pas
la chaîne ProgID telle qu'enregistrée dans le registre Windows) — c'est la
convention standard "<TypeLib>.<CoClass>" (le typelib s'appelle "OmniRig")
ET la valeur donnée explicitement dans les instructions de ce chantier,
mais aucune des deux sources n'est une confirmation indépendante à 100 %.

Pas de socket réseau ici (composant COM local, pas de DNS/TCP) : le point
d'injection pour les tests est `_open_com`, une fabrique sans argument
renvoyant un objet exposant .Rig1/.Rig2 — même principe que `_open_ws` dans
logx_tci.py. Chaque appel COM tourne sur un fil dédié borné dans le temps
(ThreadPoolExecutor à 1 worker, voir logx_rotor.py pour le même motif) :
un objet COM en appartement mono-thread (le comportement par défaut de
win32com.client.Dispatch()) doit être créé ET utilisé sur le MÊME thread
du début à la fin, donc pas de connexion persistante partagée entre appels
HTTP ici (contrairement à logx_tci) — chaque appel redispatch un objet
frais, ce qui reste bon marché puisqu'OmniRig est un serveur COM déjà
démarré localement.
"""
import concurrent.futures as _cf
import threading as _threading

try:
    import win32com.client as _win32com_client
    HAS_PYWIN32 = True
except ImportError:
    HAS_PYWIN32 = False

OMNIRIG_PROGID = 'OmniRig.OmniRigX'
TIMEOUT_S = 3.0

# ── enum RigParamX (bitmask) — voir docstring de module pour la source ──────
PM_RX = 2097152
PM_TX = 4194304
PM_CW_U = 8388608
PM_CW_L = 16777216
PM_SSB_U = 33554432
PM_SSB_L = 67108864
PM_DIG_U = 134217728
PM_DIG_L = 268435456
PM_AM = 536870912
PM_FM = 1073741824

# Mode OmniRig (RigParamX) <-> chaîne normalisée LogX (voir CIV_MODES dans
# logx_cat.py pour la même famille de noms : LSB/USB/CW/CW-R/RTTY/FM/AM).
# OmniRig ne distingue pas les modes numériques entre eux (FT8/PSK/RTTY...) :
# PM_DIG_U/PM_DIG_L couvrent tout mode "données" bande latérale haute/basse
# tel que vu par le rig — mappé sur 'DATA'/'DATA-R', pas 'RTTY', pour ne pas
# laisser croire à une distinction que le protocole n'offre pas.
MODE_TO_PARAM = {
    'CW': PM_CW_U, 'CW-R': PM_CW_L,
    'USB': PM_SSB_U, 'LSB': PM_SSB_L,
    'DATA': PM_DIG_U, 'DATA-R': PM_DIG_L,
    'AM': PM_AM, 'FM': PM_FM,
}
PARAM_TO_MODE = {v: k for k, v in MODE_TO_PARAM.items()}

# ── enum RigStatusX ──────────────────────────────────────────────────────────
ST_NOTCONFIGURED = 0
ST_DISABLED = 1
ST_PORTBUSY = 2
ST_NOTRESPONDING = 3
ST_ONLINE = 4

_STATUS_LABELS = {
    ST_NOTCONFIGURED: "rig non configuré dans OmniRig",
    ST_DISABLED: "rig désactivé dans OmniRig",
    ST_PORTBUSY: "port série occupé par un autre programme",
    ST_NOTRESPONDING: "radio ne répond pas (câble débranché, radio éteinte, mauvais port ?)",
    ST_ONLINE: "en ligne",
}


def _status_label(status):
    try:
        status = int(status)
    except (TypeError, ValueError):
        return 'statut illisible (%r)' % (status,)
    return _STATUS_LABELS.get(status, 'statut inconnu (%d)' % status)


def _default_dispatch():
    return _win32com_client.Dispatch(OMNIRIG_PROGID)


# Point d'injection pour les tests (voir docstring de module) : remplacer par
# une fabrique qui renvoie un faux objet exposant .Rig1/.Rig2, chacun avec les
# mêmes attributs qu'IRigX (Status, Freq, Mode, Tx, RigType...), sans jamais
# toucher un vrai objet COM/registre Windows.
_open_com = _default_dispatch if HAS_PYWIN32 else None

_EXECUTOR = _cf.ThreadPoolExecutor(max_workers=1, thread_name_prefix='omnirig_cat')

# ── auto-guérison de l'executor après des timeouts consécutifs ─────────────
# Contrairement à un socket (settimeout() libère réellement le thread), un
# appel COM bloqué (boîte de dialogue modale d'OmniRig, port série gelé côté
# OmniRig) ne peut PAS être interrompu depuis l'extérieur : le worker reste
# bloqué pour de vrai, indéfiniment. Avec 1 seul worker, UN SEUL blocage
# épuise l'executor pour toujours — tous les appels suivants échoueraient
# proprement mais le module deviendrait silencieusement inopérant jusqu'au
# redémarrage du process. On garde donc un compteur de timeouts CONSÉCUTIFS
# (protégé par _executor_lock, qui protège aussi l'accès à _EXECUTOR
# lui-même) : au-delà du seuil, on abandonne le worker bloqué à son sort
# (il finira par se terminer seul si l'appel COM revient un jour, ou restera
# fantôme jusqu'à la fin du process — mais il ne bloque plus rien puisque
# plus aucun nouvel appel ne lui est soumis) et on le remplace par un
# ThreadPoolExecutor tout neuf.
_executor_lock = _threading.Lock()
_consecutive_timeouts = 0
_TIMEOUT_THRESHOLD = 3


def _norm_rig_num(value):
    try:
        n = int(value)
    except (TypeError, ValueError):
        return 1
    return 2 if n == 2 else 1


def omnirig_settings(cfg):
    """Réglages OmniRig depuis la config CLIENT — jamais d'exception, valeurs
    par défaut sûres même sur cfg vide ou None (règle #4 du chantier).
    `enabled` est un interrupteur DÉDIÉ à ce sous-système (comme
    rotor_enabled dans logx_rotor.py) : le choix du backend CAT actif
    ('native'/'tci'/'rigctld'/'flrig'/'omnirig') reste porté séparément par
    cat_settings() de logx_cat — ce module ne fait que refuser d'agir si son
    propre interrupteur est resté à False, en ceinture-et-bretelles."""
    cfg = cfg or {}
    return {
        'enabled': bool(cfg.get('omnirig_enabled')),
        'rig_num': _norm_rig_num(cfg.get('omnirig_rig_num')),
    }


def _do_com_call(rig_num, func):
    """Exécute `func(rig)` sur un objet COM Rig1/Rig2 fraîchement dispatché.
    Tourne ENTIÈREMENT sur le thread qui l'appelle (voir _com_call : toujours
    soumis à l'executor dédié à 1 worker) — CoInitialize/CoUninitialize et la
    création de l'objet COM restent sur le même thread OS du début à la fin,
    condition nécessaire pour un objet en appartement mono-thread."""
    if _open_com is None:
        return {'ok': False, 'error': "pywin32 n'est pas installé — OmniRig nécessite le paquet "
                "pywin32 (pip install pywin32), Windows uniquement"}
    need_couninit = False
    try:
        import pythoncom
        pythoncom.CoInitialize()
        need_couninit = True
    except Exception:
        pass  # pythoncom absent (test/CI non-Windows), ou déjà initialisé sur ce thread
    try:
        omnirig = _open_com()
        rig = omnirig.Rig1 if rig_num == 1 else omnirig.Rig2
        return func(rig)
    except Exception as e:
        return {'ok': False, 'error': f'OmniRig injoignable ({e})'}
    finally:
        if need_couninit:
            try:
                import pythoncom
                pythoncom.CoUninitialize()
            except Exception:
                pass


def _replace_executor_locked():
    """Remplace `_EXECUTOR` par un ThreadPoolExecutor tout neuf. À appeler
    UNIQUEMENT avec `_executor_lock` déjà tenu par l'appelant (pas de
    verrouillage ici) — voir le commentaire au-dessus de `_executor_lock`
    pour le raisonnement complet."""
    global _EXECUTOR
    _EXECUTOR = _cf.ThreadPoolExecutor(max_workers=1, thread_name_prefix='omnirig_cat')


def _com_call(rig_num, func):
    """Borne dans le temps l'appel COM (même motif que
    logx_rotor._rotctld_command : ThreadPoolExecutor + .result(timeout=...))
    — un objet OmniRig qui ne répond plus (process figé, port série bloqué
    côté OmniRig lui-même) ne doit jamais geler le thread HTTP appelant.
    Executor à 1 seul worker : sérialise aussi les commandes entre elles,
    pas besoin d'un verrou séparé en plus pour ça.

    Auto-guérison : après `_TIMEOUT_THRESHOLD` timeouts CONSÉCUTIFS, le
    worker est présumé bloqué pour de bon (pas juste lent) — l'executor est
    remplacé pour que les appels suivants aient un worker frais. Le compteur
    est remis à zéro dès qu'un appel revient sans timeout (succès OU échec
    "propre" comme rig hors ligne : ça prouve que le worker répond)."""
    global _consecutive_timeouts
    with _executor_lock:
        executor = _EXECUTOR
    try:
        fut = executor.submit(_do_com_call, rig_num, func)
        result = fut.result(timeout=TIMEOUT_S + 2)
        with _executor_lock:
            _consecutive_timeouts = 0
        return result
    except _cf.TimeoutError:
        with _executor_lock:
            _consecutive_timeouts += 1
            if _consecutive_timeouts >= _TIMEOUT_THRESHOLD:
                _consecutive_timeouts = 0
                _replace_executor_locked()
                return {'ok': False, 'error': "OmniRig ne répond pas depuis plusieurs appels "
                        "consécutifs — l'exécuteur précédent semble définitivement bloqué, "
                        "nouvelle tentative avec un exécuteur neuf (réessaie dans un instant)"}
        return {'ok': False, 'error': "OmniRig ne répond pas (délai dépassé) — vérifie qu'OmniRig "
                "est bien lancé et que le rig configuré répond"}
    except Exception as e:
        with _executor_lock:
            _consecutive_timeouts = 0
        return {'ok': False, 'error': f'OmniRig injoignable ({e})'}


def get_state(cfg):
    """État courant (fréquence + mode) — même forme que
    logx_tci.get_state/logx_flrig.get_state pour que le client HTTP reste
    inchangé quel que soit le backend CAT actif."""
    settings = omnirig_settings(cfg)
    if not settings['enabled']:
        return {'ok': False, 'error': 'Pilotage OmniRig désactivé (CONFIG)', 'enabled': False}
    rig_num = settings['rig_num']

    def _read(rig):
        status = rig.Status
        if status != ST_ONLINE:
            return {'ok': False, 'enabled': True,
                    'error': f'Rig{rig_num} OmniRig hors ligne ({_status_label(status)})'}
        freq_hz = int(rig.Freq)
        mode = PARAM_TO_MODE.get(int(rig.Mode), '')
        device = str(rig.RigType or '')
        return {'ok': True, 'enabled': True, 'freq_hz': freq_hz,
                'freq_khz': round(freq_hz / 1000.0, 2), 'mode': mode, 'device': device}

    return _com_call(rig_num, _read)


def set_freq(cfg, freq_hz, mode=None):
    """QSY — retourne la même FORME de résultat ({'ok': ...}) que
    logx_tci.set_freq/logx_flrig.set_freq, mais PAS la même signature d'appel
    (logx_flrig.set_freq prend (host, port, freq_hz, mode=None) ; ici c'est
    (cfg, freq_hz, mode=None), cfg étant le dict de config CLIENT comme pour
    les autres fonctions de ce module)."""
    settings = omnirig_settings(cfg)
    if not settings['enabled']:
        return {'ok': False, 'error': 'Pilotage OmniRig désactivé (CONFIG)'}
    rig_num = settings['rig_num']

    def _write(rig):
        status = rig.Status
        if status != ST_ONLINE:
            return {'ok': False, 'error': f'Rig{rig_num} OmniRig hors ligne ({_status_label(status)})'}
        rig.Freq = int(freq_hz)
        if mode:
            param = MODE_TO_PARAM.get(str(mode).strip().upper())
            if param is not None:
                rig.Mode = param
        return {'ok': True}

    return _com_call(rig_num, _write)


def set_mode(cfg, mode):
    """Change uniquement le mode (utilisé si un appelant veut découpler
    fréquence et mode plutôt que de passer par set_freq(..., mode=...))."""
    settings = omnirig_settings(cfg)
    if not settings['enabled']:
        return {'ok': False, 'error': 'Pilotage OmniRig désactivé (CONFIG)'}
    rig_num = settings['rig_num']
    param = MODE_TO_PARAM.get(str(mode or '').strip().upper())
    if param is None:
        return {'ok': False, 'error': f'Mode "{mode}" non reconnu par OmniRig — '
                f'valeurs acceptées : {", ".join(sorted(MODE_TO_PARAM))}'}

    def _write(rig):
        status = rig.Status
        if status != ST_ONLINE:
            return {'ok': False, 'error': f'Rig{rig_num} OmniRig hors ligne ({_status_label(status)})'}
        rig.Mode = param
        return {'ok': True}

    return _com_call(rig_num, _write)


def set_ptt(cfg, on):
    """Bascule PTT — même signature que logx_tci.set_ptt/logx_flrig.set_ptt,
    pour le keyer vocal (logx_voicekeyer.py)."""
    settings = omnirig_settings(cfg)
    if not settings['enabled']:
        return {'ok': False, 'error': 'Pilotage OmniRig désactivé (CONFIG)'}
    rig_num = settings['rig_num']

    def _write(rig):
        status = rig.Status
        if status != ST_ONLINE:
            return {'ok': False, 'error': f'Rig{rig_num} OmniRig hors ligne ({_status_label(status)})'}
        rig.Tx = PM_TX if on else PM_RX
        return {'ok': True}

    return _com_call(rig_num, _write)


def test_connection(rig_num=1):
    """Test ÉPHÉMÈRE (bouton CONFIG) : lecture SEULE (Status/RigType/Freq) —
    ne déclenche jamais de PTT ni de changement de fréquence/mode (règle #5
    du chantier), contrairement à get_state() qui peut être appelé alors
    qu'un opérateur est en plein QSO."""
    rig_num = _norm_rig_num(rig_num)

    def _read(rig):
        status = rig.Status
        if status != ST_ONLINE:
            return {'ok': False, 'error': f'Rig{rig_num} OmniRig hors ligne ({_status_label(status)}) '
                    f'— vérifie qu\'OmniRig tourne (icône dans la zone de notification Windows), '
                    f'que Rig{rig_num} y est configuré avec le bon port série, et que la radio répond'}
        return {'ok': True, 'device': str(rig.RigType or ''), 'freq_hz': int(rig.Freq),
                'status': _status_label(status)}

    return _com_call(rig_num, _read)
