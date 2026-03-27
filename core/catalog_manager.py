"""
DaxterWare - Gestionnaire de catalogue
Charge, filtre et gère le catalogue de logiciels
"""

import json
import copy
import logging
import re
from pathlib import Path
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class CatalogManager:
    """Gestionnaire du catalogue de logiciels"""

    OFFLINE_EXTENSIONS = {".exe", ".msi", ".msix", ".zip"}

    def __init__(self, catalog_path: Path, offline_path: Optional[Path] = None):
        self.catalog_path = catalog_path
        self.offline_path = offline_path
        self._catalog: Dict = {}
        self._categories: List[Dict] = []
        self._all_software: List[Dict] = []
        self.load()

    def load(self) -> bool:
        """Charge le catalogue depuis le fichier JSON"""
        try:
            with open(self.catalog_path, 'r', encoding='utf-8') as f:
                self._catalog = json.load(f)

            # Important: copie profonde pour ne jamais modifier le JSON d'origine
            self._categories = copy.deepcopy(self._catalog.get("categories", []))
            self._append_offline_categories()
            self._build_software_index()

            logger.info(
                f"Catalogue chargé: {len(self._categories)} catégories, "
                f"{len(self._all_software)} logiciels"
            )
            return True

        except FileNotFoundError:
            logger.error(f"Catalogue non trouvé: {self.catalog_path}")
            return False
        except json.JSONDecodeError as e:
            logger.error(f"Erreur de parsing du catalogue: {e}")
            return False
        except Exception as e:
            logger.exception(f"Erreur lors du chargement du catalogue: {e}")
            return False

    def _append_offline_categories(self):
        """
        Ajoute des catégories offline générées automatiquement depuis:
        offline/<classification>/*.exe|*.msi|*.msix|*.zip

        - Le nom du setup est utilisé comme nom logiciel.
        - Les sous-dossiers de premier niveau servent de classifications.
        """
        if not self.offline_path:
            return

        offline_root = Path(self.offline_path)
        if not offline_root.exists() or not offline_root.is_dir():
            return

        grouped: Dict[str, List[Dict]] = {}

        for file_path in offline_root.rglob("*"):
            if not file_path.is_file() or file_path.suffix.lower() not in self.OFFLINE_EXTENSIONS:
                continue

            rel_path = file_path.relative_to(offline_root)
            
            if len(rel_path.parts) > 1:
                category_name = f"Offline - {rel_path.parts[0]}"
            else:
                category_name = "Offline"
            
            grouped.setdefault(category_name, []).append(
                self._build_offline_software(file_path=file_path, rel_path=rel_path)
            )

        if not grouped:
            return

        for cat_name in sorted(grouped.keys()):
            software_items = sorted(grouped[cat_name], key=lambda s: s.get("name", "").lower())
            self._categories.append({
                "name": cat_name,
                "icon": "📦" if cat_name == "Offline" else "📁",
                "software": software_items,
            })
        logger.info(
            "Offline chargé: %s classification(s), %s setup(s)",
            len(grouped),
            sum(len(v) for v in grouped.values())
        )

    def _build_offline_software(self, file_path: Path, rel_path: Path) -> Dict:
        """Construit une entrée logiciel depuis un setup offline."""
        stem = file_path.stem
        display_name = re.sub(r"[_\-]+", " ", stem).strip() or stem
        slug = re.sub(r"[^a-z0-9]+", "_", rel_path.as_posix().lower()).strip("_")

        installer_type_map = {
            ".msi": "msi",
            ".msix": "msix",
            ".zip": "zip",
            ".exe": "exe",
        }
        installer_type = installer_type_map.get(file_path.suffix.lower(), "exe")

        try:
            size_mb = round(file_path.stat().st_size / (1024 * 1024), 1)
        except OSError:
            size_mb = 0

        return {
            "id": f"offline_{slug}",
            "name": display_name,
            "description": f"Setup offline local ({file_path.suffix.lower().replace('.', '').upper()})",
            "version": "offline",
            "type": "offline",
            "url": "",
            "installer_type": installer_type,
            "silent_args": "",
            "sha256": "",
            "size_mb": size_mb,
            "detect_registry": "",
            "website": "",
            "local_file": rel_path.as_posix(),
        }

    def _build_software_index(self):
        """Construit l'index plat de tous les logiciels"""
        self._all_software = []
        for category in self._categories:
            cat_name = category.get("name", "")
            cat_icon = category.get("icon", "")
            for sw in category.get("software", []):
                sw["_category"] = cat_name
                sw["_category_icon"] = cat_icon
                self._all_software.append(sw)

    @property
    def categories(self) -> List[Dict]:
        """Retourne la liste des catégories"""
        return self._categories

    @property
    def all_software(self) -> List[Dict]:
        """Retourne la liste plate de tous les logiciels"""
        return self._all_software

    @property
    def catalog_version(self) -> str:
        return self._catalog.get("catalog_version", "")

    @property
    def last_updated(self) -> str:
        return self._catalog.get("last_updated", "")

    def get_category_names(self) -> List[str]:
        """Retourne la liste des noms de catégories"""
        return [cat.get("name", "") for cat in self._categories]

    def get_category(self, name: str) -> Optional[Dict]:
        """Retourne une catégorie par son nom"""
        for cat in self._categories:
            if cat.get("name", "") == name:
                return cat
        return None

    def get_software_by_category(self, category_name: str) -> List[Dict]:
        """Retourne les logiciels d'une catégorie"""
        for cat in self._categories:
            if cat.get("name", "") == category_name:
                return cat.get("software", [])
        return []

    def get_software_by_id(self, software_id: str) -> Optional[Dict]:
        """Retourne un logiciel par son ID"""
        for sw in self._all_software:
            if sw.get("id") == software_id:
                return sw
        return None

    def search_software(self, query: str) -> List[Dict]:
        """
        Recherche de logiciels par nom ou description

        Args:
            query: Texte de recherche

        Returns:
            Liste des logiciels correspondants
        """
        if not query or not query.strip():
            return self._all_software

        query_lower = query.lower().strip()
        results = []

        for sw in self._all_software:
            name = sw.get("name", "").lower()
            desc = sw.get("description", "").lower()
            sw_id = sw.get("id", "").lower()
            category = sw.get("_category", "").lower()

            if (query_lower in name or
                query_lower in desc or
                query_lower in sw_id or
                query_lower in category):
                results.append(sw)

        return results

    def get_software_count(self) -> int:
        """Retourne le nombre total de logiciels"""
        return len(self._all_software)

    def get_category_count(self) -> int:
        """Retourne le nombre de catégories"""
        return len(self._categories)

    def get_local_software(self) -> List[Dict]:
        """Retourne les logiciels locaux (installateurs déjà présents)"""
        return self._catalog.get("local_software", [])

    def add_local_software(self, software: Dict) -> bool:
        """
        Ajoute un logiciel local au catalogue

        Args:
            software: Dictionnaire avec les infos du logiciel

        Returns:
            True si ajouté avec succès
        """
        try:
            if "local_software" not in self._catalog:
                self._catalog["local_software"] = []

            self._catalog["local_software"].append(software)
            self._save()
            return True
        except Exception as e:
            logger.error(f"Erreur lors de l'ajout du logiciel local: {e}")
            return False

    def _save(self):
        """Sauvegarde le catalogue"""
        try:
            with open(self.catalog_path, 'w', encoding='utf-8') as f:
                json.dump(self._catalog, f, indent=4, ensure_ascii=False)
            logger.info("Catalogue sauvegardé")
        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde du catalogue: {e}")


