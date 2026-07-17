"""
Chargement des données brutes dans PostgreSQL RDS (schéma raw_airbyte),
dans le format produit par le connecteur Airbyte "Destinations V2"
(colonnes typées + _airbyte_raw_id, _airbyte_extracted_at, _airbyte_meta).

Contexte : Airbyte OSS tourne uniquement en local dans ce projet (Docker
Compose), conformément à ce qui est documenté dans le journal de bord.
Ce script reproduit fidèlement le schéma de sortie qu'Airbyte génère
lorsqu'il synchronise vers PostgreSQL, afin de permettre l'exécution du
pipeline DBT complet contre l'instance RDS de production, en cohérence
avec les modèles de staging existants (models/staging/*.sql).

Ce script est conçu pour s'exécuter DANS le VPC AWS (RDS n'est pas
accessible publiquement) : il est packagé dans une tâche ECS Fargate
dédiée, avec le même security group que la tâche DBT.

Variables d'environnement attendues (injectées via ECS + Secrets Manager) :
    AWS_RDS_HOST, AWS_RDS_MASTER_USERNAME, AWS_RDS_MASTER_PASSWORD
"""

import csv
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

import psycopg2
from psycopg2 import sql
from psycopg2.extras import execute_values

DONNEES_DIR = Path("/app/data")

# Définition des colonnes typées par table, alignée sur le schéma réellement
# produit par Airbyte Destinations V2 (cf. audit via \d raw_airbyte.<table>)
TABLES = {
    "infoclimat_stations": {
        "fichier": "infoclimat/infoclimat_stations.csv",
        "colonnes": {
            "id_station": "VARCHAR", "nom_station": "VARCHAR",
            "latitude": "NUMERIC(38,9)", "longitude": "NUMERIC(38,9)",
            "altitude_m": "NUMERIC(38,9)", "type_station": "VARCHAR",
            "licence": "VARCHAR", "licence_source": "VARCHAR",
            "licence_url": "VARCHAR", "licence_metadonnees_url": "VARCHAR",
        },
    },
    "infoclimat_releves": {
        "fichier": "infoclimat/infoclimat_releves.csv",
        "colonnes": {
            "id_station": "VARCHAR", "dh_utc": "VARCHAR",
            "temperature": "NUMERIC(38,9)", "pression": "NUMERIC(38,9)",
            "humidite": "NUMERIC(38,9)", "point_de_rosee": "NUMERIC(38,9)",
            "visibilite": "NUMERIC(38,9)", "vent_moyen": "NUMERIC(38,9)",
            "vent_rafales": "NUMERIC(38,9)", "vent_direction": "NUMERIC(38,9)",
            "pluie_3h": "NUMERIC(38,9)", "pluie_1h": "NUMERIC(38,9)",
            "neige_au_sol": "NUMERIC(38,9)", "nebulosite": "NUMERIC(38,9)",
            "temps_omm": "NUMERIC(38,9)",
        },
    },
    "wunderground_ichtegem": {
        "fichier": "weather_underground/weather_underground_ichtegem_be.csv",
        "colonnes": {
            "id_station_source": "VARCHAR", "date_releve": "VARCHAR",
            "heure_locale": "VARCHAR", "temperature": "VARCHAR",
            "point_de_rosee": "VARCHAR", "humidite": "VARCHAR",
            "direction_vent": "VARCHAR", "vitesse_vent": "VARCHAR",
            "rafale_vent": "VARCHAR", "pression": "VARCHAR",
            "taux_precipitation": "VARCHAR", "cumul_precipitation": "VARCHAR",
            "uv": "NUMERIC(38,9)", "rayonnement_solaire": "VARCHAR",
        },
    },
    "wunderground_la_madeleine": {
        "fichier": "weather_underground/weather_underground_la_madeleine_fr.csv",
        "colonnes": {
            "id_station_source": "VARCHAR", "date_releve": "VARCHAR",
            "heure_locale": "VARCHAR", "temperature": "VARCHAR",
            "point_de_rosee": "VARCHAR", "humidite": "VARCHAR",
            "direction_vent": "VARCHAR", "vitesse_vent": "VARCHAR",
            "rafale_vent": "VARCHAR", "pression": "VARCHAR",
            "taux_precipitation": "VARCHAR", "cumul_precipitation": "VARCHAR",
            "uv": "NUMERIC(38,9)", "rayonnement_solaire": "VARCHAR",
        },
    },
}


def ouvrir_connexion():
    return psycopg2.connect(
        host=os.environ["AWS_RDS_HOST"],
        port=5432,
        dbname="weather_dwh",
        user=os.environ["AWS_RDS_MASTER_USERNAME"],
        password=os.environ["AWS_RDS_MASTER_PASSWORD"],
    )


def creer_table(conn, nom_table: str, colonnes: dict) -> None:
    definitions = ", ".join(f"{col} {typ}" for col, typ in colonnes.items())
    ddl = sql.SQL(
        """
        CREATE SCHEMA IF NOT EXISTS raw_airbyte;
        DROP TABLE IF EXISTS raw_airbyte.{table};
        CREATE TABLE raw_airbyte.{table} (
            _airbyte_raw_id        VARCHAR(36)              NOT NULL,
            _airbyte_extracted_at  TIMESTAMPTZ              NOT NULL,
            _airbyte_generation_id BIGINT,
            _airbyte_meta          JSONB                    NOT NULL,
            {definitions}
        );
        """
    ).format(table=sql.Identifier(nom_table), definitions=sql.SQL(definitions))
    with conn.cursor() as cur:
        cur.execute(ddl)
    conn.commit()


def charger_csv(conn, nom_table: str, chemin_csv: Path, colonnes: dict) -> int:
    horodatage = datetime.now(tz=timezone.utc)
    noms_colonnes = list(colonnes.keys())

    with open(chemin_csv, newline="", encoding="utf-8") as f:
        lecteur = csv.DictReader(f)
        lignes = []
        for row in lecteur:
            valeurs = [row.get(c) or None for c in noms_colonnes]
            lignes.append((
                str(uuid.uuid4()),
                horodatage,
                None,
                "{}",
                *valeurs,
            ))

    colonnes_sql = ["_airbyte_raw_id", "_airbyte_extracted_at",
                    "_airbyte_generation_id", "_airbyte_meta"] + noms_colonnes

    requete = sql.SQL("INSERT INTO raw_airbyte.{table} ({cols}) VALUES %s").format(
        table=sql.Identifier(nom_table),
        cols=sql.SQL(", ").join(sql.Identifier(c) for c in colonnes_sql),
    )

    with conn.cursor() as cur:
        execute_values(cur, requete.as_string(conn), lignes)
    conn.commit()

    return len(lignes)


def main():
    conn = ouvrir_connexion()
    print(f"Connecté à RDS : {os.environ['AWS_RDS_HOST']}")

    total = 0
    for nom_table, config in TABLES.items():
        chemin_csv = DONNEES_DIR / config["fichier"]
        creer_table(conn, nom_table, config["colonnes"])
        n = charger_csv(conn, nom_table, chemin_csv, config["colonnes"])
        print(f"  {nom_table:<30} : {n:>5} lignes chargées")
        total += n

    conn.close()
    print(f"\nChargement terminé : {total} lignes au total dans raw_airbyte (RDS).")


if __name__ == "__main__":
    main()
