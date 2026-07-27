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

if "%ETAT%"=="10" (
    echo  [OK] Serveur deja en route sur localhost:8080, meme version.
    goto ouvre_browser
)
if "%ETAT%"=="11" goto probleme
if "%ETAT%"=="12" goto probleme
:: Tout autre code, y compris un plantage du pre-controle : on demarre.
:: logx_serveur.py refait la meme sonde pour son propre compte.

:: Lancer le serveur depuis le bon dossier (chemin relatif)
echo  [..] Lancement du serveur Python...
start "LogX Serveur" /MIN cmd /k "cd /d ""%DOSSIER%"" && python logx_serveur.py"

:: Attendre que le serveur REPONDE, au lieu de `timeout /t 3` en aveugle.
:: Deux defauts corriges d'un coup. La fenetre du serveur etant minimisee, un
:: refus de demarrer s'affichait la ou personne ne regarde pendant que le
:: navigateur s'ouvrait sur une adresse morte. Et 3 secondes n'etait qu'une
:: devinette : sur un poste lent, le navigateur s'ouvrait trop tot et affichait
:: la meme erreur alors que tout allait bien.
echo  [..] Attente de la reponse du serveur...
python "%DOSSIER%\logx_instance.py" --attendre
set "ETAT=%errorlevel%"
if "%ETAT%"=="10" goto ouvre_browser
goto probleme

:probleme
echo.
echo  [STOP] Le logiciel n'a pas ete ouvert. La raison est expliquee ci-dessus.
echo.
pause
exit /b 1

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
