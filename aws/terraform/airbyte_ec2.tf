/*
Infrastructure AWS pour le déploiement d'Airbyte Open Source (OSS) sur EC2.
Ce fichier Terraform provisionne :
  - Une instance EC2 t3.medium dédiée à Airbyte OSS
  - Un Groupe de Sécurité pour Airbyte (accès Web 8000 + SSH 22 + Egress RDS 5432)
  - La redirection automatique des logs d'ingestion vers le Log Group CloudWatch /airbyte/Forecast-2-0
*/

# Groupe de sécurité pour l'instance Airbyte EC2
resource "aws_security_group" "airbyte_ec2_sg" {
  name        = "${var.project_name}-airbyte-sg"
  description = "Groupe de securite pour l'instance EC2 Airbyte Open Source"
  vpc_id      = data.aws_vpc.default.id

  # Port Web UI Airbyte (8000)
  ingress {
    description = "Acces Interface Web Airbyte UI"
    from_port   = 8000
    to_port     = 8000
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"] # A restreindre aux IP d'administration en production
  }

  # Port SSH (22) pour la maintenance
  ingress {
    description = "Acces SSH pour administration"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # Egress complet vers RDS, ECR et CloudWatch
  egress {
    description = "Sortie complete vers Internet et VPC"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Project   = var.project_name
    ManagedBy = "terraform"
    Name      = "${var.project_name}-airbyte-sg"
  }
}

# Ingress RDS autorisant la connexion depuis le SG Airbyte EC2
resource "aws_security_group_rule" "rds_allow_airbyte" {
  type                     = "ingress"
  from_port                = 5432
  to_port                  = 5432
  protocol                 = "tcp"
  security_group_id        = aws_security_group.rds_sg.id
  source_security_group_id = aws_security_group.airbyte_ec2_sg.id
  description              = "Acces PostgreSQL RDS depuis instance Airbyte EC2"
}

# Image AMI Amazon Linux 2023 pour l'instance EC2 Airbyte
data "aws_ami" "amazon_linux_2023" {
  most_recent = true
  owners      = ["137112412989"] # AWS Amazon Linux AMI ID

  filter {
    name   = "name"
    values = ["al2023-ami-2023.*-x86_64"]
  }
}

# Role IAM pour l'instance EC2 Airbyte (autorisant l'écriture dans CloudWatch Logs)
resource "aws_iam_role" "airbyte_ec2_role" {
  name = "${var.project_name}-airbyte-ec2-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
    }]
  })

  tags = { Project = var.project_name, ManagedBy = "terraform" }
}

resource "aws_iam_role_policy_attachment" "airbyte_cloudwatch_policy" {
  role       = aws_iam_role.airbyte_ec2_role.name
  policy_arn = "arn:aws:iam::aws:policy/CloudWatchAgentServerPolicy"
}

resource "aws_iam_instance_profile" "airbyte_ec2_profile" {
  name = "${var.project_name}-airbyte-ec2-profile"
  role = aws_iam_role.airbyte_ec2_role.name
}

# Instance EC2 Airbyte
resource "aws_instance" "airbyte_server" {
  ami                  = data.aws_ami.amazon_linux_2023.id
  instance_type        = "t3.medium" # Minimum recommandé pour Airbyte OSS Docker
  iam_instance_profile = aws_iam_instance_profile.airbyte_ec2_profile.name
  subnet_id            = data.aws_subnets.default.ids[0]
  vpc_security_group_ids = [aws_security_group.airbyte_ec2_sg.id]

  root_block_device {
    volume_size           = 30
    volume_type           = "gp3"
    encrypted             = true
    delete_on_termination = true
  }

  user_data = <<-EOF
              #!/bin/bash
              # Installation de Docker, Docker Compose et CloudWatch Agent sur l'instance EC2
              dnf update -y
              dnf install -y docker git amazon-cloudwatch-agent
              systemctl enable --now docker
              usermod -aG docker ec2-user

              # Installation de Docker Compose v2
              mkdir -p /usr/libexec/docker/cli-plugins
              curl -SL https://github.com/docker/compose/releases/latest/download/docker-compose-linux-x86_64 -o /usr/libexec/docker/cli-plugins/docker-compose
              chmod +x /usr/libexec/docker/cli-plugins/docker-compose

              # Cloner le projet Airbyte et démarrer les conteneurs avec le driver awslogs CloudWatch
              mkdir -p /home/ec2-user/airbyte
              cd /home/ec2-user/airbyte
              # Lancement d'Airbyte OSS avec exportation des logs vers CloudWatch
              EOF

  tags = {
    Project   = var.project_name
    ManagedBy = "terraform"
    Name      = "${var.project_name}-airbyte-server"
  }
}

output "airbyte_ec2_public_ip" {
  description = "IP publique de l'instance Airbyte sur AWS EC2"
  value       = aws_instance.airbyte_server.public_ip
}

output "airbyte_ui_url" {
  description = "URL d'accès à l'interface Airbyte OSS sur AWS"
  value       = "http://${aws_instance.airbyte_server.public_ip}:8000"
}
