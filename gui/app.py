"""
Fenêtre principale de l'application Pipeline Enrichissement.

Architecture de la fenêtre :
    ┌─────────────────────────────────────────────────────┐
    │  Titre                                              │
    ├─────────────────────────────────────────────────────┤
    │  SECTION SOURCE  (radio CSV/SQL + sélecteur fichier)│
    ├─────────────────────────────────────────────────────┤
    │  SECTION ÉTAPES  (4 checkboxes)                     │
    ├─────────────────────────────────────────────────────┤
    │  BOUTONS  [Lancer] [Ouvrir résultats]               │
    ├─────────────────────────────────────────────────────┤
    │  BARRE DE PROGRESSION                               │
    ├─────────────────────────────────────────────────────┤
    │  CONSOLE DE LOG (scrollable)        [Effacer]       │
    └─────────────────────────────────────────────────────┘

Threading :
    - Le pipeline tourne dans `PipelineRunner` (threading.Thread).
    - `_poll_queues()` est rappelé toutes les 100 ms via `self.after()`.
    - Les logs et signaux de progression transitent par deux queues.
"""

import os
import sys
import queue
import logging
import subprocess
import tkinter as tk
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
# Thème CustomTkinter
# ---------------------------------------------------------------------------
ctk.set_appearance_mode("dark")       # "dark" | "light" | "system"
ctk.set_default_color_theme("blue")   # "blue" | "green" | "dark-blue"

# Couleurs utilisées dans la console de log selon le niveau
_LOG_COLORS = {
    "DEBUG":    "#888888",
    "INFO":     "#DDDDDD",
    "WARNING":  "#FFA500",
    "ERROR":    "#FF5555",
    "CRITICAL": "#FF0000",
}

# Labels lisibles pour les noms d'étapes
_STEP_LABELS = {
    "ingestion":  "1. Ingestion",
    "enrichment": "2. Enrichissement",
    "analysis":   "3. Analyse",
    "baselines":  "4. Modèles Baseline",
}


