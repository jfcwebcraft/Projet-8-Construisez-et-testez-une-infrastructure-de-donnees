"""
Corrige la configuration de la destination PostgreSQL Airbyte.
Les connecteurs Airbyte tournent avec --network host (mode Docker local),
ils ne peuvent donc pas résoudre le nom de service "postgres_dwh" du réseau
bridge weather_network. On utilise host.docker.internal + le port publié.

Les identifiants sont lus depuis le fichier .env du projet.
"""
import os
from pathlib import Path
import requests


def charger_env() -> dict:
    """Lit le fichier .env à la racine du projet."""
    variables = {}
    chemin_env = Path(__file__).parents[1] / ".env"
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
    env.get("AIRBYTE_BASIC_AUTH_USERNAME", os.environ.get("AIRBYTE_BASIC_AUTH_USERNAME", "")),
    env.get("AIRBYTE_BASIC_AUTH_PASSWORD", os.environ.get("AIRBYTE_BASIC_AUTH_PASSWORD", "")),
)
DESTINATION_ID = "1cf7a26e-4242-47be-a294-c78786df6a57"

resp = requests.post(f"{BASE_URL}/destinations/update", auth=AUTH, json={
    "destinationId": DESTINATION_ID,
    "name": "PostgreSQL Weather DWH",
    "connectionConfiguration": {
        "host": "host.docker.internal",
        "port": int(env.get("DWH_POSTGRES_PORT", "5434")),
        "schema": "raw_airbyte",
        "database": env.get("DWH_POSTGRES_DB", "weather_dwh"),
        "username": env.get("DWH_POSTGRES_USER", "weather_admin"),
        "password": env.get("DWH_POSTGRES_PASSWORD", os.environ.get("DWH_POSTGRES_PASSWORD", "")),
        "ssl_mode": {"mode": "disable"},
        "tunnel_method": {"tunnel_method": "NO_TUNNEL"},
        # Nécessaire car des vues DBT (staging) dépendent des tables RAW déjà
        # créées par notre script d'ingestion initial. Sans CASCADE, le
        # connecteur Postgres v2 (typing & deduping) refuse le DROP TABLE.
        "raw_data_schema": "raw_airbyte",
        "drop_cascade": True,
    },
})
print(resp.status_code)
print(resp.text[:1000])
