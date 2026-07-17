# Forecast 2.0 — Pipeline de données météorologiques

Infrastructure de données ELT pour le projet Forecast 2.0 de GreenCoop, fournisseur coopératif d'électricité d'origine renouvelable dans les Hauts-de-France.

## Contexte

GreenCoop a besoin de données météorologiques fiables et précises pour améliorer ses algorithmes de prévision de la demande électrique. Ce projet met en place un pipeline automatisé qui ingère, transforme et fiabilise les relevés de 6 stations météo (réseau InfoClimat et Weather Underground) dans un entrepôt de données PostgreSQL, accessible depuis SageMaker pour les travaux de Machine Learning.

## Architecture

![Schéma d'architecture](archives/diagrammes/02_schema_architecture.png)

Deux environnements : un socle local (Docker Compose) pour le développement et les tests, et une infrastructure AWS pour la production. Voir `archives/diagrammes/` pour les schémas source (Mermaid) et le logigramme complet du processus ELT.

**Stack technique** : Docker · Airbyte OSS 0.63.14 · DBT Core 1.9/1.11 · PostgreSQL 16 · AWS RDS · AWS ECS Fargate · AWS ECR · AWS EventBridge · AWS CloudWatch · AWS Secrets Manager · Terraform

## Structure du dépôt

```
.
├── docker-compose.yml          # Stack locale : PostgreSQL DWH + Airbyte
├── .env.example                # Variables d'environnement à configurer
├── airbyte/
│   ├── flags.yml               # Configuration des feature flags Airbyte
│   ├── data/                   # CSV sources préparés pour les connecteurs Airbyte
│   └── temporal/               # Config dynamique Temporal (workflow engine)
├── scripts/
│   ├── extraction/             # Mise à plat des sources (JSON → CSV, Excel → CSV)
│   ├── ingestion/              # Chargement RAW : PostgreSQL local + RDS (voir note ci-dessous)
│   └── reporting/              # Calcul du rapport de qualité et de latence réel
├── dbt/
│   ├── dbt_project.yml         # Configuration du projet DBT
│   ├── profiles.yml            # Profils de connexion (dev local / prod AWS)
│   ├── models/
│   │   ├── sources.yml         # Déclaration des sources RAW Airbyte
│   │   ├── staging/            # Standardisation et typage (vues)
│   │   ├── intermediate/       # Unification multi-sources (vues)
│   │   └── marts/              # Schéma en étoile final (tables matérialisées)
│   ├── seeds/                  # Données statiques de référence (métadonnées stations)
│   └── tests/                  # Tests métier personnalisés
├── aws/
│   ├── Dockerfile.dbt              # Image Docker pour DBT en mode batch (ECS)
│   ├── Dockerfile.charger-raw      # Image Docker pour le chargement RAW ponctuel vers RDS
│   └── terraform/                  # Infrastructure AWS as Code
└── archives/
    ├── diagrammes/             # Schémas visuels (Mermaid + PNG) : architecture, logigramme, BDD
    ├── screenshots/            # Captures d'écran Airbyte / DBT / AWS pour la présentation
    └── JOURNAL_DE_BORD.md      # Decisions techniques et suivi du projet
```

> **Note sur l'Architecture AWS** : L'ingestion s'appuie sur Airbyte OSS déployé sur AWS (instance EC2 `t3.medium` provisionnée via Terraform `airbyte_ec2.tf`). L'enchaînement entre Airbyte et les traitements DBT sur AWS ECS Fargate est piloté de manière séquentielle et déterministe via l'orchestrateur `scripts/orchestrate_pipeline.py`, garantissant qu'aucune transformation DBT ne se lance avant le succès total de l'ingestion Airbyte. Les logs sont unifiés dans AWS CloudWatch (`/airbyte/Forecast-2-0` et `/ecs/Forecast-2-0/dbt`).

## Modèle de données

Schéma en étoile dans le schéma `marts_marts` de PostgreSQL :

| Table | Type | Description |
|---|---|---|
| `fact_weather_observations` | Table de faits | 4 950 observations, 1 par station × instant UTC |
| `dim_weather_stations` | Dimension | 6 stations (4 InfoClimat + 2 WUnderground) |
| `dim_dates` | Dimension | Calendrier des dates couvertes |

**Sources RAW** (schéma `raw_airbyte`) : 4 tables avec payload JSONB fidèle aux sources (4 954 enregistrements bruts).

## Qualité des données

56 tests DBT automatisés au total :
- Tests génériques : unicité des clés, valeurs non nulles, relations entre tables
- Tests de plages de valeurs : température (-40/+60°C), humidité (0-100%), pression (950-1060 hPa)
- Tests métier personnalisés : cohérence des températures Hauts-de-France, couverture des 6 stations

**Résultat : 56/56 tests passés** lors de la dernière exécution (locale et sur AWS).

Rapport de qualité et d'accessibilité généré automatiquement (chiffres réels, pas estimés) :

```bash
python scripts/reporting/generer_rapport_qualite.py
```

Résultat de la dernière exécution : **taux de complétude 100%** (4 954 relevés bruts ingérés = 4 950 observations en table de faits), **0 valeur nulle** sur les colonnes critiques, latence bout-en-bout mesurée à **225 secondes (3 minutes 45 secondes)** entre l'ingestion Airbyte et la disponibilité en marts. Voir `data/reports/rapport_qualite.json` et `.md`.

## Démarrage rapide (local)

### Prérequis

- Docker Desktop (≥ 4 CPU, 8 Go RAM alloués)
- Python ≥ 3.11 avec pip

### 1. Configuration

```bash
cp .env.example .env
# Éditer .env avec vos propres valeurs
```

### 2. Lancer la stack Docker

```bash
docker compose up -d
```

L'interface Airbyte est accessible sur **http://localhost:8000** (identifiants dans `.env`).

### 3. Préparer et ingérer les données

```bash
pip install pandas openpyxl psycopg2-binary

# Mise à plat des sources brutes
python scripts/extraction/extraire_infoclimat.py
python scripts/extraction/extraire_weather_underground.py

# Chargement dans PostgreSQL (schéma raw_airbyte)
python scripts/ingestion/charger_raw_postgres.py
```

### 4. Transformations DBT

```bash
# Séquence complète automatisée (deps → seed → run → test → docs generate)
python dbt/run_dbt_batch.py

# Servir le site web de documentation dbt interactif (http://localhost:8080)
.venv\Scripts\python.exe -m dbt.cli.main docs serve --port 8080
```

Les tables analytiques sont créées dans les schémas `marts_staging`, `marts_intermediate` et `marts_marts`.

## Déploiement AWS

L'infrastructure cloud est provisionnée avec Terraform :

```bash
cd aws/terraform
cp terraform.tfvars.example terraform.tfvars
# Renseigner vos credentials dans terraform.tfvars

terraform init
terraform plan
terraform apply
```

**Ressources créées :**
- Amazon RDS PostgreSQL 16 (`db.t3.micro`, free tier)
- ECR + ECS Cluster + Task Definitions (`dbt-run` quotidien, `charger-raw` ponctuel)
- EventBridge Rule + Target planifiant `dbt-run` à 06h00 UTC
- CloudWatch Log Groups (Airbyte, DBT) + 2 alarmes (CPU RDS, échecs DBT)
- Secrets Manager pour les credentials RDS
- Security groups dédiés (RDS, tâches ECS)

### Build et déploiement des images Docker sur ECR

```bash
aws ecr get-login-password --region eu-west-3 | docker login --username AWS --password-stdin 123456789012.dkr.ecr.eu-west-3.amazonaws.com

docker build -f aws/Dockerfile.dbt -t greencoop-forecast-dbt:latest .
docker tag greencoop-forecast-dbt:latest 123456789012.dkr.ecr.eu-west-3.amazonaws.com/greencoop-forecast-dbt:latest
docker push 123456789012.dkr.ecr.eu-west-3.amazonaws.com/greencoop-forecast-dbt:latest
```

### Exécution manuelle des tâches ECS (test / première initialisation)

```bash
# 1. Peupler RDS (raw_airbyte) — exécution de l'ingestion
aws ecs run-task --cluster greencoop-forecast-dbt-cluster --task-definition greencoop-forecast-charger-raw \
  --launch-type FARGATE --network-configuration "awsvpcConfiguration={subnets=[subnet-12345678],securityGroups=[sg-12345678],assignPublicIp=ENABLED}" --region eu-west-3

# 2. Lancer les transformations DBT contre RDS PostgreSQL (PowerShell / Bash)
aws ecs run-task `
  --cluster greencoop-forecast-dbt-cluster `
  --task-definition greencoop-forecast-dbt-run `
  --launch-type FARGATE `
  --network-configuration "awsvpcConfiguration={subnets=[subnet-12345678],securityGroups=[sg-12345678],assignPublicIp=ENABLED}" `
  --region eu-west-3
```

**Résultat vérifié sur AWS (logs CloudWatch, `/ecs/greencoop-forecast/dbt`) :**
```text
Finished running 1 seed, 3 table models, 56 data tests, 4 view models in 12.51s
Completed successfully
Done. PASS=64 WARN=0 ERROR=0 SKIP=0 TOTAL=64
```

> ⚠️ Pensez à exécuter `terraform destroy` après le projet pour éviter toute facturation inattendue.

## Connecteurs Airbyte configurés

| Connexion | Source | Destination | Fréquence |
|---|---|---|---|
| InfoClimat Stations | File (CSV local) | PostgreSQL `raw_airbyte` | Manuel / quotidien |
| InfoClimat Relevés | File (CSV local) | PostgreSQL `raw_airbyte` | Manuel / quotidien |
| WUnderground Ichtegem | File (CSV local) | PostgreSQL `raw_airbyte` | Manuel / quotidien |
| WUnderground La Madeleine | File (CSV local) | PostgreSQL `raw_airbyte` | Manuel / quotidien |

## Sécurité

- Aucun secret en clair dans le code versionné
- Fichier `.env` protégé par `.gitignore`
- `terraform.tfvars` protégé par `.gitignore`
- Credentials AWS RDS stockés dans Secrets Manager
- DBT lit le mot de passe via la variable d'environnement `DWH_POSTGRES_PASSWORD`
- Accès RDS uniquement depuis le VPC (pas d'accès public)

## Sources de données

| Source | Réseau | Localisation | Fréquence | Licence |
|---|---|---|---|---|
| Armentières (00052) | InfoClimat | 50.689°N, 2.877°E | 10 min | CC BY |
| Bergues (000R5) | InfoClimat | 50.968°N, 2.441°E | 10 min | CC BY |
| Hazebrouck (STATIC0010) | InfoClimat | 50.734°N, 2.545°E | 10 min | CC BY |
| Lille-Lesquin (07015) | InfoClimat/Météo-France | 50.575°N, 3.092°E | 1 heure | Etalab |
| Ichtegem IICHTE19 | Weather Underground | 51.092°N, 2.999°E | ~5 min | — |
| La Madeleine ILAMAD25 | Weather Underground | 50.659°N, 3.070°E | ~5 min | — |
