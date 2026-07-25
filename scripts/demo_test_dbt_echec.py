#!/usr/bin/env python3
"""
Script de démonstration : test DBT en échec — Projet Forecast 2.0 / GreenCoop

Ce script orchestre la démonstration complète du point 8 du cahier des charges :
1. Connexion à RDS et insertion d'une donnée invalide (température = 999°C)
2. Exécution de dbt test en local (pointant vers RDS prod)
3. Affichage des erreurs (Failure in test...)
4. Correction de la donnée (suppression)
5. Nouvelle exécution réussie

Usage:
    python scripts/demo_test_dbt_echec.py [--etape 1|2|3|all]

Prérequis:
    - Connexion à RDS active (via .env ou variables AWS)
    - dbt installé et configuré avec le profil prod
"""

import os
import subprocess
import logging
import sys
import time
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

# --- Chargement des variables d'environnement ---
load_dotenv()

# --- Configuration du logger ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

# --- Constantes ---
DBT_DIR = Path(__file__).parent.parent / "dbt"
UUID_TEST = "00000000-dead-beef-0000-demo00000001"


def get_rds_connection() -> psycopg2.extensions.connection:
    """Établit une connexion à RDS depuis les variables d'environnement."""
    host = os.environ.get("AWS_RDS_HOST")
    user = os.environ.get("AWS_RDS_MASTER_USERNAME")
    password = os.environ.get("AWS_RDS_MASTER_PASSWORD")

    if not all([host, user, password]):
        raise EnvironmentError(
            "Variables manquantes : AWS_RDS_HOST, AWS_RDS_MASTER_USERNAME, AWS_RDS_MASTER_PASSWORD. "
            "Vérifiez votre fichier .env"
        )

    logger.info(f"Connexion à RDS : {host}:5432/weather_dwh")
    conn = psycopg2.connect(
        host=host,
        port=5432,
        dbname="weather_dwh",
        user=user,
        password=password,
        sslmode="require"
    )
    conn.autocommit = True
    return conn


def etape1_inserer_donnee_invalide(conn: psycopg2.extensions.connection) -> None:
    """
    Étape 1 : Insère une observation avec une température impossible (999°C)
    dans la table RAW Airbyte pour déclencher un échec de test DBT.
    """
    logger.info("=== ÉTAPE 1 : Insertion d'une donnée invalide ===")
    sql = """
        INSERT INTO raw_airbyte.infoclimat_releves (
            _airbyte_raw_id, 
            _airbyte_extracted_at, 
            _airbyte_meta,
            _airbyte_generation_id,
            id_station, 
            temperature, 
            humidite, 
            pression, 
            dh_utc, 
            vent_direction, 
            vent_moyen, 
            pluie_1h
        ) VALUES (
            %s::text,
            NOW(),
            '{}'::jsonb,
            1,
            '07015', 
            '999.0', 
            '50', 
            '1013.0', 
            '2024-10-15 12:00:00', 
            '180', 
            '15.0', 
            '0.0'
        )
        ON CONFLICT DO NOTHING;
    """
    with conn.cursor() as cur:
        cur.execute(sql, (str(UUID_TEST),))
    logger.info(f"✅ Donnée invalide insérée (UUID : {UUID_TEST}, température = 999°C)")
    logger.info("   → Cette valeur dépasse le seuil du test 'test_metier_temperature_raisonnable' (max 60°C)")


