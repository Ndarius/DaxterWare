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
        if compact == self._compact_mode:
            return
        self._compact_mode = compact
        if compact:
            self.size_label.configure(width=48)
            self.status_label.configure(width=86)
            self.info_btn.configure(width=28, height=28)
            text = self.status_label.cget("text")
            if text.startswith("✓"): self.status_label.configure(text="✓ OK")
            elif "Setup" in text or "📁" in text: self.status_label.configure(text="📁 Local")
            else: self.status_label.configure(text="⬇ DL")
        else:
            self.size_label.configure(width=60)
            self.status_label.configure(width=100)
            self.info_btn.configure(width=32, height=32)
            text = self.status_label.cget("text")
            if text == "✓ OK": self.status_label.configure(text="✓ Installé")
            elif text == "📁 Local": self.status_label.configure(text="📁 Setup prêt")
            elif text == "⬇ DL": self.status_label.configure(text="⬇ À télécharger")

    def _open_website(self):
        url = self.software.get("website", "")
        if url: webbrowser.open(url)

    @property
    def is_checked(self) -> bool: return self._checkbox_var.get()
    @is_checked.setter
    def is_checked(self, value: bool): self._checkbox_var.set(value)

    def set_status(self, text: str, color: str):
        display_text = text
        if self._compact_mode:
            if text.startswith("✓"): display_text = "✓ OK"
            elif "Setup" in text or "📁" in text: display_text = "📁 Local"
            elif text.startswith("⬇"): display_text = "⬇ DL"
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
        self.name_label = ctk.CTkLabel(
            self, text=self.software_name,
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=Theme.TEXT, anchor="w",
        )
        self.name_label.grid(row=0, column=0, sticky="w", padx=12, pady=(8, 2))
        self.status_label = ctk.CTkLabel(
            self, text="En attente...",
            font=ctk.CTkFont(size=11),
            text_color=Theme.TEXT_DIM, anchor="w",
        )
        self.status_label.grid(row=1, column=0, sticky="w", padx=12, pady=(0, 2))
        self.progress_bar = ctk.CTkProgressBar(
            self, height=6, progress_color=Theme.ACCENT,
            fg_color=Theme.PROGRESS_BG, corner_radius=3,
        )
        self.progress_bar.grid(row=2, column=0, sticky="ew", padx=12, pady=(2, 4))
        self.progress_bar.set(0)
        self.info_label = ctk.CTkLabel(
            self, text="", font=ctk.CTkFont(size=10),
            text_color=Theme.TEXT_DARK, anchor="w",
        )
        self.info_label.grid(row=3, column=0, sticky="w", padx=12, pady=(0, 8))

    def update_progress(self, percentage: float, status_text: str, info_text: str = ""):
        self.progress_bar.set(percentage / 100.0)
        self.status_label.configure(text=status_text)
        if info_text: self.info_label.configure(text=info_text)

    def set_complete(self, success: bool, message: str):
        self.progress_bar.set(1.0 if success else 0.0)
        color = Theme.SUCCESS if success else Theme.ERROR
        self.progress_bar.configure(progress_color=color)
        self.status_label.configure(text=message, text_color=color)
        self.info_label.configure(text="")


