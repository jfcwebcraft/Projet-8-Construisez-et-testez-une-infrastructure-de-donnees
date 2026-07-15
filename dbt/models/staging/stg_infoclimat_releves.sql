-- stg_infoclimat_releves.sql
-- Standardisation des relevés météo InfoClimat.
-- Les données sont déjà en unités SI (°C, km/h, hPa, mm) et déjà typées par
-- le connecteur Airbyte Destinations V2. Ce modèle se limite au renommage,
-- au parsing de l'horodatage et à un typage explicite des colonnes.

with source as (

    select
        _airbyte_raw_id,
        _airbyte_extracted_at,
        id_station,
        dh_utc,
        temperature,
        pression,
        humidite,
        point_de_rosee,
        visibilite,
        vent_moyen,
        vent_rafales,
        vent_direction,
        pluie_1h,
        pluie_3h,
        neige_au_sol,
        nebulosite,
        temps_omm
    from {{ source('raw_airbyte', 'infoclimat_releves') }}

),

renamedcast as (

    select
        _airbyte_raw_id,
        _airbyte_extracted_at,

        id_station,

        -- Horodatage UTC du relevé
        to_timestamp(dh_utc, 'YYYY-MM-DD HH24:MI:SS') at time zone 'UTC'  as date_heure_utc,

        temperature::numeric(6,2)        as temperature_c,
        pression::numeric(7,2)           as pression_hpa,
        humidite::smallint               as humidite_pct,
        point_de_rosee::numeric(6,2)     as point_rosee_c,
        visibilite::integer              as visibilite_m,
        vent_moyen::numeric(6,2)         as vent_moyen_kmh,
        vent_rafales::numeric(6,2)       as vent_rafales_kmh,
        vent_direction::smallint         as vent_direction_deg,
        pluie_1h::numeric(6,2)           as precipitations_1h_mm,
        pluie_3h::numeric(6,2)           as precipitations_3h_mm,
        neige_au_sol::numeric(6,1)       as neige_sol_cm,
        nebulosite::smallint             as nebulosite_octas,
        temps_omm::smallint              as code_temps_omm,

        'infoclimat'                      as source

    from source

)

select * from renamedcast
