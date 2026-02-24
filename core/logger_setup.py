"""
DaxterWare - Configuration du logging
"""

import logging
import sys
from pathlib import Path
from datetime import datetime


def setup_logging(logs_folder: Path, log_level: str = "INFO") -> logging.Logger:
    """
    Configure le système de logging de l'application

    Args:
        logs_folder: Dossier pour les fichiers de log
        log_level: Niveau de log (DEBUG, INFO, WARNING, ERROR)

    Returns:
        Logger racine configuré
    """
    logs_folder.mkdir(parents=True, exist_ok=True)

    # Nom du fichier de log avec la date
    log_filename = f"daxterware_{datetime.now().strftime('%Y%m%d')}.log"
    log_filepath = logs_folder / log_filename

    # Niveau de log
    level = getattr(logging, log_level.upper(), logging.INFO)

    # Format des messages
    file_format = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)-25s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    console_format = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%H:%M:%S"
    )

    # Logger racine
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Supprimer les handlers existants
    root_logger.handlers.clear()

    # Handler fichier
    file_handler = logging.FileHandler(log_filepath, encoding='utf-8')
    file_handler.setLevel(level)
    file_handler.setFormatter(file_format)
    root_logger.addHandler(file_handler)

    # Handler console
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(console_format)
    root_logger.addHandler(console_handler)

    # Réduire le bruit des librairies externes
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)

    root_logger.info(f"Logging initialisé - Niveau: {log_level} - Fichier: {log_filepath}")

    return root_logger


def cleanup_old_logs(logs_folder: Path, max_days: int = 30):
    """
    Supprime les fichiers de log plus anciens que max_days

    Args:
        logs_folder: Dossier des logs
        max_days: Nombre de jours de rétention
    """
    if not logs_folder.exists():
        return

    now = datetime.now()
    count = 0

    for log_file in logs_folder.glob("daxterware_*.log"):
        try:
            file_date_str = log_file.stem.replace("softwaremanager_", "")
            file_date = datetime.strptime(file_date_str, "%Y%m%d")
            age = (now - file_date).days

            if age > max_days:
                log_file.unlink()
                count += 1
        except (ValueError, OSError):
            pass

    if count > 0:
        logging.getLogger(__name__).info(f"{count} ancien(s) fichier(s) de log supprimé(s)")
