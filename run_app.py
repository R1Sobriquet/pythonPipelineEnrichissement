"""
EnrichFlow — Point d'entrée de l'application desktop.

Usage :
    python run_app.py

Packaging :
    Ce fichier est le script principal référencé dans pipeline_app.spec.
    PyInstaller le compile en un exécutable standalone (EnrichFlow.exe).
"""

import sys
import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Gestion du chemin de base pour PyInstaller (mode --onefile)
# Après compilation, les ressources sont extraites dans sys._MEIPASS.
# En développement, _ROOT pointe vers le répertoire racine du projet.
# ---------------------------------------------------------------------------
if getattr(sys, "frozen", False):
    # Exécution depuis l'exe compilé par PyInstaller
    _ROOT = Path(sys._MEIPASS)  # type: ignore[attr-defined]
    # On se place dans le répertoire de l'exe pour que data/ et .env soient trouvés
    os.chdir(Path(sys.executable).parent)
else:
    # Exécution depuis les sources Python
    _ROOT = Path(__file__).resolve().parent

# S'assure que les packages src/ et gui/ sont importables
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# ---------------------------------------------------------------------------
# Import et démarrage de la GUI
# ---------------------------------------------------------------------------
from gui.app import EnrichFlowApp


def main() -> None:
    """Lance la fenêtre principale EnrichFlow et entre dans la boucle d'événements."""
    app = EnrichFlowApp()
    app.mainloop()


if __name__ == "__main__":
    main()
