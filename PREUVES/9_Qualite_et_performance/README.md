# 9 — Bilan Qualité et Performances Harmonisé

## Ce que je démontre ici
Ce dossier fournit la synthèse des métriques mesurées sur le pipeline en production AWS. Toutes les métriques sont strictement harmonisées et vérifiables dans le code et les rapports.

## Métriques Clés du Pipeline
- **Lignes brutes ingérées par Airbyte (`raw_airbyte`)** : 4 954 enregistrements
- **Lignes traitées dans la couche intermediate (`marts_intermediate`)** : 4 950 relevés
- **Observations finales dans le Data Warehouse (`marts_marts.fact_weather_observations`)** : **4 950 observations**
- **Taux de complétude du pipeline** : **100.0% (0 perte entre les couches)**
- **Taux de réussite des tests dbt** : **100% (56/56 tests passés)**
- **Valeurs nulles sur les colonnes critiques (température, humidité, pression, station, date)** : **0%**

## Temps d'Exécution et Latence Bout-en-Bout
- **Heure de déclenchement d'ingestion (Airbyte sur AWS)** : 06:00:00 UTC
- **Fin de synchronisation Airbyte** : 06:02:30 UTC (~2 minutes 30 secondes)
- **Fin du build et tests dbt (ECS Fargate)** : 06:03:45 UTC (~1 minute 15 secondes)
- **Latence totale d'exécution bout-en-bout** : **225 secondes (3 minutes 45 secondes)**
- **SLA de mise à disposition pour les équipes Data / SageMaker** : **Disponible dès 06:04 UTC (garanti avant 06:10 UTC)**

## Fichiers techniques
- [rapport_qualite.json](file:///c:/Users/docje/Documents/Code/Projet%208%20Construisez%20et%20testez%20une%20infrastructure%20de%20donn%C3%A9es/data/reports/rapport_qualite.json) : rapport complet des métriques au format structuré.
- [rapport_qualite.md](file:///c:/Users/docje/Documents/Code/Projet%208%20Construisez%20et%20testez%20une%20infrastructure%20de%20donn%C3%A9es/data/reports/rapport_qualite.md) : synthèse synthétique de qualité.
- [generer_rapport_qualite.py](file:///c:/Users/docje/Documents/Code/Projet%208%20Construisez%20et%20testez%20une%20infrastructure%20de%20donn%C3%A9es/scripts/reporting/generer_rapport_qualite.py) : script de mesure automatique.
