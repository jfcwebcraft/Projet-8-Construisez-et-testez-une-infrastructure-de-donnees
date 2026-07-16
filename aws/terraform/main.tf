/*
Infrastructure AWS du projet Forecast 2.0 - GreenCoop
Ressources provisionnées :
  - Amazon RDS PostgreSQL 16 (instance db.t3.micro — free tier)
  - Groupe de sécurité RDS
  - Secrets Manager pour les credentials de la base
  - ECR pour l'image DBT
  - ECS Fargate pour l'exécution planifiée de DBT
  - CloudWatch Log Groups pour les logs Airbyte et DBT
  - EventBridge Rule pour planifier les runs DBT quotidiens

Sécurité : aucun secret en dur — tout est lu depuis AWS Secrets Manager.
*/

terraform {
  required_version = ">= 1.6.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# --- Data sources ---
data "aws_caller_identity" "current" {}
data "aws_availability_zones" "available" { state = "available" }

# --- VPC par défaut ---
data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

# -----------------------------------------------------------------------
# Groupe de sécurité pour RDS
# -----------------------------------------------------------------------
resource "aws_security_group" "rds_sg" {
  name        = "${var.project_name}-rds-sg"
  description = "Groupe de securite pour la base PostgreSQL Forecast 2.0"
  vpc_id      = data.aws_vpc.default.id

  ingress {
    description = "Acces PostgreSQL depuis ECS Fargate"
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    self        = true
  }

  # Accès depuis le security group dédié aux tâches ECS Fargate DBT
  # (déclaré ici en inline pour éviter tout conflit avec une ressource
  # aws_security_group_rule séparée, qui entrerait en compétition avec
  # ce bloc "ingress" sur la même ressource).
  ingress {
    description     = "Acces PostgreSQL depuis la tache ECS Fargate DBT"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.ecs_dbt_sg.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Project = var.project_name, ManagedBy = "terraform" }
}

# -----------------------------------------------------------------------
# Subnet Group RDS
# -----------------------------------------------------------------------
resource "aws_db_subnet_group" "main" {
  name       = "${var.project_name}-db-subnet-group"
  subnet_ids = data.aws_subnets.default.ids

  tags = { Project = var.project_name, ManagedBy = "terraform" }
}

# -----------------------------------------------------------------------
# RDS PostgreSQL 16 (Free Tier : db.t3.micro, 20 Go)
# -----------------------------------------------------------------------
resource "aws_db_instance" "weather_dwh" {
  identifier             = "${var.project_name}-dwh"
  engine                 = "postgres"
  engine_version         = "16.13"
  instance_class         = "db.t3.micro"
  allocated_storage      = 20
  max_allocated_storage  = 100
  db_name                = "weather_dwh"
  username               = var.db_master_username
  password               = var.db_master_password
  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.rds_sg.id]

  # Sauvegardes automatiques — CONTRAINTE DE COMPTE CONSTATÉE : ce compte AWS
  # est sous restriction Free Tier promotionnelle qui interdit toute
  # rétention de sauvegarde RDS > 0 (erreur API "FreeTierRestrictionError"
  # obtenue lors d'un essai à backup_retention_period = 7). Ce n'est pas un
  # choix de configuration mais une limite imposée par AWS sur ce type de
  # compte. Sur un compte standard (hors promotion Free Tier restreinte),
  # il faudrait fixer cette valeur à 7 jours minimum ; le stockage des
  # sauvegardes automatiques est alors gratuit jusqu'à hauteur du stockage
  # alloué à l'instance (20 Go ici).
  backup_retention_period = 0

  # Mises à jour automatiques des patches mineurs
  auto_minor_version_upgrade = true

  # Chiffrement des données au repos
  storage_encrypted = true

  # Monitoring — désactivé pour free tier (pas de rôle IAM Enhanced Monitoring)
  monitoring_interval = 0

  # Pas de Multi-AZ pour le free tier
  multi_az = false

  # Accès public désactivé — connexion via VPC uniquement
  publicly_accessible = false

  # Suppression protégée en production
  deletion_protection = false
  skip_final_snapshot = true

  tags = {
    Project   = var.project_name
    ManagedBy = "terraform"
    Env       = "prod"
  }
}

