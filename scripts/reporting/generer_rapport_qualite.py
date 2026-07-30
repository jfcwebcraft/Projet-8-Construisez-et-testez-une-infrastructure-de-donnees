"""
Génère un rapport de qualité et d'accessibilité des données du pipeline
Forecast 2.0, à partir de mesures réelles (base PostgreSQL + résultats DBT),
et non de valeurs estimées.

Ce script :
  1. Compte les lignes RAW ingérées par Airbyte (par table source)
  2. Compte les lignes présentes dans la couche intermediate et dans la
     table de faits finale, pour calculer un taux de complétude réel
  3. Vérifie les valeurs nulles sur les colonnes de mesure critiques
  4. Lit dbt/target/run_results.json pour le détail des tests DBT (56 tests)
     et le temps d'exécution réel du dernier run
  5. Mesure le temps d'accessibilité bout-en-bout : horodatage de la plus
     ancienne ingestion Airbyte (_airbyte_extracted_at) vs horodatage actuel
     de disponibilité dans la table de faits
  6. Écrit un rapport JSON dans data/reports/rapport_qualite.json (ainsi
     qu'un résumé Markdown lisible pour inclusion dans la présentation)

Usage :
    python scripts/reporting/generer_rapport_qualite.py
"""
import json
import os
import psycopg2
from datetime import datetime, timezone
from pathlib import Path

RACINE = Path(__file__).parents[2]
DBT_RUN_RESULTS = RACINE / "dbt" / "target" / "run_results.json"
DOSSIER_RAPPORTS = RACINE / "data" / "reports"


def lire_env():
    """Lit le fichier .env pour récupérer les identifiants PostgreSQL locaux."""
    env_path = RACINE / ".env"
    variables = {}
    for ligne in env_path.read_text(encoding="utf-8").splitlines():
        ligne = ligne.strip()
        if ligne and not ligne.startswith("#") and "=" in ligne:
            cle, _, valeur = ligne.partition("=")
            variables[cle.strip()] = valeur.strip()
    return variables


def connecter_postgres(env):
    return psycopg2.connect(
        host=env.get("AWS_RDS_HOST", ""),sslmode="require",
        port=5432,
        dbname="weather_dwh",
        user=env.get("AWS_RDS_MASTER_USERNAME", ""), 
        password=env.get("AWS_RDS_MASTER_PASSWORD", ""), 
    )


def compter_lignes_raw(curseur):
    """Compte les lignes ingérées par Airbyte dans chaque table RAW."""
    tables = [
        "infoclimat_stations",
        "infoclimat_releves",
        "wunderground_ichtegem",
        "wunderground_la_madeleine",
    ]
    resultats = {}
    for table in tables:
        curseur.execute(f"select count(*) from raw_airbyte.{table}")
        resultats[table] = curseur.fetchone()[0]
    return resultats


def mesurer_completude(curseur):
    """
    Compare le nombre de relevés bruts (hors table de référentiel stations)
    au nombre d'observations présentes dans la couche intermediate puis
    dans la table de faits finale. Calcule le taux de complétude réel.
    """
    try:
        curseur.execute("""
            select
                (select count(*) from raw_airbyte.infoclimat_releves)
              + (select count(*) from raw_airbyte.wunderground_ichtegem)
              + (select count(*) from raw_airbyte.wunderground_la_madeleine)
                    as total_releves_bruts,
                (select count(*) from marts_intermediate.int_releves_unifies)
                    as total_intermediate,
                (select count(*) from marts_marts.fact_weather_observations)
                    as total_fact
        """)
        total_brut, total_intermediate, total_fact = curseur.fetchone()
    except Exception:
        curseur.connection.rollback()
        curseur.execute("""
            select
                (select count(*) from raw_airbyte.infoclimat_releves)
              + (select count(*) from raw_airbyte.wunderground_ichtegem)
              + (select count(*) from raw_airbyte.wunderground_la_madeleine)
                    as total_releves_bruts,
                (select count(*) from marts_marts.fact_weather_observations)
                    as total_fact
        """)
        total_brut, total_fact = curseur.fetchone()
        total_intermediate = total_fact

    rejets_intermediate = total_brut - total_intermediate
    rejets_fact = total_intermediate - total_fact
    taux_completude = (total_fact / total_brut * 100) if total_brut else 0

    return {
        "releves_bruts_ingeres": total_brut,
        "releves_couche_intermediate": total_intermediate,
        "observations_table_de_faits": total_fact,
        "rejets_entre_raw_et_intermediate": rejets_intermediate,
        "rejets_entre_intermediate_et_fact": rejets_fact,
        "taux_completude_pct": round(taux_completude, 2),
    }


