-- stg_wunderground_releves.sql
-- Standardisation et conversion d'unités des relevés Weather Underground.
--
-- Les deux stations (Ichtegem BE et La Madeleine FR) partagent le même format
-- de fichier source (format Weather Underground, unités impériales).
-- Ce modèle unifie les deux tables RAW et convertit les unités :
--   - Température / point de rosée : °F → °C
--   - Vitesse du vent : mph → km/h
--   - Pression : pouces de mercure (inHg) → hPa
--   - Précipitations : pouces → mm
--
-- Les valeurs d'unité (ex : "56.8 °F") sont extraites par regex avant conversion.
-- Le connecteur Airbyte Destinations V2 livre ces champs comme VARCHAR
-- (texte + unité), le typage numérique reste donc nécessaire ici.

with ichtegem as (

    select
        _airbyte_raw_id,
        _airbyte_extracted_at,
        date_releve,
        heure_locale,
        temperature,
        point_de_rosee,
        humidite,
        direction_vent,
        vitesse_vent,
        rafale_vent,
        pression,
        taux_precipitation,
        cumul_precipitation,
        uv,
        rayonnement_solaire,
        'IICHTE19' as id_station
    from {{ source('raw_airbyte', 'wunderground_ichtegem') }}

),

la_madeleine as (

    select
        _airbyte_raw_id,
        _airbyte_extracted_at,
        date_releve,
        heure_locale,
        temperature,
        point_de_rosee,
        humidite,
        direction_vent,
        vitesse_vent,
        rafale_vent,
        pression,
        taux_precipitation,
        cumul_precipitation,
        uv,
        rayonnement_solaire,
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

        -- Horodatage : combinaison date (date_releve) + heure (heure_locale HH:MM:SS)
        (
            date_releve || ' ' ||
            to_char(
                to_timestamp(trim(heure_locale), 'HH24:MI:SS'),
                'HH24:MI:SS'
            )
        )::timestamp                                                       as date_heure_locale,

        -- Température brute (ex: "56.8 °F") → extraction numérique
        (regexp_match(temperature, '[\-0-9.]+'))[1]::numeric              as temperature_f_raw,

        -- Point de rosée brut
        (regexp_match(point_de_rosee, '[\-0-9.]+'))[1]::numeric          as point_rosee_f_raw,

        -- Humidité (ex: "87 %")
        (regexp_match(humidite, '[0-9]+'))[1]::smallint                  as humidite_pct,

        -- Direction du vent (texte cardinal : WSW, NNW, etc.)
        direction_vent                                                    as direction_vent_cardinal,

        -- Vitesse vent (ex: "8.2 mph")
        (regexp_match(vitesse_vent, '[0-9.]+'))[1]::numeric               as vitesse_vent_mph_raw,

        -- Rafale vent
        (regexp_match(rafale_vent, '[0-9.]+'))[1]::numeric                as rafale_vent_mph_raw,

        -- Pression (ex: "29.48 in")
        (regexp_match(pression, '[0-9.]+'))[1]::numeric                  as pression_inhg_raw,

        -- Taux de précipitation (ex: "0.00 in")
        (regexp_match(taux_precipitation, '[0-9.]+'))[1]::numeric        as taux_precip_in_raw,

        -- Cumul de précipitation
        (regexp_match(cumul_precipitation, '[0-9.]+'))[1]::numeric       as cumul_precip_in_raw,

        -- UV (déjà numérique)
        uv::smallint                                                     as uv_index,

        -- Rayonnement solaire (ex: "0 w/m²")
        (regexp_match(rayonnement_solaire, '[0-9]+'))[1]::integer        as rayonnement_solaire_wm2

    from toutes_stations

),

conversion as (

    select
        _airbyte_raw_id,
        _airbyte_extracted_at,
        id_station,
        date_heure_locale,

        -- Conversions unités impériales → SI
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
