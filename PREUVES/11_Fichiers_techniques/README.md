# 11 — Cartographie des Fichiers Techniques et Code Source

## Ce que je démontre ici
Ce dossier fournit la cartographie complète de l'ensemble des fichiers techniques, scripts et configurations IaC constituant la solution Forecast 2.0. Tous les fichiers sont nettoyés, anonymisés et directement exploitables.

## Structure Détaillée du Dépôt

```
.
├── README.md                             # Documentation principale et métriques unifiées
├── docker-compose.yml                     # Environnement de développement local
├── dedup.py                              # Script de déduplication anonymisé
├── aws/
│   ├── Dockerfile.dbt                    # Conteneur dbt pour AWS ECS Fargate
│   ├── Dockerfile.charger-raw            # Conteneur de chargement initial RAW
│   ├── docker-compose.airbyte.yml        # Déploiement Airbyte OSS sur AWS avec driver CloudWatch
│   ├── cloudwatch-agent-config.json      # Agent CloudWatch pour les logs Airbyte
│   └── terraform/
│       ├── main.tf                       # IaC : RDS (backup=7j), ECS, EventBridge, CloudWatch, SNS
│       ├── airbyte_ec2.tf                # IaC : Instance EC2 Airbyte OSS + Security Group
│       ├── variables.tf                  # Déclaration des variables Terraform
│       └── terraform.tfvars.example      # Modèle de variables sécurisé
├── dbt/
│   ├── dbt_project.yml                   # Configuration du projet dbt Core
│   ├── profiles.yml                      # Profils PostgreSQL (dev / prod AWS)
│   ├── packages.yml                      # Packages dbt (dbt-utils)
│   ├── models/                           # Modèles SQL (staging, intermediate, marts)
│   ├── seeds/                            # Referentiel statique des stations météo
│   └── tests/                            # 4 tests métier singuliers SQL
├── scripts/
│   ├── orchestrate_pipeline.py           # Orchestrateur séquentiel Airbyte -> dbt
│   ├── rds_backup_restore.py             # Preuve de sauvegarde et restauration RDS
│   ├── demo_test_dbt_echec.py            # Démo d'échec dbt et vérification SQL d'isolation
│   ├── setup_airbyte_connectors.py       # Configuration automatique des flux Airbyte
│   ├── test_alertes_cloudwatch.py        # Test du système d'alarmes SNS
│   ├── extraction/                       # Normalisation des sources brutes (JSON/Excel -> CSV)
│   ├── ingestion/                        # Scripts de chargement RAW
│   └── reporting/                        # Calculateur de rapport de qualité et latence
└── PREUVES/                              # 12 dossiers de preuves thématiques
```

Tous les fichiers techniques sont présents et prêts pour l'exécution et la reproduction du projet.
