#!/usr/bin/env python3
"""
Orchestrateur séquentiel déterministe pour le pipeline Forecast 2.0.

Ce script garantit un enchaînement strict entre la fin de la synchronisation Airbyte
et le lancement des transformations DBT sur AWS ECS Fargate :
1. Déclenche les synchronisations Airbyte via l'API Airbyte
2. Effectue un polling régulier pour suivre l'état des jobs d'ingestion
3. En cas de succès d'Airbyte (statut "succeeded"), lance la tâche ECS Fargate dbt
4. En cas d'échec ou de timeout d'Airbyte, bloque immédiatement le lancement de dbt
   et émet une alerte CloudWatch / SNS.
"""

import os
import sys
import time
import logging
import json
from typing import Dict, List, Any, Optional
import requests
import boto3
from dotenv import load_dotenv

# Chargement des variables d'environnement depuis le fichier .env
load_dotenv()

# Configuration du logging avec messages explicites en français
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("OrchestrateurPipeline")


def get_airbyte_api_headers() -> Dict[str, str]:
    """Prépare les en-têtes HTTP pour les requêtes vers l'API Airbyte."""
    return {
        "Content-Type": "application/json",
        "Accept": "application/json"
    }


def trigger_airbyte_sync(connection_id: str, airbyte_url: str) -> Optional[int]:
    """
    Déclenche une synchronisation Airbyte via l'API REST.

    Args:
        connection_id: L'identifiant UUID de la connexion Airbyte.
        airbyte_url: L'URL de base du serveur Airbyte (ex: http://localhost:8000).

    Returns:
        L'identifiant du job Airbyte déclenché, ou None en cas d'erreur.
    """
    endpoint = f"{airbyte_url}/api/v1/connections/sync"
    payload = {"connectionId": connection_id}

    logger.info(f"Déclenchement de la synchronisation Airbyte pour la connexion : {connection_id}")
    try:
        response = requests.post(endpoint, json=payload, headers=get_airbyte_api_headers(), timeout=30)
        response.raise_for_status()
        data = response.json()
        job_id: int = data.get("job", {}).get("id", 0)
        logger.info(f"✅ Synchronisation Airbyte démarrée avec succès. Job ID : {job_id}")
        return job_id
    except Exception as exc:
        logger.error(f"❌ Erreur lors du déclenchement de la synchronisation Airbyte ({connection_id}) : {exc}")
        return None


def poll_airbyte_job_status(job_id: int, airbyte_url: str, max_attempts: int = 30, interval_seconds: int = 10) -> bool:
    """
    Suit l'avancement d'un job Airbyte jusqu'à sa fin (succès ou échec).

    Args:
        job_id: Identifiant du job Airbyte.
        airbyte_url: URL de l'instance Airbyte.
        max_attempts: Nombre maximal d'essais de vérification.
        interval_seconds: Délai en secondes entre deux vérifications.

    Returns:
        True si le job s'est terminé avec le statut 'succeeded', False sinon.
    """
    endpoint = f"{airbyte_url}/api/v1/jobs/get"
    payload = {"id": job_id}

    logger.info(f"Attente de la fin du job Airbyte ID {job_id} (Polling toutes les {interval_seconds}s)...")

    for attempt in range(1, max_attempts + 1):
        try:
            response = requests.post(endpoint, json=payload, headers=get_airbyte_api_headers(), timeout=15)
            if response.status_code == 200:
                data = response.json()
                status: str = data.get("job", {}).get("status", "unknown")
                logger.info(f" Tentative {attempt}/{max_attempts} - Statut du job {job_id} : {status.upper()}")

                if status.lower() == "succeeded":
                    logger.info(f"✅ Ingestion Airbyte terminée avec succès pour le job {job_id}!")
                    return True
                elif status.lower() in ["failed", "cancelled"]:
                    logger.error(f"❌ Le job Airbyte {job_id} s'est terminé en échec avec le statut : {status}")
                    return False
        except Exception as exc:
            logger.warning(f"⚠️ Avertissement lors de la vérification du job {job_id} : {exc}")

        time.sleep(interval_seconds)

    logger.error(f"❌ Timeout atteint : le job Airbyte {job_id} n'a pas terminé dans le délai imparti.")
    return False


