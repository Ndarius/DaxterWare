"""
DaxterWare - Module de téléchargement
Gère le téléchargement via terminal (curl/BITS/PowerShell) avec détection de setups locaux
"""

import os
import hashlib
import logging
import subprocess
import threading
import time
import re
from pathlib import Path
from typing import Optional, Callable, Dict, List, Tuple
from dataclasses import dataclass
from enum import Enum
from urllib.parse import urlparse, unquote

logger = logging.getLogger(__name__)


class DownloadStatus(Enum):
    """États du téléchargement"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    LOCAL_FOUND = "local_found"


@dataclass
class DownloadProgress:
    """Informations de progression du téléchargement"""
    total_size: int
    downloaded_size: int
    speed: float  # bytes/sec
    eta: float  # secondes restantes
    percentage: float
    status: DownloadStatus


@dataclass
class DownloadResult:
    """Résultat d'un téléchargement"""
    software_id: str
    file_path: Optional[Path]
    status: DownloadStatus
    message: str
    duration: float = 0.0
    was_local: bool = False


# ━━━━━━━━━━━━━━━━━━━━━━━━ Détection setups locaux ━━━━━━━━━━━━━━━━━━━━━━━━

class LocalInstallerDetector:
    """
    Détecte les installateurs déjà présents dans le dossier installers/.
    L'utilisateur peut pré-copier les setups pour éviter le téléchargement.
    """

    INSTALLER_EXTENSIONS = {'.exe', '.msi', '.msix', '.zip'}

    def __init__(self, installers_folder):
        self.installers_folder = Path(installers_folder)
        self.installers_folder.mkdir(parents=True, exist_ok=True)

    def find_installer(self, software: Dict) -> Optional[Path]:
        """
        Cherche un installateur local pour un logiciel.
        
        Priorité de recherche :
        1. Champ 'local_file' explicite dans le catalogue
        2. Fichier nommé exactement <id>.<ext> (ex: chrome.msi)
        3. Fichier contenant l'ID dans son nom
        4. Fichier contenant le nom du logiciel
        """
        sw_id = software.get("id", "").lower()
        sw_name = software.get("name", "").lower()

        if not self.installers_folder.exists():
            return None

        # 1. Champ local_file explicite
        local_file = software.get("local_file", "")
        if local_file:
            path = self.installers_folder / local_file
            if path.exists():
                logger.info(f"Setup local (explicit): {path}")
                return path

        # 2. Nom exact : <id>.<ext>
        for ext in self.INSTALLER_EXTENSIONS:
            exact_path = self.installers_folder / f"{sw_id}{ext}"
            if exact_path.exists():
                logger.info(f"Setup local (exact): {exact_path}")
                return exact_path

        # Lister les fichiers installateurs disponibles
        all_files = [
            f for f in self.installers_folder.iterdir()
            if f.is_file() and f.suffix.lower() in self.INSTALLER_EXTENSIONS
        ]

        # 3. Fichier contenant l'ID
        if sw_id:
            for f in all_files:
                if sw_id in f.stem.lower():
                    logger.info(f"Setup local (id match): {f}")
                    return f

        # 4. Fichier contenant le nom nettoyé
        if sw_name:
            clean_name = re.sub(r'[^a-z0-9]', '', sw_name)
            for f in all_files:
                clean_fname = re.sub(r'[^a-z0-9]', '', f.stem.lower())
                if clean_name and clean_name in clean_fname:
                    logger.info(f"Setup local (name match): {f}")
                    return f

        return None

    def list_available_installers(self) -> List[Tuple[str, int]]:
        """Liste tous les installateurs présents"""
        result = []
        if self.installers_folder.exists():
            for f in self.installers_folder.iterdir():
                if f.is_file() and f.suffix.lower() in self.INSTALLER_EXTENSIONS:
                    result.append((f.name, f.stat().st_size))
        return sorted(result)

    def get_installer_count(self) -> int:
        """Nombre d'installateurs locaux disponibles"""
        if not self.installers_folder.exists():
            return 0
        return sum(
            1 for f in self.installers_folder.iterdir()
            if f.is_file() and f.suffix.lower() in self.INSTALLER_EXTENSIONS
        )


# ━━━━━━━━━━━━━━━━━━━━━━ Téléchargement via terminal ━━━━━━━━━━━━━━━━━━━━━━

