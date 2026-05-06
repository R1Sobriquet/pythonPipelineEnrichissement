# EnrichFlow

**Pipeline d'enrichissement de données de commandes — Application desktop**

EnrichFlow transforme vos fichiers de commandes bruts en datasets enrichis,
prêts pour l'analyse et la modélisation prédictive.
L'interface graphique moderne vous permet de piloter le pipeline en un clic,
de surveiller l'exécution en temps réel et d'exporter les résultats directement.

---

## Fonctionnalités

| Fonctionnalité | Description |
|---|---|
| **Interface graphique** | Fenêtre desktop CustomTkinter, thème sombre professionnel |
| **Source flexible** | Chargement depuis un fichier CSV ou depuis une base SQL Server |
| **Pipeline ETL complet** | 4 étapes : Ingestion › Enrichissement › Analyse › Modèles |
| **Console en temps réel** | Logs colorés par niveau, redirection de stdout intégrée |
| **Export CSV** | Résultats disponibles dans `data/output/` dès la fin du pipeline |
| **Build .exe** | Configuration PyInstaller incluse — distribution sans Python |

---

## Aperçu de l'interface

```
┌────────────────┬─────────────────────────────────────────────────────┐
│  EnrichFlow    │  Étape 2 / 4 — Enrichissement…                      │
│                │  ██████████░░░░░░░░  50 %                           │
│  SOURCE        ├─────────────────────────────────────────────────────┤
│  ○ CSV         │  CONSOLE / OUTPUT                            [⌫]   │
│  ○ SQL Server  │                                                     │
│  [Parcourir]   │  10:00:01  [INFO]    Configuration chargée v        │
│                │  10:00:02  [INFO]    Chargement CSV : 1 671 lignes  │
│  ETAPES        │  10:00:03  [OK]      Ingestion terminée v           │
│  v Ingestion   │  10:00:04  [WARNING] 12 doublons supprimés          │
│  v Enrichiss.  │  10:00:05  [INFO]    Ajout features temporelles…    │
│  v Analyse     │                                                     │
│  v Baselines   │                                                     │
│                │                                                     │
│  [> Lancer]    │                                                     │
│  [Résultats]   │                                                     │
│  Prêt  v1.0    │                                                     │
└────────────────┴─────────────────────────────────────────────────────┘
```

---

## Pipeline de données

Le pipeline transforme les données en 4 étapes séquentielles :

### 1. Ingestion
- Chargement depuis CSV local ou SQL Server (via pyodbc)
- Nettoyage : suppression des doublons, quantités invalides, valeurs nulles
- Agrégation journalière par article
- Complétion : toutes les combinaisons (jour × article) sont créées, jours sans commande = quantité 0
- **Sortie :** `data/processed/commandes_clean.csv`

### 2. Enrichissement
- Variables temporelles : `year`, `month`, `day`, `weekday`, `is_weekend`, `week_number`
- Variables de retard (lag) : quantité J-1, quantité J-7
- Moyennes mobiles : fenêtres 7 jours et 30 jours
- Encodage cyclique sin/cos (saisonnalité annuelle et hebdomadaire)
- **Sortie :** `data/processed/commandes_enriched.csv`

### 3. Analyse
- Graphique des ventes par jour de semaine
- Comparaison weekend vs semaine
- Graphique de ventes quotidiennes par article
- **Sortie :** `data/output/charts/*.png`

### 4. Modèles Baseline
- Entraînement de 7 modèles de référence : Naïf, Moyenne historique, Moyenne mobile (7j/30j), Moyenne par jour de semaine, Saisonnier naïf, Tendance linéaire
- Évaluation : MAE, RMSE, MAPE sur 10 % des données (test)
- **Sortie :** `data/output/baseline_results.csv`

---

## Installation

### Prérequis

- Python **3.10+** (testé sur 3.13)
- Windows 10/11 ou Linux (macOS non testé)
- Pour SQL Server : pilote ODBC 17 installé sur la machine

### Étapes

```bash
# 1. Cloner le dépôt
git clone https://github.com/R1Sobriquet/pythonPipelineEnrichissement.git
cd pythonPipelineEnrichissement

# 2. Créer un environnement virtuel (recommandé)
python -m venv .venv
source .venv/bin/activate        # Linux / macOS
.venv\Scripts\activate           # Windows

# 3. Installer les dépendances
pip install -r requirements.txt

# 4. Configurer l'application
cp .env.example .env
# Éditez .env selon votre environnement (voir section Configuration)

# 5. Lancer l'application
python run_app.py
```

---

## Configuration

Toute la configuration passe par le fichier `.env` placé à la racine du projet.
Copiez `.env.example` en `.env` et renseignez les valeurs.

### Paramètres disponibles

```env
# Source de données : "csv" ou "sqlserver"
DATA_SOURCE=csv

# ---- SQL Server (ignoré si DATA_SOURCE=csv) ----
DB_SERVER=10.147.xx.xxx
DB_NAME=votre_database
DB_USER=votre_utilisateur
DB_PASSWORD=votre_mot_de_passe
DB_DRIVER=ODBC Driver 17 for SQL Server
DB_TIMEOUT=30
DB_DEBUG=false
```

