"""
DaxterWare - Interface graphique principale
Application de gestion et d'installation de logiciels avec CustomTkinter
"""

import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox, filedialog, simpledialog
import threading
import logging
import sys
import webbrowser
from pathlib import Path
from typing import Optional, Dict, List, Callable

from core.catalog_manager import CatalogManager, SettingsManager
from core.downloader import DownloadManager, DownloadStatus, DownloadProgress, DownloadResult, LocalInstallerDetector
from core.installer import InstallerManager, InstallStatus, InstallResult
from core.license_manager import LicenseManager

logger = logging.getLogger(__name__)


# ──────────────────────────── Couleurs & Style ────────────────────────────
class Theme:
    """Palette de couleurs pour l'application"""
    current_mode = "blue"

    # Blue Theme vs Black theme represented as (Light_Mode_color, Dark_Mode_color)
    # This allows CustomTkinter to seamlessly switch the theme without a restart!
    # "Light" -> Blue Theme, "Dark" -> Black Theme.
    
    BG_DARK = ("#1a1a2e", "#080808")
    BG_CARD = ("#16213e", "#121212")
    BG_SIDEBAR = ("#0f3460", "#181818")
    ACCENT = ("#e94560", "#e94560")
    ACCENT_HOVER = ("#ff6b81", "#ff6b81")
    TEXT = ("#eaeaea", "#eaeaea")
    TEXT_DIM = ("#a0a0b0", "#a0a0b0")
    TEXT_DARK = ("#6c6c80", "#6c6c80")
    SUCCESS = ("#2ed573", "#2ed573")
    WARNING = ("#ffa502", "#ffa502")
    ERROR = ("#ff4757", "#ff4757")
    BORDER = ("#2a2a4a", "#252525")
    INPUT_BG = ("#1e1e3a", "#1a1a1a")
    PROGRESS_BG = ("#2a2a4a", "#252525")
    BADGE_ONLINE = ("#1f4f91", "#1f4f91")
    BADGE_OFFLINE = ("#2f6f46", "#2f6f46")
    BADGE_LOCAL = ("#7a5b1a", "#7a5b1a")
    
    CATEGORY_COLORS = [
        "#e94560", "#0f3460", "#2ed573", "#ffa502",
        "#5352ed", "#ff6348", "#1e90ff", "#a55eea"
    ]

    @classmethod
    def apply_mode(cls, mode_string):
        cls.current_mode = mode_string
        if mode_string == "black":
            ctk.set_appearance_mode("dark")
        else:
            ctk.set_appearance_mode("light")

    @classmethod
    def toggle(cls):
        pass # Now handled in _toggle_theme using apply_mode


# ──────────────────────────── Widgets personnalisés ────────────────────────
class SoftwareCard(ctk.CTkFrame):
    """Carte représentant un logiciel dans la liste"""

    def __init__(
        self,
        master,
        software: Dict,
        is_installed: bool = False,
        has_local_setup: bool = False,
        on_install: Optional[Callable] = None,
        on_info: Optional[Callable] = None,
        **kwargs
    ):
        super().__init__(
            master,
            fg_color=Theme.BG_CARD,
            corner_radius=10,
            border_width=1,
            border_color=Theme.BORDER,
            **kwargs
        )
        self.software = software
        self.is_installed = is_installed
        self.has_local_setup = has_local_setup
        self._on_install = on_install
        self._on_info = on_info
        self._selected = False
        self._checkbox_var = ctk.BooleanVar(value=False)
        self._compact_mode = False

        self._build()

    def _build(self):
        self.grid_columnconfigure(1, weight=1)

        # Checkbox de sélection
        self.checkbox = ctk.CTkCheckBox(
            self,
            text="",
            variable=self._checkbox_var,
            width=24,
            checkbox_width=20,
            checkbox_height=20,
            fg_color=Theme.ACCENT,
            hover_color=Theme.ACCENT_HOVER,
            border_color=Theme.TEXT_DIM,
        )
        self.checkbox.grid(row=0, column=0, rowspan=2, padx=(12, 6), pady=10)

        # Nom du logiciel
        name_text = self.software.get("name", "Inconnu")
        version = self.software.get("version", "")
        if version and version != "latest":
            name_text += f"  v{version}"

        self.name_label = ctk.CTkLabel(
            self,
            text=name_text,
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=Theme.TEXT,
            anchor="w",
        )
        self.name_label.grid(row=0, column=1, sticky="w", padx=4, pady=(10, 0))

        # Description
        desc = self.software.get("description", "")
        self.desc_label = ctk.CTkLabel(
            self,
            text=desc,
            font=ctk.CTkFont(size=11),
            text_color=Theme.TEXT_DIM,
            anchor="w",
            justify="left",
            wraplength=560,
        )
        self.desc_label.grid(row=1, column=1, sticky="w", padx=4, pady=(0, 10))

        # Taille
        size_mb = self.software.get("size_mb", 0)
        size_text = f"{size_mb} MB" if size_mb else ""
        self.size_label = ctk.CTkLabel(
            self,
            text=size_text,
            font=ctk.CTkFont(size=11),
            text_color=Theme.TEXT_DARK,
            width=60,
        )
        self.size_label.grid(row=0, column=2, rowspan=2, padx=6)

        # Statut installé / local
        if self.is_installed:
            self.status_label = ctk.CTkLabel(
                self,
                text="✓ Installé",
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color=Theme.SUCCESS,
                width=100,
            )
        elif self.has_local_setup:
            self.status_label = ctk.CTkLabel(
                self,
                text="📁 Setup prêt",
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color=Theme.WARNING,
                width=100,
            )
        else:
            self.status_label = ctk.CTkLabel(
                self,
                text="⬇ À télécharger",
                font=ctk.CTkFont(size=11),
                text_color=Theme.TEXT_DARK,
                width=100,
            )
        self.status_label.grid(row=0, column=3, rowspan=2, padx=6)

        # Bouton info/site
        self.info_btn = ctk.CTkButton(
            self,
            text="🌐",
            width=32,
            height=32,
            fg_color=Theme.BG_SIDEBAR,
            hover_color=Theme.ACCENT,
            command=self._open_website,
        )
        self.info_btn.grid(row=0, column=4, rowspan=2, padx=(2, 12))

    def set_compact_mode(self, compact: bool):
        """Ajuste la densité de la carte en mode compact."""
        if compact == self._compact_mode:
            return

        self._compact_mode = compact

        if compact:
            self.size_label.configure(width=48)
            self.status_label.configure(width=86)
            self.info_btn.configure(width=28, height=28)

            text = self.status_label.cget("text")
            if text.startswith("✓"):
                self.status_label.configure(text="✓ OK")
            elif "Setup" in text or "📁" in text:
                self.status_label.configure(text="📁 Local")
            else:
                self.status_label.configure(text="⬇ DL")
        else:
            self.size_label.configure(width=60)
            self.status_label.configure(width=100)
            self.info_btn.configure(width=32, height=32)

            text = self.status_label.cget("text")
            if text == "✓ OK":
                self.status_label.configure(text="✓ Installé")
            elif text == "📁 Local":
                self.status_label.configure(text="📁 Setup prêt")
            elif text == "⬇ DL":
                self.status_label.configure(text="⬇ À télécharger")

    def _open_website(self):
        url = self.software.get("website", "")
        if url:
            webbrowser.open(url)

    @property
    def is_checked(self) -> bool:
        return self._checkbox_var.get()

    @is_checked.setter
    def is_checked(self, value: bool):
        self._checkbox_var.set(value)

    def set_status(self, text: str, color: str):
        """Met à jour le statut affiché"""
        display_text = text
        if self._compact_mode:
            if text.startswith("✓"):
                display_text = "✓ OK"
            elif "Setup" in text or "📁" in text:
                display_text = "📁 Local"
            elif text.startswith("⬇"):
                display_text = "⬇ DL"

        self.status_label.configure(text=display_text, text_color=color)


