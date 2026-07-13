"""
Mise à plat du fichier JSON InfoClimat en un CSV unique.

Ce script prépare les données brutes du réseau InfoClimat pour qu'elles
puissent être lues par le connecteur "File (CSV, JSON, Excel...)" d'Airbyte.
Aucune valeur n'est modifiée : on se contente d'aplatir la structure imbriquée
(stations + relevés horaires) en lignes exploitables, l'objectif étant de
conserver l'intégralité de l'information source dans les tables RAW.

Usage :
    python scripts/extraction/extraire_infoclimat.py
"""

import json
from pathlib import Path

import pandas as pd

RACINE_PROJET = Path(__file__).resolve().parents[2]
FICHIER_SOURCE = RACINE_PROJET / "Données" / (
    "Stations meteorologiques du reseau InfoClimat "
    "(Bergues, Hazebrouck, Armentieres, Lille-Lesquin).json"
)
DOSSIER_SORTIE = RACINE_PROJET / "airbyte" / "data" / "infoclimat"


def charger_source() -> dict:
    with open(FICHIER_SOURCE, "r", encoding="utf-8") as f:
        return json.load(f)


def extraire_stations(donnees: dict) -> pd.DataFrame:
    """Table des métadonnées de stations (référentiel)."""
    lignes = []
    for station in donnees["stations"]:
        licence = station.get("license", {})
        lignes.append({
            "id_station": station["id"],
            "nom_station": station["name"],
            "latitude": station["latitude"],
            "longitude": station["longitude"],
            "altitude_m": station["elevation"],
            "type_station": station["type"],
            "licence": licence.get("license"),
            "licence_url": licence.get("url"),
            "licence_source": licence.get("source"),
            "licence_metadonnees_url": licence.get("metadonnees"),
        })
    return pd.DataFrame(lignes)


def extraire_releves(donnees: dict) -> pd.DataFrame:
    """Table des relevés météo horaires/infra-horaires, toutes stations confondues."""
    lignes = []
    for id_station, releves in donnees["hourly"].items():
        if id_station == "_params":
            continue
        for releve in releves:
            lignes.append(releve)
    return pd.DataFrame(lignes)


def main() -> None:
    donnees = charger_source()

    df_stations = extraire_stations(donnees)
    df_releves = extraire_releves(donnees)

    DOSSIER_SORTIE.mkdir(parents=True, exist_ok=True)

    chemin_stations = DOSSIER_SORTIE / "infoclimat_stations.csv"
    chemin_releves = DOSSIER_SORTIE / "infoclimat_releves.csv"

    df_stations.to_csv(chemin_stations, index=False, encoding="utf-8")
    df_releves.to_csv(chemin_releves, index=False, encoding="utf-8")

    print(f"Stations   : {len(df_stations):>6} lignes -> {chemin_stations}")
    print(f"Relevés    : {len(df_releves):>6} lignes -> {chemin_releves}")


if __name__ == "__main__":
    main()
