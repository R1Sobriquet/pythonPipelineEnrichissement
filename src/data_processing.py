"""
Module d'enrichissement des données de commandes.

Ce module implémente l'étape 1B du projet :
- Enrichissement des données avec variables temporelles
- Ajout de variables explicatives (jour semaine, weekend, etc.)
- Calcul des quantités de la veille (lag features)
- Analyse des patterns saisonniers
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Optional, Dict, List 
import logging
from pathlib import Path

try:
    from .utils import (
        ColumnNames,
        DisplayConfig,
        Messages,
        WEEKDAY_NAMES,
        WEEKEND_DAYS,
        get_file_path
    )
except ImportError:
    from src.utils import (
        ColumnNames,
        DisplayConfig,
        Messages,
        WEEKDAY_NAMES,
        WEEKEND_DAYS,
        get_file_path
    )

# Configuration du logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class DataEnrichmentPipeline:
    """
    Pipeline d'enrichissement des données avec variables temporelles et saisonnières.

    Transforme les données nettoyées en dataset enrichi pour la modélisation.
    """

    def __init__(self, clean_data: Optional[pd.DataFrame] = None):
        """
        Initialise le pipeline d'enrichissement.

        Args:
            clean_data: Données nettoyées (si None, charge depuis le fichier)
        """
        self.clean_data = clean_data
        self.enriched_data = None

    def load_clean_data(self, file_path: Optional[Path] = None) -> pd.DataFrame:
        """
        Charge les données nettoyées depuis un fichier.

        Args:
            file_path: Chemin du fichier (optionnel)

        Returns:
            DataFrame: Données nettoyées chargées
        """
        if self.clean_data is not None:
            return self.clean_data

        file_path = file_path or get_file_path('clean')

        if not file_path.exists():
            raise FileNotFoundError(f"Fichier non trouvé : {file_path}")

        logger.info(f"Chargement des données nettoyées : {file_path}")

        self.clean_data = pd.read_csv(
            file_path,
            parse_dates=[ColumnNames.DATE],
            date_format='%Y-%m-%d'
        )

        logger.info(f"✅ {len(self.clean_data)} lignes chargées")
        return self.clean_data

    def add_temporal_features(self) -> pd.DataFrame:
        """
        Ajoute les variables temporelles aux données.

        Variables ajoutées :
        - year, month, day
        - weekday (0=Lundi, 6=Dimanche)
        - weekday_name
        - is_weekend
        - week_number

        Returns:
            DataFrame: Données avec variables temporelles
        """
        logger.info("📅 Ajout des variables temporelles...")

        if self.clean_data is None:
            self.load_clean_data()

        # Copie des données pour éviter les modifications inattendues
        self.enriched_data = self.clean_data.copy()

        # Variables temporelles de base
        self.enriched_data[ColumnNames.YEAR] = self.enriched_data[ColumnNames.DATE].dt.year
        self.enriched_data[ColumnNames.MONTH] = self.enriched_data[ColumnNames.DATE].dt.month
        self.enriched_data[ColumnNames.DAY] = self.enriched_data[ColumnNames.DATE].dt.day

        # Jour de la semaine (0=Lundi, 6=Dimanche)
        self.enriched_data[ColumnNames.WEEKDAY] = self.enriched_data[ColumnNames.DATE].dt.weekday

        # Nom du jour de la semaine
        self.enriched_data[ColumnNames.WEEKDAY_NAME] = self.enriched_data[ColumnNames.WEEKDAY].map(WEEKDAY_NAMES)

        # Weekend (True/False)
        self.enriched_data[ColumnNames.IS_WEEKEND] = self.enriched_data[ColumnNames.WEEKDAY].isin(WEEKEND_DAYS)

        # Numéro de semaine dans l'année
        self.enriched_data[ColumnNames.WEEK_NUMBER] = self.enriched_data[ColumnNames.DATE].dt.isocalendar().week

        logger.info("✅ Variables temporelles ajoutées")
        logger.info(
            f"   - Période : {self.enriched_data[ColumnNames.DATE].min().date()} à {self.enriched_data[ColumnNames.DATE].max().date()}")
        logger.info(f"   - Jours uniques : {self.enriched_data[ColumnNames.DATE].nunique()}")

        return self.enriched_data

    def add_lag_features(self, lag_days: List[int] = [1]) -> pd.DataFrame:
        """
        Ajoute les variables de retard (quantités des jours précédents).

        Pourquoi des lag features ?
        ----------------------------
        Un modèle de prévision a besoin de savoir ce qui s'est passé avant.
        Si l'article 3 a eu 50 commandes lundi, il est probable qu'il en aura
        aussi mardi (inertie). En ajoutant "quantity_lag_1" (quantité d'hier)
        comme variable d'entrée, on permet au modèle d'exploiter cette inertie.

        Le lag-7 capture la saisonnalité hebdomadaire : la quantité du même
        jour de la semaine précédente est souvent un bon prédicteur.

        Args:
            lag_days: Liste des décalages en jours (par défaut [1] = jour précédent)

        Returns:
            DataFrame: Données avec variables de retard
        """
        logger.info(f"⏮️ Ajout des variables de retard : {lag_days} jour(s)")

        if self.enriched_data is None:
            raise ValueError("Les données doivent être enrichies d'abord")

        # Le tri par article puis par date est OBLIGATOIRE avant d'appliquer shift().
        # Sans tri, shift(1) décalerait sur la ligne précédente du DataFrame, qui
        # pourrait appartenir à un article différent — résultat incohérent.
        self.enriched_data = self.enriched_data.sort_values([
            ColumnNames.ARTICLE_ID,
            ColumnNames.DATE
        ]).reset_index(drop=True)

        for lag in lag_days:
            col_name = f"{ColumnNames.QUANTITY}_lag_{lag}"

            # groupby() garantit que le décalage (shift) reste à l'intérieur
            # de chaque groupe d'article et ne franchit pas la frontière
            # entre deux articles consécutifs dans le DataFrame.
            self.enriched_data[col_name] = (
                self.enriched_data
                .groupby(ColumnNames.ARTICLE_ID)[ColumnNames.QUANTITY]
                .shift(lag)
                .fillna(0)  # Les N premières lignes de chaque article n'ont pas d'historique → 0
                .astype(int)
            )

        # Alias lisible pour quantity_lag_1 (exigence du cahier des charges)
        if 1 in lag_days:
            self.enriched_data[ColumnNames.QUANTITY_PREV_DAY] = self.enriched_data[f"{ColumnNames.QUANTITY}_lag_1"]

        logger.info("✅ Variables de retard ajoutées")

        return self.enriched_data

    def add_rolling_features(self, windows: List[int] = [7, 30]) -> pd.DataFrame:
        """
        Ajoute des moyennes mobiles sur différentes fenêtres.

        Pourquoi des moyennes mobiles ?
        ---------------------------------
        Une moyenne mobile lisse les pics isolés (ex: grosse commande exceptionnelle)
        et révèle la tendance sous-jacente. La fenêtre à 7 jours capture les
        variations hebdomadaires, tandis que la fenêtre à 30 jours capture la
        tendance mensuelle (utile pour détecter une croissance ou une baisse durable).

        Ces features permettent à un modèle ML de savoir si l'article est "en hausse"
        ou "en baisse" sur les dernières semaines, sans se laisser piéger par
        une valeur aberrante ponctuelle.

        Args:
            windows: Liste des fenêtres (en jours) pour les moyennes mobiles

        Returns:
            DataFrame: Données avec moyennes mobiles
        """
        logger.info(f"📊 Ajout des moyennes mobiles : {windows} jours")

        if self.enriched_data is None:
            raise ValueError("Les données doivent être enrichies d'abord")

        for window in windows:
            col_name = f"{ColumnNames.QUANTITY}_rolling_mean_{window}d"

            # transform() applique la fonction à chaque groupe séparément mais
            # retourne un Series alignée sur le DataFrame original, ce qui permet
            # l'assignation directe. min_periods=1 évite les NaN au début de série.
            self.enriched_data[col_name] = (
                self.enriched_data
                .groupby(ColumnNames.ARTICLE_ID)[ColumnNames.QUANTITY]
                .transform(lambda x: x.rolling(window=window, min_periods=1).mean())
                .round(2)
            )

        logger.info("✅ Moyennes mobiles ajoutées")

        return self.enriched_data

    def calculate_weekday_stats(self) -> pd.DataFrame:
        """
        Calcule les statistiques par jour de la semaine.

        Returns:
            DataFrame: Moyennes des ventes par jour de semaine
        """
        if self.enriched_data is None:
            raise ValueError("Les données doivent être enrichies d'abord")

        weekday_stats = (
            self.enriched_data
            .groupby([ColumnNames.WEEKDAY_NAME, ColumnNames.WEEKDAY])[ColumnNames.QUANTITY]
            .agg(['mean', 'sum', 'count'])
            .round(2)
            .reset_index()
            .sort_values(ColumnNames.WEEKDAY)
        )

        # Renommage des colonnes pour plus de clarté
        weekday_stats.columns = ['jour_semaine', 'weekday_num', 'moyenne_quantite', 'total_quantite', 'nb_observations']

        logger.info("📈 Statistiques par jour de semaine calculées")

        return weekday_stats

    def get_weekend_analysis(self) -> Dict:
        """
        Analyse comparative weekend vs semaine.

        Returns:
            dict: Statistiques weekend vs semaine
        """
        if self.enriched_data is None:
            raise ValueError("Les données doivent être enrichies d'abord")

        weekend_stats = self.enriched_data.groupby(ColumnNames.IS_WEEKEND)[ColumnNames.QUANTITY].agg(
            ['mean', 'sum', 'count']).round(2)

        analysis = {
            'semaine': {
                'moyenne': weekend_stats.loc[False, 'mean'],
                'total': weekend_stats.loc[False, 'sum'],
                'observations': weekend_stats.loc[False, 'count']
            },
            'weekend': {
                'moyenne': weekend_stats.loc[True, 'mean'],
                'total': weekend_stats.loc[True, 'sum'],
                'observations': weekend_stats.loc[True, 'count']
            }
        }

        # Ratio weekend/semaine
        analysis['ratio_weekend_vs_semaine'] = round(
            analysis['weekend']['moyenne'] / analysis['semaine']['moyenne'], 2
        )

        return analysis

    def add_seasonal_features(self) -> pd.DataFrame:
        """
        Ajoute des variables saisonnières avancées.

        Returns:
            DataFrame: Données avec variables saisonnières
        """
        logger.info("🌍 Ajout des variables saisonnières...")

        if self.enriched_data is None:
            raise ValueError("Les données doivent être enrichies d'abord")

        # Jour de l'année (1-366)
        self.enriched_data['day_of_year'] = self.enriched_data[ColumnNames.DATE].dt.dayofyear

        # Trimestre
        self.enriched_data['quarter'] = self.enriched_data[ColumnNames.DATE].dt.quarter

        # Début/milieu/fin de mois
        self.enriched_data['is_month_start'] = self.enriched_data[ColumnNames.DAY] <= 5
        self.enriched_data['is_month_middle'] = (self.enriched_data[ColumnNames.DAY] > 10) & (
                    self.enriched_data[ColumnNames.DAY] <= 20)
        self.enriched_data['is_month_end'] = self.enriched_data[ColumnNames.DAY] > 25

        # Encodage cyclique sin/cos — pourquoi pas juste le numéro du jour ?
        # ---------------------------------------------------------------
        # Si on donne le jour de l'année (1–365) comme entier à un modèle,
        # il voit une grande distance entre le 1er janvier (1) et le 31 décembre
        # (365), alors que ces deux jours sont en réalité consécutifs.
        # L'encodage sin/cos projette la variable sur un cercle unitaire :
        # le jour 1 et le jour 365 sont proches sur ce cercle.
        # Même logique pour les jours de semaine (0=Lundi, 6=Dimanche → voisins).
        self.enriched_data['day_of_year_sin'] = np.sin(2 * np.pi * self.enriched_data['day_of_year'] / 365.25)
        self.enriched_data['day_of_year_cos'] = np.cos(2 * np.pi * self.enriched_data['day_of_year'] / 365.25)

        self.enriched_data['weekday_sin'] = np.sin(2 * np.pi * self.enriched_data[ColumnNames.WEEKDAY] / 7)
        self.enriched_data['weekday_cos'] = np.cos(2 * np.pi * self.enriched_data[ColumnNames.WEEKDAY] / 7)

        logger.info("✅ Variables saisonnières ajoutées")

        return self.enriched_data

    def preview_enriched_data(self, n_rows: int = 10, article_id: Optional[int] = None) -> None:
        """
        Affiche un aperçu des données enrichies.

        Args:
            n_rows: Nombre de lignes à afficher
            article_id: ID d'article spécifique (optionnel)
        """
        if self.enriched_data is None:
            raise ValueError("Aucune donnée enrichie disponible")

        data_to_show = self.enriched_data

        if article_id is not None:
            data_to_show = data_to_show[data_to_show[ColumnNames.ARTICLE_ID] == article_id]
            print(f"📋 Aperçu des données pour l'article {article_id} (premières {n_rows} lignes) :")
        else:
            print(f"📋 Aperçu des données enrichies (premières {n_rows} lignes) :")

        print("=" * 100)

        # Sélection des colonnes principales pour l'affichage
        main_cols = [
            ColumnNames.DATE,
            ColumnNames.ARTICLE_ID,
            ColumnNames.QUANTITY,
            ColumnNames.WEEKDAY_NAME,
            ColumnNames.IS_WEEKEND
        ]

        # Ajout de la colonne quantity_prev_day si elle existe
        if ColumnNames.QUANTITY_PREV_DAY in data_to_show.columns:
            main_cols.append(ColumnNames.QUANTITY_PREV_DAY)

        display_data = data_to_show[main_cols].head(n_rows)
        print(display_data.to_string(index=False))

        print("=" * 100)
        print(f"Total des colonnes disponibles : {len(self.enriched_data.columns)}")
        print(
            f"Nouvelles colonnes ajoutées : {[col for col in self.enriched_data.columns if col not in [ColumnNames.DATE, ColumnNames.ARTICLE_ID, ColumnNames.QUANTITY]]}")

    def save_enriched_data(self, output_path: Optional[Path] = None) -> Path:
        """
        Sauvegarde les données enrichies.

        Args:
            output_path: Chemin de sortie (optionnel)

        Returns:
            Path: Chemin du fichier sauvegardé
        """
        if self.enriched_data is None:
            raise ValueError("Aucune donnée enrichie à sauvegarder")

        output_path = output_path or get_file_path('enriched')

        self.enriched_data.to_csv(output_path, index=False, date_format='%Y-%m-%d')
        logger.info(f"💾 Données enrichies sauvegardées : {output_path}")

        return output_path

    def run_full_enrichment(self, save_output: bool = True) -> pd.DataFrame:
        """
        Exécute le pipeline complet d'enrichissement.

        Args:
            save_output: Sauvegarde automatique des résultats

        Returns:
            DataFrame: Données enrichies complètes
        """
        logger.info("🚀 DÉBUT DU PIPELINE D'ENRICHISSEMENT")
        logger.info("=" * 50)
        try:
            # Pipeline d'enrichissement
            self.load_clean_data()
            self.add_temporal_features()
            self.add_lag_features(lag_days=[1, 7])  # Jour précédent + semaine précédente
            self.add_rolling_features(windows=[7, 30])  # Moyennes 7 et 30 jours
            self.add_seasonal_features()

            if save_output:
                self.save_enriched_data()

            logger.info("=" * 50)
            logger.info("✅ PIPELINE D'ENRICHISSEMENT TERMINÉ AVEC SUCCÈS")
            logger.info(f"   📊 {len(self.enriched_data)} lignes enrichies")
            logger.info(f"   📈 {len(self.enriched_data.columns)} colonnes au total")

            return self.enriched_data

        except Exception as e:
            logger.error(f"❌ ERREUR DANS LE PIPELINE : {e}")
            raise

    def get_enrichment_summary(self) -> Dict:
        """
        Retourne un résumé des données enrichies.

        Returns:
            dict: Statistiques et informations sur l'enrichissement
        """
        if self.enriched_data is None:
            return {"error": "Aucune donnée enrichie disponible"}

        # Statistiques générales
        summary = {
            "total_lignes": len(self.enriched_data),
            "total_colonnes": len(self.enriched_data.columns),
            "articles_uniques": self.enriched_data[ColumnNames.ARTICLE_ID].nunique(),
            "periode": {
                "debut": self.enriched_data[ColumnNames.DATE].min(),
                "fin": self.enriched_data[ColumnNames.DATE].max(),
                "nb_jours": self.enriched_data[ColumnNames.DATE].nunique()
            }
        }

        # Analyse par jour de semaine
        weekday_stats = self.calculate_weekday_stats()
        summary["jour_plus_fort"] = weekday_stats.loc[weekday_stats['moyenne_quantite'].idxmax(), 'jour_semaine']
        summary["moyenne_par_jour"] = weekday_stats[['jour_semaine', 'moyenne_quantite']].to_dict('records')

        # Analyse weekend
        summary["analyse_weekend"] = self.get_weekend_analysis()

        return summary


# ===== FONCTIONS UTILITAIRES =====

def quick_enrichment(clean_data_path: str) -> pd.DataFrame:
    """
    Fonction rapide pour l'enrichissement complet des données.

    Args:
        clean_data_path: Chemin vers les données nettoyées

    Returns:
        DataFrame: Données enrichies
    """
    pipeline = DataEnrichmentPipeline()
    return pipeline.run_full_enrichment()


def analyze_article_pattern(enriched_data: pd.DataFrame, article_id: int) -> Dict:
    """
    Analyse les patterns d'un article spécifique.

    Args:
        enriched_data: Données enrichies
        article_id: ID de l'article à analyser

    Returns:
        dict: Analyse des patterns de l'article
    """
    article_data = enriched_data[enriched_data[ColumnNames.ARTICLE_ID] == article_id].copy()

    if article_data.empty:
        return {"error": f"Article {article_id} non trouvé"}

    # Statistiques par jour de semaine pour cet article
    weekday_stats = article_data.groupby(ColumnNames.WEEKDAY_NAME)[ColumnNames.QUANTITY].agg(
        ['mean', 'sum', 'std']).round(2)

    return {
        "article_id": article_id,
        "total_commandes": article_data[ColumnNames.QUANTITY].sum(),
        "moyenne_quotidienne": article_data[ColumnNames.QUANTITY].mean(),
        "jours_avec_commandes": (article_data[ColumnNames.QUANTITY] > 0).sum(),
        "jour_plus_fort": weekday_stats['mean'].idxmax(),
        "stats_par_jour": weekday_stats.to_dict('index')
    }


if __name__ == "__main__":
    # Test du pipeline si exécuté directement
    pipeline = DataEnrichmentPipeline()
    try:
        data = pipeline.run_full_enrichment()
        summary = pipeline.get_enrichment_summary()

        print("\n📊 RÉSUMÉ DE L'ENRICHISSEMENT :")
        print(f"📈 Jour le plus fort : {summary.get('jour_plus_fort', 'Non calculé')}")
        print(
            f"🎯 Ratio weekend/semaine : {summary.get('analyse_weekend', {}).get('ratio_weekend_vs_semaine', 'Non calculé')}")

        # Aperçu des données
        pipeline.preview_enriched_data(n_rows=10)

    except Exception as e:
        print(f"Erreur : {e}")
        print("Assurez-vous que les données nettoyées existent dans data/processed/")