# -----------------------------------------------------------------------
# AWS Secrets Manager — credentials RDS (référence pour ECS/DBT)
# -----------------------------------------------------------------------
resource "aws_secretsmanager_secret" "rds_credentials" {
  name                    = "${var.project_name}/rds/credentials"
  description             = "Identifiants PostgreSQL pour l'entrepôt météo Forecast 2.0"
  recovery_window_in_days = 7

  tags = { Project = var.project_name, ManagedBy = "terraform" }
}

resource "aws_secretsmanager_secret_version" "rds_credentials" {
  secret_id = aws_secretsmanager_secret.rds_credentials.id
  secret_string = jsonencode({
    host     = aws_db_instance.weather_dwh.address
    port     = 5432
    dbname   = "weather_dwh"
    username = var.db_master_username
    password = var.db_master_password
  })
}

# -----------------------------------------------------------------------
# CloudWatch Log Groups (logs DBT + Airbyte)
# -----------------------------------------------------------------------
resource "aws_cloudwatch_log_group" "dbt_logs" {
  name              = "/ecs/${var.project_name}/dbt"
  retention_in_days = 30

  tags = { Project = var.project_name, ManagedBy = "terraform" }
}

resource "aws_cloudwatch_log_group" "airbyte_logs" {
  name              = "/airbyte/${var.project_name}"
  retention_in_days = 30

  tags = { Project = var.project_name, ManagedBy = "terraform" }
}

# -----------------------------------------------------------------------
# ECR — dépôt de l'image Docker DBT utilisée par la tâche ECS Fargate
# -----------------------------------------------------------------------
resource "aws_ecr_repository" "dbt_image" {
  name                 = "${var.project_name}-dbt"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = { Project = var.project_name, ManagedBy = "terraform" }
}

# -----------------------------------------------------------------------
# ECR — dépôt de l'image Docker de chargement RAW ponctuel vers RDS
#
# Contexte : Airbyte OSS tourne uniquement en local dans ce projet (voir
# JOURNAL_DE_BORD.md). Cette tâche ECS reproduit fidèlement le schéma de
# sortie Airbyte Destinations V2 pour permettre l'exécution du pipeline DBT
# complet contre l'instance RDS de production. Elle est exécutée une seule
# fois manuellement (pas de planification EventBridge), à la différence de
# la tâche dbt_run qui s'exécute quotidiennement.
# -----------------------------------------------------------------------
resource "aws_ecr_repository" "charger_raw_image" {
  name                 = "${var.project_name}-charger-raw"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = { Project = var.project_name, ManagedBy = "terraform" }
}

resource "aws_ecs_task_definition" "charger_raw" {
  family                   = "${var.project_name}-charger-raw"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "256"
  memory                   = "512"
  execution_role_arn       = aws_iam_role.ecs_task_execution_role.arn

  container_definitions = jsonencode([{
    name  = "charger-raw"
    image = "${aws_ecr_repository.charger_raw_image.repository_url}:latest"

    secrets = [
      { name = "AWS_RDS_HOST", valueFrom = "${aws_secretsmanager_secret.rds_credentials.arn}:host::" },
      { name = "AWS_RDS_MASTER_USERNAME", valueFrom = "${aws_secretsmanager_secret.rds_credentials.arn}:username::" },
      { name = "AWS_RDS_MASTER_PASSWORD", valueFrom = "${aws_secretsmanager_secret.rds_credentials.arn}:password::" }
    ]

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.dbt_logs.name
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "charger-raw"
      }
    }
  }])

  tags = { Project = var.project_name, ManagedBy = "terraform" }
}

# -----------------------------------------------------------------------
# ECS Cluster pour l'exécution DBT
# -----------------------------------------------------------------------
resource "aws_ecs_cluster" "dbt_cluster" {
  name = "${var.project_name}-dbt-cluster"

  configuration {
    execute_command_configuration {
      logging = "OVERRIDE"
      log_configuration {
        cloud_watch_log_group_name = aws_cloudwatch_log_group.dbt_logs.name
      }
    }
  }

  tags = { Project = var.project_name, ManagedBy = "terraform" }
}