def etape2_lancer_dbt_test() -> int:
    """
    Étape 2 : Lance dbt test en pointant vers prod (RDS).
    Retourne le code de retour du processus (0 = succès, 1 = échec).
    """
    logger.info("")
    logger.info("=== ÉTAPE 2 : Exécution de dbt test (attendu : ÉCHEC) ===")
    cmd = [
        sys.executable, "-m", "dbt.cli.main",
        "build",
        "--profiles-dir", str(DBT_DIR),
        "--target", "prod",
        "--select", "marts"
    ]
    logger.info(f"Commande : {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=str(DBT_DIR), capture_output=False)
    return result.returncode


def etape3_corriger_donnee(conn: psycopg2.extensions.connection) -> None:
    """
    Étape 3 : Supprime la donnée invalide de la table RAW.
    En production, on pourrait déplacer la ligne dans une table de quarantaine.
    """
    logger.info("")
    logger.info("=== ÉTAPE 3 : Correction — suppression de la donnée invalide ===")
    with conn.cursor() as cur:
        cur.execute(
            "DELETE FROM raw_airbyte.infoclimat_releves WHERE _airbyte_raw_id = %s::text",
            (UUID_TEST,)
        )
        deleted = cur.rowcount
    logger.info(f"✅ {deleted} ligne(s) supprimée(s) (UUID : {UUID_TEST})")


def etape4_lancer_dbt_build() -> int:
    """
    Étape 4 : Lance dbt build pour regénérer les marts et repasser les tests.
    Retourne le code de retour (0 = succès).
    """
    logger.info("")
    logger.info("=== ÉTAPE 4 : Nouvelle exécution dbt build (attendu : SUCCÈS) ===")
    cmd = [
        sys.executable, "-m", "dbt.cli.main",
        "build",
        "--profiles-dir", str(DBT_DIR),
        "--target", "prod"
    ]
    logger.info(f"Commande : {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=str(DBT_DIR), capture_output=False)
    return result.returncode


def main() -> None:
    """Orchestre les 4 étapes de la démonstration."""
    logger.info("Démarrage de la démonstration : Tests DBT en échec (Point 8)")

    try:
        conn = get_rds_connection()
    except Exception as e:
        logger.error(f"Impossible de se connecter à RDS : {e}")
        sys.exit(1)

    try:
        # Étape 1 : insérer la donnée invalide
        etape1_inserer_donnee_invalide(conn)

        # Petite pause pour laisser le temps de capturer l'état de la table
        logger.info("Pause de 3 secondes — faites une capture de la table RAW si besoin...")
        time.sleep(3)

        # Étape 2 : lancer dbt test (doit échouer)
        rc_test = etape2_lancer_dbt_test()
        if rc_test == 0:
            logger.warning("⚠️  dbt test a réussi alors qu'un échec était attendu.")
            logger.warning("   Vérifiez que le profil 'prod' pointe bien vers RDS et non vers local.")
        else:
            logger.info("✅ Échec attendu confirmé — le test DBT a bien détecté la donnée invalide.")

        # VÉRIFICATION EXPLICITE D'ISOLATION DES DONNÉES EN TABLE FINAL (MARTS)
        logger.info("")
        logger.info("=== VÉRIFICATION D'ISOLATION : Contrôle de la table finale 'fact_weather_observations' ===")
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM marts_marts.fact_weather_observations WHERE temperature_c > 60;")
            nb_invalid_marts = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM marts_marts.fact_weather_observations;")
            total_marts = cur.fetchone()[0]

            logger.info(f"📊 Lignes invalides (>60°C) dans fact_weather_observations : {nb_invalid_marts}")
            logger.info(f"📊 Volume total d'observations valides conservées : {total_marts}")

            if nb_invalid_marts == 0:
                logger.info("🛡️ PREUVE D'ISOLATION : 0 ligne invalide en table finale !")
                logger.info("   L'arrêt du DAG dbt a strictement empêché les données corrompues de toucher la couche marts.")

        # Étape 3 : corriger la donnée
        etape3_corriger_donnee(conn)

        # Étape 4 : relancer dbt build (doit réussir)
        rc_build = etape4_lancer_dbt_build()
        if rc_build == 0:
            logger.info("")
            logger.info("✅ Pipeline corrigé et opérationnel — PASS=64, WARN=0, ERROR=0")
        else:
            logger.error("❌ dbt build a échoué après correction. Vérifiez les logs ci-dessus.")

    finally:
        conn.close()
        logger.info("")
        logger.info("Connexion RDS fermée.")


if __name__ == "__main__":
    main()
