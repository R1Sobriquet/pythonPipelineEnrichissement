# -*- mode: python ; coding: utf-8 -*-
#
# EnrichFlow — Configuration PyInstaller
#
# UTILISATION :
#     pip install pyinstaller customtkinter
#     pyinstaller pipeline_app.spec
#
# RÉSULTAT :
#     dist/EnrichFlow.exe   (Windows)
#     dist/EnrichFlow       (Linux / macOS)
#
# NOTES :
#   - Mode onefile   : tout l'exécutable tient en un seul fichier.
#   - console=False  : aucune fenêtre console noire n'apparaît derrière la GUI.
#   - Les ressources (src/, gui/, data/raw/, .env.example) sont embarquées dans l'exe
#     et extraites dans sys._MEIPASS au démarrage.
#   - À la fermeture, PyInstaller supprime automatiquement le dossier temp.
#
# DÉPENDANCE SYSTÈME (Windows uniquement) :
#   SQL Server nécessite le pilote ODBC installé sur la machine cible :
#   https://learn.microsoft.com/fr-fr/sql/connect/odbc/download-odbc-driver-for-sql-server

import sys
from pathlib import Path

_ROOT = Path(SPECPATH)

# ---------------------------------------------------------------------------
# Analyse des dépendances
# ---------------------------------------------------------------------------
a = Analysis(
    scripts=['run_app.py'],
    pathex=[str(_ROOT)],
    binaries=[],

    # Ressources embarquées : (source, destination_dans_exe)
    datas=[
        (str(_ROOT / 'src'),          'src'),
        (str(_ROOT / 'gui'),          'gui'),
        (str(_ROOT / 'main.py'),      '.'),
        (str(_ROOT / '.env.example'), '.'),
        (str(_ROOT / 'data' / 'raw'), 'data/raw'),
    ],

    # Imports que PyInstaller ne détecte pas par analyse statique
    hiddenimports=[
        # ---- GUI ----
        'customtkinter',
        'customtkinter.windows',
        'customtkinter.windows.widgets',
        'customtkinter.windows.widgets.theme',
        'customtkinter.windows.widgets.core_rendering',
        'tkinter',
        'tkinter.filedialog',
        'tkinter.messagebox',
        '_tkinter',

        # ---- Data science ----
        'pandas',
        'pandas._libs.tslibs.np_datetime',
        'pandas._libs.tslibs.nattype',
        'pandas._libs.tslibs.timedeltas',
        'numpy',
        'numpy.core._multiarray_umath',

        # ---- Machine learning ----
        'sklearn',
        'sklearn.utils._cython_blas',
        'sklearn.neighbors._partition_nodes',
        'sklearn.metrics',
        'sklearn.metrics._pairwise_distances_reduction._datasets_pair',

        # ---- Visualisation (sauvegarde PNG, pas d'affichage interactif) ----
        'matplotlib',
        'matplotlib.pyplot',
        'matplotlib.backends.backend_agg',
        'seaborn',

        # ---- Base de données ----
        'pyodbc',
        'sqlalchemy',
        'sqlalchemy.dialects.mssql',

        # ---- Configuration ----
        'dotenv',
        'python_dotenv',

        # ---- Stats / Science ----
        'statsmodels',
        'statsmodels.tsa',
        'scipy',
        'scipy.special._ufuncs_cxx',
        'scipy.linalg.cython_blas',
        'scipy.linalg.cython_lapack',

        # ---- Validation ----
        'pydantic',
        'pydantic.v1',

        # ---- Utilitaires ----
        'dateutil',
        'tqdm',
    ],

    # Modules exclus pour alléger l'exe final
    excludes=[
        'pytest',
        'pytest_cov',
        'sphinx',
        'black',
        'flake8',
        'IPython',
        'jupyter',
        'notebook',
    ],

    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],

    name='EnrichFlow',          # Nom de l'exécutable final
    console=False,              # Pas de console Windows noire
    upx=True,                   # Compression UPX si disponible (~30 % plus léger)
    upx_exclude=[],
    onefile=True,               # Un seul fichier .exe

    # Personnalisation Windows (décommentez selon vos besoins)
    # icon='assets/enrichflow.ico',   # Icône de l'exe
    version=None,
    uac_admin=False,
)

# ---------------------------------------------------------------------------
# DÉPLOIEMENT
# ---------------------------------------------------------------------------
# 1.  Copier dist/EnrichFlow.exe sur la machine cible
# 2.  Créer un fichier .env dans le même dossier que l'exe
#     (copier .env.example → .env et renseigner les valeurs)
# 3.  Double-cliquer sur EnrichFlow.exe
#
# data/output/ sera créé automatiquement au premier run.
