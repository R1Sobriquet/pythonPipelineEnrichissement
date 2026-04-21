"""
Module d'exécution du pipeline dans un thread secondaire.

Pourquoi un thread séparé ?
----------------------------
Tkinter (et CustomTkinter) est mono-threadé : si on exécute une opération
longue dans le thread principal, la fenêtre se gèle et ne répond plus aux
clics, redimensionnements, etc.

Solution : `PipelineRunner` hérite de `threading.Thread`.
- La GUI crée une instance et appelle `.start()`.
- Le pipeline tourne dans ce thread secondaire.
- Toute communication vers la GUI passe par deux queues thread-safe :
    - `log_queue`      : messages de log (texte affiché dans la console)
    - `progress_queue` : tuples de progression lus par `_poll_progress_queue`
"""

import threading
import queue
import logging
import sys
import os
from pathlib import Path
from typing import List, Optional


# ---------------------------------------------------------------------------
# Ajout du répertoire racine au chemin Python pour les imports relatifs
# Nécessaire lorsque l'app est lancée depuis run_app.py ou après compilation
# ---------------------------------------------------------------------------
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


logger = logging.getLogger(__name__)


class PipelineRunner(threading.Thread):
    """
    Thread d'exécution du pipeline de données.

    Ce thread orchestre les 4 étapes du pipeline en appelant les mêmes
    fonctions que `main.py` (via import direct), ce qui garantit que le
    comportement est identique entre l'interface CLI et l'interface GUI.

    Signaux envoyés dans `progress_queue` :
        ("step_start",  step_name: str, step_index: int, total: int)
        ("step_done",   step_name: str, success: bool)
        ("pipeline_done", success: bool)
        ("error",       error_message: str)

    Signaux envoyés dans `log_queue` :
        (level: str, message: str)  — via GUILogHandler attaché au root logger
    """

    # Noms des étapes dans l'ordre d'exécution
    ALL_STEPS = ["ingestion", "enrichment", "analysis", "baselines"]

    def __init__(
        self,
        steps: List[str],
        data_source: str,
        csv_path: Optional[str],
        log_queue: queue.Queue,
        progress_queue: queue.Queue,
    ) -> None:
        """
        Initialise le runner avec les paramètres de la session GUI.

        Args:
            steps: Liste des étapes à exécuter (sous-ensemble de ALL_STEPS).
            data_source: Source de données — "csv" ou "sqlserver".
            csv_path: Chemin absolu vers le CSV source (ignoré si data_source="sqlserver").
            log_queue: Queue pour les messages de log destinés à la console GUI.
            progress_queue: Queue pour les signaux de progression de l'UI.
        """
        super().__init__(daemon=True)  # daemon=True : le thread s'arrête avec l'app
        self.steps = steps
        self.data_source = data_source
        self.csv_path = csv_path
        self.log_queue = log_queue
        self.progress_queue = progress_queue

    # ------------------------------------------------------------------
    # Méthode principale du thread
    # ------------------------------------------------------------------

    def run(self) -> None:
        """
        Point d'entrée du thread — exécute les étapes sélectionnées dans l'ordre.

        Pour chaque étape :
        1. Envoie un signal "step_start" pour mettre à jour la barre de progression.
        2. Appelle la fonction correspondante dans `main.py`.
        3. Envoie "step_done" avec le statut succès/échec.
        Si une étape échoue, le pipeline s'arrête (comportement identique au CLI).
        """
        # Injection de la source de données dans l'environnement AVANT l'import
        # Les modules src/ lisent DATA_SOURCE via os.getenv() au moment de l'import
        os.environ["DATA_SOURCE"] = self.data_source
        if self.csv_path:
            os.environ["CSV_FILE_PATH"] = self.csv_path

        # Import différé pour s'assurer que les variables d'env sont positionnées
        try:
            from main import (
                run_ingestion_step,
                run_enrichment_step,
                run_analysis_step,
                run_baselines_step,
            )
        except Exception as exc:
            self.progress_queue.put(("error", str(exc)))
            return

        # Table de dispatch : nom d'étape → fonction
        step_functions = {
            "ingestion":  run_ingestion_step,
            "enrichment": run_enrichment_step,
            "analysis":   run_analysis_step,
            "baselines":  run_baselines_step,
        }

        total = len(self.steps)
        overall_success = True

        for index, step_name in enumerate(self.steps):
            # Signal de démarrage de l'étape → mise à jour barre de progression
            self.progress_queue.put(("step_start", step_name, index, total))

            step_fn = step_functions.get(step_name)
            if step_fn is None:
                logger.warning(f"Étape inconnue ignorée : {step_name}")
                continue

            try:
                success = step_fn()
            except Exception as exc:
                logger.error(f"Exception non interceptée dans l'étape '{step_name}' : {exc}")
                success = False

            self.progress_queue.put(("step_done", step_name, success))

            if not success:
                # On stoppe le pipeline dès la première étape en échec
                overall_success = False
                break

        # Signal de fin du pipeline complet
        self.progress_queue.put(("pipeline_done", overall_success))
