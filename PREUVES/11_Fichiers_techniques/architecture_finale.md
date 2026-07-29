# Diagramme d'Architecture Final (Projet 8 - Forecast 2.0)

Ce diagramme peut être utilisé dans ta présentation pour illustrer le flux de données (Point 11 & 12).

```mermaid
graph TD
    subgraph Sources ["Sources de données externes"]
        IC[API InfoClimat]
        WU[API Weather Underground]
    end

    subgraph AirbyteCloud ["Airbyte Cloud (Ingestion)"]
        AC[Connecteurs Sources] --> |Synchronisation 24h| AC_DEST[Connecteur Destination PostgreSQL]
    end

    subgraph AWS ["Infrastructure AWS (Production)"]
        subgraph VPC ["VPC par défaut (eu-west-3)"]
            
            subgraph Security ["Sécurité & Contrôle d'accès"]
                SM[(Secrets Manager)]
                IAM[Rôles IAM & Politiques]
            end
            
            subgraph DataWarehouse ["Couche Stockage (RDS)"]
                RDS[(RDS PostgreSQL<br/>weather_dwh)]
                SG_RDS{Security Group RDS<br/>Port 5432 Inbound}
                SG_RDS -.->|Protège| RDS
            end
            
            subgraph Transformation ["Couche Transformation (ECS)"]
                ECS[ECS Fargate Task<br/>Conteneur dbt build]
                SG_ECS{Security Group ECS<br/>Outbound uniquement}
                SG_ECS -.->|Protège| ECS
            end
            
        end
        
        subgraph Orchestration ["Orchestration & Monitoring"]
            EB((EventBridge<br/>Cron 06:00 UTC))
            CW[CloudWatch Logs<br/>& Alarmes métriques]
            SNS((SNS Topic<br/>Alertes E-mail))
        end
    end

    %% Flux d'Ingestion
    IC --> AC
    WU --> AC
    AC_DEST -->|Extrait & Charge (RAW)| SG_RDS

    %% Flux de Transformation
    EB -->|Déclenche la tâche| ECS
    ECS -->|Lit & Écrit (Staging, Inter, Marts)| SG_RDS
    SM -.->|Injecte DB Credentials| ECS

    %% Flux de Monitoring
    ECS -->|Envoie Logs dbt| CW
    CW -->|Si 'Failure' (Filtre métrique)| SNS
    SNS -.->|Notification| User((Administrateur<br/>Email))
    
    %% Styles
    classDef aws fill:#FF9900,stroke:#232F3E,stroke-width:2px,color:black;
    classDef db fill:#336699,stroke:#FFFFFF,stroke-width:2px,color:white;
    classDef ecs fill:#D2691E,stroke:#FFFFFF,stroke-width:2px,color:white;
    classDef airbyte fill:#6951FF,stroke:#FFFFFF,stroke-width:2px,color:white;
    
    class RDS db;
    class ECS ecs;
    class AC,AC_DEST airbyte;
    class SM,IAM,EB,CW,SNS,SG_RDS,SG_ECS aws;
```