class ProgressCard(ctk.CTkFrame):
    """Carte de progression pour un téléchargement/installation"""

    def __init__(self, master, software_name: str, **kwargs):
        super().__init__(
            master,
            fg_color=Theme.BG_CARD,
            corner_radius=8,
            border_width=1,
            border_color=Theme.BORDER,
            **kwargs
        )
        self.software_name = software_name
        self._build()

    def _build(self):
        self.grid_columnconfigure(0, weight=1)

        # Nom
        self.name_label = ctk.CTkLabel(
            self,
            text=self.software_name,
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=Theme.TEXT,
            anchor="w",
        )
        self.name_label.grid(row=0, column=0, sticky="w", padx=12, pady=(8, 2))

        # Statut texte
        self.status_label = ctk.CTkLabel(
            self,
            text="En attente...",
            font=ctk.CTkFont(size=11),
            text_color=Theme.TEXT_DIM,
            anchor="w",
        )
        self.status_label.grid(row=1, column=0, sticky="w", padx=12, pady=(0, 2))

        # Barre de progression
        self.progress_bar = ctk.CTkProgressBar(
            self,
            height=6,
            progress_color=Theme.ACCENT,
            fg_color=Theme.PROGRESS_BG,
            corner_radius=3,
        )
        self.progress_bar.grid(row=2, column=0, sticky="ew", padx=12, pady=(2, 4))
        self.progress_bar.set(0)

        # Info vitesse / ETA
        self.info_label = ctk.CTkLabel(
            self,
            text="",
            font=ctk.CTkFont(size=10),
            text_color=Theme.TEXT_DARK,
            anchor="w",
        )
        self.info_label.grid(row=3, column=0, sticky="w", padx=12, pady=(0, 8))

    def update_progress(self, percentage: float, status_text: str, info_text: str = ""):
        """Met à jour la carte de progression"""
        self.progress_bar.set(percentage / 100.0)
        self.status_label.configure(text=status_text)
        if info_text:
            self.info_label.configure(text=info_text)

    def set_complete(self, success: bool, message: str):
        """Marque comme terminé"""
        self.progress_bar.set(1.0 if success else 0.0)
        color = Theme.SUCCESS if success else Theme.ERROR
        self.progress_bar.configure(progress_color=color)
        self.status_label.configure(text=message, text_color=color)
        self.info_label.configure(text="")