### Mode CSV (défaut)

1. Placez votre fichier CSV dans `data/raw/`
2. Dans l'interface, sélectionnez **Fichier CSV** et cliquez sur **Parcourir...**
3. Format attendu :

```csv
date_ligne_commande,id_article,quantite,ref_article
2024-01-15,3,46,REF003
2024-01-15,5,19,REF005
```

### Mode SQL Server

1. Définissez `DATA_SOURCE=sqlserver` dans `.env`
2. Renseignez les paramètres `DB_*`
3. La table source attendue : `dbo.ligne_commande` avec les colonnes `date_ligne_commande`, `id_article`, `quantite`

---

## Utilisation

### Interface graphique

```bash
python run_app.py
```

1. **Sélectionnez la source** : CSV ou SQL Server
2. **Choisissez le fichier** CSV via *Parcourir...* (mode CSV uniquement)
3. **Cochez les étapes** à exécuter (toutes par défaut)
4. **Cliquez sur Lancer le Pipeline**
5. Suivez la progression dans la console et la barre d'avancement
6. **Cliquez sur Ouvrir les Résultats** pour accéder aux fichiers de sortie

### Interface CLI (maintenue)

```bash
python main.py --step all          # Pipeline complet
python main.py --step ingestion    # Ingestion uniquement
python main.py --step enrichment   # Enrichissement uniquement
python main.py --step analysis     # Analyse et graphiques
python main.py --step baselines    # Entrainement des baselines
python main.py --article 3         # Analyse détaillée de l'article 3
```

---

## Fichiers de sortie

| Fichier | Description |
|---|---|
| `data/processed/commandes_clean.csv` | Données nettoyées (1 ligne / jour / article) |
| `data/processed/commandes_enriched.csv` | Données enrichies (25+ colonnes) |
| `data/output/charts/weekday_analysis.png` | Analyse par jour de semaine |
| `data/output/charts/weekend_comparison.png` | Comparaison weekend / semaine |
| `data/output/charts/article_*_analysis.png` | Ventes par article |
| `data/output/baseline_results.csv` | Classement des modèles baseline |

---

## Build — Créer l'exécutable (.exe)

```bash
# Installer PyInstaller
pip install pyinstaller

# Compiler
pyinstaller pipeline_app.spec

# Résultat
ls dist/
# EnrichFlow.exe  (Windows)
# EnrichFlow      (Linux)
```

### Déploiement sur une machine sans Python

1. Copier `dist/EnrichFlow.exe` sur la machine cible
2. Créer un fichier `.env` dans le même dossier que l'exe
3. Double-cliquer sur `EnrichFlow.exe`

> **Note Windows :** Pour la connexion SQL Server, le pilote
> [ODBC Driver 17](https://learn.microsoft.com/fr-fr/sql/connect/odbc/download-odbc-driver-for-sql-server)
> doit être installé sur la machine cible.

---

## Structure du projet

```
EnrichFlow/
├── run_app.py              # Point d'entrée GUI
├── main.py                 # Orchestrateur CLI
├── requirements.txt        # Dépendances Python
├── .env.example            # Modèle de configuration
├── pipeline_app.spec       # Configuration PyInstaller
│
├── gui/                    # Package interface graphique
│   ├── app.py              # Fenêtre principale (EnrichFlowApp)
│   ├── pipeline_runner.py  # Thread d'exécution du pipeline
│   └── log_handler.py      # Handler logging -> console GUI
│
├── src/                    # Package pipeline ETL
│   ├── data_ingestion.py   # Etape 1 : Ingestion et nettoyage
│   ├── data_processing.py  # Etape 2 : Enrichissement
│   ├── visualization.py    # Etape 3 : Graphiques
│   ├── database_connector.py  # Connecteur SQL Server
│   ├── utils/
│   │   └── config.py       # Configuration centrale
│   └── models/
│       └── baseline.py     # 7 modèles de baseline
│
└── data/
    ├── raw/                # Données source (CSV utilisateur)
    ├── processed/          # Données intermédiaires (générées)
    └── output/             # Résultats finaux (générés)
```

---

## Dépendances principales

| Bibliothèque | Version min | Usage |
|---|---|---|
| `customtkinter` | 5.2.0 | Interface graphique |
| `pandas` | 2.1.0 | Manipulation de données |
| `numpy` | 1.24.0 | Calcul numérique |
| `matplotlib` / `seaborn` | 3.7.0 / 0.12.0 | Visualisations |
| `scikit-learn` | 1.3.0 | Métriques ML |
| `pyodbc` | 5.0.0 | Connexion SQL Server |
| `python-dotenv` | 1.0.0 | Chargement `.env` |
| `pyinstaller` | 6.0.0 | Packaging .exe |

---

## Licence

Projet propriétaire — tous droits réservés.
