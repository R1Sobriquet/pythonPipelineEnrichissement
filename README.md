# 📘 README — Pipeline de Traitement de Données en Python

## 📄 Description du Projet

Ce projet met en place un **pipeline complet de traitement de données en Python**, incluant :

* **Chargement et exploration initiale** des données
* **Nettoyage** (traitement des valeurs manquantes, outliers, formats, duplicats…)
* **Enrichissement** (feature engineering, normalisation, encodage…)
* **Construction de modèles baselines** pour l’analyse et la prédiction
* **Évaluation des performances**
* **Organisation modulaire** pour faciliter l’expérimentation et l’évolution du pipeline

L’objectif est de fournir une base solide permettant :
✔️ de tester rapidement des modèles
✔️ d’industrialiser progressivement le traitement des données
✔️ d’assurer la reproductibilité des analyses

---

## 📁 Structure du Projet

Le contenu exact dépend du dossier extrait, mais la structure habituelle est :

```
project/
│── data/
│   ├── raw/                # Données brutes
│   └── processed/          # Données après nettoyage
│
│── src/
│   ├── preprocessing/      # Scripts de nettoyage & enrichissement
│   ├── models/             # Modèles baselines
│   ├── utils/              # Fonctions utilitaires
│   └── pipeline.py         # Pipeline principal
│
│── notebooks/
│   └── exploration.ipynb   # Analyses exploratoires
│
│── requirements.txt         # Packages nécessaires
│── README.md                # Documentation
```

---

## 🛠️ Installation et Pré-requis

### 1. Cloner ou dézipper le projet

Si vous avez reçu le projet en **fichier .zip** :

### 🔓 Dézipper sous Windows

* Clic droit sur le fichier ZIP
* ➜ *"Extraire tout…"*
* Choisir un dossier
* ➜ *"Extraire"*

### 🔓 Dézipper sous macOS

Double-cliquez simplement sur le fichier `.zip`.

### 🔓 Dézipper sous Linux

```bash
unzip fichier.zip
```

---

## ▶️ Installation des dépendances

Vous devez avoir **Python 3.9+** installé.

### 1. Se placer dans le dossier du projet

```bash
cd nom_du_projet
```

### 2. Créer un environnement virtuel

```bash
python -m venv venv
source venv/bin/activate       # macOS / Linux
venv\Scripts\activate          # Windows
```

### 3. Installer les dépendances

```bash
pip install -r requirements.txt
```

---

## 🚀 Utilisation du Pipeline

### 🧼 1. Nettoyage & préparation

```bash
python src/pipeline.py --step preprocess
```

### 📊 2. Enrichissement (feature engineering)

```bash
python src/pipeline.py --step enrich
```

### 🤖 3. Exécution des modèles baselines

```bash
python src/pipeline.py --step baseline
```

### 📈 4. Génération des métriques

Les résultats sont exportés dans :

```
/results/metrics/
```

---

## 📦 Modèles Baselines Intégrés

* **Régression linéaire**
* **Random Forest**
* **KNN**
* **Decision Tree**
* (variable selon votre zip)

Ces modèles servent de **référence** pour comparer de futurs modèles plus élaborés.

---

## 📚 Technologies utilisées

* **Python**
* pandas, numpy — nettoyage & manipulation de données
* scikit-learn — modèles & métriques
* matplotlib / seaborn — visualisation
* tqdm — progression du pipeline

---

## 🤝 Contribution

Si vous souhaitez améliorer le pipeline :

1. Créez une branche :

```bash
git checkout -b feature/ma_feature
```

2. Committez :

```bash
git commit -m "Ajout d'une nouvelle étape de traitement"
```

3. Proposez une pull request.

---

## 🧾 Licence

Projet librement réutilisable dans un cadre éducatif ou professionnel (selon vos besoins).

---
