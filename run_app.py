"""
Point d'entrée de l'application desktop Pipeline Enrichissement.

Usage :
    python run_app.py

Packaging :
    Ce fichier est le script principal référencé dans pipeline_app.spec.
    PyInstaller le compile en un exécutable standalone (PipelineEnrichissement.exe).
"""

import sys
import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Gestion du chemin de base pour PyInstaller (mode --onefile)
# Après compilation, les ressources sont extraites dans sys._MEIPASS.
# En développement, _ROOT pointe vers le répertoire du projet.
# ---------------------------------------------------------------------------
if getattr(sys, "frozen", False):
    # Exécution depuis l'exe compilé par PyInstaller
    _ROOT = Path(sys._MEIPASS)  # type: ignore[attr-defined]
    # On se place aussi dans le répertoire contenant l'exe pour que les
    # chemins relatifs (data/, .env) pointent au bon endroit
    os.chdir(Path(sys.executable).parent)
else:
    # Exécution depuis le source Python
    _ROOT = Path(__file__).resolve().parent

# S'assure que les imports src/ et gui/ fonctionnent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# ---------------------------------------------------------------------------
# Import et démarrage de la GUI
# ---------------------------------------------------------------------------
from gui.app import PipelineApp


def main() -> None:
    """Lance la fenêtre principale de l'application et entre dans la boucle d'événements."""
    app = PipelineApp()
    app.mainloop()


if __name__ == "__main__":
    main()
