@echo off
chcp 65001 >nul 2>&1
title DaxterWare
color 0B

:: Vérifier si l'environnement virtuel existe
if exist ".venv\Scripts\python.exe" (
        echo  Lancement de DaxterWare...
        .venv\Scripts\python.exe main.py
) else (
    :: Essayer avec le Python système
    python --version >nul 2>&1
    if %ERRORLEVEL% EQU 0 (
        echo  Lancement de DaxterWare...
        python main.py
    ) else (
        echo.
        echo  [ERREUR] Python non trouvé.
        echo  Exécutez d'abord installer.bat
        echo.
        pause
    )
)
