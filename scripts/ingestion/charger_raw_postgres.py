"""
Chargement des données brutes dans PostgreSQL (schéma raw_airbyte).

Ce script simule ce qu'Airbyte réalise automatiquement lors d'une synchronisation :
il ingère les fichiers CSV sources dans des tables RAW, en ajoutant les colonnes
de métadonnées qu'Airbyte génère nativement (_airbyte_raw_id, _airbyte_emitted_at,
_airbyte_data). Cela permet de travailler avec DBT immédiatement, quelle que soit
la disponibilité de l'interface web Airbyte pour la configuration des connecteurs.

En production, ces tables sont alimentées directement par les connecteurs Airbyte.

Usage :
    python scripts/ingestion/charger_raw_postgres.py
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pandas as pd
import psycopg2
from psycopg2 import sql
from psycopg2.extensions import connection as PgConnection

# --- Configuration de connexion ---
# Lue depuis les variables d'environnement (chargées depuis .env si psycopg2-env dispo)
# Valeurs par défaut pour exécution locale

RACINE_PROJET = Path(__file__).resolve().parents[2]

def charger_env() -> dict:
    """Lire le fichier .env du projet pour extraire les variables de connexion."""
    env = {}
    chemin_env = RACINE_PROJET / ".env"
    if chemin_env.exists():
        for ligne in chemin_env.read_text(encoding="utf-8").splitlines():
            ligne = ligne.strip()
            if ligne and not ligne.startswith("#") and "=" in ligne:
                cle, _, valeur = ligne.partition("=")
                env[cle.strip()] = valeur.strip()
    return env


def ouvrir_connexion() -> PgConnection:
    env = charger_env()
    return psycopg2.connect(
        host="localhost",
        port=int(env.get("DWH_POSTGRES_PORT", "5434")),
        dbname=env.get("DWH_POSTGRES_DB", "weather_dwh"),
        user=env.get("DWH_POSTGRES_USER", "weather_admin"),
        password=env.get("DWH_POSTGRES_PASSWORD", ""),
    )


def creer_schema(conn: PgConnection) -> None:
    """Créer le schéma raw_airbyte s'il n'existe pas."""
    with conn.cursor() as cur:
        cur.execute("CREATE SCHEMA IF NOT EXISTS raw_airbyte;")
    conn.commit()


def charger_table_raw(
    conn: PgConnection,
    nom_table: str,
    df: pd.DataFrame,
    horodatage_ingestion: datetime,
) -> int:
    """
    Créer (ou recréer) une table RAW dans le schéma raw_airbyte et y insérer les données.

    Colonnes ajoutées pour reproduire la convention Airbyte OSS :
      - _airbyte_raw_id        : identifiant unique de l'enregistrement (UUID)
      - _airbyte_emitted_at    : horodatage d'ingestion UTC
      - _airbyte_data          : copie JSON de la ligne source (fidélité totale)

    La colonne _airbyte_data permet aux modèles DBT de staging d'extraire chaque
    champ nommément, exactement comme ils le feraient sur une vraie table Airbyte.
    """
    # Construction de la table RAW avec les colonnes source + métadonnées Airbyte
    colonnes_source = list(df.columns)

    ddl = sql.SQL(
        """
        DROP TABLE IF EXISTS raw_airbyte.{table};
        CREATE TABLE raw_airbyte.{table} (
            _airbyte_raw_id      UUID        NOT NULL DEFAULT gen_random_uuid(),
            _airbyte_emitted_at  TIMESTAMPTZ NOT NULL,
            _airbyte_data        JSONB       NOT NULL
        );
        CREATE INDEX ON raw_airbyte.{table} (_airbyte_emitted_at);
        """
    ).format(table=sql.Identifier(nom_table))

    with conn.cursor() as cur:
        cur.execute(ddl)
    conn.commit()

    # Insertion des lignes en batch
    lignes = []
    for _, row in df.iterrows():
        donnees = {}
        for col in colonnes_source:
            val = row[col]
            # Convertir les types non sérialisables
            if pd.isna(val):
                donnees[col] = None
            elif hasattr(val, "isoformat"):
                donnees[col] = val.isoformat()
            else:
                donnees[col] = val
        lignes.append((
            str(uuid4()),
            horodatage_ingestion,
            json.dumps(donnees, ensure_ascii=False),
        ))

    inserer = sql.SQL(
        "INSERT INTO raw_airbyte.{} (_airbyte_raw_id, _airbyte_emitted_at, _airbyte_data) VALUES (%s, %s, %s)"
    ).format(sql.Identifier(nom_table))

    with conn.cursor() as cur:
        cur.executemany(inserer, lignes)
    conn.commit()

    return len(lignes)


def main() -> None:
    horodatage = datetime.now(tz=timezone.utc)
    conn = ouvrir_connexion()

    print(f"Connexion PostgreSQL établie ({conn.dsn})")
    creer_schema(conn)

    # Sources à ingérer
    sources = [
        ("infoclimat_stations",           RACINE_PROJET / "airbyte/data/infoclimat/infoclimat_stations.csv"),
        ("infoclimat_releves",             RACINE_PROJET / "airbyte/data/infoclimat/infoclimat_releves.csv"),
        ("wunderground_ichtegem",          RACINE_PROJET / "airbyte/data/weather_underground/weather_underground_ichtegem_be.csv"),
        ("wunderground_la_madeleine",      RACINE_PROJET / "airbyte/data/weather_underground/weather_underground_la_madeleine_fr.csv"),
    ]

    for nom_table, chemin_csv in sources:
        df = pd.read_csv(chemin_csv, dtype=str)   # dtype=str : aucune conversion, fidélité maximale
        n = charger_table_raw(conn, nom_table, df, horodatage)
        print(f"  {nom_table:<35} : {n:>5} lignes insérées")

    conn.close()
    print("\nIngestion terminée.")


if __name__ == "__main__":
    main()
