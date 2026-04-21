# -*- mode: python ; coding: utf-8 -*-
#
# Fichier de configuration PyInstaller pour l'application Pipeline Enrichissement.
#
# UTILISATION :
#     pip install pyinstaller
#     pyinstaller pipeline_app.spec
#
# RÉSULTAT :
#     dist/PipelineEnrichissement.exe  (Windows)
#     dist/PipelineEnrichissement      (Linux/macOS)
#
# NOTES :
# - Mode --onefile : tout est empaqueté dans un seul exécutable.
# - console=False  : pas de fenêtre console noire derrière la GUI.
# - Les ressources (src/, data/, .env.example) sont copiées dans l'exe
#   et accessibles via sys._MEIPASS à l'exécution.
#
# DÉPENDANCES SYSTÈME (Windows) :
#   Pour la connexion SQL Server, le pilote ODBC doit être installé
#   sur la machine cible (non bundlé dans l'exe) :
#   https://learn.microsoft.com/fr-fr/sql/connect/odbc/download-odbc-driver-for-sql-server

import sys
from pathlib import Path

# Répertoire racine du projet (là où se trouve ce fichier .spec)
_ROOT = Path(SPECPATH)

# ---------------------------------------------------------------------------
# Phase 1 : Analyse des dépendances
# PyInstaller scanne run_app.py et remonte toutes ses dépendances.
# ---------------------------------------------------------------------------
a = Analysis(
    # Script d'entrée de l'application
    scripts=['run_app.py'],

    # Chemins supplémentaires à ajouter au PYTHONPATH pour la résolution
    pathex=[str(_ROOT)],

    binaries=[],

    # Fichiers de données à inclure dans l'exe
    # Format : (source_sur_disque, destination_dans_l_exe)
    datas=[
        # Package source du pipeline (tous les modules src/)
        (str(_ROOT / 'src'), 'src'),
        # Package GUI
        (str(_ROOT / 'gui'), 'gui'),
        # Script principal (main.py contient les fonctions run_*_step)
        (str(_ROOT / 'main.py'), '.'),
        # Modèle de configuration — l'utilisateur le copie en .env
        (str(_ROOT / '.env.example'), '.'),
        # Données d'exemple embarquées (optionnel, facilite le premier lancement)
        (str(_ROOT / 'data' / 'raw'), 'data/raw'),
    ],

    # ---------------------------------------------------------------------------
    # Imports cachés : PyInstaller ne les détecte pas automatiquement
    # car ils sont importés dynamiquement ou via des plugins.
    # ---------------------------------------------------------------------------
    hiddenimports=[
        # GUI
        'customtkinter',
        'customtkinter.windows',
        'customtkinter.windows.widgets',
        'customtkinter.windows.widgets.theme',

        # Tkinter (peut être absent sur certains environnements Linux)
        'tkinter',
        'tkinter.filedialog',
        'tkinter.messagebox',
        '_tkinter',

        # Data science
        'pandas',
        'pandas._libs.tslibs.np_datetime',
        'pandas._libs.tslibs.nattype',
        'pandas._libs.tslibs.timedeltas',
        'numpy',
        'numpy.core._multiarray_umath',

        # Machine learning
        'sklearn',
        'sklearn.utils._cython_blas',
        'sklearn.neighbors._partition_nodes',
        'sklearn.metrics',
        'sklearn.metrics._pairwise_distances_reduction._datasets_pair',

        # Visualisation (généré sur disque, pas affiché dans la GUI)
        'matplotlib',
        'matplotlib.pyplot',
        'matplotlib.backends.backend_agg',  # Backend non-interactif pour la sauvegarde
        'seaborn',

        # Base de données
        'pyodbc',
        'sqlalchemy',

        # Environnement
        'dotenv',
        'python_dotenv',

        # Stats
        'statsmodels',
        'scipy',
        'scipy.special._ufuncs_cxx',
        'scipy.linalg.cython_blas',
        'scipy.linalg.cython_lapack',

        # Validation
        'pydantic',
        'pydantic.v1',

        # Utilitaires
        'dateutil',
        'tqdm',
    ],

    # Fichiers à exclure pour réduire la taille de l'exe
    excludes=[
        'pytest',
        'sphinx',
        'black',
        'flake8',
        'IPython',
        'jupyter',
        'notebook',
    ],

    # Compression du bytecode Python (réduit légèrement la taille)
    noarchive=False,
)

# ---------------------------------------------------------------------------
# Phase 2 : Archive Python (bytecode compressé)
# ---------------------------------------------------------------------------
pyz = PYZ(a.pure)

# ---------------------------------------------------------------------------
# Phase 3 : Construction de l'exécutable
# ---------------------------------------------------------------------------
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],

    # Nom de l'exécutable final (sans .exe, ajouté automatiquement sur Windows)
    name='PipelineEnrichissement',

    # Désactive la console noire Windows derrière la GUI
    # Mettre à True temporairement pour déboguer les erreurs de démarrage
    console=False,

    # Active la compression UPX si disponible (réduit la taille de 30-50%)
    upx=True,
    upx_exclude=[],

    # Mode onefile : tout dans un seul exécutable
    # L'exe extrait ses ressources dans un dossier temp au démarrage
    onefile=True,

    # Informations Windows (optionnel, personnalisez selon vos besoins)
    version=None,     # Fichier de version Windows (.rc) — None = pas de version
    icon=None,        # Remplacez par 'assets/icon.ico' si vous avez une icône

    # Manifest Windows (évite les problèmes UAC)
    uac_admin=False,
)

# ---------------------------------------------------------------------------
# NOTE SUR LE DÉPLOIEMENT
# ---------------------------------------------------------------------------
# Après compilation :
#   1. Copier dist/PipelineEnrichissement.exe sur la machine cible
#   2. Créer un fichier .env dans le même dossier que l'exe
#      (copier .env.example et renseigner les valeurs)
#   3. Double-cliquer sur l'exe pour lancer l'application
#
# Le dossier data/ sera créé automatiquement au premier lancement.
# Les fichiers de résultats (CSV, graphiques) sont générés dans data/output/.
