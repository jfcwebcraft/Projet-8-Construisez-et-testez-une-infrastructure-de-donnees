# 7 — Indexation et Performances PostgreSQL

## Ce que je démontre ici
Pour garantir de bonnes performances lors des requêtes sur le Data Warehouse, j'ai implémenté des index directement depuis dbt, afin qu'ils soient recréés automatiquement lors des builds.

## Configuration mise en place
Dans mon fichier dbt_project.yml, au niveau du schéma marts, j'ai déclaré plusieurs index :
- Sur act_weather_observations : index sur station_id (clé étrangère de jointure), date_heure_utc (pour les tris et filtres temporels), et date_jour.
- Sur dim_weather_stations : index unique sur station_id.

**Justification :** La table de faits étant destinée à grossir, les filtres sur la station et la date seront systématiques dans les dashboards de GreenCoop. Les index évitent un scan complet de la table (Seq Scan).

## Résultat obtenu
En exécutant le script de vérification qui lance la commande PostgreSQL \d+, on voit que les index B-Tree ont bien été créés dans le moteur de la base.
De plus, l'exécution d'un EXPLAIN ANALYZE sur une requête simulant un dashboard montre l'utilisation d'un **Bitmap Index Scan**, offrant un temps de réponse extrêmement bas (autour de 1 à 2 millisecondes).

## Fichiers techniques
- dbt/dbt_project.yml : définition des index.
