"""
DaxterWare - Gestion des licences et périodes d'essai
- Essai gratuit: 30 jours (automatique)
- Pro: illimité (activation via clé produit)
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict

logger = logging.getLogger(__name__)


class LicenseManager:
    """Gestionnaire local de licence/essai."""

    PRODUCT_KEY_ULTIMATE = "Daxter_Ware08.2026"
    FREE_TRIAL_DAYS = 30
    PRO_TRIAL_DAYS = 30

    def __init__(self, license_file: Path, installation_date: str | None = None):
        self.license_file = Path(license_file)
        self.installation_date = installation_date or date.today().isoformat()
        self._data: Dict = {}
        self._load_or_init()

    def _load_or_init(self):
        self.license_file.parent.mkdir(parents=True, exist_ok=True)

        if self.license_file.exists():
            try:
                with open(self.license_file, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
                self._normalize_data()
                return
            except Exception as e:
                logger.warning(f"Fichier licence invalide, réinitialisation: {e}")

        install_date = self._safe_iso_date(self.installation_date)
        self._data = {
            "created_at": date.today().isoformat(),
            "installation_date": install_date,
            "free_trial_start": install_date,
            "free_trial_days": self.FREE_TRIAL_DAYS,
            "pro_key_activated": False,
            "pro_activated_on": "",
            "pro_activation_count": 0,
        }
        self._save()

    def _normalize_data(self):
        self._data.setdefault("created_at", date.today().isoformat())
        self._data.setdefault("installation_date", self._safe_iso_date(self.installation_date))
        self._data.setdefault("free_trial_start", self._data.get("installation_date", date.today().isoformat()))
        self._data.setdefault("free_trial_days", self.FREE_TRIAL_DAYS)
        # Compatibilité rétroactive: anciennes versions pouvaient stocker un indicateur différent
        legacy_pro_activated = bool(self._data.get("pro_trial_activated", False))
        self._data.setdefault("pro_key_activated", legacy_pro_activated)
        self._data.setdefault("pro_activated_on", "")
        self._data.setdefault("pro_activation_count", 0)

        # Si une activation Pro a déjà eu lieu historiquement, verrouiller en mode Pro illimité
        if int(self._data.get("pro_activation_count", 0)) > 0:
            self._data["pro_key_activated"] = True

        # Toujours ancrer l'essai gratuit au jour d'installation (pas au jour d'activation/licence)
        install_date = self._safe_iso_date(self._data.get("installation_date", self.installation_date))
        current_start = self._safe_iso_date(self._data.get("free_trial_start", install_date))
        if self._parse_iso(current_start) > self._parse_iso(install_date):
            self._data["free_trial_start"] = install_date

        self._save()

    def _save(self):
        with open(self.license_file, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=4, ensure_ascii=False)

    @staticmethod
    def _parse_iso(iso_date: str) -> date:
        return datetime.strptime(iso_date, "%Y-%m-%d").date()

    @staticmethod
    def _safe_iso_date(value: str | None) -> str:
        try:
            if value:
                return datetime.strptime(value, "%Y-%m-%d").date().isoformat()
        except Exception:
            pass
        return date.today().isoformat()

    @staticmethod
    def _days_left(start_date: date, total_days: int) -> int:
        end_date = start_date + timedelta(days=total_days)
        return (end_date - date.today()).days

    def get_status(self) -> Dict:
        """Retourne l'état courant licence/essai."""
        free_total_days = int(self._data.get("free_trial_days", self.FREE_TRIAL_DAYS))
        free_start = self._parse_iso(self._data["free_trial_start"])
        free_end = free_start + timedelta(days=free_total_days)
        free_left = self._days_left(free_start, free_total_days)

        pro_active = bool(self._data.get("pro_key_activated", False))
        if pro_active:
            plan = "pro"
            can_use = True
        elif free_left > 0:
            plan = "free_trial"
            can_use = True
        else:
            plan = "expired"
            can_use = False

        return {
            "plan": plan,
            "can_use": can_use,
            "free_days_left": max(free_left, 0),
            "free_total_days": free_total_days,
            "free_trial_start": free_start.isoformat(),
            "free_trial_end": free_end.isoformat(),
            "pro_days_left": 0,
            "pro_total_days": 0,
            "pro_trial_start": "",
            "pro_trial_end": "",
            "pro_key_activated": pro_active,
            "pro_is_unlimited": pro_active,
            "pro_activated_on": self._data.get("pro_activated_on", ""),
            "installation_date": self._data.get("installation_date", ""),
        }

    def can_use_app(self) -> bool:
        return self.get_status()["can_use"]

    def activate_pro_trial(self, product_key: str) -> tuple[bool, str]:
        """Active le mode Pro illimité avec la clé ultime."""
        entered = (product_key or "").strip()
        if entered != self.PRODUCT_KEY_ULTIMATE:
            return False, "Clé produit invalide."

        if bool(self._data.get("pro_key_activated", False)):
            return False, "Mode Pro déjà activé (illimité)."

        today = date.today().isoformat()
        self._data["pro_key_activated"] = True
        self._data["pro_activated_on"] = today
        self._data["pro_activation_count"] = int(self._data.get("pro_activation_count", 0)) + 1
        self._save()

        return True, "Mode Pro activé en illimité."
