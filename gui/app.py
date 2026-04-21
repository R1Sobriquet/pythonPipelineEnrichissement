"""
EnrichFlow — Fenêtre principale de l'application.

Architecture en deux colonnes :

    ┌────────────────┬──────────────────────────────────────────────┐
    │   SIDEBAR      │   ZONE PRINCIPALE                            │
    │                │                                              │
    │  [Logo]        │   ┌──────────────────────────────────────┐   │
    │  EnrichFlow    │   │  Étape X/4 — Enrichissement...       │   │
    │                │   │  ████████████░░░░  60 %              │   │
    │  — SOURCE —    │   └──────────────────────────────────────┘   │
    │  ○ CSV         │                                              │
    │  ○ SQL Server  │   ┌──────────────────────────────────────┐   │
    │  [Parcourir]   │   │  CONSOLE DE LOG               [⌫]   │   │
    │                │   │                                      │   │
    │  — ÉTAPES —    │   │  10:00:01  [INFO]   Démarrage...     │   │
    │  ☑ Ingestion   │   │  10:00:02  [INFO]   Chargement CSV   │   │
    │  ☑ Enrichiss.  │   │  10:00:03  [OK]     Ingestion ✓      │   │
    │  ☑ Analyse     │   │  10:00:04  [WARN]   12 doublons      │   │
    │  ☑ Baselines   │   │  10:00:05  [ERROR]  Connexion DB ✗   │   │
    │                │   │                                      │   │
    │  [▶ Lancer]    │   │  (console pleine hauteur)            │   │
    │  [📁 Résultats]│   │                                      │   │
    │                │   └──────────────────────────────────────┘   │
    │  — STATUT —    │                                              │
    │  ● Prêt        │                                              │
    └────────────────┴──────────────────────────────────────────────┘

Threading :
    - PipelineRunner (daemon Thread) exécute les étapes pipeline.
    - StdoutRedirector remplace sys.stdout pour capturer les print().
    - GUILogHandler capture logging.getLogger().
    - _poll_queues() est rappelé toutes les 100 ms via after().
"""

import os
import sys
import queue
import logging
import subprocess
import tkinter as tk
from io import StringIO
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Optional

import customtkinter as ctk

# ---------------------------------------------------------------------------
# Chemins et imports internes
# ---------------------------------------------------------------------------
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from gui.log_handler import GUILogHandler
from gui.pipeline_runner import PipelineRunner

# ---------------------------------------------------------------------------
# Thème global CustomTkinter
# ---------------------------------------------------------------------------
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

# ---------------------------------------------------------------------------
# Palette de couleurs de la console (par niveau de log)
# ---------------------------------------------------------------------------
_LOG_COLORS = {
    "DEBUG":    "#6C757D",   # Gris discret
    "INFO":     "#CDD9E5",   # Blanc bleuté — texte principal
    "WARNING":  "#E3A857",   # Ambre
    "ERROR":    "#F25C5C",   # Rouge doux
    "CRITICAL": "#FF2D55",   # Rouge vif
    "STDOUT":   "#8FC9F5",   # Bleu clair — sorties print()
    "SUCCESS":  "#4CC98A",   # Vert — messages de succès
}

# Labels lisibles pour les noms d'étapes
_STEP_LABELS = {
    "ingestion":  "Ingestion",
    "enrichment": "Enrichissement",
    "analysis":   "Analyse",
    "baselines":  "Modèles Baseline",
}

# Numéros d'étapes pour la progression
_STEP_NUMBERS = {k: i + 1 for i, k in enumerate(_STEP_LABELS)}

# Police monospace pour la console technique
_CONSOLE_FONT = ("Consolas", 10)


# ---------------------------------------------------------------------------
# Redirecteur stdout → queue
# ---------------------------------------------------------------------------

