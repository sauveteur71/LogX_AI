# -*- coding: utf-8 -*-
"""Dialogues natifs du système d'exploitation, invoqués depuis le serveur.

LogX AI tourne en local sur la machine de l'utilisateur (pas un service
distant) : le process serveur peut donc ouvrir un VRAI dialogue Windows le
temps d'une requête HTTP ponctuelle, déclenchée par un clic utilisateur.
C'est l'exception explicitement acceptée à la règle « jamais d'appel
bloquant dans le thread HTTP » : il n'y a ici ni réseau ni attente
automatique, seulement l'utilisateur qui répond à une boîte de dialogue
(ThreadingHTTPServer isole ça à un seul thread — les autres requêtes ne sont
pas affectées).

tkinter est explicitement exclu du build PyInstaller (voir logx.spec,
Analysis.excludes) : ce module ne dépend PAS de tkinter et n'en a pas
besoin — il invoque `powershell.exe` en sous-processus (System.Windows.
Forms, disponible nativement sur toute machine Windows/.NET) et parse sa
sortie standard. Aucune nouvelle dépendance Python.

Réutilisable : appelé à la fois par /backup/pick_folder (choix du dossier de
sauvegarde, CONFIG → SAUVEGARDE AUTOMATIQUE) et par /shortcut/create_desktop
(proposition de raccourci bureau au premier lancement figé, voir
logx_shortcut.py) — toute nouvelle invocation PowerShell doit rejoindre ce
module plutôt que d'en dupliquer une ailleurs.
"""
import re
import subprocess
import sys

# Un chemin UNC (\\hôte\partage) passé tel quel à Test-Path force Windows à
# tenter une authentification SMB sortante vers cet hôte — vecteur connu de
# fuite/relais NTLM (le hachage du compte local part vers un hôte arbitraire
# choisi par le client HTTP, initial_dir venant directement du corps POST de
# /backup/pick_folder). On n'accepte donc qu'un chemin LOCAL Windows
# classique (lettre de lecteur), jamais un UNC.
_LOCAL_DRIVE_PATH_RE = re.compile(r'^[A-Za-z]:[\\/]')

# Le dialogue attend une action humaine : on borne quand même l'attente pour
# ne jamais bloquer indéfiniment un thread HTTP si l'utilisateur abandonne
# la fenêtre sans la fermer.
TIMEOUT_S = 180

# La création de raccourci (WScript.Shell CreateShortcut) n'attend elle
# AUCUNE action humaine — contrairement au FolderBrowserDialog ci-dessus,
# c'est un pur appel COM synchrone. Un délai court suffit ; s'il est dépassé,
# c'est que powershell.exe lui-même est bloqué (pas un utilisateur qui réfléchit).
SHORTCUT_TIMEOUT_S = 20


def pick_folder(title='Choisir un dossier', initial_dir=''):
    """Ouvre le sélecteur de dossier natif Windows (FolderBrowserDialog) et
    attend la réponse de l'utilisateur (bloquant, volontairement — voir
    docstring du module). Retourne :
      {'ok': True, 'path': 'C:\\...'}                    si un dossier est choisi
      {'ok': False, 'error': 'annule'}                   si l'utilisateur annule
      {'ok': False, 'error': 'plateforme non supportee'} hors Windows
      {'ok': False, 'error': '...'}                       autre échec
    Ne lève jamais d'exception.
    """
    if not sys.platform.startswith('win'):
        return {'ok': False, 'error': 'plateforme non supportee',
                'message': ("Le choix graphique du dossier n'est disponible "
                             "que sous Windows pour le moment. Vous pouvez "
                             "toujours taper le chemin manuellement.")}

    # initial_dir vient du corps POST de /backup/pick_folder, donc contrôlé
    # par le client : un chemin non local (UNC notamment) est ignoré plutôt
    # que transmis au script PowerShell — voir _LOCAL_DRIVE_PATH_RE ci-dessus.
    if initial_dir and not _LOCAL_DRIVE_PATH_RE.match(initial_dir):
        initial_dir = ''

    ps_script = _build_pick_folder_script(title, initial_dir)
    try:
        proc = subprocess.run(
            ['powershell', '-NoProfile', '-NonInteractive', '-STA', '-Command', ps_script],
            capture_output=True, text=True, timeout=TIMEOUT_S,
        )
    except subprocess.TimeoutExpired:
        return {'ok': False, 'error': 'delai depasse en attendant la reponse au dialogue'}
    except Exception as e:
        return {'ok': False, 'error': f'impossible de lancer le dialogue : {e}'}

    out = (proc.stdout or '')
    for line in out.splitlines():
        line = line.strip()
        if line.startswith('LOGXAI_PICKED:'):
            path = line[len('LOGXAI_PICKED:'):].strip()
            if path:
                return {'ok': True, 'path': path}
        if line == 'LOGXAI_CANCELLED':
            return {'ok': False, 'error': 'annule'}

    # Ni marqueur de succès ni d'annulation : PowerShell a échoué avant
    # d'atteindre ShowDialog (stderr contient le détail — ex. politique
    # d'exécution, assembly introuvable...).
    err = (proc.stderr or '').strip()
    return {'ok': False, 'error': err or "le dialogue Windows n'a pas repondu"}


