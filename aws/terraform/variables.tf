/*
Variables Terraform — Forecast 2.0 GreenCoop
Toutes les valeurs sensibles doivent être définies via terraform.tfvars
(non versionné) ou via des variables d'environnement TF_VAR_*.
*/

variable "aws_region" {
  description = "Région AWS cible"
  type        = string
  default     = "eu-west-3"
}

variable "project_name" {
  description = "Préfixe des ressources AWS créées"
  type        = string
  default     = "greencoop-forecast"
}

variable "db_master_username" {
  description = "Nom d'utilisateur maître PostgreSQL RDS"
  type        = string
  sensitive   = true
}

variable "db_master_password" {
  description = "Mot de passe maître PostgreSQL RDS (min. 8 caractères)"
  type        = string
  sensitive   = true
}

variable "alert_email" {
  description = "Adresse email pour les alertes CloudWatch via SNS"
  type        = string
}