class StdoutRedirector:
    """
    Remplace sys.stdout pour capturer les print() émis par le pipeline.

    Chaque ligne écrite dans stdout est placée dans la queue sous la forme
    ("STDOUT", texte) et sera affichée en bleu clair dans la console GUI.
    """

    def __init__(self, log_queue: queue.Queue, original_stdout) -> None:
        self._queue = log_queue
        self._original = original_stdout   # conservé pour les cas exceptionnels
        self._buffer = StringIO()

    def write(self, text: str) -> None:
        """Intercepte chaque écriture sur stdout."""
        if text and text.strip():
            self._queue.put_nowait(("STDOUT", text.rstrip("\n")))

    def flush(self) -> None:
        """Requis par l'interface file-like (no-op ici)."""
        pass

    def fileno(self) -> int:
        """Renvoie le fileno du stdout original (nécessaire pour subprocess)."""
        return self._original.fileno()


# ===========================================================================
# Fenêtre principale
# ===========================================================================

class EnrichFlowApp(ctk.CTk):
    """
    Fenêtre principale de l'application EnrichFlow.

    Deux colonnes :
    - Sidebar gauche (fixe, 270 px) : branding, configuration, boutons.
    - Zone principale droite : barre de progression + console pleine hauteur.
    """

    APP_NAME = "EnrichFlow"
    APP_VERSION = "1.0"

    def __init__(self) -> None:
        super().__init__()

        # ----------------------------------------------------------------
        # Fenêtre
        # ----------------------------------------------------------------
        self.title(f"{self.APP_NAME}  ·  Pipeline d'Enrichissement")
        self.geometry("1100x720")
        self.minsize(900, 580)

        # Grille 1 ligne × 2 colonnes : sidebar | zone principale
        self.grid_columnconfigure(0, weight=0)   # sidebar : largeur fixe
        self.grid_columnconfigure(1, weight=1)   # zone principale : extensible
        self.grid_rowconfigure(0, weight=1)

        # ----------------------------------------------------------------
        # Queues inter-threads
        # ----------------------------------------------------------------
        self._log_queue: queue.Queue = queue.Queue()
        self._progress_queue: queue.Queue = queue.Queue()

        # ----------------------------------------------------------------
        # Variables Tkinter
        # ----------------------------------------------------------------
        self._data_source_var = tk.StringVar(value="csv")
        self._csv_path_var = tk.StringVar(value="")
        self._step_vars = {
            "ingestion":  tk.BooleanVar(value=True),
            "enrichment": tk.BooleanVar(value=True),
            "analysis":   tk.BooleanVar(value=True),
            "baselines":  tk.BooleanVar(value=True),
        }
        self._pipeline_running = False

        # ----------------------------------------------------------------
        # Construction de l'interface
        # ----------------------------------------------------------------
        self._build_sidebar()
        self._build_main_area()

        # ----------------------------------------------------------------
        # Logging → queue
        # ----------------------------------------------------------------
        self._gui_handler = GUILogHandler(self._log_queue)
        self._gui_handler.setLevel(logging.DEBUG)
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO)
        root_logger.addHandler(self._gui_handler)

        # ----------------------------------------------------------------
        # Stdout → queue
        # ----------------------------------------------------------------
        self._original_stdout = sys.stdout
        sys.stdout = StdoutRedirector(self._log_queue, self._original_stdout)

        # ----------------------------------------------------------------
        # Vérification .env + démarrage du polling
        # ----------------------------------------------------------------
        self._check_env_file()
        self._poll_queues()

    # ====================================================================
    # SIDEBAR
    # ====================================================================

    def _build_sidebar(self) -> None:
        """Construit la colonne de gauche : branding, config, boutons."""
        sidebar = ctk.CTkFrame(self, width=270, corner_radius=0)
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_propagate(False)   # empêche le rétrécissement
        sidebar.grid_rowconfigure(99, weight=1)   # pousse le statut en bas

        # ---- Branding ----
        brand_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
        brand_frame.grid(row=0, column=0, sticky="ew", padx=16, pady=(20, 8))

        ctk.CTkLabel(
            brand_frame,
            text=self.APP_NAME,
            font=ctk.CTkFont(family="Segoe UI", size=26, weight="bold"),
            text_color="#5B9BD5",
        ).pack(anchor="w")

        ctk.CTkLabel(
            brand_frame,
            text="Pipeline d'Enrichissement",
            font=ctk.CTkFont(size=11),
            text_color="#6C8EAD",
        ).pack(anchor="w")

        self._separator(sidebar, row=1)

        # ---- Source de données ----
        self._build_source_panel(sidebar, start_row=2)

        self._separator(sidebar, row=6)

        # ---- Étapes ----
        self._build_steps_panel(sidebar, start_row=7)

        self._separator(sidebar, row=13)

        # ---- Boutons d'action ----
        self._build_action_panel(sidebar, start_row=14)

        # ---- Statut (épinglé en bas) ----
        self._build_status_badge(sidebar, row=99)

    def _separator(self, parent: ctk.CTkFrame, row: int) -> None:
        """Ligne de séparation horizontale dans la sidebar."""
        ctk.CTkFrame(parent, height=1, fg_color="#2A3A4A").grid(
            row=row, column=0, sticky="ew", padx=16, pady=4
        )

    def _build_source_panel(self, parent: ctk.CTkFrame, start_row: int) -> None:
        """Paneau 'Source de données' dans la sidebar."""
        ctk.CTkLabel(
            parent,
            text="SOURCE DE DONNÉES",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color="#6C8EAD",
        ).grid(row=start_row, column=0, sticky="w", padx=16, pady=(8, 4))

        # Radio buttons
        for i, (value, label) in enumerate([("csv", "Fichier CSV"), ("sqlserver", "SQL Server")]):
            ctk.CTkRadioButton(
                parent,
                text=label,
                variable=self._data_source_var,
                value=value,
                command=self._on_source_change,
                font=ctk.CTkFont(size=12),
            ).grid(row=start_row + 1 + i, column=0, sticky="w", padx=20, pady=2)

        # Bouton Parcourir
        self._browse_button = ctk.CTkButton(
            parent,
            text="📂  Parcourir…",
            height=32,
            font=ctk.CTkFont(size=12),
            fg_color="#1E3A5F",
            hover_color="#2A5080",
            command=self._browse_csv,
        )
        self._browse_button.grid(row=start_row + 3, column=0, sticky="ew", padx=16, pady=(6, 2))

        # Champ chemin CSV (lecture seule, mise à jour programmatique)
        self._csv_entry = ctk.CTkEntry(
            parent,
            textvariable=self._csv_path_var,
            placeholder_text="Aucun fichier sélectionné",
            font=ctk.CTkFont(size=10),
            height=28,
            state="disabled",
        )
        self._csv_entry.grid(row=start_row + 4, column=0, sticky="ew", padx=16, pady=(0, 4))

    def _build_steps_panel(self, parent: ctk.CTkFrame, start_row: int) -> None:
        """Paneau 'Étapes du pipeline' dans la sidebar."""
        ctk.CTkLabel(
            parent,
            text="ÉTAPES DU PIPELINE",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color="#6C8EAD",
        ).grid(row=start_row, column=0, sticky="w", padx=16, pady=(8, 4))

        for i, (key, label) in enumerate(_STEP_LABELS.items()):
            ctk.CTkCheckBox(
                parent,
                text=f"{_STEP_NUMBERS[key]}.  {label}",
                variable=self._step_vars[key],
                font=ctk.CTkFont(size=12),
                checkbox_width=18,
                checkbox_height=18,
            ).grid(row=start_row + 1 + i, column=0, sticky="w", padx=20, pady=3)

    def _build_action_panel(self, parent: ctk.CTkFrame, start_row: int) -> None:
        """Boutons Lancer + Ouvrir résultats."""
        self._run_button = ctk.CTkButton(
            parent,
            text="▶   Lancer le Pipeline",
            height=42,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#1565C0",
            hover_color="#1976D2",
            command=self._run_pipeline,
        )
        self._run_button.grid(row=start_row, column=0, sticky="ew", padx=16, pady=(8, 4))

        self._open_button = ctk.CTkButton(
            parent,
            text="📁   Ouvrir les Résultats",
            height=36,
            font=ctk.CTkFont(size=12),
            fg_color="#1B2B3A",
            hover_color="#243447",
            command=self._open_output_folder,
        )
        self._open_button.grid(row=start_row + 1, column=0, sticky="ew", padx=16, pady=(0, 4))

    def _build_status_badge(self, parent: ctk.CTkFrame, row: int) -> None:
        """Badge de statut épinglé en bas de la sidebar."""
        status_frame = ctk.CTkFrame(parent, fg_color="#0D1B2A", corner_radius=8)
        status_frame.grid(row=row, column=0, sticky="ew", padx=16, pady=16)

        self._status_dot = ctk.CTkLabel(
            status_frame,
            text="●",
            font=ctk.CTkFont(size=14),
            text_color="#4CC98A",
        )
        self._status_dot.pack(side="left", padx=(10, 4), pady=8)

        self._status_label = ctk.CTkLabel(
            status_frame,
            text="Prêt",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#CDD9E5",
        )
        self._status_label.pack(side="left", pady=8)

        ctk.CTkLabel(
            status_frame,
            text=f"v{self.APP_VERSION}",
            font=ctk.CTkFont(size=10),
            text_color="#3A5068",
        ).pack(side="right", padx=10, pady=8)

    # ====================================================================
    # ZONE PRINCIPALE
    # ====================================================================

    def _build_main_area(self) -> None:
        """Zone centrale : barre de progression + console de log pleine hauteur."""
        main = ctk.CTkFrame(self, corner_radius=0, fg_color="#0D1B2A")
        main.grid(row=0, column=1, sticky="nsew", padx=(2, 0))
        main.grid_rowconfigure(1, weight=1)    # console prend tout l'espace vertical
        main.grid_columnconfigure(0, weight=1)

        # ---- Barre de progression ----
        progress_frame = ctk.CTkFrame(main, fg_color="#111E2C", corner_radius=8)
        progress_frame.grid(row=0, column=0, sticky="ew", padx=16, pady=(14, 8))
        progress_frame.grid_columnconfigure(0, weight=1)

        self._step_label = ctk.CTkLabel(
            progress_frame,
            text="En attente de démarrage…",
            font=ctk.CTkFont(size=12),
            text_color="#6C8EAD",
            anchor="w",
        )
        self._step_label.grid(row=0, column=0, sticky="ew", padx=14, pady=(10, 4))

        self._progress_bar = ctk.CTkProgressBar(
            progress_frame,
            height=10,
            progress_color="#1976D2",
            fg_color="#1A2D40",
        )
        self._progress_bar.set(0)
        self._progress_bar.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 10))

        # ---- Console de log ----
        console_frame = ctk.CTkFrame(main, fg_color="#111E2C", corner_radius=8)
        console_frame.grid(row=1, column=0, sticky="nsew", padx=16, pady=(0, 14))
        console_frame.grid_rowconfigure(1, weight=1)
        console_frame.grid_columnconfigure(0, weight=1)

        # En-tête de la console
        header = ctk.CTkFrame(console_frame, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 4))

        ctk.CTkLabel(
            header,
            text="CONSOLE  /  OUTPUT",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color="#5B9BD5",
        ).pack(side="left")

        ctk.CTkButton(
            header,
            text="⌫  Effacer",
            width=80,
            height=24,
            font=ctk.CTkFont(size=10),
            fg_color="#1B2B3A",
            hover_color="#243447",
            command=self._clear_log,
        ).pack(side="right")

        # Widget tk.Text — CustomTkinter ne supporte pas la coloration par tag
        self._log_text = tk.Text(
            console_frame,
            state="disabled",
            wrap="word",
            bg="#0A1520",
            fg=_LOG_COLORS["INFO"],
            font=_CONSOLE_FONT,
            relief="flat",
            borderwidth=0,
            selectbackground="#1E3A5F",
            insertbackground="#5B9BD5",
            padx=10,
            pady=8,
            cursor="arrow",
        )
        self._log_text.grid(row=1, column=0, sticky="nsew", padx=2, pady=(0, 2))

        # Scrollbar
        scrollbar = ctk.CTkScrollbar(console_frame, command=self._log_text.yview)
        scrollbar.grid(row=1, column=1, sticky="ns", pady=(0, 2))
        self._log_text.configure(yscrollcommand=scrollbar.set)

        # Tags de couleur par niveau
        for level, color in _LOG_COLORS.items():
            self._log_text.tag_config(level, foreground=color)

        # Tag spécial pour les marqueurs de section
        self._log_text.tag_config("SECTION", foreground="#3A6D9A", font=("Consolas", 10))

    # ====================================================================
    # CALLBACKS SIDEBAR
    # ====================================================================

    def _on_source_change(self) -> None:
        """Active/désactive le bouton de sélection CSV selon la source choisie."""
        is_csv = self._data_source_var.get() == "csv"
        state = "normal" if is_csv else "disabled"
        self._browse_button.configure(state=state)

    def _browse_csv(self) -> None:
        """Dialogue de sélection de fichier CSV."""
        path = filedialog.askopenfilename(
            title="Sélectionner le fichier CSV source",
            filetypes=[("Fichiers CSV", "*.csv"), ("Tous les fichiers", "*.*")],
        )
        if path:
            self._csv_path_var.set(path)
            # Met à jour le champ en lecture seule
            self._csv_entry.configure(state="normal")
            self._csv_entry.delete(0, "end")
            self._csv_entry.insert(0, path)
            self._csv_entry.configure(state="disabled")

    def _run_pipeline(self) -> None:
        """Valide les inputs et démarre PipelineRunner dans un thread daemon."""
        if self._pipeline_running:
            return

        selected_steps = [k for k, v in self._step_vars.items() if v.get()]
        if not selected_steps:
            messagebox.showwarning(
                "Aucune étape sélectionnée",
                "Cochez au moins une étape avant de lancer le pipeline."
            )
            return

        data_source = self._data_source_var.get()
        csv_path = self._csv_path_var.get().strip()

        if data_source == "csv" and not csv_path:
            messagebox.showwarning(
                "Fichier manquant",
                "Sélectionnez un fichier CSV source avant de lancer."
            )
            return

        if data_source == "csv" and not Path(csv_path).exists():
            messagebox.showerror(
                "Fichier introuvable",
                f"Le fichier sélectionné n'existe pas :\n{csv_path}"
            )
            return

        # Réinitialisation UI
        self._pipeline_running = True
        self._run_button.configure(state="disabled", text="⏳  En cours…")
        self._progress_bar.set(0)
        self._set_status("En cours…", "#E3A857", "●")

        # Message d'ouverture dans la console
        steps_str = "  ›  ".join(_STEP_LABELS[s] for s in selected_steps)
        self._append_log("SECTION", "─" * 60)
        self._append_log("INFO",    f"  EnrichFlow  —  Démarrage")
        self._append_log("INFO",    f"  Source  : {data_source.upper()}")
        self._append_log("INFO",    f"  Étapes  : {steps_str}")
        self._append_log("SECTION", "─" * 60)

        PipelineRunner(
            steps=selected_steps,
            data_source=data_source,
            csv_path=csv_path if data_source == "csv" else None,
            log_queue=self._log_queue,
            progress_queue=self._progress_queue,
        ).start()

    def _open_output_folder(self) -> None:
        """Ouvre data/output/ dans l'explorateur de fichiers du système."""
        output_dir = _ROOT / "data" / "output"
        output_dir.mkdir(parents=True, exist_ok=True)
        try:
            if sys.platform == "win32":
                os.startfile(str(output_dir))
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(output_dir)])
            else:
                subprocess.Popen(["xdg-open", str(output_dir)])
        except Exception as exc:
            messagebox.showerror("Erreur", f"Impossible d'ouvrir le dossier :\n{exc}")

    def _clear_log(self) -> None:
        """Efface le contenu de la console."""
        self._log_text.configure(state="normal")
        self._log_text.delete("1.0", "end")
        self._log_text.configure(state="disabled")

    # ====================================================================
    # POLLING DES QUEUES (thread principal, toutes les 100 ms)
    # ====================================================================

    def _poll_queues(self) -> None:
        """
        Lit les deux queues et met à jour l'interface graphique.

        Non-bloquant : retour immédiat si les queues sont vides.
        Rappelé automatiquement toutes les 100 ms via Tkinter after().
        """
        # Logs
        try:
            while True:
                level, msg = self._log_queue.get_nowait()
                self._append_log(level, msg)
        except queue.Empty:
            pass

        # Signaux de progression
        try:
            while True:
                self._handle_progress_signal(self._progress_queue.get_nowait())
        except queue.Empty:
            pass

        self.after(100, self._poll_queues)

    # ====================================================================
    # MISES À JOUR DE L'INTERFACE
    # ====================================================================

    def _append_log(self, level: str, message: str) -> None:
        """
        Insère une ligne colorée dans la console.

        Args:
            level  : Clé de couleur — "INFO", "WARNING", "ERROR", "STDOUT", etc.
            message: Texte à afficher (sans saut de ligne final).
        """
        tag = level if level in _LOG_COLORS else "INFO"
        self._log_text.configure(state="normal")
        self._log_text.insert("end", message + "\n", tag)
        self._log_text.see("end")
        self._log_text.configure(state="disabled")

    def _handle_progress_signal(self, signal: tuple) -> None:
        """
        Met à jour la barre de progression et le badge de statut.

        Signaux attendus (depuis PipelineRunner.progress_queue) :
            ("step_start",   step_name, index, total)
            ("step_done",    step_name, success)
            ("pipeline_done", success)
            ("error",        message)
        """
        kind = signal[0]

        if kind == "step_start":
            _, step_name, index, total = signal
            label = _STEP_LABELS.get(step_name, step_name)
            self._progress_bar.set(index / total)
            self._step_label.configure(
                text=f"Étape {index + 1} / {total}  —  {label}…",
                text_color="#CDD9E5",
            )

        elif kind == "step_done":
            _, step_name, success = signal
            label = _STEP_LABELS.get(step_name, step_name)
            if success:
                self._append_log("SUCCESS", f"  ✓  {label}  terminée avec succès")
            else:
                self._append_log("ERROR", f"  ✗  {label}  échouée")

        elif kind == "pipeline_done":
            _, success = signal
            self._pipeline_running = False
            self._run_button.configure(state="normal", text="▶   Lancer le Pipeline")

            if success:
                self._progress_bar.set(1.0)
                self._step_label.configure(
                    text="Pipeline terminé avec succès  ✓",
                    text_color="#4CC98A",
                )
                self._set_status("Terminé", "#4CC98A", "●")
                self._append_log("SECTION", "─" * 60)
                self._append_log("SUCCESS", "  Pipeline EnrichFlow terminé avec succès !")
                self._append_log("INFO",    "  ➜  Résultats disponibles dans  data/output/")
                self._append_log("SECTION", "─" * 60)
            else:
                self._step_label.configure(
                    text="Pipeline terminé avec des erreurs",
                    text_color="#F25C5C",
                )
                self._set_status("Erreur", "#F25C5C", "●")
                self._append_log("ERROR", "  Pipeline terminé avec des erreurs — consultez les logs.")

        elif kind == "error":
            _, message = signal
            self._pipeline_running = False
            self._run_button.configure(state="normal", text="▶   Lancer le Pipeline")
            self._set_status("Erreur critique", "#F25C5C", "●")
            self._append_log("CRITICAL", f"  Erreur critique : {message}")

    def _set_status(self, text: str, color: str, dot: str = "●") -> None:
        """Met à jour le badge de statut en bas de la sidebar."""
        self._status_dot.configure(text=dot, text_color=color)
        self._status_label.configure(text=text)

    # ====================================================================
    # VÉRIFICATION AU DÉMARRAGE
    # ====================================================================

    def _check_env_file(self) -> None:
        """
        Vérifie la présence du fichier .env.

        Sans .env, l'app démarre en mode CSV avec les valeurs par défaut.
        Un message d'avertissement est affiché et logué.
        """
        env_path = _ROOT / ".env"
        if not env_path.exists():
            msg = (
                f"Fichier .env introuvable : {env_path}\n\n"
                "Copiez .env.example en .env et renseignez vos paramètres.\n"
                "L'application démarre en mode CSV par défaut."
            )
            self._append_log("WARNING", f"  ⚠  {msg.splitlines()[0]}")
            self._append_log("INFO",    "  ➜  Copiez .env.example  →  .env")
            messagebox.showwarning("Configuration manquante", msg)
        else:
            try:
                from dotenv import load_dotenv
                load_dotenv(env_path)
                self._append_log("INFO", f"  ✓  Configuration chargée depuis {env_path.name}")
            except ImportError:
                pass

    # ====================================================================
    # FERMETURE PROPRE
    # ====================================================================

    def destroy(self) -> None:
        """Restaure sys.stdout avant de fermer la fenêtre."""
        sys.stdout = self._original_stdout
        super().destroy()
