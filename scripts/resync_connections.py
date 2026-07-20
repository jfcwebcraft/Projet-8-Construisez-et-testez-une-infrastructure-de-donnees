import os
from pathlib import Path
import requests
import json
import time

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
    env.get("AIRBYTE_BASIC_AUTH_USERNAME", "airbyte"),
    env.get("AIRBYTE_BASIC_AUTH_PASSWORD", "change_me"),
)


with open("scripts/_airbyte_connections.json", encoding="utf-8") as f:
    connections = json.load(f)["connections"]

# Lancement séquentiel (une sync à la fois) pour éviter la race condition
# sur la création du schéma airbyte_internal lorsque plusieurs connecteurs
# de destination démarrent en même temps.
for c in connections:
    resp = requests.post(f"{BASE_URL}/connections/sync", auth=AUTH,
                          json={"connectionId": c["connection_id"]})
    resp.raise_for_status()
    job_id = resp.json()["job"]["id"]
    print(f"{c['name']} : job {job_id} lancé")

    for _ in range(60):
        r = requests.post(f"{BASE_URL}/jobs/get", auth=AUTH, json={"id": job_id})
        status = r.json()["job"]["status"]
        if status in ("succeeded", "failed", "cancelled"):
            print(f"{c['name']} : job {job_id} -> {status}")
            break
        time.sleep(3)
    else:
        print(f"{c['name']} : job {job_id} -> toujours en cours")
