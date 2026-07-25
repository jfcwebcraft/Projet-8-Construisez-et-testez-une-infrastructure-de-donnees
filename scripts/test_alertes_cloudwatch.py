#!/usr/bin/env python3
"""
Script de test des alertes CloudWatch SNS — Projet Forecast 2.0 / GreenCoop

Ce script force manuellement une alarme CloudWatch en état ALARM pour
déclencher l'envoi d'une notification email via SNS. Utilisé pour prouver
que la chaîne d'alerte est opérationnelle (point 5 du cahier des charges).

Usage:
    python scripts/test_alertes_cloudwatch.py

Prérequis:
    - AWS CLI configuré avec les bons credentials (eu-west-3)
    - La variable d'environnement AWS_DEFAULT_REGION ou --region définie
"""

import boto3
import time
import logging

# --- Configuration du logger (logs en français comme le reste du projet) ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

# --- Constantes du projet ---
REGION = "eu-west-3"
ALARM_NAME = "greencoop-forecast-dbt-run-failures"
SNS_TOPIC_ARN = "arn:aws:sns:eu-west-3:391701072609:greencoop-forecast-alerts"


def forcer_alarme_en_etat_alarm(client_cw: boto3.client) -> None:
    """Force l'alarme CloudWatch en état ALARM pour déclencher la notification SNS."""
    logger.info(f"Passage de l'alarme '{ALARM_NAME}' en état ALARM...")
    client_cw.set_alarm_state(
        AlarmName=ALARM_NAME,
        StateValue="ALARM",
        StateReason="TEST : démonstration de la chaîne d'alerte CloudWatch → SNS → Email (point 5 du cahier des charges)"
    )
    logger.info("✅ Alarme passée en état ALARM — vérifiez votre boîte email dans les 30 secondes.")


def verifier_etat_alarme(client_cw: boto3.client) -> dict:
    """Récupère l'état actuel de l'alarme et retourne ses détails."""
    response = client_cw.describe_alarms(AlarmNames=[ALARM_NAME])
    alarms = response.get("MetricAlarms", [])
    if not alarms:
        raise ValueError(f"Alarme '{ALARM_NAME}' introuvable dans la région {REGION}")
    return alarms[0]


def restaurer_alarme_en_ok(client_cw: boto3.client) -> None:
    """Remet l'alarme en état OK après le test."""
    logger.info(f"Remise de l'alarme '{ALARM_NAME}' en état OK...")
    client_cw.set_alarm_state(
        AlarmName=ALARM_NAME,
        StateValue="OK",
        StateReason="TEST terminé : remise en état OK après démonstration"
    )
    logger.info("✅ Alarme remise en état OK.")


def main() -> None:
    """Point d'entrée principal : test complet de la chaîne d'alerte."""
    logger.info("=== Test de la chaîne d'alerte CloudWatch → SNS → Email ===")
    logger.info(f"Région AWS    : {REGION}")
    logger.info(f"Alarme testée : {ALARM_NAME}")
    logger.info(f"Topic SNS     : {SNS_TOPIC_ARN}")
    logger.info("")

    # Initialisation du client CloudWatch
    client_cw = boto3.client("cloudwatch", region_name=REGION)

    # Étape 1 : vérifier l'état initial de l'alarme
    etat_initial = verifier_etat_alarme(client_cw)
    logger.info(f"État initial de l'alarme : {etat_initial['StateValue']}")
    logger.info(f"Description              : {etat_initial['AlarmDescription']}")
    logger.info(f"Actions alarm_actions    : {etat_initial.get('AlarmActions', [])}")
    logger.info("")

    # Étape 2 : forcer l'alarme en état ALARM
    forcer_alarme_en_etat_alarm(client_cw)

    # Étape 3 : attendre et vérifier que l'état a changé
    logger.info("Attente de 5 secondes pour laisser AWS propager le changement d'état...")
    time.sleep(5)
    etat_apres = verifier_etat_alarme(client_cw)
    logger.info(f"État après déclenchement : {etat_apres['StateValue']}")
    logger.info(f"Raison                   : {etat_apres['StateReason']}")
    logger.info("")

    # Étape 4 : remise en OK pour ne pas polluer les métriques réelles
    logger.info("Attente de 15 secondes avant remise en OK (laisse le temps de capturer l'email)...")
    time.sleep(15)
    restaurer_alarme_en_ok(client_cw)

    logger.info("")
    logger.info("=== Test terminé. Vérifiez les éléments suivants pour la preuve : ===")
    logger.info("  1. Console CloudWatch → Alarmes → greencoop-forecast-dbt-run-failures")
    logger.info("     Historique d'état : OK → ALARM → OK")
    logger.info("  2. Boîte Gmail : email reçu avec le sujet 'ALARM: greencoop-forecast-dbt-run-failures'")
    logger.info("  3. Console SNS → Topic greencoop-forecast-alerts → Subscriptions : Confirmed")


if __name__ == "__main__":
    main()
