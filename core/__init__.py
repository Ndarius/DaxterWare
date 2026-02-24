"""
DaxterWare - Core Module
"""

from .installer import InstallerManager, InstallResult, InstallStatus, InstallerType, get_all_installed_software
from .downloader import DownloadManager, DownloadResult, DownloadStatus, DownloadProgress, BatchDownloader, LocalInstallerDetector
from .catalog_manager import CatalogManager, SettingsManager
from .logger_setup import setup_logging, cleanup_old_logs

__all__ = [
    'InstallerManager',
    'InstallResult', 
    'InstallStatus',
    'InstallerType',
    'get_all_installed_software',
    'DownloadManager',
    'DownloadResult',
    'DownloadStatus',
    'DownloadProgress',
    'BatchDownloader',
    'LocalInstallerDetector',
    'CatalogManager',
    'SettingsManager',
    'setup_logging',
    'cleanup_old_logs',
]
