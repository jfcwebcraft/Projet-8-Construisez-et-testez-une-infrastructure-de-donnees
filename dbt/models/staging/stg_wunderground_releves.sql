-- stg_wunderground_releves.sql
-- Standardisation et conversion d'unités des relevés Weather Underground.

with ichtegem as (
    select
        _airbyte_raw_id,
        _airbyte_extracted_at,
        CAST(_airbyte_extracted_at AS DATE) as date_releve,
        "Time" as heure_locale,
        "Temperature" as temperature,
        "Dew_Point" as point_de_rosee,
        "Humidity" as humidite,
        "Wind" as direction_vent,
        "Speed" as vitesse_vent,
        "Gust" as rafale_vent,
        "Pressure" as pression,
        "Precip__Rate_" as taux_precipitation,
        "Precip__Accum_" as cumul_precipitation,
        "UV" as uv,
        "Solar" as rayonnement_solaire,
        'IICHTE19' as id_station
    from {{ source('raw_airbyte', 'wunderground_ichtegem') }}
),

la_madeleine as (
    select
        _airbyte_raw_id,
        _airbyte_extracted_at,
        CAST(_airbyte_extracted_at AS DATE) as date_releve,
        "Time" as heure_locale,
        "Temperature" as temperature,
        "Dew_Point" as point_de_rosee,
        "Humidity" as humidite,
        "Wind" as direction_vent,
        "Speed" as vitesse_vent,
        "Gust" as rafale_vent,
        "Pressure" as pression,
        "Precip__Rate_" as taux_precipitation,
        "Precip__Accum_" as cumul_precipitation,
        "UV" as uv,
        "Solar" as rayonnement_solaire,
        'ILAMAD25' as id_station
    from {{ source('raw_airbyte', 'wunderground_la_madeleine') }}
),

toutes_stations as (
    select * from ichtegem
    union all
    select * from la_madeleine
),

extraction as (
    select
        _airbyte_raw_id,
        _airbyte_extracted_at,
        id_station,

        -- Horodatage
        (
            date_releve::text || ' ' ||
            to_char(
                to_timestamp(trim(heure_locale), 'HH24:MI:SS'),
                'HH24:MI:SS'
            )
        )::timestamp                                                       as date_heure_locale,

        -- Température brute
        (regexp_match(temperature, '[\-0-9.]+'))[1]::numeric              as temperature_f_raw,

        -- Point de rosée brut
        (regexp_match(point_de_rosee, '[\-0-9.]+'))[1]::numeric          as point_rosee_f_raw,

        -- Humidité
        (regexp_match(humidite, '[0-9]+'))[1]::smallint                  as humidite_pct,

        -- Direction du vent
        direction_vent                                                    as direction_vent_cardinal,

        -- Vitesse vent
        (regexp_match(vitesse_vent, '[0-9.]+'))[1]::numeric               as vitesse_vent_mph_raw,

        -- Rafale vent
        (regexp_match(rafale_vent, '[0-9.]+'))[1]::numeric                as rafale_vent_mph_raw,

        -- Pression
        (regexp_match(pression, '[0-9.]+'))[1]::numeric                  as pression_inhg_raw,

        -- Taux de précipitation
        (regexp_match(taux_precipitation, '[0-9.]+'))[1]::numeric        as taux_precip_in_raw,

        -- Cumul de précipitation
        (regexp_match(cumul_precipitation, '[0-9.]+'))[1]::numeric       as cumul_precip_in_raw,

        -- UV
        uv::numeric::smallint                                            as uv_index,

        -- Rayonnement solaire
        (regexp_match(rayonnement_solaire, '[0-9.]+'))[1]::numeric::integer        as rayonnement_solaire_wm2

    from toutes_stations
),

conversion as (
    select
        _airbyte_raw_id,
        _airbyte_extracted_at,
        id_station,
        date_heure_locale,

        -- Conversions
        round((temperature_f_raw  - 32) * 5.0 / 9.0, 2)  as temperature_c,
        round((point_rosee_f_raw  - 32) * 5.0 / 9.0, 2)  as point_rosee_c,
        humidite_pct,
        direction_vent_cardinal,
        round(vitesse_vent_mph_raw * 1.60934, 2)           as vent_moyen_kmh,
        round(rafale_vent_mph_raw  * 1.60934, 2)           as vent_rafales_kmh,
        round(pression_inhg_raw    * 33.8639, 2)           as pression_hpa,
        round(taux_precip_in_raw   * 25.4,    2)           as taux_precipitation_mm,
        round(cumul_precip_in_raw  * 25.4,    2)           as cumul_precipitation_mm,
        uv_index,
        rayonnement_solaire_wm2,

        'weather_underground'                              as source

    from extraction
)

select * from conversion