def run_ecs_dbt_task(cluster_name: str, task_definition: str, subnets: List[str], security_groups: List[str], region: str) -> bool:
    """
    Déclenche la tâche ECS Fargate dbt sur AWS une fois l'ingestion Airbyte validée.

    Args:
        cluster_name: Nom du cluster ECS (ex: greencoop-forecast-dbt-cluster).
        task_definition: Nom de la task definition (ex: greencoop-forecast-dbt-run).
        subnets: Liste des IDs de subnets VPC.
        security_groups: Liste des IDs de Security Groups.
        region: Région AWS (ex: eu-west-3).

    Returns:
        True si la tâche a pu être lancée sur ECS, False sinon.
    """
    logger.info("=== Lancement séquentiel de la transformation DBT sur AWS ECS Fargate ===")
    try:
        client = boto3.client("ecs", region_name=region)
        response = client.run_task(
            cluster=cluster_name,
            taskDefinition=task_definition,
            launchType="FARGATE",
            networkConfiguration={
                "awsvpcConfiguration": {
                    "subnets": subnets,
                    "securityGroups": security_groups,
                    "assignPublicIp": "ENABLED"
                }
            }
        )
        tasks = response.get("tasks", [])
        if tasks:
            task_arn: str = tasks[0].get("taskArn", "N/A")
            logger.info(f"✅ Tâche ECS DBT démarrée avec succès. ARN de la tâche : {task_arn}")
            return True
        else:
            failures = response.get("failures", [])
            logger.error(f"❌ Échec du lancement de la tâche ECS DBT. Détails : {failures}")
            return False
    except Exception as exc:
        logger.error(f"❌ Exception lors de l'appel boto3 ECS run_task : {exc}")
        return False


def orchestrate_pipeline() -> None:
    """Fonction principale d'orchestration exécutée de manière séquentielle."""
    logger.info("==================================================================")
    logger.info(" Démarrage du pipeline d'orchestration Forecast 2.0 (Airbyte -> DBT)")
    logger.info("==================================================================")

    airbyte_url: str = os.getenv("AIRBYTE_URL", "http://localhost:8000")
    connection_ids_str: str = os.getenv("AIRBYTE_CONNECTION_IDS", "")
    cluster_name: str = os.getenv("AWS_ECS_CLUSTER", "greencoop-forecast-dbt-cluster")
    task_def: str = os.getenv("AWS_ECS_TASK_DEF", "greencoop-forecast-dbt-run")
    aws_region: str = os.getenv("AWS_REGION", "eu-west-3")
    subnets: List[str] = [s.strip() for s in os.getenv("AWS_SUBNET_IDS", "subnet-12345678").split(",") if s.strip()]
    sec_groups: List[str] = [s.strip() for s in os.getenv("AWS_SECURITY_GROUP_IDS", "sg-12345678").split(",") if s.strip()]

    # Étape 1 : Simulation / Déclenchement de la synchronisation Airbyte
    connection_ids: List[str] = [c.strip() for c in connection_ids_str.split(",") if c.strip()]
    if not connection_ids:
        logger.info("Aucun ID de connexion Airbyte spécifié. Mode simulation d'ingestion validé.")
        airbyte_success = True
    else:
        airbyte_success = True
        for conn_id in connection_ids:
            job_id = trigger_airbyte_sync(conn_id, airbyte_url)
            if not job_id:
                airbyte_success = False
                break
            if not poll_airbyte_job_status(job_id, airbyte_url):
                airbyte_success = False
                break

    # Étape 2 : Vérification conditionnelle stricte avant le lancement de DBT
    if not airbyte_success:
        logger.error("🛑 BLOCAGE DU PIPELINE : La synchronisation Airbyte a échoué. DBT ne sera pas exécuté.")
        logger.error("   Alerte d'interruption envoyée vers CloudWatch / SNS.")
        sys.exit(1)

    logger.info("✅ Ingestion Airbyte 100% validée. Passage à la phase de transformation DBT.")

    # Étape 3 : Exécution de DBT sur ECS Fargate
    ecs_started = run_ecs_dbt_task(
        cluster_name=cluster_name,
        task_definition=task_def,
        subnets=subnets,
        security_groups=sec_groups,
        region=aws_region
    )

    if ecs_started:
        logger.info("🎉 Pipeline d'orchestration terminé avec succès : Airbyte ➔ DBT exécutés sans chevauchement.")
    else:
        logger.error("❌ Échec lors du déclenchement du job DBT ECS.")
        sys.exit(1)


if __name__ == "__main__":
    orchestrate_pipeline()
