#!/usr/bin/env python3
"""
LogX AI - Serveur principal v3.1
Point d'entrée : démarrage du serveur HTTP et des tâches de fond.
Lance avec : python logx_serveur.py
Puis ouvre  : le carnet (logx_logbook.html), ou la page CONFIGURATION tant que
              l'indicatif n'est pas renseigne — voir logx_bootstrap.py.

Le code est organisé en modules :
  logx_utils.py                — réseau, géodésie locator, modes numériques
  logx_definitions.py  — base des concours (définitions, scoring, URLs règlements)
  logx_storage.py              — log partagé multi-opérateur + persistance disque
  logx_rules.py                — dates, mise à jour annuelle des règlements, concours externes WA7BNM
  logx_scoring.py              — moteur de score (valeur QSO, classement stations)
  logx_clusters.py             — sources de spots (clusters DX, propagation, lookups)
  logx_prompts.py              — prompts système du copilote IA
  logx_http.py         — endpoints HTTP + orchestration du refresh
"""

import sys

# Console Windows en cp1252 : un simple print() contenant une flèche → ou un
# emoji lève UnicodeEncodeError et tue la requête en cours. Forcer l'UTF-8
# (errors='replace' garantit qu'aucun log ne pourra jamais crasher le serveur).
# Doit être fait AVANT d'importer les modules applicatifs (qui peuvent printer).
for _stream in (sys.stdout, sys.stderr):
    if _stream and hasattr(_stream, 'reconfigure'):
        try:
            _stream.reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            pass

# Journal d'erreurs (sys.excepthook + threading.excepthook) : posé AVANT tout
# le reste pour capturer même une exception survenant pendant bootstrap() ou
# les imports applicatifs suivants. Voir logx_errorlog.py — alimente aussi
# GET /debug/errors (bouton "Signaler un problème" de la barre de statut).
import logx_errorlog
logx_errorlog.install()

import threading

# Amorçage AVANT tout import applicatif : en mode figé (PyInstaller), bascule
# le répertoire de travail vers le dossier de données utilisateur (inscriptible)
# et y recopie les fichiers de référence embarqués. En dev : sans effet.
from logx_bootstrap import (bootstrap, open_browser, is_frozen,
                            start_network_diagnosis, station_deja_configuree)
bootstrap()

from logx_utils import PORT, utcnow
from logx_version import APP_VERSION
from logx_storage import load_log_from_disk, load_qtc_from_disk, load_shifts_from_disk
from logx_rules import load_rules_cache, load_external_contests, schedule_annual_check
from logx_ref_bulletin import load_ref_bulletin
from logx_http import Handler
import logx_singleton