class TerminalDownloader:
    """
    Téléchargement via terminal (curl/BITS/PowerShell) en arrière-plan.
    Plus rapide que Python requests car utilise les connexions natives Windows.
    """

    def __init__(self, download_folder):
        self.download_folder = Path(download_folder)
        self.download_folder.mkdir(parents=True, exist_ok=True)
        self._active_processes: Dict[str, subprocess.Popen] = {}

    def _get_filename(self, url: str, software: Dict) -> str:
        """Détermine le nom du fichier de sortie"""
        sw_id = software.get("id", "unknown")
        installer_type = software.get("installer_type", "exe")

        ext_map = {
            "msi": ".msi", "msix": ".msix", "exe": ".exe",
            "exe_nsis": ".exe", "exe_inno": ".exe",
            "exe_installshield": ".exe", "zip": ".zip",
        }
        ext = ext_map.get(installer_type, ".exe")

        # Essayer d'extraire depuis l'URL
        parsed = urlparse(url)
        url_filename = os.path.basename(unquote(parsed.path))
        if url_filename and any(url_filename.endswith(e) for e in ext_map.values()):
            return url_filename

        return f"{sw_id}{ext}"

    def download_file(
        self,
        software: Dict,
        progress_callback: Optional[Callable[[DownloadProgress], None]] = None,
        cancel_event: Optional[threading.Event] = None,
    ) -> DownloadResult:
        """
        Télécharge via curl → BITS → PowerShell (cascade de fallbacks).
        """
        start_time = time.time()
        sw_id = software.get("id", "unknown")
        sw_name = software.get("name", "Unknown")
        url = software.get("url", "")

        if not url:
            return DownloadResult(
                software_id=sw_id, file_path=None,
                status=DownloadStatus.FAILED,
                message="URL de téléchargement non spécifiée"
            )

        if cancel_event is None:
            cancel_event = threading.Event()

        filename = self._get_filename(url, software)
        file_path = self.download_folder / filename

        # Supprimer fichier partiel
        if file_path.exists():
            file_path.unlink()

        logger.info(f"DL terminal {sw_name}: {url}")

        if progress_callback:
            progress_callback(DownloadProgress(
                total_size=0, downloaded_size=0,
                speed=0, eta=0, percentage=2.0,
                status=DownloadStatus.IN_PROGRESS,
            ))

        # Essayer les méthodes dans l'ordre
        for method_name, method in [
            ("curl", self._dl_curl),
            ("BITS", self._dl_bits),
            ("PowerShell", self._dl_powershell),
        ]:
            try:
                result = method(url, file_path, sw_id, sw_name, progress_callback, cancel_event)
                if result is not None:
                    return result
            except Exception as e:
                logger.info(f"{method_name} échoué: {e}")
                if file_path.exists():
                    file_path.unlink()
                continue

        return DownloadResult(
            software_id=sw_id, file_path=None,
            status=DownloadStatus.FAILED,
            message="Toutes les méthodes de téléchargement ont échoué",
            duration=time.time() - start_time,
        )

    def _monitor_file_progress(
        self, process, file_path, sw_id, sw_name,
        progress_callback, cancel_event, start_time
    ) -> Optional[DownloadResult]:
        """Surveille un process de téléchargement via la taille du fichier"""
        self._active_processes[sw_id] = process
        last_size = 0
        last_time = time.time()

        while process.poll() is None:
            if cancel_event and cancel_event.is_set():
                process.kill()
                process.wait()
                if file_path.exists():
                    file_path.unlink()
                return DownloadResult(
                    software_id=sw_id, file_path=None,
                    status=DownloadStatus.CANCELLED,
                    message="Téléchargement annulé",
                    duration=time.time() - start_time,
                )

            time.sleep(0.8)

            if file_path.exists() and progress_callback:
                current_size = file_path.stat().st_size
                now = time.time()
                elapsed = now - last_time

                speed = (current_size - last_size) / elapsed if elapsed > 0.1 else 0
                last_size = current_size
                last_time = now

                # Pourcentage estimé (plafond à 90% en attendant la fin)
                pct = min(90.0, 5.0 + (current_size / (1024 * 1024)) * 1.5)

                progress_callback(DownloadProgress(
                    total_size=0, downloaded_size=current_size,
                    speed=speed, eta=0, percentage=pct,
                    status=DownloadStatus.IN_PROGRESS,
                ))

        # Terminé
        self._active_processes.pop(sw_id, None)

        if process.returncode == 0 and file_path.exists() and file_path.stat().st_size > 1024:
            size = file_path.stat().st_size
            duration = time.time() - start_time
            avg_speed = size / duration if duration > 0 else 0

            if progress_callback:
                progress_callback(DownloadProgress(
                    total_size=size, downloaded_size=size,
                    speed=avg_speed, eta=0, percentage=100.0,
                    status=DownloadStatus.COMPLETED,
                ))

            return DownloadResult(
                software_id=sw_id, file_path=file_path,
                status=DownloadStatus.COMPLETED,
                message=f"Téléchargé ({_format_size(size)}) — {_format_speed(avg_speed)}",
                duration=duration,
            )

        return None  # Signifier l'échec pour essayer le fallback suivant

    def _dl_curl(self, url, file_path, sw_id, sw_name, progress_callback, cancel_event):
        """Télécharge via curl.exe (natif Windows 10+)"""
        start_time = time.time()

        # Vérifier curl
        try:
            subprocess.run(
                ["curl.exe", "--version"], capture_output=True,
                timeout=5, creationflags=subprocess.CREATE_NO_WINDOW,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return None  # Curl non dispo

        cmd = [
            "curl.exe", "-L",
            "-o", str(file_path),
            "--connect-timeout", "15",
            "--max-time", "3600",
            "--retry", "2",
            "-A", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0",
            url,
        ]

        logger.info(f"curl: {sw_name}")
        process = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )

        result = self._monitor_file_progress(
            process, file_path, sw_id, sw_name,
            progress_callback, cancel_event, start_time
        )

        if result:
            result.message = result.message.replace("Téléchargé", "Téléchargé via curl")
            logger.info(f"curl OK: {sw_name} — {result.message}")
        else:
            stderr = process.stderr.read().decode(errors='ignore')[:200] if process.stderr else ""
            logger.warning(f"curl échoué pour {sw_name}: code {process.returncode} — {stderr}")
            if file_path.exists():
                file_path.unlink()

        return result

    def _dl_bits(self, url, file_path, sw_id, sw_name, progress_callback, cancel_event):
        """Télécharge via BITS (Background Intelligent Transfer Service)"""
        start_time = time.time()

        ps_cmd = (
            f'Start-BitsTransfer -Source "{url}" '
            f'-Destination "{file_path}" -Priority High'
        )

        logger.info(f"BITS: {sw_name}")
        process = subprocess.Popen(
            ["powershell.exe", "-NoProfile", "-Command", ps_cmd],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )

        result = self._monitor_file_progress(
            process, file_path, sw_id, sw_name,
            progress_callback, cancel_event, start_time
        )

        if result:
            result.message = result.message.replace("Téléchargé", "Téléchargé via BITS")
        else:
            if file_path.exists():
                file_path.unlink()

        return result

    def _dl_powershell(self, url, file_path, sw_id, sw_name, progress_callback, cancel_event):
        """Fallback: Invoke-WebRequest PowerShell"""
        start_time = time.time()

        ps_cmd = (
            '$ProgressPreference = "SilentlyContinue"; '
            '[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; '
            f'Invoke-WebRequest -Uri "{url}" -OutFile "{file_path}" -UseBasicParsing'
        )

        logger.info(f"PowerShell IWR: {sw_name}")
        process = subprocess.Popen(
            ["powershell.exe", "-NoProfile", "-Command", ps_cmd],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )

        result = self._monitor_file_progress(
            process, file_path, sw_id, sw_name,
            progress_callback, cancel_event, start_time
        )

        if result:
            result.message = result.message.replace("Téléchargé", "Téléchargé via PowerShell")
        else:
            stderr = process.stderr.read().decode(errors='ignore')[:200] if process.stderr else ""
            if file_path.exists():
                file_path.unlink()
            return DownloadResult(
                software_id=sw_id, file_path=None,
                status=DownloadStatus.FAILED,
                message=f"Échec PowerShell: {stderr}",
                duration=time.time() - start_time,
            )

        return result

    def cancel_download(self, software_id: str):
        proc = self._active_processes.get(software_id)
        if proc:
            try:
                proc.kill()
            except OSError:
                pass

    def cancel_all_downloads(self):
        for proc in self._active_processes.values():
            try:
                proc.kill()
            except OSError:
                pass


