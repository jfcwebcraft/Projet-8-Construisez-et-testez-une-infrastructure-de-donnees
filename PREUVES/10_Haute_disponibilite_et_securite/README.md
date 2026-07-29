# 10 — Sécurité, Anonymisation et Haute Disponibilité

## Ce que je démontre ici
Ce dossier détaille l'application des règles de sécurité des données, l'anonymisation intégrale de la documentation et la gestion sécurisée des identifiants cloud sur AWS.

## Principes de Sécurité Appliqués
1. **Gestion des Secrets et Identifiants AWS** :
   - Aucun secret ni mot de passe n'est écrit en clair dans le code source versionné.
   - Les identifiants PostgreSQL sont stockés dans **AWS Secrets Manager** (`greencoop-forecast/rds/credentials`).
   - La tâche ECS Fargate dbt et les conteneurs injectent les secrets au runtime via la propriété `valueFrom`.

2. **Moindre Privilège IAM** :
   - Rôles d'exécution dédiés (`ecs-task-exec-role`, `airbyte-ec2-role`, `eventbridge-ecs-role`).
   - Les tâches n'ont accès qu'aux ressources strictement nécessaires (GetSecretValue sur le secret RDS et PutLogEvents sur leur Log Group CloudWatch dédié).

3. **Sécurité Réseau et Groups de Sécurité (VPC)** :
   - L'instance RDS PostgreSQL est fermée à l'accès public (`publicly_accessible = false`).
   - Les règles Ingress du Groupe de Sécurité RDS (`rds-sg`) n'autorisent que le port 5432 en provenance explicite des SG dédiés aux tâches ECS (`ecs-dbt-sg`) et à l'instance Airbyte (`airbyte-sg`).

4. **Anonymisation de la Documentation et des Captures** :
   - Les AWS Account IDs ont été anonymisés vers `123456789012`.
   - Les endpoints RDS et tokens ont été remplacés par des variables d'environnement (`AWS_RDS_HOST`).
   - Les adresses IP publiques d'administration utilisent des sous-réseaux d'exemple documentés.

5. **Sauvegardes et Continuité d'Activité (Disaster Recovery)** :
   - Rétention des sauvegardes automatiques de 7 jours avec chiffrement au repos AES-256 (`storage_encrypted = true`).

## Fichiers techniques
- [main.tf](file:///c:/Users/docje/Documents/Code/Projet%208%20Construisez%20et%20testez%20une%20infrastructure%20de%20donn%C3%A9es/aws/terraform/main.tf) : provisionnement des rôles IAM, Security Groups et Secrets Manager.
- [airbyte_ec2.tf](file:///c:/Users/docje/Documents/Code/Projet%208%20Construisez%20et%20testez%20une%20infrastructure%20de%20donn%C3%A9es/aws/terraform/airbyte_ec2.tf) : règles de sécurité de l'instance Airbyte.
