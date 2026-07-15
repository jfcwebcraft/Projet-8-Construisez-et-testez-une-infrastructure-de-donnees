-- test_metier_coherence_pression.sql
-- Vérifie que la pression atmosphérique est dans la plage cohérente pour
-- une zone de plaine (Hauts-de-France, altitude < 50 m) : 950-1060 hPa.

select
    observation_id,
    station_id,
    date_heure_utc,
    pression_hpa,
    source
from {{ ref('fact_weather_observations') }}
where
    pression_hpa is not null
    and (pression_hpa < 950 or pression_hpa > 1060)
