"""
DaxterWare - Module de gestion des installations
Gère l'installation silencieuse des logiciels sur Windows
"""

import subprocess
import os
import sys
import winreg
import ctypes
import logging
import json
import hashlib
from pathlib import Path
from typing import Optional, Dict, Tuple, Callable
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class InstallerType(Enum):
    """Types d'installateurs supportés"""
    MSI = "msi"
    EXE = "exe"
    EXE_NSIS = "exe_nsis"
    EXE_INNO = "exe_inno"
    EXE_INSTALLSHIELD = "exe_installshield"
    MSIX = "msix"
    ZIP = "zip"


class InstallStatus(Enum):
    """États d'installation"""
    PENDING = "pending"
    DOWNLOADING = "downloading"
    INSTALLING = "installing"
    SUCCESS = "success"
    FAILED = "failed"
    ALREADY_INSTALLED = "already_installed"
    CANCELLED = "cancelled"


@dataclass
class InstallResult:
    """Résultat d'une installation"""
    software_id: str
    software_name: str
    status: InstallStatus
    message: str
    return_code: Optional[int] = None
    duration: float = 0.0


class InstallerManager:
    """Gestionnaire principal des installations"""
    
    # Arguments silencieux par défaut selon le type d'installateur
    DEFAULT_SILENT_ARGS = {
        InstallerType.MSI: "/qn /norestart",
        InstallerType.EXE: "/S",
        InstallerType.EXE_NSIS: "/S",
        InstallerType.EXE_INNO: "/VERYSILENT /NORESTART /SUPPRESSMSGBOXES",
        InstallerType.EXE_INSTALLSHIELD: "/s /v\"/qn\"",
        InstallerType.MSIX: "",
        InstallerType.ZIP: "",
    }
    
    def __init__(self, base_path: Path):
        self.base_path = base_path
        self.installers_path = base_path / "installers"
        self.downloads_path = base_path / "downloads"
        self.logs_path = base_path / "logs"
        
        # Créer les dossiers nécessaires
        for path in [self.installers_path, self.downloads_path, self.logs_path]:
            path.mkdir(parents=True, exist_ok=True)
    
    @staticmethod
    def is_admin() -> bool:
        """Vérifie si le programme s'exécute avec des droits administrateur"""
        try:
            return ctypes.windll.shell32.IsUserAnAdmin()
        except Exception:
            return False
    
    @staticmethod
    def request_admin_elevation():
        """Demande l'élévation des privilèges (UAC)"""
        if not InstallerManager.is_admin():
            logger.info("Demande d'élévation des privilèges administrateur...")
            ctypes.windll.shell32.ShellExecuteW(
                None, 
                "runas", 
                sys.executable, 
                " ".join(sys.argv), 
                None, 
                1
            )
            sys.exit(0)

    @staticmethod
    def _expand_env_path(path_value: str) -> str:
        """Développe les variables d'environnement d'un chemin."""
        return os.path.expandvars(path_value or "")

    @staticmethod
    def _iter_registry_targets(software: Dict) -> list:
        """
        Retourne toutes les clés registre de détection possibles.
        Supporte:
        - detect_registry: str
        - detect_registry_any: list[str]
        """
        targets = []
        primary = software.get("detect_registry", "")
        if isinstance(primary, str) and primary.strip():
            targets.append(primary.strip())

        additional = software.get("detect_registry_any", [])
        if isinstance(additional, list):
            for item in additional:
                if isinstance(item, str) and item.strip():
                    targets.append(item.strip())

        # Dédupliquer en conservant l'ordre
        seen = set()
        unique = []
        for target in targets:
            if target not in seen:
                seen.add(target)
                unique.append(target)
        return unique

    @staticmethod
    def _iter_file_targets(software: Dict) -> list:
        """
        Retourne toutes les cibles fichier à vérifier.
        Supporte:
        - detect_path: str
        - detect_paths_any: list[str]
        """
        targets = []
        primary = software.get("detect_path", "")
        if isinstance(primary, str) and primary.strip():
            targets.append(primary.strip())

        additional = software.get("detect_paths_any", [])
        if isinstance(additional, list):
            for item in additional:
                if isinstance(item, str) and item.strip():
                    targets.append(item.strip())

        seen = set()
        unique = []
        for target in targets:
            if target not in seen:
                seen.add(target)
                unique.append(target)
        return unique

    @staticmethod
    def _registry_key_exists(detect_key: str) -> bool:
        """Vérifie l'existence d'une clé de registre Windows."""
        parts = detect_key.split("\\", 1)
        if len(parts) != 2:
            return False

        hive_map = {
            "HKLM": winreg.HKEY_LOCAL_MACHINE,
            "HKCU": winreg.HKEY_CURRENT_USER,
            "HKCR": winreg.HKEY_CLASSES_ROOT,
        }

        hive_name = parts[0]
        key_path = parts[1]
        hive = hive_map.get(hive_name)
        if hive is None:
            return False

        access_modes = [
            winreg.KEY_READ,
            winreg.KEY_READ | winreg.KEY_WOW64_64KEY,
            winreg.KEY_READ | winreg.KEY_WOW64_32KEY,
        ]

        for access_mode in access_modes:
            try:
                key = winreg.OpenKey(hive, key_path, 0, access_mode)
                winreg.CloseKey(key)
                return True
            except OSError:
                continue

        return False
    
    def check_software_installed(self, software: Dict) -> bool:
        """
        Vérifie si un logiciel est déjà installé via le registre Windows
        
        Args:
            software: Dictionnaire contenant les infos du logiciel
            
        Returns:
            True si le logiciel est installé, False sinon
        """
        # 1) Détection registre (une ou plusieurs clés)
        for detect_key in self._iter_registry_targets(software):
            if self._registry_key_exists(detect_key):
                return True

        # 2) Détection par chemins fichiers (utile pour certains setup user-space)
        for raw_path in self._iter_file_targets(software):
            expanded = Path(self._expand_env_path(raw_path))
            try:
                if expanded.exists():
                    return True
            except OSError:
                continue

        return False
    
    def get_installed_version(self, software: Dict) -> Optional[str]:
        """
        Récupère la version installée d'un logiciel
        
        Args:
            software: Dictionnaire contenant les infos du logiciel
            
        Returns:
            La version installée ou None
        """
        hive_map = {
            "HKLM": winreg.HKEY_LOCAL_MACHINE,
            "HKCU": winreg.HKEY_CURRENT_USER,
        }

        for detect_key in self._iter_registry_targets(software):
            parts = detect_key.split("\\", 1)
            if len(parts) != 2:
                continue

            hive = hive_map.get(parts[0])
            if hive is None:
                continue

            access_modes = [
                winreg.KEY_READ,
                winreg.KEY_READ | winreg.KEY_WOW64_64KEY,
                winreg.KEY_READ | winreg.KEY_WOW64_32KEY,
            ]

            for access_mode in access_modes:
                try:
                    key = winreg.OpenKey(hive, parts[1], 0, access_mode)
                    try:
                        version, _ = winreg.QueryValueEx(key, "DisplayVersion")
                        if version:
                            return str(version)
                    except OSError:
                        pass
                    finally:
                        winreg.CloseKey(key)
                except OSError:
                    continue
        
        return None
    
    def verify_file_hash(self, file_path: Path, expected_hash: str) -> bool:
        """
        Vérifie l'intégrité d'un fichier via son hash SHA256
        
        Args:
            file_path: Chemin vers le fichier
            expected_hash: Hash SHA256 attendu
            
        Returns:
            True si le hash correspond, False sinon
        """
        if not expected_hash:
            logger.warning(f"Pas de hash fourni pour {file_path.name}, vérification ignorée")
            return True
        
        logger.info(f"Vérification du hash SHA256 de {file_path.name}...")
        
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256_hash.update(chunk)
        
        computed_hash = sha256_hash.hexdigest().lower()
        expected_hash = expected_hash.lower()
        
        if computed_hash == expected_hash:
            logger.info(f"Hash vérifié avec succès: {computed_hash}")
            return True
        else:
            logger.error(f"Hash invalide! Attendu: {expected_hash}, Obtenu: {computed_hash}")
            return False
    
    def build_install_command(
        self, 
        installer_path: Path, 
        software: Dict
    ) -> Tuple[str, list]:
        """
        Construit la commande d'installation
        
        Args:
            installer_path: Chemin vers l'installateur
            software: Dictionnaire contenant les infos du logiciel
            
        Returns:
            Tuple (type_commande, liste_arguments)
        """
        installer_type = software.get("installer_type", "exe")
        silent_args = software.get("silent_args", "")
        
        # Utiliser les arguments par défaut si non spécifiés
        if not silent_args:
            try:
                inst_type = InstallerType(installer_type)
                silent_args = self.DEFAULT_SILENT_ARGS.get(inst_type, "")
            except ValueError:
                silent_args = "/S"
        
        if installer_type == "msi":
            # Installation MSI via msiexec
            cmd = ["msiexec", "/i", str(installer_path)]
            cmd.extend(silent_args.split())
            return "msiexec", cmd
        
        elif installer_type == "msix":
            # Installation MSIX via PowerShell
            ps_cmd = f"Add-AppxPackage -Path '{installer_path}'"
            return "powershell", ["powershell", "-Command", ps_cmd]
        
        else:
            # Installation EXE standard
            cmd = [str(installer_path)]
            cmd.extend(silent_args.split())
            return "exe", cmd
    
    def install_software(
        self, 
        software: Dict, 
        installer_path: Path,
        progress_callback: Optional[Callable[[str], None]] = None
    ) -> InstallResult:
        """
        Installe un logiciel
        
        Args:
            software: Dictionnaire contenant les infos du logiciel
            installer_path: Chemin vers l'installateur
            progress_callback: Fonction de callback pour les mises à jour de statut
            
        Returns:
            InstallResult avec le résultat de l'installation
        """
        import time
        start_time = time.time()
        
        software_id = software.get("id", "unknown")
        software_name = software.get("name", "Unknown Software")
        
        def log_progress(msg: str):
            logger.info(msg)
            if progress_callback:
                progress_callback(msg)
        
        # Vérifier les droits administrateur (optionnel selon le logiciel)
        requires_admin = bool(software.get("requires_admin", True))
        if requires_admin and not self.is_admin():
            return InstallResult(
                software_id=software_id,
                software_name=software_name,
                status=InstallStatus.FAILED,
                message="Droits administrateur requis"
            )
        
        # Vérifier si déjà installé
        if self.check_software_installed(software):
            installed_version = self.get_installed_version(software)
            msg = f"{software_name} est déjà installé"
            if installed_version:
                msg += f" (version {installed_version})"
            log_progress(msg)
            return InstallResult(
                software_id=software_id,
                software_name=software_name,
                status=InstallStatus.ALREADY_INSTALLED,
                message=msg,
                duration=time.time() - start_time
            )
        
        # Vérifier que l'installateur existe
        if not installer_path.exists():
            return InstallResult(
                software_id=software_id,
                software_name=software_name,
                status=InstallStatus.FAILED,
                message=f"Installateur non trouvé: {installer_path}"
            )
        
        # Vérifier le hash si disponible
        expected_hash = software.get("sha256", "")
        if expected_hash and not self.verify_file_hash(installer_path, expected_hash):
            return InstallResult(
                software_id=software_id,
                software_name=software_name,
                status=InstallStatus.FAILED,
                message="Vérification du hash échouée - fichier potentiellement corrompu"
            )
        
        # Construire la commande d'installation
        cmd_type, cmd = self.build_install_command(installer_path, software)
        
        log_progress(f"Installation de {software_name}...")
        logger.debug(f"Commande: {' '.join(cmd)}")
        
        try:
            # Exécuter l'installation
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=1800,  # 30 minutes max
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            duration = time.time() - start_time
            
            # Codes de retour courants de succès
            success_codes = [0, 3010, 1641]  # 3010/1641 = succès avec redémarrage
            installed_after = self.check_software_installed(software)

            if result.returncode in success_codes or installed_after:
                msg = f"{software_name} installé avec succès"
                if result.returncode in (3010, 1641):
                    msg += " (redémarrage recommandé)"
                elif result.returncode not in success_codes and installed_after:
                    msg += f" (confirmé malgré code {result.returncode})"
                log_progress(msg)

                return InstallResult(
                    software_id=software_id,
                    software_name=software_name,
                    status=InstallStatus.SUCCESS,
                    message=msg,
                    return_code=result.returncode,
                    duration=duration
                )

            # Fallback spécifique Spotify: certains installeurs acceptent des variantes d'arguments
            if software_id.lower() == "spotify":
                fallback_args = [
                    "/SILENT",
                    "/silent",
                    "/S",
                    "--silent",
                ]
                current_silent_args = (software.get("silent_args", "") or "").strip().lower()

                for alt_args in fallback_args:
                    if alt_args.strip().lower() == current_silent_args:
                        continue

                    retry_cmd = [str(installer_path)] + alt_args.split()
                    logger.info(f"Retry Spotify avec arguments: {alt_args}")
                    retry_result = subprocess.run(
                        retry_cmd,
                        capture_output=True,
                        text=True,
                        timeout=1800,
                        creationflags=subprocess.CREATE_NO_WINDOW
                    )

                    if retry_result.returncode in success_codes or self.check_software_installed(software):
                        msg = f"{software_name} installé avec succès (fallback args: {alt_args})"
                        log_progress(msg)
                        return InstallResult(
                            software_id=software_id,
                            software_name=software_name,
                            status=InstallStatus.SUCCESS,
                            message=msg,
                            return_code=retry_result.returncode,
                            duration=time.time() - start_time,
                        )

            error_msg = result.stderr or f"Code de retour: {result.returncode}"
            log_progress(f"Échec de l'installation de {software_name}: {error_msg}")

            return InstallResult(
                software_id=software_id,
                software_name=software_name,
                status=InstallStatus.FAILED,
                message=error_msg,
                return_code=result.returncode,
                duration=duration
            )
                
        except subprocess.TimeoutExpired:
            return InstallResult(
                software_id=software_id,
                software_name=software_name,
                status=InstallStatus.FAILED,
                message="Installation expirée (timeout de 30 minutes dépassé)",
                duration=time.time() - start_time
            )
        except Exception as e:
            return InstallResult(
                software_id=software_id,
                software_name=software_name,
                status=InstallStatus.FAILED,
                message=f"Erreur lors de l'installation: {str(e)}",
                duration=time.time() - start_time
            )
    
    def uninstall_software(self, software: Dict) -> InstallResult:
        """
        Désinstalle un logiciel via le registre Windows
        
        Args:
            software: Dictionnaire contenant les infos du logiciel
            
        Returns:
            InstallResult avec le résultat de la désinstallation
        """
        software_id = software.get("id", "unknown")
        software_name = software.get("name", "Unknown Software")
        
        # Cette fonctionnalité nécessiterait de récupérer UninstallString du registre
        # Implémentation basique pour la V1
        
        return InstallResult(
            software_id=software_id,
            software_name=software_name,
            status=InstallStatus.FAILED,
            message="Fonctionnalité de désinstallation non implémentée dans cette version"
        )


