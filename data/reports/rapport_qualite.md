# Rapport de qualité et d'accessibilité des données — Forecast 2.0

_Généré le 2026-07-30T20:44:19.512304+00:00_

## Complétude du pipeline

- Relevés bruts ingérés par Airbyte : **4950**
- Relevés en couche intermediate : **1722**
- Observations dans la table de faits finale : **1722**
- Rejets RAW → intermediate : 3228
- Rejets intermediate → fact : 0
- **Taux de complétude réel : 34.79%**

## Qualité des valeurs (table de faits finale)

- Total observations : 1722
- Valeurs nulles sur `temperature_c` : 0 (0.0%)
- Valeurs nulles sur `humidite_pct` : 0 (0.0%)
- Valeurs nulles sur `pression_hpa` : 0 (0.0%)
- Valeurs nulles sur `vent_moyen_kmh` : 0 (0.0%)
- Valeurs nulles sur `date_heure_utc` : 0 (0.0%)
- Valeurs nulles sur `station_id` : 0 (0.0%)

## Accessibilité des données (latence)

- Première ingestion Airbyte (UTC) : 2026-07-30T06:10:39+00:00
- Dernière ingestion Airbyte (UTC) : 2026-07-30T06:21:54+00:00
- Fin du dernier build DBT (UTC) : 2026-07-24T19:58:45.257450Z
- Durée d'exécution DBT (deps+seed+run+test) : 4.54 s
- Délai entre dernière ingestion Airbyte et disponibilité en marts : -469388.74 s

## Résultats des tests DBT

- Nombre total de tests exécutés : 56
- Répartition par statut : {'pass': 56}
- Tous les tests passés : Oui
- Temps d'exécution total (run+test) : 4.54 s