# ─── MAIN ─────────────────────────────────────────────────────────────────────
if __name__ == '__main__':

    # ─── AUTO-TEST DU jt9 EMBARQUÉ (exécutable GELÉ) ──────────────────────────
    # « LogXAI --selftest-jt9 <fichier.wav> » décode le wav avec le binaire jt9
    # vendorisé — résolu dans _MEIPASS (PyInstaller) — puis imprime les
    # indicatifs et quitte, SANS démarrer le serveur ni toucher au port. But :
    # prouver en CI (build-release) que jt9 + ses dépendances survivent au gel
    # (UPX, @executable_path/LD_LIBRARY_PATH…), ce que verify-jt9 (non gelé) ne
    # couvre pas. Chemin de diagnostic pur, jamais un usage opérateur. Placé en
    # TOUT PREMIER, avant le verrou d'instance (aucune liaison de port).
    if '--selftest-jt9' in sys.argv:
        _i = sys.argv.index('--selftest-jt9')
        _wav = sys.argv[_i + 1] if _i + 1 < len(sys.argv) else ''
        try:
            import logx_q65_natif as _q65
            _dec = _q65.decoder_wav(_wav, submode='A', tr_period=60,
                                    freq_mhz=50.313, band='6m')
            _calls = sorted(x['call'] for x in _dec)
        except Exception as _e:  # noqa: BLE001 — on veut la raison en clair en CI
            print('SELFTEST-JT9 ERREUR: %r' % _e)
            sys.exit(3)
        print('SELFTEST-JT9 calls=%r' % _calls)
        sys.exit(0 if _calls else 2)

    # ─── AUTO-TEST DU THÈME EMBARQUÉ (exécutable GELÉ) ────────────────────────
    # « LogXAI --selftest-theme » vérifie que logx_theme.css est bien embarqué
    # ET lisible au chemin que l'inlining utilise (_MEIPASS), donc que le thème
    # sera inliné dans le HTML servi (défense anti-Avast). Prouve en CI le
    # correctif « glob *.css dans logx.spec » : sans lui, l'exe rendait des
    # pages SANS thème chez l'utilisateur (bug invisible en dev/sources).
    if '--selftest-theme' in sys.argv:
        try:
            import logx_http as _h
            _style = _h._theme_css_inline_style()
            _ok = bool(_style) and ('--accent' in _style) and ('--bg' in _style)
        except Exception as _e:  # noqa: BLE001
            print('SELFTEST-THEME ERREUR: %r' % _e)
            sys.exit(3)
        print('SELFTEST-THEME ok=%r len=%d' % (_ok, len(_style or '')))
        sys.exit(0 if _ok else 2)

    def _abandonner(message, code=1):
        """Affiche l'explication puis termine, sans traceback Python.
        En mode figé, garde la fenêtre console ouverte : Windows la referme
        sinon dès la fin du process et l'utilisateur ne lit jamais pourquoi
        rien ne s'est lancé (même raison que logx_errorlog._excepthook)."""
        print(message)
        if is_frozen():
            try:
                input('\nAppuie sur Entree pour fermer cette fenetre... ')
            except Exception:
                pass
        sys.exit(code)

    # ─── UNE SEULE INSTANCE PAR PORT ──────────────────────────────────────────
    # Tout premier geste du démarrage, AVANT le moindre chargement ou la
    # moindre écriture : si un serveur LogX AI répond déjà sur le port, ce
    # processus ne doit rien faire d'autre qu'ouvrir la fenêtre existante et
    # s'arrêter. Sans ce garde-fou, Windows laissait le second serveur se lier
    # au port en silence : l'utilisateur croyait avoir redémarré alors que
    # l'ANCIEN processus répondait toujours, et les deux serveurs écrivaient
    # dans les mêmes fichiers de données sans exclusion mutuelle (chacun avec
    # son propre verrou en mémoire). Détail complet dans logx_singleton.py.
    # Hôte d'écoute : 127.0.0.1 par défaut (poste local uniquement) ; 0.0.0.0
    # (toutes les interfaces, donc joignable par tout le LAN) seulement si
    # l'opérateur a explicitement coché l'accès réseau en CONFIG > SÉCURITÉ
    # D'ACCÈS (`lan_access`). Avant ce correctif, 0.0.0.0 était le SEUL
    # comportement possible : /config/save (donc autostart_programs, voir
    # logx_autostart.py) était atteignable par tout appareil du réseau tant
    # qu'aucun mot de passe d'accès n'était configuré — l'état par défaut
    # d'une installation neuve. logx_http est déjà entièrement importé (voir
    # `from logx_http import Handler` plus haut) : current_config est donc
    # déjà chargé ici, avant même le premier print de ce démarrage.
    import logx_http as http_mod
    bind_host = '0.0.0.0' if http_mod.current_config.get('lan_access') else '127.0.0.1'

    # Accès LAN activé : ouvre le port dans le pare-feu Windows (best-effort, en
    # tâche de fond) pour que les AUTRES postes se connectent sans que l'opérateur
    # bricole les réglages Windows — le blocage classique quand le Wi-Fi est
    # classé « Public » (cf. logx_firewall). Silencieux si pas d'admin ; la page
    # CONFIG offre alors un bouton « autoriser » avec élévation.
    if bind_host == '0.0.0.0':
        try:
            import logx_firewall
            threading.Thread(target=logx_firewall.ensure_at_startup, args=(PORT,), daemon=True).start()
        except Exception:  # noqa: BLE001
            pass

    # extra_hosts=[IP LAN] : la détection « port partagé sans risque » ne
    # vérifie sinon que 127.0.0.1, jamais l'adresse réellement annoncée aux
    # autres opérateurs sur le WiFi de l'expédition (voir docstring probe()).
    # Sans objet si l'accès LAN est désactivé : notre serveur ne s'y liera
    # de toute façon pas.
    _instance = logx_singleton.probe(
        PORT, bind_host=bind_host,
        extra_hosts=[logx_singleton.detecter_ip_lan()] if bind_host == '0.0.0.0' else [])
    if _instance['state'] == logx_singleton.LOGX:
        # Même fonction d'ouverture que le démarrage nominal (elle choisit
        # l'adresse locale la plus rapide) : l'utilisateur voulait voir LogX
        # AI, il obtient la fenêtre de l'instance qui tourne. En mode
        # développeur, pas d'ouverture automatique — comme au démarrage normal.
        if is_frozen():
            open_browser(PORT, delay=0.2)
        # Code 0 : de son point de vue rien n'a échoué, la fenêtre demandée
        # s'ouvre. Un code d'erreur ferait afficher une alerte inutile par
        # certains lanceurs (raccourci Windows, script de mise à jour).
        # _abandonner garde la console ouverte en mode figé, et c'est ici que
        # ça compte le plus : c'est CE message qui explique à l'utilisateur
        # pourquoi il retombe sur l'ancienne version après une mise à jour, et
        # comment fermer l'instance en cours. Sans la pause, il défilerait dans
        # une fenêtre qui se referme aussitôt — le problème d'origine intact.
        _abandonner(logx_singleton.message_deja_lance(
            PORT, _instance['version'], ouvre_navigateur=is_frozen(),
            version_locale=APP_VERSION), code=0)
    if _instance['state'] == logx_singleton.OTHER:
        # Port occupé par autre chose, ET ce tiers nous prendrait l'adresse
        # que nous annonçons : ne surtout pas prétendre que LogX AI tourne
        # déjà, et ne pas ouvrir de navigateur sur un logiciel tiers.
        _abandonner(logx_singleton.message_port_occupe(PORT, _instance['detail']))
    if _instance['state'] == logx_singleton.SHARED:
        # Un tiers écoute aussi le port, mais sur d'AUTRES adresses (cas banal
        # de l'écouteur IPv6 dual-stack). Mesuré : notre bind 0.0.0.0 gagne
        # 127.0.0.1 et l'IP du réseau local, donc TOUTES les URL que LogX AI
        # affiche et ouvre. On avertit, et on démarre : refuser ici était une
        # régression qui rendait le logiciel impossible à lancer sur un poste
        # faisant tourner le moindre serveur Node, Go ou python -m http.server.
        print(logx_singleton.message_port_partage(PORT, _instance['detail']))

    # VERROU DU DOSSIER DE DONNEES, avant toute lecture du carnet. La sonde
    # de port ci-dessus ne protege que le port : deux serveurs lances dans le
    # meme dossier sur deux ports differents partagent logx.db et finissent
    # par s effacer mutuellement (voir logx_singleton).
    if not logx_singleton.verrouiller_dossier_donnees():
        _abandonner(logx_singleton.message_dossier_verrouille())

    load_log_from_disk()
    load_qtc_from_disk()
    load_shifts_from_disk()
    load_rules_cache()
    load_external_contests()
    load_ref_bulletin()

    threading.Thread(target=schedule_annual_check, daemon=True).start()

    # Base DXCC : rafraîchit cty.dat s'il a plus de 30 jours (AD1C publie
    # des mises à jour avant chaque gros concours). En fond : le serveur
    # démarre sans attendre le réseau, la base actuelle sert en attendant.
    from logx_dxcc import update_cty_if_stale
    threading.Thread(target=update_cty_if_stale, daemon=True).start()

    # TLE des satellites amateur (CelesTrak) : mêmes raisons que cty.dat, plus
    # une qui lui est propre — un TLE se DÉGRADE. Une éphéméride de trois
    # semaines donne des passages faux de plusieurs minutes, ce qui suffit à
    # rater un passage de dix minutes.
    #
    # EN FOND, ET JAMAIS BLOQUANT : sur une expédition sans Internet, le
    # serveur doit démarrer normalement et la prédiction continuer sur le
    # dernier jeu connu. rafraichir_tle() refuse d'écraser un cache valide par
    # une réponse inexploitable (portail captif) — c'est là que ça se joue.
    def _maj_tle():
        try:
            import logx_sat_passes as satp
            age = satp.age_tle(satp.charger_tle())
            if age is None or age['etat'] != 'frais':
                r = satp.rafraichir_tle()
                print('[TLE] %s' % ('%d satellites' % r['nb'] if r.get('ok')
                                    else r.get('error', 'echec')))
        except Exception as e:
            print('[TLE] indisponible : %s' % e)
    threading.Thread(target=_maj_tle, daemon=True).start()

    # Annuaire WebSDR : la liste KiwiSDR de linkfanel toutes les 15 min (UN
    # fichier = l'état des ~850 récepteurs, personne n'est martelé — voir
    # logx_websdr), et la sonde douce des stations curées toutes les heures.
    # En boucle de fond, jamais dans un handler ; l'échec conserve le cache.
    def _maj_websdr():
        import time as _t
        import logx_websdr as ws
        tours = 0
        while True:
            try:
                r = ws.rafraichir_kiwis()
                if tours == 0:
                    print('[WEBSDR] %s' % ('%d récepteurs' % r['nb']
                                           if r.get('ok') else r.get('error', 'echec')))
                if tours % 4 == 0:      # 1 h : la sonde des curées
                    ws.sonder_cures()
            except Exception as e:
                if tours == 0:
                    print('[WEBSDR] indisponible : %s' % e)
            tours += 1
            _t.sleep(15 * 60)
    threading.Thread(target=_maj_websdr, daemon=True).start()

    # Liste publique des utilisateurs LoTW (ARRL) : sert à colorer les
    # indicatifs et à écarter des alertes les stations qui n'uploadent jamais
    # — un QSO avec elles ne sera jamais confirmé, donc ne comptera jamais pour
    # le DXCC. En fond comme cty.dat : 6 Mo à télécharger ne doivent pas
    # retarder le démarrage, et sans réseau on garde la liste qu'on a.
    def _maj_lotw():
        try:
            import logx_lotwusers as lotw
            lotw.update_if_stale()
            lotw.load()
        except Exception as _e:
            print(f'[LoTW] {_e}')
    threading.Thread(target=_maj_lotw, daemon=True).start()

    # Bases de références POTA/SOTA/WWFF/IOTA/WCA (parcs, sommets, refuges,
    # groupes d'îles, châteaux) : même raison que cty.dat/TLE/LoTW ci-dessus
    # -- sans ce prefetch, le téléchargement (jusqu'à 60s de timeout, cache
    # 30 jours) ne démarrait qu'au tout premier appel de
    # /activation_db/search, laissant "MA RÉFÉRENCE ACTIVÉE" sans
    # autocomplétion pendant les toutes premières secondes d'un poste neuf.
    # Correctif de l'analyse concurrentielle du 10/08/2026 (Wavelog peuple
    # ces mêmes référentiels dès sa migration de mise à jour, "out of the
    # box"). ensure_loading_started() démarre lui-même son propre thread de
    # fond et ne bloque jamais l'appelant -- pas besoin de l'envelopper ici.
    def _maj_activation_db():
        try:
            import logx_sota as sota
            sota.ensure_loading_started()
        except Exception as _e:
            print(f'[SOTA] indisponible : {_e}')
        try:
            import logx_pota as pota
            pota.parks_db.ensure_loading_started()
        except Exception as _e:
            print(f'[POTA] indisponible : {_e}')
        try:
            import logx_wwff as wwff
            wwff.directory_db.ensure_loading_started()
        except Exception as _e:
            print(f'[WWFF] indisponible : {_e}')
        try:
            import logx_iota as iota
            iota.groups_db.ensure_loading_started()
        except Exception as _e:
            print(f'[IOTA] indisponible : {_e}')
        try:
            import logx_wca as wca
            wca.ensure_loading_started()
        except Exception as _e:
            print(f'[WCA] indisponible : {_e}')
    _maj_activation_db()

    # Scoreboard en direct + sauvegarde cloud : deux threads de fond qui lisent
    # la config à chaud (activés/intervalles réglés dans CONFIG). Inactifs tant
    # que rien n'est configuré ; ne perturbent jamais le serveur en cas d'échec.
    def _scoreboard_loop():
        import time as _t
        import logx_http as h
        import logx_scoreboard as sb
        import logx_storage as st
        while True:
            _t.sleep(60)
            try:
                with h.config_lock:
                    cfg = dict(h.current_config)
                s = sb.scoreboard_settings(cfg)
                if not s['enabled']:
                    continue
                last = sb.status(cfg).get('last', {}).get('last')
                # Respecte l'intervalle (le stamp est en 'YYYY-MM-DD HH:MM')
                import datetime as _dt
                due = True
                if last:
                    try:
                        age = (utcnow()
                               - _dt.datetime.strptime(last, '%Y-%m-%d %H:%M')).total_seconds()
                        due = age >= s['interval_min'] * 60 - 5
                    except Exception:
                        due = True
                if due:
                    with st.log_lock:
                        log_copy = list(st.shared_log)
                    r = sb.push(cfg, log_copy)
                    if r.get('ok'):
                        print(f"[SCOREBOARD] score {r['score']} / {r['qso']} QSO publie")
            except Exception as _e:
                print(f"[SCOREBOARD] {_e}")

    def _backup_loop():
        import time as _t
        import logx_http as h
        import logx_backup as bk
        import logx_storage as st
        import datetime as _dt
        while True:
            _t.sleep(120)
            try:
                with h.config_lock:
                    cfg = dict(h.current_config)
                s = bk.backup_settings(cfg)
                if not s['enabled']:
                    continue
                last = bk.status(cfg).get('last', {}).get('last')
                due = True
                if last:
                    try:
                        age = (utcnow()
                               - _dt.datetime.strptime(last, '%Y-%m-%d %H:%M')).total_seconds()
                        due = age >= s['interval_min'] * 60 - 5
                    except Exception:
                        due = True
                if due:
                    with st.log_lock:
                        log_copy = list(st.shared_log)
                    r = bk.run_backup(cfg, log_copy)
                    if r.get('ok'):
                        print(f"[BACKUP] {len(r['files'])} fichiers -> {r['folder']}")
            except Exception as _e:
                print(f"[BACKUP] {_e}")

    def _telemetry_loop():
        # Heartbeat quotidien anonyme (logx_telemetry.py) — activé par défaut
        # (opt-out), mais n'envoie RIEN tant qu'aucun `telemetry_endpoint`
        # n'est configuré (aucune infrastructure serveur n'existe encore
        # pour le recevoir). Même patron que les autres tâches périodiques
        # ci-dessus (vérifie toutes les 60s, respecte son propre intervalle
        # via un stamp persisté).
        import time as _t
        import logx_http as h
        import logx_telemetry as tel
        while True:
            _t.sleep(60)
            try:
                with h.config_lock:
                    cfg = dict(h.current_config)
                s = tel.telemetry_settings(cfg)
                if not s['enabled'] or not s['endpoint']:
                    continue
                last = tel.status().get('last', {}).get('last')
                if tel.heartbeat_due(last, utcnow()):
                    r = tel.send_heartbeat(cfg)
                    if r.get('ok'):
                        print('[TELEMETRY] heartbeat envoyé')
            except Exception as _e:
                print(f"[TELEMETRY] {_e}")

    def _cloudsync_loop():
        import time as _t
        import logx_http as h
        import logx_cloudsync as cs
        import logx_storage as st
        import datetime as _dt
        # SYNCHRO IMMÉDIATE AU DÉMARRAGE : quand un 2e poste s'ouvre, l'opérateur
        # veut voir tout de suite les derniers QSO du 1er poste, pas attendre la
        # première minuterie (jusqu'à `interval` minutes de log périmé). La 1re
        # passe force donc `due` sans regarder l'intervalle. Sans risque : sync_now
        # FUSIONNE (union par clé + tombstones), il n'écrase jamais le distant.
        startup = True
        while True:
            try:
                with h.config_lock:
                    cfg = dict(h.current_config)
                s = cs.cloudsync_settings(cfg)
                if not s['enabled']:
                    startup = False
                    _t.sleep(60)
                    continue
                last = cs.status(cfg).get('last', {}).get('last')
                due = True
                interval_min = int(cfg.get('cloudsync_interval', 3) or 3)
                if last and not startup:
                    try:
                        age = (utcnow()
                               - _dt.datetime.strptime(last, '%Y-%m-%d %H:%M')).total_seconds()
                        due = age >= interval_min * 60 - 5
                    except Exception:
                        due = True
                if due:
                    with st.log_lock:
                        log_copy = list(st.shared_log)
                    r = cs.sync_now(cfg, log_copy)
                    if r.get('ok') and (r.get('pulled') or r.get('pushed')):
                        tag = ' (démarrage)' if startup else ''
                        print(f"[CLOUDSYNC]{tag} mode={r['mode']} pushed={r['pushed']} pulled={r['pulled']}")
            except Exception as _e:
                print(f"[CLOUDSYNC] {_e}")
            startup = False
            _t.sleep(60)

    def _mysql_sync_loop():
        # Même motif que _cloudsync_loop ci-dessus, transposé à une base
        # MySQL partagée (logx_mysql_sync.py) — radio-club ou plusieurs
        # postes d'un même radioamateur. SYNCHRO IMMÉDIATE au démarrage
        # (même raison que Cloud Sync : voir son commentaire).
        import time as _t
        import logx_http as h
        import logx_mysql_sync as mysql
        import logx_storage as st
        startup = True
        while True:
            try:
                with h.config_lock:
                    cfg = dict(h.current_config)
                s = mysql.mysql_settings(cfg)
                if not s['enabled']:
                    startup = False
                    _t.sleep(60)
                    continue
                with st.log_lock:
                    log_copy = list(st.shared_log)
                r = mysql.sync_now(cfg, log_copy)
                if r.get('ok') and (r.get('pulled') or r.get('pushed')):
                    tag = ' (démarrage)' if startup else ''
                    print(f"[MYSQL-SYNC]{tag} mode={r['mode']} pushed={r['pushed']} pulled={r['pulled']}")
                elif not r.get('ok'):
                    print(f"[MYSQL-SYNC] {r.get('error')}")
            except Exception as _e:
                print(f"[MYSQL-SYNC] {_e}")
            startup = False
            _t.sleep(30)

    def _lan_sync_loop():
        # SYNCHRO LAN DIRECTE (sans dossier partagé) : les postes se découvrent
        # par beacon UDP et échangent leurs QSO en HTTP. INDÉPENDANT de Cloud
        # Sync — les deux peuvent tourner ensemble (l'opérateur peut vouloir la
        # découverte LAN ET un dossier partagé). Un pair mettra jusqu'à ~15-25 s
        # à être découvert au premier démarrage (le temps d'un cycle de beacon).
        import time as _t
        import logx_http as h
        import logx_lan_sync as lan
        import logx_storage as st

        def _get_log():
            with st.log_lock:
                return list(st.shared_log)

        started = False
        startup = True
        while True:
            try:
                with h.config_lock:
                    cfg = dict(h.current_config)
                if str(cfg.get('lan_sync_enabled', '')) in ('1', 'true', 'True', 'on'):
                    if not started:
                        lan.start(lambda: dict(h.current_config), PORT)
                        started = True
                    r = lan.pull_and_merge(_get_log,
                                           lambda q: h.add_qso_to_log(q, force=False)[0],
                                           token=lan._lan_token(cfg))
                    if r.get('pulled'):
                        tag = ' (démarrage)' if startup else ''
                        print(f"[LAN-SYNC]{tag} pairs={r['peers']} tirés={r['pulled']}")
            except Exception as _e:
                print(f"[LAN-SYNC] {_e}")
            startup = False
            _t.sleep(12)

    threading.Thread(target=_scoreboard_loop, daemon=True).start()
    threading.Thread(target=_backup_loop, daemon=True).start()
    threading.Thread(target=_telemetry_loop, daemon=True).start()
    threading.Thread(target=_cloudsync_loop, daemon=True).start()
    threading.Thread(target=_mysql_sync_loop, daemon=True).start()
    threading.Thread(target=_lan_sync_loop, daemon=True).start()

    # Watcher de branchement radio/interface CAT (plug-and-play) : diff léger
    # de la liste des ports série toutes les ~1.5s, aucun octet CAT envoyé —
    # voir logx_cat.py:port_watcher_loop et le chantier du 03/08/2026.
    import logx_cat as _cat
    _cat.start_port_watcher()

    # Import unique et préalable : sans cela, si l'import du pont WSJT-X échoue,
    # http_mod restait non défini et le bloc ADIF-net levait un NameError
    # (avalé) — l'écouteur réseau ADIF ne démarrait alors jamais.
    import logx_http as http_mod

    # Auto-lancement de logiciels tiers (WSJT-X, N1MM, un décodeur...) —
    # EN THREAD DE FOND, jamais bloquant : un exécutable lent à scanner par
    # l'antivirus ne doit jamais retarder l'ouverture de LogX lui-même.
    try:
        import logx_autostart as autostart
        threading.Thread(target=lambda: autostart.lancer_tous(http_mod.current_config),
                         daemon=True).start()
    except Exception as _e:
        print(f"[AUTOSTART] indisponible : {_e}")

    # Pont WSJT-X : écouteur UDP FT8/FT4 démarré si activé dans config.json
    # (ou plus tard à chaud dès qu'un /wsjtx/state le voit activé côté client).
    try:
        import logx_wsjtx as wsjtx
        w = wsjtx.wsjtx_settings(None)
        if w['enabled']:
            wsjtx.start_listener(
                get_cfg=lambda: dict(http_mod.current_config),
                add_qso=lambda q: http_mod.add_qso_to_log(q, force=False)[0],
                port=w['port'])
    except Exception as _e:
        print(f"[WSJTX] Demarrage differe: {_e}")

    # Réseau ADIF générique (N1MM/DXLog) : écouteur UDP démarré si activé
    try:
        import logx_adifnet as adifnet
        a = adifnet.adifnet_settings(dict(http_mod.current_config))
        if a['listen']:
            adifnet.start_listener(
                get_cfg=lambda: dict(http_mod.current_config),
                add_qso=lambda q: http_mod.add_qso_to_log(q, force=False)[0],
                port=a['port'])
    except Exception as _e:
        print(f"[ADIFNET] Demarrage differe: {_e}")

    import socket as _sock
    try:
        _s = _sock.socket(_sock.AF_INET, _sock.SOCK_DGRAM)
        _s.connect(('8.8.8.8', 80))
        local_ip = _s.getsockname()[0]
        _s.close()
    except Exception:
        local_ip = '127.0.0.1'

    # Ouverture du port AVANT la bannière et le navigateur : si le bind
    # échoue, l'utilisateur ne doit pas avoir sous les yeux une liste d'URL
    # qui ne répondront jamais, ni un navigateur qui s'ouvre dans le vide.
    # LogXHTTPServer (et non ThreadingHTTPServer) : sous Windows il refuse un
    # port déjà écouté au lieu de s'y greffer en silence — filet de sécurité
    # pour la course possible entre la sonde ci-dessus et ce bind.
    try:
        server = logx_singleton.LogXHTTPServer((bind_host, PORT),
                                               Handler)
    except OSError as _e:
        _abandonner(logx_singleton.message_bind_impossible(PORT, _e))

    print('=' * 60)
    print('  LogX AI -- logiciel de concours multi-tout')
    print('  (config du concours actif : page CONFIG)')
    print('=' * 60)
    # 127.0.0.1 plutôt que localhost : une exception antivirus (Web Shield)
    # posée pour 127.0.0.1 ne couvre pas localhost par correspondance
    # textuelle, même si les deux pointent vers la même machine — observé
    # avec Avast ajoutant ~2 s d'inspection à chaque requête sur localhost.
    # Le logbook en premier dès que la station est réglée : c'est la page sur
    # laquelle le navigateur s'ouvre, autant que la console dise la même chose.
    if station_deja_configuree():
        print(f'  -> http://127.0.0.1:{PORT}/logx_logbook.html   (ouvert automatiquement)')
        print(f'  -> http://127.0.0.1:{PORT}/logx_configuration.html')
    else:
        print(f'  -> http://127.0.0.1:{PORT}/logx_configuration.html   '
              f'(premiere utilisation : renseigne ton indicatif)')
        print(f'  -> http://127.0.0.1:{PORT}/logx_logbook.html')
    print(f'  -> http://127.0.0.1:{PORT}/logx_propagation.html')
    print(f'  -> http://127.0.0.1:{PORT}/logx_calendrier.html')
    print(f'  -> http://127.0.0.1:{PORT}/logx_mobile.html (telephone)')
    print('=' * 60)
    if bind_host == '0.0.0.0':
        print(f'  Autres postes WiFi : http://{local_ip}:{PORT}/logx_logbook.html')
    else:
        print('  Accès réseau (autres postes WiFi/LAN) : DÉSACTIVÉ.')
        print('  Active-le dans CONFIG > SÉCURITÉ D\'ACCÈS pour le multi-poste/radioclub.')
    print()
    print('  Ctrl+C pour arreter')
    print()

    # Application figée : ouvre le navigateur automatiquement (sur l'adresse
    # locale la plus rapide — voir logx_bootstrap.pick_fastest_host). En mode
    # développeur, pas d'ouverture automatique mais le même diagnostic
    # s'affiche en console : utile aussi pour quelqu'un qui lance le script
    # directement et dont l'antivirus ralentirait une des deux adresses.
    if is_frozen():
        open_browser(PORT)
    else:
        start_network_diagnosis(PORT, then_open_browser=False)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('73 de F6KQJ/P !')