# ──────────────────────────── Fenêtre principale ──────────────────────────
class SoftwareManagerApp(ctk.CTk):
    """Fenêtre principale de DaxterWare"""

    WINDOW_MIN_WIDTH = 920
    WINDOW_MIN_HEIGHT = 680
    COMPACT_BREAKPOINT = 1240
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
            additional_local_folders=[base_path / settings.get("offline_folder", "offline")],
        )
        self.installer_manager = InstallerManager(base_path)

        # State
        self._software_cards: List[SoftwareCard] = []
        self._progress_cards: Dict[str, ProgressCard] = {}
        self._current_category: Optional[str] = None
        self._active_tasks = 0
        self._is_processing = False
        self._download_paused = False
        self._responsive_mode: Optional[str] = None
        self._toolbar_responsive_mode: Optional[str] = None
        self._resize_after_id: Optional[str] = None
        self._last_layout_width: Optional[int] = None

        self._configure_window()
        self._build_ui()
        self._bind_responsive_events()
        self._bind_software_scroll_events()
        self._refresh_license_ui()
        self.after(50, lambda: self._apply_responsive_layout(force=True))
        self._show_category(None)

    def _configure_window(self):
        self.title(f"{self.settings.app_name} v{self.settings.version}")
        self.geometry("1200x780")
        self.minsize(self.WINDOW_MIN_WIDTH, self.WINDOW_MIN_HEIGHT)
        Theme.apply_mode(self.settings.get("theme_palette", "blue"))
        ctk.set_default_color_theme("blue")
        self.configure(fg_color=Theme.BG_DARK)
        self.update_idletasks()
        x = (self.winfo_screenwidth() - 1200) // 2
        y = (self.winfo_screenheight() - 780) // 2
        self.geometry(f"+{x}+{y}")

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
        self.bind("<Configure>", self._on_window_resize)

    def _on_window_resize(self, event):
        if event.widget is not self: return
        if self._resize_after_id:
            try: self.after_cancel(self._resize_after_id)
            except: pass
        self._resize_after_id = self.after(90, self._apply_responsive_layout)

    def _bind_software_scroll_events(self):
        """Correction critique du scroll : bind global avec routage intelligent"""
        self.bind_all("<MouseWheel>", self._on_any_mousewheel, add="+")
        self.bind_all("<Button-4>", self._on_any_mousewheel, add="+")
        self.bind_all("<Button-5>", self._on_any_mousewheel, add="+")

    def _scroll_frame_by_wheel(self, frame, delta: int):
        canvas = getattr(frame, "_parent_canvas", None)
        if canvas is None: return
        steps = -int(delta / 6) if sys.platform.startswith("win") else -int(delta)
        if steps == 0: steps = -1 if delta > 0 else 1
        canvas.yview_scroll(steps, "units")

    def _on_any_mousewheel(self, event):
        delta = getattr(event, "delta", 0)
        if delta == 0:
            num = getattr(event, "num", None)
            if num == 4: delta = 120
            elif num == 5: delta = -120
        if delta == 0: return

        hovered = self.winfo_containing(event.x_root, event.y_root)
        if hovered is None: return

        # Routage par zone de survol
        for scroll_area in [self.category_scroll, self.progress_scroll, self.software_scroll]:
            if self._is_widget_in_scroll_area(hovered, scroll_area):
                self._scroll_frame_by_wheel(scroll_area, delta)
                return "break"
        return None

    def _is_widget_in_scroll_area(self, widget, frame) -> bool:
        candidates = {frame}
        for attr in ("_parent_canvas", "_parent_frame", "_scrollbar"):
            cand = getattr(frame, attr, None)
            if cand: candidates.add(cand)
        curr = widget
        while curr:
            if curr in candidates: return True
            curr = getattr(curr, "master", None)
        return False

    def _apply_responsive_layout(self, force: bool = False):
        width = self.winfo_width()
        if width <= 1: return
        mode = "compact" if width < self.COMPACT_BREAKPOINT else "wide"
        toolbar_mode = "compact" if width < self.TOOLBAR_COMPACT_BREAKPOINT else "wide"

        if not force and mode == self._responsive_mode and toolbar_mode == self._toolbar_responsive_mode and self._last_layout_width and abs(width - self._last_layout_width) < 12:
            return

        self._responsive_mode = mode
        self._toolbar_responsive_mode = toolbar_mode
        self._last_layout_width = width

        scale = max(0.52, min(1.0, width / 1440.0))
        side_pad = max(8, int(12 * scale))
        split_pad = max(4, int(6 * scale))
        block_pad = max(6, int(12 * scale))

        # Layout principal
        self.software_scroll.grid_configure(row=1, column=0, padx=(side_pad, split_pad), pady=block_pad, sticky="nsew")
        self.progress_panel.grid_configure(row=1, column=1, padx=(split_pad, side_pad), pady=block_pad, sticky="nsew")
        self.toolbar_actions.grid_configure(row=0, column=1, sticky="e", padx=side_pad, pady=(block_pad, 0))

        if mode == "compact":
            self.content_frame.grid_columnconfigure(0, weight=4)
            self.content_frame.grid_columnconfigure(1, weight=2)
        else:
            self.content_frame.grid_columnconfigure(0, weight=3)
            self.content_frame.grid_columnconfigure(1, weight=1)

        # Toolbar boutons (Toujours en haut à droite)
        pause_visible = self._is_processing
        self.pause_btn.grid() if pause_visible else self.pause_btn.grid_remove()
        
        # Mise à jour des cartes
        self._refresh_cards_layout(mode, width)

    def _refresh_cards_layout(self, mode: str, width: int):
        scale = max(0.64, min(1.0, width / 1440.0))
        left_col_width = self.software_scroll.winfo_width() or int(width * 0.55)
        wrap = max(170, min(620, int(left_col_width * 0.60)))
        is_extra_compact = width < self.EXTRA_COMPACT_BREAKPOINT
        
        for card in self._software_cards:
            try:
                card.desc_label.configure(wraplength=wrap)
                card.set_compact_mode(is_extra_compact)
            except: continue

    def _build_sidebar(self):
        self.sidebar = ctk.CTkFrame(self, width=240, fg_color=Theme.BG_SIDEBAR, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)
        self.sidebar.grid_columnconfigure(0, weight=1)
        self.sidebar.grid_rowconfigure(4, weight=1)

        # Logo
        logo_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        logo_frame.grid(row=0, column=0, sticky="ew", padx=16, pady=(20, 6))
        ctk.CTkLabel(logo_frame, text="📦 Daxter", font=ctk.CTkFont(size=22, weight="bold"), text_color=Theme.TEXT).pack(anchor="w")
        ctk.CTkLabel(logo_frame, text="   Ware", font=ctk.CTkFont(size=22, weight="bold"), text_color=Theme.ACCENT).pack(anchor="w")

        # Thème & Version
        ctk.CTkLabel(self.sidebar, text=f"v{self.settings.version}", font=ctk.CTkFont(size=10), text_color=Theme.TEXT_DARK).grid(row=1, column=0, sticky="w", padx=20, pady=(0, 20))
        self.theme_btn = ctk.CTkButton(self.sidebar, text="🎨 Thème", font=ctk.CTkFont(size=11), fg_color="transparent", border_width=1, border_color=Theme.BORDER, text_color=Theme.TEXT_DIM, height=24, width=70, command=self._toggle_theme)
        self.theme_btn.grid(row=1, column=0, sticky="e", padx=16, pady=(0, 20))

        # Recherche
        self.search_var = ctk.StringVar()
        self.search_var.trace_add("write", self._on_search_changed)
        self.search_entry = ctk.CTkEntry(self.sidebar, placeholder_text="🔍  Rechercher...", textvariable=self.search_var, fg_color=Theme.INPUT_BG, border_color=Theme.BORDER, text_color=Theme.TEXT, height=36)
        self.search_entry.grid(row=2, column=0, sticky="ew", padx=16, pady=(0, 16))

        # Catégories
        self.category_scroll = ctk.CTkScrollableFrame(self.sidebar, fg_color="transparent", scrollbar_button_color=Theme.BG_SIDEBAR)
        self.category_scroll.grid(row=4, column=0, sticky="nsew", padx=0, pady=0)
        self.category_scroll.grid_columnconfigure(0, weight=1)
        
        self.all_btn = ctk.CTkButton(self.category_scroll, text="📋  Tous", font=ctk.CTkFont(size=12), fg_color=Theme.ACCENT, text_color=Theme.TEXT, height=32, anchor="w", command=lambda: self._show_category(None))
        self.all_btn.pack(fill="x", padx=8, pady=4)

        self._category_buttons = {}
        for cat in self.catalog.categories:
            name = cat.get("name", "")
            icon = cat.get("icon", "")
            btn = ctk.CTkButton(self.category_scroll, text=f"{icon}  {name}", font=ctk.CTkFont(size=12), fg_color="transparent", text_color=Theme.TEXT_DIM, height=32, anchor="w", command=lambda n=name: self._show_category(n))
            btn.pack(fill="x", padx=8, pady=4)
            self._category_buttons[name] = btn

        # ─── SECTION LICENCE (Restaurée) ───
        self._build_license_section()

    def _build_license_section(self):
        bottom_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        bottom_frame.grid(row=5, column=0, sticky="ew", padx=16, pady=(10, 20))
        
        self.license_card = ctk.CTkFrame(bottom_frame, fg_color=Theme.INPUT_BG, corner_radius=10, border_width=1, border_color=Theme.BORDER)
        self.license_card.pack(fill="x", pady=(8, 0))
        self.license_card.grid_columnconfigure(0, weight=1)

        self.license_title = ctk.CTkLabel(self.license_card, text="🔐 Licence & Essai", font=ctk.CTkFont(size=12, weight="bold"), text_color=Theme.TEXT, anchor="w")
        self.license_title.grid(row=0, column=0, sticky="ew", padx=10, pady=(8, 0))

        self.license_plan_badge = ctk.CTkLabel(self.license_card, text="", font=ctk.CTkFont(size=10, weight="bold"), corner_radius=8, fg_color=Theme.BG_SIDEBAR, text_color=Theme.TEXT, padx=8, pady=2)
        self.license_plan_badge.grid(row=1, column=0, sticky="w", padx=10, pady=(6, 0))

        self.license_label = ctk.CTkLabel(self.license_card, text="", font=ctk.CTkFont(size=11, weight="bold"), text_color=Theme.WARNING, anchor="w", justify="left", wraplength=190)
        self.license_label.grid(row=2, column=0, sticky="ew", padx=10, pady=(6, 0))

        self.license_period_label = ctk.CTkLabel(self.license_card, text="", font=ctk.CTkFont(size=10), text_color=Theme.TEXT_DIM, anchor="w", justify="left", wraplength=190)
        self.license_period_label.grid(row=3, column=0, sticky="ew", padx=10, pady=(2, 0))

        self.license_progress = ctk.CTkProgressBar(self.license_card, height=6, progress_color=Theme.ACCENT, fg_color=Theme.PROGRESS_BG, corner_radius=4)
        self.license_progress.grid(row=4, column=0, sticky="ew", padx=10, pady=(8, 0))
        
        self.activate_pro_btn = ctk.CTkButton(self.license_card, text="🔑 Activer Pro illimité", font=ctk.CTkFont(size=11, weight="bold"), fg_color=Theme.ACCENT, hover_color=Theme.ACCENT_HOVER, height=30, command=self._activate_pro_trial_prompt)
        self.activate_pro_btn.grid(row=5, column=0, sticky="ew", padx=10, pady=(8, 10))

    def _refresh_license_ui(self):
        status = self.license_manager.get_status()
        plan = status.get("plan")
        if plan == "pro":
            self.license_plan_badge.configure(text="PRO ACTIVÉ", fg_color="#3b2f8f")
            self.license_label.configure(text="💎 Mode Pro illimité actif", text_color=Theme.SUCCESS)
            self.license_period_label.configure(text=f"Activation: {status.get('pro_activated_on', '') or '—'}")
            self.license_progress.set(1.0)
            self.activate_pro_btn.configure(state="disabled", text="🔓 Pro illimité")
        elif plan == "free_trial":
            days = status.get('free_days_left', 0)
            total = status.get('free_total_days', 30)
            self.license_plan_badge.configure(text="FREE TRIAL", fg_color=Theme.BG_SIDEBAR)
            self.license_label.configure(text=f"🆓 Essai gratuit — {days} jour(s)", text_color=Theme.WARNING)
            self.license_period_label.configure(text=f"Installation: {status.get('installation_date', '')}")
            self.license_progress.set(max(0, min(1.0, (total - days) / total)) if total > 0 else 0)
            self.activate_pro_btn.configure(state="normal", text="🔑 Activer Pro illimité")
        else:
            self.license_plan_badge.configure(text="EXPIRED", fg_color="#5c1f2d")
            self.license_label.configure(text="⛔ Essai expiré", text_color=Theme.ERROR)
            self.license_period_label.configure(text=f"Fin essai: {status.get('free_trial_end', '')}")
            self.license_progress.set(1.0)
            self.activate_pro_btn.configure(state="normal", text="🔑 Activer Pro illimité")

    def _activate_pro_trial_prompt(self):
        key = simpledialog.askstring("Clé produit", "Entrez votre clé produit :", parent=self)
        if key:
            ok, msg = self.license_manager.activate_pro_trial(key)
            if ok: messagebox.showinfo("Succès", msg)
            else: messagebox.showwarning("Erreur", msg)
            self._refresh_license_ui()

    def _build_main_area(self):
        main_frame = ctk.CTkFrame(self, fg_color="transparent")
        main_frame.grid(row=0, column=1, sticky="nsew")
        main_frame.grid_columnconfigure(0, weight=1)
        main_frame.grid_rowconfigure(1, weight=1)

        # Header
        header = ctk.CTkFrame(main_frame, fg_color=Theme.BG_CARD, height=60, corner_radius=0)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_propagate(False)
        header.grid_columnconfigure(0, weight=1)

        self.category_title = ctk.CTkLabel(header, text="Tous les logiciels", font=ctk.CTkFont(size=18, weight="bold"), text_color=Theme.TEXT)
        self.category_title.grid(row=0, column=0, sticky="w", padx=20, pady=15)

        self.count_label = ctk.CTkLabel(header, text="", font=ctk.CTkFont(size=12), text_color=Theme.TEXT_DIM)
        self.count_label.grid(row=0, column=1, padx=10)

        # Actions (Toujours à droite)
        self.toolbar_actions = ctk.CTkFrame(header, fg_color="transparent")
        self.toolbar_actions.grid(row=0, column=2, padx=15)

        self.select_all_btn = ctk.CTkButton(self.toolbar_actions, text="☑ Tout", width=80, height=32, fg_color="transparent", text_color=Theme.TEXT_DIM, command=self._toggle_select_all)
        self.select_all_btn.pack(side="left", padx=4)

        self.install_btn = ctk.CTkButton(self.toolbar_actions, text="⬇️ Installer", width=140, height=36, fg_color=Theme.ACCENT, font=ctk.CTkFont(weight="bold"), command=self._start_install_selected)
        self.install_btn.pack(side="left", padx=4)

        self.pause_btn = ctk.CTkButton(self.toolbar_actions, text="⏸️ Pause", width=100, height=36, fg_color=Theme.BG_SIDEBAR, command=self._toggle_download_pause)
        self.pause_btn.pack(side="left", padx=4)
        self.pause_btn.pack_forget()

        # Content
        self.content_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        self.content_frame.grid(row=1, column=0, sticky="nsew")
        self.content_frame.grid_columnconfigure(0, weight=3)
        self.content_frame.grid_columnconfigure(1, weight=1)
        self.content_frame.grid_rowconfigure(1, weight=1)

        self.software_scroll = ctk.CTkScrollableFrame(self.content_frame, fg_color="transparent", scrollbar_button_color=Theme.BG_SIDEBAR)
        self.software_scroll.grid(row=1, column=0, sticky="nsew", padx=(12, 6), pady=12)
        self.software_scroll.grid_columnconfigure(0, weight=1)

        self._build_progress_panel()

    def _build_progress_panel(self):
        self.progress_panel = ctk.CTkFrame(self.content_frame, fg_color=Theme.BG_CARD, corner_radius=10, border_width=1, border_color=Theme.BORDER)
        self.progress_panel.grid(row=1, column=1, sticky="nsew", padx=(6, 12), pady=12)
        self.progress_panel.grid_columnconfigure(0, weight=1)
        self.progress_panel.grid_rowconfigure(2, weight=1)

        ctk.CTkLabel(self.progress_panel, text="📊 Progression", font=ctk.CTkFont(size=15, weight="bold")).grid(row=0, column=0, sticky="w", padx=16, pady=15)
        self.progress_scroll = ctk.CTkScrollableFrame(self.progress_panel, fg_color="transparent")
        self.progress_scroll.grid(row=2, column=0, sticky="nsew", padx=8, pady=8)
        self.progress_placeholder = ctk.CTkLabel(self.progress_scroll, text="Sélectionnez des logiciels\npuis cliquez sur Installer", font=ctk.CTkFont(size=12), text_color=Theme.TEXT_DARK)
        self.progress_placeholder.pack(pady=40)

    def _show_category(self, category_name: Optional[str]):
        self._current_category = category_name
        self.all_btn.configure(fg_color=Theme.ACCENT if category_name is None else "transparent", text_color=Theme.TEXT if category_name is None else Theme.TEXT_DIM)
        for name, btn in self._category_buttons.items():
            active = (name == category_name)
            btn.configure(fg_color=Theme.ACCENT if active else "transparent", text_color=Theme.TEXT if active else Theme.TEXT_DIM)
        
        if category_name:
            cat = self.catalog.get_category(category_name)
            self.category_title.configure(text=f"{cat.get('icon', '')}  {category_name}")
        else:
            self.category_title.configure(text="📋  Tous les logiciels")
        self._load_software_list(category_name)

    def _load_software_list(self, category_name: Optional[str]):
        for card in self._software_cards: card.destroy()
        self._software_cards.clear()
        sw_list = self.catalog.get_software_by_category(category_name) if category_name else self.catalog.all_software
        query = self.search_var.get().strip().lower()
        if query: sw_list = [s for s in sw_list if query in s.get("name", "").lower() or query in s.get("description", "").lower()]
        
        self.count_label.configure(text=f"({len(sw_list)} logiciels)")
        for sw in sw_list:
            card = SoftwareCard(self.software_scroll, software=sw, is_installed=self.installer_manager.check_software_installed(sw), has_local_setup=self.download_manager.local_detector.find_installer(sw) is not None)
            card.pack(fill="x", pady=3, padx=2)
            self._software_cards.append(card)
        self._apply_responsive_layout(force=True)

    def _on_search_changed(self, *args): self._load_software_list(self._current_category)
    def _toggle_select_all(self):
        val = not any(c.is_checked for c in self._software_cards)
        for c in self._software_cards: c.is_checked = val
        self.select_all_btn.configure(text="☐ Aucun" if val else "☑ Tout")

    def _start_install_selected(self):
        if not self.license_manager.can_use_app():
            messagebox.showerror("Essai expiré", "Veuillez activer le mode Pro pour continuer.")
            return
        selected = [c.software for c in self._software_cards if c.is_checked]
        if not selected:
            messagebox.showinfo("Sélection", "Veuillez sélectionner au moins un logiciel.")
            return
        self._is_processing = True
        self.progress_placeholder.pack_forget()
        for sw in selected:
            pc = ProgressCard(self.progress_scroll, sw.get("name", "Inconnu"))
            pc.pack(fill="x", pady=4, padx=2)
            self._progress_cards[sw.get("id")] = pc
        self._apply_responsive_layout(force=True)
        threading.Thread(target=self._install_thread, args=(selected,), daemon=True).start()

    def _install_thread(self, selected):
        for sw in selected:
            sid = sw.get("id")
            if sid not in self._progress_cards: continue
            pc = self._progress_cards[sid]
            res = self.download_manager.download(sw, lambda p: pc.update_progress(p.percentage, f"DL: {p.percentage:.0f}%", f"{p.speed_mbps:.1f} MB/s"))
            if res.success:
                ires = self.installer_manager.install(res.file_path, sw)
                pc.set_complete(ires.success, "✓ Installé" if ires.success else f"❌ {ires.error}")
            else: pc.set_complete(False, f"❌ {res.error}")
        self._is_processing = False
        self.after(100, lambda: self._apply_responsive_layout(force=True))

    def _toggle_download_pause(self):
        self._download_paused = not self._download_paused
        if self._download_paused: self.download_manager.pause()
        else: self.download_manager.resume()
        self.pause_btn.configure(text="▶️ Reprendre" if self._download_paused else "⏸️ Pause")

    def mainloop(self): super().mainloop()