# ━━━━━━━━━━━━━━━━━━━━━━━ Gestionnaire principal ━━━━━━━━━━━━━━━━━━━━━━━━

class DownloadManager:
    """
    Gestionnaire principal.
    1. Vérifie le dossier installers/ pour les setups pré-copiés
    2. Sinon télécharge via terminal (curl > BITS > PowerShell)
    """

    def __init__(self, download_folder, installers_folder, max_concurrent: int = 3):
        self.download_folder = Path(download_folder)
        self.download_folder.mkdir(parents=True, exist_ok=True)
        self.max_concurrent = max_concurrent

        self.local_detector = LocalInstallerDetector(installers_folder)
        self.terminal_downloader = TerminalDownloader(download_folder)

    def download_file(
        self,
        software: Dict,
        progress_callback: Optional[Callable[[DownloadProgress], None]] = None,
        cancel_event: Optional[threading.Event] = None,
    ) -> DownloadResult:
        """
        Obtient l'installateur : local si dispo, sinon téléchargement terminal.
        """
        sw_id = software.get("id", "unknown")
        sw_name = software.get("name", "Unknown")

        # ─── 1. Setup local ? ───
        local_path = self.local_detector.find_installer(software)
        if local_path:
            logger.info(f"✓ Setup local pour {sw_name}: {local_path}")

            if progress_callback:
                progress_callback(DownloadProgress(
                    total_size=local_path.stat().st_size,
                    downloaded_size=local_path.stat().st_size,
                    speed=0, eta=0, percentage=100.0,
                    status=DownloadStatus.LOCAL_FOUND,
                ))

            return DownloadResult(
                software_id=sw_id,
                file_path=local_path,
                status=DownloadStatus.COMPLETED,
                message=f"📁 Setup local: {local_path.name}",
                duration=0.0,
                was_local=True,
            )

        # ─── 2. Téléchargement terminal ───
        logger.info(f"Pas de setup local pour {sw_name} → téléchargement terminal")
        return self.terminal_downloader.download_file(
            software,
            progress_callback=progress_callback,
            cancel_event=cancel_event,
        )

    def cancel_download(self, software_id: str):
        self.terminal_downloader.cancel_download(software_id)

    def cancel_all_downloads(self):
        self.terminal_downloader.cancel_all_downloads()

    def get_local_count(self) -> int:
        return self.local_detector.get_installer_count()

    def list_local_installers(self) -> List[Tuple[str, int]]:
        return self.local_detector.list_available_installers()

    @staticmethod
    def format_speed(speed_bytes: float) -> str:
        return _format_speed(speed_bytes)

    @staticmethod
    def format_eta(seconds: float) -> str:
        return _format_eta(seconds)