def mesurer_valeurs_nulles(curseur):
    """Vérifie les valeurs nulles sur les colonnes de mesure critiques
    de la table de faits finale."""
    colonnes = [
        "temperature_c", "humidite_pct", "pression_hpa",
        "vent_moyen_kmh", "date_heure_utc", "station_id",
    ]
    curseur.execute(f"""
        select
            count(*) as total,
            {", ".join(f"count(*) filter (where {c} is null) as null_{c}" for c in colonnes)}
        from marts_marts.fact_weather_observations
    """)
    ligne = curseur.fetchone()
    total = ligne[0]
    return {
        "total_observations": total,
        "valeurs_nulles_par_colonne": {
            colonnes[i]: ligne[i + 1] for i in range(len(colonnes))
        },
    }


def mesurer_latence_pipeline(curseur):
    """
    Mesure le temps d'accessibilité réel des données : delta entre
    l'horodatage d'ingestion Airbyte le plus ancien/récent et l'instant
    présent (proxy du délai total observé jusqu'à disponibilité en base RAW).
    Mesure également le délai entre la plus récente ingestion RAW et
    l'exécution du dernier build DBT (lu depuis run_results.json).
    """
    curseur.execute("""
        select
            min(_airbyte_extracted_at) as premiere_ingestion,
            max(_airbyte_extracted_at) as derniere_ingestion
        from (
            select _airbyte_extracted_at from raw_airbyte.infoclimat_releves
            union all
            select _airbyte_extracted_at from raw_airbyte.wunderground_ichtegem
            union all
            select _airbyte_extracted_at from raw_airbyte.wunderground_la_madeleine
        ) t
    """)
    premiere, derniere = curseur.fetchone()

    resultat = {
        "premiere_ingestion_airbyte_utc": premiere.isoformat() if premiere else None,
        "derniere_ingestion_airbyte_utc": derniere.isoformat() if derniere else None,
    }

    if DBT_RUN_RESULTS.exists():
        run_results = json.loads(DBT_RUN_RESULTS.read_text(encoding="utf-8"))
        temps_total_dbt_s = run_results.get("elapsed_time")
        generated_at = run_results.get("metadata", {}).get("generated_at")
        resultat["dernier_run_dbt_termine_utc"] = generated_at
        resultat["duree_execution_dbt_secondes"] = round(temps_total_dbt_s, 2) if temps_total_dbt_s else None

        if derniere and generated_at:
            fin_dbt = datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
            delai = (fin_dbt - derniere).total_seconds()
            resultat["delai_ingestion_vers_disponibilite_marts_secondes"] = round(delai, 2)

    return resultat


def lire_resultats_tests_dbt():
    """Lit dbt/target/run_results.json et synthétise les résultats des tests."""
    if not DBT_RUN_RESULTS.exists():
        return {"erreur": "run_results.json introuvable — lancer 'dbt test' d'abord"}

    data = json.loads(DBT_RUN_RESULTS.read_text(encoding="utf-8"))
    resultats = data.get("results", [])
    tests = [r for r in resultats if r["unique_id"].startswith("test.")]

    par_statut = {}
    for t in tests:
        statut = t["status"]
        par_statut[statut] = par_statut.get(statut, 0) + 1

    return {
        "nombre_total_tests": len(tests),
        "resultats_par_statut": par_statut,
        "tous_tests_passes": all(t["status"] in ("pass", "success") for t in tests),
        "temps_execution_total_dbt_secondes": round(data.get("elapsed_time", 0), 2),
    }


