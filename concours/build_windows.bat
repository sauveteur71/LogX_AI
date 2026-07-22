@echo off
REM ============================================================
REM  LogX AI - Construction de l'executable Windows
REM  Produit : dist\LogXAI.exe (autonome, sans Python)
REM ============================================================
setlocal
cd /d "%~dp0"

echo [1/3] Installation des dependances (requirements.txt)...
REM Indispensable AVANT PyInstaller : il n'embarque que les bibliotheques
REM importables au moment du build. Sans cette etape, un poste frais produit
REM un exe sans CAT serie, sans keyer vocal, sans EME - silencieusement.
python -m pip install --quiet -r requirements.txt

echo [2/3] Installation de PyInstaller si necessaire...
python -m pip install --quiet --upgrade pyinstaller

echo [3/3] Construction de l'executable...
python -m PyInstaller --noconfirm --clean logx.spec

echo.
if exist "dist\LogXAI.exe" (
  echo  ============================================================
  echo   OK ! Executable pret : dist\LogXAI.exe
  echo   Double-clique dessus pour lancer LogX AI.
  echo  ============================================================
) else (
  echo  [ERREUR] La construction a echoue. Verifie les messages ci-dessus.
)
pause