class SettingsManager:
    """Gestionnaire des paramètres de l'application"""

    DEFAULT_SETTINGS = {
        "app_name": "DaxterWare",
        "version": "1.0.0",
        "language": "fr",
        "theme": "dark",
        "download_folder": "downloads",
        "installers_folder": "installers",
        "offline_folder": "offline",
        "logs_folder": "logs",
        "max_concurrent_downloads": 3,
        "verify_hash": True,
        "auto_cleanup_downloads": True,
        "show_notifications": True,
        "log_level": "INFO",
        "proxy": {
            "enabled": False,
            "host": "",
            "port": 8080,
            "username": "",
            "password": ""
        },
        "installation": {
            "create_desktop_shortcuts": True,
            "create_start_menu_shortcuts": True,
            "auto_restart_after_install": False
        }
    }

    def __init__(self, settings_path: Path):
        self.settings_path = settings_path
        self._settings: Dict = {}
        self.load()

    def load(self) -> bool:
        """Charge les paramètres depuis le fichier JSON"""
        try:
            with open(self.settings_path, 'r', encoding='utf-8') as f:
                self._settings = json.load(f)
            logger.info("Paramètres chargés avec succès")
            return True
        except FileNotFoundError:
            logger.warning("Fichier de paramètres non trouvé, utilisation des valeurs par défaut")
            self._settings = self.DEFAULT_SETTINGS.copy()
            self.save()
            return True
        except Exception as e:
            logger.error(f"Erreur lors du chargement des paramètres: {e}")
            self._settings = self.DEFAULT_SETTINGS.copy()
            return False

    def save(self) -> bool:
        """Sauvegarde les paramètres"""
        try:
            self.settings_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.settings_path, 'w', encoding='utf-8') as f:
                json.dump(self._settings, f, indent=4, ensure_ascii=False)
            return True
        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde des paramètres: {e}")
            return False

    def get(self, key: str, default=None):
        """Récupère un paramètre"""
        keys = key.split(".")
        value = self._settings
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default
            if value is None:
                return default
        return value

    def set(self, key: str, value):
        """Définit un paramètre"""
        keys = key.split(".")
        target = self._settings
        for k in keys[:-1]:
            if k not in target or not isinstance(target[k], dict):
                target[k] = {}
            target = target[k]
        target[keys[-1]] = value

    @property
    def settings(self) -> Dict:
        return self._settings

    @property
    def app_name(self) -> str:
        return self.get("app_name", "DaxterWare")

    @property
    def version(self) -> str:
        return self.get("version", "1.0.0")

    @property
    def theme(self) -> str:
        return self.get("theme", "dark")

    @property
    def download_folder(self) -> str:
        return self.get("download_folder", "downloads")

    @property
    def max_concurrent_downloads(self) -> int:
        return self.get("max_concurrent_downloads", 3)

    @property
    def log_level(self) -> str:
        return self.get("log_level", "INFO")
