# 1 — Airbyte sur AWS

## Ce que je démontre ici
Dans ce dossier, je prouve l'ingestion des données au moyen d'une architecture Cloud entièrement hébergée sur AWS.

L'ingestion s'appuie sur **Airbyte Open Source (OSS)** déployé sur une instance AWS EC2 (`t3.medium`) dédiée au sein du VPC. L'instance est provisionnée automatiquement via Terraform (`aws/terraform/airbyte_ec2.tf`) et exécute les conteneurs Airbyte via Docker Compose (`aws/docker-compose.airbyte.yml`).

## Configuration mise en place
1. **Infrastructure IaC Terraform** :
   - Instance EC2 `t3.medium` sur AWS Amazon Linux 2023.
   - Groupe de sécurité dédié (`greencoop-forecast-airbyte-sg`) autorisant les flux Web (8000), SSH (22) et l'accès sortant vers RDS PostgreSQL (port 5432).
   - Rôle IAM et profils d'instance autorisant l'écriture de métriques et de logs dans AWS CloudWatch (`CloudWatchAgentServerPolicy`).

2. **Connecteurs Airbyte** :
   - 4 connexions configurées vers les sources météorologiques (InfoClimat et Weather Underground).
   - Destination : Instance Amazon RDS PostgreSQL (`greencoop-forecast-dwh`) dans le schéma `raw_airbyte`.

3. **Centralisation des Logs** :
   - Redirection native des logs des conteneurs Airbyte vers le Log Group CloudWatch `/airbyte/Forecast-2-0` via le log driver `awslogs`.

## Résultat obtenu
- Connexion d'ingestion validée ("All tests passed").
- Synchronisation automatique quotidienne déclenchée à 06h00 UTC.
- Ingestion brute de 4 954 enregistrements répartis dans les 4 tables du schéma `raw_airbyte` sur RDS.

## Fichiers techniques
- [airbyte_ec2.tf](file:///c:/Users/docje/Documents/Code/Projet%208%20Construisez%20et%20testez%20une%20infrastructure%20de%20donn%C3%A9es/aws/terraform/airbyte_ec2.tf) : provisionnement de l'instance EC2 Airbyte.
- [docker-compose.airbyte.yml](file:///c:/Users/docje/Documents/Code/Projet%208%20Construisez%20et%20testez%20une%20infrastructure%20de%20donn%C3%A9es/aws/docker-compose.airbyte.yml) : conteneurisation d'Airbyte OSS avec driver CloudWatch.
- [main.tf](file:///c:/Users/docje/Documents/Code/Projet%208%20Construisez%20et%20testez%20une%20infrastructure%20de%20donn%C3%A9es/aws/terraform/main.tf) : création du RDS et autorisations du groupe de sécurité.
