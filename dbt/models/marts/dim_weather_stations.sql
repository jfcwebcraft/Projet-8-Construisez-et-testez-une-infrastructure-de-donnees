-- dim_weather_stations.sql
-- Dimension des stations météo du projet Forecast 2.0.
--
-- Cette dimension intègre les métadonnées de toutes les sources :
--   - Les 4 stations InfoClimat (réseau professionnel / synop)
--   - Les 2 stations Weather Underground (réseau amateur)
--
-- Le seed dim_stations_seed.csv contient les métadonnées statiques
-- (notamment celles des stations WUnderground non disponibles via API).
-- Les données dynamiques (latitude, longitude, altitude) proviennent
-- en priorité du staging InfoClimat, qui les maintient à jour.

with seed as (

    select
        station_id,
        nom_station,
        latitude::numeric(9,6)     as latitude,
        longitude::numeric(9,6)    as longitude,
        altitude_m::integer        as altitude_m,
        type_station,
        source,
        hardware,
        software,
        notes
    from {{ ref('dim_stations_seed') }}

),

infoclimat_meta as (

    -- Surcharge des coordonnées avec les valeurs live du staging InfoClimat
    select
        id_station      as station_id,
        nom_station,
        latitude,
        longitude,
        altitude_m,
        type_station,
        source
    from {{ ref('stg_infoclimat_stations') }}

),

-- Fusion : priorité aux données InfoClimat pour les champs en commun
final as (

    select
        s.station_id,
        coalesce(i.nom_station, s.nom_station)      as nom_station,
        coalesce(i.latitude,    s.latitude)         as latitude,
        coalesce(i.longitude,   s.longitude)        as longitude,
        coalesce(i.altitude_m,  s.altitude_m)       as altitude_m,
        coalesce(i.type_station, s.type_station)    as type_station,
        s.source,
        s.hardware,
        s.software,
        s.notes
    from seed s
    left join infoclimat_meta i on s.station_id = i.station_id

)

select * from final
