# 8 — Démonstration de l'Échec de Test dbt & Blocage Strict des Données Invalides

## Ce que je démontre ici
Ce dossier démontre la tolérance aux pannes et la politique de **qualité bloquante (Fail-Fast)** du pipeline dbt. 

Si une donnée invalide ou aberrante franchit la couche d'ingestion brute, les tests dbt au niveau staging interceptent immédiatement l'anomalie, font échouer la commande `dbt build`, et **bloquent strictement l'exécution du DAG**. Les tables finales (`marts.fact_weather_observations`) conservent ainsi leur état sain antérieur sans être corrompues.

## Démonstration pas-à-pas
Le script `scripts/demo_test_dbt_echec.py` orchestre la preuve d'isolation :
1. **État sain initial** : Comptage SQL sur `marts_marts.fact_weather_observations` ➔ **4 950 observations valides**.
2. **Injection d'anomalie** : Insertion d'un enregistrement corrompu avec une température de `999.0°C` dans la table brute `raw_airbyte.infoclimat_releves`.
3. **Exécution de dbt build** :
   - Le test personnalisé `test_metier_temperature_raisonnable` (seuil max +60°C) s'exécute lors du passage de la couche staging.
   - dbt renvoie une erreur explicite : `FAIL 1 test_metier_temperature_raisonnable`.
   - **Interruption du DAG dbt** : dbt marque les modèles dépendants de la couche marts comme `CANCELLED` / `SKIPPED`.
4. **Vérification SQL d'isolation (Preuve d'arrêt)** :
   - Requête SQL exécutée sur la table finale `marts_marts.fact_weather_observations` :
     - Observations avec température > 60°C : **0** (aucune donnée corrompue n'a franchi le staging).
     - Volume total conservé : **exactement 4 950 observations sains**.
5. **Alerte CloudWatch & SNS** : L'échec génère un filtre de métrique CloudWatch qui déclenche une notification par e-mail via Amazon SNS.
6. **Nettoyage et Reprise** : Suppression de la donnée de test et ré-exécution de `dbt build` ➔ retour au statut **PASS=64 WARN=0 ERROR=0**.

## Fichiers techniques
- [demo_test_dbt_echec.py](file:///c:/Users/docje/Documents/Code/Projet%208%20Construisez%20et%20testez%20une%20infrastructure%20de%20donn%C3%A9es/scripts/demo_test_dbt_echec.py) : script d'injection, de test, de vérification SQL et de nettoyage.
- [test_metier_temperature_raisonnable.sql](file:///c:/Users/docje/Documents/Code/Projet%208%20Construisez%20et%20testez%20une%20infrastructure%20de%20donn%C3%A9es/dbt/tests/test_metier_temperature_raisonnable.sql) : test dbt singulier interceptant l'erreur.
