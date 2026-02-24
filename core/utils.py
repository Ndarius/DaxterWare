"""
DaxterWare - Utilitaires
Fonctions utilitaires partagées
"""

import os
import sys
import platform
import ctypes
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def get_system_info() -> dict:
    """Récupère les informations système"""
    return {
        "os": platform.system(),
        "os_version": platform.version(),
        "os_release": platform.release(),
        "architecture": platform.machine(),
        "processor": platform.processor(),
        "python_version": platform.python_version(),
        "hostname": platform.node(),
    }


def get_windows_version() -> str:
    """Retourne la version Windows lisible"""
    release = platform.release()
    version_map = {
        "10": "Windows 10",
        "11": "Windows 11",
    }
    build = platform.version()
    # Windows 11 est détecté par le build >= 22000
    if release == "10" and build:
        try:
            build_number = int(build.split(".")[-1]) if "." in build else int(build)
            if build_number >= 22000:
                return f"Windows 11 (build {build})"
        except (ValueError, IndexError):
            pass
    return version_map.get(release, f"Windows {release}") + f" (build {build})"


def is_64bit_os() -> bool:
    """Vérifie si l'OS est en 64 bits"""
    return platform.machine().endswith("64")


def is_internet_available() -> bool:
    """Vérifie si une connexion Internet est disponible"""
    import socket
    try:
        socket.create_connection(("8.8.8.8", 53), timeout=3)
        return True
    except OSError:
        return False


def format_duration(seconds: float) -> str:
    """Formate une durée en secondes"""
    if seconds < 1:
        return "< 1s"
    elif seconds < 60:
        return f"{seconds:.0f}s"
    elif seconds < 3600:
        m = int(seconds // 60)
        s = int(seconds % 60)
        return f"{m}min {s}s"
    else:
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        return f"{h}h {m}min"


def format_file_size(size_bytes: int) -> str:
    """Formate une taille de fichier"""
    if size_bytes < 1024:
        return f"{size_bytes} o"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} Ko"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} Mo"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} Go"


def ensure_dir(path: Path) -> Path:
    """Crée un dossier s'il n'existe pas"""
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_disk_free_space(path: str = "C:\\") -> Optional[int]:
    """Retourne l'espace disque libre en bytes"""
    try:
        if sys.platform == "win32":
            free_bytes = ctypes.c_ulonglong(0)
            ctypes.windll.kernel32.GetDiskFreeSpaceExW(
                str(path), None, None, ctypes.pointer(free_bytes)
            )
            return free_bytes.value
        else:
            st = os.statvfs(path)
            return st.f_bavail * st.f_frsize
    except Exception:
        return None


def sanitize_filename(filename: str) -> str:
    """Nettoie un nom de fichier des caractères invalides"""
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, "_")
    return filename.strip(". ")
