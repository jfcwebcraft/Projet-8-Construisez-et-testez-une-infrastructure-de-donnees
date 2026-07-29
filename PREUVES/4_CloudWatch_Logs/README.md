# 4 — Centralisation des Logs dans CloudWatch

## Ce que je démontre ici
Ce dossier atteste de la centralisation complète et unifiée des logs d'ingestion (Airbyte) et de transformation (dbt) au sein d'AWS CloudWatch.

## Configuration mise en place
1. **Logs d'ingestion Airbyte** :
   - Groupe de logs CloudWatch : `/airbyte/Forecast-2-0`
   - Redirection configurée dans `docker-compose.airbyte.yml` avec le driver `awslogs` et l'agent CloudWatch (`amazon-cloudwatch-agent`) sur l'instance EC2 Airbyte.

2. **Logs de transformation dbt (ECS Fargate)** :
   - Groupe de logs CloudWatch : `/ecs/Forecast-2-0/dbt`
   - Configuré dans Terraform (`aws_ecs_task_definition.dbt_run`) via le driver `awslogs`.

## Résultat obtenu
Toutes les étapes du pipeline sont traçables dans CloudWatch :
- **Log Stream Airbyte** : Traçabilité des requêtes API sources, nombre de lignes extraites et statut d'écriture dans `raw_airbyte`.
- **Log Stream dbt** : Traçabilité détaillée des commandes `dbt build`, création des vues staging, matérialisation des tables marts et exécution des 56 tests de qualité (`PASS=64 WARN=0 ERROR=0`).

## Fichiers techniques
- [main.tf](file:///c:/Users/docje/Documents/Code/Projet%208%20Construisez%20et%20testez%20une%20infrastructure%20de%20donn%C3%A9es/aws/terraform/main.tf) : création des Log Groups CloudWatch `/ecs/Forecast-2-0/dbt` et `/airbyte/Forecast-2-0`.
- [docker-compose.airbyte.yml](file:///c:/Users/docje/Documents/Code/Projet%208%20Construisez%20et%20testez%20une%20infrastructure%20de%20donn%C3%A9es/aws/docker-compose.airbyte.yml) : driver de logs AWS.
- [cloudwatch-agent-config.json](file:///c:/Users/docje/Documents/Code/Projet%208%20Construisez%20et%20testez%20une%20infrastructure%20de%20donn%C3%A9es/aws/cloudwatch-agent-config.json) : configuration de collecte de logs EC2.
