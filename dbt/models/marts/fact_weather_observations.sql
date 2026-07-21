-- fact_weather_observations.sql
-- Table de faits principale : relevés météo enrichis et dénormalisés.
--
-- Granularité : 1 ligne = 1 relevé = 1 station × 1 horodatage.
-- Clés étrangères : station_id → dim_weather_stations
--                   date_jour  → dim_dates
--
-- Cette table est le point d'entrée unique pour les analyses des Data Scientists
-- (corrélation météo/demande d'électricité, features ML, etc.).

{{
    config(
        post_hook=[
            "COMMENT ON TABLE {{ this }} IS 'Table de faits des relevés météo GreenCoop Forecast 2.0 — granularité : 1 observation par station et par instant';"
        ]
    )
}}

with releves as (

    select * from {{ ref('int_releves_unifies') }}

),

final as (

    select
        -- Clé surrogate unique de l'observation
        md5(
            coalesce(id_station, '')
            || '|' ||
            coalesce(date_heure_utc::text, '')
            || '|' ||
            coalesce(source, '')
        )::uuid                         as observation_id,

        -- Clés étrangères vers les dimensions
        id_station                      as station_id,
        date_heure_utc::date            as date_jour,

        -- Horodatages
        date_heure_utc,

        -- Mesures météo (toutes converties en unités SI)
        temperature_c,
        point_rosee_c,
        humidite_pct,
        pression_hpa,
        vent_moyen_kmh,
        vent_rafales_kmh,
        vent_direction,
        precipitations_1h_mm,
        taux_precipitation_mm,
        cumul_precipitation_mm,
        visibilite_m,
        uv_index,
        rayonnement_solaire_wm2,
        neige_sol_cm,
        nebulosite_octas,
        code_temps_omm,

        -- Traçabilité de la source
        source,
        raw_id

    from releves

)

select * from final
