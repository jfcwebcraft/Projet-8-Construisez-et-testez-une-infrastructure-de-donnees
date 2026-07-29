# 3 — Pipeline Automatisé Déterministe et Enchaînement Airbyte ➔ dbt

## Ce que je démontre ici
Ce dossier démontre la mise en place d'un enchaînement déterministe et sécurisé garantissant que les transformations dbt sur AWS ECS Fargate ne démarrent qu'une fois la synchronisation Airbyte totalement terminée et validée.

## Problématique résolue
Une planification aveugle à la même heure (ex: Airbyte à 06h00 et dbt à 06h00) comporte un risque majeur d'exécuter dbt sur des données incomplètes ou en cours d'écriture. Pour éliminer tout chevauchement, l'architecture met en œuvre un **orchestrateur déterministe séquentiel** (`scripts/orchestrate_pipeline.py`).

## Fonctionnement du mécanisme
1. **Déclenchement Airbyte** : À 06h00 UTC, l'orchestrateur initie les synchronisations via l'API Airbyte REST (`/api/v1/connections/sync`).
2. **Polling de statut** : L'orchestrateur scrute le statut de l'ingestion (`running`, `succeeded`, `failed`).
3. **Déclenchement conditionnel ECS dbt** : Seul le statut `succeeded` autorise l'appel à l'API AWS ECS (`aws ecs run-task`) pour démarrer la tâche Fargate `dbt-run`.
4. **Gestion des erreurs** : En cas d'échec ou de chevauchement/timeout de la synchronisation Airbyte, le pipeline dbt est immédiatement bloqué, empêchant toute exécution sur des données partielles, et émet une alerte dans CloudWatch/SNS.

## Résultat obtenu
- Garantie absolue de séquence : Ingestion (2 min 30 s) ➔ Transformation dbt (1 min 15 s).
- Latence totale du pipeline de bout-en-bout : **225 secondes (3 minutes 45 secondes)**.
- Disponibilité garantie pour les utilisateurs métier avant 06h05 UTC.

## Fichiers techniques
- [orchestrate_pipeline.py](file:///c:/Users/docje/Documents/Code/Projet%208%20Construisez%20et%20testez%20une%20infrastructure%20de%20donn%C3%A9es/scripts/orchestrate_pipeline.py) : orchestrateur séquentiel Python.
- [main.tf](file:///c:/Users/docje/Documents/Code/Projet%208%20Construisez%20et%20testez%20une%20infrastructure%20de%20donn%C3%A9es/aws/terraform/main.tf) : définition de la tâche ECS Fargate et de la règle EventBridge.
- [Dockerfile.dbt](file:///c:/Users/docje/Documents/Code/Projet%208%20Construisez%20et%20testez%20une%20infrastructure%20de%20donn%C3%A9es/aws/Dockerfile.dbt) : conteneur de traitement dbt pour ECS.
