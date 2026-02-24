"""
DaxterWare - Interface graphique principale
Application de gestion et d'installation de logiciels avec CustomTkinter
"""

import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox, filedialog
import threading
import logging
import webbrowser
from pathlib import Path
from typing import Optional, Dict, List, Callable

from core.catalog_manager import CatalogManager, SettingsManager
from core.downloader import DownloadManager, DownloadStatus, DownloadProgress, DownloadResult, LocalInstallerDetector
from core.installer import InstallerManager, InstallStatus, InstallResult

logger = logging.getLogger(__name__)


# ──────────────────────────── Couleurs & Style ────────────────────────────
class Theme:
    """Palette de couleurs pour l'application"""
    BG_DARK = "#1a1a2e"
    BG_CARD = "#16213e"
    BG_SIDEBAR = "#0f3460"
    ACCENT = "#e94560"
    ACCENT_HOVER = "#ff6b81"
    TEXT = "#eaeaea"
    TEXT_DIM = "#a0a0b0"
    TEXT_DARK = "#6c6c80"
    SUCCESS = "#2ed573"
    WARNING = "#ffa502"
    ERROR = "#ff4757"
    BORDER = "#2a2a4a"
    INPUT_BG = "#1e1e3a"
    PROGRESS_BG = "#2a2a4a"
    CATEGORY_COLORS = [
        "#e94560", "#0f3460", "#2ed573", "#ffa502",
        "#5352ed", "#ff6348", "#1e90ff", "#a55eea"
    ]


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
            fg_color="transparent",
            hover_color=Theme.BG_SIDEBAR,
            command=self._open_website,
        )
        self.info_btn.grid(row=0, column=4, rowspan=2, padx=(2, 12))

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
        self.status_label.configure(text=text, text_color=color)


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

    WINDOW_MIN_WIDTH = 1100
    WINDOW_MIN_HEIGHT = 700

    def __init__(
        self,
        catalog: CatalogManager,
        settings: SettingsManager,
        base_path: Path
    ):
        super().__init__()

        self.catalog = catalog
        self.settings = settings
        self.base_path = base_path

        # Managers
        self.download_manager = DownloadManager(
            download_folder=base_path / settings.download_folder,
            installers_folder=base_path / settings.get("installers_folder", "installers"),
            max_concurrent=settings.max_concurrent_downloads,
        )
        self.installer_manager = InstallerManager(base_path)

        # State
        self._software_cards: List[SoftwareCard] = []
        self._progress_cards: Dict[str, ProgressCard] = {}
        self._current_category: Optional[str] = None
        self._is_processing = False

        self._configure_window()
        self._build_ui()
        self._show_category(None)  # Afficher tous les logiciels

    # ─────────────── Configuration fenêtre ───────────────
    def _configure_window(self):
        self.title(f"{self.settings.app_name} v{self.settings.version}")
        self.geometry("1200x780")
        self.minsize(self.WINDOW_MIN_WIDTH, self.WINDOW_MIN_HEIGHT)

        # Thème
        ctk.set_appearance_mode("dark")
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
        self.sidebar.grid_rowconfigure(10, weight=1)  # Spacer

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

        # Bouton "Tous les logiciels"
        self.all_btn = ctk.CTkButton(
            self.sidebar,
            text=f"📋  Tous les logiciels  ({self.catalog.get_software_count()})",
            font=ctk.CTkFont(size=13),
            fg_color=Theme.ACCENT,
            hover_color=Theme.ACCENT_HOVER,
            height=38,
            anchor="w",
            command=lambda: self._show_category(None),
        )
        self.all_btn.grid(row=4, column=0, sticky="ew", padx=16, pady=3)

        # Boutons de catégories
        self._category_buttons: Dict[str, ctk.CTkButton] = {}
        for i, cat in enumerate(self.catalog.categories):
            cat_name = cat.get("name", "")
            cat_icon = cat.get("icon", "")
            sw_count = len(cat.get("software", []))

            btn = ctk.CTkButton(
                self.sidebar,
                text=f"{cat_icon}  {cat_name}  ({sw_count})",
                font=ctk.CTkFont(size=13),
                fg_color="transparent",
                hover_color=Theme.BG_CARD,
                text_color=Theme.TEXT_DIM,
                height=36,
                anchor="w",
                command=lambda n=cat_name: self._show_category(n),
            )
            btn.grid(row=5 + i, column=0, sticky="ew", padx=16, pady=2)
            self._category_buttons[cat_name] = btn

        # ─── Zone basse de la sidebar ───
        bottom_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        bottom_frame.grid(row=20, column=0, sticky="sew", padx=16, pady=(10, 16))

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

        # Info setups locaux
        local_count = self.download_manager.get_local_count()
        if local_count > 0:
            ctk.CTkLabel(
                bottom_frame,
                text=f"📁 {local_count} setup(s) local(aux)",
                font=ctk.CTkFont(size=10),
                text_color=Theme.SUCCESS,
            ).pack(anchor="w", pady=(2, 0))

    def _build_main_area(self):
        """Zone principale avec la liste des logiciels"""
        main_frame = ctk.CTkFrame(self, fg_color="transparent")
        main_frame.grid(row=0, column=1, sticky="nsew", padx=0, pady=0)
        main_frame.grid_columnconfigure(0, weight=1)
        main_frame.grid_rowconfigure(1, weight=1)

        # ─── Barre d'outils en haut ───
        toolbar = ctk.CTkFrame(
            main_frame,
            fg_color=Theme.BG_CARD,
            height=56,
            corner_radius=0,
        )
        toolbar.grid(row=0, column=0, sticky="ew")
        toolbar.grid_propagate(False)
        toolbar.grid_columnconfigure(2, weight=1)

        # Titre de la catégorie
        self.category_title = ctk.CTkLabel(
            toolbar,
            text="Tous les logiciels",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=Theme.TEXT,
        )
        self.category_title.grid(row=0, column=0, padx=20, pady=14)

        # Compteur
        self.count_label = ctk.CTkLabel(
            toolbar,
            text="",
            font=ctk.CTkFont(size=12),
            text_color=Theme.TEXT_DIM,
        )
        self.count_label.grid(row=0, column=1, padx=6)

        # Boutons d'action à droite
        btn_frame = ctk.CTkFrame(toolbar, fg_color="transparent")
        btn_frame.grid(row=0, column=3, padx=12)

        self.select_all_btn = ctk.CTkButton(
            btn_frame,
            text="☑ Tout sélectionner",
            font=ctk.CTkFont(size=12),
            fg_color="transparent",
            hover_color=Theme.BG_SIDEBAR,
            text_color=Theme.TEXT_DIM,
            width=130,
            height=32,
            command=self._toggle_select_all,
        )
        self.select_all_btn.pack(side="left", padx=4)

        self.install_btn = ctk.CTkButton(
            btn_frame,
            text="⬇️  Installer la sélection",
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=Theme.ACCENT,
            hover_color=Theme.ACCENT_HOVER,
            width=200,
            height=36,
            command=self._start_install_selected,
        )
        self.install_btn.pack(side="left", padx=4)

        # ─── Zone scrollable pour les logiciels ───
        self.content_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        self.content_frame.grid(row=1, column=0, sticky="nsew")
        self.content_frame.grid_columnconfigure(0, weight=3)  # Liste logiciels
        self.content_frame.grid_columnconfigure(1, weight=1)  # Panel progression
        self.content_frame.grid_rowconfigure(0, weight=1)

        # Liste des logiciels (scrollable)
        self.software_scroll = ctk.CTkScrollableFrame(
            self.content_frame,
            fg_color="transparent",
            scrollbar_button_color=Theme.BG_SIDEBAR,
            scrollbar_button_hover_color=Theme.ACCENT,
        )
        self.software_scroll.grid(row=0, column=0, sticky="nsew", padx=(12, 6), pady=12)
        self.software_scroll.grid_columnconfigure(0, weight=1)

        # Panel de progression (côté droit)
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
        self.progress_panel.grid(row=0, column=1, sticky="nsew", padx=(6, 12), pady=12)
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
            card.grid(row=i, column=0, sticky="ew", pady=3)
            self._software_cards.append(card)

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
        if self._is_processing:
            messagebox.showwarning(
                "En cours",
                "Un traitement est déjà en cours. Veuillez patienter."
            )
            return

        selected = self._get_selected_software()

        if not selected:
            messagebox.showinfo(
                "Aucune sélection",
                "Veuillez sélectionner au moins un logiciel à installer."
            )
            return

        # Vérifier les droits admin
        if not InstallerManager.is_admin():
            result = messagebox.askyesno(
                "Droits administrateur",
                "L'installation nécessite des droits administrateur.\n"
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

        self._is_processing = True
        self.install_btn.configure(state="disabled", text="⏳  Installation en cours...")

        # Préparer le panel de progression
        self._clear_progress_panel()

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
            self._is_processing = False
            self.install_btn.configure(
                state="normal",
                text="⬇️  Installer la sélection"
            )

            self.stats_label.configure(
                text=f"Terminé: {success} ✓  {fail} ✗  sur {total}"
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

        self.after(0, _update)

    def _clear_progress_panel(self):
        """Nettoie le panel de progression"""
        self.progress_placeholder.pack_forget()
        for card in self._progress_cards.values():
            card.destroy()
        self._progress_cards.clear()
        self.stats_label.configure(text="")
