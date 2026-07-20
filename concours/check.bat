@echo off
title LogX AI - Verification locale
color 0A

echo.
echo  ================================================
echo    LogX AI - CHECK avant commit
echo  ================================================
echo.

cd /d "%~dp0"
set ERR=0

echo  [1/2] Validation des definitions de concours...
echo  ------------------------------------------------
python logx_validate.py
if %errorlevel% neq 0 (
    echo  [ECHEC] logx_validate.py a trouve des erreurs.
    set ERR=1
) else (
    echo  [OK] Toutes les definitions sont conformes au schema.
)
echo.

echo  [2/2] Harnais d'extraction IA (mode --mock, sans appel reseau)...
echo  Note : le mock est volontairement imparfait, son score n'est jamais
echo  100%% par design. Ce test verifie juste que le harnais tourne sans
echo  planter (pas de crash Python) - il n'est PAS bloquant pour le commit.
echo  ------------------------------------------------
python logx_eval.py --mock
echo.
echo  (score au-dessus ignore volontairement pour la decision OK/ECHEC)
echo.

echo  ================================================
if %ERR%==0 (
    echo    RESULTAT : TOUT EST OK - commit possible
) else (
    echo    RESULTAT : PROBLEME DETECTE - corriger avant de commiter
)
echo  ================================================
echo.
echo  Astuce : pour tester le pipeline complet d'extraction IA sur de
echo  vrais reglements (WAE, CQ WW...), utilise plutot :
echo    set ANTHROPIC_API_KEY=sk-ant-...
echo    python logx_eval.py
echo  (fait des appels reels a l'IA, donc pas lance ici automatiquement)
echo.
pause
exit /b %ERR%