class BatchDownloader:
    """Téléchargements par lots"""

    def __init__(self, download_manager: DownloadManager):
        self.download_manager = download_manager
        self._cancel_all = threading.Event()

    def download_batch(
        self, software_list: list,
        progress_callback: Optional[Callable[[str, DownloadProgress], None]] = None,
        completion_callback: Optional[Callable[[DownloadResult], None]] = None,
    ) -> list:
        results = []
        for software in software_list:
            if self._cancel_all.is_set():
                results.append(DownloadResult(
                    software_id=software.get("id", "unknown"),
                    file_path=None,
                    status=DownloadStatus.CANCELLED,
                    message="Annulé",
                ))
                continue

            def progress_wrapper(progress: DownloadProgress):
                if progress_callback:
                    progress_callback(software.get("id", "unknown"), progress)

            result = self.download_manager.download_file(
                software, progress_callback=progress_wrapper,
            )
            results.append(result)
            if completion_callback:
                completion_callback(result)

        return results

    def cancel_all(self):
        self._cancel_all.set()
        self.download_manager.cancel_all_downloads()


# ━━━━━━━━━━━━━━━━━━━━━━━━ Fonctions utilitaires ━━━━━━━━━━━━━━━━━━━━━━━━

def _format_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


def _format_speed(speed_bytes: float) -> str:
    if speed_bytes < 1024:
        return f"{speed_bytes:.0f} B/s"
    elif speed_bytes < 1024 * 1024:
        return f"{speed_bytes / 1024:.1f} KB/s"
    else:
        return f"{speed_bytes / (1024 * 1024):.1f} MB/s"


def _format_eta(seconds: float) -> str:
    if seconds <= 0:
        return "..."
    if seconds < 60:
        return f"{seconds:.0f}s"
    elif seconds < 3600:
        return f"{seconds / 60:.0f}min"
    else:
        return f"{seconds / 3600:.1f}h"
