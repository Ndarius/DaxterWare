"""
DaxterWare v1.0.0
Point d'entrée principal de l'application
"""

import sys
import os
from pathlib import Path


def get_base_path() -> Path:
    """
    Dossier de travail de l'application (à côté de l'exe ou du script).
    C'est ici que se trouvent config/, installers/, downloads/, logs/.
    """
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).resolve().parent
    else:
        return Path(__file__).resolve().parent


def get_internal_path() -> Path:
    """
    Dossier des données embarquées (assets, config par défaut).
    En mode PyInstaller --onefile, c'est le dossier temporaire _MEIPASS.
    En mode développement, c'est le même que BASE_PATH.
    """
    if getattr(sys, 'frozen', False):
        return Path(sys._MEIPASS)
    else:
        return Path(__file__).resolve().parent


BASE_PATH = get_base_path()
INTERNAL_PATH = get_internal_path()
sys.path.insert(0, str(BASE_PATH))


def main():
    """Point d'entrée principal"""
    # ─── 1. Initialiser le logging ───
    from core.logger_setup import setup_logging, cleanup_old_logs

    logs_path = BASE_PATH / "logs"
    setup_logging(logs_path, log_level="INFO")
    cleanup_old_logs(logs_path)

    import logging
    logger = logging.getLogger(__name__)
    logger.info("=" * 60)
    logger.info("  DaxterWare - Démarrage")
    logger.info("=" * 60)

    # ─── 2. Charger la configuration ───
    from core.catalog_manager import CatalogManager, SettingsManager

    # Config : d'abord à côté de l'exe, sinon embarquée (_MEIPASS)
    settings_path = BASE_PATH / "config" / "settings.json"
    catalog_path = BASE_PATH / "config" / "software_catalog.json"

    if not settings_path.exists():
        settings_path = INTERNAL_PATH / "config" / "settings.json"
    if not catalog_path.exists():
        catalog_path = INTERNAL_PATH / "config" / "software_catalog.json"

    settings = SettingsManager(settings_path)
    logger.info(f"Configuration chargée: {settings.app_name} v{settings.version}")

    catalog = CatalogManager(catalog_path)
    logger.info(
        f"Catalogue: {catalog.get_software_count()} logiciels "
        f"dans {catalog.get_category_count()} catégories"
    )

    # ─── 3. Vérifier les dépendances (mode dev uniquement) ───
    if not getattr(sys, 'frozen', False):
        try:
            import customtkinter
            logger.info(f"CustomTkinter v{customtkinter.__version__} détecté")
        except ImportError:
            logger.error("CustomTkinter non installé !")
            print("\n[ERREUR] CustomTkinter n'est pas installé.")
            print("Exécutez: pip install -r requirements.txt\n")
            sys.exit(1)

    # ─── 4. Créer les dossiers nécessaires ───
    for folder_key in ["download_folder", "installers_folder", "logs_folder"]:
        folder = BASE_PATH / settings.get(folder_key, folder_key)
        folder.mkdir(parents=True, exist_ok=True)

    # ─── 5. Vérifier les droits admin ───
    from core.installer import InstallerManager

    if InstallerManager.is_admin():
        logger.info("Exécution avec droits administrateur")
    else:
        logger.warning("Exécution SANS droits administrateur - l'installation nécessitera une élévation")

    # ─── 6. Lancer l'interface graphique ───
    from gui.app import SoftwareManagerApp

    logger.info("Lancement de l'interface graphique...")

    app = SoftwareManagerApp(
        catalog=catalog,
        settings=settings,
        base_path=BASE_PATH,
    )

    app.mainloop()

    logger.info("Application fermée proprement")


if __name__ == "__main__":
    main()