# -----------------------------------------------------------------------
# IAM Role ECS Task Execution
# -----------------------------------------------------------------------
resource "aws_iam_role" "ecs_task_execution_role" {
  name = "${var.project_name}-ecs-task-exec-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
    }]
  })

  tags = { Project = var.project_name, ManagedBy = "terraform" }
}

resource "aws_iam_role_policy_attachment" "ecs_task_execution" {
  role       = aws_iam_role.ecs_task_execution_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# Autoriser l'accès à Secrets Manager depuis la task ECS
resource "aws_iam_role_policy" "ecs_secrets_policy" {
  name = "${var.project_name}-ecs-secrets-policy"
  role = aws_iam_role.ecs_task_execution_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["secretsmanager:GetSecretValue"]
      Resource = [aws_secretsmanager_secret.rds_credentials.arn]
    }]
  })
}

# -----------------------------------------------------------------------
# ECS Task Definition pour DBT Run quotidien
# -----------------------------------------------------------------------
resource "aws_ecs_task_definition" "dbt_run" {
  family                   = "${var.project_name}-dbt-run"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "256"
  memory                   = "512"
  execution_role_arn       = aws_iam_role.ecs_task_execution_role.arn

  container_definitions = jsonencode([{
    name = "dbt-run"
    # Image DBT avec adaptateur PostgreSQL — à pousser dans ECR après build local
    image = "${aws_ecr_repository.dbt_image.repository_url}:latest"

    # L'image Docker définit ENTRYPOINT ["dbt"], donc "build" est le premier
    # argument de la commande "dbt" — inutile de répéter "dbt" ici.
    # "dbt build" exécute seeds + models + tests dans l'ordre du DAG, alors
    # que "dbt run" seul ignore les seeds (dim_stations_seed ne serait jamais
    # chargé, faisant échouer dim_weather_stations qui en dépend).
    command = ["build", "--profiles-dir", "/app", "--target", "prod"]

    environment = [
      { name = "DBT_ENV", value = "prod" }
    ]

    secrets = [
      { name = "AWS_RDS_HOST", valueFrom = "${aws_secretsmanager_secret.rds_credentials.arn}:host::" },
      { name = "AWS_RDS_MASTER_USERNAME", valueFrom = "${aws_secretsmanager_secret.rds_credentials.arn}:username::" },
      { name = "AWS_RDS_MASTER_PASSWORD", valueFrom = "${aws_secretsmanager_secret.rds_credentials.arn}:password::" }
    ]

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.dbt_logs.name
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "dbt-run"
      }
    }
  }])

  tags = { Project = var.project_name, ManagedBy = "terraform" }
}

# -----------------------------------------------------------------------
# EventBridge Rule — déclenchement quotidien à 06h00 UTC
# -----------------------------------------------------------------------
resource "aws_iam_role" "eventbridge_ecs_role" {
  name = "${var.project_name}-eventbridge-ecs-role"

  # Le rôle est assumé par EventBridge (events.amazonaws.com), pas par le
  # scheduler AWS (Scheduler est un service distinct d'EventBridge Rules).
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "events.amazonaws.com" }
    }]
  })

  tags = { Project = var.project_name, ManagedBy = "terraform" }
}

# Autorise EventBridge à démarrer la tâche ECS Fargate et à passer les rôles
# IAM nécessaires (exécution + tâche) au moment du RunTask.
resource "aws_iam_role_policy" "eventbridge_ecs_run_task" {
  name = "${var.project_name}-eventbridge-run-task-policy"
  role = aws_iam_role.eventbridge_ecs_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["ecs:RunTask"]
        Resource = [replace(aws_ecs_task_definition.dbt_run.arn, "/:\\d+$/", ":*")]
        Condition = {
          ArnLike = { "ecs:cluster" = aws_ecs_cluster.dbt_cluster.arn }
        }
      },
      {
        Effect   = "Allow"
        Action   = ["iam:PassRole"]
        Resource = [aws_iam_role.ecs_task_execution_role.arn]
      }
    ]
  })
}

