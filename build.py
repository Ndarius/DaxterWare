"""
DaxterWare - Script de build
Crée un exécutable Windows autonome avec PyInstaller
Aucune installation de Python nécessaire sur le PC cible
"""

import subprocess
import sys
import shutil
from pathlib import Path
import zipfile
from datetime import datetime

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
    if BUILD_PATH.exists():
        print(f"[...] Nettoyage de {BUILD_PATH.name}/")
        shutil.rmtree(BUILD_PATH, ignore_errors=True)

    if DIST_PATH.exists():
        print(f"[...] Nettoyage de {DIST_PATH.name}/")
        for item in DIST_PATH.iterdir():
            try:
                if item.is_dir():
                    shutil.rmtree(item)
                else:
                    item.unlink()
            except PermissionError:
                print(f"[WARN] Impossible de supprimer {item.name} (fichier en cours d'utilisation).")

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
        "--uac-admin",                  # Demande les droits admin dès le lancement
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
    for folder_name in ["config", "downloads", "installers", "offline", "logs"]:
        (dist_app / folder_name).mkdir(parents=True, exist_ok=True)

    # Copier la config à côté de l'exe (pour pouvoir éditer)
    import shutil as sh2
    for cfg_file in (BASE_PATH / "config").glob("*.json"):
        sh2.copy2(cfg_file, dist_app / "config" / cfg_file.name)

    # Copier les setups offline (si présents) pour distribution clé en main
    source_offline = BASE_PATH / "offline"
    target_offline = dist_app / "offline"
    if source_offline.exists() and source_offline.is_dir():
        for item in source_offline.iterdir():
            destination = target_offline / item.name
            if item.is_dir():
                sh2.copytree(item, destination, dirs_exist_ok=True)
            elif item.is_file():
                sh2.copy2(item, destination)

    print("\n" + "=" * 60)
    print(f"  BUILD TERMINÉ AVEC SUCCÈS")
    print("=" * 60)
    print(f"\n  Exécutable: {dist_app / (EXE_NAME + '.exe')}")
    print(f"\n  Pour distribuer sur un autre PC :")
    print(f"  1. Copiez le contenu complet de dist/")
    print(f"  2. Les setups offline doivent être dans offline/<Classification>/")
    print(f"  3. Lancez {EXE_NAME}.exe")
    print(f"  => Le mode offline sera visible chez la personne si le dossier offline est copié.\n")


def build_portable_zip():
    """Crée un ZIP portable prêt à distribuer"""
    dist_app = DIST_PATH
    if not (dist_app / f"{EXE_NAME}.exe").exists():
        print("[ERREUR] Faites d'abord un build avec: python build.py")
        return

    zip_name = f"{EXE_NAME}_Portable"
    zip_path = DIST_PATH / f"{zip_name}.zip"
    print(f"\n[...] Création de l'archive {zip_path.name}...")

    if zip_path.exists():
        try:
            zip_path.unlink()
        except PermissionError:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            zip_path = DIST_PATH / f"{zip_name}_{ts}.zip"
            print(f"[WARN] Archive verrouillée, création de {zip_path.name} à la place.")

    file_count = 0
    with zipfile.ZipFile(zip_path, mode="w", compression=zipfile.ZIP_DEFLATED, allowZip64=True) as zf:
        for file_path in sorted(dist_app.rglob("*")):
            if not file_path.is_file():
                continue
            # Ne jamais inclure le zip de sortie lui-même
            if file_path.resolve() == zip_path.resolve():
                continue

            arcname = file_path.relative_to(dist_app)
            zf.write(file_path, arcname.as_posix())
            file_count += 1

    size_mb = zip_path.stat().st_size / (1024 * 1024)
    print(f"[OK] Archive créée: {zip_path} ({size_mb:.1f} Mo, {file_count} fichier(s))")
    print(f"\n  Envoyez ce fichier ZIP sur l'autre PC,")
    print(f"  décompressez-le et lancez {EXE_NAME}.exe\n")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--zip":
        build_exe()
        build_portable_zip()
    else:
        build_exe()
