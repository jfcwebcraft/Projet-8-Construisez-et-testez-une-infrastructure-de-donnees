-- test_metier_humidite_valide.sql
-- Vérifie qu'aucune humidité n'est en dehors de la plage physiquement possible (0-100%).
-- Les valeurs à NULL sont tolérées (données absentes de certaines stations).

select
    observation_id,
    station_id,
    date_heure_utc,
    humidite_pct,
    source
from {{ ref('fact_weather_observations') }}
where
    humidite_pct is not null
    and (humidite_pct < 0 or humidite_pct > 100)
