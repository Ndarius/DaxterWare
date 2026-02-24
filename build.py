"""
DaxterWare - Script de build
Crée un exécutable Windows autonome avec PyInstaller
Aucune installation de Python nécessaire sur le PC cible
"""

import subprocess
import sys
import shutil
from pathlib import Path

BASE_PATH = Path(__file__).resolve().parent
DIST_PATH = BASE_PATH / "dist"
BUILD_PATH = BASE_PATH / "build"
APP_NAME = "DaxterWare"
EXE_NAME = "DaxterWare"
ICON_PATH = BASE_PATH / "assets" / "icon.ico"


def install_pyinstaller():
    """Installe PyInstaller si nécessaire"""
    try:
        import PyInstaller
        print(f"[OK] PyInstaller {PyInstaller.__version__} détecté")
    except ImportError:
        print("[...] Installation de PyInstaller...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
        print("[OK] PyInstaller installé")


def clean_previous_build():
    """Nettoie les dossiers de build précédents"""
    for folder in [BUILD_PATH, DIST_PATH]:
        if folder.exists():
            print(f"[...] Nettoyage de {folder.name}/")
            shutil.rmtree(folder)
    spec_file = BASE_PATH / f"{EXE_NAME}.spec"
    if spec_file.exists():
        spec_file.unlink()


def build_exe():
    """Construit l'exécutable avec PyInstaller"""
    print("\n" + "=" * 60)
    print(f"  Construction de {APP_NAME}")
    print("=" * 60 + "\n")

    install_pyinstaller()
    clean_previous_build()

    # Arguments PyInstaller
    args = [
        sys.executable, "-m", "PyInstaller",
        "--name", EXE_NAME,
        "--onefile",                    # UN SEUL EXE autonome
        "--windowed",                   # Pas de console (GUI)
        "--noconfirm",
        "--clean",
        # Inclure les données embarquées
        "--add-data", f"config;config",
        "--add-data", f"assets;assets",
        # Imports cachés
        "--hidden-import", "customtkinter",
        "--hidden-import", "PIL",
        # Collecter customtkinter
        "--collect-data", "customtkinter",
    ]

    # Icône si disponible
    if ICON_PATH.exists():
        args.extend(["--icon", str(ICON_PATH)])

    # Point d'entrée
    args.append(str(BASE_PATH / "main.py"))

    print("[...] Lancement de PyInstaller...")
    print(f"      Commande: {' '.join(args[2:])}\n")

    result = subprocess.run(args, cwd=str(BASE_PATH))

    if result.returncode != 0:
        print("\n[ERREUR] Le build a échoué !")
        sys.exit(1)

    # Créer les dossiers nécessaires à côté de l'exe
    dist_app = DIST_PATH
    for folder_name in ["config", "downloads", "installers", "logs"]:
        (dist_app / folder_name).mkdir(parents=True, exist_ok=True)

    # Copier la config à côté de l'exe (pour pouvoir éditer)
    import shutil as sh2
    for cfg_file in (BASE_PATH / "config").glob("*.json"):
        sh2.copy2(cfg_file, dist_app / "config" / cfg_file.name)

    print("\n" + "=" * 60)
    print(f"  BUILD TERMINÉ AVEC SUCCÈS")
    print("=" * 60)
    print(f"\n  Exécutable: {dist_app / (EXE_NAME + '.exe')}")
    print(f"\n  Pour distribuer sur un autre PC :")
    print(f"  1. Copiez {EXE_NAME}.exe + les dossiers config/ et installers/")
    print(f"  2. (Optionnel) Mettez des setups dans installers/")
    print(f"  3. Lancez {EXE_NAME}.exe")
    print(f"  => Aucune installation nécessaire !\n")


def build_portable_zip():
    """Crée un ZIP portable prêt à distribuer"""
    dist_app = DIST_PATH
    if not (dist_app / f"{EXE_NAME}.exe").exists():
        print("[ERREUR] Faites d'abord un build avec: python build.py")
        return

    zip_name = f"{EXE_NAME}_Portable"
    print(f"\n[...] Création de l'archive {zip_name}.zip...")

    zip_path = shutil.make_archive(
        str(DIST_PATH / zip_name),
        'zip',
        str(DIST_PATH)
    )

    size_mb = Path(zip_path).stat().st_size / (1024 * 1024)
    print(f"[OK] Archive créée: {zip_path} ({size_mb:.1f} Mo)")
    print(f"\n  Envoyez ce fichier ZIP sur l'autre PC,")
    print(f"  décompressez-le et lancez {EXE_NAME}.exe\n")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--zip":
        build_exe()
        build_portable_zip()
    else:
        build_exe()