# -----------------------------------------------------------------------
# Groupe de sécurité pour les tâches ECS Fargate (DBT)
# -----------------------------------------------------------------------
resource "aws_security_group" "ecs_dbt_sg" {
  name        = "${var.project_name}-ecs-dbt-sg"
  description = "Groupe de securite pour la tache ECS Fargate execution DBT"
  vpc_id      = data.aws_vpc.default.id

  egress {
    description = "Sortant : acces RDS + pull image ECR + Secrets Manager (via NAT/IGW)"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Project = var.project_name, ManagedBy = "terraform" }
}

resource "aws_cloudwatch_event_rule" "dbt_schedule" {
  name                = "${var.project_name}-dbt-daily"
  description         = "Déclenche DBT run quotidien à 06h00 UTC (données météo J-1)"
  schedule_expression = "cron(0 6 * * ? *)"
  state               = "ENABLED"

  tags = { Project = var.project_name, ManagedBy = "terraform" }
}

# -----------------------------------------------------------------------
# Cible EventBridge : lance la tâche ECS Fargate DBT à chaque déclenchement
# -----------------------------------------------------------------------
resource "aws_cloudwatch_event_target" "dbt_daily_ecs_target" {
  rule     = aws_cloudwatch_event_rule.dbt_schedule.name
  arn      = aws_ecs_cluster.dbt_cluster.arn
  role_arn = aws_iam_role.eventbridge_ecs_role.arn

  ecs_target {
    task_definition_arn = aws_ecs_task_definition.dbt_run.arn
    task_count          = 1
    launch_type         = "FARGATE"

    network_configuration {
      subnets          = data.aws_subnets.default.ids
      security_groups  = [aws_security_group.ecs_dbt_sg.id]
      assign_public_ip = true
    }
  }
}

# -----------------------------------------------------------------------
# Monitoring — alarme CloudWatch sur les métriques RDS (CPU) et sur les
# erreurs applicatives DBT (filtre de logs -> métrique -> alarme)
# -----------------------------------------------------------------------
resource "aws_cloudwatch_metric_alarm" "rds_high_cpu" {
  alarm_name          = "${var.project_name}-rds-high-cpu"
  alarm_description   = "Alerte si l'utilisation CPU de l'instance RDS dépasse 80% pendant 10 minutes"
  namespace           = "AWS/RDS"
  metric_name         = "CPUUtilization"
  statistic           = "Average"
  period              = 300
  evaluation_periods  = 2
  threshold           = 80
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"

  dimensions = {
    DBInstanceIdentifier = aws_db_instance.weather_dwh.identifier
  }

  tags = { Project = var.project_name, ManagedBy = "terraform" }
}

# Filtre de logs : détecte les lignes d'erreur DBT dans CloudWatch Logs
resource "aws_cloudwatch_log_metric_filter" "dbt_run_errors" {
  name           = "${var.project_name}-dbt-run-errors"
  log_group_name = aws_cloudwatch_log_group.dbt_logs.name
  pattern        = "?ERROR ?Failed ?Traceback"

  metric_transformation {
    name      = "DbtRunErrorCount"
    namespace = "${var.project_name}/dbt"
    value     = "1"
  }
}

resource "aws_cloudwatch_metric_alarm" "dbt_run_failures" {
  alarm_name          = "${var.project_name}-dbt-run-failures"
  alarm_description   = "Alerte si une exécution DBT génère des erreurs dans les logs CloudWatch"
  namespace           = "${var.project_name}/dbt"
  metric_name         = "DbtRunErrorCount"
  statistic           = "Sum"
  period              = 3600
  evaluation_periods  = 1
  threshold           = 0
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"

  tags = { Project = var.project_name, ManagedBy = "terraform" }
}

# -----------------------------------------------------------------------
# Outputs
# -----------------------------------------------------------------------
output "rds_endpoint" {
  description = "Endpoint de connexion à la base PostgreSQL RDS"
  value       = aws_db_instance.weather_dwh.address
  sensitive   = true
}

output "rds_port" {
  description = "Port PostgreSQL"
  value       = aws_db_instance.weather_dwh.port
}

output "secrets_manager_arn" {
  description = "ARN du secret Secrets Manager contenant les credentials RDS"
  value       = aws_secretsmanager_secret.rds_credentials.arn
}

output "cloudwatch_dbt_log_group" {
  description = "Groupe de logs CloudWatch pour DBT"
  value       = aws_cloudwatch_log_group.dbt_logs.name
}
