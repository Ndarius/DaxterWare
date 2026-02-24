@echo off
chcp 65001 >nul 2>&1
title DaxterWare - Installation
color 0B

echo.
echo  ╔════════════════════════════════════════════════╗
echo  ║         DaxterWare - Installation            ║
echo  ╚════════════════════════════════════════════════╝
echo.

:: Vérifier si Python est installé
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo  [ERREUR] Python n'est pas installé ou pas dans le PATH.
    echo.
    echo  Deux options :
    echo    1. Installez Python depuis https://www.python.org/downloads/
    echo       ^(cochez "Add Python to PATH" pendant l'installation^)
    echo.
    echo    2. Utilisez plutôt la version EXE portable
    echo       ^(pas besoin de Python^)
    echo.
    pause
    exit /b 1
)

echo  [OK] Python détecté :
python --version
echo.

:: Créer un environnement virtuel
echo  [1/3] Création de l'environnement virtuel...
if not exist ".venv" (
    python -m venv .venv
    echo        Environnement créé.
) else (
    echo        Environnement déjà existant.
)

:: Activer et installer les dépendances
echo  [2/3] Installation des dépendances...
call .venv\Scripts\activate.bat
pip install -r requirements.txt --quiet

if %ERRORLEVEL% NEQ 0 (
    echo  [ERREUR] Échec de l'installation des dépendances.
    pause
    exit /b 1
)
echo        Dépendances installées.

:: Créer les dossiers nécessaires
echo  [3/3] Création des dossiers...
if not exist "downloads" mkdir downloads
if not exist "installers" mkdir installers
if not exist "logs" mkdir logs

echo.
echo  ╔════════════════════════════════════════════════╗
echo  ║         Installation terminée !                ║
echo  ╠════════════════════════════════════════════════╣
echo  ║  Pour lancer l'application :                   ║
echo  ║    - Double-cliquez sur  lancer.bat            ║
echo  ║    - Ou exécutez :  python main.py             ║
echo  ╚════════════════════════════════════════════════╝
echo.
pause