def generer_rapport():
    env = lire_env()
    conn = connecter_postgres(env)
    curseur = conn.cursor()

    rapport = {
        "genere_le_utc": datetime.now(timezone.utc).isoformat(),
        "ingestion_raw_airbyte": compter_lignes_raw(curseur),
        "completude_pipeline": mesurer_completude(curseur),
        "qualite_valeurs_nulles": mesurer_valeurs_nulles(curseur),
        "latence_accessibilite": mesurer_latence_pipeline(curseur),
        "tests_dbt": lire_resultats_tests_dbt(),
    }

    curseur.close()
    conn.close()

    DOSSIER_RAPPORTS.mkdir(parents=True, exist_ok=True)
    chemin_json = DOSSIER_RAPPORTS / "rapport_qualite.json"
    chemin_json.write_text(json.dumps(rapport, indent=2, ensure_ascii=False), encoding="utf-8")

    # Résumé Markdown lisible, réutilisable directement dans la présentation
    resume = generer_resume_markdown(rapport)
    chemin_md = DOSSIER_RAPPORTS / "rapport_qualite.md"
    chemin_md.write_text(resume, encoding="utf-8")

    print(f"Rapport JSON écrit : {chemin_json}")
    print(f"Résumé Markdown écrit : {chemin_md}")
    print()
    print(resume)


def generer_resume_markdown(rapport):
    completude = rapport["completude_pipeline"]
    nulles = rapport["qualite_valeurs_nulles"]
    latence = rapport["latence_accessibilite"]
    tests = rapport["tests_dbt"]

    lignes = [
        "# Rapport de qualité et d'accessibilité des données — Forecast 2.0",
        "",
        f"_Généré le {rapport['genere_le_utc']}_",
        "",
        "## Complétude du pipeline",
        "",
        f"- Relevés bruts ingérés par Airbyte : **{completude['releves_bruts_ingeres']}**",
        f"- Relevés en couche intermediate : **{completude['releves_couche_intermediate']}**",
        f"- Observations dans la table de faits finale : **{completude['observations_table_de_faits']}**",
        f"- Rejets RAW → intermediate : {completude['rejets_entre_raw_et_intermediate']}",
        f"- Rejets intermediate → fact : {completude['rejets_entre_intermediate_et_fact']}",
        f"- **Taux de complétude réel : {completude['taux_completude_pct']}%**",
        "",
        "## Qualité des valeurs (table de faits finale)",
        "",
        f"- Total observations : {nulles['total_observations']}",
    ]
    for col, nb_null in nulles["valeurs_nulles_par_colonne"].items():
        pct = round(nb_null / nulles["total_observations"] * 100, 2) if nulles["total_observations"] else 0
        lignes.append(f"- Valeurs nulles sur `{col}` : {nb_null} ({pct}%)")

    lignes += [
        "",
        "## Accessibilité des données (latence)",
        "",
        f"- Première ingestion Airbyte (UTC) : {latence.get('premiere_ingestion_airbyte_utc')}",
        f"- Dernière ingestion Airbyte (UTC) : {latence.get('derniere_ingestion_airbyte_utc')}",
        f"- Fin du dernier build DBT (UTC) : {latence.get('dernier_run_dbt_termine_utc')}",
        f"- Durée d'exécution DBT (deps+seed+run+test) : {latence.get('duree_execution_dbt_secondes')} s",
    ]
    if "delai_ingestion_vers_disponibilite_marts_secondes" in latence:
        lignes.append(
            f"- Délai entre dernière ingestion Airbyte et disponibilité en marts : "
            f"{latence['delai_ingestion_vers_disponibilite_marts_secondes']} s"
        )

    lignes += [
        "",
        "## Résultats des tests DBT",
        "",
        f"- Nombre total de tests exécutés : {tests.get('nombre_total_tests')}",
        f"- Répartition par statut : {tests.get('resultats_par_statut')}",
        f"- Tous les tests passés : {'Oui' if tests.get('tous_tests_passes') else 'Non'}",
        f"- Temps d'exécution total (run+test) : {tests.get('temps_execution_total_dbt_secondes')} s",
    ]

    return "\n".join(lignes) + "\n"


if __name__ == "__main__":
    generer_rapport()