def _build_pick_folder_script(title, initial_dir):
    """Construit le script PowerShell. Concaténation simple (pas de f-string
    autour du bloc PowerShell) pour ne pas confondre les accolades PS avec
    l'échappement des f-strings Python."""
    title_ps = _ps_quote(title)
    initial_ps = _ps_quote(initial_dir)
    return (
        "Add-Type -AssemblyName System.Windows.Forms | Out-Null\n"
        "$f = New-Object System.Windows.Forms.FolderBrowserDialog\n"
        "$f.Description = " + title_ps + "\n"
        "$f.ShowNewFolderButton = $true\n"
        "$init = " + initial_ps + "\n"
        "if ($init -ne '' -and (Test-Path $init)) { $f.SelectedPath = $init }\n"
        "$result = $f.ShowDialog()\n"
        "if ($result -eq [System.Windows.Forms.DialogResult]::OK) {\n"
        "    Write-Output ('LOGXAI_PICKED:' + $f.SelectedPath)\n"
        "} else {\n"
        "    Write-Output 'LOGXAI_CANCELLED'\n"
        "}\n"
    )


def create_desktop_shortcut(target, name='LogX AI', description=''):
    """Crée un raccourci Windows (.lnk) sur le Bureau de l'utilisateur, pointant
    vers `target` (typiquement sys.executable — l'exécutable figé en cours
    d'exécution lui-même, jamais un chemin codé en dur). Retourne :
      {'ok': True, 'path': 'C:\\...\\Desktop\\LogX AI.lnk'}
      {'ok': False, 'error': 'plateforme non supportee'} hors Windows
      {'ok': False, 'error': '...'}                       autre échec
    Ne lève jamais d'exception.

    Utilise $ws.SpecialFolders('Desktop') plutôt que %USERPROFILE%\\Desktop
    codé en dur : sous OneDrive avec redirection de dossiers connus (« Known
    Folder Move »), le Bureau réellement affiché à l'utilisateur peut être
    ailleurs — SpecialFolders('Desktop') est le seul moyen fiable de viser
    l'endroit que l'utilisateur voit vraiment sur son écran."""
    if not sys.platform.startswith('win'):
        return {'ok': False, 'error': 'plateforme non supportee',
                'message': ("La création automatique de raccourci n'est "
                             "disponible que sous Windows pour le moment.")}

    ps_script = _build_shortcut_script(target, name, description)
    try:
        proc = subprocess.run(
            ['powershell', '-NoProfile', '-NonInteractive', '-Command', ps_script],
            capture_output=True, text=True, timeout=SHORTCUT_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired:
        return {'ok': False, 'error': 'delai depasse lors de la creation du raccourci'}
    except Exception as e:
        return {'ok': False, 'error': f'impossible de lancer PowerShell : {e}'}

    out = (proc.stdout or '')
    for line in out.splitlines():
        line = line.strip()
        if line.startswith('LOGXAI_SHORTCUT_OK:'):
            path = line[len('LOGXAI_SHORTCUT_OK:'):].strip()
            if path:
                return {'ok': True, 'path': path}

    # Aucun marqueur de succès : le script PowerShell a échoué avant Save()
    # (stderr contient le détail — ex. COM indisponible, chemin invalide...).
    err = (proc.stderr or '').strip()
    return {'ok': False, 'error': err or "la creation du raccourci a echoue sans message"}


def _build_shortcut_script(target, name, description):
    """Construit le script PowerShell (même choix de concaténation simple
    que _build_pick_folder_script — voir sa docstring)."""
    target_ps = _ps_quote(target)
    name_ps = _ps_quote(name)
    desc_ps = _ps_quote(description)
    return (
        "$ws = New-Object -ComObject WScript.Shell\n"
        "$desktop = $ws.SpecialFolders('Desktop')\n"
        "$lnkPath = Join-Path $desktop (" + name_ps + " + '.lnk')\n"
        "$sc = $ws.CreateShortcut($lnkPath)\n"
        "$sc.TargetPath = " + target_ps + "\n"
        "$sc.Description = " + desc_ps + "\n"
        "$sc.WorkingDirectory = Split-Path " + target_ps + " -Parent\n"
        "$sc.Save()\n"
        "Write-Output ('LOGXAI_SHORTCUT_OK:' + $lnkPath)\n"
    )


def _ps_quote(s):
    """Échappe une chaîne pour l'injecter dans un script PowerShell entre
    guillemets simples (seul caractère à doubler : le guillemet simple —
    les guillemets simples désactivent toute interpolation PowerShell, donc
    aucun autre caractère du chemin/titre ne peut être interprété)."""
    s = str(s or '')
    return "'" + s.replace("'", "''") + "'"
