"""
Script de configuration réelle des connecteurs Airbyte pour le projet Forecast 2.0.

Ce script pilote l'API Airbyte OSS pour :
  1. Récupérer le connecteur source "File" (CSV/JSON/Excel/Parquet)
  2. Créer 4 sources File pointant vers les CSV montés dans /tmp/airbyte_local/
  3. Créer 4 connexions liant chaque source à la destination PostgreSQL existante
  4. Déclencher une synchronisation manuelle pour chaque connexion
  5. Attendre la fin des jobs et afficher le résultat

Objectif : avoir un flux Airbyte réellement fonctionnel (et non un simple script
Python de contournement), conformément aux consignes du projet Forecast 2.0.
"""
import os
from pathlib import Path
import requests
import time
import json

def charger_env() -> dict:
    """Lit le fichier .env à la racine du projet."""
    variables = {}
    chemin_env = Path(__file__).resolve().parents[1] / ".env"
    if chemin_env.exists():
        for ligne in chemin_env.read_text(encoding="utf-8").splitlines():
            ligne = ligne.strip()
            if ligne and not ligne.startswith("#") and "=" in ligne:
                cle, _, valeur = ligne.partition("=")
                variables[cle.strip()] = valeur.strip()
    return variables

env = charger_env()
BASE_URL = f"http://localhost:{env.get('AIRBYTE_WEBAPP_PORT', '8000')}/api/v1"
AUTH = (
    os.getenv("AIRBYTE_BASIC_AUTH_USERNAME", env.get("AIRBYTE_BASIC_AUTH_USERNAME", "airbyte")),
    os.getenv("AIRBYTE_BASIC_AUTH_PASSWORD", env.get("AIRBYTE_BASIC_AUTH_PASSWORD", "password")),
)
HEADERS = {"Content-Type": "application/json"}
WORKSPACE_ID = "c00e1f59-9504-4d96-afc8-ff3ea066aecf"
DESTINATION_ID = "1cf7a26e-4242-47be-a294-c78786df6a57"


# Fichiers CSV disponibles dans le volume Airbyte local (montés via docker-compose)
FILES = [
    {
        "name": "InfoClimat Stations",
        "url": "/local/weather_data/infoclimat/infoclimat_stations.csv",
        "stream_name": "infoclimat_stations",
    },
    {
        "name": "InfoClimat Releves",
        "url": "/local/weather_data/infoclimat/infoclimat_releves.csv",
        "stream_name": "infoclimat_releves",
    },
    {
        "name": "WUnderground Ichtegem",
        "url": "/local/weather_data/weather_underground/weather_underground_ichtegem_be.csv",
        "stream_name": "wunderground_ichtegem",
    },
    {
        "name": "WUnderground La Madeleine",
        "url": "/local/weather_data/weather_underground/weather_underground_la_madeleine_fr.csv",
        "stream_name": "wunderground_la_madeleine",
    },
]


def post(path, payload):
    resp = requests.post(f"{BASE_URL}{path}", auth=AUTH, headers=HEADERS, json=payload)
    if resp.status_code >= 400:
        print(f"[ERREUR] {path} -> {resp.status_code}: {resp.text[:500]}")
        resp.raise_for_status()
    return resp.json()


def get_file_source_definition_id():
    data = post("/source_definitions/list", {"workspaceId": WORKSPACE_ID})
    for d in data["sourceDefinitions"]:
        if d["name"].startswith("File ("):
            return d["sourceDefinitionId"]
    raise RuntimeError("Connecteur source File introuvable")


def main():
    source_def_id = get_file_source_definition_id()
    print(f"Connecteur File trouvé : {source_def_id}")

    created_connections = []

    for f in FILES:
        print(f"\n--- Traitement de {f['name']} ---")

        # 1. Créer la source File
        source = post("/sources/create", {
            "sourceDefinitionId": source_def_id,
            "connectionConfiguration": {
                "dataset_name": f["stream_name"],
                "format": "csv",
                "url": f["url"],
                "provider": {"storage": "local"},
                "reader_options": "{}",
            },
            "workspaceId": WORKSPACE_ID,
            "name": f["name"],
        })
        source_id = source["sourceId"]
        print(f"Source créée : {source_id}")

        # 2. Découvrir le schéma de la source
        schema_resp = post("/sources/discover_schema", {"sourceId": source_id})
        catalog = schema_resp["catalog"]

        # Configurer le stream en mode full_refresh/overwrite (table RAW simple)
        for stream in catalog["streams"]:
            stream["config"]["syncMode"] = "full_refresh"
            stream["config"]["destinationSyncMode"] = "overwrite"

        # 3. Créer la connexion source -> destination PostgreSQL
        connection = post("/connections/create", {
            "sourceId": source_id,
            "destinationId": DESTINATION_ID,
            "syncCatalog": catalog,
            "status": "active",
            "name": f"{f['name']} -> PostgreSQL Weather DWH",
            "namespaceDefinition": "customformat",
            "namespaceFormat": "raw_airbyte",
            "prefix": "",
            "scheduleType": "manual",
        })
        connection_id = connection["connectionId"]
        print(f"Connexion créée : {connection_id}")
        created_connections.append((f["name"], connection_id))

    # 4. Déclencher une synchronisation manuelle pour chaque connexion
    print("\n=== Déclenchement des synchronisations ===")
    job_ids = []
    for name, conn_id in created_connections:
        job = post("/connections/sync", {"connectionId": conn_id})
        job_id = job["job"]["id"]
        job_ids.append((name, job_id))
        print(f"{name} : job {job_id} lancé")

    # 5. Attendre la fin des jobs
    print("\n=== Attente des résultats de synchronisation ===")
    for name, job_id in job_ids:
        for attempt in range(30):
            status_resp = post("/jobs/get", {"id": job_id})
            status = status_resp["job"]["status"]
            if status in ("succeeded", "failed", "cancelled"):
                print(f"{name} : job {job_id} -> {status}")
                break
            time.sleep(3)
        else:
            print(f"{name} : job {job_id} -> timeout (toujours en cours)")

    # Sauvegarder les IDs pour usage ultérieur (captures d'écran, reporting)
    with open("scripts/_airbyte_connections.json", "w", encoding="utf-8") as fp:
        json.dump(
            {"connections": [{"name": n, "connection_id": c} for n, c in created_connections]},
            fp, indent=2
        )

    print("\nConfiguration Airbyte terminée.")


if __name__ == "__main__":
    main()
