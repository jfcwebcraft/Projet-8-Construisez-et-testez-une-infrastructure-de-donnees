"""
Consolidation des classeurs Weather Underground (une feuille par jour) en un
CSV unique par station.

Les fichiers sources contiennent une feuille par jour d'octobre 2024, avec les
mêmes 12 colonnes (Time, Temperature, Dew Point, Humidity, Wind, Speed, Gust,
Pressure, Precip. Rate., Precip. Accum., UV, Solar). On concatène les feuilles
en ajoutant une colonne de date déduite du nom de la feuille (format DDMMAA),
sans convertir les unités ni modifier les valeurs : la standardisation des
unités (imperial -> métrique) est faite plus tard, dans la couche staging DBT,
afin de garder les tables RAW strictement fidèles à la source.

Usage :
    python scripts/extraction/extraire_weather_underground.py
"""

from datetime import datetime
from pathlib import Path

import pandas as pd

RACINE_PROJET = Path(__file__).resolve().parents[2]
DOSSIER_DONNEES = RACINE_PROJET / "Données"
DOSSIER_SORTIE = RACINE_PROJET / "airbyte" / "data" / "weather_underground"

FICHIERS_SOURCES = {
    "ichtegem_be": DOSSIER_DONNEES / "Weather+Underground+-+Ichtegem,+BE.xlsx",
    "la_madeleine_fr": DOSSIER_DONNEES / "Weather+Underground+-+La+Madeleine,+FR.xlsx",
}

NOMS_COLONNES = [
    "heure_locale",
    "temperature",
    "point_de_rosee",
    "humidite",
    "direction_vent",
    "vitesse_vent",
    "rafale_vent",
    "pression",
    "taux_precipitation",
    "cumul_precipitation",
    "uv",
    "rayonnement_solaire",
]


def nom_feuille_vers_date(nom_feuille: str) -> str:
    """Convertit un nom de feuille 'DDMMAA' (ex: '011024') en date ISO."""
    return datetime.strptime(nom_feuille, "%d%m%y").strftime("%Y-%m-%d")


def consolider_classeur(chemin_fichier: Path) -> pd.DataFrame:
    classeur = pd.ExcelFile(chemin_fichier)
    tables_journalieres = []

    for nom_feuille in classeur.sheet_names:
        df_jour = pd.read_excel(
            classeur, sheet_name=nom_feuille, skiprows=2, header=None
        )
        if df_jour.empty:
            continue
        df_jour.columns = NOMS_COLONNES
        df_jour.insert(0, "date_releve", nom_feuille_vers_date(nom_feuille))
        tables_journalieres.append(df_jour)

    return pd.concat(tables_journalieres, ignore_index=True)


def main() -> None:
    DOSSIER_SORTIE.mkdir(parents=True, exist_ok=True)

    for identifiant_station, chemin_fichier in FICHIERS_SOURCES.items():
        df_station = consolider_classeur(chemin_fichier)
        df_station.insert(0, "id_station_source", identifiant_station)

        chemin_sortie = DOSSIER_SORTIE / f"weather_underground_{identifiant_station}.csv"
        df_station.to_csv(chemin_sortie, index=False, encoding="utf-8")

        print(f"{identifiant_station:<20} : {len(df_station):>5} lignes -> {chemin_sortie}")


if __name__ == "__main__":
    main()
