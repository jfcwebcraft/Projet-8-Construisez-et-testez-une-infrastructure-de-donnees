# 2 — Synchronisations Airbyte

## Ce que je démontre ici
Ce dossier démontre la planification et l'exécution automatisée des synchronisations Airbyte alimentant l'entrepôt Amazon RDS.

## Configuration mise en place
Dans Airbyte sur AWS, un "Sync Schedule" automatique est paramétré sur l'ensemble des 4 connexions d'ingestion. La fréquence est fixée à **24 heures** avec un déclenchement quotidien planifié à **06h00 UTC**.

**Justification métier de l'horaire :** Les données météorologiques de la journée J-1 sont définitivement clôturées et consolidées durant la nuit. L'extraction à 06h00 UTC garantit la présence de la totalité des relevés de la veille pour le pipeline de transformation dbt.

## Résultat obtenu
- Statut des jobs d'ingestion : **"Succeeded"** sur les 4 flux.
- Volume d'ingestion brute : **4 954 lignes** chargées dans les tables `raw_airbyte.infoclimat_stations`, `raw_airbyte.infoclimat_releves`, `raw_airbyte.wunderground_ichtegem`, et `raw_airbyte.wunderground_la_madeleine`.
- Durée moyenne d'ingestion Airbyte : **~2 minutes 30 secondes**.

## Fichiers techniques
- [airbyte_ec2.tf](file:///c:/Users/docje/Documents/Code/Projet%208%20Construisez%20et%20testez%20une%20infrastructure%20de%20donn%C3%A9es/aws/terraform/airbyte_ec2.tf) : instance EC2 exécutant le moteur Airbyte.
- [orchestrate_pipeline.py](file:///c:/Users/docje/Documents/Code/Projet%208%20Construisez%20et%20testez%20une%20infrastructure%20de%20donn%C3%A9es/scripts/orchestrate_pipeline.py) : script vérifiant l'état des synchronisations avant le lancement de dbt.