# ──────────────────────────── Fenêtre principale ──────────────────────────
class SoftwareManagerApp(ctk.CTk):
    """Fenêtre principale de DaxterWare"""

    WINDOW_MIN_WIDTH = 780
    WINDOW_MIN_HEIGHT = 620
    COMPACT_BREAKPOINT = 1080
    TOOLBAR_COMPACT_BREAKPOINT = 1360
    EXTRA_COMPACT_BREAKPOINT = 1040

    def __init__(
        self,
        catalog: CatalogManager,
        settings: SettingsManager,
        base_path: Path,
        license_manager: LicenseManager,
    ):
        super().__init__()

        self.catalog = catalog
        self.settings = settings
        self.base_path = base_path
        self.license_manager = license_manager

        # Managers
        self.download_manager = DownloadManager(
            download_folder=base_path / settings.download_folder,
            installers_folder=base_path / settings.get("installers_folder", "installers"),
            max_concurrent=settings.max_concurrent_downloads,
            additional_local_folders=[
                base_path / settings.get("offline_folder", "offline")
            ],
        )
        self.installer_manager = InstallerManager(base_path)

        # State
        self._software_cards: List[SoftwareCard] = []
        self._progress_cards: Dict[str, ProgressCard] = {}
        self._current_category: Optional[str] = None
        self._active_tasks = 0
        self._is_processing = False
        self._current_download_id: Optional[str] = None
        self._download_paused = False
        self._responsive_mode: Optional[str] = None
        self._toolbar_responsive_mode: Optional[str] = None
        self._resize_after_id: Optional[str] = None
        self._last_layout_width: Optional[int] = None
        self._progress_reset_after_id: Optional[str] = None
        self._active_scroll_target: str = "software"

        self._configure_window()
        self._build_ui()
        self._bind_responsive_events()
        self._bind_software_scroll_events()
        self._refresh_license_ui()
        self.after(50, lambda: self._apply_responsive_layout(force=True))
        self._show_category(None)  # Afficher tous les logiciels

    # ─────────────── Configuration fenêtre ───────────────
    def _configure_window(self):
        self.title(f"{self.settings.app_name} v{self.settings.version}")
        self.geometry("1200x780")
        self.minsize(self.WINDOW_MIN_WIDTH, self.WINDOW_MIN_HEIGHT)

        # Thème
        saved_theme = self.settings.get("theme_palette", "blue")
        Theme.apply_mode(saved_theme)
        ctk.set_default_color_theme("blue")

        self.configure(fg_color=Theme.BG_DARK)

        # Centrer la fenêtre
        self.update_idletasks()
        x = (self.winfo_screenwidth() - 1200) // 2
        y = (self.winfo_screenheight() - 780) // 2
        self.geometry(f"+{x}+{y}")

        # Icône (si disponible)
        icon_path = self.base_path / "assets" / "icon.ico"
        if icon_path.exists():
            self.iconbitmap(str(icon_path))

    # ─────────────── Construction UI ───────────────
    def _build_ui(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._build_sidebar()
        self._build_main_area()

    def _toggle_theme(self):
        current = self.settings.get("theme_palette", "blue")
        new_theme = "black" if current == "blue" else "blue"
        self.settings.set("theme_palette", new_theme)
        self.settings.save()
        Theme.apply_mode(new_theme)

    def _bind_responsive_events(self):
        """Active l'adaptation responsive en fonction de la largeur de fenêtre."""
        self.bind("<Configure>", self._on_window_resize)

    def _on_window_resize(self, event):
        if event.widget is not self:
            return

        if self._resize_after_id:
            try:
                self.after_cancel(self._resize_after_id)
            except Exception:
                pass

        self._resize_after_id = self.after(90, self._apply_responsive_layout)

    def _bind_software_scroll_events(self):
        """Fiabilise le scroll molette de la liste logiciels sans interférer avec les autres scrolls."""
        self.bind_all("<MouseWheel>", self._on_any_mousewheel, add="+")
        self.bind_all("<Button-4>", self._on_any_mousewheel, add="+")
        self.bind_all("<Button-5>", self._on_any_mousewheel, add="+")

        self.software_scroll.bind("<Enter>", lambda _e: self._set_active_scroll_target("software"), add="+")
        self.progress_scroll.bind("<Enter>", lambda _e: self._set_active_scroll_target("progress"), add="+")
        self.category_scroll.bind("<Enter>", lambda _e: self._set_active_scroll_target("category"), add="+")

        self._bind_scroll_frame_wheel(self.software_scroll, self._on_software_mousewheel)
        self._bind_scroll_frame_wheel(self.progress_scroll, self._on_progress_mousewheel)
        self._bind_scroll_frame_wheel(self.category_scroll, self._on_category_mousewheel)

    def _bind_scroll_frame_wheel(self, frame, callback):
        canvas = getattr(frame, "_parent_canvas", None)
        if canvas is None:
            return
        canvas.bind("<MouseWheel>", callback, add="+")
        canvas.bind("<Button-4>", callback, add="+")
        canvas.bind("<Button-5>", callback, add="+")

    def _scroll_frame_by_wheel(self, frame, delta: int):
        canvas = getattr(frame, "_parent_canvas", None)
        if canvas is None:
            return
        if sys.platform.startswith("win"):
            steps = -int(delta / 6)
        else:
            steps = -int(delta)

        if steps == 0:
            steps = -1 if delta > 0 else 1

        canvas.yview_scroll(steps, "units")

    @staticmethod
    def _normalize_wheel_delta(event) -> int:
        delta = getattr(event, "delta", 0)
        if delta == 0:
            num = getattr(event, "num", None)
            if num == 4:
                delta = 120
            elif num == 5:
                delta = -120
        return delta

    def _on_software_mousewheel(self, event):
        self._set_active_scroll_target("software")
        delta = self._normalize_wheel_delta(event)
        if delta == 0:
            return
        self._scroll_frame_by_wheel(self.software_scroll, delta)
        return "break"

    def _on_progress_mousewheel(self, event):
        self._set_active_scroll_target("progress")
        delta = self._normalize_wheel_delta(event)
        if delta == 0:
            return
        self._scroll_frame_by_wheel(self.progress_scroll, delta)
        return "break"

    def _on_category_mousewheel(self, event):
        self._set_active_scroll_target("category")
        delta = self._normalize_wheel_delta(event)
        if delta == 0:
            return
        self._scroll_frame_by_wheel(self.category_scroll, delta)
        return "break"

    def _set_active_scroll_target(self, target: str):
        self._active_scroll_target = target

    def _on_any_mousewheel(self, event):
        delta = self._normalize_wheel_delta(event)
        if delta == 0:
            return

        target = self._active_scroll_target
        if target == "progress":
            self._scroll_frame_by_wheel(self.progress_scroll, delta)
        elif target == "category":
            self._scroll_frame_by_wheel(self.category_scroll, delta)
        else:
            self._scroll_frame_by_wheel(self.software_scroll, delta)
        return "break"

    def _apply_responsive_layout(self, force: bool = False):
        """Ajuste l'interface pour les écrans étroits/larges."""
        width = self.winfo_width()
        mode = "compact" if width < self.COMPACT_BREAKPOINT else "wide"
        toolbar_mode = "compact" if width < self.TOOLBAR_COMPACT_BREAKPOINT else "wide"

        if (
            not force
            and mode == self._responsive_mode
            and toolbar_mode == self._toolbar_responsive_mode
            and self._last_layout_width is not None
            and abs(width - self._last_layout_width) < 12
        ):
            return

        self._responsive_mode = mode
        self._toolbar_responsive_mode = toolbar_mode
        self._last_layout_width = width

        scale = max(0.52, min(1.0, width / 1440.0))
        side_pad = max(8, int(12 * scale))
        split_pad = max(4, int(6 * scale))
        block_pad = max(6, int(12 * scale))

        # Disposition stable : progression toujours visible à droite
        self.software_scroll.grid_configure(row=1, column=0, padx=(side_pad, split_pad), pady=block_pad, sticky="nsew", columnspan=1)
        self.progress_panel.grid_configure(row=1, column=1, padx=(split_pad, side_pad), pady=block_pad, sticky="nsew", columnspan=1)
        self.toolbar_actions.grid_configure(row=0, column=1, columnspan=1, sticky="ew", padx=side_pad, pady=(block_pad, 0))

        self.content_frame.grid_rowconfigure(0, weight=0)
        self.content_frame.grid_rowconfigure(1, weight=1)
        self.content_frame.grid_rowconfigure(2, weight=0)
        self.content_frame.grid_rowconfigure(3, weight=0)

        if mode == "compact":
            self.sidebar.configure(width=240)

            if hasattr(self, "license_label"):
                self.license_label.configure(wraplength=198)
            if hasattr(self, "license_period_label"):
                self.license_period_label.configure(wraplength=198)

            self.content_frame.grid_columnconfigure(0, weight=4)
            self.content_frame.grid_columnconfigure(1, weight=2)
        else:
            self.sidebar.configure(width=240)

            if hasattr(self, "license_label"):
                self.license_label.configure(wraplength=198)
            if hasattr(self, "license_period_label"):
                self.license_period_label.configure(wraplength=198)

            self.content_frame.grid_columnconfigure(0, weight=3)
            self.content_frame.grid_columnconfigure(1, weight=1)

        inner_width = max(460, width - self.sidebar.cget("width"))
        pause_visible = self._is_processing

        # Quand pause est visible, on pousse la colonne de droite pour garder
        # les 3 boutons sur UNE seule ligne sans retour.
        progress_ratio = 0.40 if pause_visible else 0.30
        progress_min = 300 if pause_visible else 170
        progress_max = 460 if pause_visible else 340
        progress_width = max(progress_min, min(progress_max, int(inner_width * progress_ratio)))
        left_width = max(240, inner_width - progress_width - (side_pad * 2 + split_pad * 2))

        self.content_frame.grid_columnconfigure(0, minsize=left_width)
        self.content_frame.grid_columnconfigure(1, minsize=progress_width)

        self.category_title.configure(font=ctk.CTkFont(size=max(14, int(18 * scale)), weight="bold"))
        self.count_label.configure(font=ctk.CTkFont(size=max(10, int(12 * scale))))

        # Toolbar responsive : adapter texte/largeur sans casser la grille
        toolbar_scale = max(0.62, min(1.0, width / 1440.0))
        toolbar_available = max(240, progress_width - (side_pad * 2))
        pause_text = "▶️ Reprendre DL" if self._download_paused else "⏸️  Pause DL"
        self._set_pause_button_visibility(pause_visible)

        if pause_visible:
            # 3 boutons sur la même ligne: répartitions proportionnelles
            small_w = max(80, int(toolbar_available * 0.24))
            install_w = max(176, int(toolbar_available * 0.44))
            pause_w = max(120, int(toolbar_available * 0.28))
        else:
            small_w = max(84, int(toolbar_available * 0.34))
            install_w = max(128, int(toolbar_available * 0.62))
            pause_w = max(88, int(toolbar_available * 0.24))

        small_h = max(26, int(32 * toolbar_scale))
        main_h = max(28, int(36 * toolbar_scale))

        if toolbar_mode == "compact":
            self.select_all_btn.configure(width=max(74, int(small_w * 0.9)), height=small_h, text="☑ Tout")
            self.install_btn.configure(width=max(152, int(install_w * 0.9)), height=main_h, text="⬇️ Installer")
            self.select_all_btn.grid_configure(row=0, column=0, sticky="e")
            self.install_btn.grid_configure(row=0, column=1, sticky="ew")

            if pause_visible:
                self.pause_btn.configure(width=max(108, int(pause_w * 0.9)), height=main_h, text="▶️ Reprendre")
                self.pause_btn.grid_configure(row=0, column=2, columnspan=1, sticky="e", padx=(0, 0), pady=0)
        else:
            self.select_all_btn.configure(width=small_w, height=small_h, text="☑ Tout sélectionner")
            self.install_btn.configure(width=max(176, install_w), height=main_h, text="⬇️  Installer la sélection")
            self.select_all_btn.grid_configure(row=0, column=0, sticky="e")
            self.install_btn.grid_configure(row=0, column=1, sticky="ew")

            if pause_visible:
                self.pause_btn.configure(width=max(120, pause_w), height=main_h, text=pause_text)
                self.pause_btn.grid_configure(row=0, column=2, columnspan=1, sticky="e", padx=(0, 0), pady=0)

        # Adapter la densité d'affichage des descriptions selon largeur
        self._refresh_cards_layout(mode, width)

    def _refresh_cards_layout(self, mode: str, width: int):
        """Ajuste les cartes en mode compact / large."""
        scale = max(0.64, min(1.0, width / 1440.0))
        left_col_width = self.software_scroll.winfo_width() or int(width * 0.55)
        wrap = max(170, min(620, int(left_col_width * 0.60)))

        is_extra_compact = width < self.EXTRA_COMPACT_BREAKPOINT
        title_size = max(11, int((13 if is_extra_compact else 14) * scale))
        desc_size = max(9, int((10 if is_extra_compact else 11) * scale))
        size_width = max(42, int(60 * scale))
        status_width = max(74, int(100 * scale))
        info_wh = max(24, int(32 * scale))
        checkbox_wh = max(14, int(20 * scale))

        for card in self._software_cards:
            try:
                card.desc_label.configure(wraplength=wrap)
                card.name_label.configure(font=ctk.CTkFont(size=title_size, weight="bold"))
                card.desc_label.configure(font=ctk.CTkFont(size=desc_size))
                card.size_label.configure(width=size_width)
                card.status_label.configure(width=status_width)
                card.info_btn.configure(width=info_wh, height=info_wh)
                card.checkbox.configure(
                    width=max(16, int(24 * scale)),
                    checkbox_width=checkbox_wh,
                    checkbox_height=checkbox_wh,
                )
                card.set_compact_mode(is_extra_compact)
            except Exception:
                continue

    def _build_sidebar(self):
        """Barre latérale avec catégories"""
        self.sidebar = ctk.CTkFrame(
            self,
            width=240,
            fg_color=Theme.BG_SIDEBAR,
            corner_radius=0,
        )
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)
        self.sidebar.grid_columnconfigure(0, weight=1)
        self.sidebar.grid_rowconfigure(4, weight=1)

        # Logo / Titre
        title_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        title_frame.grid(row=0, column=0, sticky="ew", padx=16, pady=(20, 6))

        ctk.CTkLabel(
            title_frame,
            text="📦 Daxter",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=Theme.TEXT,
        ).pack(anchor="w")

        ctk.CTkLabel(
            title_frame,
            text="   Ware",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=Theme.ACCENT,
        ).pack(anchor="w")

        ctk.CTkLabel(
            self.sidebar,
            text=f"v{self.settings.version}",
            font=ctk.CTkFont(size=10),
            text_color=Theme.TEXT_DARK,
        ).grid(row=1, column=0, sticky="w", padx=20, pady=(0, 20))

        self.theme_btn = ctk.CTkButton(
            self.sidebar,
            text="🎨 Thème",
            font=ctk.CTkFont(size=11),
            fg_color="transparent",
            border_width=1,
            border_color=Theme.BORDER,
            text_color=Theme.TEXT_DIM,
            height=24,
            width=70,
            command=self._toggle_theme,
        )
        self.theme_btn.grid(row=1, column=0, sticky="e", padx=16, pady=(0, 20))

        # Barre de recherche
        self.search_var = ctk.StringVar()
        self.search_var.trace_add("write", self._on_search_changed)

        self.search_entry = ctk.CTkEntry(
            self.sidebar,
            placeholder_text="🔍  Rechercher...",
            textvariable=self.search_var,
            fg_color=Theme.INPUT_BG,
            border_color=Theme.BORDER,
            text_color=Theme.TEXT,
            height=36,
        )
        self.search_entry.grid(row=2, column=0, sticky="ew", padx=16, pady=(0, 16))

        # Séparateur
        ctk.CTkFrame(
            self.sidebar, height=1, fg_color=Theme.BORDER
        ).grid(row=3, column=0, sticky="ew", padx=16, pady=(0, 10))

        # Liste catégories (scrollable pour éviter le contenu tronqué)
        self.category_scroll = ctk.CTkScrollableFrame(
            self.sidebar,
            fg_color="transparent",
            scrollbar_button_color=Theme.BG_CARD,
            scrollbar_button_hover_color=Theme.ACCENT,
        )
        self.category_scroll.grid(row=4, column=0, sticky="nsew", padx=10, pady=(0, 8))

        # Bouton "Tous les logiciels"
        self.all_btn = ctk.CTkButton(
            self.category_scroll,
            text=f"📋  Tous les logiciels  ({self.catalog.get_software_count()})",
            font=ctk.CTkFont(size=13),
            fg_color=Theme.ACCENT,
            hover_color=Theme.ACCENT_HOVER,
            height=38,
            anchor="w",
            command=lambda: self._show_category(None),
        )
        self.all_btn.pack(fill="x", padx=6, pady=(2, 4))

        # Boutons de catégories
        self._category_buttons: Dict[str, ctk.CTkButton] = {}
        for i, cat in enumerate(self.catalog.categories):
            cat_name = cat.get("name", "")
            cat_icon = cat.get("icon", "")
            sw_count = len(cat.get("software", []))

            btn = ctk.CTkButton(
                self.category_scroll,
                text=f"{cat_icon}  {cat_name}  ({sw_count})",
                font=ctk.CTkFont(size=13),
                fg_color="transparent",
                hover_color=Theme.BG_CARD,
                text_color=Theme.TEXT_DIM,
                height=36,
                anchor="w",
                command=lambda n=cat_name: self._show_category(n),
            )
            btn.pack(fill="x", padx=6, pady=2)
            self._category_buttons[cat_name] = btn

        # ─── Zone basse de la sidebar ───
        bottom_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        bottom_frame.grid(row=5, column=0, sticky="sew", padx=16, pady=(6, 16))

        # Info admin
        is_admin = InstallerManager.is_admin()
        admin_text = "🛡️ Administrateur" if is_admin else "⚠️ Mode utilisateur"
        admin_color = Theme.SUCCESS if is_admin else Theme.WARNING

        ctk.CTkLabel(
            bottom_frame,
            text=admin_text,
            font=ctk.CTkFont(size=11),
            text_color=admin_color,
        ).pack(anchor="w", pady=(0, 4))

        ctk.CTkLabel(
            bottom_frame,
            text=f"Catalogue: {self.catalog.last_updated}",
            font=ctk.CTkFont(size=10),
            text_color=Theme.TEXT_DARK,
        ).pack(anchor="w")

        # Statut licence / essai
        self.license_card = ctk.CTkFrame(
            bottom_frame,
            fg_color=Theme.INPUT_BG,
            corner_radius=10,
            border_width=1,
            border_color=Theme.BORDER,
        )
        self.license_card.pack(fill="x", pady=(8, 0))
        self.license_card.grid_columnconfigure(0, weight=1)

        self.license_title = ctk.CTkLabel(
            self.license_card,
            text="🔐 Licence & Essai",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=Theme.TEXT,
            anchor="w",
        )
        self.license_title.grid(row=0, column=0, sticky="ew", padx=10, pady=(8, 0))

        self.license_plan_badge = ctk.CTkLabel(
            self.license_card,
            text="",
            font=ctk.CTkFont(size=10, weight="bold"),
            corner_radius=8,
            fg_color=Theme.BG_SIDEBAR,
            text_color=Theme.TEXT,
            padx=8,
            pady=2,
        )
        self.license_plan_badge.grid(row=1, column=0, sticky="w", padx=10, pady=(6, 0))

        self.license_label = ctk.CTkLabel(
            self.license_card,
            text="",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=Theme.WARNING,
            anchor="w",
            justify="left",
            wraplength=200,
        )
        self.license_label.grid(row=2, column=0, sticky="ew", padx=10, pady=(6, 0))

        self.license_period_label = ctk.CTkLabel(
            self.license_card,
            text="",
            font=ctk.CTkFont(size=10),
            text_color=Theme.TEXT_DIM,
            anchor="w",
            justify="left",
            wraplength=200,
        )
        self.license_period_label.grid(row=3, column=0, sticky="ew", padx=10, pady=(2, 0))

        self.license_progress = ctk.CTkProgressBar(
            self.license_card,
            height=6,
            progress_color=Theme.ACCENT,
            fg_color=Theme.PROGRESS_BG,
            corner_radius=4,
        )
        self.license_progress.grid(row=4, column=0, sticky="ew", padx=10, pady=(8, 0))
        self.license_progress.set(0)

        self.activate_pro_btn = ctk.CTkButton(
            self.license_card,
            text="🔑 Activer Pro illimité",
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color=Theme.ACCENT,
            hover_color=Theme.ACCENT_HOVER,
            height=30,
            command=self._activate_pro_trial_prompt,
        )
        self.activate_pro_btn.grid(row=5, column=0, sticky="ew", padx=10, pady=(8, 10))

        # Info setups locaux
        local_count = self.download_manager.get_local_count()
        if local_count > 0:
            ctk.CTkLabel(
                bottom_frame,
                text=f"📁 {local_count} setup(s) local(aux)",
                font=ctk.CTkFont(size=10),
                text_color=Theme.SUCCESS,
            ).pack(anchor="w", pady=(2, 0))

    def _refresh_license_ui(self):
        """Met à jour l'état licence/essai dans la sidebar."""
        status = self.license_manager.get_status()
        plan = status.get("plan")

        def _set_progress(days_left: int, total_days: int):
            if total_days <= 0:
                self.license_progress.set(0)
                return
            used = max(0, min(total_days, total_days - days_left))
            self.license_progress.set(used / total_days)

        if plan == "pro":
            self.license_plan_badge.configure(text="PRO ACTIVÉ", fg_color="#3b2f8f", text_color=Theme.TEXT)
            self.license_label.configure(
                text="💎 Mode Pro illimité actif",
                text_color=Theme.SUCCESS,
            )
            self.license_period_label.configure(
                text=f"Activation: {status.get('pro_activated_on', '') or '—'}"
            )
            self.license_progress.set(1.0)
            self.activate_pro_btn.configure(state="disabled", text="🔓 Pro illimité")
        elif plan == "free_trial":
            days_left = status.get('free_days_left', 0)
            total_days = status.get('free_total_days', 30)
            self.license_plan_badge.configure(text="FREE TRIAL", fg_color=Theme.BG_SIDEBAR, text_color=Theme.TEXT)
            self.license_label.configure(
                text=f"🆓 Essai gratuit — {days_left} jour(s) restant(s)",
                text_color=Theme.WARNING,
            )
            self.license_period_label.configure(
                text=f"Installation: {status.get('installation_date', '')}"
            )
            _set_progress(days_left, total_days)
            self.activate_pro_btn.configure(state="normal", text="🔑 Activer Pro illimité")
        else:
            self.license_plan_badge.configure(text="EXPIRED", fg_color="#5c1f2d", text_color=Theme.TEXT)
            self.license_label.configure(
                text="⛔ Essai expiré",
                text_color=Theme.ERROR,
            )
            self.license_period_label.configure(
                text=f"Fin essai gratuit: {status.get('free_trial_end', '')}"
            )
            self.license_progress.set(1.0)
            self.activate_pro_btn.configure(state="normal", text="🔑 Activer Pro illimité")

        if hasattr(self, "install_btn"):
            can_use = status.get("can_use", False)
            self.install_btn.configure(state="normal" if can_use else "disabled")

    def _activate_pro_trial_prompt(self):
        """Demande la clé produit et active l'essai Pro."""
        key = simpledialog.askstring(
            "Clé produit",
            "Entrez votre clé produit pour activer le mode Pro (illimité) :",
            parent=self,
        )
        if key is None:
            return

        ok, message = self.license_manager.activate_pro_trial(key)
        if ok:
            messagebox.showinfo("Activation réussie", message)
        else:
            messagebox.showwarning("Activation", message)

        self._refresh_license_ui()

    def _build_main_area(self):
        """Zone principale avec la liste des logiciels"""
        main_frame = ctk.CTkFrame(self, fg_color="transparent")
        main_frame.grid(row=0, column=1, sticky="nsew", padx=0, pady=0)
        main_frame.grid_columnconfigure(0, weight=1)
        main_frame.grid_rowconfigure(0, weight=1)

        self.content_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        self.content_frame.grid(row=0, column=0, sticky="nsew")
        self.content_frame.grid_columnconfigure(0, weight=3)  # Left column
        self.content_frame.grid_columnconfigure(1, weight=1)  # Right column
        self.content_frame.grid_rowconfigure(0, weight=0) # Headers
        self.content_frame.grid_rowconfigure(1, weight=1) # Content
        self.content_frame.grid_rowconfigure(2, weight=0) 
        self.content_frame.grid_rowconfigure(3, weight=0)

        # --- LEFT SIDE HEADER ---
        left_header = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        left_header.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 0))
        
        self.category_title = ctk.CTkLabel(
            left_header,
            text="Tous les logiciels",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=Theme.TEXT,
        )
        self.category_title.pack(side="left", padx=(8, 12))

        self.count_label = ctk.CTkLabel(
            left_header,
            text="",
            font=ctk.CTkFont(size=12),
            text_color=Theme.TEXT_DIM,
        )
        self.count_label.pack(side="left")

        # --- RIGHT SIDE HEADER (Buttons) ---
        self.toolbar_actions = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        self.toolbar_actions.grid(row=0, column=1, sticky="ew", padx=12, pady=(12, 0))
        self.toolbar_actions.grid_columnconfigure(0, weight=0)
        self.toolbar_actions.grid_columnconfigure(1, weight=1)
        self.toolbar_actions.grid_columnconfigure(2, weight=0)

        self.select_all_btn = ctk.CTkButton(
            self.toolbar_actions,
            text="☑ Tout sélectionner",
            font=ctk.CTkFont(size=12),
            fg_color="transparent",
            hover_color=Theme.BG_SIDEBAR,
            text_color=Theme.TEXT_DIM,
            width=130,
            height=32,
            command=self._toggle_select_all,
        )
        self.select_all_btn.grid(row=0, column=0, padx=(0, 6), pady=0, sticky="e")

        self.install_btn = ctk.CTkButton(
            self.toolbar_actions,
            text="⬇️  Installer la sélection",
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=Theme.ACCENT,
            hover_color=Theme.ACCENT_HOVER,
            width=200,
            height=36,
            command=self._start_install_selected,
        )
        self.install_btn.grid(row=0, column=1, padx=(0, 6), pady=0, sticky="ew")

        self.pause_btn = ctk.CTkButton(
            self.toolbar_actions,
            text="⏸️  Pause DL",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=Theme.BG_SIDEBAR,
            hover_color=Theme.ACCENT,
            width=130,
            height=36,
            state="disabled",
            command=self._toggle_download_pause,
        )
        self.pause_btn.grid(row=0, column=2, padx=(0, 0), pady=0, sticky="e")
        self.pause_btn.grid_remove()

        # --- LEFT SIDE CONTENT (List) ---
        self.software_scroll = ctk.CTkScrollableFrame(
            self.content_frame,
            fg_color="transparent",
            scrollbar_button_color=Theme.BG_SIDEBAR,
            scrollbar_button_hover_color=Theme.ACCENT,
        )
        self.software_scroll.grid(row=1, column=0, sticky="nsew", padx=(12, 6), pady=(8, 12))

        # --- RIGHT SIDE CONTENT (Progression) ---
        self._build_progress_panel()

    def _build_progress_panel(self):
        """Panneau latéral pour la progression"""
        self.progress_panel = ctk.CTkFrame(
            self.content_frame,
            fg_color=Theme.BG_CARD,
            corner_radius=10,
            border_width=1,
            border_color=Theme.BORDER,
        )
        self.progress_panel.grid(row=1, column=1, sticky="nsew", padx=(6, 12), pady=(8, 12))
        self.progress_panel.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            self.progress_panel,
            text="📊  Progression",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=Theme.TEXT,
        ).grid(row=0, column=0, sticky="w", padx=16, pady=(16, 4))

        ctk.CTkFrame(
            self.progress_panel, height=1, fg_color=Theme.BORDER
        ).grid(row=1, column=0, sticky="ew", padx=12, pady=8)

        # Scroll pour les cartes de progression
        self.progress_scroll = ctk.CTkScrollableFrame(
            self.progress_panel,
            fg_color="transparent",
            scrollbar_button_color=Theme.BG_SIDEBAR,
        )
        self.progress_scroll.grid(row=2, column=0, sticky="nsew", padx=8, pady=(0, 8))
        self.progress_panel.grid_rowconfigure(2, weight=1)

        # Message par défaut
        self.progress_placeholder = ctk.CTkLabel(
            self.progress_scroll,
            text="Sélectionnez des logiciels\npuis cliquez sur Installer",
            font=ctk.CTkFont(size=12),
            text_color=Theme.TEXT_DARK,
            justify="center",
        )
        self.progress_placeholder.pack(pady=40)

        # ─── Stats en bas du panel ───
        stats_frame = ctk.CTkFrame(self.progress_panel, fg_color="transparent")
        stats_frame.grid(row=3, column=0, sticky="ew", padx=16, pady=(4, 12))

        self.stats_label = ctk.CTkLabel(
            stats_frame,
            text="",
            font=ctk.CTkFont(size=11),
            text_color=Theme.TEXT_DIM,
        )
        self.stats_label.pack(anchor="w")

    # ─────────────── Navigation catégories ───────────────
    def _show_category(self, category_name: Optional[str]):
        """Affiche les logiciels d'une catégorie"""
        self._current_category = category_name

        # Mettre à jour le style des boutons
        self.all_btn.configure(
            fg_color=Theme.ACCENT if category_name is None else "transparent",
            text_color=Theme.TEXT if category_name is None else Theme.TEXT_DIM,
        )

        for name, btn in self._category_buttons.items():
            is_active = name == category_name
            btn.configure(
                fg_color=Theme.ACCENT if is_active else "transparent",
                text_color=Theme.TEXT if is_active else Theme.TEXT_DIM,
            )

        # Titre
        if category_name:
            cat = self.catalog.get_category(category_name)
            icon = cat.get("icon", "") if cat else ""
            self.category_title.configure(text=f"{icon}  {category_name}")
        else:
            self.category_title.configure(text="📋  Tous les logiciels")

        # Charger les logiciels
        self._load_software_list(category_name)

    def _load_software_list(self, category_name: Optional[str]):
        """Charge et affiche la liste des logiciels"""
        # Nettoyer
        for card in self._software_cards:
            card.destroy()
        self._software_cards.clear()

        # Récupérer les logiciels
        if category_name:
            software_list = self.catalog.get_software_by_category(category_name)
        else:
            software_list = self.catalog.all_software

        # Filtre de recherche
        search_query = self.search_var.get().strip()
        if search_query:
            query_lower = search_query.lower()
            software_list = [
                sw for sw in software_list
                if query_lower in sw.get("name", "").lower()
                or query_lower in sw.get("description", "").lower()
                or query_lower in sw.get("id", "").lower()
            ]

        # Compteur
        self.count_label.configure(text=f"{len(software_list)} logiciel(s)")

        # Créer les cartes
        for i, sw in enumerate(software_list):
            is_installed = self.installer_manager.check_software_installed(sw)
            has_local = self.download_manager.local_detector.find_installer(sw) is not None

            card = SoftwareCard(
                self.software_scroll,
                software=sw,
                is_installed=is_installed,
                has_local_setup=has_local,
            )
            card.pack(fill="x", pady=3, padx=2)
            self._bind_widget_to_software_scroll(card)
            self._software_cards.append(card)

        # Réappliquer le responsive sur les cartes nouvellement rendues
        current_width = self.winfo_width() or self.WINDOW_MIN_WIDTH
        mode = "compact" if current_width < self.COMPACT_BREAKPOINT else "wide"
        self._refresh_cards_layout(mode, current_width)

    def _on_search_changed(self, *args):
        """Appelé quand le texte de recherche change"""
        self._load_software_list(self._current_category)

    # ─────────────── Sélection ───────────────
    def _toggle_select_all(self):
        """Sélectionner / Désélectionner tout"""
        any_checked = any(card.is_checked for card in self._software_cards)
        new_value = not any_checked

        for card in self._software_cards:
            card.is_checked = new_value

        text = "☐ Tout désélectionner" if new_value else "☑ Tout sélectionner"
        self.select_all_btn.configure(text=text)

    def _get_selected_software(self) -> List[Dict]:
        """Retourne la liste des logiciels sélectionnés"""
        return [
            card.software
            for card in self._software_cards
            if card.is_checked
        ]

    # ─────────────── Installation ───────────────
    def _start_install_selected(self):
        """Démarre le téléchargement et l'installation des logiciels sélectionnés"""
        if not self.license_manager.can_use_app():
            messagebox.showerror(
                "Essai expiré",
                "Votre période d'essai gratuit est expirée.\n"
                "Activez le mode Pro illimité avec une clé produit pour continuer."
            )
            return

        selected = self._get_selected_software()

        if not selected:
            messagebox.showinfo(
                "Aucune sélection",
                "Veuillez sélectionner au moins un logiciel à installer."
            )
            return

        # Vérifier les droits admin uniquement pour les logiciels qui l'exigent
        needs_admin = any(bool(sw.get("requires_admin", True)) for sw in selected)
        if needs_admin and not InstallerManager.is_admin():
            result = messagebox.askyesno(
                "Droits administrateur",
                "Certains logiciels sélectionnés nécessitent des droits administrateur.\n"
                "Voulez-vous relancer en mode administrateur ?",
            )
            if result:
                InstallerManager.request_admin_elevation()
            return

        # Confirmation
        names = "\n".join(f"  • {sw.get('name', '')}" for sw in selected)
        confirm = messagebox.askyesno(
            "Confirmer l'installation",
            f"Installer {len(selected)} logiciel(s) ?\n\n{names}",
        )
        if not confirm:
            return

        self._active_tasks += 1
        self._is_processing = True
        self._download_paused = False
        self._current_download_id = None

        if self._progress_reset_after_id:
            try:
                self.after_cancel(self._progress_reset_after_id)
            except Exception:
                pass
            self._progress_reset_after_id = None

        # self.install_btn.configure(state="disabled", text="⏳  Installation en cours...")
        self.pause_btn.configure(state="normal", text="⏸️  Pause DL")
        self._set_pause_button_visibility(True)

        # Réinitialiser l'ancien état pour éviter les erreurs persistantes
        self._clear_progress_panel()
        self.progress_placeholder.pack_forget()

        for sw in selected:
            name = sw.get("name", "Inconnu")
            sw_id = sw.get("id", "unknown")
            card = ProgressCard(self.progress_scroll, software_name=name)
            card.pack(fill="x", pady=4, padx=4)
            self._progress_cards[sw_id] = card

        # Lancer dans un thread
        thread = threading.Thread(
            target=self._process_installations,
            args=(selected,),
            daemon=True,
        )
        thread.start()

    def _process_installations(self, software_list: List[Dict]):
        """Traite les installations en arrière-plan"""
        total = len(software_list)
        success_count = 0
        fail_count = 0

        for idx, sw in enumerate(software_list):
            sw_id = sw.get("id", "unknown")
            sw_name = sw.get("name", "Inconnu")
            self._current_download_id = sw_id
            self._download_paused = False
            self.after(0, lambda: self.pause_btn.configure(text="⏸️  Pause DL"))

            progress_card = self._progress_cards.get(sw_id)

            try:
                # ─ Étape 1 : Obtenir l'installateur (local ou téléchargement) ─
                self._update_progress_card(
                    sw_id, 0.0,
                    f"Recherche du setup de {sw_name}...",
                    f"Étape {idx + 1}/{total}"
                )

                def on_progress(progress: DownloadProgress, sid=sw_id, sname=sw_name):
                    from core.downloader import DownloadManager
                    pct = progress.percentage

                    if progress.status == DownloadStatus.LOCAL_FOUND:
                        self._update_progress_card(
                            sid, 70.0,
                            f"📁 Setup local trouvé !",
                            "Installation directe..."
                        )
                    elif progress.status == DownloadStatus.PAUSED:
                        self._update_progress_card(
                            sid, pct * 0.7,
                            "⏸ Téléchargement en pause",
                            "Cliquez sur Reprendre DL pour continuer"
                        )
                    else:
                        speed_str = DownloadManager.format_speed(progress.speed)
                        eta_str = DownloadManager.format_eta(progress.eta)
                        self._update_progress_card(
                            sid, pct * 0.7,
                            f"⬇ Téléchargement... {pct:.0f}%",
                            f"{speed_str} — ETA: {eta_str}"
                        )

                dl_result: DownloadResult = self.download_manager.download_file(
                    sw,
                    progress_callback=on_progress,
                )

                if dl_result.status != DownloadStatus.COMPLETED:
                    self._set_progress_complete(sw_id, False, f"Échec DL: {dl_result.message}")
                    fail_count += 1
                    self._current_download_id = None
                    continue

                # ─ Étape 2 : Installation ─
                self._update_progress_card(
                    sw_id, 75.0,
                    f"Installation de {sw_name}...",
                    "Veuillez patienter..."
                )

                install_result: InstallResult = self.installer_manager.install_software(
                    sw,
                    installer_path=dl_result.file_path,
                )

                if install_result.status in (InstallStatus.SUCCESS, InstallStatus.ALREADY_INSTALLED):
                    self._set_progress_complete(sw_id, True, install_result.message)
                    success_count += 1
                    # Mettre à jour la carte dans la liste
                    self._update_software_card_status(sw_id, "✓ Installé", Theme.SUCCESS)
                else:
                    self._set_progress_complete(sw_id, False, install_result.message)
                    fail_count += 1

                # Nettoyage du fichier téléchargé (sauf si c'était un setup local)
                if (not dl_result.was_local
                        and self.settings.get("auto_cleanup_downloads", True)
                        and dl_result.file_path and dl_result.file_path.exists()):
                    try:
                        dl_result.file_path.unlink()
                    except OSError:
                        pass

            except Exception as e:
                logger.exception(f"Erreur pour {sw_name}")
                self._set_progress_complete(sw_id, False, f"Erreur: {str(e)}")
                fail_count += 1
            finally:
                self._current_download_id = None
                self._download_paused = False
                self.after(0, lambda: self.pause_btn.configure(text="⏸️  Pause DL"))

        # Fin du traitement
        self._finalize_processing(total, success_count, fail_count)

    # ─────────────── Helpers UI thread-safe ───────────────
    def _update_progress_card(self, sw_id: str, percentage: float, status: str, info: str = ""):
        """Met à jour une carte de progression (thread-safe)"""
        def _update():
            card = self._progress_cards.get(sw_id)
            if card:
                card.update_progress(percentage, status, info)
        self.after(0, _update)

    def _set_progress_complete(self, sw_id: str, success: bool, message: str):
        """Marque une carte de progression comme terminée (thread-safe)"""
        def _update():
            card = self._progress_cards.get(sw_id)
            if card:
                card.set_complete(success, message)
        self.after(0, _update)

    def _update_software_card_status(self, sw_id: str, text: str, color: str):
        """Met à jour le statut d'une carte logiciel (thread-safe)"""
        def _update():
            for card in self._software_cards:
                if card.software.get("id") == sw_id:
                    card.set_status(text, color)
                    card.is_installed = True
                    break
        self.after(0, _update)

    def _finalize_processing(self, total: int, success: int, fail: int):
        """Finalise le traitement (thread-safe)"""
        def _update():
            self._active_tasks -= 1
            if self._active_tasks <= 0:
                self._active_tasks = 0
                self._is_processing = False
                self.install_btn.configure(
                    state="normal",
                    text="⬇️  Installer la sélection"
                )
                self.pause_btn.configure(
                    state="disabled",
                    text="⏸️  Pause DL"
                )
                self._set_pause_button_visibility(False)

            self.stats_label.configure(
                text=f"Terminé (dernière tâche): {success} ✓  {fail} ✗  sur {total}"
            )

            # Notification
            if fail == 0:
                messagebox.showinfo(
                    "Installation terminée",
                    f"Tous les {total} logiciel(s) ont été installés avec succès !"
                )
            else:
                messagebox.showwarning(
                    "Installation terminée",
                    f"{success} installé(s), {fail} en échec sur {total}."
                )

            # Désélectionner tout
            for card in self._software_cards:
                card.is_checked = False

            # Nettoyage visuel différé: n'affiche pas les erreurs indéfiniment
            if self._progress_reset_after_id:
                try:
                    self.after_cancel(self._progress_reset_after_id)
                except Exception:
                    pass
            self._progress_reset_after_id = self.after(30000, self._reset_progress_panel_if_idle)

        self.after(0, _update)

    def _reset_progress_panel_if_idle(self):
        """Efface la progression si aucune tâche n'est active."""
        self._progress_reset_after_id = None
        if self._is_processing:
            return
        self._clear_progress_panel()
        self.progress_placeholder.pack(pady=40)

    def _toggle_download_pause(self):
        """Met en pause / reprend le téléchargement actif"""
        if not self._is_processing:
            return

        sw_id = self._current_download_id
        if not sw_id:
            messagebox.showinfo(
                "Téléchargement",
                "Aucun téléchargement actif pour le moment."
            )
            return

        if not self._download_paused:
            paused = self.download_manager.pause_download(sw_id)
            if paused:
                self._download_paused = True
                self.pause_btn.configure(text="▶️  Reprendre DL")
                self.stats_label.configure(text="Téléchargement en pause")
            else:
                messagebox.showwarning(
                    "Pause impossible",
                    "Impossible de mettre en pause ce téléchargement actuellement."
                )
        else:
            resumed = self.download_manager.resume_download(sw_id)
            if resumed:
                self._download_paused = False
                self.pause_btn.configure(text="⏸️  Pause DL")
                self.stats_label.configure(text="Téléchargement repris")
            else:
                messagebox.showwarning(
                    "Reprise impossible",
                    "Impossible de reprendre ce téléchargement actuellement."
                )

    def _clear_progress_panel(self):
        """Nettoie le panel de progression"""
        self.progress_placeholder.pack_forget()
        for card in self._progress_cards.values():
            card.destroy()
        self._progress_cards.clear()
        self.stats_label.configure(text="")

    def _bind_widget_to_software_scroll(self, widget):
        """Force le scroll molette des cartes logiciel vers le panneau principal."""
        try:
            widget.bind("<Enter>", lambda _e: self._set_active_scroll_target("software"), add="+")
            widget.bind("<MouseWheel>", self._on_software_mousewheel, add="+")
            widget.bind("<Button-4>", self._on_software_mousewheel, add="+")
            widget.bind("<Button-5>", self._on_software_mousewheel, add="+")
        except Exception:
            return

        for child in widget.winfo_children():
            self._bind_widget_to_software_scroll(child)

    def _set_pause_button_visibility(self, visible: bool):
        """Affiche le bouton pause uniquement pendant un traitement actif."""
        if visible:
            self.pause_btn.grid()
        else:
            self.pause_btn.grid_remove()
