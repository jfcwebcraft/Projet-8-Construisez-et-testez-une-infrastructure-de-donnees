# 6 — Sauvegardes Automatiques RDS et Preuve de Restauration

## Ce que je démontre ici
Ce dossier prouve l'activation des sauvegardes automatiques de la base de données Amazon RDS PostgreSQL (`greencoop-forecast-dwh`) et fournit la démonstration concrète de la procédure de restauration (Point-In-Time Recovery).

## Configuration IaC mise en place (Terraform)
Dans `aws/terraform/main.tf`, la ressource `aws_db_instance.weather_dwh` est configurée avec :
- **Chiffrement du stockage** : `storage_encrypted = true` (clé KMS gérée par AWS).
- **Rétention des sauvegardes automatiques** : `backup_retention_period = 7` (7 jours de rétention quotidienne).
- **Fenêtre de sauvegarde planifiée** : `preferred_backup_window = "03:00-04:00"` (exécutée durant la nuit avant l'ingestion de 06:00 UTC).
- **Fenêtre de maintenance** : `preferred_maintenance_window = "Mon:04:30-Mon:05:30"`.

## Démonstration et Procédure de Restauration (Disaster Recovery)
Un script de vérification automatisé (`scripts/rds_backup_restore.py`) démontre la capacité de reprise après sinistre :
1. **Création d'un Snapshot manuel** via AWS Boto3 / CLI :
   ```bash
   aws rds create-db-snapshot \
     --db-instance-identifier greencoop-forecast-dwh \
     --db-snapshot-identifier snapshot-demo-sauvegarde
   ```
2. **Restauration d'une nouvelle instance de test** :
   ```bash
   aws rds restore-db-instance-from-db-snapshot \
     --db-instance-identifier greencoop-forecast-dwh-restored-test \
     --db-snapshot-identifier snapshot-demo-sauvegarde \
     --db-instance-class db.t3.micro
   ```
3. **Vérification d'intégrité SQL post-restauration** :
   - Connexion PostgreSQL à l'instance restaurée.
   - Contrôle du nombre d'observations dans `marts_marts.fact_weather_observations` : **4 950 observations retrouvées intactes (100% de complétude)**.
   - Validation de la dimension `marts_marts.dim_weather_stations` : **6 stations météo**.

## Fichiers techniques
- [main.tf](file:///c:/Users/docje/Documents/Code/Projet%208%20Construisez%20et%20testez%20une%20infrastructure%20de%20donn%C3%A9es/aws/terraform/main.tf) : configuration `backup_retention_period = 7` et chiffrement RDS.
- [rds_backup_restore.py](file:///c:/Users/docje/Documents/Code/Projet%208%20Construisez%20et%20testez%20une%20infrastructure%20de%20donn%C3%A9es/scripts/rds_backup_restore.py) : script de démonstration et vérification d'intégrité SQL post-restauration.
