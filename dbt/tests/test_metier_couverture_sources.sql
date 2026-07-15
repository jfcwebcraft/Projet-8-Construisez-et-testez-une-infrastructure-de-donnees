-- test_metier_couverture_sources.sql
-- Vérifie que les 6 stations attendues ont bien des données dans la table de faits.
-- Si une station est absente, la requête retourne une ligne (= test en échec).

select
    s.station_id,
    count(f.observation_id) as nb_observations
from {{ ref('dim_weather_stations') }} s
left join {{ ref('fact_weather_observations') }} f
    on s.station_id = f.station_id
group by s.station_id
having count(f.observation_id) = 0