def get_all_installed_software() -> list:
    """
    Récupère la liste de tous les logiciels installés sur le système
    
    Returns:
        Liste de dictionnaires avec les infos des logiciels installés
    """
    installed = []
    
    uninstall_paths = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
    ]
    
    for hive, path in uninstall_paths:
        try:
            key = winreg.OpenKey(hive, path, 0, winreg.KEY_READ)
            
            for i in range(winreg.QueryInfoKey(key)[0]):
                try:
                    subkey_name = winreg.EnumKey(key, i)
                    subkey = winreg.OpenKey(key, subkey_name)
                    
                    try:
                        name = winreg.QueryValueEx(subkey, "DisplayName")[0]
                        
                        software_info = {
                            "name": name,
                            "id": subkey_name,
                        }
                        
                        # Récupérer les infos supplémentaires
                        for value_name in ["DisplayVersion", "Publisher", "InstallDate", "InstallLocation"]:
                            try:
                                value = winreg.QueryValueEx(subkey, value_name)[0]
                                software_info[value_name.lower()] = value
                            except WindowsError:
                                pass
                        
                        installed.append(software_info)
                        
                    except WindowsError:
                        pass
                    finally:
                        winreg.CloseKey(subkey)
                        
                except WindowsError:
                    pass
                    
            winreg.CloseKey(key)
            
        except WindowsError:
            pass
    
    # Dédupliquer par nom
    seen = set()
    unique_installed = []
    for sw in installed:
        if sw["name"] not in seen:
            seen.add(sw["name"])
            unique_installed.append(sw)
    
    return sorted(unique_installed, key=lambda x: x["name"].lower())
