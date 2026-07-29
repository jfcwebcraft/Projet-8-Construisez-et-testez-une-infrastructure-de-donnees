# 5 — Alertes et Monitoring

## Ce que je démontre ici
Avoir des logs c'est bien, être prévenu en cas de crash, c'est mieux ! J'ai configuré des alarmes pour être alerté par e-mail en cas de comportement anormal de l'infrastructure ou du pipeline.

## Configuration mise en place
J'ai créé un topic **Amazon SNS** auquel je me suis abonné avec mon adresse e-mail. 
Ensuite, j'ai configuré deux alarmes CloudWatch liées à ce topic SNS :
1. **CPU RDS** : se déclenche si l'utilisation CPU de la base de données dépasse 80% pendant 2 périodes consécutives de 5 minutes.
2. **Échecs DBT** : se déclenche via un filtre de métrique sur les logs. Dès que le mot "ERROR" ou "Failure" apparaît dans les logs dbt, la métrique monte et l'alarme se déclenche.

## Résultat obtenu
Les alarmes sont bien créées et actives. Lors d'un test d'échec provoqué volontairement (voir dossier 8), l'alarme est bien passée en état "En alarme" (rouge) et j'ai immédiatement reçu le mail de notification SNS.

## Fichiers techniques
- ws/terraform/main.tf : création du topic SNS, des abonnements, des métriques personnalisées et des alarmes CloudWatch.
