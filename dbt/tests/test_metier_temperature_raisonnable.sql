-- test_metier_temperature_raisonnable.sql
-- Test métier personnalisé : vérifie qu'aucune observation n'a une température
-- aberrante pour les Hauts-de-France en octobre (plage attendue : -5°C à 35°C).
-- Tout enregistrement retourné par cette requête est considéré comme un échec.

select
    observation_id,
    station_id,
    date_heure_utc,
    temperature_c,
    source
from {{ ref('fact_weather_observations') }}
where
    temperature_c is not null
    and (temperature_c < -5 or temperature_c > 35)