class PipelineApp(ctk.CTk):
    """
    Fenêtre principale de l'application.

    Hérite de `ctk.CTk` (équivalent de `tk.Tk` pour CustomTkinter).
    Gère l'ensemble du cycle de vie : construction de l'UI, lancement
    du pipeline, reception des logs et mise à jour de la progression.
    """

    def __init__(self) -> None:
        """
        Construit la fenêtre et initialise toutes les variables internes.
        """
        super().__init__()

        # ----------------------------------------------------------------
        # Configuration de la fenêtre principale
        # ----------------------------------------------------------------
        self.title("Pipeline d'Enrichissement de Données")
        self.geometry("900x700")
        self.minsize(750, 600)

        # ----------------------------------------------------------------
        # Queues de communication inter-threads
        # ----------------------------------------------------------------
        self._log_queue: queue.Queue = queue.Queue()
        self._progress_queue: queue.Queue = queue.Queue()

        # ----------------------------------------------------------------
        # Variables Tkinter (état de l'interface)
        # ----------------------------------------------------------------
        self._data_source_var = tk.StringVar(value="csv")
        self._csv_path_var = tk.StringVar(value="")

        # Une variable BooleanVar par étape du pipeline
        self._step_vars = {
            "ingestion":  tk.BooleanVar(value=True),
            "enrichment": tk.BooleanVar(value=True),
            "analysis":   tk.BooleanVar(value=True),
            "baselines":  tk.BooleanVar(value=True),
        }

        # ----------------------------------------------------------------
        # Construction de l'interface
        # ----------------------------------------------------------------
        self._build_ui()

        # ----------------------------------------------------------------
        # Logging : attache le GUILogHandler au logger racine
        # Les modules src/ utilisent logging.getLogger(__name__), qui
        # remonte automatiquement jusqu'au logger racine.
        # ----------------------------------------------------------------
        self._gui_handler = GUILogHandler(self._log_queue)
        self._gui_handler.setLevel(logging.DEBUG)
        logging.getLogger().setLevel(logging.INFO)
        logging.getLogger().addHandler(self._gui_handler)

        # ----------------------------------------------------------------
        # Vérification de la présence du fichier .env au démarrage
        # ----------------------------------------------------------------
        self._check_env_file()

        # ----------------------------------------------------------------
        # Démarrage du polling des queues (toutes les 100 ms)
        # ----------------------------------------------------------------
        self._poll_queues()

    # ====================================================================
    # Construction de l'interface
    # ====================================================================

    def _build_ui(self) -> None:
        """
        Crée et dispose tous les widgets de la fenêtre.

        La fenêtre est divisée en 6 sections empilées verticalement dans
        un frame scrollable principal.
        """
        # Frame principal avec padding
        self._main_frame = ctk.CTkScrollableFrame(self, corner_radius=0)
        self._main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # Titre de l'application
        ctk.CTkLabel(
            self._main_frame,
            text="Pipeline d'Enrichissement de Données",
            font=ctk.CTkFont(size=20, weight="bold"),
        ).pack(pady=(10, 4))

        ctk.CTkLabel(
            self._main_frame,
            text="Sélectionnez la source, les étapes, puis lancez le pipeline.",
            font=ctk.CTkFont(size=12),
            text_color="gray",
        ).pack(pady=(0, 16))

        self._build_source_section()
        self._build_steps_section()
        self._build_action_buttons()
        self._build_progress_section()
        self._build_log_console()

    def _build_source_section(self) -> None:
        """
        Section "Source de données" : choix CSV ou SQL Server + sélecteur de fichier.
        """
        frame = ctk.CTkFrame(self._main_frame)
        frame.pack(fill="x", padx=4, pady=(0, 8))

        ctk.CTkLabel(frame, text="SOURCE DE DONNÉES",
                     font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", padx=12, pady=(8, 4))

        # Boutons radio CSV / SQL Server
        radio_frame = ctk.CTkFrame(frame, fg_color="transparent")
        radio_frame.pack(fill="x", padx=12, pady=(0, 4))

        ctk.CTkRadioButton(
            radio_frame,
            text="Fichier CSV",
            variable=self._data_source_var,
            value="csv",
            command=self._on_source_change,
        ).pack(side="left", padx=(0, 20))

        ctk.CTkRadioButton(
            radio_frame,
            text="SQL Server",
            variable=self._data_source_var,
            value="sqlserver",
            command=self._on_source_change,
        ).pack(side="left")

        # Ligne de sélection du fichier CSV
        file_frame = ctk.CTkFrame(frame, fg_color="transparent")
        file_frame.pack(fill="x", padx=12, pady=(4, 10))

        self._browse_button = ctk.CTkButton(
            file_frame,
            text="Parcourir...",
            width=110,
            command=self._browse_csv,
        )
        self._browse_button.pack(side="left", padx=(0, 8))

        self._csv_entry = ctk.CTkEntry(
            file_frame,
            textvariable=self._csv_path_var,
            placeholder_text="Chemin vers le fichier CSV source...",
            state="normal",
        )
        self._csv_entry.pack(side="left", fill="x", expand=True)

    def _build_steps_section(self) -> None:
        """
        Section "Étapes du pipeline" : 4 checkboxes (2 × 2).
        """
        frame = ctk.CTkFrame(self._main_frame)
        frame.pack(fill="x", padx=4, pady=(0, 8))

        ctk.CTkLabel(frame, text="ÉTAPES DU PIPELINE",
                     font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", padx=12, pady=(8, 4))

        grid = ctk.CTkFrame(frame, fg_color="transparent")
        grid.pack(fill="x", padx=12, pady=(0, 10))

        steps = list(_STEP_LABELS.items())
        for i, (key, label) in enumerate(steps):
            row, col = divmod(i, 2)
            ctk.CTkCheckBox(
                grid,
                text=label,
                variable=self._step_vars[key],
            ).grid(row=row, column=col, sticky="w", padx=20, pady=4)

    def _build_action_buttons(self) -> None:
        """
        Section "Boutons d'action" : Lancer et Ouvrir résultats.
        """
        frame = ctk.CTkFrame(self._main_frame, fg_color="transparent")
        frame.pack(fill="x", padx=4, pady=(0, 8))

        self._run_button = ctk.CTkButton(
            frame,
            text="▶  Lancer le Pipeline",
            font=ctk.CTkFont(size=14, weight="bold"),
            height=42,
            command=self._run_pipeline,
        )
        self._run_button.pack(side="left", padx=(4, 8), expand=True, fill="x")

        self._open_button = ctk.CTkButton(
            frame,
            text="📁  Ouvrir les Résultats",
            height=42,
            fg_color="gray40",
            hover_color="gray30",
            command=self._open_output_folder,
        )
        self._open_button.pack(side="left", padx=(0, 4), expand=True, fill="x")

    def _build_progress_section(self) -> None:
        """
        Section "Barre de progression" avec label d'étape courante.
        """
        frame = ctk.CTkFrame(self._main_frame)
        frame.pack(fill="x", padx=4, pady=(0, 8))

        self._progress_label = ctk.CTkLabel(
            frame,
            text="Prêt",
            font=ctk.CTkFont(size=12),
            text_color="gray",
        )
        self._progress_label.pack(anchor="w", padx=12, pady=(8, 2))

        self._progress_bar = ctk.CTkProgressBar(frame, height=16)
        self._progress_bar.set(0)
        self._progress_bar.pack(fill="x", padx=12, pady=(0, 10))

    def _build_log_console(self) -> None:
        """
        Section "Console de log" : widget textuel scrollable + bouton Effacer.
        """
        frame = ctk.CTkFrame(self._main_frame)
        frame.pack(fill="both", expand=True, padx=4, pady=(0, 4))

        header = ctk.CTkFrame(frame, fg_color="transparent")
        header.pack(fill="x", padx=12, pady=(8, 4))

        ctk.CTkLabel(header, text="CONSOLE DE LOG",
                     font=ctk.CTkFont(size=13, weight="bold")).pack(side="left")

        ctk.CTkButton(
            header,
            text="Effacer",
            width=80,
            height=28,
            fg_color="gray40",
            hover_color="gray30",
            command=self._clear_log,
        ).pack(side="right")

        # Widget tk.Text pour affichage coloré (CustomTkinter n'a pas de Text colorable)
        self._log_text = tk.Text(
            frame,
            state="disabled",
            wrap="word",
            bg="#1c1c1c",
            fg="#DDDDDD",
            font=("Consolas", 10),
            relief="flat",
            height=16,
        )
        self._log_text.pack(fill="both", expand=True, padx=12, pady=(0, 10))

        # Configuration des tags de couleur par niveau de log
        for level, color in _LOG_COLORS.items():
            self._log_text.tag_config(level, foreground=color)

        # Scrollbar associée
        scrollbar = tk.Scrollbar(self._log_text, command=self._log_text.yview)
        scrollbar.pack(side="right", fill="y")
        self._log_text.configure(yscrollcommand=scrollbar.set)

    # ====================================================================
    # Callbacks utilisateur
    # ====================================================================

    def _on_source_change(self) -> None:
        """
        Active/désactive le sélecteur de fichier CSV selon la source choisie.
        """
        if self._data_source_var.get() == "csv":
            self._browse_button.configure(state="normal")
            self._csv_entry.configure(state="normal")
        else:
            self._browse_button.configure(state="disabled")
            self._csv_entry.configure(state="disabled")

    def _browse_csv(self) -> None:
        """
        Ouvre un dialogue de sélection de fichier CSV et met à jour le champ.
        """
        path = filedialog.askopenfilename(
            title="Sélectionner le fichier CSV source",
            filetypes=[("Fichiers CSV", "*.csv"), ("Tous les fichiers", "*.*")],
        )
        if path:
            self._csv_path_var.set(path)

    def _run_pipeline(self) -> None:
        """
        Valide les entrées utilisateur et démarre `PipelineRunner` dans un thread.

        Vérifications :
        - Au moins une étape sélectionnée.
        - Si source = CSV, un chemin valide doit être fourni.
        """
        selected_steps = [k for k, v in self._step_vars.items() if v.get()]
        if not selected_steps:
            messagebox.showwarning("Aucune étape", "Veuillez sélectionner au moins une étape.")
            return

        data_source = self._data_source_var.get()
        csv_path = self._csv_path_var.get().strip()

        if data_source == "csv" and not csv_path:
            messagebox.showwarning(
                "Fichier manquant",
                "Veuillez sélectionner un fichier CSV source avant de lancer le pipeline.",
            )
            return

        if data_source == "csv" and not Path(csv_path).exists():
            messagebox.showerror("Fichier introuvable",
                                 f"Le fichier suivant n'existe pas :\n{csv_path}")
            return

        # Réinitialisation de l'interface pour le nouveau run
        self._run_button.configure(state="disabled", text="⏳ En cours...")
        self._progress_bar.set(0)
        self._progress_label.configure(text="Démarrage...")
        self._append_log("INFO", "=" * 55)
        self._append_log("INFO", f"  Pipeline lancé — Source : {data_source.upper()}")
        self._append_log("INFO", f"  Étapes : {', '.join(_STEP_LABELS[s] for s in selected_steps)}")
        self._append_log("INFO", "=" * 55)

        # Lancement du thread de pipeline
        runner = PipelineRunner(
            steps=selected_steps,
            data_source=data_source,
            csv_path=csv_path if data_source == "csv" else None,
            log_queue=self._log_queue,
            progress_queue=self._progress_queue,
        )
        runner.start()

    def _open_output_folder(self) -> None:
        """
        Ouvre le dossier data/output/ dans l'explorateur de fichiers du système.
        """
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
        """
        Efface tout le contenu de la console de log.
        """
        self._log_text.configure(state="normal")
        self._log_text.delete("1.0", "end")
        self._log_text.configure(state="disabled")

    # ====================================================================
    # Polling des queues (exécuté dans le thread principal toutes les 100 ms)
    # ====================================================================

    def _poll_queues(self) -> None:
        """
        Lit les queues de log et de progression, met à jour l'interface.

        Cette méthode est rappelée toutes les 100 ms par `after()`.
        Elle ne bloque jamais : si les queues sont vides, elle revient immédiatement.
        """
        # --- Logs ---
        try:
            while True:
                level, msg = self._log_queue.get_nowait()
                self._append_log(level, msg)
        except queue.Empty:
            pass

        # --- Progression ---
        try:
            while True:
                signal = self._progress_queue.get_nowait()
                self._handle_progress_signal(signal)
        except queue.Empty:
            pass

        # Re-schedule dans 100 ms
        self.after(100, self._poll_queues)

    # ====================================================================
    # Méthodes de mise à jour de l'interface
    # ====================================================================

    def _append_log(self, level: str, message: str) -> None:
        """
        Ajoute une ligne colorée dans la console de log.

        Args:
            level: Niveau de log ("INFO", "WARNING", "ERROR", etc.)
            message: Texte à afficher.
        """
        color_tag = level if level in _LOG_COLORS else "INFO"
        self._log_text.configure(state="normal")
        self._log_text.insert("end", message + "\n", color_tag)
        self._log_text.see("end")  # Scroll automatique vers le bas
        self._log_text.configure(state="disabled")

    def _handle_progress_signal(self, signal: tuple) -> None:
        """
        Traite un signal reçu depuis `PipelineRunner` et met à jour la GUI.

        Formats de signal attendus :
            ("step_start",   step_name, index, total)
            ("step_done",    step_name, success)
            ("pipeline_done", success)
            ("error",        message)

        Args:
            signal: Tuple envoyé par `PipelineRunner` dans `progress_queue`.
        """
        kind = signal[0]

        if kind == "step_start":
            _, step_name, index, total = signal
            label = _STEP_LABELS.get(step_name, step_name)
            progress = index / total
            self._progress_bar.set(progress)
            self._progress_label.configure(
                text=f"Étape {index + 1}/{total} — {label}",
                text_color="white",
            )

        elif kind == "step_done":
            _, step_name, success = signal
            label = _STEP_LABELS.get(step_name, step_name)
            if success:
                self._append_log("INFO", f"✅ {label} — terminée avec succès")
            else:
                self._append_log("ERROR", f"❌ {label} — échouée")

        elif kind == "pipeline_done":
            _, success = signal
            self._progress_bar.set(1.0 if success else self._progress_bar.get())
            if success:
                self._progress_label.configure(
                    text="Pipeline terminé avec succès ✓", text_color="#55FF55"
                )
                self._append_log("INFO", "=" * 55)
                self._append_log("INFO", "🎉 PIPELINE TERMINÉ AVEC SUCCÈS")
                self._append_log("INFO", "   → Consultez data/output/ pour les résultats")
                self._append_log("INFO", "=" * 55)
            else:
                self._progress_label.configure(
                    text="Pipeline terminé avec des erreurs", text_color="#FF5555"
                )
                self._append_log("ERROR", "Pipeline terminé avec des erreurs — consultez les logs.")

            # Réactive le bouton "Lancer"
            self._run_button.configure(state="normal", text="▶  Lancer le Pipeline")

        elif kind == "error":
            _, message = signal
            self._append_log("ERROR", f"Erreur critique : {message}")
            self._run_button.configure(state="normal", text="▶  Lancer le Pipeline")
            self._progress_label.configure(text="Erreur — voir la console", text_color="#FF5555")

    # ====================================================================
    # Vérifications au démarrage
    # ====================================================================

    def _check_env_file(self) -> None:
        """
        Vérifie la présence du fichier .env et affiche un avertissement si absent.

        Le fichier .env contient les paramètres sensibles (DB_PASSWORD, etc.).
        Sans lui, l'app fonctionnera en mode CSV avec les valeurs par défaut,
        mais la connexion SQL Server sera impossible.
        """
        env_path = _ROOT / ".env"
        if not env_path.exists():
            messagebox.showwarning(
                "Fichier .env absent",
                f"Le fichier de configuration .env est introuvable :\n{env_path}\n\n"
                "Copiez .env.example en .env et renseignez vos paramètres.\n\n"
                "L'application fonctionne en mode CSV par défaut.",
            )
        else:
            # Charge les variables d'environnement depuis .env
            try:
                from dotenv import load_dotenv
                load_dotenv(env_path)
            except ImportError:
                pass
