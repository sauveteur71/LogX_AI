@echo off
title LogX AI — Lanceur
color 0A

echo.
echo  ================================================
echo    LogX AI v3.0
echo    Logiciel de concours radioamateur
echo  ================================================
echo.

:: Dossier du .bat (fonctionne peu importe ou le zip est extrait)
set "DOSSIER=%~dp0concours"

:: Verifier si Python est installe
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo  [ERREUR] Python n'est pas installe !
    echo.
    echo  Telecharge Python sur https://www.python.org/downloads/
    echo  Coche bien "Add Python to PATH" lors de l'installation.
    echo.
    pause
    exit /b 1
)

:: Un serveur repond-il deja -- ET est-ce la BONNE VERSION ?
:: Ce test appelait `curl http://localhost:8080/` : il repondait a la question
:: « quelque chose ecoute-t-il ? » et sautait au navigateur des que oui. Un
:: serveur laisse en route depuis la veille faisait donc rouvrir l'ANCIENNE
:: version apres une mise a jour, en affichant « [OK] Serveur deja en route ».
:: logx_instance.py compare la version qui repond a celle de ce dossier.
:: Tout imprevu (code de sortie inattendu) retombe sur le demarrage normal,
:: ou logx_serveur.py refait le meme controle pour son propre compte.
python "%DOSSIER%\logx_instance.py"
set "ETAT=%errorlevel%"

if "%ETAT%"=="12" (
    echo.
    echo  [STOP] Le port 8080 est pris par un autre logiciel ^(details ci-dessus^).
    echo.
    pause
    exit /b 1
)
if "%ETAT%"=="11" (
    echo.
    echo  [STOP] Une AUTRE version de LogX AI repond encore sur ce poste.
    echo         Ferme-la comme indique ci-dessus, puis relance ce fichier.
    echo         Aucune page n'est ouverte : elle afficherait l'ancienne version.
    echo.
    pause
    exit /b 1
)
if "%ETAT%"=="10" (
    echo  [OK] Serveur deja en route sur localhost:8080, meme version.
    goto ouvre_browser
)

:: Lancer le serveur depuis le bon dossier (chemin relatif)
echo  [..] Lancement du serveur Python...
start "LogX Serveur" /MIN cmd /k "cd /d ""%DOSSIER%"" && python logx_serveur.py"

:: Attendre que le serveur demarre
echo  [..] Attente demarrage (3 secondes)...
timeout /t 3 /nobreak >nul

:ouvre_browser
echo  [OK] Ouverture du navigateur...
echo.
echo  -> http://localhost:8080/logx_logbook.html
echo  -> http://localhost:8080/logx_configuration.html
echo.

:: Ouvrir dans le navigateur par defaut (Chrome ou autre)
start "" "http://localhost:8080/logx_configuration.html"
timeout /t 1 /nobreak >nul
start "" "http://localhost:8080/logx_logbook.html"

echo  ================================================
echo    Logiciel ouvert ! Bonne chance pour le concours
echo  ================================================
echo.
pause
